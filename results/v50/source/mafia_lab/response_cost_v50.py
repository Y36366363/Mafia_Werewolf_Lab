"""First-round public-ballot cost diagnostics for an announced countervote."""
from collections import Counter

from .adaptive_counter_v49 import AdaptiveCounterAPI


def loses_prefix_lead(obs, ordinary, counter):
    """Whether redirecting removes the old target from the current leaders."""
    if ordinary is None or ordinary == counter:
        return False
    prefix = {p:v for e in obs.public_events if e.day==1 and e.kind=='live_vote'
              for p,v in e.ballots if p!=obs.player}
    tally = Counter(v for v in prefix.values() if v is not None)
    before, after = tally.copy(), tally.copy()
    before[ordinary] += 1
    after[counter] += 1
    return before[ordinary] == max(before.values()) and after[ordinary] < max(after.values())


class ResponseCostAPI(AdaptiveCounterAPI):
    def __init__(self, cooperation, relay, q, pace, receiver):
        super().__init__(cooperation,relay,q,pace!='original',receiver,False)
        self.pace = pace
        self.counter_attempts = []

    def vote(self, obs, policy, rng, candidates=None):
        before = len(self.counter_ballots)
        target = super().vote(obs,policy,rng,candidates)
        if len(self.counter_ballots)==before:
            return target
        proposal = self.counter_ballots[-1]
        costly = loses_prefix_lead(obs,proposal['baseline'],target)
        blocked = self.pace=='protect_lead' and costly
        self.counter_attempts.append(dict(proposal,costly=costly,blocked=blocked))
        if blocked:
            self.counter_ballots.pop()
            return proposal['baseline']
        return target
