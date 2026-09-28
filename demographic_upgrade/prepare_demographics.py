from pathlib import Path
import zipfile,io,json,hashlib,re
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parent
AGES=['10대 미만','10대','20대','30대','40대','50대','60대','70대']
def run():
 src=ROOT/'data/source.zip';frames={};audit={}
 with zipfile.ZipFile(src) as z:
  for name in z.namelist():
   b=z.read(name);(ROOT/'data/raw'/name).write_bytes(b);d=pd.read_csv(io.BytesIO(b));kind=name.split('_',1)[1][:-4];frames[kind]=d
   audit[kind]={'rows':len(d),'regions':len(d[['시도','시군구']].drop_duplicates()),'sex_values':d.성별.unique().tolist(),'age_values':d.연령.unique().tolist()}
 heat=frames['구성비 히트맵'];age=frames['연령별 방문자 구성비'];sex=frames['성별 방문자 구성비'];key=['시도','시군구'];dkey=key+['성별','연령']
 ages=age.drop_duplicates(dkey+['비율']);sexes=sex.drop_duplicates(dkey+['비율'])
 conflicts=set()
 for df in [ages,sexes]:
  tmp=df.groupby(dkey).size();conflicts|={tuple(k[:2]) for k in tmp[tmp>1].index}
 regions=heat[key].drop_duplicates().sort_values(key);bad=[];good=[]
 for _,rr in regions.iterrows():
  r=tuple(rr);aa=ages[(ages.시도==r[0])&(ages.시군구==r[1])];ss=sexes[(sexes.시도==r[0])&(sexes.시군구==r[1])];hh=heat[(heat.시도==r[0])&(heat.시군구==r[1])]
  reasons=[]
  if r in conflicts:reasons.append('CONFLICTING_ROWS_NO_COMPONENT_KEY')
  if not hh.구성비.between(0,100).all():reasons.append('HEATMAP_OUT_OF_PERCENT_RANGE')
  if len(aa)!=8 or set(aa.연령)!=set(AGES) or len(ss)!=2 or set(ss.성별)!={'남성','여성'}:reasons.append('INCOMPLETE_PROFILE')
  if not reasons:
   if not aa.비율.between(0,100).all() or not ss.비율.between(0,100).all():reasons.append('VALUE_OUT_OF_RANGE')
   if abs(aa.비율.sum()-100)>.1 or abs(ss.비율.sum()-100)>.1:reasons.append('SUM_OUTSIDE_ROUNDING_TOLERANCE')
   male=float(ss.loc[ss.성별=='남성','비율'].iloc[0])
   if len(hh)!=1 or abs(float(hh.구성비.iloc[0])-male)>.05:reasons.append('HEATMAP_DETAIL_MISMATCH')
  if reasons:bad.append({'source_region':r[0]+'|'+r[1],'sido':r[0],'sigungu':r[1],'reason':'|'.join(reasons)});continue
  row={'source_region':r[0]+'|'+r[1],'sido':r[0],'sigungu':r[1],'age_sum':float(aa.비율.sum()),'sex_sum':float(ss.비율.sum())}
  for a in AGES:row['age_'+a]=float(aa.loc[aa.연령==a,'비율'].iloc[0])
  for s,k in [('남성','male'),('여성','female')]:row['sex_'+k]=float(ss.loc[ss.성별==s,'비율'].iloc[0])
  good.append(row)
 df=pd.DataFrame(good);df.to_csv(ROOT/'data/region_demographic_profiles.csv',index=False,encoding='utf-8-sig');pd.DataFrame(bad).to_csv(ROOT/'results/excluded_regions.csv',index=False,encoding='utf-8-sig')
 # Only rounding-scale normalization. No pooling across duplicate component rows.
 bench_age={a:float((df['age_'+a]/df.age_sum).median()) for a in AGES}
 bench_sex={s:float((df['sex_'+s]/df.sex_sum).median()) for s in ['male','female']}
 regs={r.source_region:{'sido':r.sido,'sigungu':r.sigungu,'age':{a:r['age_'+a]/r.age_sum for a in AGES},'sex':{s:r['sex_'+s]/r.sex_sum for s in ['male','female']}} for _,r in df.iterrows()}
 master=pd.read_csv(ROOT/'data/master_age_v3.csv');courses=json.loads((ROOT/'data/citytour.json').read_text());app_regions=set(master.region_name)|{x[0] for x in courses}
 coarse={'서울','부산','대구','대전','울산','인천','광주','제주','세종'};matches=[];region_map={}
 for ar in sorted(app_regions):
  if ar in coarse:cands=[];status='COARSE_REGION_NO_WEIGHTED_AGGREGATE'
  elif ar=='경기광주':cands=[('경기도','광주시')];status='NAME_EXPLICIT_PROVINCE'
  elif ar=='고성(강원)':cands=[('강원특별자치도','고성군')];status='NAME_EXPLICIT_PROVINCE'
  else:
   cands=[tuple(x) for x in regions.to_numpy() if re.sub('[시군구]$','',x[1])==ar];status='NAME_UNIQUE_REGION' if len(cands)==1 else 'AMBIGUOUS_OR_NO_MATCH'
  rkey='|'.join(cands[0]) if len(cands)==1 else ''
  eligible=rkey in regs
  if eligible:region_map[ar]={'regionKey':rkey,'weight':.5,'status':status,'identityVerified':False}
  matches.append({'app_region':ar,'candidate_source_regions':';'.join('|'.join(x) for x in cands),'source_region':rkey,'match_status':status,'usable':eligible,'weight':.5 if eligible else 0})
 pd.DataFrame(matches).to_csv(ROOT/'data/app_region_crosswalk.csv',index=False,encoding='utf-8-sig')
 config={'version':'regional-marginals-v1','period':['2025-09','2026-08'],'sourceSha256':hashlib.sha256(src.read_bytes()).hexdigest(),'regionalGamma':.02,'ageWeight':.75,'sexWeight':.25,'combinedPlaceCityCap':.02,'referenceScope':'90 complete profiles selected by male-composition Top100; NOT nationwide population baseline','upperAgeLabel':'70대 (70+ interpretation unverified)','benchmarkAge':bench_age,'benchmarkSex':bench_sex,'regions':regs,'appRegions':region_map,'placeRegion':dict(zip(master.place_id,master.region_name))}
 (ROOT/'data/region-demographics.json').write_text(json.dumps(config,ensure_ascii=False,indent=2))
 mapping=pd.DataFrame(matches).rename(columns={'app_region':'region_name','source_region':'demographic_source_region','usable':'demographic_usable','weight':'demographic_weight','match_status':'demographic_match_status'})
 full=master.merge(mapping.drop(columns='candidate_source_regions'),on='region_name',how='left')
 fcols=['source_region']+[x for x in df.columns if x.startswith(('age_','sex_'))]
 f=df[fcols].rename(columns={x:'regional_'+x for x in fcols if x!='source_region'})
 full=full.merge(f,left_on='demographic_source_region',right_on='source_region',how='left').drop(columns='source_region')
 full.to_csv(ROOT/'results/nationwide_places_demographics.csv',index=False,encoding='utf-8-sig')
 audit.update({'valid_regions':len(df),'excluded_conflicting_regions':len(conflicts),'detail_regions':len(age[key].drop_duplicates()),'detail_duplicated_age_rows_removed':len(age)-len(ages),'detail_duplicated_sex_rows_removed':len(sex)-len(sexes),'app_regions_mapped':len(region_map),'app_places_with_region_proxy':int(full.demographic_usable.sum()),'city_courses_with_region_proxy':sum(x[0] in region_map for x in courses),'age_benchmarks':bench_age,'sex_benchmarks':bench_sex,'joint_sex_age_available':False})
 (ROOT/'results/audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2));print(json.dumps(audit,ensure_ascii=False,indent=2))
if __name__=='__main__':run()
