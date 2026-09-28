from pathlib import Path
import zipfile,io,json,re
import pandas as pd,numpy as np
P=Path(__file__).resolve().parent;src=P/'data/source/datalab_age_source.zip'
(P/'data/raw').mkdir(parents=True,exist_ok=True);(P/'results').mkdir(exist_ok=True)
frames=[]
with zipfile.ZipFile(src) as z:
 for f in z.namelist():
  b=z.read(f);(P/'data/raw'/f).write_bytes(b)
  d=pd.read_csv(io.BytesIO(b),dtype={'관광지ID':str,'연령대':str})
  d=d.rename(columns={'순위':'source_rank','관광지ID':'datalab_id','관심지점명':'datalab_name','구분':'category_raw','연령대':'age_band','비율':'share_pct'})
  d['age_band']=d.age_band.replace({'60':'60plus','전체':'all'})
  d['share_pct']=pd.to_numeric(d.share_pct.astype(str).str.strip());d['source_file']=f
  d['period_start']='2025-09';d['period_end']='2026-08';d['period_source']='upload_filename'
  d['rank_tie_adjusted']=d.share_pct.rank(method='average',ascending=False)
  d['top30_rank_exposure']=(31-d.rank_tie_adjusted)/30
  d['within_age_relative_intensity']=d.share_pct/d.share_pct.max()
  frames.append(d)
long=pd.concat(frames,ignore_index=True)
assert len(long)==180 and not long.duplicated(['datalab_id','age_band']).any()
long.to_csv(P/'data/datalab_age_popularity_long.csv',index=False,encoding='utf-8-sig')
meta=long.drop_duplicates('datalab_id')[['datalab_id','datalab_name','category_raw']]
age=['20','30','40','50','60plus']
share=long.pivot(index='datalab_id',columns='age_band',values='share_pct').reindex(columns=age+['all'])
rank=long[long.age_band!='all'].pivot(index='datalab_id',columns='age_band',values='top30_rank_exposure').reindex(index=meta.datalab_id,columns=age).fillna(0)
rank.index.name='datalab_id';rank.to_csv(P/'data/age_rank_exposure_matrix.csv',encoding='utf-8-sig')
meta.merge(share,on='datalab_id').to_csv(P/'data/age_share_observed_matrix.csv',index=False,encoding='utf-8-sig')
master=pd.read_csv(P/'data/source/nationwide_places_all_3118.csv')
norm=lambda x:re.sub(r'\s+','',str(x)).casefold()
blocked={'보문사':'동명이소 위험 및 원자료 지역 누락','송정해수욕장':'부산 울산 등 동명이소 위험 및 원자료 지역 누락'}
links=[]
for _,r in meta.iterrows():
 c=master[master.place_name.map(norm)==norm(r.datalab_name)]
 status='name_unique_provisional' if len(c)==1 else 'ambiguous' if len(c)>1 else 'unmatched'
 if r.datalab_name in blocked:status='blocked_homonym'
 pid=c.iloc[0].place_id if status=='name_unique_provisional' else ''
 links.append({'datalab_id':r.datalab_id,'datalab_name':r.datalab_name,'candidate_place_ids':'|'.join(c.place_id),
 'place_id':pid,'match_status':status,'match_weight':.5 if pid else 0,'verified':False,
 'review_note':blocked.get(r.datalab_name,'좌표 주소 미제공 · 공백 제거 명칭 매칭 · 현장 동일성 미확인' if pid else '별칭 시설 범위 및 주소 검토 필요')})
link=pd.DataFrame(links);link.to_csv(P/'data/datalab_place_crosswalk.csv',index=False,encoding='utf-8-sig')
intensity=long[long.age_band!='all'].pivot(index='datalab_id',columns='age_band',values='within_age_relative_intensity').reindex(columns=age)
features=link[['datalab_id','place_id','match_status','match_weight']].query("place_id!=''").merge(share[age].add_prefix('age_share_'),on='datalab_id').merge(intensity.add_prefix('age_intensity_'),on='datalab_id')
full=master.merge(features,on='place_id',how='left');full['age_data_status']=full.match_status.fillna('no_linked_top30_data')
full.to_csv(P/'data/nationwide_places_with_age.csv',index=False,encoding='utf-8-sig')
# App dictionary: raw popularity values and explicitly provisional identity dampening.
byplace={}
for _,r in link.query("place_id!=''").iterrows():
 rows=long[(long.datalab_id==r.datalab_id)&(long.age_band!='all')]
 byplace[r.place_id]={'datalabId':r.datalab_id,'name':r.datalab_name,'matchStatus':r.match_status,'matchWeight':float(r.match_weight),'verified':False,
 'ages':{x.age_band:{'rank':int(x.source_rank),'sharePct':float(x.share_pct),'relativeIntensity':float(x.within_age_relative_intensity)} for _,x in rows.iterrows()}}
config={'version':'datalab-202509-202608-top30-v1','beta':.03,'period':['2025-09','2026-08'],'ageBands':age,'byPlace':byplace,'scope':'top30_exposure_only','defaultMatchMode':'provisional_damped'}
(P/'data/age-popularity.json').write_text(json.dumps(config,ensure_ascii=False,indent=2))
audit={'rows':len(long),'unique_datalab_places':len(meta),'rows_per_age':long.groupby('age_band').size().to_dict(),'share_sums':long.groupby('age_band').share_pct.sum().to_dict(),'match_counts':link.match_status.value_counts().to_dict(),'app_matched_places':int((link.place_id!='').sum()),'app_coverage_pct':float((link.place_id!='').sum()/len(master)*100),'complete_age_profiles':int(share[age].notna().all(axis=1).sum()),'period_from_filename':True,'share_denominator':'not specified in CSV; each top30 sum about 100','verified_crosswalk':0}
(P/'results/data_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2));print(json.dumps(audit,ensure_ascii=False,indent=2))
