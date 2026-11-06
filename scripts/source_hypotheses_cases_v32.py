"""Two deterministic, post-hoc explanatory cases; no new acceptance seeds."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.source_hypotheses_v32 import ResponseAPI
from mafia_lab.unresolved_conflict_experiment_v31 import build_spec
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.restatement_experiment_v23 import save


class CaseAPI(ResponseAPI):
    def __init__(self, restrained):super().__init__(restrained);self.nights=[]
    def choose_kill(self, obs, policy, rng):
        target=super().__getattr__("choose_kill")(obs,policy,rng);self.nights.append((obs.day+1,target));return target


def main():
 f=json.loads((ROOT/'results/v32/freeze.json').read_text());data=json.loads((ROOT/'results/v32/holdout.json').read_text())
 r,gs,ms=build_spec(f['base_config']);g=gs[-1];M={m.name:m for m in ms};D={(c['response'],c['mafia']):c['rows'] for c in data['cells']}
 selections=[('late_old','terminal_gain',lambda a,b:a['win']==0 and b['win']==1),
             ('decoy_old','first_day_mafia_loss_same_terminal',lambda a,b:a['day1_mafia_exile']==1 and b['day1_mafia_exile']==0 and a['win']==b['win'])]
 result=[];lines=['# v32 两个过程例子','', '从验收表按种子升序选择每类第一个符合条件的局。事后解释，不是新增独立验证；角色标签只供读者复盘，不是平民信息。所有座位以下从1开始。','']
 for mn,kind,predicate in selections:
  chosen=next(((a,b) for a,b in zip(D['inherited',mn],D['restrained',mn]) if a['dead_clear'] and predicate(a,b)),None)
  if chosen is None:continue
  seed=chosen[0]['seed'];lines += [f'## {mn} / {kind}，seed={seed}','']
  for resp,row in zip(('inherited','restrained'),chosen):
   api=CaseAPI(resp=='restrained');s=opening(r,g,M[mn],seed,api);o=continue_game(s,g,M[mn],seed,trace=True,decision_api=api,public_ballots=True)
   assert hash_events(o.transcript)==row['trace_hash']
   result.append(dict(seed=seed,mafia=mn,response=resp,roles_evaluation_only=[x.value for x in s.roles],transcript=o.transcript,nights=api.nights))
   roles=lambda role:','.join(str(i+1) for i,x in enumerate(s.roles) if x.value==role)
   lines += [f'**{resp}**：警察{roles("police")}；匪徒{roles("mafia")}。最终'+('好人胜。' if o.good_win else '匪胜。'),'']
   for e in o.transcript:
    p=e['payload'];day=e['day'];ev=e['event']
    if ev in ('night_death','day_death'):
     seat=p['victim'];lines.append(f'- 第{day}日'+('夜刀' if ev=='night_death' else '放逐')+f'：{seat+1}号（裁判身份{s.roles[seat].value}）。')
    elif day==1 and ev in ('message','speech_extension','last_words_extension','final_call') and p['kind'] in ('report','shortlist','accuse','relay','delegate'):
     target=p['target'];tar='—' if target is None else str(target+1)
     label={'report':'报查杀' if p['verdict'] else '报金水','shortlist':'给内推','accuse':'正式归票','relay':'接力归票','delegate':'授权'}[p['kind']]
     extra=(('；授权来源' if p['kind']=='relay' else '；名单')+','.join(str(x+1) for x in p['targets'])) if p['targets'] else ''
     lines.append(f'- {p["speaker"]+1}号（{p["context"]}）{label}{tar}{extra}。')
    elif day==1 and ev in ('votes','pk_votes'):
     from collections import Counter
     counts=Counter(p.values());lines.append('- '+('首轮票' if ev=='votes' else 'PK票')+'：'+ '；'.join(('弃票' if k is None else str(int(k)+1)+'号')+f'{v}票' for k,v in sorted(counts.items(),key=lambda x:(x[0] is None,x[0] or 0)))+'。')
   recorded={e['day'] for e in o.transcript if e['event']=='night_death'}
   for day,seat in api.nights:
    if day not in recorded:lines.append(f'- 第{day}日致终局夜刀：{seat+1}号（裁判身份{s.roles[seat].value}）；夜间已终局，未进入白天。')
   lines.append('')
 # Complete legal speech prefixes for the same-observation counterexample.
 from dataclasses import asdict
 from mafia_lab.engine import from_roles,resolve_night,observe,add_message,Message,Role,speech_order
 from mafia_lab.source_hypotheses_v32 import role_support
 initial=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,r),0,8)
 initial=add_message(initial,Message(0,'report',8,False,'last_words',1))
 for actor in speech_order(initial):
  initial=add_message(initial,Message(actor,'report',8,False,'day',1) if actor==4 else Message(actor,'pass',context='day',day=1))
  if actor==4:break
 view=observe(initial,15);w=role_support(view,0,4)['witnesses'];worlds=[]
 for key in ('P/M','M/P'):
  state=resolve_night(from_roles(w[key],r),0,8)
  for msg in view.messages:
   state=add_message(state,msg)
   if msg.kind=='report' and state.roles[msg.speaker]==Role.POLICE:
    assert state.investigations[0].target==msg.target and state.investigations[0].is_mafia==msg.verdict
  assert observe(state,15)==view
  worlds.append(dict(source_roles=key,roles=w[key],observation=asdict(observe(state,15))))
 save(ROOT/'results/v32_same_history_witness.json',dict(worlds=worlds,scope='Full legal ordinary-turn prefix including passes; not claimed equally likely under frozen policies.'))
 save(ROOT/'results/v32_cases.json',dict(selection='first qualifying seed per pre-named descriptive type; selected after holdout',cases=result))
 (ROOT/'docs/source_hypotheses_cases_v32.md').write_text('\n'.join(lines))
 print('case replays',len(result))

if __name__=='__main__':main()
