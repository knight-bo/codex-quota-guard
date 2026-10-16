"""Synthetic threshold and local draft-package checks; no live tasks or uploads."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from quota_guard.cli import main
from quota_guard.core import Guard, Policy
from test_guard import payload

ROOT = Path(__file__).resolve().parents[1]


class ThresholdTests(unittest.TestCase):
    def test_selected_reserves_exact_zero_buffer_boundary(self):
        for reserve in (5, 10, 20, 30):
            for remaining, allowed in ((reserve+.25, True),(reserve,False),(reserve-.25,False)):
                with self.subTest(reserve=reserve, remaining=remaining):
                    guard=Guard(Policy('demo',threshold=reserve,buffer=0))
                    guard.ingest(payload(100-remaining),1000)
                    decision=guard.decision(1000)
                    self.assertEqual(decision['allow_new_work'],allowed)
                    self.assertEqual(decision['reason'],'healthy' if allowed else 'low_quota')
                    self.assertTrue(decision['data_valid'])

    def test_default_buffer_detects_two_points_earlier(self):
        for reserve in (5,10,20,30):
            guard=Guard(Policy('demo',threshold=reserve))
            guard.ingest(payload(100-(reserve+2)),1000)
            self.assertEqual(guard.decision(1000)['reason'],'low_quota')
            exact=Guard(Policy('demo',threshold=reserve,buffer=0))
            exact.ingest(payload(100-(reserve+2)),1000)
            self.assertTrue(exact.decision(1000)['allow_new_work'])

    def test_policy_range_and_invalid_values(self):
        for reserve,buffer in ((0,0),(100,0),(98,2),(5,95)):
            Policy('demo',threshold=reserve,buffer=buffer)
        for reserve,buffer in ((-1,0),(101,0),(100,2),(99,2),(0,-1),
                               (float('nan'),0),(float('inf'),0),(True,0),(5,False)):
            with self.subTest(reserve=reserve,buffer=buffer),self.assertRaises(ValueError):
                Policy('demo',threshold=reserve,buffer=buffer)

    def test_cli_thresholds_never_enable_interrupt_by_default(self):
        for reserve in (5,10,20,30):
            calls=[]
            class Fake:
                generation=0
                def __init__(self,**kwargs):pass
                def call(self,method,*args):
                    calls.append(method)
                    return payload(100-reserve)
                def close(self):pass
            with tempfile.TemporaryDirectory() as d,patch('quota_guard.cli.RPC',Fake),patch('quota_guard.cli.time.time',return_value=1000),contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(['read','--bucket','demo','--reserve',str(reserve),
                                       '--buffer','0','--state-dir',d]),2)
                self.assertEqual(calls,['account/rateLimits/read'])
                self.assertEqual(json.loads(out.getvalue())['remaining_percent'],reserve)
                self.assertFalse((Path(d)/'checkpoint.json').exists())
