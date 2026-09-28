# -*- coding: utf-8 -*-
"""노트북과 같은 분석을 순서대로 실행합니다."""
import os
from pathlib import Path
os.environ.setdefault("MPLBACKEND", "Agg")
os.chdir(Path(__file__).resolve().parent)
from pathlib import Path
PLACES_CSV = Path("tour-places.csv")  # 여행장소 파일 또는 None
CITYTOUR_CSV = Path("citytour.csv")  # 시티투어 파일 또는 None
OUTPUT_ROOT = Path("outputs_cosine")
AUTO_INSTALL = False
PCA_TARGET = 0.95
K_MAX = 10
SEEDS = [42, 7, 19]
N_INIT = 20
MIN_CLUSTER_SHARE = 0.02
MIN_SEED_ARI = 0.80
SILHOUETTE_SAMPLE = 1200
MIN_CITY_CATEGORY_COVERAGE = 0.50
PLACE_WEIGHTS = {"category": 0.60, "stay": 0.30, "unesco_mark": 0.10}
CITY_WEIGHTS = {"category": 0.75, "stop_count": 0.15, "night": 0.10}

# 지역 지출 비율 CSV가 있는 폴더 또는 ZIP
SPENDING_INPUT = Path("spending_csv")
REGRESSION_ALPHAS = [0.1, 1.0, 10.0, 100.0, 1000.0]
MIN_CATALOG_PLACES = 3

MARINE_INPUT = Path("marine_csv")  # 해양 기본 CSV 3개 + 선택 검색순위 CSV 폴더 또는 다운로드 ZIP, 제외 시 None
MARINE_RATIO_TOLERANCE_PP = 0.01
MARINE_MEAN_TOLERANCE = 1.0  # 정수 반올림 평균 비교 허용차

# 코사인 확장 설정
COSINE_N_INIT = 20
COSINE_MAX_ITER = 200
SURVEY_CSV = Path("survey_responses.csv")  # 없으면 명시적 가상 설문 시연


import importlib.util, subprocess, sys
required = {"numpy":"numpy>=1.26,<3", "pandas":"pandas>=2.2,<4",
            "matplotlib":"matplotlib>=3.8,<4", "sklearn":"scikit-learn>=1.5,<2",
            "joblib":"joblib>=1.3,<2", "threadpoolctl":"threadpoolctl>=3,<4"}
missing = [package for module, package in required.items() if importlib.util.find_spec(module) is None]
if missing:
    if not AUTO_INSTALL:
        raise RuntimeError("현재 커널에 설치할 패키지: " + " ".join(missing))
    subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])

import os, io, re, json, hashlib, unicodedata, platform, itertools, warnings
from datetime import datetime
from collections import defaultdict, Counter
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, adjusted_rand_score, pairwise_distances
from threadpoolctl import threadpool_limits
import sklearn, joblib

RUN_DIR = OUTPUT_ROOT / datetime.now().strftime("run_%Y%m%d_%H%M%S_%f")
TABLES, PLOTS, MODELS = [RUN_DIR / name for name in ("tables", "plots", "models")]
for folder in (TABLES, PLOTS, MODELS): folder.mkdir(parents=True, exist_ok=True)
for candidate in ["C:/Windows/Fonts/malgun.ttf", "/usr/share/fonts/opentype/task-noto/NotoSansCJKkr-Regular.otf", "/usr/local/share/fonts/task-droid/DroidSansFallback.ttf"]:
    if Path(candidate).exists(): font_manager.fontManager.addfont(candidate)
available_fonts = {f.name for f in font_manager.fontManager.ttflist}
font = next((f for f in ["Malgun Gothic", "AppleGothic", "Noto Sans CJK KR", "NanumGothic", "Droid Sans Fallback"] if f in available_fonts), "DejaVu Sans")
plt.rcParams.update({"font.family":font, "axes.unicode_minus":False, "font.size":10,
                     "axes.spines.top":False, "axes.spines.right":False,
                     "figure.facecolor":"white", "axes.titleweight":"bold"})
PALETTE = ["#D8A900", "#3475B5", "#C9495B", "#7B60A3", "#B97991", "#758B7C", "#899BB0", "#9A6C4C", "#D9A6BA", "#50555A"]
CATEGORIES = ["herit", "heal", "activity", "food", "sea"]
CAT_LABELS = {"herit":"Heritage", "heal":"Nature", "activity":"Activity", "food":"Food", "sea":"Coast", "stay":"Lodging"}
INPUT_META, PLOT_FILES, RUN_SUMMARY = {}, [], {}

def show_table(df, n=12):
    try: display(df.head(n))
    except NameError: print(df.head(n).to_string(index=False))

def save_csv(df, name, index=False):
    path = TABLES / (name + ".csv")
    df.to_csv(path, index=index, encoding="utf-8-sig")
    return path

def finish(fig, name):
    fig.tight_layout()
    path = PLOTS / (name + ".png")
    # Finish the image in memory before writing, including on synced folders.
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=300, bbox_inches="tight", facecolor="white")
    path.write_bytes(buffer.getvalue())
    PLOT_FILES.append(path)
    plt.show()
    plt.close(fig)

