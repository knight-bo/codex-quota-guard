import argparse
import json
import random
import sys
import time
from pathlib import Path
from .core import Guard, Policy, number
from .rpc import RPC
from .state import ManagedStop, State


def main(argv=None):
    p = argparse.ArgumentParser(description='Conservative Codex quota alerts; POSIX / Python 3.10+')
    p.add_argument('mode', choices=['simulate', 'read', 'watch', 'check'])
    p.add_argument('--bucket', required=True, help='Explicit metered limitId; no automatic bucket choice')
    p.add_argument('--threshold', type=float, default=10)
    p.add_argument('--buffer', type=float, default=2, help='Percentage points added to threshold')
    p.add_argument('--max-age', type=float, default=90)
    p.add_argument('--interval', type=float, default=30)
    p.add_argument('--timeout', type=float, default=10)
    p.add_argument('--state-dir', default=str(Path.home()/'.local/state/codex-quota-guard'))
    p.add_argument('--fixture')
    p.add_argument('--managed-thread')
    p.add_argument('--managed-turn')
    p.add_argument('--allow-interrupt', action='store_true')
    a = p.parse_args(argv)
    state = rpc = None
    try:
        policy = Policy(a.bucket, a.threshold, a.buffer, a.max_age)
        if not all(number(v) and v > 0 for v in (a.interval, a.timeout)):
            raise ValueError('invalid_timing')
        if bool(a.managed_thread) != bool(a.managed_turn):
            raise ValueError('incomplete_binding')
        if a.allow_interrupt and (a.mode != 'watch' or not a.managed_thread):
            raise ValueError('interrupt_requires_watch_and_binding')
        if a.mode == 'check':
            # Read an atomic snapshot while the monitor holds its writer lock.
            state = State(a.state_dir, readonly=True)
            d = state.data.get('decision', {})
            now = time.time()
            ok = (state.data.get('provenance') == 'live' and
                  state.data.get('policy') == vars(policy) and
                  d.get('allow_new_work') is True and
                  number(d.get('observed_at')) and number(d.get('valid_until')) and
                  d['observed_at'] <= now < d['valid_until'])
            print(json.dumps({'allow_new_work': ok, 'reason': 'healthy' if ok else 'unavailable'}))
            return 0 if ok else 2
        state = State(a.state_dir)
        state.data['policy'] = vars(policy)
        state.data['provenance'] = 'synthetic' if a.mode == 'simulate' else 'live'
        guard = Guard(policy)
        state.save(guard.decision())  # Revoke prior cached permission before handshake.
        stopper = ManagedStop(state, a.managed_thread, a.managed_turn, a.allow_interrupt) if a.managed_thread else None

        def publish(now=None):
            d = guard.decision(now)
            if a.mode == 'simulate':
                d = dict(d, simulated_allow_new_work=d['allow_new_work'],
                         simulated_reason=d['reason'], allow_new_work=False,
                         reason='simulation_only')
            state.save(d)
            out = dict(d)
            if stopper and not d['allow_new_work']:
                out['managed_action'] = stopper.stop(rpc) if a.allow_interrupt and rpc else 'would_interrupt'
                out['checkpoint_status'] = 'unconfirmed'
            print(json.dumps(out), flush=True)
            return d

        if a.mode == 'simulate':
            if not a.fixture:
                raise ValueError('fixture_required')
            with open(a.fixture) as f:
                for line in f:
                    event = json.loads(line)
                    now = event['at']
                    if not number(now):
                        raise ValueError('invalid_fixture_time')
                    kind = event['kind']
                    if kind == 'read':
                        guard.ingest(event['payload'], now)
                    elif kind == 'updated':
                        guard.invalidate('notification_requires_read')
                    elif kind == 'error':
                        guard.invalidate('unavailable')
                    elif kind != 'tick':
                        raise ValueError('invalid_fixture_event')
                    publish(now)
            # Simulation state can NEVER authorize real work.
            guard.invalidate('simulation_only')
            state.save(guard.decision())
            return 0
        attempt = 0
        while True:
            try:
                if rpc is None:
                    rpc = RPC(timeout=a.timeout, on_update=lambda: (guard.invalidate('notification_requires_read'), state.save(guard.decision())))
                generation = rpc.generation
                payload = rpc.call('account/rateLimits/read')
                guard.ingest(payload)
                if rpc.generation != generation:
                    guard.invalidate('notification_requires_read')
                result = publish()
                attempt = 0
                if a.mode == 'read':
                    return 0 if result['allow_new_work'] else 2
                rpc.wait(min(a.interval, a.max_age))
            except Exception:
                guard.invalidate('transport_or_auth_error')
                publish()
                if rpc:
                    rpc.close()
                    rpc = None
                if a.mode == 'read':
                    return 2
                attempt += 1
                time.sleep(random.uniform(0.5, 1)*min(60, 2**min(attempt, 6)))
    except KeyboardInterrupt:
        return 130
    except Exception:
        # Deliberately suppress exception strings, raw server messages and paths.
        if state:
            try:
                state.save({'allow_new_work': False, 'reason': 'error', 'valid_until': None})
            except Exception:
                pass
        print('{"allow_new_work":false,"reason":"configuration_or_io_error"}', file=sys.stderr)
        return 2
    finally:
        cleanup_failed = False
        if state:
            try:
                # Daemon exit revokes permissions; read retains short-lived reading.
                if a.mode == 'watch':
                    state.save({'allow_new_work': False, 'reason': 'monitor_stopped', 'valid_until': None})
            except Exception:
                cleanup_failed = True
            finally:
                try:
                    state.close()
                except Exception:
                    cleanup_failed = True
        if rpc:
            try:
                rpc.close()
            except Exception:
                cleanup_failed = True
        if cleanup_failed:
            print('{"allow_new_work":false,"reason":"cleanup_or_state_error"}', file=sys.stderr)
            return 2


if __name__ == '__main__':
    sys.exit(main())
