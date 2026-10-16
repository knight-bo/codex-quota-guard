"""Optional human presentation only. Never translates policy or wire fields."""
from datetime import datetime, timezone
from functools import lru_cache
from importlib.resources import files
import json
import sys

from .core import number

SUPPORTED = ('en', 'zh', 'ru', 'ja', 'ko', 'es', 'fr', 'de', 'pt')


def select_locale(value):
    """Explicit locale only; regional variants use their base language."""
    if not isinstance(value, str):
        return 'en'
    base = value.strip().lower().replace('_', '-').split('-', 1)[0]
    return base if base in SUPPORTED else 'en'


@lru_cache(maxsize=len(SUPPORTED))
def catalog(locale):
    locale = select_locale(locale)
    root = files('quota_guard').joinpath('locales')
    english = json.loads(root.joinpath('en.json').read_text(encoding='utf-8'))
    if locale == 'en':
        return english
    try:
        translated = json.loads(root.joinpath(locale+'.json').read_text(encoding='utf-8'))
        if not isinstance(translated, dict):
            return english
        return {key: translated.get(key) if isinstance(translated.get(key), str) and translated[key]
                else value for key, value in english.items()}
    except (OSError, ValueError):
        return english


def render(report, locale='en'):
    words = catalog(select_locale(locale))
    def label(key):
        return words.get(key, words['unknown']) if isinstance(key, str) else words['unknown']
    def boolean(value):
        return label('yes' if value is True else 'no' if value is False else 'unknown')
    def numeric(value):
        return str(value) if number(value) else label('unknown')
    def timestamp(value):
        if not number(value):
            return label('unknown')
        try:
            return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec='seconds')
        except (OverflowError, OSError, ValueError):
            return label('unknown')
    reason = report.get('reason', 'unknown')
    reason = 'stale_reason' if reason == 'stale' else reason
    lines = [label('title'), label('reason')+': '+label(reason),
             label('admission')+': '+boolean(report.get('allow_new_work'))]
    bucket = report.get('bucket')
    if isinstance(bucket, str):
        lines.append(label('bucket')+': '+json.dumps(bucket, ensure_ascii=False))
    # Display only established report fields, never raw RPC payloads or errors.
    for key in ('data_valid', 'stale'):
        lines.append(label(key)+': '+boolean(report.get(key)))
    for key in ('observed_at', 'valid_until', 'reported_at'):
        lines.append(label(key)+': '+timestamp(report.get(key)))
    windows = report.get('windows', {})
    for name in ('primary', 'secondary'):
        window = windows.get(name) if isinstance(windows, dict) else None
        if not isinstance(window, dict):
            continue
        lines.extend([label(name)+':',
                      '  '+label('remaining')+': '+numeric(window.get('remaining_percent'))+'%',
                      '  '+label('duration')+': '+numeric(window.get('window_duration_mins')),
                      '  '+label('resets_at')+': '+timestamp(window.get('resets_at'))])
    if 'managed_action' in report:
        lines.append(label('managed_action')+': '+label(report['managed_action']))
    if 'checkpoint_status' in report:
        # Never render a checkpoint as confirmed, including unexpected values.
        lines.append(label('checkpoint')+': '+label('unconfirmed'))
    lines.append(label('advisory'))
    return '\n'.join(lines)


def emit(report, output_format='json', locale='en', stream=None):
    stream = sys.stdout if stream is None else stream
    text = json.dumps(report) if output_format == 'json' else render(report, locale)
    try:
        print(text, file=stream, flush=True)
    except UnicodeEncodeError:
        # Legacy terminals retain a readable escaped representation, not a crash.
        encoding = getattr(stream, 'encoding', None) or 'ascii'
        print(text.encode(encoding, errors='backslashreplace').decode(encoding), file=stream, flush=True)
