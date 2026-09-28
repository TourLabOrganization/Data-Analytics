'use strict';
const fs=require('node:fs');
const V4=require('./scoring-v4.cjs'),V2=require('./scoring-v2.cjs');
const input=JSON.parse(fs.readFileSync(process.argv[2],'utf8').replace(/^\uFEFF/,''));
const recommendation=V4.recommendV4(input);
const stays=(input.stayExamples||[]).map(s=>({id:s.id,data_status:input.data_status||'USER_SUPPLIED',...V2.estimateStay({...s,answers:input.answers,preference:recommendation.preference})}));
const timeline=input.timeline?V2.validateTimeline({...input.timeline,answers:input.answers}):null;
process.stdout.write(JSON.stringify({data_status:input.data_status||'USER_SUPPLIED',recommendation,stays,timeline},null,2));
