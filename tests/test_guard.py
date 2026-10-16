import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from quota_guard.core import Guard, Policy
from quota_guard.state import State, ManagedStop
from quota_guard.rpc import RPC, RpcError
from quota_guard.cli import main


def payload(used=20, reset=2000, secondary=None):
    return {'rateLimits': {'limitId': 'demo', 'primary': {
        'usedPercent': used, 'windowDurationMins': 300, 'resetsAt': reset},
        'secondary': secondary}}


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.g = Guard(Policy('demo'))

    def test_missing(self):
        self.assertFalse(self.g.decision(1000)['allow_new_work'])

    def test_threshold(self):
        for used, expected in [(87, True), (88, False), (90, False), (100, False)]:
            self.g.ingest(payload(used), 1000)
            self.assertEqual(self.g.decision(1000)['allow_new_work'], expected)

    def test_all_windows(self):
        self.g.ingest(payload(20, secondary={'usedPercent': 95,
            'windowDurationMins': 10080, 'resetsAt': 9000}), 1000)
        self.assertEqual(self.g.decision(1000)['reason'], 'low_quota')

    def test_invalid_percent(self):
        for v in (-1, 101, float('nan'), float('inf'), True, '12', None):
            self.g.ingest(payload(v), 1000)
            self.assertFalse(self.g.decision(1000)['allow_new_work'])

    def test_stale_reset_clock(self):
        self.g.ingest(payload(reset=1050), 1000)
        for now in (999, 1050, 1100):
            self.assertFalse(self.g.decision(now)['allow_new_work'])
        self.g.ingest(payload(reset=3000), 1051)
        self.assertTrue(self.g.decision(1051)['allow_new_work'])

    def test_order(self):
        self.g.ingest(payload(80), 1000)
        self.g.ingest(payload(20), 1001)
        self.assertEqual(self.g.decision(1001)['reason'], 'out_of_order')
        self.g.ingest(payload(20, 3000), 1002)
        self.assertTrue(self.g.decision(1002)['allow_new_work'])
        self.g.ingest(payload(90, 2000), 1003)
        self.assertFalse(self.g.decision(1003)['allow_new_work'])

    def test_bucket(self):
        p = payload()
        p['rateLimitsByLimitId'] = {'other': p['rateLimits']}
        self.g.ingest(p, 1000)
        self.assertFalse(self.g.decision(1000)['allow_new_work'])

    def test_missing_secondary(self):
        p = payload()
        del p['rateLimits']['secondary']
        self.g.ingest(p, 1000)
        self.assertFalse(self.g.decision(1000)['allow_new_work'])

    def test_invalid_policy(self):
        for kwargs in ({'threshold': -1}, {'buffer': 101}, {'max_age': 0}, {'buffer': float('nan')}):
            with self.assertRaises(ValueError):
                Policy('demo', **kwargs)

    def test_reached(self):
        p = payload()
        p['rateLimits']['rateLimitReachedType'] = 'unknown_future_type'
        self.g.ingest(p, 1000)
        self.assertFalse(self.g.decision(1000)['allow_new_work'])


class StateTests(unittest.TestCase):
    def test_lock_and_atomic_reader(self):
        with tempfile.TemporaryDirectory() as d:
            s = State(d)
            with self.assertRaises(BlockingIOError):
                State(d)
            s.save({'allow_new_work': False})
            r = State(d, readonly=True)
            self.assertFalse(r.data['decision']['allow_new_work'])
            r.close()
            s.close()

    def test_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            os.symlink('/dev/null', Path(d)/'state.json')
            with self.assertRaises(OSError):
                State(d)

    def test_stop_idempotent_restart(self):
        class Fake:
            calls = []
            def call(self, method, params):
                self.calls.append((method, params))
                return {}
        with tempfile.TemporaryDirectory() as d:
            s, rpc = State(d), Fake()
            self.assertEqual(ManagedStop(s, 't', 'u').stop(rpc), 'would_interrupt')
            self.assertEqual(rpc.calls, [])
            stop = ManagedStop(s, 't', 'u', True)
            stop.stop(rpc)
            stop.stop(rpc)
            s.close()
            s = State(d)
            ManagedStop(s, 't', 'u', True).stop(rpc)
            self.assertEqual(len(rpc.calls), 1)
            self.assertEqual(rpc.calls[0][1], {'threadId': 't', 'turnId': 'u'})
            s.close()

    def test_ambiguous_stop(self):
        class Fake:
            def call(self, *a):
                raise TimeoutError('sensitive text')
        with tempfile.TemporaryDirectory() as d:
            s = State(d)
            stop = ManagedStop(s, 't', 'u', True)
            self.assertEqual(stop.stop(Fake()), 'pending_unknown')
            self.assertEqual(stop.stop(None), 'pending_unknown')
            self.assertNotIn('sensitive', (Path(d)/'state.json').read_text())
            s.close()

    def test_simulation_never_authorizes(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['simulate', '--bucket', 'demo', '--state-dir', d,
                                  '--fixture', 'fixtures/demo.jsonl']), 0)
            self.assertEqual(main(['check', '--bucket', 'demo', '--state-dir', d]), 2)


