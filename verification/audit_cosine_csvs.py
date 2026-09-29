"""Recompute every cosine-similarity CSV from the stored features and compare.

Run from the repository root: python verification/audit_cosine_csvs.py [analysis/outputs_cosine/run_...]
Without an argument the newest run folder is used. Writes verification/cosine_csv_audit.json and exits 1 on any issue.
Covers GC/TC unit features, centers, assignments, transitions, silhouettes, candidate selection,
representatives, profiles, the *_with_cosine_all tables, the direct-preference course rankings,
session_results and the reference_calc course scores.
"""
import sys, pathlib
import numpy as np, pandas as pd, json
from sklearn.metrics import silhouette_samples, silhouette_score, pairwise_distances
RUN = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else sorted(pathlib.Path('analysis/outputs_cosine').glob('run_*'))[-1]
R = str(RUN / 'tables') + '/'
rd=lambda f: pd.read_csv(R+f+'.csv',encoding='utf-8-sig')
issues=[]; ok=[]
def check(name,cond,detail=''):
    (ok if cond else issues).append(f'{name} {detail}')
CATS=['herit','heal','activity','food','sea']
for P,feat_all in [('G','G_features'),('T','T_features')]:
    F=rd(feat_all).set_index('source_index'); X=F.to_numpy(float)
    U=rd(f'{P}_cosine_unit_features').set_index('source_index')
    check(f'{P} unit columns = feature columns',list(U.columns)==list(F.columns))
    Uv=U.loc[F.index].to_numpy(float); n=np.linalg.norm(X,axis=1)
    check(f'{P} unit norm 1',np.allclose(np.linalg.norm(Uv,axis=1),1,atol=1e-9))
    check(f'{P} unit = feature/norm',np.allclose(Uv,X/n[:,None],atol=1e-9),f'max {np.abs(Uv-X/n[:,None]).max():.2e}')
    E=rd(f'{P}_cosine_eligibility').set_index('source_index')
    check(f'{P} eligibility norm',np.allclose(E.loc[F.index,'norm'],n,atol=1e-9)); check(f'{P} all eligible',E.cosine_eligible.all(),f'{(~E.cosine_eligible).sum()} excluded')
    C=rd(f'{P}_cosine_centers'); labs=C.cosine_cluster.tolist(); Cv=C[F.columns].to_numpy(float)
    check(f'{P} centers unit norm',np.allclose(np.linalg.norm(Cv,axis=1),1,atol=1e-9))
    A=rd(f'{P}_cosine_assignments').set_index('source_index')
    check(f'{P} assignments rows',len(A)==len(F) and set(A.index)==set(F.index),f'{len(A)}')
    S=U.loc[A.index].to_numpy(float)@Cv.T; top=np.sort(S,axis=1)
    check(f'{P} assigned_cosine = max u·c',np.allclose(A.assigned_cosine,top[:,-1],atol=1e-9),f'max {np.abs(A.assigned_cosine-top[:,-1]).max():.2e}')
    check(f'{P} margin = best - second',np.allclose(A.margin_to_second,top[:,-1]-top[:,-2],atol=1e-9))
    am=np.array(labs)[S.argmax(axis=1)]; mism=(am!=A.cosine_cluster.to_numpy()).sum()
    check(f'{P} cluster = argmax center',mism==0,f'{mism} mismatches')
    check(f'{P} cosine range',A.assigned_cosine.between(-1-1e-12,1+1e-12).all() and (A.margin_to_second>=-1e-12).all(),f'min assigned {A.assigned_cosine.min():.3f}')
    # center = normalized mean of member unit vectors (spherical k-means fixed point)
    cen=np.array([U.loc[A.index[A.cosine_cluster==l]].to_numpy().sum(0) for l in labs]); cen/=np.linalg.norm(cen,axis=1)[:,None]
    check(f'{P} centers = normalized member mean',np.allclose(cen,Cv,atol=1e-8),f'max {np.abs(cen-Cv).max():.2e}')
    T=rd(f'{P}_baseline_cosine_transition').set_index('baseline_cluster')
    ct=pd.crosstab(A.baseline_cluster,A.cosine_cluster)
    check(f'{P} transition = crosstab',ct.reindex(index=T.index,columns=T.columns).fillna(0).astype(int).equals(T.astype(int)))
    check(f'{P} transition total',int(T.values.sum())==len(A))
    Sm=rd(f'{P}_cosine_silhouette_samples').set_index('source_index')
    check(f'{P} sample cols match assignments',np.allclose(Sm.assigned_cosine,A.loc[Sm.index,'assigned_cosine']) and (Sm.cosine_cluster==A.loc[Sm.index,'cosine_cluster']).all())
    Us=U.loc[Sm.index].to_numpy(float); Dc=np.clip(1-Us@Us.T,0,2); np.fill_diagonal(Dc,0)
    ss=silhouette_samples(Dc,Sm.cosine_cluster,metric='precomputed')
    check(f'{P} silhouette samples recomputed',np.allclose(ss,Sm.cosine_silhouette,atol=1e-9),f'mean {ss.mean():.6f}, negative {(ss<0).mean():.3f}')
    cmp=rd('cosine_baseline_comparison').query('dataset==@P').set_index('model')
    De=pairwise_distances(F.loc[Sm.index].to_numpy(float)); np.fill_diagonal(De,0)
    for m,lab in [('baseline_selected',Sm.baseline_cluster),('cosine_selected',Sm.cosine_cluster)]:
        c=silhouette_score(Dc,lab,metric='precomputed'); e=silhouette_score(De,lab,metric='precomputed')
        check(f'{P} comparison {m}',abs(c-cmp.loc[m,'cosine_silhouette'])<1e-9 and abs(e-cmp.loc[m,'euclidean_silhouette'])<1e-9,f'cos {c:.6f} eu {e:.6f}')
    check(f'{P} comparison n/k',cmp.loc['cosine_selected','n']==len(A) and cmp.loc['cosine_selected','k']==len(labs) and cmp.loc['cosine_selected','sample_n']==len(Sm))
    cand=rd(f'{P}_cosine_candidates'); sp=cand[cand.model=='spherical_cosine']; pool=sp[sp.passes_gates]
    sel=pool.sort_values(['cosine_silhouette_mean','k'],ascending=[False,True]).iloc[0]
    check(f'{P} selected k = best passing candidate',int(sel.k)==len(labs),f'k={int(sel.k)} sil={sel.cosine_silhouette_mean:.4f}')
    check(f'{P} candidate values finite',np.isfinite(cand[['cosine_silhouette_mean','seed_ari_min','min_cluster_share']]).all().all())
    obj=rd(f'{P}_cosine_objective').cosine_objective.to_numpy()
    check(f'{P} objective non-decreasing',(np.diff(obj)>=-1e-9).all(),f'{obj[0]:.4f}->{obj[-1]:.4f}')
    check(f'{P} objective final = sum assigned',abs(obj[-1]-A.assigned_cosine.sum())<1e-6 or abs(obj[-1]-A.assigned_cosine.mean())<1e-9,f'{obj[-1]:.6f} vs sum {A.assigned_cosine.sum():.6f}')
    Rp=rd(f'{P}_cosine_representatives')
    exp=A.reset_index().sort_values(['cosine_cluster','assigned_cosine'],ascending=[True,False]).groupby('cosine_cluster').head(3)
    check(f'{P} representatives = top3 per cluster',sorted(Rp.source_index)==sorted(exp.source_index))
    pr=rd(f'{P}_cosine_profiles').set_index('cosine_cluster')
    check(f'{P} profile sizes',(pr.n==A.cosine_cluster.value_counts().reindex(pr.index)).all())
