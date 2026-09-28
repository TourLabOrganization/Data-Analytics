'use strict';
const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const V=require('./scoring-v2.cjs'),V4=require('./scoring-v4.cjs'),Q=require('../data/github.json').questions;
const server=http.createServer(async(req,res)=>{
 try{
  if(req.method==='GET'&&req.url==='/'){res.setHeader('Content-Type','text/html; charset=utf-8');return res.end(fs.readFileSync(path.join(__dirname,'../ui/index.html')));}
  if(req.method==='GET'&&req.url==='/questions'){res.setHeader('Content-Type','application/json');return res.end(JSON.stringify({questions:Q,stats:require('../data/hallyu_2026.json')}));}
  if(req.method==='POST'&&req.url==='/calculate'){
   let body='';for await(const chunk of req){body+=chunk;if(body.length>250000)throw new Error('입력 크기 초과');}
   const input=JSON.parse(body),r=V4.recommendV4(input);
   const demo=V.estimateStay({answers:input.answers,preference:r.preference,place:{baseMinutes:60,minMinutes:30,maxMinutes:120,categories:[],contentProfile:{verified:true,source:'SYNTHETIC: 단일 드라마 태그 산식 시연용 가상 장소',media:{drama:1}}}});
   const timeline=input.schedule?V.validateTimeline({...input.schedule,answers:input.answers}):null;
   res.setHeader('Content-Type','application/json');return res.end(JSON.stringify({version:r.version,demographicPolicy:r.demographicPolicy,agePolicy:r.agePolicy,agePlaceRanking:r.agePlaceRanking,preference:r.preference,typeScores:r.legacy.trace.totalScores,themes:r.themePicks,cities:r.cityPicks.map(({raw,...x})=>x),stayDemo:demo,timeline}));
  }
  res.statusCode=404;res.end('Not found');
 }catch(e){res.statusCode=400;res.setHeader('Content-Type','application/json');res.end(JSON.stringify({error:e.message}));}
});
server.listen(Number(process.env.PORT||8787),'127.0.0.1',()=>console.log('신규 설문 시연: http://127.0.0.1:'+server.address().port));
