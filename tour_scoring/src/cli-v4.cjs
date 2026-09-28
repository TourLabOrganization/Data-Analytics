const fs=require('node:fs'),V=require('./scoring-v4.cjs');
const file=process.argv[2];if(!file)throw Error('입력 JSON 경로 필요');console.log(JSON.stringify(V.recommendV4(JSON.parse(fs.readFileSync(file,'utf8'))),null,2));
