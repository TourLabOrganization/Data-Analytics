from pathlib import Path
import json
import numpy as np,pandas as pd
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score,adjusted_rand_score
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parent

def run(root=ROOT):
 root=Path(root);out=root/'results';out.mkdir(exist_ok=True)
 matrix=pd.read_csv(root/'data/age_rank_exposure_matrix.csv',index_col=0)
 active=matrix.sum(axis=1)>0;X=matrix.loc[active].to_numpy();models={};rows=[]
 with threadpool_limits(limits=1):
  for mode,threshold in [('raw',None),('pca95',.95)]:
   pca=PCA(n_components=threshold,svd_solver='full') if threshold else None
   Z=pca.fit_transform(X) if pca else X
   for k in range(2,7):
    runs=[KMeans(n_clusters=k,n_init=50,random_state=s).fit(Z) for s in [0,7,42]]
    vals=[silhouette_score(X,m.labels_) for m in runs]
    ari=min(adjusted_rand_score(runs[0].labels_,m.labels_) for m in runs[1:])
    size=np.bincount(runs[0].labels_,minlength=k)
    rows.append({'mode':mode,'k':k,'components':Z.shape[1],'silhouette_original_mean':float(np.mean(vals)),'seed_ari_min':ari,'min_cluster_size':int(size.min())})
    models[(mode,k)]=(pca,runs[0],Z)
 met=pd.DataFrame(rows);valid=met[(met.seed_ari_min>=.8)&(met.min_cluster_size>=5)]
 if valid.empty:raise RuntimeError('No age cluster passes exploratory gates')
 best=valid.sort_values(['silhouette_original_mean','k'],ascending=[False,True]).iloc[0];pca,km,Z=models[(best['mode'],int(best.k))]
 result=matrix.copy();result['age_cluster']=None;result.loc[active,'age_cluster']=['A%02d'%(i+1) for i in km.labels_]
 meta=pd.read_csv(root/'data/datalab_age_popularity_long.csv').drop_duplicates('datalab_id')[['datalab_id','datalab_name','category_raw']]
 result=result.reset_index().merge(meta,on='datalab_id');result.to_csv(out/'age_cluster_assignments.csv',index=False,encoding='utf-8-sig')
 met.to_csv(out/'age_model_comparison.csv',index=False,encoding='utf-8-sig')
 cols=['20','30','40','50','60plus'];profiles=result.groupby('age_cluster')[cols].mean();profiles['count']=result.groupby('age_cluster').size();profiles.to_csv(out/'age_cluster_profiles.csv',encoding='utf-8-sig')
 fullp=PCA(svd_solver='full').fit(X);pc=fullp.transform(X);r=result.set_index('datalab_id').loc[matrix.index[active]].reset_index();r['PC1']=pc[:,0];r['PC2']=pc[:,1];r.to_csv(out/'age_pca_scores.csv',index=False,encoding='utf-8-sig')
 pd.DataFrame({'PC':range(1,6),'variance':fullp.explained_variance_ratio_,'cumulative':np.cumsum(fullp.explained_variance_ratio_)}).to_csv(out/'age_pca_variance.csv',index=False,encoding='utf-8-sig')
 # Sensitivity to replacing tied rank exposure with displayed-percent / within-age maximum.
 long=pd.read_csv(root/'data/datalab_age_popularity_long.csv',dtype={'age_band':str});Y=long[long.age_band!='all'].pivot(index='datalab_id',columns='age_band',values='within_age_relative_intensity').reindex(index=matrix.index[active],columns=cols).fillna(0).to_numpy()
 with threadpool_limits(limits=1):alt=KMeans(n_clusters=int(best.k),n_init=50,random_state=0).fit(Y)
 sensitivity=float(adjusted_rand_score(km.labels_,alt.labels_))
 summary={'rows':len(matrix),'fit_rows':len(X),'excluded_no_age_rows':int((~active).sum()),'selected':best.to_dict(),'ratio_feature_sensitivity_ari':sensitivity,'pca_first2_variance':float(fullp.explained_variance_ratio_[:2].sum()),'semantics':'top30_listing_exposure_not_visits_or_personas'}
 (out/'age_cluster_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 full=pd.read_csv(root/'data/nationwide_places_with_age.csv');full=full.merge(result[['datalab_id','age_cluster']],on='datalab_id',how='left')
 full.to_csv(out/'nationwide_places_age_clustered.csv',index=False,encoding='utf-8-sig')
 print(json.dumps(summary,ensure_ascii=False,indent=2));return summary
if __name__=='__main__':run()
