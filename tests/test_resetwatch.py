"""Public-watch tests use mock HTTP and synthetic account-free data only."""
import contextlib
from copy import deepcopy
from datetime import datetime, timezone
from email.message import Message
import io
import json
from pathlib import Path
from string import Formatter
import tempfile
import unittest
import subprocess
import sys
import signal
import time
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from quota_guard.cli import main
from quota_guard.i18n import SUPPORTED, catalog, emit, render
from quota_guard.notifications import deliver_local, notification_payload
from quota_guard.reset_cli import FixtureProvider
from quota_guard.resetwatch import (ModelYardProvider, NoRedirect,
    PublicHTTP, ResetWatch, TYPES, WatchError, event_record, iso, rss_date, parse_modelyard_rss, FEED_URL, MAX_ENTRY_BYTES,
    parse_json, public_url, utc, MAX_BYTES)
from quota_guard.state import State

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 18, tzinfo=timezone.utc).timestamp()


def date(at):
    return iso(datetime.fromtimestamp(at, timezone.utc))


def event(at=NOW, kind='planned', post_id=None, updated=None):
    ident = post_id or str((int(at * 1000) - 1288834974657) << 22)
    return {'post_id': ident, 'post_url': 'https://x.com/thsottiaux/status/' + ident,
            'event_type': kind, 'published_at': date(at), 'updated_at': date(updated or at),
            'products': ['codex', 'chatgpt_work'], 'source_url': 'https://tibo.modelyard.dev/events/124',
            'source_verification': 'directly_verified'}


def snapshot(events, at=NOW):
    return json.dumps({'schema_version': 1, 'checked_at': date(at), 'events': events})


