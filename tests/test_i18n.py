"""Presentation-only localization tests; no real account data or RPC calls."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from quota_guard.cli import main
from quota_guard.core import Guard, Policy
from quota_guard.i18n import SUPPORTED, catalog, emit, render, select_locale
from test_guard import payload

ROOT = Path(__file__).resolve().parents[1]


class LocaleTests(unittest.TestCase):
    def test_locale_selection_and_fallback(self):
        for raw, expected in [('ZH_cn', 'zh'), ('pt-BR', 'pt'), ('de-DE', 'de'),
                              (' FR ', 'fr'), ('ja-JP', 'ja'), ('ko_KR', 'ko'),
                              ('ru-RU', 'ru'), ('es-MX', 'es'), ('EN-us', 'en'),
                              ('xx', 'en'), ('../../secret', 'en'), ('', 'en'), (None, 'en')]:
            self.assertEqual(select_locale(raw), expected)

    def test_nine_catalogs_have_complete_utf8_keys(self):
        english = catalog('en')
        for locale in SUPPORTED:
            data = json.loads((ROOT/'quota_guard/locales'/f'{locale}.json').read_text(encoding='utf-8'))
            self.assertEqual(set(data), set(english))
            self.assertTrue(all(isinstance(value, str) and value for value in data.values()))
            if locale != 'en':
                self.assertNotEqual(data['title'], english['title'])
            self.assertTrue((ROOT/'docs/i18n'/f'{locale}.md').is_file())

    def test_missing_translation_key_falls_back_to_english(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)/'locales'; root.mkdir()
            (root/'en.json').write_text(json.dumps(catalog('en')), encoding='utf-8')
            (root/'fr.json').write_text('{"title":"Rapport", "reason":null}', encoding='utf-8')
            catalog.cache_clear()
            try:
                with patch('quota_guard.i18n.files', return_value=Path(d)):
                    translated = catalog('fr')
                    self.assertEqual(translated['title'], 'Rapport')
                    self.assertEqual(translated['reason'], 'Status')
                    self.assertEqual(catalog('ja')['title'], 'Codex quota report')
            finally:
                catalog.cache_clear()

    def test_human_report_keeps_values_and_utc(self):
        guard = Guard(Policy('demo'))
        guard.ingest(payload(used=27.5), 1000)
        report = guard.decision(1000)
        original = json.dumps(report, sort_keys=True)
        for locale in SUPPORTED:
            text = render(report, locale)
            self.assertIn('72.5%', text)
            self.assertIn('300', text)
            self.assertIn('1970-01-01T00:16:40+00:00', text)
            self.assertIn(catalog(locale)['data_valid']+': '+catalog(locale)['yes'], text)
            self.assertIn(catalog(locale)['advisory'], text)
        self.assertEqual(json.dumps(report, sort_keys=True), original)

    def test_invalid_stale_and_checkpoint_never_presented_confirmed(self):
        report = {'reason':'stale', 'allow_new_work':False, 'data_valid':False,
                  'stale':True, 'checkpoint_status':'unexpected-confirmed',
                  'managed_action':'interrupt_acknowledged'}
        for locale in SUPPORTED:
            words = catalog(locale)
            text = render(report, locale)
            self.assertIn(words['stale_reason'], text)
            self.assertIn(words['data_valid']+': '+words['no'], text)
            self.assertIn(words['checkpoint']+': '+words['unconfirmed'], text)
            self.assertNotIn('unexpected-confirmed', text)

    def test_json_emission_unchanged_for_every_locale(self):
        report = {'allow_new_work':False, 'reason':'low_quota', 'remaining_percent':12}
        for locale in SUPPORTED + ('xx',):
            output = io.StringIO()
            emit(report, locale=locale, stream=output)
            self.assertEqual(output.getvalue(), json.dumps(report)+'\n')

    def test_ascii_terminal_does_not_crash_on_translations(self):
        raw = io.BytesIO()
        output = io.TextIOWrapper(raw, encoding='ascii', errors='strict')
        emit({'allow_new_work':False, 'reason':'missing'}, 'text', 'zh', output)
        output.flush()
        result = raw.getvalue().decode('ascii')
        self.assertIn('\\u', result)
        self.assertNotIn('Traceback', result)

    def test_unknown_reason_and_invalid_time_fail_to_unknown(self):
        words = catalog('de')
        output = render({'reason':'unknown-future-code', 'observed_at':1e100}, 'de')
        self.assertIn(words['reason']+': '+words['unknown'], output)
        self.assertIn(words['observed_at']+': '+words['unknown'], output)
        self.assertNotIn('unknown-future-code', output)


class LocalizedCliTests(unittest.TestCase):
    def test_locale_never_changes_simulation_json_or_state_policy(self):
        reference = None
        for locale in SUPPORTED + ('xx',):
            with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(['simulate', '--bucket','demo', '--fixture','fixtures/demo.jsonl',
                                       '--state-dir',d, '--locale',locale]),0)
                if reference is None:
                    reference = out.getvalue()
                self.assertEqual(out.getvalue(), reference)
                saved = json.loads((Path(d)/'state.json').read_text())
                self.assertFalse(saved['decision']['allow_new_work'])
                self.assertNotIn('locale', saved)
                self.assertEqual(saved['policy'], vars(Policy('demo')))

    def test_text_read_uses_same_policy_and_exit_codes(self):
        for locale in SUPPORTED:
            for used, code in ((20,0),(95,2)):
                calls=[]
                class Fake:
                    generation=0
                    def __init__(self, **kwargs): pass
                    def call(self, method):
                        calls.append(method)
                        return payload(used=used)
                    def close(self): pass
                with tempfile.TemporaryDirectory() as d, patch('quota_guard.cli.RPC',Fake), patch('quota_guard.cli.time.time',return_value=1000), contextlib.redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(main(['read','--bucket','demo','--state-dir',d,
                                           '--format','text','--locale',locale]),code)
                    self.assertIn(catalog(locale)['title'],out.getvalue())
                    self.assertEqual(calls,['account/rateLimits/read'])
                    saved=json.loads((Path(d)/'state.json').read_text())
                    self.assertEqual(saved['decision']['reason'],'healthy' if code==0 else 'low_quota')
                    self.assertNotIn('locale',saved)

    def test_configuration_error_localized_without_secret_detail(self):
        for locale in SUPPORTED:
            with contextlib.redirect_stderr(io.StringIO()) as out:
                self.assertEqual(main(['read','--bucket','demo','--reserve','-1',
                                       '--format','text','--locale',locale]),2)
            self.assertIn(catalog(locale)['configuration_or_io_error'],out.getvalue())
            self.assertNotIn('Traceback',out.getvalue())

    def test_localized_stop_acceptance_does_not_claim_exit(self):
        words=catalog('ja')
        output=render({'allow_new_work':False,'reason':'stop_requested'},'ja')
        self.assertIn(words['stop_requested'],output)
        self.assertNotIn(words['reason']+': '+words['monitor_stopped'],output)


if __name__=='__main__':
    unittest.main()
