from pathlib import Path
import json,csv,sys,math
root=Path(__file__).resolve().parent;sys.path.insert(0,str(root))
from recommend_reference import recommend,normalize,CFG
from score_survey import evaluate
answers={'S1':'C','S2':'A','S3':'C','S4':'C','S5':'C','S6':'A','B2':'A','F1':'BALANCED'}
out=recommend(answers);d=dict(answers);d['B2']='D';d.pop('F1');none=recommend(d)
for name,obj in [('demo_answers',answers),('demo_result',out),('demo_none_answers',d),('demo_none_result',none)]:
 (root/f'{name}.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2))
assert out['survey']['result_types']==['C4','C5']
assert out['survey']['scores']['C4']==out['survey']['scores']['C5']==13
assert none['survey']['scores']['C4']==8 and none['survey']['scores']['C5']==11
assert all(abs(x-y)<1e-12 for x,y in zip(out['preference_vector'],[.3,.45,.025,.125,.1]))
assert len(out['course_rankings'])==179
assert len({r['region'] for r in out['course_distinct_region_top5']})==5
assert out['q_source']=='type_profile_prior' and out['score_fusion'] is False
assert all(abs(sum(normalize(v))-1)<1e-12 for v in CFG['profiles'].values())
assert all(0<=t['theme_index']<=100 for t in out['theme_rankings'])
assert all(0<=r['adjusted_score']<=100 and abs(sum(r['contributions'])-r['adjusted_score'])<1e-10 for r in out['course_rankings'])
assert all(all(t[k]==0 for k in ['G','H','A','D']) for t in out['theme_rankings'])
for name,rows in [('demo_themes',out['theme_rankings']),('demo_courses',out['course_rankings']),('demo_region_top5',out['course_distinct_region_top5'])]:
 with (root/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
checks={'status':'passed','mixed_types':out['survey']['result_types'],'course_count':179,'distinct_region_count':5,'type_profile_L1':sum(out['preference_vector']),'D_preserves_previous_scores':True,'empirical_validation':False,'deployment':False}
(root/'integration_verification.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
print(json.dumps(checks,ensure_ascii=False,indent=2))
