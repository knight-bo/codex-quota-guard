"""Human-in-the-loop events with synthetic readings; never real user messaging."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from quota_guard.cli import main
from quota_guard.confirmation import ConfirmationPolicy, ConfirmationEvents
from quota_guard.core import Guard, Policy
from quota_guard.state import State
from test_guard import payload


def reading(remaining, reset=2000, now=1000):
    guard=Guard(Policy('demo'))
    guard.ingest(payload(100-remaining, reset),now)
    return guard.decision(now)


class ConfirmationTests(unittest.TestCase):
    def test_arbitrary_targets_and_invalid_values(self):
        for target in (0,5,10,20,30,37.5,80,99.9,100):
            self.assertEqual(ConfirmationPolicy(target).target,target)
        for target in (-.1,100.1,float('nan'),float('inf'),True,'80'):
            with self.assertRaises(ValueError):ConfirmationPolicy(target)
        for warn,confirm in ((-1,0),(0,1),(101,1),(2,-1),(float('inf'),1)):
            with self.assertRaises(ValueError):ConfirmationPolicy(80,warn,confirm)

    def test_80_target_warning_at82_confirmation81_reached80(self):
        with tempfile.TemporaryDirectory() as d:
            state=State(d);engine=ConfirmationEvents(state,ConfirmationPolicy(80),'synthetic-task')
            expected=[(83,[]),(82,['warning']),(81,['confirmation_required']),(80,['target_reached']),(79,[])]
            ids=[]
            for remaining,kinds in expected:
                report=engine.evaluate(reading(remaining))
                self.assertEqual([e['type'] for e in report['events']],kinds)
                ids.extend(e['id'] for e in report['events'])
                if remaining<=80:
                    self.assertFalse(report['allow_new_work'])
                    self.assertEqual(report['reason'],'confirmation_target_reached')
                    self.assertTrue(report['confirmation']['quota_policy_allow_new_work'])
                for event in report['events']:
                    self.assertFalse(event['user_notified'])
                    self.assertFalse(event['pause_authorized'])
                    self.assertFalse(event['task_paused'])
            self.assertEqual(len(ids),len(set(ids)))
            state.close()

    def test_first_below_or_jump_emits_immediate_confirmation(self):
        for initial in (False,True):
            with tempfile.TemporaryDirectory() as d:
                state=State(d);engine=ConfirmationEvents(state,ConfirmationPolicy(80),'task')
                if not initial:engine.evaluate(reading(95))
                report=engine.evaluate(reading(65))
                self.assertEqual([e['type'] for e in report['events']],['confirmation_required','target_reached'])
                self.assertTrue(all(e['target_already_reached'] for e in report['events']))
                self.assertFalse(report['allow_new_work'])
                state.close()

    def test_endpoints_and_decimal_are_not_fixed_presets(self):
        for target,remaining in ((100,100),(0,0),(37.5,37.5)):
            with tempfile.TemporaryDirectory() as d:
                state=State(d);engine=ConfirmationEvents(state,ConfirmationPolicy(target),'task')
                report=engine.evaluate(reading(remaining))
                self.assertEqual([e['type'] for e in report['events']],['confirmation_required','target_reached'])
                self.assertEqual(report['confirmation']['target_percent'],target)
                self.assertFalse(report['allow_new_work'])
                state.close()

    def test_restart_dedup_and_new_cycle_is_not_authorization(self):
        with tempfile.TemporaryDirectory() as d:
            state=State(d);engine=ConfirmationEvents(state,ConfirmationPolicy(80),'PRIVATE_TASK_ID')
            first=engine.evaluate(reading(80));state.save(first);state.close()
            state=State(d);engine=ConfirmationEvents(state,ConfirmationPolicy(80),'PRIVATE_TASK_ID')
            repeated=engine.evaluate(reading(80))
            self.assertEqual(repeated['events'],[])
            self.assertFalse(repeated['allow_new_work'])
            self.assertNotIn('PRIVATE_TASK_ID',json.dumps(state.data))
            fresh=ConfirmationEvents(state,ConfirmationPolicy(80),'PRIVATE_TASK_ID',new_cycle=True).evaluate(reading(80))
            self.assertNotEqual(first['events'][0]['id'],fresh['events'][0]['id'])
            self.assertFalse(fresh['confirmation']['pause_authorized'])
            self.assertFalse(fresh['confirmation']['task_paused'])
            state.close()

    def test_quota_reset_never_unlatches_or_resumes(self):
        with tempfile.TemporaryDirectory() as d:
            state=State(d);engine=ConfirmationEvents(state,ConfirmationPolicy(80),'task')
            engine.evaluate(reading(79))
            report=engine.evaluate(reading(99,reset=3000))
            self.assertEqual([e['type'] for e in report['events']],['quota_changed'])
            self.assertTrue(report['confirmation']['target_reached_latched'])
            self.assertFalse(report['allow_new_work'])
            self.assertFalse(report['confirmation']['task_paused'])
            self.assertEqual(engine.evaluate(reading(99,reset=3000))['events'],[])
            state.close()

    def test_invalid_or_stale_data_never_triggers_target_events(self):
        with tempfile.TemporaryDirectory() as d:
            state=State(d);engine=ConfirmationEvents(state,ConfirmationPolicy(80),'task')
            for update in ({'data_valid':False},{'stale':True},{'remaining_percent':None}):
                report=reading(79);report.update(update)
                out=engine.evaluate(report)
                self.assertEqual(out['events'],[])
                self.assertFalse(out['allow_new_work'])
                self.assertFalse(out['confirmation']['target_reached_latched'])
            state.close()


class ConfirmationCliTests(unittest.TestCase):
    def test_target_mode_forbids_managed_interrupt_and_missing_binding(self):
        for extras in ([],['--task-key','task','--allow-interrupt'],['--task-key','task','--managed-thread','t','--managed-turn','u']):
            with tempfile.TemporaryDirectory() as d,contextlib.redirect_stderr(io.StringIO()),patch('quota_guard.cli.RPC') as rpc:
                self.assertEqual(main(['read','--bucket','demo','--target','80','--state-dir',d]+extras),2)
                rpc.assert_not_called()

    def test_target_read_check_and_no_implicit_task_action(self):
        calls=[]
        class Fake:
            generation=0
            def __init__(self,**kwargs):pass
            def call(self,method,*args):calls.append(method);return payload(20)
            def close(self):pass
        with tempfile.TemporaryDirectory() as d,patch('quota_guard.cli.RPC',Fake),patch('quota_guard.cli.time.time',return_value=1000):
            args=['--bucket','demo','--target','80','--task-key','task','--state-dir',d]
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(['read']+args),2)
            report=json.loads(out.getvalue());self.assertFalse(report['allow_new_work'])
            self.assertEqual(len(report['events']),2)
            self.assertEqual(calls,['account/rateLimits/read'])
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(['check']+args),2)
            self.assertEqual(json.loads(out.getvalue())['events'],[])
            self.assertFalse((Path(d)/'checkpoint.json').exists())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['check','--bucket','demo','--state-dir',d]),2)

    def test_task_or_policy_mismatch_never_admits_from_cached_target(self):
        class Fake:
            generation=0
            def __init__(self,**kwargs):pass
            def call(self,*args):return payload(5)
            def close(self):pass
        with tempfile.TemporaryDirectory() as d,patch('quota_guard.cli.RPC',Fake),patch('quota_guard.cli.time.time',return_value=1000),contextlib.redirect_stdout(io.StringIO()):
            base=['--bucket','demo','--state-dir',d]
            self.assertEqual(main(['read']+base+['--target','80','--task-key','task']),0)
            for extra in ([],['--target','79','--task-key','task'],['--target','80','--task-key','other']):
                self.assertEqual(main(['check']+base+extra),2)

class TargetRegressionTests(unittest.TestCase):
    def test_low_target_not_overridden_by_old_default_and_mixed_flags_rejected(self):
        class Fake:
            generation=0
            def __init__(self,**kwargs):pass
            def call(self,*args):return payload(94)  # 6% remaining, target 5%.
            def close(self):pass
        with tempfile.TemporaryDirectory() as d,patch('quota_guard.cli.RPC',Fake),patch('quota_guard.cli.time.time',return_value=1000):
            args=['read','--bucket','demo','--target','5','--task-key','task','--state-dir',d]
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(args),0)
            report=json.loads(out.getvalue())
            self.assertEqual(report['reserve_percent'],5)
            self.assertEqual(report['buffer_percent'],0)
            self.assertEqual([event['type'] for event in report['events']],['confirmation_required'])
            for flag in ('--reserve','--threshold','--buffer'):
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(args+[flag,'0']),2)

    def test_margin_change_does_not_clear_reached_target(self):
        with tempfile.TemporaryDirectory() as d:
            state=State(d)
            ConfirmationEvents(state,ConfirmationPolicy(80),'task').evaluate(reading(79))
            changed=ConfirmationEvents(state,ConfirmationPolicy(80,3,2),'task')
            report=changed.evaluate(reading(99,reset=3000))
            self.assertFalse(report['allow_new_work'])
            self.assertTrue(report['confirmation']['target_reached_latched'])
            state.close()

    def test_stop_during_target_read_emits_no_confirmation_events(self):
        calls=[]
        with tempfile.TemporaryDirectory() as d:
            class Fake:
                generation=0
                def __init__(self,**kwargs):pass
                def call(self,method,*args):
                    calls.append(method)
                    reader=State(d,readonly=True);assert reader.request_stop();reader.close()
                    return payload(30)
                def close(self):pass
            with patch('quota_guard.cli.RPC',Fake),contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(['start','--bucket','demo','--target','80','--task-key','task','--state-dir',d]),0)
            reports=[json.loads(line) for line in out.getvalue().splitlines()]
            self.assertEqual(calls,['account/rateLimits/read'])
            self.assertTrue(all(not report.get('events') and not report['allow_new_work'] for report in reports))

    def test_supervised_process_event_stream_and_cooperative_stop(self):
        import os,selectors,subprocess,sys,time
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);exe=base/'codex'
            exe.write_text('#!'+sys.executable+'\n'+'''import sys,json
n=0
for line in sys.stdin:
 m=json.loads(line)
 if m['method']=='initialized':continue
 result={}
 if m['method']=='account/rateLimits/read':
  remaining=[83,82,81,80,80][min(n,4)];n+=1
  result={'rateLimits':{'limitId':'demo','primary':{'usedPercent':100-remaining,'windowDurationMins':300,'resetsAt':4102444800},'secondary':None}}
 print(json.dumps({'id':m['id'],'result':result}),flush=True)
''')
            exe.chmod(0o700)
            state=base/'state'
            command=[sys.executable,str(root/'scripts/quota_guard.py')]
            env=dict(os.environ,PATH=str(base)+os.pathsep+os.environ['PATH'])
            proc=subprocess.Popen(command+['start','--bucket','demo','--target','80','--task-key','task',
                                 '--interval','.03','--state-dir',str(state)],env=env,
                                 stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                reports=[];deadline=time.monotonic()+5
                with selectors.DefaultSelector() as selector:
                    selector.register(proc.stdout,selectors.EVENT_READ)
                    while len(reports)<5:
                        self.assertLess(time.monotonic(),deadline)
                        self.assertIsNone(proc.poll())
                        if selector.select(.1):reports.append(json.loads(proc.stdout.readline()))
                self.assertEqual([[e['type'] for e in r['events']] for r in reports],
                                 [[],['warning'],['confirmation_required'],['target_reached'],[]])
                self.assertFalse(reports[3]['allow_new_work'])
                stopped=subprocess.run(command+['stop','--state-dir',str(state)],capture_output=True,text=True,timeout=5)
                self.assertEqual(stopped.returncode,0)
                proc.communicate(timeout=5)
                self.assertEqual(proc.returncode,0)
                self.assertFalse(json.loads((state/'state.json').read_text())['decision']['allow_new_work'])
            finally:
                if proc.poll() is None:proc.kill()
                proc.communicate()


if __name__=='__main__':unittest.main()
