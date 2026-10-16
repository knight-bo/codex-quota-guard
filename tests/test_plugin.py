"""Offline plugin/lifecycle regressions. All quota values are synthetic."""
import contextlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from quota_guard.cli import main
from quota_guard.core import Guard, Policy
from quota_guard.state import State
from test_guard import payload

ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_manifests_and_bundled_entry_resolve(self):
        from quota_guard import __version__
        portable = json.loads((ROOT/'plugin.json').read_text())
        compat = json.loads((ROOT/'.codex-plugin/plugin.json').read_text())
        marketplace = json.loads((ROOT/'.agents/plugins/marketplace.json').read_text())
        self.assertEqual(portable['$schema'], 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json')
        for manifest in (portable, compat):
            self.assertEqual(manifest['version'], __version__)
            self.assertEqual(manifest['license'], 'MIT')
            self.assertEqual(manifest['name'], 'codex-quota-guard')
            self.assertNotIn('hooks', manifest)
        entry = marketplace['plugins'][0]
        self.assertEqual((ROOT/entry['source']['path']).resolve(), ROOT)
        self.assertEqual(entry['name'], portable['name'])
        self.assertEqual(entry['policy']['installation'], 'AVAILABLE')
        skill = ROOT/'skills/quota-guard/SKILL.md'
        self.assertTrue((skill.parent/'../../scripts/quota_guard.py').resolve().is_file())
        self.assertIn('name: quota-guard', skill.read_text())
        self.assertIn('MIT License', (ROOT/'LICENSE').read_text())


class ReportTests(unittest.TestCase):
    def test_data_valid_low_quota_and_stale_are_distinct(self):
        g = Guard(Policy('demo', threshold=15, buffer=3, max_age=10))
        g.ingest(payload(82), 1000)
        d = g.decision(1000)
        self.assertFalse(d['allow_new_work'])
        self.assertTrue(d['data_valid'])
        self.assertFalse(d['stale'])
        self.assertEqual(d['reserve_percent'], 15)
        self.assertEqual(d['windows']['primary']['remaining_percent'], 18)
        self.assertEqual(d['observed_at'], 1000)
        self.assertEqual(d['valid_until'], 1010)
        d = g.decision(1010)
        self.assertTrue(d['stale'])
        self.assertFalse(d['data_valid'])
        self.assertEqual(d['remaining_percent'], 18)  # Historical, explicitly stale.

    def test_notification_invalidates_not_fabricates_new_timestamp(self):
        g = Guard(Policy('demo'))
        g.ingest(payload(), 1000)
        g.invalidate('notification_requires_read')
        d = g.decision(1001)
        self.assertFalse(d['data_valid'])
        self.assertFalse(d['allow_new_work'])
        self.assertEqual(d['observed_at'], 1000)

    def test_reserve_alias_and_invalid_timing(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['simulate', '--bucket', 'demo', '--reserve', '25', '--buffer', '5',
                                   '--fixture', 'fixtures/demo.jsonl', '--state-dir', d]), 0)
            s = json.loads((Path(d)/'state.json').read_text())
            self.assertEqual(s['policy']['threshold'], 25)
            for interval in ('0', '-1', 'nan', 'inf'):
                self.assertEqual(main(['read', '--bucket', 'demo', '--interval', interval, '--state-dir', d]), 2)

    def test_cached_stale_report_preserves_observed_time(self):
        with tempfile.TemporaryDirectory() as d:
            state = State(d)
            state.data.update(policy=vars(Policy('demo')), provenance='live')
            g = Guard(Policy('demo'))
            g.ingest(payload(), 1000)
            state.save(g.decision(1000))
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(['check', '--bucket', 'demo', '--state-dir', d]), 2)
            report = json.loads(out.getvalue())
            self.assertTrue(report['stale'])
            self.assertFalse(report['data_valid'])
            self.assertEqual(report['observed_at'], 1000)
            state.close()

    def test_stop_token_does_not_target_new_monitor(self):
        with tempfile.TemporaryDirectory() as d:
            writer = State(d)
            writer.data['monitor_token'] = 'old'
            writer.save({'allow_new_work': False})
            reader = State(d, readonly=True)
            self.assertTrue(reader.request_stop())
            self.assertTrue(writer.stop_requested('old'))
            self.assertFalse(writer.stop_requested('new'))
            reader.close()
            writer.close()
            reader = State(d, readonly=True)
            self.assertFalse(reader.request_stop())
            reader.close()

    def test_stop_pending_revokes_cached_admission(self):
        with tempfile.TemporaryDirectory() as d:
            state = State(d)
            state.data.update(policy=vars(Policy('demo')), provenance='live', monitor_token='monitor')
            g = Guard(Policy('demo'))
            g.ingest(payload(reset=time.time()+1000))
            state.save(g.decision())
            reader = State(d, readonly=True)
            self.assertTrue(reader.request_stop())
            reader.close()
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(['check', '--bucket', 'demo', '--state-dir', d]), 2)
            self.assertFalse(json.loads(out.getvalue())['data_valid'])
            state.close()

    def test_readonly_failure_never_overwrites_monitor_state(self):
        with tempfile.TemporaryDirectory() as d:
            writer = State(d)
            writer.data['monitor_token'] = 'current'
            writer.save({'allow_new_work': False})
            original = (Path(d)/'state.json').read_bytes()
            (Path(d)/'stop.json').write_text('invalid-json')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['check', '--bucket', 'demo', '--state-dir', d]), 2)
            self.assertEqual((Path(d)/'state.json').read_bytes(), original)
            writer.close()

    def test_stop_during_read_suppresses_result_and_interrupt(self):
        for outcome in ('healthy', 'low', 'error'):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as d:
                calls = []
                class Fake:
                    generation = 0
                    def __init__(self, **kwargs): pass
                    def call(self, method, *args):
                        calls.append(method)
                        if method == 'account/rateLimits/read':
                            reader = State(d, readonly=True)
                            assert reader.request_stop()
                            reader.close()
                            if outcome == 'error':
                                raise OSError('synthetic transport failure')
                            return payload(20 if outcome == 'healthy' else 95, reset=time.time()+1000)
                        return {}
                    def wait(self, *args): raise AssertionError('must stop before waiting')
                    def close(self): pass
                with patch('quota_guard.cli.RPC', Fake), contextlib.redirect_stdout(io.StringIO()) as out:
                    code = main(['start', '--bucket', 'demo', '--state-dir', d,
                                 '--managed-thread', 'synthetic-thread', '--managed-turn', 'synthetic-turn',
                                 '--allow-interrupt'])
                self.assertEqual(code, 0)
                self.assertEqual(calls, ['account/rateLimits/read'])
                reports = [json.loads(line) for line in out.getvalue().splitlines()]
                self.assertTrue(reports)
                self.assertTrue(all(not r['allow_new_work'] for r in reports))
                self.assertEqual(reports[-1]['reason'], 'monitor_stopped')
                saved = json.loads((Path(d)/'state.json').read_text())
                self.assertFalse(saved['decision']['allow_new_work'])
                self.assertIsNone(saved['monitor_token'])
                self.assertFalse((Path(d)/'checkpoint.json').exists())
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(['check', '--bucket', 'demo', '--state-dir', d]), 2)

    def test_cleanup_failure_is_redacted_and_lock_released(self):
        class Fake:
            generation = 0
            def __init__(self, **kwargs): pass
            def call(self, *args): return payload(reset=time.time()+1000)
            def close(self): raise OSError('PRIVATE_CLEANUP_PATH')
        with tempfile.TemporaryDirectory() as d, patch('quota_guard.cli.RPC', Fake), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as out:
            self.assertEqual(main(['read', '--bucket', 'demo', '--state-dir', d]), 2)
            self.assertIn('cleanup_or_state_error', out.getvalue())
            self.assertNotIn('PRIVATE_CLEANUP_PATH', out.getvalue())
            state = State(d)
            self.assertFalse(state.data['decision']['allow_new_work'])
            state.close()