def read_csv_input(path, kind):
    if path is None or not Path(path).is_file():
        print(f"{kind}: 파일 없음, 이 입력 분석을 건너뜁니다. 설정값={path}")
        return None
    path = Path(path)
    for encoding in ["utf-8-sig", "cp949", "utf-16"]:
        try:
            frame = pd.read_csv(path, encoding=encoding, dtype=str, keep_default_na=False)
            frame.columns = [c.strip().lstrip("\ufeff") for c in frame.columns]
            INPUT_META[kind] = {"file":str(path), "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                                "encoding":encoding, "rows":len(frame), "columns":frame.columns.tolist()}
            print(f"{kind}: {len(frame):,}행 × {len(frame.columns)}열 / {encoding}")
            return frame
        except UnicodeError:
            continue
    raise ValueError(f"인코딩을 읽을 수 없습니다. UTF-8 CSV로 다시 저장하세요: {path}")

def standard_columns(df, mapping, required_columns):
    result = pd.DataFrame(index=df.index)
    for target, aliases in mapping.items():
        source = next((c for c in aliases if c in df.columns), None)
        if source is not None: result[target] = df[source].astype(str).str.strip()
        elif target in required_columns: raise ValueError(f"필수 칼럼 누락: {target}; 허용 이름={aliases}")
        else: result[target] = ""
    return result

def robust_log(values):
    z = np.log1p(np.asarray(values, dtype=float))
    median = float(np.median(z))
    q25, q75 = np.quantile(z, [0.25, 0.75])
    scale = float(q75-q25)
    if scale < 1e-12: scale = float(np.std(z)) or 1.0
    return (z-median)/scale, {"log1p_median":median, "scale":scale, "fallback":"std_then_1_if_IQR_zero"}

places_raw = read_csv_input(PLACES_CSV, "places")
cities_raw = read_csv_input(CITYTOUR_CSV, "citytour")
if places_raw is None and cities_raw is None and (SPENDING_INPUT is None or not Path(SPENDING_INPUT).exists()) and (MARINE_INPUT is None or not Path(MARINE_INPUT).exists()):
    raise FileNotFoundError("장소·코스 CSV, 지출 입력, 해양 입력 중 하나 이상을 첫 설정 셀에서 지정하세요.")
print("Python", platform.python_version(), "| scikit-learn", sklearn.__version__)
print("저장 폴더:", RUN_DIR.resolve())


places, place_model, place_features, place_preprocess = None, None, None, None
if places_raw is not None:
    mapping = {"place_id":["id","place_id"], "region":["지역","region_name","region"],
               "name":["이름(한국어)","place_name","name"], "category":["카테고리","category"],
               "base_minutes":["추천 체류(분)","base_minutes"], "lat":["위도","lat"], "lon":["경도","lon"],
               "unesco_raw":["유네스코","badge_unesco"]}
    places = standard_columns(places_raw, mapping, {"place_id","region","name","category","base_minutes"})
    if places.place_id.eq("").any() or places.place_id.duplicated().any():
        save_csv(places[places.place_id.eq("") | places.place_id.duplicated(False)], "place_id_errors")
        raise ValueError("장소 ID가 비었거나 중복입니다. place_id_errors.csv를 확인하세요.")
    for col in ["base_minutes","lat","lon"]:
        places[col] = pd.to_numeric(places[col], errors="coerce").replace([np.inf,-np.inf],np.nan)
    places["unesco_mark"] = places.unesco_raw.str.upper().isin(["Y","YES","1","TRUE"]).astype(int)
    places["quality_reason"] = ""
    places.loc[places.category.eq("stay"),"quality_reason"] = "LODGING_EXCLUDED"
    places.loc[~places.category.isin(CATEGORIES+["stay"]),"quality_reason"] = "UNKNOWN_CATEGORY"
    missing_time = ~places.base_minutes.gt(0)
    places["base_time_missing_or_invalid"] = missing_time
    places.loc[missing_time & places.quality_reason.eq(""),"quality_reason"] = "BASE_TIME_MISSING_OR_NONPOSITIVE"
    places["cluster_eligible"] = places.quality_reason.eq("")
    places["coordinate_valid"] = places.lat.between(-90,90) & places.lon.between(-180,180)
    eligible_places = places.loc[places.cluster_eligible].copy()
    save_csv(places, "place_cleaned_all")
    save_csv(places[~places.cluster_eligible], "place_excluded")
    audit = pd.DataFrame({"item":["All rows","Eligible","Excluded","Invalid base time","Invalid/missing coordinates"],
                          "count":[len(places),len(eligible_places),int((~places.cluster_eligible).sum()),int(missing_time.sum()),int((~places.coordinate_valid).sum())]})
    show_table(audit); save_csv(audit,"place_quality_summary")
    if len(eligible_places) < 4: raise ValueError("유효한 비숙박 장소가 4행 이상 필요합니다.")
    scaled_stay, stay_parameters = robust_log(eligible_places.base_minutes)
    place_features = pd.DataFrame({f"cat_{c}":eligible_places.category.eq(c).astype(float)*np.sqrt(PLACE_WEIGHTS["category"]/2) for c in CATEGORIES}, index=eligible_places.index)
    place_features["log_stay_robust"] = scaled_stay*np.sqrt(PLACE_WEIGHTS["stay"])
    place_features["unesco_mark"] = eligible_places.unesco_mark*np.sqrt(PLACE_WEIGHTS["unesco_mark"])
    place_preprocess = {"weights":PLACE_WEIGHTS, "stay":stay_parameters, "unesco_rule":"marked 1; blank/unmarked 0, not verified absence", "categories":CATEGORIES}
    fig,ax=plt.subplots(figsize=(8,4))
    counts=places.category.value_counts();ax.bar([CAT_LABELS.get(c,c) for c in counts.index],counts.values,color="#9F718B")
    ax.set(title="Input places by category",ylabel="Number of records")
    for i,v in enumerate(counts.values): ax.text(i,v,str(v),ha="center",va="bottom")
    finish(fig,"01_place_categories")


def fit_cluster_pipeline(feature_frame, prefix, preprocess, k_max=None, min_cluster_share=None):
    k_max = K_MAX if k_max is None else k_max
    min_cluster_share = MIN_CLUSTER_SHARE if min_cluster_share is None else min_cluster_share
    constant = feature_frame.columns[feature_frame.std(ddof=0).le(1e-12)].tolist()
    F = feature_frame.drop(columns=constant)
    X = F.to_numpy(float)
    if not np.isfinite(X).all() or X.shape[1] == 0: raise ValueError(f"{prefix}: 유효한 비상수 특성이 없습니다.")
    unique_n = len(np.unique(np.round(X,12),axis=0))
    max_k = min(k_max,len(X)-1,unique_n-1)
    if max_k < 2: raise ValueError(f"{prefix}: 서로 다른 특성 조합이 최소 3개 필요합니다.")
    pca = PCA(svd_solver="full",whiten=False).fit(X)
    all_pc = pca.transform(X)
    cumulative = np.cumsum(pca.explained_variance_ratio_)
    m = min(len(cumulative),int(np.searchsorted(cumulative,PCA_TARGET)+1))
    Z = all_pc[:,:m]
    sample = np.sort(np.random.default_rng(SEEDS[0]).choice(len(X), min(len(X),SILHOUETTE_SAMPLE), replace=False))
    with threadpool_limits(limits=2):
        distances = pairwise_distances(X[sample]); np.fill_diagonal(distances,0)
        rows=[]
        for mode,training in [("raw",X),("pca",Z)]:
            for k in range(2,max_k+1):
                labels_all=[];sils=[];min_shares=[];inertias=[]
                for seed in SEEDS:
                    model=KMeans(n_clusters=k,n_init=N_INIT,random_state=seed,algorithm="lloyd").fit(training)
                    labels=model.labels_;labels_all.append(labels)
                    sampled_labels=labels[sample]
                    sil=silhouette_score(distances,sampled_labels,metric="precomputed") if 1<len(np.unique(sampled_labels))<len(sample) else np.nan
                    sils.append(sil);min_shares.append(np.bincount(labels,minlength=k).min()/len(labels));inertias.append(model.inertia_)
                ari=min(adjusted_rand_score(a,b) for a,b in itertools.combinations(labels_all,2))
                rows.append({"mode":mode,"k":k,"components":training.shape[1],"silhouette_mean":float(np.nanmean(sils)),
                             "silhouette_sd":float(np.nanstd(sils)),"seed_ari_min":float(ari),"min_cluster_share":float(min(min_shares)),
                             "inertia_mean_in_training_space":float(np.mean(inertias))})
    comparison=pd.DataFrame(rows)
    comparison["passes_gates"]=(comparison.seed_ari_min>=MIN_SEED_ARI)&(comparison.min_cluster_share>=min_cluster_share)
    pool=comparison[comparison["mode"].eq("pca") & comparison.passes_gates]
    gates_passed=not pool.empty
    if pool.empty: pool=comparison[comparison["mode"].eq("pca")]
    selected=pool.sort_values(["silhouette_mean","k"],ascending=[False,True]).iloc[0]
    with threadpool_limits(limits=2):
        model=KMeans(n_clusters=int(selected.k),n_init=N_INIT,random_state=SEEDS[0],algorithm="lloyd").fit(Z)
    # A deterministic within-run numbering rule. Not semantic identities across datasets.
    order=sorted(range(int(selected.k)),key=lambda lab:tuple(np.mean(X[model.labels_==lab],axis=0).round(10)))
    label_map={lab:f"{prefix}{i+1:02d}" for i,lab in enumerate(order)}
    labels=np.array([label_map[lab] for lab in model.labels_])
    pcs=pd.DataFrame(all_pc,columns=[f"PC{i+1}" for i in range(all_pc.shape[1])],index=F.index)
    axes=pd.DataFrame(pca.components_.T,index=F.columns,columns=pcs.columns)
    variance=pd.DataFrame({"component":pcs.columns,"explained_variance_ratio":pca.explained_variance_ratio_,"cumulative":cumulative})
    save_csv(F.assign(source_index=F.index),f"{prefix}_features")
    save_csv(comparison,f"{prefix}_model_comparison")
    save_csv(axes.rename_axis("feature").reset_index(),f"{prefix}_pca_axes")
    save_csv(pd.DataFrame({"feature":F.columns,"mean":pca.mean_}),f"{prefix}_pca_input_means")
    save_csv(variance,f"{prefix}_pca_variance")
    save_csv(pcs.assign(source_index=pcs.index),f"{prefix}_pca_scores")
    summary={"rows":len(X),"features":F.columns.tolist(),"removed_constant_features":constant,"pca_components":m,
             "pca_retained_variance":float(cumulative[m-1]),"plot_2pc_variance":float(cumulative[min(1,len(cumulative)-1)]),
             "k":int(selected.k),"silhouette_mean":float(selected.silhouette_mean),"seed_ari_min":float(selected.seed_ari_min),
             "passes_gates":gates_passed,"silhouette_sample_size":len(sample),"numbering":"run-specific, no persona assignment"}
    bundle={"preprocess":preprocess,"features":F.columns.tolist(),"pca":pca,"components_used":m,"kmeans":model,"label_map":label_map,"summary":summary,"sklearn_version":sklearn.__version__}
    joblib.dump(bundle,MODELS/f"{prefix}_pca_kmeans.joblib")
    print(prefix,json.dumps(summary,ensure_ascii=False,indent=2))
    for axis in axes.columns[:2]:
        signed=axes[axis].sort_values()
        print(axis,"negative:",signed.head(2).round(4).to_dict(),"positive:",signed.tail(2).round(4).to_dict())
    dominant=axes.PC1.abs().idxmax()
    if abs(axes.loc[dominant,"PC1"])>=0.9:
        print(f"축 해석: PC1 계수의 절댓값이 가장 큰 변수는 {dominant}입니다. 단일 변수의 영향이 크므로 테마 성향이나 여행자 유형으로 바로 해석하지 마세요.")
    if int(selected.k)==max_k:
        print(f"군집 수 해석: k={max_k}는 이번 탐색의 상한입니다. 전역 최적 군집 수가 확정된 것은 아닙니다.")
    return {"F":F,"X":X,"Z":Z,"labels":labels,"pcs":pcs,"axes":axes,"variance":variance,"comparison":comparison,
            "model":model,"pca":pca,"summary":summary,"prefix":prefix}

def plot_diagnostics(result, start):
    prefix=result["prefix"];v=result["variance"];c=result["comparison"];s=result["summary"]
    fig,ax=plt.subplots(figsize=(8,4));axis=np.arange(1,len(v)+1)
    ax.bar(axis,v.explained_variance_ratio,color="#AD7B93",label="Individual")
    ax.plot(axis,v.cumulative,"o-",color="#6A4E85",label="Cumulative");ax.axhline(PCA_TARGET,color="#555",ls="--",label=f"Target {PCA_TARGET:.0%}")
    ax.set(xticks=axis,ylim=(0,1.06),xlabel="Principal component",ylabel="Explained variance ratio",title=f"{prefix}: PCA variance (retained {s['pca_components']} PCs)");ax.legend(frameon=False)
    finish(fig,f"{start:02d}_{prefix}_pca_variance")
    fig,axs=plt.subplots(1,2,figsize=(11,4))
    for mode,color in [("raw","#888888"),("pca","#A94B74")]:
        q=c[c["mode"].eq(mode)];axs[0].errorbar(q.k,q.silhouette_mean,yerr=q.silhouette_sd,marker="o",label=mode,color=color)
        axs[1].plot(q.k,q.seed_ari_min,"o-",label=mode,color=color)
    axs[0].set(title="Silhouette on common feature distances",xlabel="k",ylabel="Mean silhouette");axs[0].axvline(s["k"],ls=":",color="#333")
    axs[1].axhline(MIN_SEED_ARI,ls="--",color="#555");axs[1].set(title="Stability across seeds",xlabel="k",ylabel="Minimum ARI",ylim=(-.05,1.05))
    for ax in axs:ax.legend(frameon=False);ax.set_xticks(sorted(c.k.unique()))
    finish(fig,f"{start+1:02d}_{prefix}_model_comparison")
    xy=result["pcs"].iloc[:,:2].copy()
    if xy.shape[1]==1: xy["PC2"]=0.0
    xy.columns=["PC1","PC2"];xy["cluster"]=result["labels"]
    # Aggregate exactly coincident points. No artificial coordinate jitter.
    xy[["PC1","PC2"]]=xy[["PC1","PC2"]].round(8)
    grouped=xy.groupby(["PC1","PC2","cluster"]).size().reset_index(name="count")
    fig,ax=plt.subplots(figsize=(9,6))
    for i,label in enumerate(sorted(xy.cluster.unique())):
        q=grouped[grouped.cluster.eq(label)];ax.scatter(q.PC1,q.PC2,s=18+q["count"]*2,alpha=.72,color=PALETTE[i%len(PALETTE)],label=label,edgecolor="white",linewidth=.35)
    vr=result["pca"].explained_variance_ratio_
    ax.set(xlabel=f"PC1 ({vr[0]:.1%})",ylabel=f"PC2 ({vr[1] if len(vr)>1 else 0:.1%})",
           title=f"{prefix}: PCA projection, k={s['k']} (model uses {s['pca_components']} PCs)")
    ax.legend(bbox_to_anchor=(1.02,1),loc="upper left",frameon=False,title="Cluster");ax.text(0,-.15,"Marker area = 18 + 2 × coincident records; no jitter",transform=ax.transAxes,fontsize=9,color="#555")
    finish(fig,f"{start+2:02d}_{prefix}_pca_clusters")
    axes=result["axes"].iloc[:,:min(5,len(result["axes"].columns))]
    fig,ax=plt.subplots(figsize=(8,5));im=ax.imshow(axes,cmap="RdBu_r",vmin=-1,vmax=1,aspect="auto")
    ax.set(xticks=np.arange(axes.shape[1]),xticklabels=axes.columns,yticks=np.arange(len(axes)),yticklabels=axes.index,title=f"{prefix}: PCA axis coefficients")
    for i in range(len(axes)):
        for j in range(axes.shape[1]):ax.text(j,i,f"{axes.iloc[i,j]:.2f}",ha="center",va="center",color="white" if abs(axes.iloc[i,j])>.6 else "black",fontsize=9)
    fig.colorbar(im,ax=ax,label="Axis coefficient");finish(fig,f"{start+3:02d}_{prefix}_pca_axes")


if places is not None:
    place_model=fit_cluster_pipeline(place_features,"G",place_preprocess)
    RUN_SUMMARY["places"]=place_model["summary"]
    eligible_places["G_cluster"]=place_model["labels"]
    eligible_places=eligible_places.join(place_model["pcs"])
    places=places.join(eligible_places[["G_cluster","PC1","PC2"]] if "PC2" in eligible_places else eligible_places[["G_cluster","PC1"]])
    appended=places.add_prefix("analysis_")
    save_csv(pd.concat([places_raw,appended],axis=1),"G_place_assignments_all")
    plot_diagnostics(place_model,2)
    groups=eligible_places.groupby("G_cluster")
    profile=groups.agg(n=("place_id","size"),base_minutes_median=("base_minutes","median"),base_minutes_mean=("base_minutes","mean"),unesco_mark_rate=("unesco_mark","mean"))
    shares=pd.crosstab(eligible_places.G_cluster,eligible_places.category,normalize="index").reindex(columns=CATEGORIES,fill_value=0)
    save_csv(profile.join(shares).reset_index(),"G_cluster_profiles");show_table(profile.reset_index())
    fig,axs=plt.subplots(1,2,figsize=(11,4));colors=[PALETTE[i%len(PALETTE)] for i in range(len(profile))]
    axs[0].bar(profile.index,profile.n,color=colors);axs[0].set(title="Places in each cluster",ylabel="Records")
    axs[1].boxplot([groups.get_group(g).base_minutes.to_numpy() for g in profile.index],showfliers=True)
    axs[1].set_xticks(np.arange(1,len(profile)+1),profile.index)
    axs[1].set(title="Source base stay time by cluster",ylabel="Minutes (source values)")
    for ax in axs:ax.tick_params(axis="x",rotation=45)
    finish(fig,"06_G_sizes_and_stay")
    fig,ax=plt.subplots(figsize=(9,4));bottom=np.zeros(len(shares))
    for i,c in enumerate(CATEGORIES):ax.bar(shares.index,shares[c],bottom=bottom,label=CAT_LABELS[c],color=PALETTE[i]);bottom+=shares[c].to_numpy()
    ax.set(title="G cluster category composition",ylabel="Share",ylim=(0,1));ax.legend(bbox_to_anchor=(1.02,1),loc="upper left",frameon=False);finish(fig,"07_G_category_profiles")
    valid=eligible_places[eligible_places.coordinate_valid]
    fig,ax=plt.subplots(figsize=(7,8))
    for i,g in enumerate(sorted(eligible_places.G_cluster.unique())):
        q=valid[valid.G_cluster.eq(g)];ax.scatter(q.lon,q.lat,s=10,alpha=.45,color=PALETTE[i%len(PALETTE)],label=g)
    if len(valid):ax.set_aspect(1/max(.1,np.cos(np.deg2rad(valid.lat.mean()))))
    ax.set(title="G clusters at source coordinates",xlabel="Longitude",ylabel="Latitude")
    ax.legend(bbox_to_anchor=(1.02,1),loc="upper left",frameon=False);finish(fig,"08_G_coordinate_scatter")


def norm_name(text):
    text=unicodedata.normalize("NFKC",str(text)).lower()
    return re.sub(r"[^0-9a-z가-힣]","",text)

def no_parentheses(text):
    return re.sub(r"\([^()]*\)|（[^（）]*）","",str(text)).strip()

def norm_region(text):
    text=norm_name(text)
    # Keep 고성 distinct from 고성(강원); no inferred province mappings.
    return re.sub(r"(특별자치시|광역시|특별시|시|군)$","",text)

def split_outside(text, separators):
    parts=[];buffer=[];depth=0;i=0
    separators=sorted(separators,key=len,reverse=True)
    while i<len(text):
        char=text[i]
        if char in "(（[":depth+=1
        if char in ")）]":depth=max(0,depth-1)
        sep=next((s for s in separators if depth==0 and text.startswith(s,i)),None)
        if sep:
            parts.append("".join(buffer).strip());buffer=[];i+=len(sep)
        else:buffer.append(char);i+=1
    parts.append("".join(buffer).strip())
    return [p for p in parts if p]

def parse_route(text):
    text=str(text).strip()
    if not text:return [],"EMPTY"
    if re.search(r"자유코스|자율코스|맞춤|홈페이지.*참조|리플릿.*참조|운행 요청|원하는 일정|자유선택|요구반영|일대$",text):return [text],"FLEXIBLE_OR_UNSPECIFIED"
    numbered=list(re.finditer(r"(?:^|\s)(\d{1,2})\s+(?=\S)",text))
    if len(numbered)>=2 and [int(m.group(1)) for m in numbered]==list(range(1,len(numbered)+1)):
        parts=[text[m.end():numbered[j+1].start() if j+1<len(numbered) else len(text)].strip() for j,m in enumerate(numbered)]
        return parts,"NUMBERED_ORDER"
    parts=split_outside(text,["->","→","⇒","↔",">","+","_"," - "])
    if len(parts)>1:return parts,"EXPLICIT_SEPARATOR"
    comma=split_outside(text,[",","，"])
    if len(comma)>1:return comma,"UNORDERED_LIST_REVIEW"
    return [text],"UNSPLIT_REVIEW"

def strip_number(text):
    return re.sub(r"^\s*(?:[①-⑳]|\d{1,2}[.)])\s*","",text).strip()

KW={"herit":r"궁|성곽|읍성|산성|사찰|[가-힣]사$|향교|서원|박물관|유적|고분|릉|역사|문화재|한옥|민속|전통|사지|기념관",
    "heal":r"산$|숲|수목원|공원|호수|저수지|계곡|습지|정원|폭포|자연|생태|휴양림|둘레길|농원|수변",
    "activity":r"체험|테마파크|랜드|케이블카|레일|짚|루지|월드|과학관|전망대|스카이|목장|놀이",
    "food":r"시장|먹거리|맛|음식|카페|막걸리|와이너리|양조|빵|맥주|술",
    "sea":r"해수욕장|해변|[가-힣]항$|바다|섬|포구|해안|등대|해상|해양|방조제"}
full_index,base_index=defaultdict(set),defaultdict(set)
place_lookup={}
if places is not None:
    for _,p in places.iterrows():
        region=norm_region(p.region);full_index[(region,norm_name(p["name"]))].add(p.place_id)
        base_index[(region,norm_name(no_parentheses(p["name"])))].add(p.place_id)
        place_lookup[p.place_id]=p

def match_place(region,name,conditional=False):
    if conditional:return "CONDITIONAL_STOP_REVIEW",None
    if places is None:return "NO_PLACE_MASTER",None
    key=(norm_region(region),norm_name(name))
    ids=full_index.get(key,set());status="EXACT_NAME_REGION_CANDIDATE"
    if not ids:
        ids=base_index.get((norm_region(region),norm_name(no_parentheses(name))),set());status="PAREN_ALIAS_CANDIDATE"
    if len(ids)>1:return "AMBIGUOUS_NAME",None
    if len(ids)==1:return status,next(iter(ids))
    return "UNMATCHED",None

city=None;stops=None;city_features=None;city_model=None
if cities_raw is not None:
    mapping={"region":["지역","region_name"],"name":["투어명","course_name"],"type":["유형","course_type_raw"],
             "boarding":["탑승 장소","boarding_raw"],"route":["코스(경유지)","route_raw"],
             "start":["운행 시작","first_departure_raw"],"end":["운행 종료","last_departure_raw"],
             "headway":["배차 간격(분)","headway_raw"],"url":["홈페이지","url"],
             "notes":["운행 요일·비고","notes_raw"],"reference_date":["데이터 기준일","reference_date"]}
    city=standard_columns(cities_raw,mapping,{"region","name","route"})
    city["course_id"]=["ct_"+hashlib.sha256((str(i)+"|"+r.region+"|"+r["name"]+"|"+r.route).encode()).hexdigest()[:14] for i,r in city.iterrows()]
    records=[];course_records=[]
    for index,r in city.iterrows():
        parts,parser=parse_route(r.route);parsed=parser in ["EXPLICIT_SEPARATOR","NUMBERED_ORDER"]
        visit_vectors=[];known=0;matched=0;conditional_count=0;cluster_counter=Counter();visit_n=0
        for seq,raw in enumerate(parts,1):
            name=strip_number(raw);base=no_parentheses(name)
            conditional=bool(re.search(r"또는|봄|여름|가을|겨울|하계|동계|계절|선택",name) or "/" in base)
            role="VISIT_CANDIDATE"
            if re.search(r"출발|도착|승차",name):role="BOARDING_OR_RETURN"
            elif re.search(r"차창|경유|통과",name):role="PASS_BY"
            elif seq in [1,len(parts)] and (norm_name(base)==norm_name(no_parentheses(r.boarding)) or re.search(r"역$|터미널$|주차장$",base)):role="ENDPOINT_TRANSPORT"
            if not parsed:role="UNRESOLVED_ROUTE"
            status,pid=match_place(r.region,name,conditional)
            if role!="VISIT_CANDIDATE":status,pid="NON_VISIT_OR_UNRESOLVED",None
            vector=np.zeros(5);category_source="UNKNOWN";cluster=""
            if role=="VISIT_CANDIDATE":
                visit_n+=1;conditional_count+=int(conditional)
                if pid:
                    p=place_lookup[pid];matched+=1
                    if p.category in CATEGORIES:
                        vector[CATEGORIES.index(p.category)]=1;category_source="PROVISIONAL_PLACE_CATEGORY"
                    if pd.notna(p.get("G_cluster")):cluster=p.G_cluster;cluster_counter[cluster]+=1
                if not vector.any() and not conditional:
                    vector=np.array([bool(re.search(KW[c],base)) for c in CATEGORIES],float)
                    if vector.sum():vector/=vector.sum();category_source="KEYWORD_ESTIMATE"
                known+=int(vector.any());visit_vectors.append(vector)
            records.append({"course_id":r.course_id,"source_row":index+2,"region":r.region,"course_name":r["name"],"sequence":seq,
                            "stop_raw":raw,"name_candidate":base,"parser_status":parser,"role":role,"conditional":conditional,
                            "match_status":status,"place_id_candidate":pid or "","identity_verified":False,"G_cluster":cluster,
                            "category_source":category_source,**{c:float(vector[j]) for j,c in enumerate(CATEGORIES)}})
        shares=np.sum(visit_vectors,axis=0)/visit_n if visit_n else np.zeros(5)
        coverage=known/visit_n if visit_n else 0.0
        eligible=parsed and visit_n>=2 and conditional_count==0 and coverage>=MIN_CITY_CATEGORY_COVERAGE
        why="ELIGIBLE" if eligible else "ROUTE_UNRESOLVED" if not parsed else "CONDITIONAL_STOPS" if conditional_count else "TOO_FEW_VISITS" if visit_n<2 else "LOW_CATEGORY_COVERAGE"
        flags=[]
        if str(r.headway) in ["0","0000",""]:flags.append("HEADWAY_UNKNOWN_OR_NOT_APPLICABLE")
        if str(r.headway)=="1":flags.append("HEADWAY_ONE_REVIEW")
        if r.start==r.end=="00:00":flags.append("OPERATING_TIME_UNDECIDED")
        if not r.url:flags.append("URL_MISSING")
        date=pd.to_datetime(r.reference_date,errors="coerce")
        if pd.isna(date):flags.append("REFERENCE_DATE_MISSING_OR_INVALID")
        elif (pd.Timestamp.now().normalize()-date).days>365:flags.append("REFERENCE_OLDER_THAN_365_DAYS")
        course_records.append({"source_index":index,"course_id":r.course_id,"region":r.region,"name":r["name"],"parser_status":parser,
                               "parsed_stop_count":len(parts),"visit_candidate_count":visit_n,"category_known_count":known,
                               "category_coverage":coverage,"place_candidate_count":matched,"place_match_coverage":matched/visit_n if visit_n else 0,
                               "conditional_stop_count":conditional_count,"cluster_eligible":eligible,"cluster_status":why,
                               "night_flag":int(bool(re.search(r"야간|야경|나이트|밤|야시장|달빛|별빛",r["name"]+r.route))),
                               "operational_flags":"|".join(flags),**{f"share_{c}":float(shares[j]) for j,c in enumerate(CATEGORIES)},
                               "G_composition_counts":json.dumps(dict(sorted(cluster_counter.items())),ensure_ascii=False)})
    stops=pd.DataFrame(records);course_table=pd.DataFrame(course_records).set_index("source_index")
    save_csv(stops,"citytour_stop_links_review");save_csv(course_table.reset_index(),"citytour_features_and_quality")
    save_csv(stops[stops.match_status.isin(["UNMATCHED","AMBIGUOUS_NAME","CONDITIONAL_STOP_REVIEW","NON_VISIT_OR_UNRESOLVED"])],"citytour_stop_unresolved")
    print("코스 / 분석 가능:",len(course_table),"/",int(course_table.cluster_eligible.sum()))
    show_table(course_table.groupby(["parser_status","cluster_status"]).size().reset_index(name="courses"),30)
    print("잠정 장소 후보 연결 슬롯:",int(stops.place_id_candidate.ne("").sum()),"| 확인된 장소 연결: 0")


if city is not None:
    city_eligible=course_table.loc[course_table.cluster_eligible].copy()
    if len(city_eligible)>=4:
        city_features=city_eligible[[f"share_{c}" for c in CATEGORIES]]*np.sqrt(CITY_WEIGHTS["category"]/2)
        scaled_count,count_params=robust_log(city_eligible.visit_candidate_count)
        city_features["log_visit_count_robust"]=scaled_count*np.sqrt(CITY_WEIGHTS["stop_count"])
        city_features["night_flag"]=city_eligible.night_flag*np.sqrt(CITY_WEIGHTS["night"])
        if len(np.unique(np.round(city_features.to_numpy(),12),axis=0))>=3:
            city_model=fit_cluster_pipeline(city_features,"T",{"weights":CITY_WEIGHTS,"visit_count":count_params,"keywords":KW,"minimum_category_coverage":MIN_CITY_CATEGORY_COVERAGE})
            RUN_SUMMARY["citytour"]=city_model["summary"]
            city_eligible["T_cluster"]=city_model["labels"]
            city_eligible=city_eligible.join(city_model["pcs"])
            course_table=course_table.join(city_eligible[["T_cluster"]+[c for c in ["PC1","PC2"] if c in city_eligible]])
            plot_diagnostics(city_model,9)
            profile=city_eligible.groupby("T_cluster")[[f"share_{c}" for c in CATEGORIES]+["visit_candidate_count","night_flag","category_coverage","place_match_coverage"]].mean()
            profile.insert(0,"n",city_eligible.groupby("T_cluster").size())
            save_csv(profile.reset_index(),"T_cluster_profiles");show_table(profile.reset_index(),20)
            fig,ax=plt.subplots(figsize=(9,4));bottom=np.zeros(len(profile))
            for i,c in enumerate(CATEGORIES):
                values=profile[f"share_{c}"];ax.bar(profile.index,values,bottom=bottom,label=CAT_LABELS[c],color=PALETTE[i]);bottom+=values.to_numpy()
            ax.bar(profile.index,1-bottom,bottom=bottom,label="Unknown",color="#DDDDDD")
            ax.set(title="T cluster mean category composition",ylabel="Share",ylim=(0,1));ax.legend(bbox_to_anchor=(1.02,1),loc="upper left",frameon=False)
            finish(fig,"13_T_category_profiles")
        else:print("코스의 서로 다른 특성 조합이 3개 미만이어서 T PCA·군집은 생략합니다.")
    else:print("유효 코스가 4개 미만이어서 T PCA·군집은 생략합니다. 품질표는 저장합니다.")
    save_csv(pd.concat([cities_raw,course_table.add_prefix("analysis_")],axis=1),"T_citytour_assignments_all")
    fig,axs=plt.subplots(1,2,figsize=(12,5))
    count=course_table.cluster_status.value_counts();axs[0].barh(count.index,count.values,color="#9F718B");axs[0].invert_yaxis();axs[0].set(title="Course modeling eligibility",xlabel="Courses")
    count=stops.match_status.value_counts();axs[1].barh(count.index,count.values,color="#77658D");axs[1].invert_yaxis();axs[1].set(title="Stop identity linking status",xlabel="Parsed records")
    for ax in axs:
        ax.tick_params(axis="y",labelsize=8)
        for bar in ax.patches:ax.text(bar.get_width()+.5,bar.get_y()+bar.get_height()/2,str(int(bar.get_width())),va="center",fontsize=9)
    finish(fig,"14_citytour_quality_and_linking")
    if places is not None and stops.G_cluster.ne("").any():
        matched=stops[stops.G_cluster.ne("")]
        by_course=pd.crosstab(matched.course_id,matched.G_cluster)
        denominator=course_table.set_index("course_id").visit_candidate_count
        shares=by_course.div(denominator.reindex(by_course.index),axis=0)
        shares["Unknown_or_unlinked"]=1-shares.sum(axis=1)
        save_csv(shares.reset_index(),"citytour_G_composition_shares")
        # Display the 20 most linked routes; the CSV preserves every linked route.
        selected=by_course.sum(axis=1).sort_values(ascending=False).head(20).index
        display_shares=shares.loc[selected].copy()
        names=course_table.set_index("course_id").apply(lambda r:r["region"]+" "+r["name"],axis=1)
        labels=[(name[:24]+"…") if len(name)>25 else name for name in names.loc[selected]] if font!="DejaVu Sans" else [f"Route {i+1}" for i in range(len(selected))]
        fig,ax=plt.subplots(figsize=(11,7));im=ax.imshow(display_shares,cmap="Purples",vmin=0,vmax=1,aspect="auto")
        ax.set(yticks=np.arange(len(selected)),yticklabels=labels,xticks=np.arange(len(shares.columns)),xticklabels=shares.columns,title="Course composition by G cluster (top 20 linked routes)")
        ax.tick_params(axis="x",rotation=60);ax.tick_params(axis="y",labelsize=9);fig.colorbar(im,ax=ax,label="Share of all visit-candidate slots")
        finish(fig,"15_citytour_G_composition")


import zipfile
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold, GridSearchCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
SPEND={};SPEND_INFO={};spend_model_data=None;spend_regression=None
REGION_HEADERS={'광역지자체 명','기초지자체 명','광역지자체 지출액 비율(%)','기초지자체 지출액 비율(%)'}
def numeric_checked(series,name):
    v=pd.to_numeric(series.astype(str).str.replace(',','',regex=False),errors='coerce')
    if v.isna().any() or (~np.isfinite(v)).any() or v.lt(0).any():raise ValueError(f'{name}: 누락·음수·비수치')
    return v.astype(float)
def load_region_input(source):
    if source is None or not Path(source).exists():
        print('지역 지출 자료 없음: 지역 설명 모델을 건너뜁니다.');return {}
    p=Path(source)
    if p.is_dir():blobs=[(str(x),x.read_bytes()) for x in sorted(p.glob('*.csv'))]
    elif p.suffix.lower()=='.zip':
        with zipfile.ZipFile(p) as z:blobs=[(n,z.read(n)) for n in z.namelist() if n.lower().endswith('.csv')]
    elif p.suffix.lower()=='.csv':blobs=[(str(p),p.read_bytes())]
    else:raise ValueError('지역 지출 입력은 CSV, 폴더 또는 ZIP이어야 합니다.')
    found={}
    for name,b in blobs:
        for enc in ['utf-8-sig','cp949','utf-16']:
            try:df=pd.read_csv(io.BytesIO(b),encoding=enc,dtype=str,keep_default_na=False);break
            except UnicodeError:continue
        else:raise ValueError(f'CSV 인코딩 확인 필요: {name}')
        df.columns=[str(c).strip().lstrip('\ufeff') for c in df.columns]
        if not REGION_HEADERS.issubset(df.columns):continue
        if found:raise ValueError('지역 지출 CSV가 여러 개입니다.')
        found['region']=df
        INPUT_META['spend_region']={'file':name,'sha256':hashlib.sha256(b).hexdigest(),'rows':len(df),'encoding':enc,'columns':df.columns.tolist()}
    if not found:raise ValueError('지역 지출 필수 칼럼을 갖춘 CSV가 없습니다.')
    return found
SPEND=load_region_input(SPENDING_INPUT)
if SPEND:
    sp_reg=SPEND['region'].rename(columns={'광역지자체 명':'province','기초지자체 명':'municipality','광역지자체 지출액 비율(%)':'province_pct','기초지자체 지출액 비율(%)':'within_province_pct'}).copy()
    for col in ['province','municipality']:
        sp_reg[col]=sp_reg[col].str.strip()
        if sp_reg[col].eq('').any():raise ValueError('지역명 누락')
    for col in ['province_pct','within_province_pct']:sp_reg[col]=numeric_checked(sp_reg[col],col)
    if sp_reg.duplicated(['province','municipality']).any():raise ValueError('지역 키 중복')
    if sp_reg.groupby('province').province_pct.nunique().gt(1).any():raise ValueError('광역 비율 불일치')
    if sp_reg[['province_pct','within_province_pct']].gt(100).any().any():raise ValueError('100% 초과')
    sp_province=sp_reg.groupby('province').agg(province_pct=('province_pct','first'),child_sum_pct=('within_province_pct','sum'),rows=('municipality','size')).reset_index()
    if not sp_province.child_sum_pct.between(99,101).all() or not 99<=sp_province.province_pct.sum()<=101:raise ValueError('지역 계층 비율 합계 확인 필요')
    sp_reg['region_id']=sp_reg.province+'|'+sp_reg.municipality
    sp_reg['national_share_pct_raw']=sp_reg.province_pct*sp_reg.within_province_pct/100
    sp_reg['national_share_pct_normalized']=100*(sp_reg.province_pct/sp_province.province_pct.sum())*(sp_reg.within_province_pct/sp_reg.province.map(sp_province.set_index('province').child_sum_pct))
    sp_reg['zero_share_review']=sp_reg.within_province_pct.eq(0)
    sp_reg['boundary_review']=sp_reg.province.str.contains('통합')|sp_reg.province.eq('인천광역시')
    sp_reg['boundary_note']=np.where(sp_reg.province.eq('인천광역시'),'원본 하위 명칭의 경계와 기간 확인 필요',np.where(sp_reg.province.str.contains('통합'),'원본 광역 명칭 보존; 경계 환산 안 함',''))
    pos=sp_reg.national_share_pct_normalized.gt(0);sp_reg['economic_context_score']=np.nan
    sp_reg.loc[pos,'economic_context_score']=100*(sp_reg.loc[pos,'national_share_pct_normalized'].rank(method='average')-1)/max(1,pos.sum()-1)
    SPEND_INFO={'region_rows':len(sp_reg),'province_labels':len(sp_province),'regional_amount_estimation_enabled':False,
      'population_label':'내국인 지출로 제공됨; CSV에 대상집단 확인 열 없음',
      'period_status':'지역 CSV에 기간 열 없음; 다른 파일의 기간을 자동 적용하지 않음',
      'region_share_denominator':'hierarchical denominator inferred from sums; not verified from UI metadata'}
    save_csv(sp_reg,'spend_region_context');save_csv(sp_province,'spend_province_quality')
    print(json.dumps(SPEND_INFO,ensure_ascii=False,indent=2))


if SPEND:
    sp_parent_alias={'서울':'서울특별시','부산':'부산광역시','대구':'대구광역시','대전':'대전광역시','인천':'인천광역시','울산':'울산광역시','세종':'세종특별자치시','제주':'제주특별자치도'}
    sp_explicit_alias={'경기광주':('경기도','광주시'),'고성(강원)':('강원특별자치도','고성군')}
    def spend_join_region(name):
        name=str(name).strip()
        if name in sp_parent_alias:
            p=sp_parent_alias[name];hit=sp_province[sp_province.province.eq(p)]
            return {'region':name,'spend_region_id':p,'spend_province':p,'spend_level':'province','join_status':'PROVINCE_CONTEXT_ONLY','national_share_pct':float(hit.iloc[0].province_pct/sp_province.province_pct.sum()*100) if len(hit) else np.nan,'economic_context_score':np.nan,'boundary_review':p=='인천광역시'}
        if name=='광주':hit=sp_reg.iloc[:0];status='AMBIGUOUS_METRO_VS_CITY'
        elif name in sp_explicit_alias:
            p,m=sp_explicit_alias[name];hit=sp_reg[sp_reg.province.eq(p)&sp_reg.municipality.eq(m)];status='EXPLICIT_PARENT_ALIAS'
        else:
            hit=sp_reg[sp_reg.municipality.map(lambda x:re.sub(r'[시군구]$','',str(x))).eq(name)];status='UNIQUE_MUNICIPALITY_ALIAS'
        if len(hit)==1:
            a=hit.iloc[0]
            return {'region':name,'spend_region_id':a.region_id,'spend_province':a.province,'spend_level':'municipality','join_status':status,'national_share_pct':float(a.national_share_pct_normalized),'economic_context_score':float(a.economic_context_score),'boundary_review':bool(a.boundary_review)}
        return {'region':name,'spend_region_id':'','spend_province':'','spend_level':'unresolved','join_status':status if name=='광주' else 'AMBIGUOUS_NAME' if len(hit)>1 else 'UNMATCHED','national_share_pct':np.nan,'economic_context_score':np.nan,'boundary_review':False}
    sp_names=set()
    if places is not None:sp_names.update(places.region.unique())
    if city is not None:sp_names.update(city.region.unique())
    sp_mapping=pd.DataFrame([spend_join_region(x) for x in sorted(sp_names)])
    if len(sp_mapping):save_csv(sp_mapping,'spend_region_mapping_review')
    if places is not None:
        sp_place_links=places[['place_id','region','name','category','base_minutes','G_cluster']].reset_index().merge(sp_mapping,on='region',how='left',validate='many_to_one')
        sp_place_links['recommendation_spend_bonus']=0.0
        sp_place_links['score_status']='CONTEXT_ONLY_NOT_CALIBRATED'
        save_csv(sp_place_links,'G_places_with_spending_context')
        sp_gcontext=sp_place_links[sp_place_links.G_cluster.notna()].groupby('G_cluster').agg(places=('place_id','size'),linked_municipality_places=('spend_level',lambda x:int(x.eq('municipality').sum())),unique_source_regions=('region','nunique'),context_score_median=('economic_context_score','median'))
        save_csv(sp_gcontext.reset_index(),'G_spending_context_profiles')
    if city is not None:
        sp_course_links=course_table.reset_index().merge(sp_mapping,on='region',how='left',validate='many_to_one')
        sp_course_links['recommendation_spend_bonus']=0.0;sp_course_links['score_status']='CONTEXT_ONLY_NOT_CALIBRATED'
        save_csv(sp_course_links,'T_citytours_with_spending_context')
    sp_top=sp_reg.nlargest(20,'national_share_pct_normalized').sort_values('national_share_pct_normalized')
    fig,ax=plt.subplots(figsize=(10,7));ax.barh(sp_top.province+' '+sp_top.municipality,sp_top.national_share_pct_normalized,color='#9F718B')
    ax.set(title='Regional shares derived from the source hierarchy',xlabel='National share (%) - normalized, not KRW');finish(fig,'24_spend_region_shares')
    if len(sp_mapping):show_table(sp_mapping.groupby(['spend_level','join_status']).size().reset_index(name='source_regions'),20)


if SPEND and places is not None:
    sp_rows=[]
    for region,group in places.groupby('region'):
        gp=group[group.cluster_eligible];gmap=sp_mapping[sp_mapping.region.eq(region)].iloc[0]
        row=gmap.to_dict();row.update({'n_catalog_places':len(gp),'n_lodging':int(group.category.eq('stay').sum()),'n_citytours':int(city.region.eq(region).sum()) if city is not None else 0,
                                    'median_base_minutes':float(gp.base_minutes.median()) if len(gp) else np.nan,'unesco_mark_rate':float(gp.unesco_mark.mean()) if len(gp) else np.nan})
        row.update({f'share_{c}':float(gp.category.eq(c).mean()) if len(gp) else np.nan for c in CATEGORIES})
        row['model_eligible']=bool(gmap.spend_level=='municipality' and len(gp)>=MIN_CATALOG_PLACES and pd.notna(gmap.national_share_pct) and gmap.national_share_pct>0)
        row['model_reason']='ELIGIBLE' if row['model_eligible'] else 'MIXED_OR_UNRESOLVED_GEOGRAPHY' if gmap.spend_level!='municipality' else 'CATALOG_TOO_SMALL_OR_SHARE_NOT_POSITIVE'
        sp_rows.append(row)
    sp_region_catalog=pd.DataFrame(sp_rows)
    save_csv(sp_region_catalog,'spend_region_catalog_features_all')
    spend_model_data=sp_region_catalog[sp_region_catalog.model_eligible].copy().reset_index(drop=True)
    # Keep the mixed-boundary source label visible; grouping uses that label as provided.
    if len(spend_model_data)>=20 and spend_model_data.spend_province.nunique()>=5:
        for col in ['n_catalog_places','n_lodging','n_citytours','median_base_minutes']:
            spend_model_data['log_'+col]=np.log1p(spend_model_data[col])
        sp_feats=['log_n_catalog_places','log_n_lodging','log_n_citytours','log_median_base_minutes','share_heal','share_activity','share_food','share_sea','unesco_mark_rate']
        sp_x=spend_model_data[sp_feats].copy();sp_y=np.log(spend_model_data.national_share_pct.to_numpy());sp_groups=spend_model_data.spend_province.to_numpy()
        sp_oof={k:np.full(len(sp_y),np.nan) for k in ['M0_mean','M1_catalog_count','M2_composition']}
        sp_foldid=np.zeros(len(sp_y),int);sp_foldrows=[];sp_coefrows=[]
        sp_outer=GroupKFold(n_splits=5)
        for fold,(train,test) in enumerate(sp_outer.split(sp_x,sp_y,sp_groups),1):
            assert not set(sp_groups[train])&set(sp_groups[test]);sp_foldid[test]=fold
            sp_oof['M0_mean'][test]=sp_y[train].mean()
            for name,features in [('M1_catalog_count',sp_feats[:1]),('M2_composition',sp_feats)]:
                pipe=Pipeline([('scale',StandardScaler()),('ridge',Ridge())])
                inner=GroupKFold(n_splits=min(3,len(set(sp_groups[train]))))
                search=GridSearchCV(pipe,{'ridge__alpha':REGRESSION_ALPHAS},cv=inner,scoring='neg_mean_squared_error',n_jobs=1,error_score='raise')
                search.fit(sp_x.iloc[train][features],sp_y[train],groups=sp_groups[train])
                pred=search.predict(sp_x.iloc[test][features]);sp_oof[name][test]=pred
                sp_foldrows.append({'fold':fold,'model':name,'test_provinces':'|'.join(sorted(set(sp_groups[test]))),'n_train':len(train),'n_test':len(test),'alpha':float(search.best_params_['ridge__alpha']),'mae_log':float(mean_absolute_error(sp_y[test],pred)),'rmse_log':float(np.sqrt(mean_squared_error(sp_y[test],pred))),'r2_log':float(r2_score(sp_y[test],pred))})
                if name=='M2_composition':
                    sp_coefrows.extend({'fold':fold,'feature':f,'standardized_beta':float(b)} for f,b in zip(features,search.best_estimator_.named_steps['ridge'].coef_))
        sp_metrics=[]
        for name,pred in sp_oof.items():
            assert np.isfinite(pred).all()
            sp_metrics.append({'model':name,'n_regions':len(sp_y),'mae_log':float(mean_absolute_error(sp_y,pred)),'rmse_log':float(np.sqrt(mean_squared_error(sp_y,pred))),'r2_log':float(r2_score(sp_y,pred)),'mae_share_pp':float(mean_absolute_error(np.exp(sp_y),np.exp(pred)))})
        sp_metrics=pd.DataFrame(sp_metrics);sp_folds=pd.DataFrame(sp_foldrows);sp_coefs=pd.DataFrame(sp_coefrows)
        sp_predictions=spend_model_data[['region','spend_region_id','spend_province','national_share_pct','boundary_review']].copy();sp_predictions['fold']=sp_foldid;sp_predictions['target_log_share']=sp_y
        for name,pred in sp_oof.items():sp_predictions[name+'_oof_log']=pred;sp_predictions[name+'_oof_share_pct']=np.exp(pred)
        sp_finalsearch=GridSearchCV(Pipeline([('scale',StandardScaler()),('ridge',Ridge())]),{'ridge__alpha':REGRESSION_ALPHAS},cv=GroupKFold(n_splits=5),scoring='neg_mean_squared_error',error_score='raise')
        sp_finalsearch.fit(sp_x,sp_y,groups=sp_groups)
        spend_regression=sp_finalsearch.best_estimator_
        sp_finalcoef=pd.DataFrame({'feature':sp_feats,'standardized_beta':spend_regression.named_steps['ridge'].coef_})
        sp_z=spend_regression.named_steps['scale'].transform(sp_x)
        sp_explain=pd.DataFrame(sp_z*spend_regression.named_steps['ridge'].coef_,columns=sp_feats)
        sp_explain.insert(0,'region',spend_model_data.region);sp_explain['intercept']=float(spend_regression.named_steps['ridge'].intercept_)
        sp_explain['fitted_log_share']=sp_explain[sp_feats].sum(axis=1)+sp_explain.intercept
        assert np.allclose(sp_explain.fitted_log_share,spend_regression.predict(sp_x))
        for frame,name in [(spend_model_data,'spend_regression_input'),(sp_predictions,'spend_regression_oof'),(sp_metrics,'spend_regression_metrics'),(sp_folds,'spend_regression_folds'),(sp_coefs,'spend_regression_fold_coefficients'),(sp_finalcoef,'spend_regression_coefficients'),(sp_explain,'spend_regression_additive_explanations')]:save_csv(frame,name)
        sp_buffer=io.BytesIO();joblib.dump({'pipeline':spend_regression,'features':sp_feats,'target':'log normalized national regional share percent','alpha':float(sp_finalsearch.best_params_['ridge__alpha']),'sklearn':sklearn.__version__},sp_buffer);(MODELS/'spend_region_ridge.joblib').write_bytes(sp_buffer.getvalue())
        SPEND_INFO['regression']={'n_regions':len(sp_y),'n_province_groups':len(set(sp_groups)),'outer_folds':5,'inner_folds':3,'features':sp_feats,'metrics':sp_metrics.to_dict('records'),'final_alpha':float(sp_finalsearch.best_params_['ridge__alpha']),
                                  'added_features_improve_mae':bool(sp_metrics.set_index('model').loc['M2_composition','mae_log']<sp_metrics.set_index('model').loc['M1_catalog_count','mae_log']),
                                  'all_target_region_values_are_derived_shares':True,'future_forecast_validated':False}
        print('지역 설명 모델 OOF 결과');show_table(sp_metrics,10)
        fig,axs=plt.subplots(1,2,figsize=(11,4))
        axs[0].bar(sp_metrics.model,sp_metrics.mae_log,color=['#999999','#78618E','#AF7891']);axs[0].set(title='Held-out province evaluation',ylabel='MAE of log share');axs[0].tick_params(axis='x',rotation=20)
        axs[1].scatter(sp_y,sp_oof['M2_composition'],color='#AF7891',s=28,alpha=.75);lo=min(sp_y.min(),sp_oof['M2_composition'].min());hi=max(sp_y.max(),sp_oof['M2_composition'].max());axs[1].plot([lo,hi],[lo,hi],'--',color='#555')
        axs[1].set(xlabel='Observed derived log share',ylabel='Out-of-fold predicted log share',title=f'M2 pooled R2 = {sp_metrics.set_index("model").loc["M2_composition","r2_log"]:.3f}')
        finish(fig,'25_spend_regression_oof')
        sp_c=sp_finalcoef.sort_values('standardized_beta');fig,ax=plt.subplots(figsize=(10,5));ax.barh(sp_c.feature,sp_c.standardized_beta,color=np.where(sp_c.standardized_beta>=0,'#AF7891','#78618E'));ax.axvline(0,color='#555',lw=1)
        ax.set(title='Full-fit standardized Ridge coefficients (associations)',xlabel='Change in log share per training SD');finish(fig,'26_spend_regression_coefficients')
        fig,ax=plt.subplots(figsize=(9,4));sp_cp=sp_coefs.pivot(index='feature',columns='fold',values='standardized_beta');lim=max(.01,float(np.abs(sp_cp.to_numpy()).max()));im=ax.imshow(sp_cp,aspect='auto',cmap='RdBu_r',vmin=-lim,vmax=lim)
        ax.set(xticks=np.arange(len(sp_cp.columns)),xticklabels=sp_cp.columns,yticks=np.arange(len(sp_cp)),yticklabels=sp_cp.index,title='Coefficient sensitivity across held-out provinces',xlabel='Outer fold');fig.colorbar(im,ax=ax,label='Standardized coefficient');finish(fig,'27_spend_coefficient_stability')
    else:print('지역 설명 회귀는 연결 지역 20개 및 광역 집단 5개 이상일 때 실행합니다. 연결표와 기술통계는 저장합니다.')


if SPEND:
    assert np.isclose(sp_reg.national_share_pct_normalized.sum(),100)
    assert SPEND_INFO['regional_amount_estimation_enabled'] is False
    if places is not None:
        assert len(sp_place_links)==len(places)
        assert sp_place_links.recommendation_spend_bonus.eq(0).all()
    if city is not None:
        assert len(sp_course_links)==len(course_table)
        assert sp_course_links.recommendation_spend_bonus.eq(0).all()
    (RUN_DIR/'spending_summary.json').write_text(json.dumps(SPEND_INFO,ensure_ascii=False,indent=2),encoding='utf-8')
    RUN_SUMMARY['spending']=SPEND_INFO
    print('지출 확장 완료:',json.dumps(SPEND_INFO.get('regression',{}),ensure_ascii=False,indent=2))


MARINE_HEADERS = {
    'heatmap': {'지역명','방문자수','구분'},
    'monthly': {'기준년월','구분','지자체건수','방문자수(평균)'},
    'top5': {'순위','읍면동','방문자 수','전년동기 방문자 수','비율'},
    'search_rank': {'순위','관광지명','도로명','분류','검색 건수'}
}
MARINE_GROUPS = ['전국','연안 도시','연안 어촌','연안 전체','비연안']
MARINE_PRIMARY = ['연안 도시','연안 어촌','비연안']
MARINE_LABELS = {'전국':'National','연안 도시':'Coastal urban','연안 어촌':'Coastal rural','연안 전체':'All coastal','비연안':'Non-coastal'}
MARINE_COLORS = {'전국':'#555555','연안 도시':'#A25F86','연안 어촌':'#78618E','연안 전체':'#3475B5','비연안':'#909090'}
marine_info = {}; marine_flags = []; marine_places = None; marine_courses = None; marine_stop_links = None

def load_marine_input(source):
    if source is None or not Path(source).exists():
        print('해양 입력 없음: 해양 확장을 건너뜁니다.'); return {}
    source=Path(source)
    if source.is_dir(): blobs=[(str(p),p.read_bytes()) for p in sorted(source.glob('*.csv'))]
    elif source.suffix.lower()=='.zip':
        with zipfile.ZipFile(source) as z: blobs=[(n,z.read(n)) for n in z.namelist() if n.lower().endswith('.csv')]
    else: raise ValueError('MARINE_INPUT은 해양 CSV 폴더 또는 ZIP입니다.')
    registry={}
    if source.is_dir() and (source/'source_registry.json').is_file():
        registry=json.loads((source/'source_registry.json').read_text(encoding='utf-8'))
    elif source.suffix.lower()=='.zip':
        with zipfile.ZipFile(source) as z:
            registry_names=[name for name in z.namelist() if Path(name).name=='source_registry.json']
            if len(registry_names)>1:raise ValueError('source_registry.json이 여러 개 있습니다.')
            if registry_names:registry=json.loads(z.read(registry_names[0]).decode('utf-8'))
    result={}
    for name,b in blobs:
        for enc in ['utf-8-sig','cp949','utf-16']:
            try: d=pd.read_csv(io.BytesIO(b),encoding=enc,dtype=str,keep_default_na=False);break
            except UnicodeError:continue
        else:raise ValueError('해양 CSV 인코딩 확인 필요: '+name)
        d.columns=[str(c).strip().lstrip('\ufeff') for c in d.columns]
        types=[k for k,h in MARINE_HEADERS.items() if h.issubset(d.columns)]
        if not types:continue
        if len(types)!=1 or types[0] in result:raise ValueError('중복·불명확한 해양 CSV: '+name)
        k=types[0];result[k]=d
        INPUT_META['marine_'+k]={'file':name,'rows':len(d),'columns':d.columns.tolist(),'sha256':hashlib.sha256(b).hexdigest(),'encoding':enc}
        record=registry.get(k,{})
        valid_record=record.get('sha256')==INPUT_META['marine_'+k]['sha256']
        meta=INPUT_META['marine_'+k]
        meta['source_registry_status']='hash_matched' if valid_record else 'hash_mismatch_ignored' if record else 'not_provided'
        meta['original_filename']=record['original_filename'] if valid_record else Path(name).name
        for field in ['declared_scope','declared_population','declaration_evidence']:
            meta[field]=record.get(field,'not_recorded') if valid_record else 'not_recorded'
        if not valid_record:
            if '외지인방문자' in Path(name).name:
                meta['declared_population']='외지인방문자';meta['declaration_evidence']='current_filename_hint'
            if '연안 전체' in Path(name).name:
                meta['declared_scope']='연안 전체 선택 목록';meta['declaration_evidence']='current_filename_hint'
    if not {'heatmap','monthly','top5'}.issubset(result):raise ValueError('해양 기본 CSV 3종 필요: 확인된 종류 '+str(list(result)))
    inventory=pd.DataFrame([{'input_kind':k,**INPUT_META['marine_'+k]} for k in result])
    inventory['columns']=inventory['columns'].map(lambda a:' | '.join(a))
    save_csv(inventory,'marine_input_source_inventory')
    return result

def marine_admin_parts(text):
    tokens=str(text).strip().split()
    if len(tokens)<3 or not re.search(r'[읍면동]$',tokens[-1]):
        raise ValueError('광역·시군구·읍면동 이름 확인 필요: '+str(text))
    return tokens[0],' '.join(tokens[1:-1]),tokens[-1]

MARINE=load_marine_input(MARINE_INPUT)
if MARINE:
    mh=MARINE['heatmap'].rename(columns={'지역명':'admin_name','방문자수':'area_visitors','구분':'marine_class'}).copy()
    mt=MARINE['monthly'].rename(columns={'기준년월':'month','구분':'group','지자체건수':'area_count','방문자수(평균)':'mean_visitors'}).copy()
    mg=MARINE['top5'].rename(columns={'순위':'source_rank','읍면동':'admin_name','방문자 수':'current_visitors','전년동기 방문자 수':'previous_visitors','비율':'source_ratio_pct'}).copy()
    # Blank heatmap visitor counts are unknown, not zero; keep area metadata.
    heat_raw=mh.area_visitors.astype(str).str.strip().str.replace(',','',regex=False)
    mh['visitor_value_missing']=heat_raw.eq('')
    mh['area_visitors']=pd.to_numeric(heat_raw.mask(mh.visitor_value_missing),errors='coerce')
    invalid=(~mh.visitor_value_missing & ~np.isfinite(mh.area_visitors)) | mh.area_visitors.lt(0)
    if invalid.any():raise ValueError('히트맵 방문자 수의 비수치·무한대·음수는 허용하지 않습니다.')
    mh['visitor_value_status']=np.where(mh.visitor_value_missing,'MISSING_NOT_IMPUTED','OBSERVED')
    mh['heatmap_source_present']=True
    for d,cs in [(mt,['area_count','mean_visitors']),(mg,['source_rank','current_visitors','previous_visitors'])]:
        for c in cs:d[c]=numeric_checked(d[c],'marine '+c)
    mg['source_ratio_pct']=pd.to_numeric(mg.source_ratio_pct.astype(str).str.replace(',','',regex=False),errors='coerce')
    if not np.isfinite(mg.source_ratio_pct).all():raise ValueError('Top5 비율에 비수치가 있습니다.')
    mt['month']=mt.month.astype(str).str.strip();mt['group']=mt.group.astype(str).str.strip()
    if not mt.month.str.fullmatch(r'\d{6}').all():raise ValueError('해양 월은 YYYYMM이어야 합니다.')
    periods=pd.to_datetime(mt.month,format='%Y%m',errors='raise').dt.to_period('M')
    expected=pd.period_range(periods.min(),periods.max(),freq='M').strftime('%Y%m').tolist()
    if mt.duplicated(['month','group']).any():raise ValueError('해양 월×구분 중복 행')
    if set(mt.group)!=set(MARINE_GROUPS):raise ValueError('해양 월별 구분 5종 확인 필요')
    if any(set(g.month)!=set(expected) for _,g in mt.groupby('group')):raise ValueError('해양 월×구분 누락')
    if mt.area_count.le(0).any() or (mt.area_count%1!=0).any():raise ValueError('지자체건수는 양의 정수여야 합니다.')
    mt['area_count']=mt.area_count.astype(int)
    mt=mt.sort_values(['month','group']).reset_index(drop=True)
    for d in [mh,mg]:
        d['admin_name']=d.admin_name.astype(str).str.strip()
        if d.admin_name.duplicated().any():raise ValueError('해양 읍면동 중복')
        parts=d.admin_name.map(marine_admin_parts)
        d[['province','municipality','township']]=pd.DataFrame(parts.tolist(),index=d.index)
    if not mh.marine_class.isin(['연안 도시','연안 어촌','비연안']).all():raise ValueError('히트맵 구분 확인 필요')
    if mg.source_rank.duplicated().any() or (mg.source_rank%1!=0).any():raise ValueError('Top5 순위 확인 필요')
    mg['source_rank']=mg.source_rank.astype(int)
    mg['standard_yoy_pct']=np.where(mg.previous_visitors.gt(0),100*(mg.current_visitors/mg.previous_visitors-1),np.nan)
    mg['current_denominator_pct']=np.where(mg.current_visitors.gt(0),100*(mg.current_visitors-mg.previous_visitors)/mg.current_visitors,np.nan)
    mg['source_matches_current_denominator']=np.isclose(mg.source_ratio_pct,mg.current_denominator_pct,atol=MARINE_RATIO_TOLERANCE_PP,rtol=0)
    mg['source_matches_previous_denominator']=np.isclose(mg.source_ratio_pct,mg.standard_yoy_pct,atol=MARINE_RATIO_TOLERANCE_PP,rtol=0)
    mg['source_minus_standard_pp']=mg.source_ratio_pct-mg.standard_yoy_pct
    mg['marine_class']=mg.admin_name.map(mh.set_index('admin_name').marine_class)
    mg['class_evidence']=np.where(mg.marine_class.notna(),'matched_heatmap_source_label','not_in_heatmap_no_class_inference')
    mg['selection_bias']='top5_only_not_a_national_training_sample'
    mvalue=mt.pivot(index='month',columns='group',values='mean_visitors').reindex(expected)
    mcount=mt.pivot(index='month',columns='group',values='area_count').reindex(expected)
    checks=[]
    for month in expected:
        for parent,children in [('연안 전체',['연안 도시','연안 어촌']),('전국',['연안 전체','비연안'])]:
            counts=mcount.loc[month,children];reconstructed=np.average(mvalue.loc[month,children],weights=counts)
            actual=float(mvalue.loc[month,parent]); count_ok=int(counts.sum())==int(mcount.loc[month,parent])
            checks.append({'month':month,'parent':parent,'reconstructed_weighted_mean':reconstructed,'source_mean':actual,'difference_visitors':actual-reconstructed,'count_sum_matches':count_ok,'within_rounding_tolerance':abs(actual-reconstructed)<=MARINE_MEAN_TOLERANCE})
    marine_checks=pd.DataFrame(checks)
    if not marine_checks.count_sum_matches.all():raise ValueError('해양 계층별 지자체건수 합계 불일치')
    if not marine_checks.within_rounding_tolerance.all():marine_flags.append({'check':'mean_reconciliation','status':'review','detail':'지자체건수 가중 평균과 원본 평균의 차이가 허용범위를 넘습니다.'})
    marine_info={'method_version':'marine-input-context-2.1','period_start':expected[0],'period_end':expected[-1],'months':len(expected),'heatmap_rows':len(mh),'heatmap_municipalities':sorted(mh.municipality.unique().tolist()),'monthly_rows':len(mt),'top5_rows':len(mg),'all_source_ratios_match_current_denominator':bool(mg.source_matches_current_denominator.all()),'max_weighted_mean_abs_difference':float(marine_checks.difference_visitors.abs().max()),'recommendation_bonus':0.0,'stay_multiplier':1.0,'new_marine_clustering_fitted':False,'forecast_validated':False,'spend_per_visitor_computed':False,'admin_boundary_verified_links':0,'snapshot_csv_has_period_column':False,'source_scope':'national heatmap snapshot as supplied; separate monthly group means; selected top5; not a township time panel'}
    marine_info.update({'heatmap_scope':'national_query_as_supplied',
        'heatmap_valid_visitor_rows':int(mh.area_visitors.notna().sum()),
        'heatmap_missing_visitor_rows':int(mh.visitor_value_missing.sum()),
        'heatmap_province_labels':int(mh.province.nunique()),
        'heatmap_class_counts':{k:int(v) for k,v in mh.marine_class.value_counts().items()},
        'heatmap_missing_area_names':mh.loc[mh.visitor_value_missing,'admin_name'].tolist(),
        'admin_labels_preserved_without_unverified_crosswalk':True,
        'monthly_population_label':INPUT_META['marine_monthly']['declared_population'],
        'monthly_population_evidence':INPUT_META['marine_monthly']['declaration_evidence']})
    for d,n in [(mh,'marine_township_heatmap'),(mt,'marine_monthly_clean'),(mg,'marine_top5_growth_audit'),(marine_checks,'marine_monthly_reconciliation')]:save_csv(d,n)
    show_table(mg[['admin_name','source_ratio_pct','standard_yoy_pct','source_matches_current_denominator']],10)
    print('해양 입력과 검증',json.dumps(marine_info,ensure_ascii=False,indent=2))



if MARINE:
    mi=mt.copy()
    period_means=mt.groupby('group').mean_visitors.mean()
    mi['period_mean_index']=100*mi.mean_visitors/mi.group.map(period_means).replace(0,np.nan)
    national=mvalue['전국'].to_dict();noncoastal=mvalue['비연안'].to_dict()
    mi['relative_to_national_index']=100*mi.mean_visitors/mi.month.map(national).replace(0,np.nan)
    mi['relative_to_noncoastal_index']=100*mi.mean_visitors/mi.month.map(noncoastal).replace(0,np.nan)
    mi['mom_pct']=mi.groupby('group').mean_visitors.pct_change(fill_method=None)*100
    changed=mi.groupby('group').area_count.diff().fillna(0).ne(0);mi['area_count_changed_from_previous']=changed
    profile=[]
    for group,d in mi.groupby('group'):
        peak=d.loc[d.mean_visitors.idxmax()];low=d.loc[d.mean_visitors.idxmin()]
        profile.append({'group':group,'mean_of_monthly_means':float(d.mean_visitors.mean()),'peak_month':peak.month,'peak_mean_visitors':float(peak.mean_visitors),'low_month':low.month,'peak_to_low_ratio':float(peak.mean_visitors/low.mean_visitors) if low.mean_visitors>0 else np.nan,'months':len(d),'min_area_count':int(d.area_count.min()),'max_area_count':int(d.area_count.max())})
    mprofile=pd.DataFrame(profile)
    save_csv(mi,'marine_monthly_indices');save_csv(mprofile,'marine_monthly_group_summary')
    fig,ax=plt.subplots(figsize=(11,4.4))
    for g in MARINE_PRIMARY+['전국','연안 전체']:
        ax.plot(expected,mvalue[g],marker='o',label=MARINE_LABELS[g],color=MARINE_COLORS[g],lw=2 if g in MARINE_PRIMARY else 1,ls='-' if g in MARINE_PRIMARY else '--')
    ax.set(title='Marine tourism: mean visitors per administrative area',ylabel='Source mean visitor estimate',xlabel='Month');ax.tick_params(axis='x',rotation=45);ax.legend(bbox_to_anchor=(1.01,1));finish(fig,'28_marine_monthly_means')
    fig,ax=plt.subplots(figsize=(11,4))
    for g in MARINE_PRIMARY:
        a=mi[mi.group.eq(g)];ax.plot(a.month,a.period_mean_index,'o-',color=MARINE_COLORS[g],label=MARINE_LABELS[g])
    ax.axhline(100,color='#666',lw=1,ls='--');ax.set(title='Within-observed-period demand pattern',ylabel='Each group period mean = 100',xlabel='Month');ax.tick_params(axis='x',rotation=45);ax.legend();finish(fig,'29_marine_period_indices')
    fig,ax=plt.subplots(figsize=(11,4))
    for g in ['연안 도시','연안 어촌','연안 전체']:
        a=mi[mi.group.eq(g)];ax.plot(a.month,a.relative_to_noncoastal_index,'o-',color=MARINE_COLORS[g],label=MARINE_LABELS[g])
    ax.axhline(100,color='#666',ls='--',lw=1);ax.set(title='Coastal group mean relative to non-coastal mean',ylabel='Same-month non-coastal mean = 100',xlabel='Month');ax.tick_params(axis='x',rotation=45);ax.legend(loc='upper center',bbox_to_anchor=(.5,-.23),ncol=3,frameon=False);finish(fig,'30_marine_relative_demand')
    a=mh.dropna(subset=['area_visitors']).nlargest(min(20,len(mh)),'area_visitors').sort_values('area_visitors')
    if len(a):
        fig,ax=plt.subplots(figsize=(11,8))
        ax.barh(a.admin_name,a.area_visitors/1e6,color=a.marine_class.map(MARINE_COLORS))
        ax.set(title='National heatmap: top 20 observed area visitor estimates',xlabel='Source area visitor estimate / million')
        ax.tick_params(axis='y',labelsize=9)
        for j,v in enumerate(a.area_visitors):ax.text(v/1e6+.04,j,f'{v/1e6:.2f}',va='center',fontsize=8)
        ax.set_xlim(0,a.area_visitors.max()/1e6*1.15);finish(fig,'31_marine_national_heatmap_top20')
    # National snapshot summaries retain every source row, including missing values.
    mh_quality=mh[['admin_name','province','municipality','township','marine_class','area_visitors','visitor_value_missing','visitor_value_status']].copy()
    save_csv(mh_quality,'marine_heatmap_quality')
    national_group=mh.groupby('marine_class').agg(
        source_rows=('admin_name','size'),valid_visitor_rows=('area_visitors','count'),
        missing_visitor_rows=('visitor_value_missing','sum'),median_visitors=('area_visitors','median'),
        mean_visitors=('area_visitors','mean'),p75_visitors=('area_visitors',lambda x:x.quantile(.75))).reset_index()
    province_group=mh.groupby(['province','marine_class']).agg(
        source_rows=('admin_name','size'),valid_visitor_rows=('area_visitors','count'),
        missing_visitor_rows=('visitor_value_missing','sum'),median_visitors=('area_visitors','median'),
        mean_visitors=('area_visitors','mean')).reset_index()
    save_csv(national_group,'marine_heatmap_class_summary')
    save_csv(province_group,'marine_heatmap_province_class_summary')
    fig,axs=plt.subplots(1,2,figsize=(11,4.5))
    for i,g in enumerate(MARINE_PRIMARY):
        rows=national_group[national_group.marine_class.eq(g)]
        count=int(rows.source_rows.iloc[0]) if len(rows) else 0
        axs[0].bar(i,count,color=MARINE_COLORS[g]);axs[0].text(i,count+40,str(count),ha='center')
        vals=np.sort(mh.loc[mh.marine_class.eq(g),'area_visitors'].dropna().to_numpy())
        if len(vals):axs[1].step(vals,np.arange(1,len(vals)+1)/len(vals),where='post',label=MARINE_LABELS[g],color=MARINE_COLORS[g])
    axs[0].set(xticks=range(3),xticklabels=[MARINE_LABELS[g] for g in MARINE_PRIMARY],ylabel='Source area rows',title='National heatmap coverage')
    axs[0].tick_params(axis='x',labelsize=9);axs[0].set_ylim(0,national_group.source_rows.max()*1.15)
    axs[1].set_xscale('symlog',linthresh=1)
    axs[1].set(title='Snapshot visitor distribution',xlabel='Area visitor estimate (log scale above 1)',ylabel='Empirical cumulative fraction')
    axs[1].legend(frameon=False,fontsize=8)
    finish(fig,'35_marine_national_coverage_distribution')
    pivot=province_group.pivot(index='province',columns='marine_class',values='median_visitors').reindex(columns=MARINE_PRIMARY)/1e6
    fig,ax=plt.subplots(figsize=(8,8));arr=pivot.to_numpy(float)
    cmap=plt.get_cmap('Purples').copy();cmap.set_bad('#E8E8E8')
    im=ax.imshow(np.ma.masked_invalid(arr),aspect='auto',cmap=cmap,vmin=0)
    ax.set(yticks=np.arange(len(pivot)),yticklabels=pivot.index,xticks=range(3),
           xticklabels=[MARINE_LABELS[g] for g in MARINE_PRIMARY],title='Province labels by coastal class: median area visitors')
    for i in range(len(pivot)):
        for j in range(3):
            v=arr[i,j];ax.text(j,i,f'{v:.2f}' if np.isfinite(v) else 'N/A',ha='center',va='center',fontsize=9,
                             color='white' if np.isfinite(v) and v>np.nanmax(arr)*.55 else 'black')
    fig.colorbar(im,ax=ax,label='Median source area visitor estimate / million')
    finish(fig,'36_marine_province_class_heatmap')
    fig,ax=plt.subplots(figsize=(9,5));a=mg.sort_values('source_rank',ascending=False);y=np.arange(len(a))
    ax.barh(y-.18,a.source_ratio_pct,height=.34,label='CSV (current denominator)',color='#8F809B')
    ax.barh(y+.18,a.standard_yoy_pct,height=.34,label='YoY (previous denominator)',color='#B46B91')
    ax.set(yticks=y,yticklabels=a.admin_name,title='Top5: the denominator changes the percentage',xlabel='Percent');ax.legend(loc='upper center',bbox_to_anchor=(.5,-.15),ncol=2,frameon=False,fontsize=9);finish(fig,'32_marine_growth_denominator_audit')
    marine_monthly_spend=None
    marine_flags.extend([
        {'check':'heatmap_scope','status':'national_snapshot','detail':f'전국 조회 원본 {len(mh)}행, 방문값 유효 {mh.area_visitors.notna().sum()}행; CSV에 기간·방문자 조건·행정코드 열 없음'},
        {'check':'top5_selection','status':'limited','detail':'상위 5곳의 선택 표본; 미등재 지역의 성장률을 0으로 채우지 않음'},
        {'check':'ratio_denominator','status':'review','detail':'원본 비율을 보존하고 전년 분모 증가율을 별도 계산'},
        {'check':'area_count_changes','status':'review','detail':'집계구역 수 변화가 있는 월을 표시; 고정 경계 전년비로 해석하지 않음'},
        {'check':'visit_count_interpretation','status':'limited','detail':'읍면동/월 방문 추정값; 지역·기간을 더한 고유 방문자 총수 아님'},
        {'check':'spend_link','status':'limited','detail':'소비와 방문자의 대상·공간 단위 불일치; 1인당 지출 계산 안 함'},
        {'check':'pca_sample','status':'not_fitted','detail':'단일 시점 방문값과 연안 구분으로 신규 다변량 군집을 학습하지 않음; 월별 파일은 중복 집계군 평균'}])



if MARINE:
    # One row per source administrative unit. Heatmap and selected growth evidence stay distinct.
    mh_obs=mh.rename(columns={'marine_class':'heatmap_class'}).copy()
    mg_obs=mg[['admin_name','province','municipality','township','current_visitors','previous_visitors','source_ratio_pct','standard_yoy_pct','source_rank','marine_class']].rename(columns={'marine_class':'top5_class'})
    mobs=mh_obs.merge(mg_obs,on=['admin_name','province','municipality','township'],how='outer',validate='one_to_one')
    mobs['marine_class']=mobs.heatmap_class.combine_first(mobs.top5_class)
    mobs['class_conflict']=mobs.heatmap_class.notna() & mobs.top5_class.notna() & mobs.heatmap_class.ne(mobs.top5_class)
    mobs['evidence_kind']=np.select([
        mobs.heatmap_source_present.eq(True) & mobs.current_visitors.notna(),
        mobs.heatmap_source_present.eq(True) & mobs.area_visitors.notna(),
        mobs.heatmap_source_present.eq(True)],
        ['heatmap_and_selected_top5','heatmap','heatmap_metadata_only'],default='selected_top5')
    if mobs.class_conflict.any():raise ValueError('동일 읍면동의 해양 구분 충돌')
    save_csv(mobs,'marine_township_observations')
    # Candidate indexing avoids scanning all 3,564 areas for every place.
    # Aliases only standardize abbreviated spellings. Administrative mergers or
    # renamed districts are not inferred from similarity of names.
    province_aliases={
        '서울특별시':['서울특별시','서울'], '부산광역시':['부산광역시','부산'],
        '대구광역시':['대구광역시','대구'], '인천광역시':['인천광역시','인천'],
        '광주광역시':['광주광역시','광주'], '대전광역시':['대전광역시','대전'],
        '울산광역시':['울산광역시','울산'], '세종특별자치시':['세종특별자치시','세종'],
        '경기도':['경기도','경기'], '강원특별자치도':['강원특별자치도','강원도','강원'],
        '충청북도':['충청북도','충북'], '충청남도':['충청남도','충남'],
        '전북특별자치도':['전북특별자치도','전라북도','전북'],
        '전라남도':['전라남도','전남'], '경상북도':['경상북도','경북'],
        '경상남도':['경상남도','경남'], '제주특별자치도':['제주특별자치도','제주도','제주']}
    for p in mobs.province.unique():province_aliases.setdefault(p,[p])
    alias_to_province={a:p for p,aliases in province_aliases.items() for a in aliases}
    marine_town_index=defaultdict(list)
    for a in mobs.to_dict('records'):marine_town_index[a['township']].append(a)
    def marine_address_diagnosis(address):
        # Exact alphanumeric Korean tokens: 동/리/도로명 or renamed areas are not inferred.
        tokens=set(re.findall(r'[가-힣0-9]+',str(address)))
        explicit={alias_to_province[t] for t in tokens if t in alias_to_province}
        before=[]; found=[]; rejected=[]
        for town in tokens.intersection(marine_town_index):
            for a in marine_town_index[town]:
                if not set(a['municipality'].split()).issubset(tokens):continue
                before.append(a['admin_name'])
                if explicit and a['province'] not in explicit:
                    rejected.append(a['admin_name']);continue
                found.append(a['admin_name'])
        found=sorted(set(found))
        return {'candidates':found,'pre_province_candidate_count':len(set(before)),
                'province_rejected_count':len(set(rejected)),
                'province_rejected_candidates':' | '.join(sorted(set(rejected))),
                'address_province_labels':' | '.join(sorted(explicit)),
                'reason':'MATCH_CANDIDATE' if len(found)==1 else 'MULTIPLE_AREA_CANDIDATES' if len(found)>1
                         else 'PROVINCE_LABEL_CONFLICT' if rejected else 'NO_EXACT_MUNICIPALITY_TOWNSHIP_TOKENS'}
    def match_marine_address(address):return marine_address_diagnosis(address)['candidates']
    if places is not None:
        raw_key=next(c for c in ['id','ID','place_id'] if c in places_raw.columns)
        raw_address=places_raw.set_index(raw_key)['출처'].to_dict() if '출처' in places_raw else {}
        marine_places=places[['place_id','region','name','category','base_minutes','cluster_eligible']].copy()
        marine_places['address_source']=marine_places.place_id.map(raw_address).fillna('')
        address_diagnoses=marine_places.address_source.map(marine_address_diagnosis)
        candidates=address_diagnoses.map(lambda d:d['candidates'])
        audit=marine_places[['place_id','region','name','address_source']].copy()
        for col in ['pre_province_candidate_count','province_rejected_count','province_rejected_candidates','address_province_labels','reason']:
            audit[col]=address_diagnoses.map(lambda d:d[col])
        audit['candidate_count']=candidates.map(len)
        audit['candidate_admin_names']=candidates.map(lambda x:' | '.join(x))
        save_csv(audit,'marine_place_link_audit')
        marine_places['marine_match_status']=candidates.map(lambda a:'address_candidate' if len(a)==1 else 'ambiguous_address' if len(a)>1 else 'no_source_area_match')
        marine_places['marine_admin_name']=candidates.map(lambda a:a[0] if len(a)==1 else '')
        marine_places=marine_places.merge(mobs.add_prefix('marine_').rename(columns={'marine_marine_class':'marine_class'}),on='marine_admin_name',how='left',validate='many_to_one')
        marine_places['marine_admin_verified']=False
        marine_places['sea_theme_in_catalog']=marine_places.category.eq('sea')
        marine_places['marine_recommendation_bonus']=0.0
        marine_places['marine_stay_multiplier']=1.0
        marine_places['visitor_unit']='township_estimate_not_individual_place_visits'
        marine_places['monthly_context_scope']='national_group_reference_not_local_monthly_observation'
        save_csv(marine_places,'marine_place_evidence_all')
        save_csv(marine_places[marine_places.marine_match_status.eq('address_candidate')],'marine_place_candidates')
        marine_info['place_rows']=len(marine_places)
        marine_info['place_match_counts']={k:int(v) for k,v in marine_places.marine_match_status.value_counts().items()}
        marine_info['place_evidence_by_kind']={k:int(v) for k,v in marine_places.marine_evidence_kind.value_counts().items()}
        marine_info['catalog_sea_places']=int(marine_places.sea_theme_in_catalog.sum())
        coverage_by_region=marine_places.groupby('region').agg(
            place_rows=('place_id','size'),candidate_places=('marine_match_status',lambda x:int(x.eq('address_candidate').sum())),
            visitor_value_linked_places=('marine_area_visitors','count'))
        coverage_by_region['candidate_share']=coverage_by_region.candidate_places/coverage_by_region.place_rows
        save_csv(coverage_by_region.reset_index(),'marine_place_coverage_by_region')
        marine_info['place_regions_with_candidates']=int(coverage_by_region.candidate_places.gt(0).sum())
        marine_info['place_value_linked_rows']=int(marine_places.marine_area_visitors.notna().sum())
        marine_info['place_missing_value_linked_rows']=int((marine_places.marine_match_status.eq('address_candidate') & marine_places.marine_evidence_kind.eq('heatmap_metadata_only')).sum())
        marine_info['place_province_conflict_rows']=int(audit.reason.eq('PROVINCE_LABEL_CONFLICT').sum())
        marine_info['place_any_province_rejection_rows']=int(audit.province_rejected_count.gt(0).sum())

        fig,ax=plt.subplots(figsize=(8,4));counts=marine_places.marine_match_status.value_counts()
        ax.barh(counts.index,counts.values,color=['#929292','#B87998','#78618E'][:len(counts)])
        for j,v in enumerate(counts):ax.text(v+10,j,str(v),va='center')
        ax.set(title='Marine source area linkage to place catalogue',xlabel='Place rows (candidate links require boundary review)');ax.set_xlim(0,counts.max()*1.18);finish(fig,'33_marine_place_coverage')
        if city is not None:
            marine_stop_links=stops.merge(marine_places[['place_id','marine_admin_name','marine_match_status','marine_class','marine_evidence_kind']],left_on='place_id_candidate',right_on='place_id',how='left',validate='many_to_one')
            marine_stop_links=marine_stop_links[marine_stop_links.marine_match_status.eq('address_candidate')].copy()
            marine_stop_links['marine_link_verified']=False
            marine_stop_links['link_chain']='unverified_stop_candidate + address_token_candidate'
            save_csv(marine_stop_links,'marine_course_stop_candidates')
            marine_courses=course_table[['course_id','region','name','parsed_stop_count','cluster_eligible']].copy()
            gr=marine_stop_links.groupby('course_id')
            marine_courses['marine_candidate_slots']=marine_courses.course_id.map(gr.size()).fillna(0).astype(int)
            marine_courses['marine_candidate_unique_places']=marine_courses.course_id.map(gr.place_id.nunique()).fillna(0).astype(int)
            marine_courses['marine_observed_area_candidates']=marine_courses.course_id.map(gr.marine_admin_name.agg(lambda a:' | '.join(sorted(set(a))))).fillna('')
            marine_courses['marine_link_verified']=False
            marine_courses['marine_recommendation_bonus']=0.0;marine_courses['marine_stay_multiplier']=1.0
            save_csv(marine_courses,'marine_course_evidence_all')
            marine_info['course_rows']=len(marine_courses);marine_info['course_candidate_count']=int(marine_courses.marine_candidate_slots.gt(0).sum());marine_info['course_candidate_slots']=len(marine_stop_links)
            regional_courses=marine_courses.groupby('region').agg(course_rows=('course_id','size'),
                candidate_courses=('marine_candidate_slots',lambda x:int(x.gt(0).sum())),candidate_slots=('marine_candidate_slots','sum'))
            save_csv(regional_courses.reset_index(),'marine_course_coverage_by_region')

    def explain_marine_place(place_id,month):
        if marine_places is None:raise ValueError('장소 CSV가 필요합니다.')
        rows=marine_places[marine_places.place_id.eq(str(place_id))]
        if len(rows)!=1:raise ValueError('장소 ID를 확인하세요: '+str(place_id))
        a=rows.iloc[0]
        result={'place_id':a.place_id,'place_name':a['name'],'catalog_category':a.category,'source_admin_candidate':a.marine_admin_name or None,'admin_match_status':a.marine_match_status,'admin_link_verified':False,'marine_class':a.marine_class if pd.notna(a.marine_class) else None,'is_place_visit_count':False,'township_snapshot_period':'not_encoded_in_csv; check original download period','monthly_reference_scope':'national group for requested observed month, not township time series','recommendation_bonus':0.0,'stay_multiplier':1.0}
        if pd.notna(a.marine_area_visitors):result['township_heatmap_visitors']=float(a.marine_area_visitors)
        if pd.notna(a.marine_standard_yoy_pct):result['selected_top5_standard_yoy_pct']=float(a.marine_standard_yoy_pct)
        ref=mi[mi.month.eq(str(month)) & mi.group.eq(result['marine_class'])]
        result['month']=str(month);result['monthly_reference_status']='available_observed_national_group' if len(ref) else 'unavailable_no_forecast'
        if len(ref):
            b=ref.iloc[0];result['national_group_period_mean_index']=float(b.period_mean_index);result['national_group_vs_noncoastal_index']=float(b.relative_to_noncoastal_index)
        return result
    marine_examples=[]
    if marine_places is not None:
        for pid in ['ro7','nax623','ctt142','ro9','gj1','gjx9','gz1','gz11']:
            if marine_places.place_id.eq(pid).any():marine_examples.append(explain_marine_place(pid,expected[-1]))
        (RUN_DIR/'marine_explanation_examples.json').write_text(json.dumps(marine_examples,ensure_ascii=False,indent=2),encoding='utf-8')
        show_table(pd.DataFrame(marine_examples),10)



# Search counts describe the supplied ranked list, not visits or unlisted zeros.
marine_search_info={'status':'not_supplied','score_bonus':0.0,'stay_multiplier':1.0}
if MARINE and 'search_rank' in MARINE:
    ms=MARINE['search_rank'].rename(columns={'순위':'source_rank','관광지명':'source_name','도로명':'source_address','분류':'source_category','검색 건수':'search_count'}).copy()
    for col in ['source_rank','search_count']:
        ms[col]=numeric_checked(ms[col],'marine search '+col)
        if (ms[col]%1!=0).any():raise ValueError('검색 순위와 건수는 정수여야 합니다.')
        ms[col]=ms[col].astype(int)
    if ms.source_rank.le(0).any() or ms.source_rank.duplicated().any():raise ValueError('검색 순위는 고유한 양의 정수여야 합니다.')
    for col in ['source_name','source_address','source_category']:
        ms[col]=ms[col].astype(str).str.strip()
        if ms[col].eq('').any():raise ValueError('검색 목록 필수 텍스트 공란: '+col)
    if ms.duplicated(['source_name','source_address']).any():raise ValueError('검색 관광지명과 주소 중복')
    ms=ms.sort_values('source_rank').reset_index(drop=True)
    ms['search_id']=ms.source_rank.map(lambda x:f'MSR{x:04d}')
    ms['name_key']=ms.source_name.map(norm_name)
    ms['scope']=INPUT_META['marine_search_rank'].get('declared_scope','not_encoded_in_csv')
    ms['period_status']='not_encoded_in_csv'
    ms['is_visit_count']=False
    if not ms.search_count.is_monotonic_decreasing:
        marine_flags.append({'check':'search_rank_order','status':'review','detail':'원본 순위와 검색 건수 내림차순이 다름; 원본 순위 유지'})
    search_alias=dict(alias_to_province)
    # This is only a spelling alias seen in the supplied source, not an old/new boundary crosswalk.
    search_alias.update({'전남광주':'전남광주통합특별시','전남광주통합특별시':'전남광주통합특별시'})
    def search_address_parts(address):
        words=re.findall(r'[가-힣A-Za-z0-9]+',str(address))
        province=search_alias.get(words[0],words[0]) if words else ''
        local=[]
        for w in words[1:]:
            if re.fullmatch(r'[가-힣]+[시군구]',w):local.append(w)
            else:break
        return province,local
    source_parts=ms.source_address.map(search_address_parts)
    ms['source_province']=source_parts.map(lambda x:x[0])
    ms['source_municipality']=source_parts.map(lambda x:' '.join(x[1]))
    ms['road_address_detail_present']=ms.source_address.map(lambda s:bool(re.search(r'[가-힣A-Za-z0-9]+(?:대로|로|길)(?:\s|$)',s)))
    save_csv(ms,'marine_search_rank_clean')
    search_class_summary=ms.groupby('source_category').agg(listed_poi_count=('search_id','size'),listed_search_count=('search_count','sum'),best_source_rank=('source_rank','min')).reset_index()
    total_search=ms.search_count.sum()
    search_class_summary['share_of_listed_searches_pct']=100*search_class_summary.listed_search_count/total_search if total_search>0 else np.nan
    search_class_summary=search_class_summary.sort_values('listed_search_count',ascending=False)
    save_csv(search_class_summary,'marine_search_class_summary')
    marine_search_info.update({'status':'loaded','rows':len(ms),'source_categories':int(ms.source_category.nunique()),'source_rank_min':int(ms.source_rank.min()),'source_rank_max':int(ms.source_rank.max()),'listed_search_count':int(total_search),'scope':ms.scope.iloc[0] if len(ms) else 'empty','period_in_csv':False,'is_visit_count':False,'nonlisted_values_imputed':False})

    fig,ax=plt.subplots(figsize=(10,7))
    top=ms.head(20).iloc[::-1]
    ax.barh(top.source_name,top.search_count/1e3,color='#A25F86')
    ax.set(title='Coastal search list: first 20 source ranks',xlabel='Search events / thousand (not visitors)')
    ax.tick_params(axis='y',labelsize=9)
    for i,row in enumerate(top.itertuples()):ax.text(row.search_count/1e3+10,i,f'#{row.source_rank}',va='center',fontsize=8)
    ax.set_xlim(0,max(1,top.search_count.max()/1e3)*1.12)
    finish(fig,'37_marine_search_top20')
    fig,axs=plt.subplots(1,2,figsize=(12,7))
    cat=search_class_summary.iloc[::-1]
    axs[0].barh(cat.source_category,cat.listed_poi_count,color='#78618E')
    axs[0].set(title='POIs in the supplied list',xlabel='Listed POI count')
    axs[1].barh(cat.source_category,cat.listed_search_count/1e6,color='#A25F86')
    axs[1].set(title='Search events within the supplied list',xlabel='Listed searches / million')
    for ax in axs:ax.tick_params(axis='y',labelsize=9)
    finish(fig,'38_marine_search_category_composition')

    def assess_search_region(source,place):
        tokens=set(re.findall(r'[가-힣A-Za-z0-9]+',str(place['address_source'])))
        region=str(place['region']).strip()
        explicit={search_alias[t] for t in tokens if t in search_alias}
        # Province-qualified catalogue labels, such as 고성(강원), keep their province.
        region_parts=re.findall(r'[가-힣A-Za-z0-9]+',region)
        explicit.update(search_alias[t] for t in region_parts if t in search_alias)
        if explicit and source.source_province not in explicit:return False,'PROVINCE_CONFLICT'
        src_local=source.source_municipality.split()
        for ending in ['시','군','구']:
            src={x for x in src_local if x.endswith(ending)}
            dst={x for x in tokens if re.fullmatch(r'[가-힣]+[시군구]',x) and x.endswith(ending) and x not in search_alias}
            if src and dst and not src.intersection(dst):return False,'MUNICIPALITY_CONFLICT'
        normalized_region=norm_region(region_parts[0]) if region_parts else ''
        municipality_match=any(normalized_region==norm_region(x) for x in src_local)
        metro_match=region in search_alias and search_alias[region]==source.source_province
        address_match=bool(src_local) and set(src_local).issubset(tokens)
        if not (municipality_match or metro_match or address_match):return False,'REGION_NOT_CONFIRMED'
        return True,'EXACT_NAME_REGION_CANDIDATE'

    if places is not None:
        raw_key=next(c for c in ['id','ID','place_id'] if c in places_raw.columns)
        addr=places_raw.set_index(raw_key)['출처'].to_dict() if '출처' in places_raw else {}
        catalogue=places[['place_id','region','name','category','cluster_eligible']].copy()
        catalogue['address_source']=catalogue.place_id.map(addr).fillna('')
        catalogue['name_key']=catalogue['name'].map(norm_name)
        name_index={k:g.to_dict('records') for k,g in catalogue.groupby('name_key')}
        audit=[];links=[]
        for source in ms.itertuples(index=False):
            name_matches=name_index.get(source.name_key,[]);accepted=[];rejected=[]
            for place in name_matches:
                ok,why=assess_search_region(source,place)
                if ok:accepted.append(place['place_id'])
                else:rejected.append({'place_id':place['place_id'],'reason':why})
            status='NAME_REGION_CANDIDATE' if len(accepted)==1 else 'AMBIGUOUS_CATALOGUE_MATCH' if len(accepted)>1 else 'NAME_FOUND_REGION_REJECTED' if name_matches else 'NO_EXACT_NAME'
            audit.append({'search_id':source.search_id,'source_rank':source.source_rank,'source_name':source.source_name,'source_address':source.source_address,'exact_name_candidates':len(name_matches),'eligible_region_candidates':len(accepted),'candidate_place_ids':' | '.join(accepted),'rejected_candidates':json.dumps(rejected,ensure_ascii=False),'status':status,'identity_verified':False})
            if len(accepted)==1:links.append({'search_id':source.search_id,'place_id':accepted[0],'search_match_status':status})
        search_audit=pd.DataFrame(audit)
        links=pd.DataFrame(links,columns=['search_id','place_id','search_match_status'])
        # Several listed entities mapping to one catalogue ID require review, never best-rank selection.
        repeated=links.place_id.duplicated(keep=False)
        if repeated.any():
            search_audit.loc[search_audit.search_id.isin(links.loc[repeated,'search_id']),'status']='MULTIPLE_SOURCE_ENTITIES_FOR_PLACE'
            links=links[~repeated].copy()
        save_csv(search_audit,'marine_search_rank_match_audit')
        evidence=links.merge(ms,on='search_id',how='left',validate='one_to_one').merge(catalogue.drop(columns='name_key'),on='place_id',how='left',validate='one_to_one')
        evidence['search_identity_verified']=False
        save_csv(evidence,'marine_search_place_candidates')
        selected=links.merge(ms[['search_id','source_rank','search_count','source_name','source_address','source_category']],on='search_id',how='left',validate='one_to_one')
        search_places=catalogue.merge(selected,on='place_id',how='left',validate='one_to_one')
        search_places['search_match_status']=search_places.search_match_status.fillna('NOT_LISTED_OR_UNRESOLVED')
        search_places['search_identity_verified']=False
        search_places['search_score_bonus']=0.0
        search_places['search_stay_multiplier']=1.0
        save_csv(search_places,'marine_search_place_evidence_all')
        marine_search_info.update({'matched_catalogue_places':len(links),'rank_status_counts':{k:int(v) for k,v in search_audit.status.value_counts().items()},'unlinked_catalogue_rows':int(search_places.source_rank.isna().sum())})
        if city is not None:
            search_stops=stops.merge(selected,left_on='place_id_candidate',right_on='place_id',how='inner',validate='many_to_one')
            search_stops['search_identity_verified']=False
            search_stops['link_chain']='unverified_route_place_candidate + unverified_name_region_candidate'
            save_csv(search_stops,'marine_search_course_stop_candidates')
            course_search=course_table[['course_id','region','name','parsed_stop_count','cluster_eligible']].copy()
            agg=search_stops.groupby('course_id').agg(search_candidate_slots=('search_id','size'),search_unique_listed_pois=('search_id','nunique'),best_listed_source_rank=('source_rank','min'),listed_poi_names=('source_name',lambda s:' | '.join(sorted(set(s))))).reset_index()
            course_search=course_search.merge(agg,on='course_id',how='left',validate='one_to_one')
            for col in ['search_candidate_slots','search_unique_listed_pois']:course_search[col]=course_search[col].fillna(0).astype(int)
            course_search['listed_poi_names']=course_search.listed_poi_names.fillna('')
            course_search['search_link_verified']=False
            course_search['search_score_bonus']=0.0;course_search['search_stay_multiplier']=1.0
            save_csv(course_search,'marine_search_course_evidence_all')
            marine_search_info.update({'course_candidates':int(course_search.search_candidate_slots.gt(0).sum()),'course_stop_candidate_rows':len(search_stops)})
        assert len(search_places)==len(places_raw)
        assert search_places.loc[search_places.search_match_status.eq('NOT_LISTED_OR_UNRESOLVED'),['source_rank','search_count']].isna().all().all()
        assert not evidence.search_identity_verified.any()
    marine_flags.append({'check':'search_scope','status':'selected_list_context_only','detail':f'선택 검색순위 {len(ms)}행; 검색 건수는 방문자 수 아님; 미등재는 0으로 대체하지 않음'})
    show_table(ms[['source_rank','source_name','source_category','search_count']],10)
RUN_SUMMARY['marine_search']=marine_search_info
print('검색순위 적용',json.dumps(marine_search_info,ensure_ascii=False,indent=2))


if MARINE:
    assert not mt.duplicated(['month','group']).any()
    assert len(mh)==len(MARINE['heatmap']) and not mh.admin_name.duplicated().any()
    assert mh.loc[mh.visitor_value_missing,'area_visitors'].isna().all()
    assert mh.loc[~mh.visitor_value_missing,'area_visitors'].ge(0).all()
    assert int(national_group.source_rows.sum())==len(mh)
    assert int(national_group.valid_visitor_rows.sum())==int(mh.area_visitors.notna().sum())
    assert len(mi)==len(mt)
    assert np.allclose(mi.groupby('group').period_mean_index.mean(),100)
    assert marine_info['new_marine_clustering_fitted'] is False
    if marine_places is not None:
        assert len(marine_places)==len(places_raw)
        assert not marine_places.marine_admin_verified.any()
        assert marine_places.marine_recommendation_bonus.eq(0).all()
        assert marine_places.marine_stay_multiplier.eq(1).all()
    if marine_courses is not None:assert len(marine_courses)==len(cities_raw)
    marine_flags.append({'check':'heatmap_missing_visitors','status':'preserved',
                         'detail':f'결측 {mh.visitor_value_missing.sum()}행 보존; 방문자 수 0 대체 없음'})
    marine_flags.append({'check':'admin_labels','status':'review',
                         'detail':'원본 광역·시군구 표기를 보존하고 미검증 개편 명칭은 자동 치환하지 않음; 충돌 후보는 audit에 기록'})
    marine_flags.append({'check':'admin_link' ,'status':'candidate_only','detail':'출처 주소의 시군구·읍면동 토큰 후보 연결; 행정동 코드·경계 검증 미완료'})
    save_csv(pd.DataFrame(marine_flags),'marine_quality_flags')
    fields=[
        ['period_mean_index','100 × 해당 월 평균 / 관측 기간 월평균의 평균','지수','반복 계절성·미래값 아님'],
        ['relative_to_noncoastal_index','100 × 해당 집계군 월평균 / 같은 월 비연안 평균','지수','지역 총량이나 1인당 소비 아님'],
        ['standard_yoy_pct','100 × (현재−전년) / 전년','%','전년 값 0이면 결측'],
        ['current_denominator_pct','100 × (현재−전년) / 현재','%','원본 비율의 분모 검증용'],
        ['marine_admin_name','출처 주소에서 찾은 시군구+읍면동 후보','이름','행정 경계 확인 전 잠정'],
        ['marine_area_visitors','히트맵 원본 읍면동 방문 추정값','방문 추정값','장소 자체 방문자 수 아님'],
        ['search_count','검색순위 CSV의 검색 건수','검색 건수','방문자 수·미등재 0점으로 해석하지 않음'],
        ['best_listed_source_rank','연결된 검색 목록 경유지 중 원본 순위 최솟값','순위','코스 인기 순위가 아니며 미연결은 결측'],
        ['marine_recommendation_bonus','0','점','검증 전 개인 적합도에 미반영'],
        ['marine_stay_multiplier','1','배','체류시간 관측값 없음']]
    save_csv(pd.DataFrame(fields,columns=['field','formula_or_source','unit','interpretation']),'marine_field_dictionary')
    (RUN_DIR/'marine_summary.json').write_text(json.dumps(marine_info,ensure_ascii=False,indent=2),encoding='utf-8')
    RUN_SUMMARY['marine']=marine_info
    print('해양 확장 완료',json.dumps(marine_info,ensure_ascii=False,indent=2))


# This module is embedded in the delivered notebook. No external import is needed.
from sklearn.metrics import silhouette_samples
from sklearn.metrics.pairwise import cosine_similarity

COSINE_RESULTS = {}
COSINE_COMPARISONS = []

def unit_rows(X, eps=1e-12):
    X = np.asarray(X, dtype=float)
    if X.ndim != 2 or not np.isfinite(X).all():
        raise ValueError('코사인 입력은 결측이 없는 2차원 수치 배열이어야 합니다.')
    norms = np.linalg.norm(X, axis=1)
    valid = norms > eps
    return X[valid] / norms[valid, None], valid, norms

def spherical_kmeans(U, k, seed=42, n_init=20, max_iter=200):
    """Unit data AND unit centroids; maximizes sum of assigned cosine similarities.

    Reject collapsed or nonconverged starts. A successful start must reach a
    label fixed point. A plain data bundle, not a custom class, is serialized.
    """
    U = np.asarray(U, float)
    if not np.allclose(np.linalg.norm(U, axis=1), 1, atol=1e-10):
        raise ValueError('구면 K-means에는 길이 1인 행만 입력합니다.')
    if k < 2 or k > len(np.unique(U.round(12), axis=0)):
        raise ValueError('군집 수가 유효한 서로 다른 방향 수를 벗어납니다.')
    rng = np.random.default_rng(seed)
    best = None; rejected = 0
    for restart in range(n_init):
        chosen = [int(rng.integers(len(U)))]; centers = [U[chosen[0]].copy()]
        # Squared chord distance is 2 * (1 - cosine). Constant 2 cancels.
        for _ in range(1, k):
            d = np.clip(1 - (U @ np.array(centers).T).max(axis=1), 0, 2)
            d[chosen] = 0
            d[d < 1e-12] = 0
            if d.sum() <= 0: break
            j = int(rng.choice(len(U), p=d/d.sum()))
            chosen.append(j); centers.append(U[j].copy())
        if len(centers) != k:
            rejected += 1; continue
        C = np.array(centers); labels = (U @ C.T).argmax(axis=1)
        history = [float((U * C[labels]).sum())]
        converged = False
        for iteration in range(max_iter):
            counts = np.bincount(labels, minlength=k)
            if np.any(counts == 0): break
            sums = np.zeros((k, U.shape[1])); np.add.at(sums, labels, U)
            lengths = np.linalg.norm(sums, axis=1)
            if np.any(lengths <= 1e-12): break
            C = sums / lengths[:, None]
            new_labels = (U @ C.T).argmax(axis=1)
            objective = float((U * C[new_labels]).sum())
            if objective + 1e-8 < history[-1]:
                raise AssertionError('구면 목적함수가 감소했습니다.')
            history.append(objective)
            if np.array_equal(new_labels, labels):
                converged = True; labels = new_labels; break
            labels = new_labels
        if not converged:
            rejected += 1; continue
        if best is None or objective > best['objective'] + 1e-10:
            best = {'labels': labels.copy(), 'centers': C.copy(), 'objective': objective,
                    'n_iter': iteration + 1, 'history': history, 'restart': restart}
    if best is None:
        raise RuntimeError(f'k={k}, seed={seed}: 수렴한 초기화가 없습니다. 입력 방향과 k를 점검하세요.')
    best['rejected_starts'] = rejected
    return best

def fit_cosine_extension(base, prefix, k_max=10, min_share=.02):
    # Reuse exactly the baseline weighted features. No PCA centering here.
    F = base['F']; X = F.to_numpy(float)
    U, valid, norms = unit_rows(X)
    kept = np.flatnonzero(valid); index = F.index[valid]
    exclusion = pd.DataFrame({'source_index': F.index, 'norm': norms,
                              'cosine_eligible': valid,
                              'reason': np.where(valid, 'ELIGIBLE', 'ZERO_VECTOR')})
    save_csv(exclusion, prefix+'_cosine_eligibility')
    max_k = min(k_max, len(U)-1, len(np.unique(U.round(12), axis=0))-1)
    if max_k < 2:
        print(prefix, '코사인 분석 생략: 서로 다른 비영 방향이 3개 미만입니다.'); return None
    sample = np.sort(np.random.default_rng(SEEDS[0]).choice(len(U), min(len(U), SILHOUETTE_SAMPLE), replace=False))
    Dc = np.clip(1 - U[sample] @ U[sample].T, 0, 2); np.fill_diagonal(Dc, 0)
    De = pairwise_distances(X[valid][sample]); np.fill_diagonal(De, 0)
    def sil(labels, D):
        q = labels[sample]
        return float(silhouette_score(D, q, metric='precomputed')) if 1 < len(np.unique(q)) < len(q) else np.nan
    rows = []; fitted = {}
    with threadpool_limits(limits=1):
        for k in range(2, max_k+1):
            for mode in ['pca_euclidean_control', 'spherical_cosine']:
                labs = []; cos_values = []; eu_values = []; sizes = []; objectives = []; rejects = []
                for seed in SEEDS:
                    if mode == 'spherical_cosine':
                        fit = spherical_kmeans(U, k, seed, COSINE_N_INIT, COSINE_MAX_ITER)
                        labels = fit['labels']; objectives.append(fit['objective']/len(U)); rejects.append(fit['rejected_starts'])
                        fitted[(k, seed)] = fit
                    else:
                        labels = KMeans(n_clusters=k, n_init=N_INIT, random_state=seed, algorithm='lloyd').fit_predict(base['Z'][valid])
                    labs.append(labels); cos_values.append(sil(labels, Dc)); eu_values.append(sil(labels, De))
                    sizes.append(np.bincount(labels, minlength=k).min()/len(U))
                ari = min(adjusted_rand_score(a,b) for a,b in itertools.combinations(labs,2))
                rows.append({'model':mode,'k':k,'cosine_silhouette_mean':np.nanmean(cos_values),
                             'cosine_silhouette_sd':np.nanstd(cos_values),'euclidean_silhouette_mean':np.nanmean(eu_values),
                             'seed_ari_min':ari,'min_cluster_share':min(sizes),
                             'mean_assigned_cosine':np.mean(objectives) if objectives else np.nan,
                             'rejected_starts':sum(rejects),
                             'passes_gates':bool(ari>=MIN_SEED_ARI and min(sizes)>=min_share)})
    candidates = pd.DataFrame(rows)
    spherical = candidates[candidates.model.eq('spherical_cosine')]
    pool = spherical[spherical.passes_gates]; qualified = not pool.empty
    if pool.empty: pool = spherical
    selected = pool.sort_values(['cosine_silhouette_mean','k'], ascending=[False,True]).iloc[0]
    k = int(selected.k); final = fitted[(k, SEEDS[0])]
    order = sorted(range(k), key=lambda lab:tuple(X[valid][final['labels']==lab].mean(axis=0).round(10)))
    label_map = {old:f'{prefix}C{j+1:02d}' for j,old in enumerate(order)}
    names = np.array([label_map[x] for x in final['labels']]); centers = final['centers'][order]
    similarities = U @ centers.T
    top = np.sort(similarities,axis=1)
    baseline_labels = np.asarray(base['labels'])[valid]
    assignments = pd.DataFrame({'source_index':index,'baseline_cluster':baseline_labels,'cosine_cluster':names,
                                'assigned_cosine':top[:,-1], 'margin_to_second':top[:,-1]-top[:,-2]})
    ss = silhouette_samples(Dc, final['labels'][sample], metric='precomputed')
    sample_table = assignments.iloc[sample].copy(); sample_table['cosine_silhouette']=ss
    cross = pd.crosstab(assignments.baseline_cluster, assignments.cosine_cluster)
    for method, labels in [('baseline_selected',baseline_labels),('cosine_selected',final['labels'])]:
        COSINE_COMPARISONS.append({'dataset':prefix,'model':method,'k':len(np.unique(labels)),
                                  'n':len(U),'sample_n':len(sample),
                                  'cosine_silhouette':sil(labels,Dc),'euclidean_silhouette':sil(labels,De)})
    info = {'rows':len(U),'excluded_zero_vectors':int((~valid).sum()),'features':F.columns.tolist(),
            'k':k,'search_max_k':max_k,'at_search_upper_bound':k==max_k,
            'cosine_silhouette_mean':float(selected.cosine_silhouette_mean),
            'cosine_silhouette_final_seed':float(ss.mean()),'negative_silhouette_share':float((ss<0).mean()),
            'seed_ari_min':float(selected.seed_ari_min),'min_cluster_share_across_seeds':float(selected.min_cluster_share),
            'passes_gates':qualified,'min_share_required':min_share,'sample_n':len(sample),
            'ari_vs_baseline':float(adjusted_rand_score(baseline_labels,names)),
            'mean_assigned_cosine':float(top[:,-1].mean()),'mean_assignment_margin':float((top[:,-1]-top[:,-2]).mean()),
            'iterations':final['n_iter'],'final_seed':SEEDS[0],
            'fit_space':'L2-normalized baseline weighted features; no PCA centering',
            'status':'QUALIFIED_EXPLORATORY' if qualified else 'EXPLORATORY_GATES_FAILED'}
    save_csv(candidates,prefix+'_cosine_candidates')
    save_csv(assignments,prefix+'_cosine_assignments')
    save_csv(sample_table,prefix+'_cosine_silhouette_samples')
    save_csv(cross.reset_index(),prefix+'_baseline_cosine_transition')
    save_csv(pd.DataFrame(centers,columns=F.columns).assign(cosine_cluster=[label_map[j] for j in order]),prefix+'_cosine_centers')
    save_csv(pd.DataFrame(U,index=index,columns=F.columns).rename_axis('source_index').reset_index(),prefix+'_cosine_unit_features')
    save_csv(pd.DataFrame({'iteration':range(len(final['history'])),'cosine_objective':final['history']}),prefix+'_cosine_objective')
    # Portable bundle with only standard arrays, dicts, numbers and strings.
    preprocess = joblib.load(MODELS/f'{prefix}_pca_kmeans.joblib')['preprocess']
    joblib.dump({'method':'spherical-cosine-1.0','features':F.columns.tolist(),'preprocess':preprocess,
                 'centers':centers,'cluster_names':[label_map[j] for j in order],
                 'normalization':'row L2; reject norm <= 1e-12','summary':info},MODELS/f'{prefix}_spherical_cosine.joblib')
    # Same baseline PCA projection for direct visual comparison; never used to fit cosine model.
    xy = base['pcs'].loc[index].iloc[:,:2].to_numpy()
    if xy.shape[1]==1: xy=np.column_stack([xy[:,0],np.zeros(len(xy))])
    fig,axs=plt.subplots(1,2,figsize=(11,4))
    for mode,col,label in [('pca_euclidean_control','#78618E','PCA Euclidean'),('spherical_cosine','#AD4772','Spherical cosine')]:
        q=candidates[candidates.model.eq(mode)]
        axs[0].errorbar(q.k,q.cosine_silhouette_mean,yerr=q.cosine_silhouette_sd,marker='o',color=col,label=label)
        axs[1].plot(q.k,q.seed_ari_min,'o-',color=col,label=label)
    axs[0].set(title=f'{prefix}: common cosine-distance evaluation',xlabel='k',ylabel='Mean silhouette');axs[0].axvline(k,color='#555',ls=':')
    axs[1].set(title='Stability across seeds',xlabel='k',ylabel='Minimum ARI',ylim=(-.05,1.05));axs[1].axhline(MIN_SEED_ARI,color='#555',ls='--')
    for ax in axs:ax.legend(frameon=False);ax.set_xticks(range(2,max_k+1))
    finish(fig,f'C_{prefix}_01_model_comparison')
    fig,axs=plt.subplots(1,2,figsize=(12,4.8))
    for ax,lab,title in [(axs[0],baseline_labels,'Baseline PCA K-means'),(axs[1],names,'Spherical cosine')]:
        frame=pd.DataFrame({'x':xy[:,0].round(8),'y':xy[:,1].round(8),'label':lab})
        counts=frame.groupby(['x','y','label']).size().reset_index(name='n')
        for j,g in enumerate(sorted(set(lab))):
            q=counts[counts.label.eq(g)];ax.scatter(q.x,q.y,s=14+2*q.n,alpha=.65,label=g,color=PALETTE[j%len(PALETTE)],edgecolors='white',linewidth=.2)
        ax.set(title=title,xlabel='Baseline PC1',ylabel='Baseline PC2');ax.legend(fontsize=7,frameon=False,ncol=2)
    fig.suptitle(f'{prefix}: same PCA projection; cosine fit uses original weighted directions',fontsize=11)
    finish(fig,f'C_{prefix}_02_pca_projection')
    fig,ax=plt.subplots(figsize=(8,5));bottom=0;ticks=[];ticklabels=[]
    for j,g in enumerate(sorted(set(names))):
        values=np.sort(ss[names[sample]==g]); y=np.arange(bottom,bottom+len(values))
        ax.fill_betweenx(y,0,values,color=PALETTE[j%len(PALETTE)],alpha=.85)
        ticks.append(bottom+len(values)/2);ticklabels.append(g);bottom+=len(values)+max(2,len(sample)//100)
    ax.axvline(ss.mean(),color='#333',ls='--',label=f'Mean {ss.mean():.3f}')
    ax.set(yticks=ticks,yticklabels=ticklabels,xlim=(-1,1),xlabel='Cosine silhouette',title=f'{prefix}: final seed, sample n={len(sample)}');ax.legend(frameon=False)
    finish(fig,f'C_{prefix}_03_silhouette')
    fig,ax=plt.subplots(figsize=(8,5));im=ax.imshow(cross,cmap='Purples',aspect='auto')
    ax.set(xticks=np.arange(len(cross.columns)),xticklabels=cross.columns,yticks=np.arange(len(cross)),yticklabels=cross.index,
           xlabel='Cosine cluster',ylabel='Baseline cluster',title=f'{prefix}: assignment transition (counts)')
    for i in range(len(cross)):
        for j in range(len(cross.columns)):ax.text(j,i,str(cross.iloc[i,j]),ha='center',va='center',fontsize=8,color='white' if cross.iloc[i,j]>cross.to_numpy().max()*.55 else 'black')
    fig.colorbar(im,ax=ax,label='Records');finish(fig,f'C_{prefix}_04_transition')
    fig,ax=plt.subplots(figsize=(9,5));im=ax.imshow(centers,cmap='RdBu_r',vmin=-1,vmax=1,aspect='auto')
    ax.set(xticks=np.arange(len(F.columns)),xticklabels=F.columns,yticks=np.arange(k),yticklabels=[label_map[j] for j in order],title=f'{prefix}: unit centroid coordinates')
    ax.tick_params(axis='x',rotation=45);fig.colorbar(im,ax=ax,label='Weighted direction coordinate');finish(fig,f'C_{prefix}_05_centroids')
    assert np.allclose(np.linalg.norm(centers,axis=1),1)
    assert np.array_equal(np.array([label_map[j] for j in order])[similarities.argmax(axis=1)],names)
    assert np.all(np.diff(final['history']) >= -1e-8)
    print(prefix,json.dumps(info,ensure_ascii=False,indent=2))
    result={'assignments':assignments,'summary':info,'centers':centers,'U':U,'index':index,'candidates':candidates}
    COSINE_RESULTS[prefix]=result;return result

if place_model is not None:
    fit_cosine_extension(place_model,'G',K_MAX,MIN_CLUSTER_SHARE)
if city_model is not None:
    fit_cosine_extension(city_model,'T',K_MAX,MIN_CLUSTER_SHARE)

# Full original-row outputs and interpretable profiles, without overwriting G/T labels.
for prefix,base_raw,clean,name in [('G',places_raw,places,'G_places_with_cosine_all'),('T',cities_raw,globals().get('course_table'),'T_citytours_with_cosine_all')]:
    if prefix not in COSINE_RESULTS:continue
    a=COSINE_RESULTS[prefix]['assignments'].set_index('source_index')
    full=pd.concat([base_raw,clean.add_prefix('baseline_')],axis=1).join(a.add_prefix('cosine_'))
    save_csv(full,name)
    interpretation=clean.loc[a.index].join(a[['cosine_cluster','assigned_cosine','margin_to_second']])
    if prefix=='G':
        profiles=interpretation.groupby('cosine_cluster').agg(n=('place_id','size'),base_minutes_median=('base_minutes','median'),unesco_mark_rate=('unesco_mark','mean'))
        profiles=profiles.join(pd.crosstab(interpretation.cosine_cluster,interpretation.category,normalize='index').reindex(columns=CATEGORIES,fill_value=0))
    else:
        profiles=interpretation.groupby('cosine_cluster')[[f'share_{c}' for c in CATEGORIES]+['visit_candidate_count','category_coverage','night_flag']].mean()
        profiles.insert(0,'n',interpretation.groupby('cosine_cluster').size())
    save_csv(profiles.reset_index(),prefix+'_cosine_profiles')
    representative=interpretation.sort_values(['cosine_cluster','assigned_cosine'],ascending=[True,False]).groupby('cosine_cluster').head(3)
    save_csv(representative.reset_index(),prefix+'_cosine_representatives')

cosine_comparison=pd.DataFrame(COSINE_COMPARISONS)
if len(cosine_comparison):
    save_csv(cosine_comparison,'cosine_baseline_comparison');show_table(cosine_comparison,20)
    fig,axs=plt.subplots(1,2,figsize=(10,4))
    for ax,metric,title in [(axs[0],'cosine_silhouette','Common cosine distances'),(axs[1],'euclidean_silhouette','Common Euclidean distances')]:
        pivot=cosine_comparison.pivot(index='dataset',columns='model',values=metric)
        pivot.plot.bar(ax=ax,color=['#78618E','#AD4772']);ax.set(title=title,ylabel='Silhouette',xlabel='Dataset');ax.tick_params(axis='x',rotation=0);ax.legend(['Baseline selected','Cosine selected'],fontsize=8,frameon=False)
    finish(fig,'C_all_metrics_comparison')
RUN_SUMMARY['cosine']={k:v['summary'] for k,v in COSINE_RESULTS.items()}


# Survey-to-course cosine score. This is a separate candidate-ranking component.
SURVEY_FIELDS = [f'q_{c}' for c in CATEGORIES]
SURVEY_QUESTIONS = [
    '역사 유적과 전통문화를 얼마나 즐기고 싶나요?',
    '숲과 자연경관에서 쉬는 여행을 얼마나 원하나요?',
    '체험과 활동 중심의 여행을 얼마나 원하나요?',
    '지역 음식과 미식 경험을 얼마나 원하나요?',
    '바다와 해변을 방문하고 싶은 정도는 어느 정도인가요?']
survey_dictionary=pd.DataFrame({'column':SURVEY_FIELDS,'question':SURVEY_QUESTIONS,
                               'allowed_values':'0,1,2,3,4,5','meaning':'0 관심 없음, 5 매우 관심 있음'})
save_csv(survey_dictionary,'cosine_survey_dictionary')

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
    candidates=candidates.sort_values(['coverage_adjusted_score','cosine_similarity','category_coverage','course_id'],ascending=[False,False,False,True])
    # Equal component scores share a rank. course_id is only deterministic display order.
    candidates['score_rank']=candidates.coverage_adjusted_score.rank(method='min',ascending=False).astype(int)
    candidates['display_order']=np.arange(1,len(candidates)+1)
    keep=['respondent_id','data_status','score_rank','display_order','course_id','region','name','cosine_cluster',
          'cosine_similarity','cosine_fit_score','coverage_factor','coverage_adjusted_score',
          *[f'contribution_{c}_points' for c in CATEGORIES],'operational_availability_verified']
    result=candidates[keep]
    assert np.allclose(result[[f'contribution_{c}_points' for c in CATEGORIES]].sum(axis=1),result.coverage_adjusted_score)
    return result.head(top_n) if top_n else result, 'SCORED_CANDIDATES_NOT_BOOKING_CONFIRMATION'

survey_columns=['respondent_id',*SURVEY_FIELDS,'desired_region']
pd.DataFrame(columns=survey_columns).to_csv(RUN_DIR/'survey_responses_template.csv',index=False,encoding='utf-8-sig')
survey_results=[];survey_status=[]
if city is not None:
    if SURVEY_CSV is not None and Path(SURVEY_CSV).is_file():
        survey=read_csv_input(SURVEY_CSV,'survey')
        missing=set(survey_columns)-set(survey.columns)
        if missing:raise ValueError(f'설문 CSV 필수 열 누락: {sorted(missing)}')
        survey['data_status']='USER_INPUT'
        if survey.respondent_id.eq('').any() or survey.respondent_id.duplicated().any():raise ValueError('설문 respondent_id는 비어 있지 않은 고유값이어야 합니다.')
    else:
        survey=pd.DataFrame([
            ['DEMO_CULTURE',5,2,1,2,0,''],['DEMO_COAST',1,3,1,2,5,''],
            ['DEMO_ACTIVE',1,1,5,3,2,''],['DEMO_BALANCED',3,3,3,3,3,'']],columns=survey_columns)
        survey['data_status']='SYNTHETIC_DEMONSTRATION'
        print('실제 설문 CSV 없음: 명시적 가상 응답 4개로 계산 구조만 시연합니다.')
    save_csv(survey,'cosine_survey_inputs_used')
    for _,response in survey.iterrows():
        result,status=rank_courses_cosine(response,course_table)
        survey_status.append({'respondent_id':response.respondent_id,'data_status':response.data_status,'status':status,'n_candidates':len(result)})
        if len(result):survey_results.append(result)
    save_csv(pd.DataFrame(survey_status),'cosine_survey_status')
    if survey_results:
        rankings=pd.concat(survey_results,ignore_index=True);save_csv(rankings,'cosine_course_rankings_all')
        top_rankings=rankings[rankings.display_order.le(10)];save_csv(top_rankings,'cosine_course_rankings_top10');show_table(top_rankings,20)
        first=rankings[rankings.respondent_id.eq(rankings.respondent_id.iloc[0])].head(5).iloc[::-1]
        fig,ax=plt.subplots(figsize=(11,5));left=np.zeros(len(first))
        for j,c in enumerate(CATEGORIES):
            values=first[f'contribution_{c}_points'];ax.barh(np.arange(len(first)),values,left=left,label=CAT_LABELS[c],color=PALETTE[j]);left+=values.to_numpy()
        ax.set(yticks=np.arange(len(first)),yticklabels=[f'{r.region} {r["name"][:30]}' for _,r in first.iterrows()],
               xlabel='Coverage-adjusted component points',xlim=(0,105),title=f'{first.respondent_id.iloc[0]}: top 5 course score contributions')
        ax.legend(frameon=False,ncol=5,loc='lower right',fontsize=8);finish(fig,'C_survey_course_contributions')
        assert rankings.coverage_adjusted_score.between(0,100+1e-8).all()
    RUN_SUMMARY['cosine_survey']={'respondents':len(survey),'status_counts':{str(k):int(v) for k,v in survey.data_status.value_counts().items()},
                                'formula':'100 * cosine(q, course category shares) * category_coverage',
                                'production_score_replaced':False,'stay_formula_changed':False,
                                'operational_availability_verified':False}

# Meaningful edge-case and mathematical checks.
assert np.isclose(cosine_similarity([[10,20,10]],[[100,200,100]])[0,0],1)
u,valid,_=unit_rows([[0,0],[1,2]])
assert valid.tolist()==[False,True] and np.allclose(np.linalg.norm(u,axis=1),1)
toy=np.array([[1,.03],[1,-.02],[-1,.03],[-1,-.02]],float);toy/=np.linalg.norm(toy,axis=1)[:,None]
toyfit=spherical_kmeans(toy,2,42,5,100)
assert adjusted_rand_score([0,0,1,1],toyfit['labels'])==1
if city is not None:
    blank={'respondent_id':'ZERO',**dict.fromkeys(SURVEY_FIELDS,0),'desired_region':''}
    assert rank_courses_cosine(blank,course_table)[1]=='NO_STATED_PREFERENCE'
    invalid={**blank,'q_herit':6}
    try:rank_courses_cosine(invalid,course_table)
    except ValueError:pass
    else:raise AssertionError('잘못된 설문 값이 거부되지 않았습니다.')
print('코사인 수학·수렴·영벡터·설문 범위·기여도 합 검증 완료')


if places is not None:
    assert len(places)==len(places_raw)
    assert len(place_model["labels"])==int(places.cluster_eligible.sum())
    assert np.isfinite(place_model["pcs"].to_numpy()).all()
if city is not None:
    assert len(course_table)==len(cities_raw)
    assert course_table[[f"share_{c}" for c in CATEGORIES]].sum(axis=1).le(1+1e-10).all()
    assert stops.identity_verified.eq(False).all()
    if city_model is not None: assert len(city_model["labels"])==int(course_table.cluster_eligible.sum())
assert all(p.is_file() and p.stat().st_size>0 for p in PLOT_FILES)
summary={"method_version":"integrated-5.0", "created_at":datetime.now().isoformat(),"inputs":INPUT_META,
         "parameters":{"pca_target":PCA_TARGET,"k_max":K_MAX,"seeds":SEEDS,"n_init":N_INIT,"min_cluster_share":MIN_CLUSTER_SHARE,"min_seed_ari":MIN_SEED_ARI,"cosine_n_init":COSINE_N_INIT,"cosine_max_iter":COSINE_MAX_ITER},
         "models":RUN_SUMMARY,"versions":{"python":platform.python_version(),"numpy":np.__version__,"pandas":pd.__version__,"sklearn":sklearn.__version__,"matplotlib":matplotlib.__version__},
         "plot_count":len(PLOT_FILES),"verified_stop_links":0,
         "scope":"Baseline and spherical cosine clusters, survey-to-course candidate scoring, regional spending and marine context; no production deployment or validated satisfaction inference."}
(RUN_DIR/"run_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
manifest=[]
for path in sorted(RUN_DIR.rglob("*")):
    if path.is_file():manifest.append({"file":str(path.relative_to(RUN_DIR)),"bytes":path.stat().st_size,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
pd.DataFrame(manifest).to_csv(RUN_DIR/"file_manifest.csv",index=False,encoding="utf-8-sig")
print("완료:",RUN_DIR.resolve())
print("PNG",len(PLOT_FILES),"개 / CSV",len(list(TABLES.glob("*.csv"))),"개")
show_table(pd.DataFrame(manifest)[["file","bytes"]],100)
