// APP.zip 홈에서 추출한 KW, prof, 순위 계산. R, CT, CL은 외부 입력으로 분리.
function originalCity(R,CT,CL){
  const KW=[/궁|성곽|읍성|산성|사찰|[가-힣]사$|향교|서원|박물관|유적|고분|릉|왕|역사|문화재|한옥|민속|전통|사지|탑|기념관/,/산$|산 |숲|수목원|공원|호수|저수지|계곡|습지|정원|폭포|자연|생태|휴양림|둘레길|꽃|농원|수변/,/체험|테마파크|랜드|케이블카|레일|짚|루지|월드|과학관|전망대|스카이|목장|놀이/,/시장|먹거리|맛|음식|카페|막걸리|와이너리|양조|빵|맥주|술/,/해수욕장|해변|[가-힣]항$|바다|섬|포구|해안|등대|해상|해양|방조제/];
  const prof=x=>{if(x.__p)return x.__p;const st=String(x[4]||'').split(/→|->|-|,|·/).map(t=>t.replace(/\(.*?\)/g,'').trim()).filter(Boolean);const v=[0,0,0,0,0];st.forEach(t=>KW.forEach((r,k)=>{if(r.test(t))v[k]++;}));const n=Math.max(1,st.length);const night=/야간|야경|나이트|밤|야시장|달빛|별빛/.test(x[1]+x[4])?1:0;return (x.__p={v:v.map(y=>y/n),night,stops:st.length});};
  let rec=[];
  if(CT&&CT.length&&R&&R.p!==undefined&&this.CL[R.p]){const w1=this.CL[R.p][3],w2=R.mix&&this.CL[R.s2]?this.CL[R.s2][3]:null,a1=(R.pr||100),a2=(R.pr2||0);const cats=R.cats||[];
    const sc=CT.map((x,i)=>{const p=prof(x);let fit=p.v.reduce((s,y,k)=>s+y*w1[k],0);if(w2)fit=(a1*fit+a2*p.v.reduce((s,y,k)=>s+y*w2[k],0))/(a1+a2);const bonus=0.5*cats.reduce((s,k)=>s+(k==='night'?p.night:p.v[k]),0);return {x,i,s:fit+bonus+(p.stops>=3?.02:0)};}).sort((a,b)=>b.s-a.s);
    const seen={};for(const z of sc){if(seen[z.x[0]])continue;seen[z.x[0]]=1;rec.push(z.x);if(rec.length>=5)break;}}

return rec;
}
