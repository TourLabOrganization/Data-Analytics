from pathlib import Path
import json
import numpy as np,pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score,adjusted_rand_score
from threadpoolctl import threadpool_limits
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parent

def run():
 d=pd.read_csv(ROOT/'data/region_demographic_profiles.csv');ac=['age_'+a for a in ['10대 미만','10대','20대','30대','40대','50대','60대','70대']];sc=['sex_male','sex_female']
 age=d[ac].div(d.age_sum,axis=0).to_numpy();sex=d[sc].div(d.sex_sum,axis=0).to_numpy()
 X=np.c_[np.sqrt(.75)*np.sqrt(age),np.sqrt(.25)*np.sqrt(sex)];models={};rows=[]
 with threadpool_limits(limits=1):
  for mode in ['raw','pca95']:
   Z=X if mode=='raw' else PCA(n_components=.95,svd_solver='full').fit_transform(X)
   for k in range(2,7):
    ms=[KMeans(n_clusters=k,n_init=50,random_state=s).fit(Z) for s in [0,7,42]];v=np.mean([silhouette_score(X,m.labels_) for m in ms]);ari=min(adjusted_rand_score(ms[0].labels_,m.labels_) for m in ms[1:]);size=np.bincount(ms[0].labels_).min()
    rows.append({'mode':mode,'k':k,'components':Z.shape[1],'silhouette':v,'min_seed_ari':ari,'min_cluster_size':size});models[(mode,k)]=ms[0]
 met=pd.DataFrame(rows);valid=met[(met.min_seed_ari>=.8)&(met.min_cluster_size>=8)]
 if valid.empty:raise RuntimeError('No exploratory candidate meets gates')
 best=valid.sort_values(['silhouette','k'],ascending=[False,True]).iloc[0];m=models[(best['mode'],int(best.k))];d['regional_cluster']=['R%02d'%(x+1) for x in m.labels_]
 pca=PCA().fit(X);pc=pca.transform(X);d['PC1']=pc[:,0];d['PC2']=pc[:,1]
 with threadpool_limits(limits=1):alt=KMeans(n_clusters=int(best.k),n_init=50,random_state=0).fit(np.sqrt(age))
 summary={'n_regions':len(d),'input_columns':10,'block_weights':{'age':.75,'sex':.25},'selected':best.to_dict(),'pca_two_axis_variance':float(pca.explained_variance_ratio_[:2].sum()),'age_only_sensitivity_ari':float(adjusted_rand_score(m.labels_,alt.labels_)),'cluster_sizes':d.regional_cluster.value_counts().sort_index().to_dict(),'scope':'90 selected regions only; no inference to national visitor personas'}
 d.to_csv(ROOT/'results/regional_cluster_assignments.csv',index=False,encoding='utf-8-sig');met.to_csv(ROOT/'results/regional_model_comparison.csv',index=False,encoding='utf-8-sig')
 profiles=d.groupby('regional_cluster')[ac+sc].mean();profiles['count']=d.groupby('regional_cluster').size();profiles.to_csv(ROOT/'results/regional_cluster_profiles.csv',encoding='utf-8-sig')
 (ROOT/'results/regional_cluster_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 full=pd.read_csv(ROOT/'results/nationwide_places_demographics.csv');full=full.drop(columns='regional_cluster',errors='ignore').merge(d[['source_region','regional_cluster']],left_on='demographic_source_region',right_on='source_region',how='left').drop(columns='source_region');full.to_csv(ROOT/'results/nationwide_places_demographics.csv',index=False,encoding='utf-8-sig')
 for candidate in ['C:/Windows/Fonts/malgun.ttf','/usr/share/fonts/opentype/task-noto/NotoSansCJKkr-Regular.otf','/usr/local/share/fonts/task-droid/DroidSansFallback.ttf']:
  if Path(candidate).exists():font_manager.fontManager.addfont(candidate)
 available={f.name for f in font_manager.fontManager.ttflist}
 plt.rcParams['font.family']=next((f for f in ['Noto Sans CJK KR','Malgun Gothic','AppleGothic','NanumGothic','Droid Sans Fallback'] if f in available),'DejaVu Sans')
 plt.rcParams.update({'axes.unicode_minus':False,'font.size':11,'axes.spines.top':False,'axes.spines.right':False})
 colors=['#B7396B','#72509B','#75808D','#DA8FAD','#383D45','#C496C4']
 def save(fig,name,note):
  fig.tight_layout(rect=(0,.08,1,1));fig.text(.02,.015,note,fontsize=9,color='#636A74');fig.savefig(ROOT/'plots'/name,dpi=300,bbox_inches='tight');plt.close(fig)
 fig,ax=plt.subplots(figsize=(10,6.4))
 for (c,t),color in zip(d.groupby('regional_cluster'),colors):ax.scatter(t.PC1,t.PC2,label=f'{c} · {len(t)}지역',c=color,s=38,alpha=.8)
 for _,r in d[d.sigungu.isin(['거제시','군산시','신안군','화천군','평택시'])].iterrows():ax.annotate(r.sigungu,(r.PC1,r.PC2),xytext=(5,5),textcoords='offset points',fontsize=9)
 ax.set(xlabel=f'PC1 ({pca.explained_variance_ratio_[0]*100:.1f}%)',ylabel=f'PC2 ({pca.explained_variance_ratio_[1]*100:.1f}%)',title='지역별 연령 구성과 성별 구성의 탐색 군집');ax.legend(frameon=False);ax.grid(alpha=.12)
 save(fig,'01_regional_pca.png','정상 자료90개 지역 · 남성 구성비 상위 목록에 선택된 자료 | R은 지역 군집이며 개인 유형이 아님')
 fig,axs=plt.subplots(1,2,figsize=(12.5,4.9),gridspec_kw={'width_ratios':[4,1.5]})
 for a,cols,names in [(axs[0],ac,['10대 미만','10대','20대','30대','40대','50대','60대','70대']),(axs[1],sc,['남성','여성'])]:
  arr=profiles[cols].to_numpy();a.imshow(arr,cmap='RdPu',aspect='auto',vmin=0,vmax=30 if len(cols)==8 else 70);a.set_xticks(range(len(cols)),names,rotation=25);a.set_yticks(range(len(profiles)),[f'{x} ({int(profiles.loc[x,"count"])}지역)' for x in profiles.index]);
  for i in range(arr.shape[0]):
   for j in range(arr.shape[1]):a.text(j,i,f'{arr[i,j]:.1f}',ha='center',va='center',fontsize=10,color='white' if arr[i,j]>(20 if len(cols)==8 else 48) else '#222')
 axs[0].set_title('군집별 평균 연령 구성비 (%)',loc='left');axs[1].set_title('성별 구성비 (%)')
 save(fig,'02_regional_profiles.png','성별×연령 교차비율이 아닌 각각의 구성비 | 표본 수가 없어 신뢰구간·전국 가중평균을 추정하지 않음')
 fig,ax=plt.subplots(figsize=(10,4.7));labels=['원자료 히트맵 지역','상세표 고유 지역','품질검사 통과 지역','앱 지역 잠정 연결'];values=[230,94,90,54];ax.barh(labels,values,color=['#CCD0D6','#A6ADB7','#B7396B','#72509B']);ax.invert_yaxis();ax.set(xlabel='지역 수',title='자료 확보와 앱 연결 범위',xlim=(0,260))
 for i,v in enumerate(values):ax.text(v+3,i,str(v),va='center')
 save(fig,'03_regional_coverage.png','히트맵은 남성·전체연령 선택값 | 상세표 미포함136지역과 값이 충돌한4지역은 신규 지역 보정 제외')
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':run()
