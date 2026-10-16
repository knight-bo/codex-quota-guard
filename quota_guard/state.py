"""Private, atomic state; POSIX single-writer lock."""
import fcntl
import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path


class State:
    def __init__(self, directory, readonly=False):
        self.path = Path(directory).absolute()
        self.path.mkdir(mode=0o700, parents=True, exist_ok=True)
        s = self.path.lstat()
        if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077:
            raise ValueError('state_directory_must_be_private')
        fd = os.open(self.path/'lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        self.lock = os.fdopen(fd, 'w')
        try:
            if not readonly:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.data = self.read('state.json') or {'stops': {}}
            if not isinstance(self.data.get('stops'), dict):
                raise ValueError('invalid_state')
        except BaseException:
            self.lock.close()
            raise

    def read(self, name):
        try:
            fd = os.open(self.path/name, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return None
        with os.fdopen(fd) as f:
            text = f.read(1024*1024+1)
        if len(text) > 1024*1024:
            raise ValueError('state_too_large')
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError('invalid_state')
        return value

    def write(self, name, value):
        fd, tmp = tempfile.mkstemp(dir=self.path)
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(value, f, allow_nan=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path/name)
            d = os.open(self.path, os.O_RDONLY)
            try:
                os.fsync(d)
            finally:
                os.close(d)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def save(self, decision):
        self.data['decision'] = decision
        self.write('state.json', self.data)

    def request_stop(self):
        """Cooperative request bound to this exact monitor, never signal a PID."""
        try:
            fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            token = self.data.get('monitor_token')
            if not isinstance(token, str) or not token:
                return False
            self.write('stop.json', {'monitor_token': token})
            return True
        return False

    def stop_requested(self, token):
        request = self.read('stop.json')
        return request is not None and request.get('monitor_token') == token

    def close(self):
        self.lock.close()


class ManagedStop:
    """Explicit exact thread/turn binding; crash ambiguity never auto-retries."""
    def __init__(self, state, thread, turn, enabled=False):
        if not thread or not turn or max(len(thread), len(turn)) > 256:
            raise ValueError('invalid_binding')
        self.state, self.thread, self.turn, self.enabled = state, thread, turn, enabled
        self.key = hashlib.sha256(json.dumps([thread, turn]).encode()).hexdigest()

    def stop(self, rpc):
        if not self.enabled:
            return 'would_interrupt'
        prior = self.state.data['stops'].get(self.key)
        if prior:
            return prior
        # Durable intent before sending; a lost response is ambiguous, not success.
        self.state.data['stops'][self.key] = 'pending_unknown'
        self.state.write('state.json', self.state.data)
        self.state.write('checkpoint.json', {'binding_sha256': self.key,
                          'requested': True, 'contract_version': 1,
                          'checkpoint_status': 'unconfirmed'})
        try:
            rpc.call('turn/interrupt', {'threadId': self.thread, 'turnId': self.turn})
        except Exception:
            return 'pending_unknown'
        self.state.data['stops'][self.key] = 'interrupt_acknowledged'
        self.state.write('state.json', self.state.data)
        return 'interrupt_acknowledged'