class ProcessTests(unittest.TestCase):
    def fake_environment(self, directory):
        exe = Path(directory)/'codex'
        exe.write_text('#!'+sys.executable+'\n'+'''import json,sys,time
print('WARNING: non-fatal PATH update unavailable',file=sys.stderr,flush=True)
for line in sys.stdin:
 m=json.loads(line)
 if m['method']=='initialized': continue
 result={}
 if m['method']=='account/rateLimits/read':
  result={'rateLimits':{'limitId':'demo','primary':{'usedPercent':20,'windowDurationMins':10080,'resetsAt':4102444800},'secondary':None}}
 print(json.dumps({'id':m['id'],'result':result}),flush=True)
''')
        exe.chmod(0o700)
        return dict(os.environ, PATH=str(directory)+os.pathsep+os.environ['PATH'])

    def command(self, mode, directory):
        return [sys.executable, str(ROOT/'scripts/quota_guard.py'), mode,
                '--bucket', 'demo', '--interval', '30', '--state-dir', str(directory)]

    def await_healthy(self, directory, proc):
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            self.assertIsNone(proc.poll())
            try:
                saved=json.loads((Path(directory)/'state.json').read_text())
                if saved['decision']['allow_new_work']:
                    return saved
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            time.sleep(.02)
        self.fail('monitor did not produce synthetic healthy reading')

    def test_warning_is_nonfatal_and_launcher_is_cwd_independent(self):
        with tempfile.TemporaryDirectory() as d:
            result=subprocess.run(self.command('read', Path(d)/'state'), env=self.fake_environment(d),
                                  cwd='/',capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr)
            report=json.loads(result.stdout)
            self.assertTrue(report['data_valid'])
            self.assertEqual(report['windows']['primary']['window_duration_mins'],10080)
            self.assertNotIn('WARNING',result.stdout+result.stderr)

    def test_cooperative_stop_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            state=Path(d)/'state'
            proc=subprocess.Popen(self.command('start',state),env=self.fake_environment(d),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                self.await_healthy(state,proc)
                stopped=subprocess.run(self.command('stop',state),capture_output=True,text=True,timeout=5)
                self.assertEqual(stopped.returncode,0,stopped.stderr)
                self.assertTrue(json.loads(stopped.stdout)['stop_requested'])
                out,err=proc.communicate(timeout=5)
                self.assertEqual(proc.returncode,0,err)
                self.assertIn('monitor_stopped',out)
                saved=json.loads((state/'state.json').read_text())
                self.assertFalse(saved['decision']['allow_new_work'])
                self.assertIsNone(saved['monitor_token'])
                s=State(state);s.close()  # Writer lock released.
            finally:
                if proc.poll() is None: proc.kill()
                proc.communicate()

    def test_sigterm_revokes_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as d:
            state=Path(d)/'state'
            proc=subprocess.Popen(self.command('watch',state),env=self.fake_environment(d),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                self.await_healthy(state,proc)
                proc.send_signal(signal.SIGTERM)
                proc.communicate(timeout=5)
                self.assertEqual(proc.returncode,130)
                saved=json.loads((state/'state.json').read_text())
                self.assertFalse(saved['decision']['allow_new_work'])
                self.assertIsNone(saved['monitor_token'])
                s=State(state);s.close()
            finally:
                if proc.poll() is None: proc.kill()
                proc.communicate()


if __name__=='__main__':
    unittest.main()
