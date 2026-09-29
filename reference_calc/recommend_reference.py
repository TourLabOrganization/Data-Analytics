"""Integrated 6.3 reference calculation; not a production deployment.
Type profiles are inherited design priors, not measured personal preferences.
Python 3.10+, standard library only. python recommend_reference.py demo_answers.json
"""
from pathlib import Path
import json,csv,math,sys
from score_survey import evaluate
ROOT=Path(__file__).resolve().parent
CFG=json.loads((ROOT/'recommendation_config.json').read_text(encoding='utf-8'))

def normalize(v):
    if len(v)!=5 or any(not math.isfinite(x) or x<0 for x in v) or sum(v)<=0:
        raise ValueError('Expected five nonnegative values with positive sum')
    return [x/sum(v) for x in v]

def recommend(answers):
    classification=evaluate(answers)
    if classification['status']!='complete':
        return {'status':'incomplete','survey':classification}
    selected=classification['result_types'];s=classification['scores'];top=max(s.values())
    a={c:2**((s[c]-top)/2) for c in selected};den=sum(a.values());a={c:w/den for c,w in a.items()}
    u=[sum(a[c]*normalize(CFG['profiles'][c])[j] for c in a) for j in range(5)]
    interest=answers['S4'];mapped={'C':0,'D':1,'E':4,'F':3,'G':2}
    themes=[]
    for t in CFG['themes']:
        p=normalize(t['proportions']);fit=sum(x*y for x,y in zip(u,p))
        bonus_base=p[mapped[interest]] if interest in mapped else t['night'] if interest=='H' else 0.0
        themes.append({'theme_id':t['id'],'name':t['name'],'region':t['region'],'profile_fit':fit,
            'primary_bonus':.5*bonus_base,'theme_index':100*(fit+.5*bonus_base)/1.5,
            'interest_support':'five_category' if interest in mapped else 'night_metadata' if interest=='H' else 'additional_metadata_required',
            'G':0.0,'H':0.0,'A':0.0,'D':0.0})
    themes.sort(key=lambda x:(-x['theme_index'],x['theme_id']))
    # Course bonuses: S4 interest (same 0.5 weight as themes), S6 evening/night and S3 pace (0.1 each).
    # Only active terms enter the denominator, so the index stays 0~100 and equals 100*cos*coverage when none apply.
    cw=CFG['course_score'];night_active=answers['S6']=='C' and interest!='H';pace=answers['S3'] if answers['S3'] in ('A','C') else None
    courses=[];normu=math.sqrt(sum(x*x for x in u))
    with (ROOT/'eligible_courses.csv').open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            p=[float(row['analysis_share_'+c]) for c in CFG['categories']]
            cov=float(row['analysis_category_coverage']);night=int(row['analysis_night_flag']);n=int(row['analysis_visit_candidate_count'])
            assert all(math.isfinite(x) and x>=0 for x in p) and 0<cov<=1 and abs(sum(p)-cov)<1e-8 and night in (0,1) and n>=2
            denom=normu*math.sqrt(sum(x*x for x in p))
            cosine=sum(x*y for x,y in zip(u,p))/denom
            length=min(max((n-3)/5,0.0),1.0)
            terms={}
            if interest in mapped:terms['interest']=(cw['interest_weight'],p[mapped[interest]])
            elif interest=='H':terms['interest']=(cw['interest_weight'],night)
            if night_active:terms['night']=(cw['night_weight'],night)
            if pace:terms['pace']=(cw['pace_weight'],length if pace=='A' else 1-length)
            scale=1+sum(w for w,_ in terms.values())
            cs=[100*x*y/denom*cov/scale for x,y in zip(u,p)]
            bonus={k:100*w*b/scale for k,(w,b) in terms.items()}
            courses.append({'course_id':row['analysis_course_id'],'region':row['analysis_region'],'name':row['analysis_name'],
                 'cosine_similarity':cosine,'coverage':cov,'category_fit_score':100*cosine*cov,'adjusted_score':sum(cs)+sum(bonus.values()),
                 'contributions':cs,'bonus_points':bonus,'visit_candidate_count':n,'night_flag':night,
                 'proportions':p,'route_text':row['코스(경유지)'],'T_cluster':row['analysis_T_cluster'],
                 'q_source':'type_profile_prior','operational_availability_verified':False})
    courses.sort(key=lambda x:(-x['adjusted_score'],-x['cosine_similarity'],-x['coverage'],x['course_id']))
    distinct=[];seen=set()
    for c in courses:
        if c['region'] not in seen:distinct.append(c);seen.add(c['region'])
        if len(distinct)==5:break
    return {'version':CFG['version'],'status':'complete','survey':classification,'mix_weights':a,'preference_vector':u,
        'q_source':'type_profile_prior','theme_rankings':themes,'theme_top3':themes[:3],
        'course_bonus_terms':sorted(courses[0]['bonus_points']) if courses else [],
        'course_rankings':courses,'course_distinct_region_top5':distinct,'score_fusion':False,
        'model_status':'reference_calculation_not_empirically_validated_or_deployed'}

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: python recommend_reference.py answers.json')
    print(json.dumps(recommend(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))),ensure_ascii=False,indent=2))
