'use strict';
// 현재 홈 finish()의 산식을 순수 함수로 분리한 설명용 모듈.
// 추가한 기능은 입력 검증과 trace뿐이며 정상 입력의 원본 결과를 유지한다.
const github = require('../data/github.json');
const appZip = require('../data/app_zip.json');
function configFor(version){if(!['github','app_zip'].includes(version))throw new Error('version은 github 또는 app_zip');return version==='github'?github:appZip;}
function validateAnswers(a,Q){
  for(const [key,v] of Object.entries(a)){
    const i=Number(key);if(!Number.isInteger(i)||i<0||i>=Q.length)throw new Error('잘못된 문항 인덱스: '+key);
    if(Q[i].multi){if(!Array.isArray(v)||v.length>Q[i].multi||new Set(v).size!==v.length)throw new Error('복수 선택 형식 오류: Q'+(i+1));}
    else if(Array.isArray(v))throw new Error('단일 선택 형식 오류: Q'+(i+1));
    for(const j of (Array.isArray(v)?v:[v]))if(!Number.isInteger(j)||j<0||j>=Q[i].o.length)throw new Error('보기 인덱스 오류: Q'+(i+1));
  }
}
function recommend(answers={}, {version='github',browserLanguage='ko-KR'}={}){
  const {questions:Q,clusters:CL,themes:TH}=configFor(version),a=answers;
  validateAnswers(a,Q);const tot=Array(10).fill(0),contributions=[];
  const foreign=a[5]===1,domestic=a[5]===0;
  const add=(row,reason)=>{row.forEach((v,c)=>tot[c]+=v);contributions.push({reason,scores:[...row]});};
  [0,1,2,4,7,8].forEach(i=>{if(a[i]!==undefined)add(Q[i].s[a[i]],'Q'+(i+1));});
  (a[3]||[]).forEach(j=>add(Q[3].s[j],'Q4 선택 '+j));
  if(a[6]!==undefined)add((foreign?Q[6].sF:Q[6].s)[a[6]],foreign?'Q7 해외':'Q7 국내');
  if(foreign){
    add([0,0,0,0,0,0,2,2,2,2],'해외 방문 기본 가산');
    const lang=(browserLanguage||'ko').toLowerCase();
    if(lang.startsWith('zh'))add([0,0,0,0,0,0,1,0,1,0],'브라우저 zh');
    else if(lang.startsWith('ja'))add([0,0,0,0,0,0,0,1,0,0],'브라우저 ja');
    else if(lang.startsWith('en')||lang.startsWith('es'))add([0,0,0,0,0,0,0,0,0,2],'브라우저 en 또는 es');
  }
  const cand=tot.map((_,c)=>c).filter(c=>!(domestic&&c>=6));
  const w={};let W=0;cand.forEach(c=>{w[c]=Math.pow(2,tot[c]/2);W+=w[c];});
  const prob=c=>w[c]/W;
  const q2=a[1]!==undefined?Q[1].s[a[1]]:tot.map(()=>0);
  const order=cand.slice().sort((x,y)=>tot[y]-tot[x]||q2[y]-q2[x]);
  const p=order[0],s2=order[1],mix=prob(p)<0.5;
  const cats=(a[3]||[]).map(j=>Q[3].cat[j]).filter(c=>c!==null),age=a[0];
  // app_zip의 fr 누락을 의도적으로 고치지 않는다. 해당 경로의 TypeError가 현재 동작이다.
  const regOf=(t,c)=>c>=6?t.fr[c-6]:(age!==undefined?Math.max(-.05,Math.min(.05,.1*(t.rl[age]-1))):0);
  const fitOf=(t,c)=>t.pr.reduce((sum,v,k)=>sum+v*CL[c][3][k],0);
  const ranked=TH.map(t=>{
    const fit=mix?(prob(p)*fitOf(t,p)+prob(s2)*fitOf(t,s2))/(prob(p)+prob(s2)):fitOf(t,p);
    const bonus=.5*cats.reduce((sum,k)=>sum+(k==='night'?t.night:t.pr[k]),0);
    const reg=mix?(prob(p)*regOf(t,p)+prob(s2)*regOf(t,s2))/(prob(p)+prob(s2)):regOf(t,p);
    return {k:t.k,fit,bonus,reg,score:fit+bonus+reg};
  }).sort((x,y)=>y.score-x.score);
  const filters=[];[9,10,11,12].forEach(i=>{if(a[i]!==undefined)filters.push(Q[i].o[a[i]]);});
  (a[13]||[]).forEach(j=>filters.push(Q[13].o[j]));
  const result={p,s2,pts:tot[p],pts2:tot[s2],pr:Math.round(prob(p)*100),pr2:Math.round(prob(s2)*100),mix,picks:ranked.slice(0,3),filters};
  if(version==='app_zip')result.cats=cats;
  return {result,trace:{version,browserLanguage,contributions,totalScores:tot,candidateClusters:cand.map(c=>CL[c][0]),clusterRanking:order.map(c=>({cluster:CL[c][0],index:c,score:tot[c],q2TieBreak:q2[c],weight:w[c],probability:prob(c)})),interestCategories:cats,allThemes:ranked}};
}
module.exports={recommend,configFor};
