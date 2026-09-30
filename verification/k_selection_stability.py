"""군집 수(k) 선택의 안정성 점검.

analysis/run_analysis.py와 같은 후보 탐색(PCA KMeans · 구면 코사인, k=2~10, 시드 42/7/19, 초기화 20회,
시드 간 ARI 0.80 · 최소 군집 비율 0.02 조건, 실루엣은 1,200행 표본)을 전체 행과 90% 부분표본에 반복해,
어느 k가 얼마나 자주 선택되는지 센다. 결과는 verification/k_selection_stability.json에 기록했다.

사용: python verification/k_selection_stability.py <tables>/G_features.csv 20 0.9 out.json
"""
import ast,sys,json,itertools,numpy as np,pandas as pd
from multiprocessing import Pool
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score,adjusted_rand_score,pairwise_distances
from threadpoolctl import threadpool_limits
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
src=(ROOT/'analysis/run_analysis.py').read_text(encoding='utf-8')
mod=ast.parse(src)
fn=[n for n in mod.body if isinstance(n,ast.FunctionDef) and n.name=='spherical_kmeans'][0]
exec(compile(ast.Module([fn],[]),'sk','exec'))
SEEDS=[42,7,19];N_INIT=20;SAMPLE=1200;MIN_ARI=.8;MIN_SHARE=.02
def evaluate(X,kmax=10):
    n=len(X)
    pca=PCA(svd_solver='full').fit(X);cum=np.cumsum(pca.explained_variance_ratio_)
    Z=pca.transform(X)[:,:min(len(cum),int(np.searchsorted(cum,.95)+1))]
    nr=np.linalg.norm(X,axis=1);ok=nr>1e-12;U=X[ok]/nr[ok,None]
    samp=np.sort(np.random.default_rng(42).choice(n,min(n,SAMPLE),replace=False))
    De=pairwise_distances(X[samp]);np.fill_diagonal(De,0)
    su=np.sort(np.random.default_rng(42).choice(len(U),min(len(U),SAMPLE),replace=False))
    Dc=np.clip(1-U[su]@U[su].T,0,2);np.fill_diagonal(Dc,0)
    out=[]
    for k in range(2,kmax+1):
        for mode in ['pca','cos']:
            labs=[];sils=[];shares=[]
            for s in SEEDS:
                if mode=='pca':
                    l=KMeans(n_clusters=k,n_init=N_INIT,random_state=s,algorithm='lloyd').fit(Z).labels_;q=l[samp];D=De
                else:
                    l=spherical_kmeans(U,k,s,N_INIT,200)['labels'];q=l[su];D=Dc
                labs.append(l);shares.append(np.bincount(l,minlength=k).min()/len(l))
                sils.append(silhouette_score(D,q,metric='precomputed') if 1<len(np.unique(q))<len(q) else np.nan)
            ari=min(adjusted_rand_score(a,b) for a,b in itertools.combinations(labs,2))
            out.append(dict(mode=mode,k=k,sil=float(np.nanmean(sils)),ari=ari,share=min(shares),ok=bool(ari>=MIN_ARI and min(shares)>=MIN_SHARE)))
    return pd.DataFrame(out)
def choose(df,mode,tol=None):
    p=df[(df['mode']==mode)&df.ok]
    if p.empty:p=df[df['mode']==mode]
    if tol is None:return int(p.sort_values(['sil','k'],ascending=[False,True]).iloc[0].k)
    return int(p[p.sil>=p.sil.max()-tol].k.min())
def rep(args):
    X,b,frac=args
    with threadpool_limits(1):
        idx=np.sort(np.random.default_rng(1000+b).choice(len(X),int(round(frac*len(X))),replace=False)) if b>=0 else np.arange(len(X))
        df=evaluate(X[idx])
    return b,{m:{'cur':choose(df,m),'tol01':choose(df,m,.01),'tol02':choose(df,m,.02)} for m in ['pca','cos']},df.to_dict('records')
if __name__=='__main__':
    path,B,frac,out=sys.argv[1],int(sys.argv[2]),float(sys.argv[3]),sys.argv[4]
    F=pd.read_csv(path);X=F.drop(columns=[c for c in F.columns if c=='source_index']).to_numpy(float)
    with Pool(4) as p: res=p.map(rep,[(X,b,frac) for b in range(-1,B)])
    json.dump([{'b':b,'choice':c,'table':t} for b,c,t in res],open(out,'w'))
    full=[r for r in res if r[0]==-1][0]
    print('FULL',full[1]); print(pd.DataFrame(full[2]).pivot(index='k',columns='mode',values='sil').round(4).to_string())
    for m in ['pca','cos']:
        for rule in ['cur','tol01','tol02']:
            ks=[c[m][rule] for b,c,t in res if b>=0]
            print(m,rule,dict(sorted(pd.Series(ks).value_counts().items())))
