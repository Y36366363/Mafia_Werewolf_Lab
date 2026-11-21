"""Conditional day-two comparison on observations of two returning claimants."""
from .corroborated_hit_v44 import common_hit
from .engine import Message, Role, speech_order
from .hit_candidates_v37 import explain
from .paired_source_routing_v40 import current_calls
from .policies import teammates
from .report_timing_v46 import ReportTimingAPI
from .source_evidence_pilot_v42 import AMBIGUOUS


def original_pair(obs):
    reports = {m.speaker: (m.target, m.verdict) for m in obs.messages
               if m.day == 1 and m.kind == 'report' and m.context == 'day'}
    if len(reports) == 2 and len(set(reports.values())) == 2 and set(reports) <= set(obs.alive):
        return tuple(sorted(reports))
    return ()


def first_day_record(obs, source):
    """Use only the completed first ballot; PK candidates can force a switch."""
    calls = [m.target for m in obs.messages if m.day == 1 and m.context == 'day'
             and m.speaker == source and m.kind == 'accuse']
    votes = next((dict(e.ballots) for e in obs.public_events if e.day == 1 and e.kind == 'vote'), {})
    return calls[-1] if calls else None, votes.get(source), source in votes


def consistency_flags(obs, source, rival, report, call):
    yesterday_call, yesterday_vote, voted = first_day_record(obs, source)
    flags = set()
    if yesterday_call is not None and voted and yesterday_call != yesterday_vote:
        flags.add('prior_call_ballot_mismatch')
    if (not report.verdict and voted and yesterday_call is not None
            and report.target == yesterday_call == yesterday_vote):
        flags.add('clear_of_prior_push')
    hits = {m.target for m in obs.messages if m.speaker == source and m.kind == 'report' and m.verdict}
    if report.verdict:
        hits.add(report.target)
    if call not in hits and call != rival:
        flags.add('call_without_own_hit_or_rival')
    return flags


def compare_sources(obs, info, pair):
    if (not pair or obs.role != Role.CIVILIAN or obs.day != 2 or info['known_bad']
            or info['reason'] not in AMBIGUOUS or common_hit(obs, info) is not None
            or set(info['proposal_sources']) != set(pair)):
        return None
    calls = current_calls(obs)
    if (any(calls.get(s) not in info['proposals'][str(s)] for s in pair)
            or calls[pair[0]] == calls[pair[1]]):
        return None
    reports = {m.speaker: m for m in obs.messages if m.day == 2 and m.context == 'day' and m.kind == 'report'}
    if not all(s in reports for s in pair):
        return None
    past_targets = {m.target for m in obs.messages if m.day < 2 and m.kind == 'report'}
    fresh = [s for s in pair if reports[s].target not in past_targets]
    first, second = pair
    flags = {s: consistency_flags(obs,s,rival,reports[s],calls[s]) for s,rival in ((first,second),(second,first))}
    preferred = next((s for s,rival in ((first,second),(second,first)) if flags[s] < flags[rival]), None)
    return dict(calls={s:calls[s] for s in pair}, fresh=fresh, preferred=preferred,
                flags={s:sorted(values) for s,values in flags.items()})


class ReturningSourcesAPI(ReportTimingAPI):
    def __init__(self, cooperation, relay, q, bluff, receiver):
        super().__init__(cooperation, relay, q, risk=True, bluff='inherited', timing=False)
        self.returning_bluff = bluff
        self.returning_receiver = receiver
        self.pair = ()
        self.night_adjustment = None
        self.bluff_plan = None
        self.comparisons = []

    def choose_kill(self, obs, policy, rng):
        original = super().choose_kill(obs,policy,rng)
        if obs.day != 1 or self.returning_bluff is None:
            return original
        pair = original_pair(obs)
        if not pair:
            return original
        allies = teammates(obs)
        allowed = [p for p in obs.alive if p not in pair and p not in allies]
        if not allowed:
            return original
        self.pair = pair
        victim = original if original in allowed else rng.choice(allowed)
        self.night_adjustment = dict(original=original, victim=victim)
        self.nights[-1]['target'] = victim
        source = next((p for p in pair if p in allies), None)
        if source is not None:
            self.prepare_bluff(obs,source,victim,rng)
        return victim

    def message(self, obs, policy, rng, context='day', override=None):
        if obs.day != 2 or not self.pair or context != 'day':
            return super().message(obs,policy,rng,context,override)
        if obs.role == Role.POLICE:
            if obs.player in self.pair:
                check = obs.investigations[-1]
                assert check.day == 2
                return Message(obs.player,'report',check.target,check.is_mafia,context,2)
            return Message(obs.player,'civilian',context=context,day=2)
        if obs.role != Role.MAFIA or obs.player not in self.pair:
            return super().message(obs,policy,rng,context,override)
        plan = self.bluff_plan
        assert plan and plan['source'] == obs.player
        return Message(obs.player,'report',plan['target'],plan['hit'],context,2)

    def prepare_bluff(self, obs, source, victim, rng):
        # This is planned on night two, after deciding the mafia's own kill
        # and before seeing the elimination, last words or any day-two report.
        rival = next(p for p in self.pair if p != source)
        allies = teammates(obs)
        pool = [p for p in obs.alive if p not in allies and p != victim]
        old_call, _, _ = first_day_record(obs,source)
        default_call = old_call if old_call in pool else pool[0]
        false_hit = rng.random() < 0.5
        reportable = pool if false_hit else [p for p in pool if p not in {rival, default_call}]
        old_targets = {m.target for m in obs.messages if m.kind == 'report'}
        candidate_order = sorted(p for p in reportable if p not in old_targets) or sorted(reportable)
        rng.shuffle(candidate_order)
        def proposal(p):
            call = default_call if self.returning_bluff == 'unlinked' else p if false_hit else rival
            return Message(source,'report',p,false_hit,'day',2), call
        plans = [proposal(p) for p in candidate_order]
        report, call = (min(plans,key=lambda plan:len(consistency_flags(obs,source,rival,*plan)))
                        if self.returning_bluff == 'prepared' else plans[0])
        self.bluff_plan = dict(source=source,target=report.target,hit=report.verdict,call=call)

    def after_speech(self, obs, policy, rng):
        if obs.role == Role.MAFIA and obs.day == 2 and self.bluff_plan and obs.player == self.bluff_plan['source']:
            return Message(obs.player,'accuse',self.bluff_plan['call'],context='day',day=2)
        return super().after_speech(obs,policy,rng)

    def vote(self, obs, policy, rng, candidates=None):
        if obs.role == Role.MAFIA and obs.day == 2 and self.pair:
            source = next((p for p in self.pair if p in teammates(obs)), None)
            if source is not None:
                call = current_calls(obs).get(source)
                if call is not None and call != obs.player and call in (obs.alive if candidates is None else candidates):
                    return call
        base = super().vote(obs,policy,rng,candidates)
        if obs.role != Role.CIVILIAN or obs.day != 2 or not self.pair or candidates is not None:
            return base
        info = explain(obs,policy,retain=True)
        row = compare_sources(obs,info,self.pair)
        if row is None:
            return base
        novel = row['fresh'][0] if len(row['fresh']) == 1 else None
        source = row['preferred'] if self.returning_receiver == 'consistency' and row['preferred'] is not None else novel
        target = row['calls'][source] if source is not None else base
        assert target in info['legal'] and target not in info['known_good']
        self.pilot_ballots[-1]['target'] = target
        self.comparisons.append(dict(player=obs.player,baseline=base,novel=novel,source=source,target=target,**row))
        return target
