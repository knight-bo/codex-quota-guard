"""Separate public-watch lifecycle; quota CLI and its state are untouched."""
import argparse
import hashlib
import signal
import sys
import threading
import time
import uuid
from pathlib import Path

from .i18n import catalog, emit, select_locale
from .resetwatch import (ModelYardProvider, PublicHTTP, ResetWatch,
                         TYPES, WatchError, parse_json, MAX_BYTES)
from .state import State


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # Never echo user arguments, provider responses or filesystem paths.
        raise WatchError('reset_configuration_error')

    def _print_message(self, message, file=None):
        if message:
            stream = sys.stderr if file is None else file
            try:
                stream.write(message)
            except UnicodeEncodeError:
                encoding = getattr(stream, 'encoding', None) or 'ascii'
                stream.write(message.encode(encoding, errors='backslashreplace').decode(encoding))


class FixtureProvider:
    def __init__(self, path):
        self.path = Path(path)
        self.key = 'fixture:' + hashlib.sha256(str(self.path.absolute()).encode()).hexdigest()
        self.attribution = 'offline_fixture'

    def fetch(self, now):
        with self.path.open('rb') as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise WatchError('reset_parse_error')
        try:
            return parse_json(data.decode('utf-8-sig'), now)
        except UnicodeError:
            raise WatchError('reset_parse_error') from None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    # Language discovery is presentation only; normal parsing still validates argv.
    language = 'en'
    fallback_format = 'json'
    for index, value in enumerate(argv):
        if value == '--locale' and index + 1 < len(argv):
            language = argv[index + 1]
        elif value.startswith('--locale='):
            language = value.split('=', 1)[1]
        if value == '--format' and index + 1 < len(argv):
            fallback_format = argv[index + 1]
        elif value.startswith('--format='):
            fallback_format = value.split('=', 1)[1]
    words = catalog(select_locale(language))
    parser = Parser(prog='codex-quota-guard resetwatch', add_help=False,
                    description=words['reset_help'], epilog=words['reset_limits'])
    parser._positionals.title = words['reset_commands']
    parser._optionals.title = words['reset_options']
    parser.add_argument('-h', '--help', action='help', help=words['reset_help_option'])
    parser.add_argument('action', choices=['read', 'start', 'stop', 'status'], help=words['reset_action_help'])
    parser.add_argument('--state-dir', default=str(Path.home()/'.local/state/codex-quota-guard'), help=words['reset_state_help'])
    parser.add_argument('--provider', choices=['modelyard'], default='modelyard', help=words['reset_provider_help'])
    parser.add_argument('--events', default=','.join(TYPES), help=words['reset_events_help'])
    parser.add_argument('--interval', type=float, default=3600, help=words['reset_interval_help'])
    parser.add_argument('--max-age', type=float, default=172800, help=words['reset_age_help'])
    parser.add_argument('--event-age', type=float, default=604800, help=words['reset_event_age_help'])
    parser.add_argument('--timeout', type=float, default=10, help=words['reset_timeout_help'])
    parser.add_argument('--timezone', default='UTC', help=words['reset_timezone_help'])
    parser.add_argument('--format', choices=['json', 'text'], default='json', help=words['reset_format_help'])
    parser.add_argument('--locale', default='en', help=words['reset_locale_help'])
    parser.add_argument('--fixture', help=words['reset_fixture_help'])
    args = state = None
    old_term = None
    token = None

    def output(report, stream=None):
        emit(report, args.format if args else ('text' if fallback_format == 'text' else 'json'),
             args.locale if args else language, stream)

    def basic(status):
        return {'schema_version': 1, 'kind': 'public_reset_watch', 'status': status,
                'events': [], 'personal_quota_verified': False, 'task_action': 'none'}

    try:
        args = parser.parse_args(argv)
        directory = Path(args.state_dir)/'public-reset-watch'
        if args.fixture:
            if args.action != 'read':
                raise WatchError('reset_configuration_error')
            directory = directory/'fixtures'  # Synthetic state can never poison live dedup/baselines.
        readonly = args.action in ('stop', 'status')
        if readonly:
            state = State(directory, readonly=True)
            if args.action == 'stop':
                requested = state.request_stop()
                output(dict(basic('reset_stop_requested' if requested else 'reset_no_monitor'), stop_requested=requested))
                return 0 if requested else 2
            report = state.read('report.json')
            if not report:
                output(basic('reset_no_status'))
                return 2
            report = dict(report, events=[], cached=True)
            now = time.time()
            checked = report.get('provider_checked_at')
            if checked is None:
                checked = report.get('fetched_at')
            if checked is None or now - checked > report.get('max_age_seconds', 172800):
                report['status'] = 'reset_stale'
            elif now < report.get('checked_at', now):
                report['status'] = 'reset_clock_error'
            output(report)
            return 0 if report.get('status') in ('reset_ok', 'reset_baseline', 'reset_waiting') else 2
        http = PublicHTTP(args.timeout)
        provider = FixtureProvider(args.fixture) if args.fixture else ModelYardProvider(http)
        state = State(directory)
        watch = ResetWatch(state, provider, args.events.split(','), args.interval, args.max_age,
                           args.event_age, args.timezone)
        token = uuid.uuid4().hex if args.action == 'start' else None
        state.data.update(monitor_token=token, kind='public_reset_watch')
        state.write('state.json', state.data)
        if token and threading.current_thread() is threading.main_thread():
            def terminate(signum, frame):
                raise KeyboardInterrupt()
            old_term = signal.signal(signal.SIGTERM, terminate)
        while True:
            if token and state.stop_requested(token):
                output(basic('reset_stopped'))
                return 0
            report = watch.poll()
            if token and state.stop_requested(token):
                output(basic('reset_stopped'))
                return 0
            if args.fixture:
                report['synthetic'] = True
            state.write('report.json', dict(report, events=[]))
            output(report)
            if args.action == 'read':
                return 0 if report['status'] in ('reset_ok', 'reset_baseline', 'reset_waiting') else 2
            # Interruptible cooperative wait; each process's persisted deadline survives restarts.
            deadline = time.monotonic() + max(1, report['next_poll_at'] - time.time())
            while time.monotonic() < deadline and not state.stop_requested(token):
                time.sleep(min(1, max(0, deadline - time.monotonic())))
    except KeyboardInterrupt:
        output(basic('reset_stopped'))
        return 130
    except (WatchError, OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        # All unexpected state/config/IO details are private. Provider WatchErrors
        # from polling are reported inside poll; this branch never creates events.
        output(basic(error.code if isinstance(error, WatchError) else 'reset_configuration_error'), sys.stderr)
        return 2
    finally:
        cleanup_failed = False
        if state:
            try:
                if token:
                    state.data['monitor_token'] = None
                    state.write('state.json', state.data)
            except (OSError, ValueError):
                cleanup_failed = True
            finally:
                try:
                    state.close()
                except OSError:
                    cleanup_failed = True
        if old_term is not None:
            signal.signal(signal.SIGTERM, old_term)
        if cleanup_failed:
            output(basic('reset_state_error'), sys.stderr)
            return 2
