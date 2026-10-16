"""Conservative quota policy. Never interprets context tokens as quota."""
import math
import time
from dataclasses import dataclass


def number(x):
    return type(x) in (int, float) and math.isfinite(x)


@dataclass(frozen=True)
class Policy:
    bucket: str
    threshold: float = 10
    buffer: float = 2
    max_age: float = 90

    def __post_init__(self):
        if (not self.bucket or not all(number(v) for v in
                (self.threshold, self.buffer, self.max_age)) or
                min(self.threshold, self.buffer) < 0 or
                self.threshold + self.buffer > 100 or self.max_age <= 0):
            raise ValueError('invalid_policy')


class Guard:
    def __init__(self, policy):
        self.policy = policy
        self.windows = {}
        self.received = None
        self.problem = 'missing'

    def invalidate(self, reason='unavailable'):
        self.problem = reason

    def ingest(self, payload, now=None):
        """Only authoritative reads may authorize work; notifications invalidate."""
        now = time.time() if now is None else now
        try:
            if 'rateLimitsByLimitId' in payload:
                bucket = payload['rateLimitsByLimitId'][self.policy.bucket]
            else:
                bucket = payload['rateLimits']
            if bucket.get('limitId') != self.policy.bucket:
                raise ValueError()
            if bucket.get('rateLimitReachedType') is not None:
                self.invalidate('limit_reached')
                return
            windows = {}
            for name in ('primary', 'secondary'):
                if name not in bucket:  # absent is not explicit null
                    raise ValueError()
                w = bucket[name]
                if w is None:
                    continue
                used, duration, reset = (w[k] for k in
                    ('usedPercent', 'windowDurationMins', 'resetsAt'))
                if not all(number(v) for v in (used, duration, reset)):
                    raise ValueError()
                if not 0 <= used <= 100 or duration <= 0 or reset <= now:
                    raise ValueError()
                old = self.windows.get(name)
                if old and (reset < old['reset'] or
                            (reset == old['reset'] and used < old['used'])):
                    self.invalidate('out_of_order')
                    return
                windows[name] = {'used': used, 'reset': reset, 'duration': duration}
            if not windows or any(k not in windows for k in self.windows):
                raise ValueError()
            self.windows, self.received, self.problem = windows, now, None
        except (KeyError, TypeError, ValueError, AttributeError):
            self.invalidate('invalid_or_missing')

    def decision(self, now=None):
        now = time.time() if now is None else now
        reason = self.problem
        if reason is None and (now < self.received or now-self.received >= self.policy.max_age):
            reason = 'stale'
        if reason is None and any(w['reset'] <= now for w in self.windows.values()):
            reason = 'reset_requires_read'
        remaining = min((100-w['used'] for w in self.windows.values()), default=None)
        if reason is None and remaining <= self.policy.threshold+self.policy.buffer:
            reason = 'low_quota'
        return {'allow_new_work': reason is None, 'reason': reason or 'healthy',
                'remaining_percent': remaining, 'observed_at': self.received,
                'data_valid': reason in (None, 'low_quota'),
                'stale': self.received is not None and (now < self.received or now-self.received >= self.policy.max_age or any(w['reset'] <= now for w in self.windows.values())),
                'reported_at': now, 'bucket': self.policy.bucket,
                'reserve_percent': self.policy.threshold, 'buffer_percent': self.policy.buffer,
                'windows': {name: {'remaining_percent': 100-w['used'],
                    'window_duration_mins': w['duration'], 'resets_at': w['reset']}
                    for name, w in self.windows.items()},
                'valid_until': min([self.received+self.policy.max_age] +
                    [w['reset'] for w in self.windows.values()]) if self.received is not None else None}
