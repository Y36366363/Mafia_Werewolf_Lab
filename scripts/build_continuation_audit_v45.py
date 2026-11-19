"""Recompute v45 case findings and v44 process counts from hashed raw records."""
from collections import Counter
import gzip
import json
from pathlib import Path

from run_corroborated_hit_v44 import ROOT, digest, load_spec, save_json


def main():
    out = ROOT/'results/v45'
    manifest = json.loads((out/'manifest.json').read_text())
    assert all(digest(out/name) == h for name,h in manifest['files'].items())
    freeze = json.loads((out/'freeze.json').read_text())
    assert all(digest(ROOT/rel) == digest(out/'source'/rel) == h
               for rel,h in freeze['assets'].items())
    parent_cfg = json.loads((ROOT/freeze['config']['parent_freeze']).read_text())['config']
    _, policy, _ = load_spec(parent_cfg)
    # Shadow voters keep actual sequential-ballot prefixes. That is valid for
    # this receiver because both ballot-history mechanisms are frozen off.
    assert not policy.history and not policy.vote_history
    parent_path = ROOT/freeze['config']['parent_pairs']
    assert digest(parent_path) == freeze['parent_pairs_sha256']
    old = json.load(gzip.open(parent_path, 'rt'))
    raw = json.load(gzip.open(out/'cases.json.gz', 'rt'))
    rows = []
    for seed, arms in raw.items():
        before, after = arms['copy_shared'], arms['copy_both']
        roles = after['roles_evaluation_only']
        b2,b3 = [next(d for d in before['days'] if d['day'] == n) for n in (2,3)]
        a2,a3 = [next(d for d in after['days'] if d['day'] == n) for n in (2,3)]
        assert before['win'] and not after['win']
        assert roles[b2['day_exile']] == roles[a2['day_exile']] == 'mafia'
        assert roles[b3['day_exile']] == 'mafia' and roles[a3['day_exile']] == 'civilian'
        assert b3['night_victim'] == a3['night_victim']
        assert not after['copy_events']
        assert [x['day'] for x in after['successions']] == [3]
        assert all(v['target'] in v['info']['known_bad'] for v in after['votes']
                   if v['observation']['role'] == 'police' and v['info']['known_bad'])
        police = [v for v in after['votes'] if v['observation']['day'] == 3
                  and v['observation']['role'] == 'police' and v['candidates'] is None]
        civilians = [v for v in after['votes'] if v['observation']['day'] == 3
                     and v['observation']['role'] == 'civilian' and v['candidates'] is None]
        assert len(police) == 2 and len({v['target'] for v in police}) == 1
        mafia_alive = {p for p in police[0]['observation']['alive'] if roles[p] == 'mafia'}
        assert all(mafia_alive <= set(v['info']['known_bad']) for v in police)
        ordinary = [v for v in civilians if not v['info']['known_bad']]
        assert len(ordinary) == 6
        assert all(v['info']['reason'] == 'compatible_sources_protocol'
                   and not v['info']['active_edges'] and v['agreement'] is None
                   and v['common_hit'] is None and v['target'] == a3['day_exile'] for v in ordinary)
        refuted = [v for v in civilians if v['info']['known_bad']]
        assert len(refuted) == 1 and roles[refuted[0]['target']] == 'mafia'
        shadow, = after['shadow']
        assert not shadow['new']['verdict']
        callers = [m for m in after['messages'] if m['output'] == shadow['old']]
        assert len(callers) == 1
        assert callers[0]['observation']['investigations'][-1] == shadow['latest']
        assert shadow['old']['target'] in [c['target'] for c in callers[0]['observation']['investigations'] if c['day'] < 3 and c['is_mafia']]
        changed = sum(v['before'] != v['after'] for v in shadow['ballots'])
        call = next(c for c in after['calls'] if c['day'] == 2)
        assert call['predicted'][str(call['target'])] - call['predicted'][str(call['original'])] == 1
        first = next((x,y) for x,y in zip(before['events'],after['events']) if x != y)
        assert first[0]['day'] == first[1]['day'] == 2
        rows.append(dict(seed=int(seed), original_day2=b2['day_exile'], coordinated_day2=a2['day_exile'],
            day3_night=a3['night_victim'], original_day3=b3['day_exile'], coordinated_day3=a3['day_exile'],
            day3_police_target=police[0]['target'], next_mafia=after['successions'][0]['speaker'],
            day3_private_mafia=sorted(mafia_alive), day3_first_difference=first,
            omitted_clear=shadow['new']['target'], shadow_changed_ballots=changed,
            shadow_leaders=shadow['after_leaders'],
            shadow_unique_mafia=len(shadow['after_leaders']) == 1 and roles[shadow['after_leaders'][0]] == 'mafia'))
    assert len(rows) == 6
    assert sum(r['shadow_changed_ballots'] for r in rows) == 6
    assert sum(r['shadow_unique_mafia'] for r in rows) == 1
    joint, process, exile_delta = Counter(), Counter(), Counter()
    for a,b in zip(old['copy_shared'],old['copy_both'], strict=True):
        joint[f"{a['win']}_to_{b['win']}"] += 1
        if not a['win'] and not b['win']:
            process['both_loss'] += 1
            process['trace_changed'] += a['trace'] != b['trace']
            process['exile_sequence_changed'] += a['exile'] != b['exile']
            if a['trace'] != b['trace']:
                ma = sum(r == 'mafia' for r in a['exile_roles'].values())
                mb = sum(r == 'mafia' for r in b['exile_roles'].values())
                exile_delta[str(mb-ma)] += 1
    summary = dict(cases=rows, parent_pair_joint=joint, parent_same_loss_process=process,
                   parent_changed_same_loss_mafia_exile_delta=exile_delta,
                   full_trace_matches=24, fresh_performance_games=0,
                   conclusions=dict(same_mechanism_cases=6, live_hit_superseded_latest_clear=6,
                       day3_real_police_aligned=6, all_remaining_mafia_privately_known=6,
                       actual_death_report_copies=0, shadow_unique_mafia_leader=1))
    save_json(out/'summary.json', summary)
    lines = ['# v45 六局逐局阅读版', '',
             '座位均从1开始；P为警察、M为匪、C为平民。身份是赛后裁判标注，未交给平民。', '',
             '两组都保留共同查杀优先；“原组”不按预测票数改归，“协调组”会这样改归。第三天的真假身份只用于解释结果。', '']
    for row in rows:
        arms = raw[str(row['seed'])]
        lines += [f"## 种子 {row['seed']}", '',
                  '| 日程 | 原组：夜刀／放逐／日末P-M-C | 协调组：夜刀／放逐／日末P-M-C |',
                  '|---|---|---|']
        days = {arm:{d['day']:d for d in arms[arm]['days']} for arm in ('copy_shared','copy_both')}
        def cell(day):
            if day is None: return '已结束'
            end = day['end']
            exile = '无' if day['day_exile'] is None else str(day['day_exile']+1)
            return f"{day['night_victim']+1}／{exile}／{end['police']}-{end['mafia']}-{end['civilian']}"
        for day in sorted(set(days['copy_shared']) | set(days['copy_both'])):
            lines.append(f"| {day} | {cell(days['copy_shared'].get(day))} | {cell(days['copy_both'].get(day))} |")
        for arm,label in [('copy_shared','原组'),('copy_both','协调组')]:
            r = arms[arm]; day = days[arm][3]
            reports = '；'.join(f"{m['speaker']+1}号{'遗言' if m['context']=='last_words' else '发言'}报{m['target']+1}号{'匪' if m['verdict'] else '好人'}" for m in day['reports'])
            calls = '；'.join(f"{m['speaker']+1}→{m['target']+1}" for m in day['calls'])
            tally = '，'.join(f"{int(t)+1}号{n}票" for t,n in day['tally'].items())
            lines += ['', f'**{label}第三天：** {reports}。正式归票：{calls}。票数：{tally}。']
        lines += ['', f"协调组两名警察都知道存活的 {', '.join(str(x+1) for x in row['day3_private_mafia'])} 号是匪，均投 {row['day3_police_target']+1} 号，没有警队分票。被假查杀的平民投接续匪，其余六名平民按候选的位置排序投了平民。",
                  '', f"当晚还验到 {row['omitted_clear']+1} 号好人，但公开报告重复旧查杀。只把报告换成新金水、其余归票不动的影子计算，改变 {row['shadow_changed_ballots']} 张首轮票；新的最高票为 {', '.join(str(x+1) for x in row['shadow_leaders'])} 号。该计算未运行后续对局。", '']
    (ROOT/'docs/continuation_audit_cases_v45.md').write_text('\n'.join(lines).rstrip()+'\n')
    save_json(ROOT/'results/v45_analysis_manifest.json', dict(
        builder_sha256=digest(Path(__file__).resolve()),
        inputs={str((out/name).relative_to(ROOT)):digest(out/name) for name in ('manifest.json','cases.json.gz','freeze.json')},
        outputs={str(p.relative_to(ROOT)):digest(p) for p in (out/'summary.json', ROOT/'docs/continuation_audit_cases_v45.md')}))
    print(json.dumps(dict(joint=joint, process=process, findings=summary['conclusions']), indent=2))


if __name__ == '__main__':
    main()