class Provider:
    key, attribution = 'test', 'https://tibo.modelyard.dev/feed.xml.json'
    def __init__(self, events=None):
        self.events, self.error, self.checked, self.calls = events or [], None, None, 0
    def fetch(self, now):
        self.calls += 1
        if self.error:
            raise self.error
        return now if self.checked is None else self.checked, deepcopy(self.events)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = State(self.tmp.name)
        self.provider = Provider([event(NOW - 100)])
        self.watch = ResetWatch(self.state, self.provider)
    def tearDown(self):
        self.state.close()
        self.tmp.cleanup()
    def baseline(self):
        report = self.watch.poll(NOW)
        self.assertEqual(report['status'], 'reset_baseline')
        self.assertEqual(report['events'], [])
    def test_first_start_and_restart_suppress_known_oct17_history(self):
        values = json.loads((ROOT/'fixtures/reset-announcements.json').read_text())
        self.provider.events = values['events']
        self.baseline()
        self.watch = ResetWatch(self.state, self.provider)
        report = self.watch.poll(NOW + 3600)
        self.assertEqual(report['events'], [])
        self.assertEqual(report['status'], 'reset_ok')
        self.assertEqual(len(self.watch.data['seen']), 2)
        saved=self.state.read('announcements.json')['seen']['2111492738025959922']['records']['planned']
        self.assertEqual(saved['post_url'],'https://x.com/thsottiaux/status/2111492738025959922')
        self.assertEqual(saved['published_at'],'2026-10-17T16:21:00Z')
        self.assertEqual(saved['source_verification'],'directly_verified')
        self.assertEqual(saved['verification'],'third_party_reported')
        self.assertEqual(saved['source'],'test')
    def test_new_event_persisted_before_emit_and_deduplicated_after_restart(self):
        self.baseline()
        self.provider.events += [event(NOW + 100, 'completed')]
        report = self.watch.poll(NOW + 3600)
        self.assertEqual([e['event_type'] for e in report['events']], ['completed'])
        saved = self.state.read('announcements.json')
        self.assertIn(report['events'][0]['post_id'], saved['seen'])
        self.assertFalse(report['events'][0]['user_notified'])
        self.assertFalse(report['personal_quota_verified'])
        self.assertEqual(report['task_action'], 'none')
        self.assertNotIn('allow_new_work', report)
        self.watch = ResetWatch(self.state, self.provider)
        self.assertEqual(self.watch.poll(NOW + 7200)['events'], [])
    def test_same_post_planned_to_completed_only_new_state(self):
        planned = self.provider.events[0]
        self.baseline()
        completed = dict(planned, event_type='completed', updated_at=date(NOW + 60))
        self.provider.events = [completed, planned]
        report = self.watch.poll(NOW + 3600)
        self.assertEqual([e['event_type'] for e in report['events']], ['completed'])
        self.provider.events = [planned]  # Out-of-order downgrade does not replay.
        self.assertEqual(self.watch.poll(NOW + 7200)['events'], [])
        self.provider.events = [completed]
        self.assertEqual(self.watch.poll(NOW + 10800)['events'], [])
    def test_out_of_order_rows_newest_state_wins_and_old_late_posts_suppressed(self):
        self.baseline()
        new = event(NOW + 100)
        completed = dict(new, event_type='completed', updated_at=date(NOW + 200))
        self.provider.events = [completed, event(NOW - 86400, 'completed'), new, completed]
        report = self.watch.poll(NOW + 3600)
        self.assertEqual([e['event_type'] for e in report['events']], ['completed'])
    def test_old_post_edited_after_baseline_is_not_a_new_announcement(self):
        self.baseline()
        self.provider.events = [event(NOW - 86400, 'banked', updated=NOW + 120)]
        self.assertEqual(self.watch.poll(NOW + 3600)['events'], [])
    def test_completed_before_baseline_not_replayed_by_provider_reindex(self):
        self.baseline()
        self.provider.events = [dict(self.provider.events[0], event_type='completed')]
        self.assertEqual(self.watch.poll(NOW + 3600)['events'], [])
    def test_all_four_types_and_filtering_does_not_replay_on_setting_change(self):
        self.watch = ResetWatch(self.state, self.provider, ['banked'])
        self.baseline()
        self.provider.events = [event(NOW + 100 + i, kind) for i, kind in enumerate(TYPES)]
        report = self.watch.poll(NOW + 3600)
        self.assertEqual([e['event_type'] for e in report['events']], ['banked'])
        self.watch = ResetWatch(self.state, self.provider)
        self.assertEqual(self.watch.poll(NOW + 7200)['events'], [])
    def test_failures_never_establish_baseline_or_reset_verdict_then_recover(self):
        for n, code in enumerate(('reset_network_error', 'reset_parse_error', 'reset_stale', 'reset_source_error')):
            self.provider.error = WatchError(code)
            report = self.watch.poll(NOW + 86400*n)
            self.assertEqual(report['status'], code)
            self.assertEqual(report['events'], [])
            self.assertNotIn('baseline_at', self.watch.ledger)
            self.assertNotIn('reset_detected', report)
        self.provider.error = None
        self.provider.events = [event(NOW + 4*86400 - 100, 'completed')]
        self.assertEqual(self.watch.poll(NOW + 4*86400)['status'], 'reset_baseline')
        self.assertEqual(self.watch.ledger['failures'], 0)
    def test_failed_snapshot_does_not_consume_events_then_recovery_emits_once(self):
        self.baseline()
        new = event(NOW + 100, 'completed')
        self.provider.events = [new, dict(new, post_url='https://x.com/attacker/status/' + new['post_id'])]
        report = self.watch.poll(NOW + 3600)
        self.assertEqual(report['status'], 'reset_source_error')
        self.assertNotIn(new['post_id'], self.watch.data['seen'])
        self.provider.events = [new]
        self.assertEqual(len(self.watch.poll(NOW + 10800)['events']), 1)
    def test_expired_or_future_provider_check_is_unknown_even_if_events_valid(self):
        self.provider.checked = NOW - 172801
        self.assertEqual(self.watch.poll(NOW)['status'], 'reset_stale')
        self.provider.checked = NOW + 86400 + 301
        self.assertEqual(self.watch.poll(NOW + 86400)['status'], 'reset_parse_error')
        self.assertEqual(self.watch.data['seen'], {})
    def test_persisted_cooldown_rate_limit_and_bounded_backoff(self):
        self.provider.error = WatchError('reset_rate_limited', retry_after=7000)
        with patch('quota_guard.resetwatch.random.uniform', return_value=1.1):
            report = self.watch.poll(NOW)
        self.assertGreaterEqual(report['next_poll_at'], NOW + 7000)
        self.watch = ResetWatch(self.state, self.provider, interval=3600)
        self.assertEqual(self.watch.poll(NOW + 60)['status'], 'reset_waiting')
        self.assertEqual(self.provider.calls, 1)
        for i in range(8):
            at = self.watch.ledger['next_poll_at']
            report = self.watch.poll(at)
            self.assertLessEqual(report['next_poll_at'] - at, 86400)
            self.assertGreaterEqual(report['next_poll_at'] - at, 3600)
    def test_cooldown_written_before_fetch_and_clock_rollback_blocks(self):
        def fetch(now):
            self.assertEqual(self.state.read('announcements.json')['providers']['test']['next_poll_at'], NOW + 3600)
            return now, []
        self.provider.fetch = fetch
        self.watch.poll(NOW)
        self.assertEqual(self.watch.poll(NOW - 1)['status'], 'reset_clock_error')
    def test_switch_provider_establishes_baseline_but_keeps_global_dedup(self):
        self.baseline()
        self.provider.key = 'second'
        other = ResetWatch(self.state, self.provider)
        self.provider.events += [event(NOW + 100, 'completed')]
        self.assertEqual(other.poll(NOW + 3600)['status'], 'reset_baseline')
        self.assertEqual(other.poll(NOW + 7200)['events'], [])
    def test_duplicate_conflicts_fail_without_partial_events(self):
        self.baseline()
        new = event(NOW + 100)
        self.provider.events = [new, dict(new, updated_at=date(NOW + 300))]
        self.assertEqual(self.watch.poll(NOW + 3600)['status'], 'reset_parse_error')
    def test_old_newly_discovered_post_event_age_and_empty_snapshot(self):
        self.watch = ResetWatch(self.state, self.provider, event_age=3600)
        self.baseline()
        self.provider.events = [event(NOW + 100)]
        self.assertEqual(self.watch.poll(NOW + 7200)['events'], [])
        self.provider.events = []
        self.assertEqual(self.watch.poll(NOW + 10800)['status'], 'reset_ok')
    def test_invalid_config_or_state_is_rejected_without_network(self):
        for kwargs in ({'interval':3599}, {'interval':float('nan')}, {'event_types':['fake']},
                       {'event_types':[]}, {'timezone_name':'bad/timezone'}, {'max_age':0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(WatchError):
                ResetWatch(self.state, self.provider, **kwargs)
        self.state.write('announcements.json', {'schema_version':1, 'providers':{}, 'seen':{'bad':{}}})
        with self.assertRaises(WatchError): ResetWatch(self.state, self.provider)
        self.assertEqual(self.provider.calls, 0)

    def test_empty_state_is_corruption_not_permission_to_rebaseline(self):
        self.state.write('announcements.json', {})
        with self.assertRaises(WatchError):ResetWatch(self.state,self.provider)

    def test_older_completion_update_is_unknown_then_newer_update_recovers(self):
        self.provider.events=[event(NOW-100,updated=NOW)]
        self.baseline()
        self.provider.events=[dict(self.provider.events[0],event_type='completed',updated_at=date(NOW-60))]
        self.assertEqual(self.watch.poll(NOW+3600)['status'],'reset_parse_error')
        self.provider.events[0]['updated_at']=date(NOW+60)
        self.assertEqual(len(self.watch.poll(NOW+10800)['events']),1)

    def test_oversized_ledger_fails_before_writing_or_emitting(self):
        self.baseline()
        before=self.state.read('announcements.json')
        self.watch.data['oversized_test_field']='x'*(MAX_BYTES+1)
        with self.assertRaises(WatchError):self.watch.save()
        self.assertEqual(self.state.read('announcements.json'),before)


class SchemaTests(unittest.TestCase):
    def test_known_fixture_dates_and_snowflake_consistency(self):
        text = (ROOT/'fixtures/reset-announcements.json').read_text(encoding='utf-8')
        _, events = parse_json(text, NOW)
        self.assertEqual([e['post_id'] for e in events], ['2111492738025959922','2111566005684289735'])
        self.assertEqual([e['published_at'] for e in events], ['2026-10-17T16:21:00Z','2026-10-17T21:12:00Z'])
    def test_json_wire_rejects_naive_dates_unknown_types_and_invalid_schema(self):
        values = [dict(event(), published_at='2026-10-18T00:00:00'),
                  dict(event(), event_type='prediction'), dict(event(), published_at='2025-10-18T00:00:00Z'),
                  dict(event(), updated_at=date(NOW - 1)), dict(event(), products=['unrecognized'])]
        for value in values:
            with self.subTest(value=value), self.assertRaises(WatchError): event_record(value, NOW)
        for text in ('invalid', '{}', '[]', '{"schema_version":true}', snapshot([None]),
                     json.dumps({'schema_version':1,'checked_at':date(NOW),'events':{}})):
            with self.subTest(text=text), self.assertRaises(WatchError): parse_json(text,NOW)
    def test_forged_sources_and_impersonating_urls_rejected(self):
        for link in ('https://x.com/other/status/2111492738025959922',
                     'https://x.com.evil.example/thsottiaux/status/2111492738025959922',
                     'https://thsottiaux@x.com/thsottiaux/status/2111492738025959922',
                     'http://x.com/thsottiaux/status/2111492738025959922', 'javascript:alert(1)'):
            with self.subTest(link=link), self.assertRaises(WatchError): event_record(dict(event(),post_url=link),NOW)
    def test_raw_url_retained_and_third_party_cannot_promote_itself_to_official(self):
        value = dict(event(), verification='official', official=True)
        value['post_url'] = value['post_url'].replace('x.com','twitter.com')
        result = event_record(value,NOW)
        self.assertEqual(result['post_url'],value['post_url'])
        self.assertEqual(result['verification'],'third_party_reported')
        self.assertNotIn('official',result)
    def test_public_urls_reject_credentials_private_hosts_and_redirect_tricks(self):
        for url in ('http://example.com/feed', 'https://user:secret@example.com/feed',
                    'https://127.0.0.1/feed', 'https://localhost/feed', 'https://example.local/feed',
                    'https://example.com:444/feed', 'https://example.com/feed#secret', 'https://localhost./private', 'https://127.0.0.1.nip.io/private', 'https://example.com/\nfeed'):
            with self.subTest(url=url), self.assertRaises(WatchError): public_url(url)
    def test_timezone_and_dates_do_not_depend_on_machine_locale(self):
        self.assertEqual(iso(rss_date('Sat, 17 Oct 2026 12:21:13 -0400')), '2026-10-17T16:21:13Z')
        self.assertEqual(iso(rss_date('Mon, 02 Nov 2026 00:21:00 -0500')), '2026-11-02T05:21:00Z')
        for raw in ('Sat, 17 Oct 2026 12:21:13', 'tomorrow', 'Oct 99, 2026'):
            with self.assertRaises(WatchError): rss_date(raw)
    def test_json_fixture_contract_retains_attribution_without_network(self):
        checked,events=parse_json(snapshot([event()]),NOW)
        self.assertEqual(checked,NOW)
        self.assertEqual(events[0]['verification'],'third_party_reported')
        self.assertEqual(events[0]['source_url'],'https://tibo.modelyard.dev/events/124')


def rss_sample():
    return (ROOT/'fixtures/modelyard-rss-item-124.xml').read_text(encoding='utf-8')


def rss_event(at=NOW,kind='Reset Planned',source_text='Codex and ChatGPT Work reset planned',title='Codex reset'):
    from email.utils import format_datetime
    from xml.sax.saxutils import escape
    value=event(at)
    item=f"""<item><title>{escape(title)}</title><description>Public report.
Source text: {escape(source_text)}
Source: {value['post_url']}</description><link>https://tibo.modelyard.dev/events/125</link><guid isPermaLink="true">https://tibo.modelyard.dev/events/125</guid><pubDate>{format_datetime(datetime.fromtimestamp(at,timezone.utc),usegmt=True)}</pubDate><category>{escape(kind)}</category></item>"""
    import re
    return re.sub(r'<item>.*?</item>',lambda match:item,rss_sample(),flags=re.S)


class ModelYardTests(unittest.TestCase):
    def provider(self,text=None):
        http=Mock(timeout=10)
        http.get.return_value=rss_sample() if text is None else text
        return ModelYardProvider(http),http
    def test_actual_cropped_rss_category_source_namespace_date_and_unverified_scope(self):
        provider,http=self.provider()
        checked,events=provider.fetch(NOW)
        self.assertIsNone(checked)
        self.assertEqual(len(events),1)
        value=events[0]
        self.assertEqual(value['post_id'],'2111492738025959922')
        self.assertEqual(value['published_at'],'2026-10-17T16:21:13Z')
        self.assertEqual(value['event_type'],'planned')
        self.assertEqual(value['verification'],'third_party_reported')
        self.assertEqual(value['source_verification'],'unverified')
        self.assertEqual(value['products'],['unknown'])
        self.assertEqual(value['reported_products'],['chatgpt_work','codex'])
        self.assertEqual(value['scope_provenance'],'unspecified')
        self.assertIsNone(value['updated_at'])
        self.assertEqual(http.get.call_count,1)
        self.assertEqual(http.get.call_args.args[0],FEED_URL)
        self.assertEqual(provider.snapshot_metadata['fetched_at'],NOW)
        self.assertLess(provider.snapshot_metadata['feed_last_build_at'],NOW)
    def test_old_valid_feed_establishes_baseline_without_source_heartbeat(self):
        provider,_=self.provider()
        later=NOW+365*86400
        with tempfile.TemporaryDirectory() as directory:
            state=State(directory)
            try:
                watch=ResetWatch(state,provider)
                result=watch.poll(later)
                self.assertEqual(result['status'],'reset_baseline')
                self.assertEqual(result['events'],[])
                self.assertIsNone(result['provider_checked_at'])
                self.assertEqual(result['fetched_at'],later)
                self.assertEqual(result['source_coverage'],'unknown')
                self.assertGreater(result['latest_entry_age_seconds'],300*86400)
                self.assertEqual(watch.poll(later+3600)['events'],[])
            finally:state.close()
    def test_same_post_category_upgrade_is_local_observation_not_new_post(self):
        provider,http=self.provider()
        with tempfile.TemporaryDirectory() as directory:
            state=State(directory)
            try:
                watch=ResetWatch(state,provider)
                watch.poll(NOW)
                http.get.return_value=rss_sample().replace('<category>Reset Planned</category>','<category>Reset Completed</category>')
                report=watch.poll(NOW+3600)
                self.assertEqual(len(report['events']),1)
                value=report['events'][0]
                self.assertEqual(value['announcement_kind'],'aggregation_status_update')
                self.assertEqual(value['first_observed_status_at'],NOW+3600)
                self.assertEqual(value['status_time_provenance'],'local_observation')
                self.assertEqual(value['published_at'],'2026-10-17T16:21:13Z')
                self.assertIsNone(value['updated_at'])
                watch=ResetWatch(state,provider)
                self.assertEqual(watch.poll(NOW+7200)['events'],[])
                http.get.return_value=rss_sample()
                self.assertEqual(watch.poll(NOW+10800)['events'],[])
            finally:state.close()
    def test_chatgpt_only_is_filtered_unknown_scope_remains_explicit(self):
        provider,http=self.provider()
        with tempfile.TemporaryDirectory() as directory:
            state=State(directory)
            try:
                watch=ResetWatch(state,provider);watch.poll(NOW)
                http.get.return_value=rss_event(NOW+120,source_text='Global reset for paid ChatGPT accounts',title='ChatGPT reset')
                self.assertEqual(watch.poll(NOW+3600)['events'],[])
                _,values=provider.fetch(NOW+3600)
                self.assertEqual(values[0]['products'],['chatgpt'])
                self.assertNotIn('codex',values[0]['products'])
            finally:state.close()
    def test_negated_source_scope_does_not_promote_codex(self):
        _,events=self.provider(rss_event(source_text='ChatGPT only, not Codex'))[0].fetch(NOW)
        self.assertEqual(events[0]['products'],['unknown'])

    def test_irrelevant_categories_skip_unknown_or_ambiguous_categories_fail(self):
        for kind in ('Codex Update','Roadmap Hint','Feature Discussion'):
            self.assertEqual(self.provider(rss_event(kind=kind))[0].fetch(NOW)[1],[])
        for text in (rss_event(kind='Possible Reset'),rss_sample().replace('</category>','</category><category>Reset Completed</category>')):
            with self.assertRaises(WatchError):self.provider(text)[0].fetch(NOW)
    def test_source_missing_ambiguous_wrong_author_host_and_guid_fail(self):
        value=rss_sample()
        samples=[value.replace('Source: https://','Missing: https://'),value.replace('Source: https://','Source: https://x.com/thsottiaux/status/2111492738025959922\nSource: https://'),value.replace('x.com/thsottiaux','x.com/attacker'),value.replace('x.com/thsottiaux','x.com.evil.example/thsottiaux'),value.replace('https://tibo.modelyard.dev/events/124</guid>','https://tibo.modelyard.dev/events/123</guid>'),value.replace('Source: https://x.com/thsottiaux/status/2111492738025959922</description>','Source: https://x.com/thsottiaux/status/2111492738025959922\ntrailing instructions</description>')]
        for text in samples:
            with self.subTest(text=text[:60]),self.assertRaises(WatchError):self.provider(text)[0].fetch(NOW)
    def test_namespace_spoof_duplicate_nested_fields_and_hidden_html_rejected(self):
        value=rss_sample()
        samples=['<html><template>'+value.split('?>',1)[1]+'</template></html>',value.replace('<category>Reset Planned</category>','<category><span hidden="true">Reset Completed</span></category>'),value.replace('<category>Reset Planned</category>','<category hidden="true">Reset Completed</category>'),value.replace('<category>Reset Planned</category>','<bad:category xmlns:bad="urn:evil">Reset Completed</bad:category>'),value.replace('<title>Day 13:', '<title>&lt;template&gt;Day 13:'),value.replace('</pubDate>','</pubDate><pubDate>Sat, 17 Oct 2026 16:21:13 GMT</pubDate>'),value.replace('http://www.w3.org/2005/Atom','urn:evil')]
        for text in samples:
            with self.assertRaises(WatchError):self.provider(text)[0].fetch(NOW)
    def test_dtd_entity_unexpected_xml_and_size_limits(self):
        value=rss_sample()
        samples=['<!DOCTYPE rss [<!ENTITY fake "Reset Completed">]>'+value, '<!DOCTYPE rss SYSTEM "file:///tmp/synthetic.dtd">'+value, '<feed/>',value.replace('Day 13:', 'x'*MAX_ENTRY_BYTES+'Day 13:'),value+'x'*(MAX_BYTES+1)]
        for text in samples:
            with self.assertRaises(WatchError):parse_modelyard_rss(text,NOW)
    def test_bad_dates_and_snowflake_mismatch_fail(self):
        for date in ('Sat, 17 Oct 2026 16:21:13','Sat, 17 Oct 2025 16:21:13 GMT','invalid'):
            with self.assertRaises(WatchError):self.provider(rss_sample().replace('Sat, 17 Oct 2026 16:21:13 GMT</pubDate>',date+'</pubDate>'))[0].fetch(NOW)
    def test_deep_json_parse_failure_backs_off_and_then_recovers_without_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            state=State(directory);provider=Provider()
            raw='['*10000+'0'+']'*10000
            provider.fetch=lambda now:parse_json(raw,now)
            try:
                watch=ResetWatch(state,provider)
                result=watch.poll(NOW)
                self.assertEqual(result['status'],'reset_parse_error')
                self.assertEqual(result['events'],[])
                self.assertNotIn('baseline_at',watch.ledger)
                raw=snapshot([],NOW+10800)
                self.assertEqual(watch.poll(NOW+10800)['status'],'reset_baseline')
            finally:state.close()


class Response:
    status=200
    def __init__(self, body=b'{}', content_type='application/json', url='https://tibo.modelyard.dev/feed.xml'):
        self.headers=Message();self.headers['Content-Type']=content_type
        self.body,self.url=io.BytesIO(body),url
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def geturl(self):return self.url
    def read1(self,size):return self.body.read(size)


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.http=PublicHTTP(10);self.http.opener=Mock()
    def get(self):return self.http.get('https://tibo.modelyard.dev/feed.xml',10**20,('application/json',))
    def test_anonymous_get_has_no_auth_cookies_payload_or_redirects(self):
        self.http.opener.open.return_value=Response()
        self.assertEqual(self.get(),'{}')
        request=self.http.opener.open.call_args.args[0]
        self.assertIsNone(request.data)
        self.assertEqual(request.get_method(),'GET')
        self.assertNotIn('Authorization',request.headers)
        self.assertNotIn('Cookie',request.headers)
        with self.assertRaises(WatchError): NoRedirect().redirect_request(None,None,302,None,None,'https://other.example/')
        for host in ('x.com','twitter.com','api.x.com'):
            with self.assertRaises(WatchError):self.http.get('https://'+host+'/public.json',10**20,('application/json',))
    def test_timeout_403_429_and_retry_after(self):
        cases=[(TimeoutError(),'reset_network_error'),(URLError('private error'),'reset_network_error'),
               (HTTPError('https://tibo.modelyard.dev/feed.xml',403,'private',{},None),'reset_network_error'),
               (HTTPError('https://tibo.modelyard.dev/feed.xml',429,'private',{'Retry-After':'7000'},None),'reset_rate_limited')]
        for error,code in cases:
            self.http.opener.open.side_effect=error
            with self.assertRaises(WatchError) as caught:self.get()
            self.assertEqual(caught.exception.code,code)
            self.assertNotIn('private',str(caught.exception))
            if code=='reset_rate_limited':self.assertEqual(caught.exception.retry_after,7000)
    def test_deadline_size_encoding_content_type_and_unexpected_origin(self):
        with self.assertRaises(WatchError):self.http.get('https://tibo.modelyard.dev/feed.xml',0,('application/json',))
        self.http.opener.open.assert_not_called()
        for response in (Response(b'x'*(MAX_BYTES+1)),Response(b'\xff'),Response(content_type='text/html'),
                         Response(url='https://other.example/feed')):
            self.http.opener.open.return_value=response
            with self.assertRaises(WatchError):self.get()
    def test_deadline_checked_during_body_read(self):
        self.http.opener.open.return_value=Response(b'{}')
        with patch('quota_guard.resetwatch.time.monotonic',side_effect=[0,0,11]):
            with self.assertRaises(WatchError):self.http.get('https://tibo.modelyard.dev/feed.xml',10,('application/json',))


class CliAndLocaleTests(unittest.TestCase):
    def run_cli(self,args):
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            code=main(['resetwatch']+args)
        return code,out.getvalue(),err.getvalue()
    def test_nine_catalogs_complete_placeholders_encoding_and_help(self):
        expected=json.loads((ROOT/'quota_guard/locales/en.json').read_text(encoding='utf-8'))
        for locale in SUPPORTED:
            raw=json.loads((ROOT/f'quota_guard/locales/{locale}.json').read_text(encoding='utf-8'))
            self.assertEqual(set(raw),set(expected))
            for key,value in raw.items():
                self.assertTrue(isinstance(value,str) and value)
                self.assertNotIn('\ufffd',value)
                self.assertEqual({field for _,field,_,_ in Formatter().parse(value) if field},
                                 {field for _,field,_,_ in Formatter().parse(expected[key]) if field})
            with contextlib.redirect_stdout(io.StringIO()) as out, self.assertRaises(SystemExit) as caught:
                main(['resetwatch','--help','--locale',locale])
            self.assertEqual(caught.exception.code,0)
            shown=' '.join(out.getvalue().split())
            self.assertIn(raw['reset_help'],shown)
            self.assertIn(raw['reset_limits'],shown)
            self.assertIn(raw['reset_events_help'],shown)
            binary=io.BytesIO();stream=io.TextIOWrapper(binary,encoding='ascii',errors='strict')
            with contextlib.redirect_stdout(stream),self.assertRaises(SystemExit):
                main(['resetwatch','--help','--locale',locale])
            stream.flush();self.assertIn('--interval',binary.getvalue().decode('ascii'))
    def test_fixture_cli_json_identical_in_all_languages_never_reads_account(self):
        reference=None
        for locale in SUPPORTED+('xx',):
            with tempfile.TemporaryDirectory() as d, patch('quota_guard.cli.RPC') as rpc, patch('quota_guard.reset_cli.time.time',return_value=NOW):
                code,out,err=self.run_cli(['read','--state-dir',d,'--locale',locale,'--fixture',str(ROOT/'fixtures/reset-announcements.json')])
                self.assertEqual(code,0,err)
                reference=out if reference is None else reference
                self.assertEqual(out,reference)
                report=json.loads(out)
                self.assertEqual(report['events'],[])
                self.assertTrue(report['synthetic'])
                rpc.assert_not_called()
                self.assertTrue((Path(d)/'public-reset-watch/fixtures/announcements.json').exists())
                self.assertFalse((Path(d)/'state.json').exists())
    def test_notifications_types_errors_dates_and_ascii_terminals_all_languages(self):
        for locale in SUPPORTED:
            words=catalog(locale)
            for kind in TYPES:
                notice=notification_payload(event(NOW,kind),locale,'Asia/Shanghai')
                self.assertIn(words['reset_'+kind],notice['body'])
                self.assertIn('2026-10-18T08:00:00+08:00',notice['body'])
                self.assertIn(words['reset_advisory'],notice['body'])
                self.assertIn(words['reset_third_party'],notice['body'])
                sink=Mock(return_value='local-result')
                self.assertEqual(deliver_local(event(NOW,kind),sink,locale),'local-result')
                sink.assert_called_once()
            aggregate=dict(event(),products=['unknown'],announcement_kind='aggregation_status_update',first_observed_status_at=NOW)
            notice=notification_payload(aggregate,locale)
            self.assertIn(words['reset_aggregation_update'],notice['body'])
            self.assertIn(words['reset_scope_unknown'],notice['body'])
            self.assertIn(words['reset_coverage_unknown'],notice['body'])
            self.assertIn(words['reset_first_observed_status_at'],notice['body'])
            for status in ('reset_network_error','reset_stale','reset_parse_error','reset_source_error','reset_rate_limited'):
                output=render({'kind':'public_reset_watch','status':status,'events':[]},locale)
                self.assertIn(words[status],output)
                self.assertIn(words['reset_advisory'],output)
            waiting=render({'kind':'public_reset_watch','status':'reset_waiting',
                            'last_poll_status':'reset_network_error'},locale)
            self.assertIn(words['reset_network_error'],waiting)
            raw=io.BytesIO();stream=io.TextIOWrapper(raw,encoding='ascii',errors='strict')
            emit({'kind':'public_reset_watch','status':'reset_stale','events':[]},'text',locale,stream)
            stream.flush();self.assertNotIn('Traceback',raw.getvalue().decode('ascii'))
    def test_daylight_saving_and_regional_fallback(self):
        notice=notification_payload(event(NOW,'completed'),'zh-CN','America/Los_Angeles')
        self.assertIn('2026-10-17T17:00:00-07:00',notice['body'])
        self.assertEqual(notification_payload(event(),'xx'),notification_payload(event(),'en'))
    def test_invalid_options_localized_and_unsafe_task_control_not_accepted(self):
        for locale in SUPPORTED:
            for extra in (['--interval','1'],['--timezone','bad/zone'],['--allow-interrupt'],['--provider','json']):
                with tempfile.TemporaryDirectory() as d:
                    code,out,err=self.run_cli(['read','--state-dir',d,'--format','text','--locale',locale]+extra)
                    self.assertEqual(code,2)
                    self.assertIn(catalog(locale)['reset_configuration_error'],err)
                    self.assertNotIn('Traceback',err)
    def test_new_watch_keeps_existing_quota_state_and_locks_independent(self):
        with tempfile.TemporaryDirectory() as d:
            quota=State(d);quota.save({'allow_new_work':False,'reason':'low_quota'})
            original=(Path(d)/'state.json').read_bytes()
            with patch('quota_guard.reset_cli.ModelYardProvider',return_value=Provider()),patch('quota_guard.reset_cli.time.time',return_value=NOW):
                code,out,err=self.run_cli(['read','--state-dir',d])
            self.assertEqual(code,0,err)
            self.assertEqual((Path(d)/'state.json').read_bytes(),original)
            quota.close()
    def test_stop_during_fetch_only_stops_exact_public_watch(self):
        with tempfile.TemporaryDirectory() as d:
            provider=Provider()
            def fetch(now):
                reader=State(Path(d)/'public-reset-watch',readonly=True)
                self.assertTrue(reader.request_stop());reader.close()
                return now,[event(NOW)]
            provider.fetch=fetch
            with patch('quota_guard.reset_cli.ModelYardProvider',return_value=provider):
                code,out,err=self.run_cli(['start','--state-dir',d])
            self.assertEqual(code,0,err)
            self.assertEqual(json.loads(out)['status'],'reset_stopped')
            saved=json.loads((Path(d)/'public-reset-watch/state.json').read_text())
            self.assertIsNone(saved['monitor_token'])
            code,out,_=self.run_cli(['stop','--state-dir',d])
            self.assertEqual(code,2);self.assertFalse(json.loads(out)['stop_requested'])
    def test_cached_status_has_no_events_and_marks_expired_evidence(self):
        with tempfile.TemporaryDirectory() as d,patch('quota_guard.reset_cli.ModelYardProvider',return_value=Provider()):
            with patch('quota_guard.reset_cli.time.time',return_value=NOW):
                self.assertEqual(self.run_cli(['read','--state-dir',d])[0],0)
            with patch('quota_guard.reset_cli.time.time',return_value=NOW+172801):
                code,out,err=self.run_cli(['status','--state-dir',d])
            report=json.loads(out)
            self.assertEqual(code,2,err)
            self.assertTrue(report['cached'])
            self.assertEqual(report['status'],'reset_stale')
            self.assertEqual(report['events'],[])
    def test_fixture_cannot_start_and_corrupt_state_fails_without_fallback_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            code,_,_=self.run_cli(['start','--state-dir',d,'--fixture','does-not-exist'])
            self.assertEqual(code,2)
            directory=Path(d)/'public-reset-watch';directory.mkdir(mode=0o700)
            (directory/'announcements.json').write_text('not json')
            with patch('quota_guard.reset_cli.ModelYardProvider',return_value=Provider()) as factory:
                code,_,err=self.run_cli(['read','--state-dir',d])
            self.assertEqual(code,2)
            self.assertEqual(factory.return_value.calls,0)
            self.assertEqual((directory/'announcements.json').read_text(),'not json')

    def test_all_nine_guides_cover_public_workflow_and_configuration(self):
        for locale in SUPPORTED:
            text=(ROOT/f'docs/i18n/{locale}.md').read_text(encoding='utf-8')
            for token in ('resetwatch read','resetwatch start','resetwatch stop','resetwatch status',
                          '--events','--interval','--timezone','--max-age','--event-age','--timeout',
                          '--provider','--fixture','manual_credit','RESET-SOURCES.md'):
                self.assertIn(token,text,(locale,token))

    def test_start_shutdown_cleanup_failure_is_redacted_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as d:
            original=State.write
            def write(state,name,value):
                if name=='state.json' and value.get('kind')=='public_reset_watch' and value.get('monitor_token') is None:
                    raise OSError('PRIVATE_CLEANUP_DETAIL')
                return original(state,name,value)
            with patch('quota_guard.reset_cli.ModelYardProvider',return_value=Provider()), patch('quota_guard.state.State.write',write), patch('quota_guard.resetwatch.ResetWatch.poll',side_effect=KeyboardInterrupt):
                code,out,err=self.run_cli(['start','--state-dir',d])
            self.assertEqual(code,2)
            self.assertIn('reset_state_error',err)
            self.assertNotIn('PRIVATE_CLEANUP_DETAIL',out+err)
            state=State(Path(d)/'public-reset-watch');state.close()


class PublicProcessTests(unittest.TestCase):
    """Real local process lifecycle, fake public provider, no network/account."""
    def launch(self,directory):
        script='''import sys
sys.path.insert(0,sys.argv[1])
from quota_guard import reset_cli
class Fake:
    key='process-fixture'
    attribution='https://provider.example/public.json'
    def __init__(self,*args):pass
    def fetch(self,now):return now,[]
reset_cli.ModelYardProvider=Fake
raise SystemExit(reset_cli.main(['start','--state-dir',sys.argv[2]]))
'''
        return subprocess.Popen([sys.executable,'-c',script,str(ROOT),str(directory)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,cwd='/tmp')
    def await_baseline(self,directory,proc):
        end=time.monotonic()+5
        while time.monotonic()<end:
            self.assertIsNone(proc.poll())
            try:
                saved=json.loads((Path(directory)/'public-reset-watch/announcements.json').read_text())
                if saved['providers']['process-fixture'].get('baseline_at'):return
            except (FileNotFoundError,KeyError,json.JSONDecodeError):pass
            time.sleep(.01)
        self.fail('no baseline')
    def test_cooperative_stop_and_sigterm_do_not_leave_writer_lock(self):
        for how in ('stop','sigterm'):
            with self.subTest(how=how),tempfile.TemporaryDirectory() as d:
                proc=self.launch(d)
                try:
                    self.await_baseline(d,proc)
                    if how=='stop':
                        result=subprocess.run([sys.executable,str(ROOT/'scripts/quota_guard.py'),'resetwatch','stop','--state-dir',d],capture_output=True,text=True,timeout=5,cwd='/tmp')
                        self.assertEqual(result.returncode,0,result.stderr)
                        self.assertTrue(json.loads(result.stdout)['stop_requested'])
                    else:proc.send_signal(signal.SIGTERM)
                    out,err=proc.communicate(timeout=5)
                    self.assertEqual(proc.returncode,0 if how=='stop' else 130,err)
                    self.assertEqual(json.loads(out.splitlines()[-1])['status'],'reset_stopped')
                    state=State(Path(d)/'public-reset-watch')
                    self.assertIsNone(state.data['monitor_token']);state.close()
                    self.assertFalse((Path(d)/'state.json').exists())
                finally:
                    if proc.poll() is None:proc.kill()
                    proc.communicate()


if __name__=='__main__':unittest.main()
