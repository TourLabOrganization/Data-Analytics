'use strict';
// APP.zip 홈의 prof() 및 시티투어 순위 계산을 분리. 원본의 정규식과 반올림 가중치를 유지.
const {clusters:CL}=require('../data/app_zip.json');
const defaultTours=require('../data/citytour_app_zip.json');
const KW=[/궁|성곽|읍성|산성|사찰|[가-힣]사$|향교|서원|박물관|유적|고분|릉|왕|역사|문화재|한옥|민속|전통|사지|탑|기념관/,/산$|산 |숲|수목원|공원|호수|저수지|계곡|습지|정원|폭포|자연|생태|휴양림|둘레길|꽃|농원|수변/,/체험|테마파크|랜드|케이블카|레일|짚|루지|월드|과학관|전망대|스카이|목장|놀이/,/시장|먹거리|맛|음식|카페|막걸리|와이너리|양조|빵|맥주|술/,/해수욕장|해변|[가-힣]항$|바다|섬|포구|해안|등대|해상|해양|방조제/];
function profile(x){
 const st=String(x[4]||'').split(/→|->|-|,|·/).map(t=>t.replace(/\(.*?\)/g,'').trim()).filter(Boolean),v=[0,0,0,0,0];
 st.forEach(t=>KW.forEach((r,k)=>{if(r.test(t))v[k]++;}));const n=Math.max(1,st.length);
 const night=/야간|야경|나이트|밤|야시장|달빛|별빛/.test(x[1]+x[4])?1:0;
 return {v:v.map(y=>y/n),night,stops:st.length};
}
function recommendCityTours(R,tours=defaultTours){
 if(!R||R.p===undefined||!CL[R.p])return [];
 const w1=CL[R.p][3],w2=R.mix&&CL[R.s2]?CL[R.s2][3]:null,a1=R.pr||100,a2=R.pr2||0,cats=R.cats||[];
 const scored=tours.map((x,i)=>{const p=profile(x);let fit=p.v.reduce((s,y,k)=>s+y*w1[k],0);if(w2)fit=(a1*fit+a2*p.v.reduce((s,y,k)=>s+y*w2[k],0))/(a1+a2);const bonus=.5*cats.reduce((s,k)=>s+(k==='night'?p.night:p.v[k]),0),stopBonus=p.stops>=3?.02:0;return {index:i,region:x[0],name:x[1],route:x[4],fit,bonus,stopBonus,score:fit+bonus+stopBonus,profile:p,raw:x};}).sort((a,b)=>b.score-a.score);
 const seen={},rec=[];for(const z of scored){if(seen[z.region])continue;seen[z.region]=1;rec.push(z);if(rec.length>=5)break;}return rec;
}
module.exports={profile,recommendCityTours};
