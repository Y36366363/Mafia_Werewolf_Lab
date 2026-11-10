"""Channel ablations of v10 concentration scoring; no new signal or search.

All four variants keep v10's deterministic night tie-break, including when
signal weight is zero. Thus disabling a feature cannot change the tie rule.
"""
from dataclasses import dataclass
from . import strategies_v10 as v10


@dataclass(frozen=True)
class MafiaPolicyV11(v10.MafiaPolicyV10):
    signal_channels: str = "both"
    counter_mode: str = "concentration"
    counter_weight: float = 2.0

    def __post_init__(self):
        super().__post_init__()
        if self.signal_channels not in {"none", "vote", "kill", "both"}:
            raise ValueError("invalid signal channels")
        if self.counter_mode != "concentration" or self.counter_weight != 2.0:
            raise ValueError("v11 freezes the concentration feature at weight 2")


def _channel_policy(policy, channel):
    if not isinstance(policy, MafiaPolicyV11):
        return policy
    # Convert to parent rather than creating an invalid zero-weight V11 policy.
    values = {k: v for k, v in vars(policy).items() if k != "signal_channels"}
    if policy.signal_channels not in {channel, "both"}:
        values["counter_weight"] = 0.0
    return v10.MafiaPolicyV10(**values)


choose_inspection = v10.choose_inspection
message = v10.message


def choose_kill(obs, policy, rng):
    return v10.choose_kill(obs, _channel_policy(policy, "kill"), rng)


def vote(obs, policy, rng, candidates=None):
    return v10.vote(obs, _channel_policy(policy, "vote"), rng, candidates)
