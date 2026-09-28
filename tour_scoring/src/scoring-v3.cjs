'use strict';
const V2=require('./scoring-v2.cjs');
const data=require('../data/age-popularity.json');
const profiles=require('../data/age-candidate-profiles.json');
function ageBand(answers={}){return ({1:'20',2:'30',3:'40',4:'50',5:'60plus',6:'60plus'})[answers[0]]||null;}
function placeAgeBonus(placeId,answers={},options={}){
 const beta=options.beta??data.beta;
 if(!Number.isFinite(beta)||beta<0||beta>.05)throw new Error('beta는 0~0.05');
 const band=ageBand(answers),p=data.byPlace[placeId];
 const zero=reason=>({score:0,band,reason,placeId,sourceVersion:data.version});
 if(answers[5]!==0)return zero('NOT_DOMESTIC_MODE');
 if(!band)return zero('AGE_NOT_COVERED');
 if(!p)return zero('NO_LINKED_DATA');
 if(options.strictVerified&&p.verified!==true)return zero('PROVISIONAL_MATCH_DISABLED');
 const x=p.ages[band];
 if(!x)return zero('NOT_IN_AGE_TOP30');
 return {score:beta*p.matchWeight*x.relativeIntensity,band,placeId,reason:'OBSERVED_TOP30_PROVISIONAL_MATCH',
  rank:x.rank,sharePct:x.sharePct,relativeIntensity:x.relativeIntensity,matchWeight:p.matchWeight,
  matchStatus:p.matchStatus,name:p.name,sourceVersion:data.version};
}
function candidateAgeBonus(profile,answers,options={}){
 const zero=reason=>({score:0,reason,denominator:0,parts:[]});
 if(!profile||profile.parseSupported!==true)return zero('PROFILE_NOT_SUPPORTED');
 if(!Array.isArray(profile.slots)||!profile.slots.length)return zero('EMPTY_PROFILE');
 // 미연결 경유지도 분모에 포함한다.No extrapolation to missing places.
 const parts=profile.slots.map(s=>{
  if(!Number.isFinite(s.linkWeight)||s.linkWeight<0||s.linkWeight>1)throw new Error('linkWeight 범위');
  const r=placeAgeBonus(s.placeId,answers,options);
  return {...r,routeOrThemeLinkWeight:s.linkWeight,weightedScore:r.score*s.linkWeight};
 });
 return {score:parts.reduce((a,b)=>a+b.weightedScore,0)/parts.length,scope:profile.scope,denominator:parts.length,
  linkedSlots:parts.filter(x=>x.reason==='OBSERVED_TOP30_PROVISIONAL_MATCH').length,
  reason:'BOUNDED_AGE_EVIDENCE_AVERAGE',parts};
}
function applyAgeToPlace(candidate,answers,options={}){
 if(!Number.isFinite(candidate.score))throw new Error('기존 장소 점수 필요');
 const age=placeAgeBonus(candidate.placeId,answers,options);
 return {...candidate,scoreBeforeAge:candidate.score,score:candidate.score+age.score,age};
}
function recommendV3(input={}){
 const old=V2.recommendV2(input),answers=input.answers,options=input.ageOptions||{};
 const themes=old.allThemes.map(t=>{
  const profile=input.ageProfiles?.themes?.[t.k]||profiles.themes[t.k];
  const age=candidateAgeBonus(profile,answers,options);
  // Existing age-derived regional term and new age bonus share the +/- .05 budget.
  const newReg=answers[5]===0?Math.max(-.05,Math.min(.05,t.reg+age.score)):t.reg;
  return {...t,scoreBeforeAge:t.score,age:{...age,effectiveBonus:newReg-t.reg,regionalTermAfter:newReg},score:t.score+newReg-t.reg};
 }).sort((a,b)=>b.score-a.score||a.index-b.index);
 const cities=old.allCities.map(t=>{
  const profile=input.ageProfiles?.tours?.[t.index]||profiles.tours[t.index];
  const matches=profile&&(!profile.rawRow||JSON.stringify(profile.rawRow)===JSON.stringify(t.raw));
  const age=candidateAgeBonus(matches?profile:null,answers,options);
  return {...t,scoreBeforeAge:t.score,age:{...age,effectiveBonus:age.score},score:t.score+age.score};
 }).sort((a,b)=>b.score-a.score||a.index-b.index);
 const agePlaceRanking=Object.keys(data.byPlace).map(id=>placeAgeBonus(id,answers,options)).filter(x=>x.score>0).sort((a,b)=>b.score-a.score);
 return {...old,version:'3.0.0',allThemes:themes,themePicks:themes.slice(0,3),allCities:cities,
   cityPicks:V2.pickDistinctRegions(cities),agePlaceRanking,
   agePolicy:{version:data.version,band:ageBand(answers),beta:options.beta??data.beta,strictVerified:!!options.strictVerified,
     populationRule:'domestic_mode_only',matchStatus:'44 name-only provisional links; not identity-verified',
     sourceScope:'each age Top30; absence has no bonus, not negative preference'}};
}
module.exports={ageBand,placeAgeBonus,candidateAgeBonus,applyAgeToPlace,recommendV3};
