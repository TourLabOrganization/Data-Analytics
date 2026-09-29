"""Proposed branching survey classifier. Python 3.10+, standard library only.

Run: python score_survey.py example_answers.json
Scores describe rule-based preferences; they are not calibrated probabilities.
Each type is scored out of 100: raw option points are divided by the most raw points
that type can collect on one route (S1~S6 and one branch), so types with few scoring
options are not outnumbered by types that appear in many options.
"""
import json
import math
import sys
from pathlib import Path

CONFIG=json.loads(Path(__file__).with_name('survey_config.json').read_text(encoding='utf-8'))
SCORING=CONFIG['scoring']

def type_max_raw():
    """Most raw points each type can collect on one route: best option per common question,
    with S4 and its branch taken together because S4 decides the branch."""
    branches={q['id']:q for q in CONFIG['branches']}; out={}
    for c in CONFIG['types']:
        rest=sum(max(o['scores'].get(c,0) for o in q['options']) for q in CONFIG['common'] if q['id']!='S4')
        s4=next(q for q in CONFIG['common'] if q['id']=='S4')
        out[c]=rest+max(o['scores'].get(c,0)+max(b['scores'].get(c,0) for b in branches[o['branch']]['options']) for o in s4['options'])
    return out
TYPE_MAX_RAW=type_max_raw()
assert TYPE_MAX_RAW==SCORING['type_max_raw'], 'survey_config.json type_max_raw is stale'
UNIT={c:SCORING['type_full_score']/m for c,m in TYPE_MAX_RAW.items()}

def evaluate(answers):
    if not isinstance(answers,dict):
        raise ValueError('answers must be an object')
    common=CONFIG['common']; branches={q['id']:q for q in CONFIG['branches']}
    known={q['id'] for q in common}|set(branches)|{'F1'}
    if set(answers)-known:
        raise ValueError('Unknown question ID')
    scores={c:0.0 for c in CONFIG['types']}; ledger=[]
    def apply(q,converted=False):
        value=answers[q['id']]
        options={o['id']:o for o in q['options']}
        if not isinstance(value,str) or value not in options:
            raise ValueError('Invalid option at '+q['id'])
        raw=options[value]['scores']
        # Question options carry raw points; F1 points are already on the 100-point scale.
        contribution=dict(raw) if converted else {c:v*UNIT[c] for c,v in raw.items()}
        for c,v in contribution.items(): scores[c]+=v
        entry={'node':q['id'],'option':value,'contribution':contribution}
        if not converted: entry['raw_points']=raw
        ledger.append(entry)
        return options[value]
    for idx,q in enumerate(common):
        if q['id'] not in answers:
            allowed={x['id'] for x in common[:idx]}
            if set(answers)-allowed:
                raise ValueError('Answers out of sequence; missing '+q['id'])
            return {'version':CONFIG['version'],'status':'incomplete','next_question':q,'scores':scores,'ledger':ledger}
        option=apply(q)
        if q['id']=='S4': branch_id=option['branch']
    stale=set(answers)&(set(branches)-{branch_id})
    if stale: raise ValueError('Inactive branch answers must be removed: '+','.join(sorted(stale)))
    branch=branches[branch_id]
    if branch_id not in answers:
        if 'F1' in answers: raise ValueError('F1 before branch answer')
        return {'version':CONFIG['version'],'status':'incomplete','next_question':branch,'scores':scores,'ledger':ledger}
    apply(branch)
    ranked=sorted(scores,key=lambda c:(-scores[c],int(c[1:])))
    base_gap=scores[ranked[0]]-scores[ranked[1]]
    margin=SCORING['clarification_margin']; points=SCORING['clarification_points']; eps=1e-9
    candidates=[c for c in ranked if scores[ranked[0]]-scores[c]<=margin+eps]
    if base_gap<=margin+eps:
        clarification={'id':'F1','title':'이번 여행에서 가장 양보하고 싶지 않은 경험은 무엇인가요','selection':'single',
          'options':[{'id':c,'label':CONFIG['types'][c]['scene'],'scores':{c:points}} for c in candidates]+[
             {'id':'BALANCED','label':'위 경험들이 비슷하게 중요해요','scores':{c:points/len(candidates) for c in candidates}}]}
        if 'F1' not in answers:
            return {'version':CONFIG['version'],'status':'incomplete','next_question':clarification,'scores':scores,'ledger':ledger,'clarification_candidates':candidates}
        apply(clarification,converted=True)
    elif 'F1' in answers:
        raise ValueError('F1 is not active; remove stale confirmation')
    ranked=sorted(scores,key=lambda c:(-scores[c],int(c[1:])))
    top=scores[ranked[0]]
    result_types=[c for c in ranked if top-scores[c]<=SCORING['final_mixed_margin']+eps]
    weights={c:2**((scores[c]-top)/SCORING['weight_halving_points']) for c in scores}
    total=math.fsum(weights.values())
    return {'version':CONFIG['version'],'status':'complete','answered_count':len(ledger),'scores':scores,'ledger':ledger,
       'mode':'single' if len(result_types)==1 else 'mixed','result_types':result_types,
       'relative_weights':{c:weights[c]/total for c in scores},'ranking':ranked,'base_gap':base_gap,
       'score_scale':'Each type out of 100 (raw points / type_max_raw x 100); F1 adds clarification_points directly',
       'interpretation':'Rule-based relative weights, not probability or cosine scores'}

if __name__=='__main__':
    if len(sys.argv)!=2:
        raise SystemExit('Usage: python score_survey.py answers.json')
    try:
        payload=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
        print(json.dumps(evaluate(payload),ensure_ascii=False,indent=2))
    except ValueError as e:
        raise SystemExit(str(e))
