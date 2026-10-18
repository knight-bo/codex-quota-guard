"""Localized payload for a host's existing local notification adapter.

No subprocess, OS permission request, remote message or user-data upload. The
host owns delivery and records actual success separately from the event ledger.
"""
from zoneinfo import ZoneInfo
from .i18n import catalog
from .resetwatch import TYPES, utc


def notification_payload(event, locale='en', timezone_name='UTC'):
    words = catalog(locale)
    if event.get('event_type') not in TYPES:
        raise ValueError('invalid_public_event')
    published = utc(event['published_at']).astimezone(ZoneInfo(timezone_name)).isoformat(timespec='seconds')
    extra = []
    if event.get('announcement_kind') == 'aggregation_status_update':
        extra.append(words['reset_aggregation_update'])
    products = event.get('products', ['unknown'])
    names = {'codex': 'Codex', 'chatgpt_work': 'ChatGPT Work', 'chatgpt': 'ChatGPT', 'unknown': words['unknown']}
    extra.append(words['reset_scope'] + ': ' + ', '.join(names.get(value, words['unknown']) for value in products))
    if 'unknown' in products:
        extra.append(words['reset_scope_unknown'])
    observed = event.get('first_observed_status_at')
    if observed is not None:
        from datetime import datetime
        extra.append(words['reset_first_observed_status_at'] + ': ' + datetime.fromtimestamp(observed, ZoneInfo(timezone_name)).isoformat(timespec='seconds'))
    return {'title': words['reset_title'],
            'body': '\n'.join((words['reset_' + event['event_type']],
                 *extra,
                 words['reset_published'] + ': ' + published,
                 words['reset_source'] + ': ' + event['source_url'],
                 words['reset_synthetic'] if event.get('verification') == 'synthetic' else words['reset_third_party'],
                 event['post_url'], words['reset_coverage_unknown'], words['reset_advisory'])),
            'post_url': event['post_url'], 'source_url': event['source_url']}


def deliver_local(event, notify, locale='en', timezone_name='UTC'):
    """Host supplies its existing local adapter; success never mutates consent/quota."""
    return notify(notification_payload(event, locale, timezone_name))
