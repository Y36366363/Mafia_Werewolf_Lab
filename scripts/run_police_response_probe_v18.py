#!/usr/bin/env python3
import json,sys,shutil
from pathlib import Path
from hashlib import sha256
from statistics import mean
from dataclasses import asdict
from concurrent.futures import ProcessPoolExecutor
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from mafia_lab.police_response_experiment_v18 import build_spec,_metrics,_branches,_contrasts
from mafia_lab.simulation import opening,continue_game
from mafia_lab.experiments import fingerprint
from mafia_lab.statistics import win_summary
from mafia_lab import strategies_v18_probe as decisions

def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def evaluate(job):
    rules,g,m,start,n=job;raw={};samples=[]
    for i,seed in enumerate(range(start,start+n)):
        initial=opening(rules,g,m,seed,decisions)
        outcome=continue_game(initial,g,m,seed,trace=True,decision_api=decisions,public_ballots=True)
        metrics=_metrics(initial,outcome)
        police={p for p,r in enumerate(initial.roles) if r.value=='police'}
        fake=[e['payload'] for e in outcome.transcript if e['day']==1 and e['event']=='message'
              and e['payload']['context']=='day' and e['payload']['kind']=='report'
              and e['payload']['speaker'] not in police]
        denials=[e['payload'] for e in outcome.transcript if e['day']==1 and e['event']=='speech_extension'
                 and e['payload']['kind']=='accuse' and e['payload']['speaker'] in police
                 and fake and e['payload']['target']==fake[0]['speaker']]
        metrics['actual_denial']=int(bool(denials))
        metrics['self_denial']=int(bool(fake) and any(x['speaker']==fake[0]['target'] for x in denials))
        for k,v in metrics.items():raw.setdefault(k,[]).append(v)
        if i in {0,n//2,n-1}:samples.append({'index':i,'seed':seed,'trace_hash':sha256(repr(outcome.transcript).encode()).hexdigest()})
    return {'phase':'targeted_probe','good':g.name,'mafia':m.name,'n':n,'seed_start':start,
            'raw':raw,'means':{k:mean(v) for k,v in raw.items()},'win_summary':win_summary(raw['win']),
            'branches':_branches(raw),'samples':samples}

def main():
    output=ROOT/'results/v18_probe'
    if output.exists():raise ValueError('use new output')
    output.mkdir()
    config=json.loads((ROOT/'configs/police_response_v18.json').read_text())
    rules,good,mafia,cal=build_spec(config);mafia=[m for m in mafia if m.response=='early']
    assets=list((ROOT/'mafia_lab').glob('*.py'))+[ROOT/'configs/police_response_v18.json',ROOT/'docs/police_response_probe_protocol_v18.md',Path(__file__).resolve()]
    for source in assets:
        target=output/'source'/source.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    freeze={'source_sha256':fingerprint(),'seed_start':154000000,'n':1024,
            'good':[asdict(p) for p in good],'mafia':[asdict(p) for p in mafia],
            'assets':{str(p.relative_to(output)):sha256(p.read_bytes()).hexdigest() for p in (output/'source').rglob('*') if p.is_file()}}
    save(output/'freeze.json',freeze)
    with ProcessPoolExecutor(max_workers=4) as pool:
        cells=list(pool.map(evaluate,[(rules,g,m,154000000,1024) for g in good for m in mafia]))
    assert fingerprint()==freeze['source_sha256']
    save(output/'probe.json',{'cells':cells,'contrasts':_contrasts(cells,good,mafia),
        'scope':'Exploratory posthoc diagnostic; no policy selection, not original holdout.'})
    save(output/'manifest.json',{'games':sum(c['n'] for c in cells),'files':{n:sha256((output/n).read_bytes()).hexdigest() for n in ['freeze.json','probe.json']}})
    print(json.dumps({'games':sum(c['n'] for c in cells),'status':'complete'}))
if __name__=='__main__':main()
