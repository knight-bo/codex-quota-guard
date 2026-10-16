"""Bounded newline-delimited app-server transport; no raw logging."""
import json
import os
import selectors
import subprocess
import time
from . import __version__


class RpcError(Exception):
    pass


class RPC:
    def __init__(self, argv=None, timeout=10, on_update=None):
        self.timeout, self.on_update = timeout, on_update
        self.seq, self.buf = 0, bytearray()
        self.generation = 0
        self.proc = subprocess.Popen(argv or ['codex', 'app-server'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            bufsize=0, shell=False)
        self.sel = selectors.DefaultSelector()
        try:
            os.set_blocking(self.proc.stdin.fileno(), False)
            self.sel.register(self.proc.stdout, selectors.EVENT_READ)
            self.call('initialize', {'clientInfo': {'name': 'codex_quota_guard',
                      'version': __version__}})
            self.send({'method': 'initialized', 'params': {}})
        except BaseException:
            self.close()
            raise

    @staticmethod
    def remaining(deadline):
        left = deadline-time.monotonic()
        if left <= 0:
            raise RpcError('timeout')
        return left

    def send(self, message, deadline=None):
        deadline = time.monotonic()+self.timeout if deadline is None else deadline
        self.remaining(deadline)
        data = (json.dumps(message, allow_nan=False)+'\n').encode()
        if len(data) > 4096:
            raise RpcError('request_too_large')
        try:
            with selectors.DefaultSelector() as writable:
                writable.register(self.proc.stdin, selectors.EVENT_WRITE)
                offset = 0
                while offset < len(data):
                    if not writable.select(self.remaining(deadline)):
                        raise RpcError('timeout')
                    self.remaining(deadline)
                    try:
                        count = os.write(self.proc.stdin.fileno(), data[offset:])
                    except BlockingIOError:
                        continue
                    if count <= 0:
                        raise RpcError('short_write')
                    offset += count
            self.remaining(deadline)
        except OSError:
            raise RpcError('transport_closed') from None

    def read_chunk(self):
        data = os.read(self.proc.stdout.fileno(), 65536)
        if not data:
            raise RpcError('eof')
        self.buf.extend(data)
        if len(self.buf) > 1024*1024 and b'\n' not in self.buf:
            raise RpcError('frame_too_large')

    def message(self, deadline):
        while True:
            # Buffered bytes do not extend the request deadline.
            self.remaining(deadline)
            if b'\n' in self.buf:
                line, _, rest = self.buf.partition(b'\n')
                self.buf = bytearray(rest)
                if len(line) > 1024*1024:
                    raise RpcError('frame_too_large')
                try:
                    obj = json.loads(line)
                    if not isinstance(obj, dict):
                        raise ValueError()
                except (ValueError, UnicodeError):
                    raise RpcError('invalid_frame') from None
                self.remaining(deadline)
                return obj
            if len(self.buf) > 1024*1024:
                raise RpcError('frame_too_large')
            if not self.sel.select(self.remaining(deadline)):
                raise RpcError('timeout')
            self.remaining(deadline)
            self.read_chunk()

    def notification(self, msg, deadline=None):
        if 'method' in msg and 'id' in msg:
            if type(msg['id']) not in (int, str):
                raise RpcError('invalid_request_id')
            self.send({'id': msg['id'], 'error': {'code': -32601,
                      'message': 'Unsupported by read-only quota guard'}}, deadline)
        elif msg.get('method') in ('account/rateLimits/updated', 'account/updated'):
            self.generation += 1
            if self.on_update:
                self.on_update()  # Never retain raw params.
        elif 'id' in msg and 'method' not in msg:
            # There is only one outstanding request on this transport.
            raise RpcError('unexpected_response')

    def drain_ready(self, deadline):
        """Handle already-buffered/readable notifications before returning a read.

        A partial pending frame is unknown, so fail closed instead of publishing
        a potentially outdated response. Future arrivals cannot be reserved away.
        """
        while True:
            self.remaining(deadline)
            if b'\n' in self.buf:
                self.notification(self.message(deadline), deadline)
            elif self.sel.select(0):
                self.read_chunk()
            elif self.buf:
                raise RpcError('incomplete_pending_frame')
            else:
                self.remaining(deadline)
                return

    def call(self, method, params=None):
        if method not in ('initialize', 'account/rateLimits/read', 'turn/interrupt'):
            raise RpcError('method_not_allowed')
        self.seq += 1
        request_id = self.seq
        deadline = time.monotonic()+self.timeout
        self.send({'id': request_id, 'method': method, 'params': params or {}}, deadline)
        while True:
            msg = self.message(deadline)
            if 'id' in msg and 'method' not in msg:
                if type(msg['id']) is not int or msg['id'] != request_id:
                    raise RpcError('invalid_response_id')
                if 'error' in msg or not isinstance(msg.get('result'), dict):
                    raise RpcError('remote_error')
                result = msg['result']
                self.drain_ready(deadline)
                return result
            self.notification(msg, deadline)

    def wait(self, seconds):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            try:
                self.notification(self.message(deadline), deadline)
            except RpcError as e:
                if str(e) == 'timeout':
                    return
                raise

    def close(self):
        self.sel.close()
        # Only the child transport created by this client, never process groups.
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=2)
        for stream in (self.proc.stdin, self.proc.stdout):
            stream.close()
