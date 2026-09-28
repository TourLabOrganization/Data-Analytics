const A=require('node:assert/strict'),fs=require('node:fs'),V=require('../src/scoring-v2.cjs');let n=0;
const test=(s,f)=>{f();n++;console.log('PASS '+s)},near=(x,y)=>A.ok(Math.abs(x-y)<1e-10);
const a={0:2,1:0,2:2,5:1},h={residenceArea:'JP',experienced:true};
const pref=r=>V.resolveContentPreference(a,{...h,contentPreference:{drama:{rating:r,answered:true}}});
const media=m=>({verified:true,source:'synthetic fixture, not production',media:m});
for(const [r,v]of[[0,-.05],[.25,-.025],[.5,0],[.75,.025],[1,.05]])test('직접 응답 '+r,()=>near(V.contentAdjustment(pref(r),media({drama:1})).score,v));
test('통계 미응답',()=>near(V.contentAdjustment(V.resolveContentPreference(a,h),media({drama:1})).score,.00482));
for(const [s,ans,hh]of[['국내',{...a,5:0},h],['60대',{...a,0:5},h],['10대 미확인',{...a,0:0},h],['경험 없음',a,{...h,experienced:false}],['국가 없음',a,{}]])test(s,()=>A.equal(V.resolveContentPreference(ans,hh).eligible,false));
test('15~19세 대상',()=>A.equal(V.resolveContentPreference({...a,0:0},{...h,age15to19:true}).eligible,true));
test('보통과 미응답 구분',()=>A.equal(pref(.5).values.drama.source,'direct'));
test('잘못된 rating',()=>A.throws(()=>pref(.6)));
test('합 1 초과',()=>A.throws(()=>V.contentAdjustment(pref(1),media({drama:1,music:1}))));
test('근거 없는 태그',()=>A.throws(()=>V.contentAdjustment(pref(1),{media:{drama:1}})));
test('미해결 경유지 분모',()=>near(V.buildCourseMedia([{id:'a',contentProfile:media({drama:1})}],4).media.drama,.25));
test('경유지 중복',()=>A.throws(()=>V.buildCourseMedia([{id:'a'},{id:'a'}],2)));
test('가산 후 지역 대표 선정',()=>{const p=V.resolveContentPreference(a,{contentPreference:{drama:{rating:1,answered:true},music:{rating:0,answered:true}}});const rows=[['A','A1',.6,{music:1}],['A','A2',.58,{drama:1}],['B','B1',.61,{}],['C','C1',.53,{drama:1}]].map(([region,name,b,m],index)=>({region,name,index,score:b+V.contentAdjustment(p,media(m)).score}));A.deepEqual(V.pickDistinctRegions(rows).map(x=>x.name),['A2','B1','C1']);});
const place={baseMinutes:60,minMinutes:30,maxMinutes:120,categories:[],contentProfile:media({drama:1})};
for(const [r,m]of[[1,80],[.5,75],[0,65]])test('체류 '+r,()=>A.equal(V.estimateStay({answers:a,preference:pref(r),place}).recommendedMinutes,m));
test('고정 시간 우선',()=>A.equal(V.estimateStay({answers:a,preference:pref(1),place,fixedMinutes:90,manualMinutes:80}).appliedMinutes,90));
test('수동 하한 충돌 보존',()=>{let r=V.estimateStay({answers:a,preference:pref(1),place,manualMinutes:10});A.equal(r.appliedMinutes,10);A.ok(r.warnings.includes('STAY_BOUND_CONFLICT'));});
test('체류 범위 거부',()=>A.throws(()=>V.estimateStay({answers:a,preference:pref(1),place:{...place,minMinutes:80}})));
const day=()=>({date:'2026-10-01',origin:'TEST',transportVerified:true,start:540,end:1080,stops:[{id:'x',moveMinutes:30,walkMinutes:10,stayMinutes:60,openMinute:600,closeMinute:1020,features:{pets:true,accessible:true}}]});
const check=(d,ans={12:0})=>V.validateTimeline({answers:ans,days:[d]});
test('개장 대기',()=>{let r=check(day());A.equal(r.status,'feasible');A.equal(r.timelines[0].events[0].start,600);});
for(const [s,change,code]of[
 ['폐장',d=>d.stops[0].closeMinute=620,'CLOSING_CONFLICT'],
 ['운영시간 누락',d=>delete d.stops[0].openMinute,'HOURS_UNKNOWN'],
 ['보행',d=>Object.assign(d.stops[0],{moveMinutes:90,walkMinutes:70}),'WALK_LIMIT_CONFLICT'],
 ['고정코스 부족',d=>Object.assign(d.stops[0],{redepartMinute:625,boardingBufferMinutes:5,minVisitMinutes:30}),'SHORT_STOP_CONFLICT'],
 ['막차',d=>Object.assign(d.stops[0],{loopDepartures:[600],stopWalkMinutes:5,boardingBufferMinutes:5}),'LAST_BUS_CONFLICT'],
 ['귀환',d=>Object.assign(d,{returnDeadline:700,returnMoveMinutes:50,returnBufferMinutes:5,returnWalkMinutes:5,returnDeadlineKind:'arrival_home'}),'RETURN_CONFLICT']])test(s,()=>{let d=day();change(d);A.ok(check(d).issues.some(x=>x.code===code));});
test('3시간 초과 수치 필수',()=>A.throws(()=>check(day(),{12:2})));
test('기간 불일치',()=>A.throws(()=>check(day(),{10:1,12:0})));
test('잘못된 날짜',()=>{let d=day();d.date='2026-02-31';A.throws(()=>check(d));});
test('무장애 미확인',()=>{let d=day();delete d.stops[0].features.accessible;A.equal(check(d,{12:0,13:[1]}).status,'needs_data');});
test('280개 미매핑 점수 보존',()=>{let r=V.recommendV2(require('../examples/v2_domestic.json'));A.equal(r.allCities.length,280);r.allCities.forEach(x=>near(x.score,x.legacyScore));A.equal(r.cityPicks.length,5);});
test('외래객 계산',()=>A.equal(V.recommendV2({answers:a}).allThemes.length,5));
test('필수 문항',()=>A.throws(()=>V.recommendV2({answers:{}})));
fs.writeFileSync('examples/v2_verification.json',JSON.stringify({passed:n,failed:0,scope:'pure functions; not production integration'},null,2));console.log(n+' new tests passed');
