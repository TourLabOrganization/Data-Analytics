"""Proposed branching survey classifier. Python 3.10+, standard library only.

Run: python score_survey.py example_answers.json
Scores describe rule-based preferences; they are not calibrated probabilities.
Each type is scored out of 100: raw option points are divided by the most raw points
that type can collect on one route (S1~S6 and its branches), so types with few scoring
options are not outnumbered by types that appear in many options.
S4 takes two different interests (unordered, equal weight). Each interest opens its branch
question; two interests with the same branch ask it once, so a route has one or two B answers.
"""
import itertools
import json
import math
import sys
from pathlib import Path

CONFIG=json.loads(Path(__file__).with_name('survey_config.json').read_text(encoding='utf-8'))
SCORING=CONFIG['scoring']

S4_COUNT=next(q for q in CONFIG['common'] if q['id']=='S4')['select_count']

def s4_branches(options):
    """Branch IDs opened by the chosen S4 options, without duplicates, in branch order."""
    return sorted({o['branch'] for o in options},key=lambda b:int(b[1:]))

def type_max_raw():
    """Most raw points each type can collect on one route: best option per common question,
    with the S4 pair and its branches taken together because S4 decides the branches."""
    branches={q['id']:q for q in CONFIG['branches']}; out={}
    s4=next(q for q in CONFIG['common'] if q['id']=='S4')
    for c in CONFIG['types']:
        rest=sum(max(o['scores'].get(c,0) for o in q['options']) for q in CONFIG['common'] if q['id']!='S4')
        out[c]=rest+max(sum(o['scores'].get(c,0) for o in pair)
                        +sum(max(b['scores'].get(c,0) for b in branches[bid]['options']) for bid in s4_branches(pair))
                        for pair in itertools.combinations(s4['options'],S4_COUNT))
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
        if q.get('selection')=='multiple':
            # S4: exactly select_count different options; order does not matter, stored in option order
            if not isinstance(value,(list,tuple)) or len(value)!=q['select_count'] or len(set(value))!=len(value) or not all(isinstance(v,str) and v in options for v in value):
                raise ValueError('Choose %d different options at %s'%(q['select_count'],q['id']))
            value=sorted(value,key=list(options).index)
            raw={}
            for v in value:
                for c,x in options[v]['scores'].items(): raw[c]=raw.get(c,0)+x
            contribution={c:v*UNIT[c] for c,v in raw.items()}
            for c,v in contribution.items(): scores[c]+=v
            ledger.append({'node':q['id'],'option':value,'contribution':contribution,'raw_points':raw})
            return [options[v] for v in value]
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
        if q['id']=='S4': branch_ids=s4_branches(option)
    stale=set(answers)&(set(branches)-set(branch_ids))
    if stale: raise ValueError('Inactive branch answers must be removed: '+','.join(sorted(stale)))
    for branch_id in branch_ids:
        if branch_id not in answers:
            later=set(answers)&({'F1'}|set(branch_ids[branch_ids.index(branch_id)+1:]))
            if later: raise ValueError('Answers out of sequence; missing '+branch_id)
            return {'version':CONFIG['version'],'status':'incomplete','next_question':branches[branch_id],'scores':scores,'ledger':ledger,'active_branches':branch_ids}
        apply(branches[branch_id])
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
    return {'version':CONFIG['version'],'status':'complete','answered_count':len(ledger),'active_branches':branch_ids,'scores':scores,'ledger':ledger,
       'mode':'single' if len(result_types)==1 else 'mixed','result_types':result_types,
       'relative_weights':{c:weights[c]/total for c in scores},'ranking':ranked,'base_gap':base_gap,
       'score_scale':'Each type out of 100 (raw points / type_max_raw x 100); F1 adds clarification_points directly',
       'interests':next(x['option'] for x in ledger if x['node']=='S4'),
       'interpretation':'Rule-based relative weights, not probability or cosine scores'}

if __name__=='__main__':
    if len(sys.argv)!=2:
        raise SystemExit('Usage: python score_survey.py answers.json')
    try:
        payload=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
        print(json.dumps(evaluate(payload),ensure_ascii=False,indent=2))
    except ValueError as e:
        raise SystemExit(str(e))
