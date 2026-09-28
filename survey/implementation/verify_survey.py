"""Exhaustive route/score checks, not empirical survey validation."""
import itertools
import json
from pathlib import Path
from score_survey import CONFIG,evaluate

def run():
    common=CONFIG['common']; branches={q['id']:q for q in CONFIG['branches']}
    assert len(common)==6 and len(branches)==7
    for q in common+list(branches.values()):
        for o in q['options']:
            if q['id'].startswith('B') and o['id']=='D':
                assert o['label']=='없음' and o['scores']=={}
                assert o['score_action']=='no_change'
            else:
                assert o['scores'] and min(o['scores'].values())>0
            assert set(o['scores'])<=set(CONFIG['types'])
            if q['id'].startswith('B'): assert sum(o['scores'].values())==(0 if o['id']=='D' else 4)
    completed=0; base_paths=0; winners=set(); examples={}; max_mix=0
    for choices in itertools.product(*[[o['id'] for o in q['options']] for q in common]):
        a=dict(zip([q['id'] for q in common],choices))
        branch_id=next(o for o in common[3]['options'] if o['id']==a['S4'])['branch']
        for opt in branches[branch_id]['options']:
            aa={**a,branch_id:opt['id']}; base_paths+=1
            r=evaluate(aa)
            if opt['id']=='D':
                before=evaluate(a)
                assert r['scores']==before['scores']
                assert r['ledger'][-1]=={'node':branch_id,'option':'D','contribution':{}}
            variants=[(aa,r)]
            if r['status']=='incomplete':
                assert r['next_question']['id']=='F1'
                variants=[({**aa,'F1':o['id']},evaluate({**aa,'F1':o['id']})) for o in r['next_question']['options']]
            for reply,out in variants:
                assert out['status']=='complete' and out['answered_count'] in (7,8)
                assert abs(sum(out['relative_weights'].values())-1)<1e-10
                assert abs(sum(out['scores'].values())-sum(sum(x['contribution'].values()) for x in out['ledger']))<1e-10
                completed+=1
                max_mix=max(max_mix,len(out['result_types']))
                if out['mode']=='single':
                    winners.add(out['result_types'][0])
                if out['mode'] not in examples:
                    examples[out['mode']]={'answers':reply,'result':out}
    assert winners==set(CONFIG['types'])
    # Inactive answers and invalid options must be rejected.
    seed=examples['single']['answers']
    active=next(k for k in seed if k.startswith('B'))
    inactive=next(k for k in branches if k!=active)
    for bad in ({**seed,inactive:'A'},{**seed,'S1':None},{**seed,'S4':['A','B']},{**seed,'S1':'Z'}):
        try: evaluate(bad)
        except ValueError: pass
        else: raise AssertionError('invalid reply accepted')
    report={'status':'passed','fixed_options':60,'common_questions':6,'branch_questions':7,'base_paths':base_paths,'completed_paths_including_clarification':completed,'answer_counts':[7,8],'single_result_reachable':sorted(winners,key=lambda c:int(c[1:])),'max_mixed_types_observed':max_mix,'checks':['Common and branch A/B/C choices add to eligible types','Every branch D is answered with zero contribution and leaves all previous scores unchanged','Branch A/B/C contribute 4 points; D contributes zero without redistribution','All routes finish in 7 or 8 answers','Every type can be a sole result','Stale branch and invalid answers rejected','Score ledger and relative weights consistent'],'interpretation':'Exhaustive combinatorial checks; not accuracy, user distribution, or survey validity evidence.'}
    Path(__file__).with_name('verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    Path(__file__).with_name('verified_examples.json').write_text(json.dumps(examples,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':run()
