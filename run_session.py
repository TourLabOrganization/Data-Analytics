"""Run legacy/v4 scoring, independent cosine scoring and, when supplied, the branch survey 6.3 reference recommendation for one session.

The three results are written side by side for comparison; their scores are never added together.
"""
from pathlib import Path
import argparse,json,subprocess,shutil,os,sys
import pandas as pd
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'analysis'))
import cosine_scoring as cs
sys.path.insert(0,str(ROOT/'reference_calc'))
import recommend_reference as rr
def shown(path):
    # Paths inside the repository are recorded relative to it so the summary does not depend on the checkout location.
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
def main():
    p=argparse.ArgumentParser()
    p.add_argument('input',nargs='?',default=str(ROOT/'examples/full_session.json'))
    p.add_argument('--run-dir',help='Path to the analysis outputs_cosine/run_... folder')
    p.add_argument('--output',default=str(ROOT/'session_results'))
    p.add_argument('--node',default=os.environ.get('CODEX_PRIMARY_RUNTIME_NODE') or shutil.which('node'))
    a=p.parse_args();src=Path(a.input).resolve();data=json.loads(src.read_text(encoding='utf-8-sig'))
    if not a.node:raise SystemExit('Node.js 18 이상을 설치하거나 --node 경로를 지정하세요.')
    runs=sorted((ROOT/'analysis/outputs_cosine').glob('run_*'))
    run=Path(a.run_dir).resolve() if a.run_dir else runs[-1] if runs else None
    if run is None:raise SystemExit('먼저 analysis/run_analysis.py 또는 노트북 Run All을 실행하세요.')
    output=Path(a.output).resolve();output.mkdir(parents=True,exist_ok=True)
    result=subprocess.run([a.node,str(ROOT/'tour_scoring/src/session.cjs'),str(src)],check=True,text=True,capture_output=True,encoding='utf-8')
    legacy=json.loads(result.stdout)
    (output/'legacy_v4_scores_and_stay.json').write_text(json.dumps(legacy,ensure_ascii=False,indent=2),encoding='utf-8')
    raw=pd.read_csv(run/'tables/T_citytour_assignments_all.csv',keep_default_na=False)
    courses=raw[[c for c in raw if c.startswith('analysis_')]].rename(columns=lambda x:x.removeprefix('analysis_'))
    courses['cluster_eligible']=courses.cluster_eligible.astype(str).str.lower().eq('true')
    labels=pd.read_csv(run/'tables/T_cosine_assignments.csv')
    cs.COSINE_RESULTS={'T':{'assignments':labels}}
    q=data.get('cosineSurvey')
    if q is None:
        ranked=pd.DataFrame();status='COSINE_SURVEY_NOT_SUPPLIED'
    else:
        if not str(q.get('respondent_id','')).strip():raise ValueError('respondent_id가 필요합니다.')
        ranked,status=cs.rank_courses_cosine(q,courses)
    if len(ranked):
        ranked.to_csv(output/'cosine_all_courses.csv',index=False,encoding='utf-8-sig')
        # Apply the existing regional diversity rule after cosine ranking, without score fusion.
        picked=ranked.drop_duplicates('region').head(5)
        picked.to_csv(output/'cosine_distinct_region_top5.csv',index=False,encoding='utf-8-sig')
    else:
        picked=pd.DataFrame()
        for filename in ['cosine_all_courses.csv','cosine_distinct_region_top5.csv']:
            (output/filename).unlink(missing_ok=True)
    branch=data.get('branchSurvey');branch_file=output/'branch_survey_recommendation.json'
    if branch is None:
        branch_summary={'status':'BRANCH_SURVEY_NOT_SUPPLIED'};branch_file.unlink(missing_ok=True)
    else:
        rec=rr.recommend(branch)
        if rec['status']!='complete':
            branch_summary={'status':'INCOMPLETE','next_question':rec['survey']['next_question']['id']};branch_file.unlink(missing_ok=True)
        else:
            sv=rec['survey']
            # Compact record: the full 229-course ranking stays reproducible from reference_calc.
            keep={'version':rec['version'],'survey_version':sv['version'],'answers':branch,'scores':sv['scores'],'ledger':sv['ledger'],
                  'result_types':sv['result_types'],'mode':sv['mode'],'mix_weights':rec['mix_weights'],'preference_vector':rec['preference_vector'],
                  'theme_top3':rec['theme_top3'],'course_bonus_terms':rec['course_bonus_terms'],
                  'course_distinct_region_top5':[{k:c[k] for k in ('course_id','region','name','category_fit_score','bonus_points','adjusted_score','route_text')} for c in rec['course_distinct_region_top5']],
                  'q_source':rec['q_source'],'model_status':rec['model_status']}
            branch_file.write_text(json.dumps(keep,ensure_ascii=False,indent=2),encoding='utf-8')
            branch_summary={'status':'COMPLETE','survey_version':sv['version'],'result_types':sv['result_types'],
                'mix_weights':{c:round(w,6) for c,w in rec['mix_weights'].items()},
                'theme_top3':[{'name':t['name'],'score':round(t['theme_index'],6)} for t in rec['theme_top3']],
                'city_picks':[{'region':c['region'],'name':c['name'],'score':round(c['adjusted_score'],6)} for c in rec['course_distinct_region_top5']]}
    summary={'status':status,'cosine_candidates':len(ranked),'cosine_distinct_regions':len(picked),
        'legacy_theme_picks':[{'key':x['k'],'score':x['score']} for x in legacy['recommendation']['themePicks']],
        'legacy_city_picks':[{'region':x['region'],'name':x['name'],'score':x['score']} for x in legacy['recommendation']['cityPicks']],
        'branch_survey':branch_summary,
        'score_fusion':False,'input':shown(src),'analysis_run':shown(run),'data_status':data.get('data_status','USER_SUPPLIED')}
    (output/'session_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
