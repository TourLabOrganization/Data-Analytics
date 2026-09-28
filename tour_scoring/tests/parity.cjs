'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const root=path.join(__dirname,'..'),{recommend,configFor}=require('../src/scoring.cjs'),{recommendCityTours}=require('../src/citytour.cjs');
function original(version,a,lang){const ctx={DCLogic:class{setState(p){this.state={...this.state,...p}}},navigator:{language:lang},localStorage:{setItem(){}}};vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(root,'reference',version+'_recommendation.js'),'utf8')+';globalThis.ob=new Component()',ctx);ctx.ob.state.ans=a;ctx.ob.finish();return JSON.parse(JSON.stringify(ctx.ob.state.result));}
function capture(f){try{return {value:f()}}catch(e){return {error:e.name,message:e.message}}}
let seed=927;const rand=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
const cases=[{}, {0:0,1:0,2:0,3:[0,1],4:0,5:1,6:0,7:2,8:3}, {5:0}, {5:1}, {3:[7,4],5:0}];
for(let n=0;n<300;n++){const a={};configFor('github').questions.forEach((q,i)=>{if(rand()<.15)return;if(q.multi){a[i]=[...new Set(Array.from({length:Math.floor(rand()*(q.multi+1))},()=>Math.floor(rand()*q.o.length)))];}else a[i]=Math.floor(rand()*q.o.length);});cases.push(a);}
const summary={checkedAt:'2026-09-27',casesPerVersion:cases.length,comparisons:0,successes:0,expectedSourceErrors:0,cityTourComparisons:0,checks:[]};
for(const version of ['github','app_zip'])for(const [i,a] of cases.entries()){
 const lang=['ko-KR','en-US','zh-CN','ja-JP','es-ES'][i%5];const ref=capture(()=>original(version,a,lang)),actual=capture(()=>recommend(a,{version,browserLanguage:lang}).result);assert.deepEqual(actual,ref,'parity '+version+' '+i);summary.comparisons++;if(ref.error)summary.expectedSourceErrors++;else summary.successes++;
 if(version==='app_zip'&&!ref.error){const CT=JSON.parse(fs.readFileSync(path.join(root,'data/citytour_app_zip.json'))),CL=configFor('app_zip').clusters,ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(root,'reference/app_zip_citytour.js'),'utf8'),ctx);const raw=ctx.originalCity.call({CL},ref.value,CT,CL);assert.equal(JSON.stringify(recommendCityTours(ref.value).map(x=>x.raw)),JSON.stringify(raw));summary.cityTourComparisons++;}
}
const a={0:1,1:1,2:1,3:[2,3],5:0},b={...a,9:2,10:2,11:3,12:2,13:[0,1,2]};assert.deepEqual(recommend(a).result.picks,recommend(b).result.picks);summary.checks.push('Q10~Q14 변경은 테마 순위에 영향을 주지 않음');
const errInput=JSON.parse(fs.readFileSync(path.join(root,'examples/app_zip_foreign_error.json')));assert.equal(capture(()=>recommend(errInput.answers,errInput)).error,'TypeError');summary.checks.push('APP.zip 외래객 fr 누락 오류 재현');
assert.throws(()=>recommend({0:99}));summary.checks.push('설명용 모듈의 추가 입력 검증 통과');
fs.writeFileSync(path.join(root,'tests/verification_result.json'),JSON.stringify(summary,null,2));console.log(JSON.stringify(summary,null,2));
