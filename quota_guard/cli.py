import argparse
import json
import random
import sys
import time
import uuid
import signal
import threading
from pathlib import Path
from .core import Guard, Policy, number
from .rpc import RPC
from .state import ManagedStop, State
from .i18n import emit


class MonitorStopped(Exception):
    """Cooperative cancellation, not a transport failure or interrupt trigger."""


def main(argv=None):
    p = argparse.ArgumentParser(description='Conservative Codex quota alerts; POSIX / Python 3.10+')
    p.add_argument('mode', choices=['simulate', 'read', 'watch', 'start', 'stop', 'check'])
    p.add_argument('--bucket', help='Explicit metered limitId; no automatic bucket choice')
    p.add_argument('--threshold', '--reserve', dest='threshold', type=float, default=10)
    p.add_argument('--buffer', type=float, default=2, help='Percentage points added to threshold')
    p.add_argument('--max-age', type=float, default=90)
    p.add_argument('--interval', type=float, default=30)
    p.add_argument('--timeout', type=float, default=10)
    p.add_argument('--state-dir', default=str(Path.home()/'.local/state/codex-quota-guard'))
    p.add_argument('--fixture')
    p.add_argument('--managed-thread')
    p.add_argument('--managed-turn')
    p.add_argument('--allow-interrupt', action='store_true')
    p.add_argument('--format', choices=['json', 'text'], default='json', help='JSON is stable machine output; text is a localized human report')
    p.add_argument('--locale', default='en', help='Text language: en, zh, ru, ja, ko, es, fr, de, pt; unsupported values fall back to en')
    a = p.parse_args(argv)
    def output(report, stream=None):
        emit(report, a.format, a.locale, stream)
    if a.mode == 'start':
        a.mode = 'watch'
    if a.mode != 'stop' and not a.bucket:
        p.error('--bucket is required except for stop')
    state = rpc = None
    old_term = None
    try:
        if a.mode == 'stop':
            state = State(a.state_dir, readonly=True)
            requested = state.request_stop()
            output({'stop_requested': requested,
                'reason': 'stop_requested' if requested else 'no_active_monitor',
                'allow_new_work': False})
            return 0 if requested else 2
        if a.mode == 'watch' and threading.current_thread() is threading.main_thread():
            def terminate(signum, frame):
                raise KeyboardInterrupt()
            old_term = signal.signal(signal.SIGTERM, terminate)
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
            stop_pending = bool(state.data.get('monitor_token')) and state.stop_requested(state.data['monitor_token'])
            ok = (not stop_pending and state.data.get('provenance') == 'live' and
                  state.data.get('policy') == vars(policy) and
                  d.get('allow_new_work') is True and d.get('data_valid', True) is True and
                  number(d.get('observed_at')) and number(d.get('valid_until')) and
                  d['observed_at'] <= now < d['valid_until'])
            fresh = (number(d.get('observed_at')) and number(d.get('valid_until')) and
                     d['observed_at'] <= now < d['valid_until'])
            trusted = (not stop_pending and state.data.get('provenance') == 'live' and
                       state.data.get('policy') == vars(policy))
            out = dict(d, allow_new_work=ok, reported_at=now,
                       stale=not fresh, data_valid=bool(fresh and trusted and d.get('data_valid', True)),
                       reason=d.get('reason', 'healthy') if fresh and trusted else 'unavailable')
            output(out)
            return 0 if ok else 2
        state = State(a.state_dir)
        state.data['policy'] = vars(policy)
        state.data['provenance'] = 'synthetic' if a.mode == 'simulate' else 'live'
        token = uuid.uuid4().hex if a.mode == 'watch' else None
        state.data['monitor_token'] = token
        guard = Guard(policy)
        state.save(guard.decision())  # Revoke prior cached permission before handshake.
        stopper = ManagedStop(state, a.managed_thread, a.managed_turn, a.allow_interrupt) if a.managed_thread else None

        def stopped():
            return a.mode == 'watch' and state.stop_requested(token)

        def ensure_running():
            if stopped():
                raise MonitorStopped()

        def publish(now=None):
            ensure_running()
            d = guard.decision(now)
            if a.mode == 'simulate':
                d = dict(d, simulated_allow_new_work=d['allow_new_work'],
                         simulated_reason=d['reason'], allow_new_work=False,
                         reason='simulation_only', data_valid=False, data_source='synthetic')
            state.save(d)
            out = dict(d)
            if stopper and not d['allow_new_work']:
                ensure_running()
                out['managed_action'] = stopper.stop(rpc) if a.allow_interrupt and rpc else 'would_interrupt'
                out['checkpoint_status'] = 'unconfirmed'
            ensure_running()
            output(out)
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
        def wait(seconds, transport=False):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                if stopped():
                    return
                duration = min(1, deadline - time.monotonic())
                if duration <= 0:
                    break
                if transport:
                    rpc.wait(duration)
                else:
                    time.sleep(duration)

        def updated():
            guard.invalidate('notification_requires_read')
            decision = guard.decision()
            state.save(decision)
            # No recursive interrupt RPC from within the transport callback.
            output(decision)

        attempt = 0
        while True:
            ensure_running()
            try:
                if rpc is None:
                    rpc = RPC(timeout=a.timeout, on_update=updated)
                generation = rpc.generation
                payload = rpc.call('account/rateLimits/read')
                ensure_running()
                guard.ingest(payload)
                if rpc.generation != generation:
                    guard.invalidate('notification_requires_read')
                result = publish()
                attempt = 0
                if a.mode == 'read':
                    return 0 if result['allow_new_work'] else 2
                wait(min(a.interval, a.max_age), transport=True)
            except MonitorStopped:
                raise
            except Exception:
                ensure_running()
                guard.invalidate('transport_or_auth_error')
                publish()
                if rpc:
                    rpc.close()
                    rpc = None
                if a.mode == 'read':
                    return 2
                attempt += 1
                wait(random.uniform(0.5, 1)*min(60, 2**min(attempt, 6)))
    except MonitorStopped:
        output({'allow_new_work': False, 'reason': 'monitor_stopped', 'data_valid': False})
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception:
        # Deliberately suppress exception strings, raw server messages and paths.
        if state and a.mode not in ('check', 'stop'):
            try:
                state.save({'allow_new_work': False, 'reason': 'error', 'valid_until': None})
            except Exception:
                pass
        output({'allow_new_work': False, 'reason': 'configuration_or_io_error'}, sys.stderr)
        return 2
    finally:
        cleanup_failed = False
        if rpc:
            try:
                rpc.close()
            except Exception:
                cleanup_failed = True
        if state:
            try:
                # Revoke before releasing the writer lock. Clean one-shot reads
                # retain only their short-lived snapshot.
                if a.mode == 'watch' or (cleanup_failed and a.mode not in ('check', 'stop')):
                    state.data['monitor_token'] = None
                    state.save({'allow_new_work': False,
                                'reason': 'cleanup_or_state_error' if cleanup_failed else 'monitor_stopped',
                                'valid_until': None, 'data_valid': False})
            except Exception:
                cleanup_failed = True
            finally:
                try:
                    state.close()
                except Exception:
                    cleanup_failed = True
        if old_term is not None:
            signal.signal(signal.SIGTERM, old_term)
        if cleanup_failed:
            output({'allow_new_work': False, 'reason': 'cleanup_or_state_error'}, sys.stderr)
            return 2



if __name__ == '__main__':
    sys.exit(main())