# profile shares for T
Q=rd('citytour_features_and_quality').set_index('source_index')
A=rd('T_cosine_assignments').set_index('source_index'); pr=rd('T_cosine_profiles').set_index('cosine_cluster')
m=Q.loc[A.index].assign(c=A.cosine_cluster).groupby('c')[[f'share_{c}' for c in CATS]+['visit_candidate_count','category_coverage','night_flag']].mean()
check('T profile means',np.allclose(m.loc[pr.index].to_numpy(float),pr[m.columns].to_numpy(float),atol=1e-9))
# with_cosine_all tables
for P,f,n in [('G','G_places_with_cosine_all',3109),('T','T_citytours_with_cosine_all',280)]:
    W=rd(f); A=rd(f'{P}_cosine_assignments').set_index('source_index')
    check(f'{P} with_cosine_all rows',len(W)==n,str(len(W)))
    got=W['cosine_cosine_cluster'].dropna(); check(f'{P} with_cosine_all assigned count',len(got)==len(A),f'{len(got)}')
    idx=W.index[W['cosine_cosine_cluster'].notna()]
    check(f'{P} with_cosine_all values match',np.allclose(W.loc[idx,'cosine_assigned_cosine'].to_numpy(float),A.loc[idx,'assigned_cosine'].to_numpy(float)) and (W.loc[idx,'cosine_cosine_cluster'].to_numpy()==A.loc[idx,'cosine_cluster'].to_numpy()).all())