class RpcTests(unittest.TestCase):
    def server(self, tail):
        code = '''import sys,json,time
m=json.loads(sys.stdin.readline())
assert m['method']=='initialize'
print(json.dumps({'id':m['id'],'result':{}}),flush=True)
assert json.loads(sys.stdin.readline())['method']=='initialized'
''' + tail
        return RPC([sys.executable, '-u', '-c', code], timeout=0.3)

    def test_handshake_notifications_fragmented_reply(self):
        rpc = self.server('''m=json.loads(sys.stdin.readline())
print(json.dumps({'method':'account/rateLimits/updated','params':{'secret':'never log'}}),flush=True)
s=json.dumps({'id':m['id'],'result':{'ok':True}})+'\\n'
for c in s:
 sys.stdout.write(c); sys.stdout.flush()
time.sleep(2)
''')
        try:
            self.assertTrue(rpc.call('account/rateLimits/read')['ok'])
            self.assertEqual(rpc.generation, 1)
        finally:
            rpc.close()

    def test_timeout_eof_invalid_and_remote_error(self):
        for code in ["time.sleep(2)", "sys.exit(0)", "print('bad json',flush=True)",
                     "m=json.loads(sys.stdin.readline()); print(json.dumps({'id':m['id'],'error':{'message':'private'}}),flush=True)"]:
            rpc = self.server(code)
            try:
                with self.assertRaises(RpcError) as cm:
                    rpc.call('account/rateLimits/read')
                self.assertNotIn('private', str(cm.exception))
            finally:
                rpc.close()

    def test_method_allowlist(self):
        rpc = self.server('time.sleep(2)')
        try:
            with self.assertRaises(RpcError):
                rpc.call('account/login/start')
        finally:
            rpc.close()

