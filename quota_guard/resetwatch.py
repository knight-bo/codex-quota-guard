"""Opt-in public announcements. Never imports RPC, quota policy or task control.

Provider statements are third-party reports, even when a provider says
"directly verified". A successful poll says nothing about any account's quota.
"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.client import HTTPException
import hashlib
import ipaddress
import json
import random
import re
import time
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from . import __version__
from .core import number

TYPES = ('planned', 'completed', 'banked', 'manual_credit')
ORIGIN = 'https://tibo.modelyard.dev'
MAX_BYTES = 1024 * 1024
MAX_EVENTS = 500
POST = re.compile(r'https://(?:x\.com|twitter\.com)/thsottiaux/status/([0-9]{15,22})/?\Z', re.I)


class WatchError(Exception):
    def __init__(self, code, retry_after=0):
        super().__init__(code)
        self.code, self.retry_after = code, retry_after


def public_url(value):
    """Explicit public HTTPS endpoints only; never send auth, cookies or redirects."""
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) <= 32 for c in value):
        raise WatchError('reset_configuration_error')
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None or
                parsed.password is not None or parsed.port not in (None, 443) or parsed.fragment):
            raise ValueError()
        host = parsed.hostname.lower()
        if host.endswith('.'):
            raise ValueError()
        if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')) or '.' not in host:
            raise ValueError()
        try:
            if not ipaddress.ip_address(host).is_global:
                raise ValueError()
        except ValueError:
            # Numeric literals must actually be globally routable IP addresses.
            if re.fullmatch(r'[0-9.:]+', host) or ':' in host:
                raise ValueError()
    except ValueError:
        raise WatchError('reset_configuration_error') from None
    if host not in {'tibo.modelyard.dev', 'codexresets.com', 'x.com', 'twitter.com'}:
        raise WatchError('reset_source_error')
    return value


def utc(value):
    """Strict timezone-bearing wire dates. No local timezone guesses."""
    if not isinstance(value, str) or len(value) > 64:
        raise WatchError('reset_parse_error')
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if date.utcoffset() is None:
            raise ValueError()
        return date.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise WatchError('reset_parse_error') from None


def iso(date):
    return date.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def event_record(value, now):
    """Allowlisted contract, also used by replaceable JSON providers/fixtures."""
    if not isinstance(value, dict) or value.get('event_type') not in TYPES:
        raise WatchError('reset_parse_error')
    match = POST.fullmatch(value.get('post_url', '')) if isinstance(value.get('post_url'), str) else None
    if not match or value.get('post_id') != match[1]:
        raise WatchError('reset_source_error')
    published = utc(value.get('published_at'))
    timing = value.get('update_time_source', 'provider' if 'updated_at' in value else 'publication')
    if timing not in ('provider', 'publication', 'unavailable'):
        raise WatchError('reset_parse_error')
    updated = None if timing == 'unavailable' else utc(value.get('updated_at', value.get('published_at')))
    if timing == 'unavailable' and value.get('updated_at') is not None:
        raise WatchError('reset_parse_error')
    # The snowflake is a consistency check, NOT authentication of the author.
    post_time = ((int(match[1]) >> 22) + 1288834974657) / 1000
    if abs(post_time - published.timestamp()) > 120 or not (0 <= published.timestamp() <= (updated or published).timestamp() <= now + 300):
        raise WatchError('reset_parse_error')
    products = value.get('products')
    if (not isinstance(products, list) or not products or
            any(p not in ('codex', 'chatgpt_work', 'chatgpt', 'unknown') for p in products)):
        raise WatchError('reset_parse_error')
    try:
        source_url = public_url(value.get('source_url'))
    except WatchError:
        raise WatchError('reset_source_error') from None
    claim = value.get('source_verification', 'unverified')
    if claim not in ('directly_verified', 'indexed_only', 'unverified'):
        raise WatchError('reset_parse_error')
    scope = value.get('scope_provenance', 'provider_reported')
    if scope not in ('source_text', 'unspecified', 'provider_reported'):
        raise WatchError('reset_parse_error')
    reported = value.get('reported_products', products)
    if not isinstance(reported, list) or not reported or any(p not in ('codex', 'chatgpt_work', 'chatgpt', 'unknown') for p in reported):
        raise WatchError('reset_parse_error')
    return {'post_id': match[1], 'post_url': value['post_url'],
            'published_at': iso(published), 'updated_at': iso(updated) if updated else None,
            'event_type': value['event_type'], 'products': sorted(set(products)),
            'source_url': source_url, 'source_verification': claim,
            'verification': 'third_party_reported',
            'update_time_source': timing, 'scope_provenance': scope, 'reported_products': sorted(set(reported))}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise WatchError('reset_source_error')


class PublicHTTP:
    """Anonymous bounded GETs. No X access, credentials, cookies or uploads.

    One snapshot shares a deadline. read1 avoids unbounded buffered reads; a
    deadline can overrun by at most one socket timeout (both <=30 seconds).
    """
    def __init__(self, timeout=10):
        if not number(timeout) or not 1 <= timeout <= 30:
            raise WatchError('reset_configuration_error')
        self.timeout = timeout
        self.opener = build_opener(NoRedirect())

    def get(self, url, deadline, content_types):
        public_url(url)
        if url != ORIGIN + '/feed.xml':
            raise WatchError('reset_source_error')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise WatchError('reset_network_error')
        request = Request(url, headers={'User-Agent': 'codex-quota-guard/' + __version__,
                                       'Accept': ', '.join(content_types)})
        try:
            with self.opener.open(request, timeout=min(self.timeout, remaining)) as response:
                if response.status != 200 or response.geturl() != url:
                    raise WatchError('reset_source_error')
                if response.headers.get_content_type() not in content_types:
                    raise WatchError('reset_parse_error')
                chunks, size = [], 0
                while True:
                    if time.monotonic() >= deadline:
                        raise WatchError('reset_network_error')
                    chunk = response.read1(min(65536, MAX_BYTES + 1 - size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise WatchError('reset_parse_error')
                try:
                    return b''.join(chunks).decode('utf-8-sig')
                except UnicodeError:
                    raise WatchError('reset_parse_error') from None
        except HTTPError as error:
            delay = 0
            if error.code in (429, 503):
                raw = error.headers.get('Retry-After', '')
                try:
                    delay = float(raw) if raw.isdecimal() else parsedate_to_datetime(raw).timestamp() - time.time()
                except (ValueError, TypeError, OverflowError):
                    pass
            code = error.code
            error.close()
            raise WatchError('reset_rate_limited' if code == 429 else 'reset_network_error',
                             min(86400, max(0, delay))) from None
        except (URLError, OSError, TimeoutError, HTTPException):
            raise WatchError('reset_network_error') from None


ATOM = 'http://www.w3.org/2005/Atom'
FEED_URL = ORIGIN + '/feed.xml'
MAX_ENTRY_BYTES = 32768
CATEGORIES = {'Reset Planned': 'planned', 'Reset Completed': 'completed',
              'Reset cards': 'banked', 'Manual Credit': 'manual_credit'}
OTHER_CATEGORIES = {'Codex Update', 'Time Changed', 'Policy', 'Roadmap Hint', 'Feature Discussion'}


def rss_date(value):
    """RFC 822 with an explicit timezone; independent of local clock/locale."""
    if not isinstance(value, str) or len(value) > 80:
        raise WatchError('reset_parse_error')
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.utcoffset() is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        raise WatchError('reset_parse_error') from None


def xml_text(parent, name, required=True):
    elements = parent.findall(name)
    if len(elements) != 1:
        if not elements and not required:
            return None
        raise WatchError('reset_parse_error')
    element = elements[0]
    value = (element.text or '').strip()
    # The supplied real RSS uses plain text. Do not interpret embedded HTML,
    # templates, hidden elements or arbitrary nested XML as announcement fields.
    attrs_ok = element.attrib in ({}, {'isPermaLink': 'true'}) if name == 'guid' else not element.attrib
    if not attrs_ok or len(element) or '<' in value or '>' in value or (required and not value):
        raise WatchError('reset_parse_error')
    return value


def product_scope(text):
    # Ambiguous/negated product references are not affirmative scope evidence.
    if re.search(r'\b(?:not|except|excluding|without)\b', text, re.I):
        return ['unknown']
    products = []
    if re.search(r'\bcodex\b', text, re.I):
        products.append('codex')
    if re.search(r'\bChatGPT\s+Work\b|\bCodex\s*(?:/|and|&)\s*Work\b', text, re.I):
        products.append('chatgpt_work')
    elif re.search(r'\bchatgpt\b', text, re.I):
        products.append('chatgpt')
    return products or ['unknown']


def parse_modelyard_rss(text, now):
    """RSS 2.0 contract verified against the explicitly cropped real sample.

    lastBuildDate is a feed/event date, NEVER a provider-sync heartbeat. A valid
    old feed can establish a baseline, but cannot prove complete/current coverage.
    Raw descriptions and source text are only inspected, never persisted/emitted.
    """
    if (not isinstance(text, str) or len(text.encode('utf-8')) > MAX_BYTES or
            re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b', text, re.I)):
        raise WatchError('reset_parse_error')
    try:
        root = ET.fromstring(text)
    except (ET.ParseError, ValueError, RecursionError):
        raise WatchError('reset_parse_error') from None
    if (root.tag != 'rss' or root.attrib != {'version': '2.0'} or
            len(root) != 1 or root[0].tag != 'channel'):
        raise WatchError('reset_parse_error')
    channel = root[0]
    if channel.attrib:
        raise WatchError('reset_parse_error')
    allowed = {'title', 'link', 'description', 'language', 'lastBuildDate', 'item', '{' + ATOM + '}link'}
    if any(child.tag not in allowed for child in channel):
        raise WatchError('reset_parse_error')
    if xml_text(channel, 'title') != 'ModelYard · Tibo Codex Monitor':
        raise WatchError('reset_source_error')
    if xml_text(channel, 'link') != ORIGIN + '/':
        raise WatchError('reset_source_error')
    xml_text(channel, 'description')
    if xml_text(channel, 'language') != 'en':
        raise WatchError('reset_parse_error')
    atom_links = channel.findall('{' + ATOM + '}link')
    if (len(atom_links) != 1 or atom_links[0].attrib !=
            {'href': FEED_URL, 'rel': 'self', 'type': 'application/rss+xml'} or len(atom_links[0])):
        raise WatchError('reset_source_error')
    build = xml_text(channel, 'lastBuildDate', required=False)
    build_at = rss_date(build).timestamp() if build else None
    if build_at is not None and not 0 <= build_at <= now + 300:
        raise WatchError('reset_parse_error')
    items = channel.findall('item')
    if len(items) > MAX_EVENTS:
        raise WatchError('reset_parse_error')
    events, published_times = [], []
    for item in items:
        if (item.attrib or any(len(child) or child.tag not in {'title', 'description', 'link', 'guid', 'pubDate', 'category'} for child in item) or
                len(ET.tostring(item, encoding='utf-8')) > MAX_ENTRY_BYTES):
            raise WatchError('reset_parse_error')
        xml_text(item, 'title')
        description = xml_text(item, 'description')
        item_url = xml_text(item, 'link')
        guid = xml_text(item, 'guid')
        if not re.fullmatch(r'https://tibo\.modelyard\.dev/events/[0-9]{1,12}', item_url) or guid != item_url:
            raise WatchError('reset_source_error')
        if item.find('guid').attrib not in ({}, {'isPermaLink': 'true'}):
            raise WatchError('reset_parse_error')
        published = rss_date(xml_text(item, 'pubDate'))
        if not 0 <= published.timestamp() <= now + 300:
            raise WatchError('reset_parse_error')
        published_times.append(published.timestamp())
        category = xml_text(item, 'category')  # Multiple categories are ambiguous, even under another namespace.
        if category not in CATEGORIES:
            if category in OTHER_CATEGORIES:
                continue
            raise WatchError('reset_parse_error')
        sources = re.findall(r'^Source:[ \t]*(\S+)[ \t]*$', description, re.M)
        if (len(sources) != 1 or not re.search(r'^Source:[ \t]*\S+[ \t]*\Z', description, re.M) or
                not (match := POST.fullmatch(sources[0]))):
            raise WatchError('reset_source_error')
        original_text = description.split('Source text:', 1)[1].rsplit('Source:', 1)[0] if 'Source text:' in description else ''
        products = product_scope(original_text)
        reported_products = product_scope(xml_text(item, 'title'))
        scope = 'source_text' if products != ['unknown'] else 'unspecified'
        events.append(event_record({'event_type': CATEGORIES[category], 'post_id': match[1],
            'post_url': sources[0], 'published_at': iso(published),
            'products': products, 'reported_products': reported_products, 'scope_provenance': scope,
            'source_url': item_url, 'source_verification': 'unverified',
            'update_time_source': 'unavailable'}, now))
    metadata = {'fetched_at': now, 'source_latest_published_at': max(published_times) if published_times else None,
                'feed_last_build_at': build_at, 'source_coverage': 'unknown'}
    return metadata, events


class ModelYardProvider:
    """Anonymous public RSS only. No HTML/API/JSON discovery or X requests."""
    key, url, attribution = 'modelyard:rss-v1', FEED_URL, ORIGIN + '/'
    source_check_available = False

    def __init__(self, http):
        self.http = http
        self.snapshot_metadata = {}

    def fetch(self, now):
        text = self.http.get(self.url, time.monotonic() + self.http.timeout,
                             ('application/rss+xml', 'application/xml', 'text/xml'))
        self.snapshot_metadata, events = parse_modelyard_rss(text, now)
        return None, events  # RSS has no observed source-synchronization heartbeat.




def parse_json(text, now):
    try:
        data = json.loads(text)
        if not isinstance(data, dict) or data.get('schema_version') != 1 or type(data.get('schema_version')) is not int:
            raise ValueError()
        values = data['events']
        if not isinstance(values, list) or len(values) > MAX_EVENTS:
            raise ValueError()
        return utc(data['checked_at']).timestamp(), [event_record(e, now) for e in values]
    except (ValueError, KeyError, TypeError, RecursionError):
        raise WatchError('reset_parse_error') from None


class ResetWatch:
    """Persistent at-most-once event ledger, baseline and scheduling. No quota state."""
    def __init__(self, state, provider, event_types=TYPES, interval=3600, max_age=172800,
                 event_age=604800, timezone_name='UTC'):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        if (not event_types or any(v not in TYPES for v in event_types) or
                not all(number(v) for v in (interval, max_age, event_age)) or
                not 3600 <= interval <= 86400 or not interval <= max_age <= 604800 or
                not 3600 <= event_age <= 2592000):
            raise WatchError('reset_configuration_error')
        try:
            ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            raise WatchError('reset_configuration_error') from None
        self.state, self.provider = state, provider
        self.types, self.interval, self.max_age, self.event_age = set(event_types), interval, max_age, event_age
        self.timezone = timezone_name
        saved = state.read('announcements.json')
        self.data = saved if saved is not None else {'schema_version': 1, 'providers': {}, 'seen': {}}
        if (type(self.data.get('schema_version')) is not int or self.data.get('schema_version') != 1 or not isinstance(self.data.get('providers'), dict) or
                not isinstance(self.data.get('seen'), dict)):
            raise WatchError('reset_state_error')
        self.ledger = self.data['providers'].setdefault(provider.key, {})
        self.validate_state()

    def validate_state(self):
        if len(self.data['seen']) > 5000 or not isinstance(self.ledger, dict):
            raise WatchError('reset_state_error')
        for ledger in self.data['providers'].values():
            if not isinstance(ledger, dict):
                raise WatchError('reset_state_error')
            for field in ('baseline_at', 'next_poll_at', 'last_success_at', 'last_attempt_at', 'provider_checked_at', 'fetched_at', 'source_latest_published_at', 'feed_last_build_at'):
                if field in ledger and not (field in ('provider_checked_at', 'source_latest_published_at', 'feed_last_build_at') and ledger[field] is None) and (not number(ledger[field]) or ledger[field] < 0):
                    raise WatchError('reset_state_error')
            failures = ledger.get('failures', 0)
            if type(failures) is not int or not 0 <= failures <= 16:
                raise WatchError('reset_state_error')
        for key, entry in self.data['seen'].items():
            if (not re.fullmatch(r'[0-9]{15,22}', key) or not isinstance(entry, dict) or
                    not isinstance(entry.get('types'), list) or not entry['types'] or
                    any(t not in TYPES for t in entry['types']) or not number(entry.get('at')) or
                    not isinstance(entry.get('records'), dict) or set(entry['records']) != set(entry['types'])):
                raise WatchError('reset_state_error')
            for kind, record in entry['records'].items():
                if not isinstance(record, dict) or record.get('post_id') != key or record.get('event_type') != kind:
                    raise WatchError('reset_state_error')
                try:
                    observed = record.get('first_observed_status_at')
                    if observed is not None and (not number(observed) or not 0 <= observed <= entry['at']):
                        raise WatchError('reset_state_error')
                    event_record(record, utc(record.get('updated_at') or record.get('published_at')).timestamp())
                except WatchError:
                    raise WatchError('reset_state_error') from None

    def save(self):
        if len(json.dumps(self.data, allow_nan=False)) > MAX_BYTES:
            raise WatchError('reset_state_error')
        self.state.write('announcements.json', self.data)

    def report(self, status, now, events=None):
        return {'schema_version': 1, 'kind': 'public_reset_watch', 'status': status,
                'checked_at': now, 'last_success_at': self.ledger.get('last_success_at'),
                'provider_checked_at': self.ledger.get('provider_checked_at'),
                'fetched_at': self.ledger.get('fetched_at'),
                'source_latest_published_at': self.ledger.get('source_latest_published_at'),
                'feed_last_build_at': self.ledger.get('feed_last_build_at'),
                'source_coverage': 'unknown',
                'latest_entry_age_seconds': max(0, now - self.ledger['source_latest_published_at']) if self.ledger.get('source_latest_published_at') is not None else None,
                'last_poll_status': self.ledger.get('last_poll_status'),
                'next_poll_at': self.ledger.get('next_poll_at'),
                'provider': self.provider.key.split(':', 1)[0], 'source_url': self.provider.attribution,
                'timezone': self.timezone, 'interval_seconds': self.interval, 'max_age_seconds': self.max_age,
                'events': events or [], 'personal_quota_verified': False, 'task_action': 'none'}

    def poll(self, now=None):
        now = time.time() if now is None else now
        last = self.ledger.get('last_attempt_at')
        if last is not None and now < last:
            return self.report('reset_clock_error', now)
        if now < self.ledger.get('next_poll_at', 0):
            return self.report('reset_waiting', now)
        # Persist the minimum cooldown BEFORE network I/O, including failed/crashed polls.
        self.ledger.update(last_attempt_at=now, next_poll_at=now + self.interval)
        self.save()
        try:
            checked, events = self.provider.fetch(now)
            if checked is None:
                if getattr(self.provider, 'source_check_available', True):
                    raise WatchError('reset_parse_error')
            elif not number(checked) or not 0 <= checked <= now + 300:
                raise WatchError('reset_parse_error')
            if checked is not None and now - checked > self.max_age:
                raise WatchError('reset_stale')
            if not isinstance(events, list) or len(events) > MAX_EVENTS:
                raise WatchError('reset_parse_error')
            # Revalidate even injectable providers and reject contradictory same-post/type rows.
            normalized = [event_record(e, now) for e in events]
            unique = {}
            for event in normalized:
                key = (event['post_id'], event['event_type'])
                if key in unique and unique[key] != event:
                    raise WatchError('reset_parse_error')
                unique[key] = event
            normalized = sorted(unique.values(), key=lambda e: (e['updated_at'] or e['published_at'], e['event_type'] == 'completed', e['post_id']))
            for event in normalized:
                if event['event_type'] == 'completed':
                    prior = self.data['seen'].get(event['post_id'], {}).get('records', {}).get('planned')
                    planned = unique.get((event['post_id'], 'planned'), prior)
                    if planned and event['updated_at'] and planned['updated_at'] and event['updated_at'] < planned['updated_at']:
                        raise WatchError('reset_parse_error')
        except WatchError as error:
            failures = min(16, self.ledger.get('failures', 0) + 1)
            delay = max(self.interval, error.retry_after,
                        min(86400, self.interval * 2 ** min(failures - 1, 5)) * random.uniform(1, 1.1))
            self.ledger.update(failures=failures, next_poll_at=now + min(86400, delay), last_poll_status=error.code)
            self.save()
            return self.report(error.code, now)
        baseline = self.ledger.get('baseline_at')
        origin = now if baseline is None else baseline
        completed = {e['post_id'] for e in normalized if e['event_type'] == 'completed'}
        pending = []
        for event in normalized:
            ident, kind = event['post_id'], event['event_type']
            prior = self.data['seen'].get(ident, {'types': [], 'at': now, 'records': {}})
            seen = prior['types']
            upgrade = kind == 'completed' and 'planned' in seen and 'completed' not in seen
            candidate = (kind not in seen and not (kind == 'planned' and ('completed' in seen or ident in completed)))
            published = utc(event['published_at']).timestamp()
            updated = utc(event['updated_at']).timestamp() if event['updated_at'] else None
            local_update = upgrade and event['update_time_source'] == 'unavailable'
            recent = published >= origin or (upgrade and updated is not None and updated > origin) or (local_update and now > origin)
            effective_time = updated if upgrade and updated is not None else published
            first_observed = prior['records'].get(kind, {}).get('first_observed_status_at', now)
            if (baseline is not None and candidate and recent and
                    now - effective_time <= self.event_age and kind in self.types and event['products'] != ['chatgpt']):
                pending.append(dict(event, schema_version=1,
                    id=hashlib.sha256((ident + ':' + kind).encode()).hexdigest(),
                    source=self.provider.key.split(':', 1)[0], observed_at=now, first_observed_status_at=first_observed,
                    announcement_kind='aggregation_status_update' if local_update else 'post_announcement',
                    status_time_provenance='local_observation' if local_update else event['update_time_source'],
                    user_notified=False, personal_quota_verified=False, task_action='none'))
                if self.provider.key.startswith('fixture:'):
                    pending[-1]['verification'] = 'synthetic'
            if kind not in seen:
                seen.append(kind)
            records = prior['records']
            # Older observations cannot overwrite saved provenance for a newer state.
            if kind not in records or (event['updated_at'] or event['published_at']) >= (records[kind]['updated_at'] or records[kind]['published_at']):
                records[kind] = dict(event, source=self.provider.key.split(':', 1)[0], first_observed_status_at=first_observed)
                if self.provider.key.startswith('fixture:'):
                    records[kind]['verification'] = 'synthetic'
            self.data['seen'][ident] = {'types': seen, 'at': now, 'records': records}
        if len(self.data['seen']) > 4000:
            # Safe horizon: discarded posts are older than event_age and every provider baseline.
            cutoff = min([now - self.event_age] + [p.get('baseline_at', now) for p in self.data['providers'].values()])
            self.data['seen'] = {k: v for k, v in self.data['seen'].items() if v['at'] >= cutoff}
        if len(self.data['seen']) > 5000:
            raise WatchError('reset_state_error')
        self.ledger.update(baseline_at=now if baseline is None else baseline, last_success_at=now,
                           provider_checked_at=checked, fetched_at=now, failures=0,
                           source_latest_published_at=getattr(self.provider, 'snapshot_metadata', {}).get('source_latest_published_at'),
                           feed_last_build_at=getattr(self.provider, 'snapshot_metadata', {}).get('feed_last_build_at'),
                           last_poll_status='reset_baseline' if baseline is None else 'reset_ok')
        # Durable intent precedes delivery: a crash can lose a notification, never replay it.
        self.save()
        return self.report('reset_baseline' if baseline is None else 'reset_ok', now, pending)
