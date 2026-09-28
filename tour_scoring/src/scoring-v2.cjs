'use strict';
// 신규 질문 → 선호 → 점수/체류 → 일정 검증. 외부 API 호출이나 운영 배포 없음.
const {recommend:legacy}=require('./scoring.cjs');
const {recommendCityTours}=require('./citytour.cjs');
const defaultTours=require('../data/citytour_app_zip.json');
const stats=require('../data/hallyu_2026.json');
const K=Object.keys(stats.active);
const finite=(x,label,min=0)=>{if(!Number.isFinite(x)||x<min)throw new Error(label+' 범위 오류');return x;};
function resolveContentPreference(answers,h={}){
  const eligible=answers[5]===1 && stats.residenceAreas.includes(h.residenceArea) &&
    ((answers[0]===0&&h.age15to19===true)||(answers[0]>=1&&answers[0]<=4)) && h.experienced===true;
  const values={};
  for(const k of K){
    const v=h.contentPreference?.[k];
    if(v && typeof v.answered!=='boolean')throw new Error(k+' answered 필수');
    const answered=v?.answered===true;
    if(answered&&![0,.25,.5,.75,1].includes(v.rating))throw new Error(k+' rating 오류');
    if(v&&!answered&&v.rating!=null)throw new Error(k+' 미응답 rating은 null');
    const e=answered?v.rating:null,r=stats.active[k]/100;
    values[k]={e,c:answered?1:0,r,z:answered?e:.5+(eligible?.2:0)*(r-.5),
      source:answered?'direct':eligible?'survey_prior':'neutral'};
  }
  return {eligible,version:stats.version,values};
}
function validateMedia(media={}){
  let sum=0;
  for(const [k,v] of Object.entries(media)){if(!K.includes(k))throw new Error('비활성 태그 '+k);sum+=finite(v,'M.'+k);}
  if(sum>1+1e-9)throw new Error('미디어 비중 합은 1 이하');
  return sum;
}
// 실제 근거를 보유한 프로필만 허용. 경로 문자열에서 촬영지를 추정하지 않는다.
function verifiedMedia(profile){
  if(!profile)return {media:{},warning:'MEDIA_NOT_MAPPED'};
  if(profile.verified!==true||typeof profile.source!=='string'||!profile.source.trim())throw new Error('태그 검증 및 출처 필요');
  validateMedia(profile.media);return {media:profile.media||{},warning:null,source:profile.source};
}
function buildCourseMedia(stops,totalUniqueStops){
  if(!Number.isInteger(totalUniqueStops)||totalUniqueStops<=0)return {verified:true,source:'no complete stop inventory',media:{},warning:'STOP_COUNT_UNKNOWN'};
  const ids=new Set(),sum=Object.fromEntries(K.map(k=>[k,0]));
  for(const s of stops){
    if(!s.id||ids.has(s.id))throw new Error('고유 경유지 id 필요');ids.add(s.id);
    const {media}=verifiedMedia(s.contentProfile);
    for(const k of K)sum[k]+=media[k]||0;
  }
  if(ids.size>totalUniqueStops)throw new Error('전체 경유지 수 불일치');
  return {verified:true,source:'verified stop profiles; denominator='+totalUniqueStops,
    media:Object.fromEntries(K.map(k=>[k,sum[k]/totalUniqueStops])),
    warning:stops.length<totalUniqueStops?'PARTIAL_STOP_COVERAGE':null};
}
function contentAdjustment(pref,profile){
  const {media,warning,source}=verifiedMedia(profile);
  const parts=Object.fromEntries(K.map(k=>[k,.1*(media[k]||0)*(pref.values[k].z-.5)]));
  return {score:Object.values(parts).reduce((a,b)=>a+b,0),parts,media,source,
    warning:profile?.warning||warning};
}
function pickDistinctRegions(scored,limit=5){
  if(!Number.isInteger(limit)||limit<1)throw new Error('limit 오류');
  const seen=new Set();return scored.slice().sort((a,b)=>b.score-a.score||a.index-b.index)
    .filter(x=>{if(seen.has(x.region))return false;seen.add(x.region);return true;}).slice(0,limit);
}
function recommendV2(input={}){
  const {answers={},hallyu={},themeProfiles={},tourProfiles={},tours=defaultTours,browserLanguage='ko-KR'}=input;
  for(const i of [0,1,2,5])if(answers[i]===undefined)throw new Error('필수 문항 Q'+(i+1));
  // fr가 존재하는 확인된 GitHub 테마 자료를 명시 사용한다. legacy APP 모드는 변경하지 않는다.
  const old=legacy(answers,{version:'github',browserLanguage}),pref=resolveContentPreference(answers,hallyu);
  const themes=old.trace.allThemes.map((t,index)=>{
    const content=contentAdjustment(pref,themeProfiles[t.k]);
    return {...t,index,legacyScore:t.score,content,score:t.score+content.score};
  }).sort((a,b)=>b.score-a.score||a.index-b.index);
  const R={...old.result,cats:old.trace.interestCategories};
  const cities=tours.map((row,index)=>{
    const t=recommendCityTours(R,[row])[0],content=contentAdjustment(pref,tourProfiles[index]);
    return {...t,index,legacyScore:t.score,content,score:t.score+content.score};
  });
  return {version:'2.0.0',source:'github themes + app_zip citytour',answers,hallyu,
    preference:pref,legacy:old,themePicks:themes.slice(0,3),allThemes:themes,
    cityPicks:pickDistinctRegions(cities),allCities:cities.sort((a,b)=>b.score-a.score||a.index-b.index)};
}
function estimateStay({answers,preference,place,extraMinutes=0,manualMinutes=null,fixedMinutes=null}){
  const {baseMinutes:B,minMinutes:L,maxMinutes:U,categories=[],contentProfile}=place;
  finite(B,'B');finite(L,'L');finite(U,'U');
  if(B===0)return {excluded:true,recommendedMinutes:0,appliedMinutes:0,warnings:['EXCLUDED_BASE_ZERO']};
  if(L<=0||L>B||B>U)throw new Error('0<L<=B<=U 필요');
  if(![0,1,2].includes(answers[2]))throw new Error('Q3 필수');
  finite(extraMinutes,'추가 활동');
  const cats=new Set((answers[3]||[]).map(j=>({2:0,3:1,4:4,5:3,6:2})[j]).filter(v=>v!==undefined));
  if(categories.some(c=>!Number.isInteger(c)||c<0||c>4)||new Set(categories).size!==categories.length)throw new Error('장소 카테고리 오류');
  const I0=categories.length?categories.reduce((s,c)=>s+(cats.has(c)?1:.5),0)/categories.length:.5;
  const {media,warning}=verifiedMedia(contentProfile),mass=validateMedia(media);
  const I=K.reduce((s,k)=>s+(media[k]||0)*preference.values[k].z,0)+(1-mass)*I0;
  const pace=[.85,1,1.2][answers[2]],raw=B*(1+.2*(I-.5))*pace+extraMinutes;
  const recommendedMinutes=Math.max(L,Math.min(U,5*Math.ceil(raw/5)));
  const warnings=warning?[warning]:[];
  if(manualMinutes!==null)finite(manualMinutes,'수동 체류',Number.MIN_VALUE);
  if(fixedMinutes!==null)finite(fixedMinutes,'고정 체류',Number.MIN_VALUE);
  const appliedMinutes=fixedMinutes??manualMinutes??recommendedMinutes;
  if(fixedMinutes!==null&&manualMinutes!==null&&fixedMinutes!==manualMinutes)warnings.push('FIXED_OVERRIDES_MANUAL');
  if(appliedMinutes<L||appliedMinutes>U)warnings.push('STAY_BOUND_CONFLICT');
  return {I0,I,pace,raw,recommendedMinutes,appliedMinutes,
    appliedSource:fixedMinutes!==null?'fixed':manualMinutes!==null?'manual':'recommended',warnings};
}
function walkingLimit(answers,longWalkingMinutes){
  if(answers[12]===undefined)return null;
  if(answers[12]===0)return 60;if(answers[12]===1)return 180;
  if(answers[12]===2)return finite(longWalkingMinutes,'3시간 이상 실제 보행 한도',180);
  throw new Error('Q13 오류');
}
// 날짜별 공급된 분 단위 이동/운영정보 검증. 경로 API/시간표를 만들어내지 않는다.
function validateTimeline({answers,days,longWalkingMinutes}){
  if(!Array.isArray(days)||!days.length)throw new Error('실제 일자별 일정 필요');
  const issues=[],timelines=[];let unknown=false;
  const add=(day,id,code,uncertain=false)=>{issues.push({day,id,code});if(uncertain)unknown=true;};
  const dates=days.map(d=>d.date);
  if(dates.some(x=>!/^\d{4}-\d{2}-\d{2}$/.test(x)||!Number.isFinite(Date.parse(x))||new Date(x).toISOString().slice(0,10)!==x)||new Set(dates).size!==dates.length||dates.some((x,i)=>i&&Date.parse(x)-Date.parse(dates[i-1])!==86400000))throw new Error('연속된 실제 날짜 필요');
  const expected=answers[10]===0?1:answers[10]===1?2:null;
  if(expected&&days.length!==expected||answers[10]===2&&days.length<3)throw new Error('Q11 여행 기간과 날짜 불일치');
  const limit=walkingLimit(answers,longWalkingMinutes);
  for(const d of days){
    finite(d.start,'하루 시작');finite(d.end,'하루 종료');if(d.end<=d.start||d.end>1440)throw new Error('일일 시간 범위 오류');
    let time=d.start,walk=0;const events=[];
    if(limit===null)add(d.date,null,'WALK_LIMIT_UNKNOWN',true);
    if(!d.origin)add(d.date,null,'ORIGIN_UNKNOWN',true);
    if(!d.transportVerified)add(d.date,null,'TRANSPORT_UNVERIFIED',true);
    for(const s of d.stops||[]){
      for(const key of ['moveMinutes','walkMinutes','stayMinutes'])finite(s[key],key);
      const queue=s.queueMinutes??0;finite(queue,'대기');walk+=s.walkMinutes;
      // moveMinutes는 보행을 포함한 전체 이동이다. walkMinutes를 다시 시간에 더하지 않는다.
      if(s.walkMinutes>s.moveMinutes)throw new Error('보행분은 이동분에 포함되어야 함');
      const arrival=time+s.moveMinutes;
      let start=arrival;
      if(s.openMinute==null||s.closeMinute==null)add(d.date,s.id,'HOURS_UNKNOWN',true);
      if(s.openMinute!=null){finite(s.openMinute,'개장');start=Math.max(start,s.openMinute);}
      start+=queue;
      if(s.fixedStartMinute!=null){finite(s.fixedStartMinute,'고정 시작');if(start>s.fixedStartMinute)add(d.date,s.id,'FIXED_START_CONFLICT');start=Math.max(start,s.fixedStartMinute);}
      let end=start+s.stayMinutes;
      if(s.lastEntryMinute!=null&&start>s.lastEntryMinute)add(d.date,s.id,'LAST_ENTRY_CONFLICT');
      if(s.closeMinute!=null&&end>s.closeMinute)add(d.date,s.id,'CLOSING_CONFLICT');
      const features=s.features||{};
      for(const [q,key] of [[0,'pets'],[1,'accessible']])if((answers[13]||[]).includes(q)){
        if(features[key]===false)add(d.date,s.id,key.toUpperCase()+'_CONFLICT');
        else if(features[key]!==true)add(d.date,s.id,key.toUpperCase()+'_UNKNOWN',true);
      }
      if((answers[13]||[]).includes(2)&&d.raining&&features.indoor!==true)add(d.date,s.id,'INDOOR_PREFERENCE_UNMET',true);
      if(s.redepartMinute!=null){
        finite(s.redepartMinute,'고정 재출발');finite(s.boardingBufferMinutes,'승차 버퍼');finite(s.minVisitMinutes,'최소 관람');
        if(s.redepartMinute-start-s.boardingBufferMinutes<s.minVisitMinutes)add(d.date,s.id,'SHORT_STOP_CONFLICT');
        if(end+s.boardingBufferMinutes>s.redepartMinute)add(d.date,s.id,'FIXED_DEPARTURE_CONFLICT');
        end=Math.max(end,s.redepartMinute);
      }
      if(s.loopDepartures!=null){
        finite(s.stopWalkMinutes,'정류장 보행');finite(s.boardingBufferMinutes,'승차 버퍼');
        if(!Array.isArray(s.loopDepartures))throw new Error('순환버스 시간표 배열 필요');
        s.loopDepartures.forEach(t=>finite(t,'출발 시각'));
        const next=s.loopDepartures.slice().sort((a,b)=>a-b).find(t=>t>=end+s.stopWalkMinutes+s.boardingBufferMinutes);
        walk+=s.stopWalkMinutes;
        if(next===undefined)add(d.date,s.id,'LAST_BUS_CONFLICT');else end=next;
      }
      events.push({id:s.id,arrival,start,end});time=end;
    }
    if(limit!==null&&walk>limit)add(d.date,null,'WALK_LIMIT_CONFLICT');
    if(time>d.end)add(d.date,null,'DAILY_END_CONFLICT');
    if(d.returnDeadline!=null){
      finite(d.returnDeadline,'귀환 마감');finite(d.returnMoveMinutes,'귀환 이동');finite(d.returnBufferMinutes,'귀환 버퍼');
      finite(d.returnWalkMinutes,'귀환 보행');
      if(d.returnWalkMinutes>d.returnMoveMinutes)throw new Error('귀환 보행 범위 오류');
      if(!['arrival_home','departure_hub'].includes(d.returnDeadlineKind))throw new Error('귀환 마감 의미 필수');
      if(time+d.returnMoveMinutes+d.returnBufferMinutes>d.returnDeadline)add(d.date,null,'RETURN_CONFLICT');
      if(limit!==null&&walk<=limit&&walk+d.returnWalkMinutes>limit)add(d.date,null,'WALK_LIMIT_CONFLICT');
      walk+=d.returnWalkMinutes;
    }
    timelines.push({date:d.date,events,end:time,walkingMinutes:walk});
  }
  return {status:issues.some(i=>i.code.endsWith('_CONFLICT'))?'conflict':unknown?'needs_data':'feasible',issues,timelines};
}
module.exports={resolveContentPreference,buildCourseMedia,contentAdjustment,pickDistinctRegions,recommendV2,estimateStay,walkingLimit,validateTimeline};
