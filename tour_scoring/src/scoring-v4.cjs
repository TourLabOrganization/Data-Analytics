'use strict';
const V3=require('./scoring-v3.cjs'),V2=require('./scoring-v2.cjs');
const D=require('../data/region-demographics.json'),P=require('../data/age-candidate-profiles.json');
const clip=(x,lo,hi)=>Math.max(lo,Math.min(hi,x));
function regionAgeBand(answers={}){return ({0:'10대',1:'20대',2:'30대',3:'40대',4:'50대',5:'60대'})[answers[0]]||null;}
function options(d={}){
 if(!d||typeof d!=='object'||Array.isArray(d))throw Error('demographics는 객체');
 if(d.enabled!==undefined&&typeof d.enabled!=='boolean')throw Error('enabled는 boolean');
 if(d.sex!==undefined&&d.sex!==null&&!['male','female','unspecified'].includes(d.sex))throw Error('sex는 male/female/unspecified/null');
 return {enabled:d.enabled!==false,sex:['male','female'].includes(d.sex)?d.sex:null};
}
function relativeEvidence(p,b){if(!Number.isFinite(p)||!Number.isFinite(b)||p<0||b<=0)throw Error('비율 또는 기준값 오류');return p===0?0:clip(Math.log2(p/b),0,1);}
function regionalBonus(appRegion,answers={},demographics={},ageOptions={}){
 const o=options(demographics),a=regionAgeBand(answers),m=D.appRegions[appRegion];
 const zero=reason=>({score:0,reason,appRegion,ageBand:a,sex:o.sex,sourceVersion:D.version});
 if(!o.enabled)return zero('REGIONAL_DEMOGRAPHICS_DISABLED');
 if(answers[5]!==0)return zero('NOT_DOMESTIC_MODE');
 if(!m)return zero('NO_USABLE_REGION_PROFILE');
 if(ageOptions.strictVerified&&!m.identityVerified)return zero('PROVISIONAL_REGION_DISABLED');
 const r=D.regions[m.regionKey];
 const zAge=a?relativeEvidence(r.age[a],D.benchmarkAge[a]):0;
 const zSex=o.sex?relativeEvidence(r.sex[o.sex],D.benchmarkSex[o.sex]):0;
 return {score:D.regionalGamma*m.weight*(D.ageWeight*zAge+D.sexWeight*zSex),reason:'SEPARATE_REGIONAL_MARGINALS',appRegion,regionKey:m.regionKey,ageBand:a,sex:o.sex,
  ageShare:a?r.age[a]:null,ageBenchmark:a?D.benchmarkAge[a]:null,sexShare:o.sex?r.sex[o.sex]:null,sexBenchmark:o.sex?D.benchmarkSex[o.sex]:null,
  ageEvidence:zAge,sexEvidence:zSex,agePart:D.regionalGamma*m.weight*D.ageWeight*zAge,sexPart:D.regionalGamma*m.weight*D.sexWeight*zSex,
  ageReason:a?'SUPPORTED':'AGE_UPPER_BOUND_UNVERIFIED_OR_MISSING',sexReason:o.sex?'ANSWERED':'NOT_ANSWERED_NO_REALLOCATION',
  gamma:D.regionalGamma,regionWeight:m.weight,sourceVersion:D.version,jointSexAgeUsed:false};
}
function placeDemographicBonus(placeId,answers,demographics={},ageOptions={}){return regionalBonus(D.placeRegion[placeId],answers,demographics,ageOptions);}
function applyDemographicsToPlace(candidate,answers,demographics={},ageOptions={}){
 if(!Number.isFinite(candidate.score))throw Error('기존 장소 점수 필요');
 const age=V3.placeAgeBonus(candidate.placeId,answers,ageOptions),region=placeDemographicBonus(candidate.placeId,answers,demographics,ageOptions);
 const combined=clip(age.score+region.score,0,D.combinedPlaceCityCap);
 return {...candidate,scoreBeforeDemographics:candidate.score,age,regionalDemographics:region,combinedDemographicBonus:combined,score:candidate.score+combined};
}
function themeBonus(key,answers,demographics,ageOptions){
 const p=P.themes[key];if(!p?.slots?.length)return {score:0,reason:'NO_THEME_PROFILE',parts:[]};
 const parts=p.slots.map(x=>({placeId:x.placeId,...placeDemographicBonus(x.placeId,answers,demographics,ageOptions)}));
 return {score:parts.reduce((a,x)=>a+x.score,0)/parts.length,denominator:parts.length,parts,reason:'ALL_THEME_SLOTS_AVERAGE'};
}
function recommendV4(input={}){
 const d=options(input.demographics||{}),old=V3.recommendV3(input),answers=input.answers,ao=input.ageOptions||{};
 const themes=old.allThemes.map(t=>{
  const r=themeBonus(t.k,answers,d,ao),after=clip(t.age.regionalTermAfter+r.score,-.05,.05),delta=after-t.age.regionalTermAfter;
  return {...t,scoreBeforeRegional:t.score,regionalDemographics:{...r,effectiveBonus:delta,regionalTermAfter:after},score:t.score+delta};
 }).sort((a,b)=>b.score-a.score||a.index-b.index);
 const cities=old.allCities.map(t=>{
  const r=regionalBonus(t.region,answers,d,ao),combined=clip(t.age.score+r.score,0,D.combinedPlaceCityCap),delta=combined-t.age.score;
  return {...t,scoreBeforeRegional:t.score,regionalDemographics:{...r,effectiveBonus:delta,combinedDemographicBonus:combined},score:t.score+delta};
 }).sort((a,b)=>b.score-a.score||a.index-b.index);
 return {...old,version:'4.0.0',allThemes:themes,themePicks:themes.slice(0,3),allCities:cities,cityPicks:V2.pickDistinctRegions(cities),
  demographicPolicy:{...d,version:D.version,regionalAgeBand:regionAgeBand(answers),regionalGamma:D.regionalGamma,ageWeight:D.ageWeight,sexWeight:D.sexWeight,
   validRegions:90,referenceScope:D.referenceScope,jointSexAgeUsed:false,regionScope:'regional proxy; not attraction visitor composition',strictVerified:!!ao.strictVerified}};
}
module.exports={regionAgeBand,relativeEvidence,regionalBonus,placeDemographicBonus,applyDemographicsToPlace,recommendV4};
