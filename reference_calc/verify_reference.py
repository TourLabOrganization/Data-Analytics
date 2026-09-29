from pathlib import Path
import json,csv,sys,math
root=Path(__file__).resolve().parent;sys.path.insert(0,str(root));sys.path.insert(0,str(root.parent/'survey/implementation'))
from recommend_reference import recommend,normalize,CFG
from score_survey import evaluate,CONFIG
CFG_S=CONFIG['scoring']
# 30대 · 혼자 · 천천히 · 역사+자연 · 한적한 곳 · 아침, B2 문화유산 산책, B3 없음, F1 균형
answers={'S1':'C','S2':'A','S3':'C','S4':['C','D'],'S5':'C','S6':'A','B2':'A','B3':'D','F1':'BALANCED'}
n_courses=sum(1 for _ in csv.DictReader((root/'eligible_courses.csv').open(encoding='utf-8-sig')))
out=recommend(answers);d=dict(answers);d['B2']='D';d['B3']='A';d.pop('F1');none=recommend(d)
for name,obj in [('demo_answers',answers),('demo_result',out),('demo_none_answers',d),('demo_none_result',none)]:
 (root/f'{name}.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2))
assert out['survey']['result_types']==['C4','C5']
# 100-point type scores: raw 13 of C4's 19 and 14 of C5's 22 (S4 역사+자연 both count), then F1 BALANCED adds 20/2 to each
sc=out['survey']['scores'];pts=CFG_S['clarification_points']/2
assert abs(sc['C4']-(100*13/19+pts))<1e-9 and abs(sc['C5']-(100*14/22+pts))<1e-9
# B2 없음 keeps the C4 points before it; B3 A adds C5 4: C4 10/19, C5 18/22 → C5 alone
assert abs(none['survey']['scores']['C4']-100*10/19)<1e-9 and abs(none['survey']['scores']['C5']-100*18/22)<1e-9 and none['survey']['result_types']==['C5']
assert out['survey']['interests']==['C','D'] and out['survey']['active_branches']==['B2','B3'] and out['survey']['answered_count']==9
h=CFG_S['weight_halving_points'];w4=1.0;w5=2**((sc['C5']-sc['C4'])/h)
assert abs(out['mix_weights']['C4']-w4/(w4+w5))<1e-12 and abs(out['mix_weights']['C5']-w5/(w4+w5))<1e-12
P={c:normalize(v) for c,v in CFG['profiles'].items()}
assert all(abs(x-(out['mix_weights']['C4']*a+out['mix_weights']['C5']*b))<1e-12 for x,a,b in zip(out['preference_vector'],P['C4'],P['C5']))
assert len(out['course_rankings'])==n_courses
assert len({r['region'] for r in out['course_distinct_region_top5']})==5
assert out['q_source']=='type_profile_prior' and out['score_fusion'] is False
assert all(abs(sum(normalize(v))-1)<1e-12 for v in CFG['profiles'].values())
assert all(0<=t['theme_index']<=100 for t in out['theme_rankings'])
assert all(0<=r['adjusted_score']<=100 and abs(sum(r['contributions'])+sum(r['bonus_points'].values())-r['adjusted_score'])<1e-10 for r in out['course_rankings'])
assert out['course_bonus_terms']==['interest','pace']
def done(a):
 r=recommend(a)
 return r if r['status']=='complete' else recommend({**a,'F1':'BALANCED'})
# 드라마 + 쇼핑: neither interest has a category column, so no interest term
plain=done({'S1':'C','S2':'A','S3':'B','S4':['A','I'],'S5':'C','S6':'A','B1':'A','B7':'A'})
assert plain['course_bonus_terms']==[] and all(abs(r['adjusted_score']-r['category_fit_score'])<1e-10 for r in plain['course_rankings'])
# 드라마 + 야경: the interest term is the night flag alone; S6 저녁·밤 adds no second night term when 야경 is chosen
night=done({'S1':'B','S2':'C','S3':'B','S4':['A','H'],'S5':'A','S6':'C','B1':'C','B6':'B'})
assert night['course_bonus_terms']==['interest'] and all(r['night_flag']==1 for r in night['course_distinct_region_top5'][:3])
# 자연 + 바다 share branch B3, which is asked once
sea=evaluate({'S1':'C','S2':'E','S3':'B','S4':['D','E'],'S5':'B','S6':'B','B3':'B'})
if sea['status']=='incomplete':sea=evaluate({'S1':'C','S2':'E','S3':'B','S4':['D','E'],'S5':'B','S6':'B','B3':'B','F1':'C9'})
assert sea['active_branches']==['B3'] and sea['answered_count'] in (7,8)
assert 'C9' in sea['result_types']
assert all(all(t[k]==0 for k in ['G','H','A','D']) for t in out['theme_rankings'])
for name,rows in [('demo_themes',out['theme_rankings']),('demo_courses',out['course_rankings']),('demo_region_top5',out['course_distinct_region_top5'])]:
 with (root/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
checks={'status':'passed','survey_score_unit':CFG_S['score_unit'],'mixed_types':out['survey']['result_types'],'mix_weights':out['mix_weights'],'course_count':n_courses,'distinct_region_count':5,'course_bonus_terms_demo':out['course_bonus_terms'],'no_bonus_equals_category_fit':True,'night_interest_top3_night_courses':True,'type_profile_L1':sum(out['preference_vector']),'D_preserves_previous_scores':True,'empirical_validation':False,'deployment':False}
(root/'integration_verification.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
print(json.dumps(checks,ensure_ascii=False,indent=2))