# direct-preference course rankings
def rank(q,courses):
    sh=courses[[f'share_{c}' for c in CATS]].to_numpy(float); nq=q/np.linalg.norm(q); nr=np.linalg.norm(sh,axis=1)
    contrib=nq[None,:]*(sh/nr[:,None]); cos=np.clip(contrib.sum(1),0,1); cov=sh.sum(1)
    return cos,cov,100*contrib*cov[:,None]
Tas=rd('T_cosine_assignments').set_index('source_index').cosine_cluster
elig=Q[Q.cluster_eligible.astype(bool)]
RK=rd('cosine_course_rankings_all'); INP=rd('cosine_survey_inputs_used')
for _,r in INP.iterrows():
    sub=RK[RK.respondent_id==r.respondent_id].set_index('course_id'); q=np.array([r[f'q_{c}'] for c in CATS],float)
    cc=elig.set_index('course_id'); cc=cc.loc[sub.index]
    cos,cov,con=rank(q,cc)
    check(f'rankings {r.respondent_id} rows',len(sub)==len(elig),str(len(sub)))
    check(f'rankings {r.respondent_id} cosine',np.allclose(sub.cosine_similarity,cos,atol=1e-9) and np.allclose(sub.cosine_fit_score,100*cos) and np.allclose(sub.coverage_factor,cov) and np.allclose(sub.coverage_adjusted_score,100*cos*cov))
    check(f'rankings {r.respondent_id} contributions',np.allclose(sub[[f'contribution_{c}_points' for c in CATS]].to_numpy(),con,atol=1e-9) and np.allclose(sub[[f'contribution_{c}_points' for c in CATS]].sum(1),sub.coverage_adjusted_score))
    s2=sub.reset_index().sort_values('display_order')
    key=s2.coverage_adjusted_score.round(9); rk=key.rank(method='min',ascending=False).astype(int).to_numpy()
    tie_ok=all(g.course_id.is_monotonic_increasing for _,g in s2.assign(k=key,c=s2.cosine_similarity.round(12),v=s2.coverage_factor.round(12)).groupby(['k','c','v']))
    check(f'rankings {r.respondent_id} order',(np.diff(key)<=0).all() and (s2.score_rank.to_numpy()==rk).all() and tie_ok,f'ties by course_id {tie_ok}')
    check(f'rankings {r.respondent_id} TC label',(sub.cosine_cluster==Tas.reindex(cc.index.map(dict(zip(elig.course_id,elig.index)))).to_numpy()).all())
