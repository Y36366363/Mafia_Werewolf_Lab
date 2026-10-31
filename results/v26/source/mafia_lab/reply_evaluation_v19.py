"""Predeclared paired evaluation, no strategy training or equilibrium claim."""
import json, shutil, time
from pathlib import Path
from hashlib import sha256
from statistics import mean
from dataclasses import asdict
from concurrent.futures import ProcessPoolExecutor
from .engine import Rules, Role, speech_order
from .simulation import opening, continue_game
from .statistics import paired_summary, win_summary
from .experiments import fingerprint
from . import strategies_v19 as d

BRANCHES=('all','eligible','civilian_target','police_target','dead_police','no_opportunity')
PAIRS=(('clear_guard','old_keep','guard_keep'),('reply','guard_keep','guard_answer'),
       ('selective','guard_answer','guard_selective'),('survival','guard_selective','guard_bait'),
       ('civilian_denial','answer_no_denial','guard_answer'))

def save(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def build_spec(c):
    rules=Rules(**c['rules'])
    common=dict(reveal='silent',trust='none',dead_police_message='truth',dead_claim_response='trust',
        live_counter='hidden',inspect_position='gap',dead_clear_plan='truth',leadership='nominate',
        position_model='posterior',prior_model='equal',shortlist_rule='list2',flow='timed',source_credit=True,history=False)
    good=tuple(d.GoodPolicyV19(**common,**r) for r in c['good'])
    mafia=tuple(d.MafiaPolicyV19(bluff='none',kill='claims',opening_mode='ordinary',dead_mafia_message='silent',**r) for r in c['mafia'])
    a,b=c['blocks'];assert a['seed_start']+a['n']<=b['seed_start']
    assert (rules.police,rules.mafia,rules.civilians)==(4,4,8)
    return rules,good,mafia

def metrics(s,o):
    police={p for p,r in enumerate(s.roles) if r==Role.POLICE}
    mafia={p for p,r in enumerate(s.roles) if r==Role.MAFIA}
    events=[e for e in o.transcript if e['day']==1]
    ordinary=[e['payload'] for e in events if e['event']=='message' and e['payload']['context']=='day']
    fakes=[m for m in ordinary if m['speaker'] in mafia and m['kind']=='report']
    fake=fakes[0] if fakes else None
    order=list(speech_order(s));op=bool(fake) and any(p in police for p in order[order.index(fake['speaker'])+1:])
    firstdead=s.roles[s.deaths[0].player]==Role.POLICE
    eligible=not firstdead and op
    denials=[e['payload'] for e in events if e['event']=='speech_extension' and e['payload']['kind']=='accuse'
             and e['payload']['speaker'] in police and fake and e['payload']['target']==fake['speaker']]
    exiles=[e['payload']['victim'] for e in events if e['event']=='day_death']
    exile=exiles[0] if exiles else None
    night2=[e for e in o.transcript if e['day']==2 and e['event']=='night_death']
    return dict(win=int(o.good_win),eligible=int(eligible),civilian_target=int(eligible and s.roles[fake['target']]==Role.CIVILIAN),
        police_target=int(eligible and s.roles[fake['target']]==Role.POLICE),dead_police=int(firstdead and op),
        no_opportunity=int(bool(fake) and not op),opportunity=int(op),false_claim=int(bool(fake)),
        first_dead=int(s.deaths[0].player),first_check=int(s.investigations[0].target),first_check_mafia=int(s.investigations[0].is_mafia),
        fake_speaker=fake['speaker'] if fake else -1,fake_target=fake['target'] if fake else -1,
        reply=int(bool(denials)),police_claims=len({m['speaker'] for m in ordinary if m['speaker'] in police and m['kind'] in {'report','police'}}),
        day1_fake_exile=int(bool(fake) and exile==fake['speaker']),day1_mafia_exile=int(exile in mafia),
        day1_police_exile=int(exile in police),day1_no_exile=int(exile is None),
        day1_shortlist=int(any(e['event']=='speech_extension' and e['payload']['kind']=='shortlist' for e in events)),
        day1_pk=int(any(e['event']=='pk_votes' for e in events)))

def evaluate(job):
    phase,rules,g,m,start,n=job;raw={};samples=[]
    for i,seed in enumerate(range(start,start+n)):
        initial=opening(rules,g,m,seed,d)
        outcome=continue_game(initial,g,m,seed,trace=True,decision_api=d,public_ballots=True)
        for k,v in metrics(initial,outcome).items():raw.setdefault(k,[]).append(v)
        if i in {0,n//2,n-1}:samples.append(dict(index=i,seed=seed,trace_hash=sha256(repr(outcome.transcript).encode()).hexdigest()))
    return dict(phase=phase,good=g.name,mafia=m.name,n=n,seed_start=start,raw=raw,
                means={k:mean(v) for k,v in raw.items()},samples=samples,
                branches={b:win_summary([v for i,v in enumerate(raw['win']) if b=='all' or raw[b][i]]) for b in BRANCHES})

def contrasts(cells):
    lookup={(c['good'],c['mafia']):c for c in cells};out=[]
    for name,a,b in PAIRS:
        for m in sorted({c['mafia'] for c in cells}):
            x,y=lookup[a,m],lookup[b,m]
            for k in ('first_dead','first_check','first_check_mafia','fake_speaker','fake_target','opportunity'):
                assert x['raw'][k]==y['raw'][k],(name,m,k)
            for branch in BRANCHES:
                mask=[True]*x['n'] if branch=='all' else [bool(v) for v in x['raw'][branch]]
                assert branch=='all' or x['raw'][branch]==y['raw'][branch]
                row=dict(name=name,control=a,treatment=b,mafia=m,branch=branch)
                for metric in ('win','day1_mafia_exile','day1_fake_exile','day1_police_exile','police_claims','reply'):
                    row[metric]=paired_summary([v for v,keep in zip(x['raw'][metric],mask) if keep],
                                               [v for v,keep in zip(y['raw'][metric],mask) if keep])
                out.append(row)
    return out

def run(config,output,workers=4):
    root=Path(__file__).resolve().parents[1];output=Path(output)
    if output.exists():raise ValueError('output already exists')
    output.mkdir(parents=True);rules,good,mafia=build_spec(config)
    assets=list((root/'mafia_lab').glob('*.py'))+list((root/'scripts').glob('*v19.py'))+list((root/'tests').glob('*v19.py'))+[root/'configs/reply_v19.json',root/'docs/reply_protocol_v19.md']
    for src in assets:
        dst=output/'source'/src.relative_to(root);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    freeze=dict(config=config,good=[asdict(p) for p in good],mafia=[asdict(p) for p in mafia],source_sha256=fingerprint(),
                assets={str(p.relative_to(output)):sha256(p.read_bytes()).hexdigest() for p in (output/'source').rglob('*') if p.is_file()})
    save(output/'freeze.json',freeze);started=time.monotonic();total=0
    for block in config['blocks']:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            cells=list(pool.map(evaluate,[(block['name'],rules,g,m,block['seed_start'],block['n']) for g in good for m in mafia]))
        save(output/(block['name']+'.json'),dict(cells=cells,contrasts=contrasts(cells)))
        total+=sum(c['n'] for c in cells)
        assert fingerprint()==freeze['source_sha256']
        print(block['name']+' completed',flush=True)
    files=['freeze.json']+[b['name']+'.json' for b in config['blocks']]
    manifest=dict(games=total,elapsed_seconds=time.monotonic()-started,files={p:sha256((output/p).read_bytes()).hexdigest() for p in files})
    save(output/'manifest.json',manifest);return manifest
