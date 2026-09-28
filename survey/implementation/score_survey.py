"""Proposed branching survey classifier. Python 3.10+, standard library only.

Run: python score_survey.py example_answers.json
Scores describe rule-based preferences; they are not calibrated probabilities.
"""
import json
import math
import sys
from pathlib import Path

CONFIG=json.loads(Path(__file__).with_name('survey_config.json').read_text(encoding='utf-8'))

def evaluate(answers):
    if not isinstance(answers,dict):
        raise ValueError('answers must be an object')
    common=CONFIG['common']; branches={q['id']:q for q in CONFIG['branches']}
    known={q['id'] for q in common}|set(branches)|{'F1'}
    if set(answers)-known:
        raise ValueError('Unknown question ID')
    scores={c:0.0 for c in CONFIG['types']}; ledger=[]
    def apply(q):
        value=answers[q['id']]
        options={o['id']:o for o in q['options']}
        if not isinstance(value,str) or value not in options:
            raise ValueError('Invalid option at '+q['id'])
        contribution=options[value]['scores']
        for c,v in contribution.items(): scores[c]+=v
        ledger.append({'node':q['id'],'option':value,'contribution':contribution})
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
    candidates=[c for c in ranked if scores[ranked[0]]-scores[c]<=2]
    if base_gap<=2:
        clarification={'id':'F1','title':'이번 여행에서 가장 양보하고 싶지 않은 경험은 무엇인가요','selection':'single',
          'options':[{'id':c,'label':CONFIG['types'][c]['scene'],'scores':{c:4}} for c in candidates]+[
             {'id':'BALANCED','label':'위 경험들이 비슷하게 중요해요','scores':{c:4/len(candidates) for c in candidates}}]}
        if 'F1' not in answers:
            return {'version':CONFIG['version'],'status':'incomplete','next_question':clarification,'scores':scores,'ledger':ledger,'clarification_candidates':candidates}
        apply(clarification)
    elif 'F1' in answers:
        raise ValueError('F1 is not active; remove stale confirmation')
    ranked=sorted(scores,key=lambda c:(-scores[c],int(c[1:])))
    top=scores[ranked[0]]
    result_types=[c for c in ranked if top-scores[c]<=2]
    weights={c:2**((scores[c]-top)/2) for c in scores}
    total=math.fsum(weights.values())
    return {'version':CONFIG['version'],'status':'complete','answered_count':len(ledger),'scores':scores,'ledger':ledger,
       'mode':'single' if len(result_types)==1 else 'mixed','result_types':result_types,
       'relative_weights':{c:weights[c]/total for c in scores},'ranking':ranked,'base_gap':base_gap,
       'interpretation':'Rule-based relative weights, not probability or cosine scores'}

if __name__=='__main__':
    if len(sys.argv)!=2:
        raise SystemExit('Usage: python score_survey.py answers.json')
    try:
        payload=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
        print(json.dumps(evaluate(payload),ensure_ascii=False,indent=2))
    except ValueError as e:
        raise SystemExit(str(e))