class RegressionTests(unittest.TestCase):
    def test_oversized_frame(self):
        rpc = RpcTests().server("m=json.loads(sys.stdin.readline()); print('x'*1100000,flush=True)")
        try:
            with self.assertRaises(RpcError):
                rpc.call('account/rateLimits/read')
        finally:
            rpc.close()

    def test_missing_window_after_known(self):
        g = Guard(Policy('demo'))
        g.ingest(payload(secondary={'usedPercent': 30, 'windowDurationMins': 10080, 'resetsAt': 5000}), 1000)
        g.ingest(payload(30), 1001)
        self.assertFalse(g.decision(1001)['allow_new_work'])

    def test_watch_reconnect_and_revoke(self):
        from unittest.mock import patch
        class Fake:
            generation = 0
            count = 0
            def __init__(self, **kwargs):
                Fake.count += 1
            def call(self, *args):
                if Fake.count == 1:
                    raise RpcError('remote_error')
                raise KeyboardInterrupt()
            def close(self):
                pass
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()), patch('quota_guard.cli.RPC', Fake), patch('quota_guard.cli.time.sleep') as sleep:
            self.assertEqual(main(['watch', '--bucket', 'demo', '--state-dir', d]), 130)
            self.assertEqual(Fake.count, 2)
            self.assertTrue(0 < sleep.call_args.args[0] <= 60)
            saved = json.loads((Path(d)/'state.json').read_text())
            self.assertFalse(saved['decision']['allow_new_work'])

    def test_notification_race(self):
        from unittest.mock import patch
        import time
        class Fake:
            generation = 0
            def __init__(self, **kwargs):
                pass
            def call(self, *args):
                self.generation += 1
                return payload(reset=time.time()+1000)
            def close(self):
                pass
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()) as out, patch('quota_guard.cli.RPC', Fake):
            self.assertEqual(main(['read', '--bucket', 'demo', '--state-dir', d]), 2)
            self.assertIn('notification_requires_read', out.getvalue())

    def test_policy_mismatch_and_expiry(self):
        import time
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            s = State(d)
            s.data['policy'] = vars(Policy('demo'))
            s.data['provenance'] = 'live'
            s.save({'allow_new_work': True, 'observed_at': time.time(), 'valid_until': time.time()+30})
            self.assertEqual(main(['check', '--bucket', 'demo', '--state-dir', d]), 0)
            self.assertEqual(main(['check', '--bucket', 'other', '--state-dir', d]), 2)
            s.save({'allow_new_work': True, 'observed_at': 1, 'valid_until': 2})
            self.assertEqual(main(['check', '--bucket', 'demo', '--state-dir', d]), 2)
            s.close()

    def test_bad_cli_options_are_redacted(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stderr(io.StringIO()) as out:
            self.assertEqual(main(['read', '--bucket', 'demo', '--allow-interrupt', '--state-dir', d]), 2)
            self.assertEqual(json.loads(out.getvalue())['reason'], 'configuration_or_io_error')


class FailureRedactionTests(unittest.TestCase):
    def test_state_io_failure_never_prints_path(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stderr(io.StringIO()) as out, patch('quota_guard.cli.State.save', side_effect=OSError('private-path-or-secret')):
            self.assertEqual(main(['watch', '--bucket', 'demo', '--state-dir', d]), 2)
            self.assertNotIn('private-path-or-secret', out.getvalue())


class SimulationProvenanceTests(unittest.TestCase):
    def run_replay_observer(self, interrupt=False):
        from unittest.mock import patch
        import time
        original_save = State.save
        observed = []
        with tempfile.TemporaryDirectory() as d:
            fixture = Path(d)/'healthy.jsonl'
            fixture.write_text(json.dumps({'at': time.time(), 'kind': 'read',
                                          'payload': payload(reset=time.time()+1000)})+'\n')
            def intercept(state, decision):
                original_save(state, decision)
                observed.append(json.loads((Path(d)/'state.json').read_text()))
                # Separate process reads while the simulator owns the writer lock.
                import subprocess
                check = subprocess.run([sys.executable, '-m', 'quota_guard', 'check',
                                        '--bucket', 'demo', '--state-dir', d],
                                       capture_output=True, text=True, timeout=5)
                self.assertEqual(check.returncode, 2)
                self.assertFalse(json.loads(check.stdout)['allow_new_work'])
                if interrupt and 'simulated_allow_new_work' in decision:
                    raise KeyboardInterrupt()
            with contextlib.redirect_stdout(io.StringIO()), patch.object(State, 'save', intercept):
                code = main(['simulate', '--bucket', 'demo', '--state-dir', d,
                             '--fixture', str(fixture)])
            self.assertEqual(code, 130 if interrupt else 0)
            self.assertGreaterEqual(len(observed), 2)
            for snapshot in observed:
                self.assertEqual(snapshot['provenance'], 'synthetic')
                self.assertFalse(snapshot['decision']['allow_new_work'])
            # A synthetic record claiming healthy still cannot pass provenance gate.
            snapshot = observed[-1]
            snapshot['decision'] = {'allow_new_work': True, 'observed_at': time.time(),
                                    'valid_until': time.time()+1000}
            (Path(d)/'state.json').write_text(json.dumps(snapshot))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['check', '--bucket', 'demo', '--state-dir', d]), 2)

    def test_concurrent_check_during_healthy_replay(self):
        self.run_replay_observer()

    def test_interrupted_healthy_replay(self):
        self.run_replay_observer(interrupt=True)

    def test_legacy_provenance_missing_rejected(self):
        import time
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            s = State(d)
            s.data['policy'] = vars(Policy('demo'))
            s.save({'allow_new_work': True, 'observed_at': time.time(), 'valid_until': time.time()+60})
            self.assertEqual(main(['check', '--bucket', 'demo', '--state-dir', d]), 2)
            s.close()


