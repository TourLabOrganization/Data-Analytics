const fs=require('node:fs'),{recommendV3}=require('./scoring-v3.cjs');
if(!process.argv[2])throw new Error('입력 JSON 경로 필요');
console.log(JSON.stringify(recommendV3(JSON.parse(fs.readFileSync(process.argv[2],'utf8'))),null,2));
