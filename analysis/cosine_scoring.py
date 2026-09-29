import numpy as np
import pandas as pd
CATEGORIES=["herit","heal","activity","food","sea"]
SURVEY_FIELDS=[f"q_{c}" for c in CATEGORIES]
COSINE_RESULTS={}
def rank_courses_cosine(response, courses, top_n=None):
    q=np.array([response[c] for c in SURVEY_FIELDS],float)
    if not np.isfinite(q).all() or (q<0).any() or (q>5).any() or not np.equal(q,np.floor(q)).all():
        raise ValueError('설문은 0~5의 정수 5개를 모두 입력해야 합니다.')
    if np.linalg.norm(q)<=1e-12:
        return pd.DataFrame(), 'NO_STATED_PREFERENCE'
    candidates=courses[courses.cluster_eligible].copy()
    desired=str(response.get('desired_region','')).strip()
    # Exact source region label only. No inferred proximity or ambiguous name merging.
    if desired:candidates=candidates[candidates.region.eq(desired)]
    if candidates.empty:return pd.DataFrame(),'NO_ELIGIBLE_COURSES_IN_REGION'
    shares=candidates[[f'share_{c}' for c in CATEGORIES]].to_numpy(float)
    norms=np.linalg.norm(shares,axis=1); valid=norms>1e-12
    candidates=candidates.loc[valid].copy();shares=shares[valid];norms=norms[valid]
    if candidates.empty:return pd.DataFrame(),'NO_CLASSIFIED_COURSES'
    contributions=(q/np.linalg.norm(q))[None,:]*(shares/norms[:,None])
    sim=contributions.sum(axis=1)
    coverage=shares.sum(axis=1)
    # Coverage is a conservative data-completeness adjustment, not calibrated probability.
    candidates['cosine_similarity']=np.clip(sim,0,1)
    candidates['cosine_fit_score']=100*candidates.cosine_similarity
    candidates['coverage_factor']=coverage
    candidates['coverage_adjusted_score']=100*candidates.cosine_similarity*coverage
    for j,c in enumerate(CATEGORIES):
        candidates[f'contribution_{c}_points']=100*contributions[:,j]*coverage
    if 'T' in COSINE_RESULTS:
        labels=COSINE_RESULTS['T']['assignments'].set_index('source_index').cosine_cluster
        candidates['cosine_cluster']=labels.reindex(candidates.index)
    else:candidates['cosine_cluster']=pd.NA
    candidates['respondent_id']=str(response['respondent_id'])
    candidates['data_status']=str(response.get('data_status','USER_INPUT'))
    candidates['operational_availability_verified']=False
    # Order and rank on rounded keys so mathematically equal scores (float noise ~1e-14) tie.
    keys=pd.DataFrame({'s':candidates.coverage_adjusted_score.round(9),'c':candidates.cosine_similarity.round(12),
                       'v':candidates.category_coverage.round(12),'id':candidates.course_id},index=candidates.index)
    candidates=candidates.loc[keys.sort_values(['s','c','v','id'],ascending=[False,False,False,True]).index]
    # Equal component scores share a rank. course_id is only deterministic display order.
    candidates['score_rank']=keys.s.reindex(candidates.index).rank(method='min',ascending=False).astype(int)
    candidates['display_order']=np.arange(1,len(candidates)+1)
    keep=['respondent_id','data_status','score_rank','display_order','course_id','region','name','cosine_cluster',
          'cosine_similarity','cosine_fit_score','coverage_factor','coverage_adjusted_score',
          *[f'contribution_{c}_points' for c in CATEGORIES],'operational_availability_verified']
    result=candidates[keep]
    assert np.allclose(result[[f'contribution_{c}_points' for c in CATEGORIES]].sum(axis=1),result.coverage_adjusted_score)
    return result.head(top_n) if top_n else result, 'SCORED_CANDIDATES_NOT_BOOKING_CONFIRMATION'