class ProtocolReviewTests(unittest.TestCase):
    def test_response_then_update_same_write_denies_cli_read(self):
        from unittest.mock import patch
        import time
        # Response first, update second: both bytes delivered in a single write.
        tail = """m=json.loads(sys.stdin.readline())
r={'id':m['id'],'result':RESPONSE}
n={'method':'account/rateLimits/updated','params':{'secret':'must_not_log'}}
import os
os.write(sys.stdout.fileno(),(json.dumps(r)+'\\n'+json.dumps(n)+'\\n').encode())
time.sleep(2)
""".replace('RESPONSE', repr(payload(reset=time.time()+1000)))
        rpc = RpcTests().server(tail)
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()) as out, patch('quota_guard.cli.RPC', return_value=rpc):
            self.assertEqual(main(['read', '--bucket', 'demo', '--state-dir', d]), 2)
            self.assertIn('notification_requires_read', out.getvalue())
            self.assertNotIn('must_not_log', out.getvalue())
            self.assertFalse(json.loads((Path(d)/'state.json').read_text())['decision']['allow_new_work'])

    def test_buffered_message_after_deadline_rejected(self):
        import time
        rpc = RPC.__new__(RPC)
        rpc.buf = bytearray(b'{"id":1,"result":{}}\n')
        with self.assertRaisesRegex(RpcError, '^timeout$'):
            rpc.message(time.monotonic()-1)

    def test_deadline_checked_after_parsing(self):
        from unittest.mock import patch
        import time
        rpc = RPC.__new__(RPC)
        rpc.buf = bytearray(b'{"id":1,"result":{}}\n')
        def slow_parse(_):
            time.sleep(0.03)
            return {'id': 1, 'result': {}}
        with patch('quota_guard.rpc.json.loads', slow_parse):
            with self.assertRaisesRegex(RpcError, '^timeout$'):
                rpc.message(time.monotonic()+0.01)

    def test_boolean_and_float_response_ids_rejected(self):
        import subprocess
        for bad in ('true', '1.0', '"1"'):
            code = "import sys,time; sys.stdin.readline(); print('" + '{"id":' + bad + ',"result":{}}' + "',flush=True); time.sleep(2)"
            with self.assertRaisesRegex(RpcError, '^invalid_response_id$'):
                RPC([sys.executable, '-u', '-c', code], timeout=0.3)

    def test_partial_notification_after_response_rejected(self):
        tail = """m=json.loads(sys.stdin.readline())
import os
os.write(sys.stdout.fileno(),(json.dumps({'id':m['id'],'result':{}})+'\\n'+ '{"method":').encode())
time.sleep(2)
"""
        rpc = RpcTests().server(tail)
        try:
            with self.assertRaisesRegex(RpcError, '^incomplete_pending_frame$'):
                rpc.call('account/rateLimits/read')
        finally:
            rpc.close()

    def test_write_timeout_when_child_stops_reading(self):
        import subprocess
        # Outer watchdog makes regression safe even if write becomes blocking.
        script = """import sys,json
from quota_guard.rpc import RPC,RpcError
child="import sys,json,time; m=json.loads(sys.stdin.readline()); print(json.dumps({'id':m['id'],'result':{}}),flush=True); time.sleep(10)"
r=RPC([sys.executable,'-u','-c',child],timeout=0.1)
try:
 for i in range(100):
  r.send({'method':'initialized','params':{'padding':'x'*3000}})
 raise AssertionError('pipe did not fill')
except RpcError as e:
 assert str(e)=='timeout',str(e)
 print('write_timeout')
finally:
 r.close()
"""
        result = subprocess.run([sys.executable, '-c', script], capture_output=True,
                                text=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'write_timeout')

    def test_checkpoint_never_reported_saved_on_interrupt_ack(self):
        from unittest.mock import patch
        import time
        class Fake:
            generation = 0
            def __init__(self, **kwargs):
                pass
            def call(self, method, *args):
                return payload(95, time.time()+1000) if method == 'account/rateLimits/read' else {}
            def wait(self, seconds):
                raise KeyboardInterrupt()
            def close(self):
                pass
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()) as out, patch('quota_guard.cli.RPC', Fake):
            self.assertEqual(main(['watch', '--bucket', 'demo', '--state-dir', d,
                                  '--managed-thread', 't', '--managed-turn', 'u',
                                  '--allow-interrupt']), 130)
            decision = json.loads(out.getvalue())
            self.assertEqual(decision['managed_action'], 'interrupt_acknowledged')
            self.assertEqual(decision['checkpoint_status'], 'unconfirmed')
            request = json.loads((Path(d)/'checkpoint.json').read_text())
            self.assertEqual(request['checkpoint_status'], 'unconfirmed')


if __name__ == '__main__':
    unittest.main()
