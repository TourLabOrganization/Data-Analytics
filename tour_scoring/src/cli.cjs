'use strict';
const fs=require('fs'),{recommend}=require('./scoring.cjs'),{recommendCityTours}=require('./citytour.cjs');
try{const input=JSON.parse(fs.readFileSync(process.argv[2]||'examples/domestic.json','utf8'));const out=recommend(input.answers,input);if(input.version==='app_zip')out.cityTours=recommendCityTours(out.result);console.log(JSON.stringify(out,null,2));}catch(e){console.error(JSON.stringify({error:e.name,message:e.message,note:'app_zip 외래객 fr 누락은 원본 오류를 그대로 재현합니다.'},null,2));process.exitCode=1;}
