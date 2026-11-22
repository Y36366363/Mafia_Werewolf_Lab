"""Isolate public target novelty and prior speech-backed countervotes."""

from .returning_sources_v47 import ReturningSourcesAPI, first_day_record


def corroborated_challenges(obs, pair):
    """Find first-day hit targets who subsequently named and voted for their source."""
    witnesses = {source: [] for source in pair}
    for index, report in enumerate(obs.messages):
        if (report.day != 1 or report.context != 'day' or report.kind != 'report'
                or report.verdict is not True or report.speaker not in pair
                or report.target in pair):
            continue
        target, source = report.target, report.speaker
        _, vote, voted = first_day_record(obs, target)
        if not voted or vote != source:
            continue
        if any(m.day == 1 and m.context == 'day' and m.kind == 'nominate'
               and m.speaker == target and m.target == source
               for m in obs.messages[index+1:]):
            if target not in witnesses[source]:
                witnesses[source].append(target)
    return witnesses


class NoveltyAblationAPI(ReturningSourcesAPI):
    def __init__(self, cooperation, relay, q, bluff, receiver):
        super().__init__(cooperation, relay, q, bluff, 'novelty')
        self.novelty_receiver = receiver

    def vote(self, obs, policy, rng, candidates=None):
        before = len(self.comparisons)
        legacy = super().vote(obs, policy, rng, candidates)
        if len(self.comparisons) == before:
            return legacy
        row = self.comparisons[-1]
        challenges = corroborated_challenges(obs, self.pair)
        challenged = [source for source, targets in challenges.items() if targets]
        supported = (next(source for source in self.pair if source != challenged[0])
                     if len(challenged) == 1 else None)
        row.update(challenges=challenges, supported=supported, novelty_target=legacy)
        if self.novelty_receiver == 'novelty':
            return legacy
        source = supported if self.novelty_receiver == 'challenge' else None
        target = row['calls'][source] if source is not None else row['baseline']
        row.update(source=source,target=target)
        self.pilot_ballots[-1]['target'] = target
        return target
