"""Task-scoped, durable confirmation events; no user messaging or task control."""
from dataclasses import dataclass
import hashlib
import json
import uuid

from .core import number


@dataclass(frozen=True)
class ConfirmationPolicy:
    target: float
    warn_margin: float = 2
    confirm_margin: float = 1

    def __post_init__(self):
        values = (self.target, self.warn_margin, self.confirm_margin)
        if (not all(number(value) for value in values) or
                not 0 <= self.target <= 100 or
                not 0 <= self.confirm_margin <= self.warn_margin <= 100):
            raise ValueError('invalid_confirmation_policy')


class ConfirmationEvents:
    def __init__(self, state, policy, task_key, new_cycle=False):
        if not isinstance(task_key, str) or not task_key.strip() or len(task_key) > 1024:
            raise ValueError('explicit_task_binding_required')
        self.state, self.policy = state, policy
        self.binding = hashlib.sha256(task_key.encode()).hexdigest()
        config = dict(vars(policy), task_binding=self.binding)
        ledger = state.data.get('confirmation_tracker')
        previous = ledger.get('config', {}) if isinstance(ledger, dict) else {}
        same_target = (isinstance(previous, dict) and previous.get('target') == policy.target and
                       previous.get('task_binding') == self.binding)
        if new_cycle or not same_target:
            ledger = {'schema_version': 1, 'config': config, 'cycle': uuid.uuid4().hex,
                      'sequence': 0, 'warned': False, 'asked': False, 'reached': False,
                      'last_remaining': None, 'last_windows': None}
            state.data['confirmation_tracker'] = ledger
        if (ledger.get('schema_version') != 1 or not isinstance(ledger.get('cycle'), str) or
                type(ledger.get('sequence')) is not int or ledger['sequence'] < 0 or
                any(type(ledger.get(key)) is not bool for key in ('warned', 'asked', 'reached'))):
            raise ValueError('invalid_confirmation_ledger')
        ledger['config'] = config  # Margin changes do not clear a reached target.
        self.ledger = ledger

    def evaluate(self, decision):
        """Return versioned events. Persist before emitting; delivery is unconfirmed."""
        result = dict(decision)
        events = []
        ledger, policy = self.ledger, self.policy
        remaining = decision.get('remaining_percent')
        valid = decision.get('data_valid') is True and decision.get('stale') is False and number(remaining) and 0 <= remaining <= 100
        stage = 'unavailable'

        def event(kind):
            ledger['sequence'] += 1
            events.append({'schema_version': 1,
                'id': ledger['cycle']+':'+str(ledger['sequence']), 'type': kind,
                'task_binding': self.binding, 'remaining_percent': remaining,
                'target_percent': policy.target, 'observed_at': decision.get('observed_at'),
                'target_already_reached': remaining <= policy.target,
                'requires_user_confirmation': kind == 'confirmation_required',
                'requires_task_authorization': kind == 'target_reached',
                'user_notified': False, 'pause_authorized': False, 'task_paused': False})

        if valid:
            windows = {name: window.get('resets_at') for name, window in decision.get('windows', {}).items()}
            if ledger['last_windows'] is not None and (windows != ledger['last_windows'] or
                    remaining > ledger['last_remaining']):
                event('quota_changed')  # Never clears a reached target or resumes a task.
            ledger['last_windows'], ledger['last_remaining'] = windows, remaining
            warn_at = min(100, policy.target+policy.warn_margin)
            confirm_at = min(100, policy.target+policy.confirm_margin)
            stage = ('target_reached' if remaining <= policy.target else
                     'confirmation_required' if remaining <= confirm_at else
                     'warning' if remaining <= warn_at else 'observing')
            if remaining <= confirm_at and not ledger['asked']:
                ledger['asked'] = True
                event('confirmation_required')
            elif remaining <= warn_at and not ledger['warned'] and not ledger['asked']:
                ledger['warned'] = True
                event('warning')
            if remaining <= policy.target and not ledger['reached']:
                ledger['reached'] = True
                event('target_reached')
        result['confirmation'] = {'schema_version': 1, 'task_binding': self.binding,
            'target_percent': policy.target, 'warn_margin': policy.warn_margin,
            'confirm_margin': policy.confirm_margin, 'stage': stage,
            'target_reached_latched': ledger['reached'],
            'quota_policy_allow_new_work': decision.get('allow_new_work', False),
            'quota_policy_reason': decision.get('reason', 'unavailable'),
            'pause_authorized': False, 'task_paused': False}
        result['events'] = events
        if not valid:
            result['allow_new_work'] = False
            result['data_valid'] = False
            if decision.get('allow_new_work'):
                result['reason'] = 'unavailable'
        if ledger['reached']:
            result['allow_new_work'] = False
            if valid:
                result['reason'] = 'confirmation_target_reached'
        return result