top=rd('cosine_course_rankings_top10'); check('top10 = display_order<=10',top.reset_index(drop=True).equals(RK[RK.display_order<=10].reset_index(drop=True)))
st=rd('cosine_survey_status'); check('survey status counts',all(st.n_candidates==len(elig)),st.to_dict('records').__str__()[:120])
# session results
SA=pd.read_csv('session_results/cosine_all_courses.csv',encoding='utf-8-sig').sort_values('display_order'); cs=json.load(open('examples/full_session.json',encoding='utf-8'))['cosineSurvey']
q=np.array([cs[f'q_{c}'] for c in CATS],float); cc=elig.set_index('course_id').loc[SA.course_id]; cos,cov,con=rank(q,cc)
check('session cosine/scores',np.allclose(SA.cosine_similarity,cos,atol=1e-9) and np.allclose(SA.coverage_adjusted_score,100*cos*cov,atol=1e-7))
key=SA.coverage_adjusted_score.round(9)
check('session order and ties',(np.diff(key)<=0).all() and (SA.score_rank.to_numpy()==key.rank(method='min',ascending=False).astype(int).to_numpy()).all()
      and all(g.course_id.is_monotonic_increasing for _,g in SA.assign(k=key,c=SA.cosine_similarity.round(12),v=SA.coverage_factor.round(12)).groupby(['k','c','v'])))
T5=pd.read_csv('session_results/cosine_distinct_region_top5.csv',encoding='utf-8-sig')
check('session top5 = first course per region',list(T5.course_id)==list(SA.drop_duplicates('region').head(5).course_id))
sys.path.insert(0,'reference_calc'); import recommend_reference as rr
E=pd.read_csv('reference_calc/eligible_courses.csv',encoding='utf-8-sig').set_index('analysis_course_id')
dc=pd.read_csv('reference_calc/demo_courses.csv',encoding='utf-8-sig'); u=np.array(json.load(open('reference_calc/demo_result.json',encoding='utf-8'))['preference_vector'])
sh=E.loc[dc.course_id,[f'analysis_share_{c}' for c in CATS]].to_numpy(float); cv=E.loc[dc.course_id,'analysis_category_coverage'].to_numpy(float)
cz=(u/np.linalg.norm(u))@(sh/np.linalg.norm(sh,axis=1)[:,None]).T
check('reference demo cosine/fit',np.allclose(dc.cosine_similarity,cz,atol=1e-9) and np.allclose(dc.category_fit_score,100*cz*cv,atol=1e-7))
check('reference demo adjusted = contributions + bonus',np.allclose(dc.adjusted_score,[sum(eval(a))+sum(eval(b).values()) for a,b in zip(dc.contributions,dc.bonus_points)]))
tm=pd.read_csv('reference_calc/type_course_matching.csv',encoding='utf-8-sig')
for t,g in tm.groupby('type'):
    u=np.array(rr.normalize(rr.CFG['profiles'][t])); sh=E.loc[g.course_id,[f'analysis_share_{c}' for c in CATS]].to_numpy(float); cv=E.loc[g.course_id,'analysis_category_coverage'].to_numpy(float)
    cz=(u/np.linalg.norm(u))@(sh/np.linalg.norm(sh,axis=1)[:,None]).T
    check(f'type matching {t}',np.allclose(g.cosine_similarity,cz,atol=1e-6) and np.allclose(g.category_fit_score,100*cz*cv,atol=1e-5) and (np.diff(g.sort_values('rank').category_fit_score)<=1e-9).all())
pathlib.Path('verification/cosine_csv_audit.json').write_text(json.dumps({'run':RUN.name,'passed':len(ok),'issues':issues,'checks':ok},ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
print(RUN.name,len(ok),'ok;',len(issues),'issues'); [print(' ISSUE',i) for i in issues]
sys.exit(1 if issues else 0)
