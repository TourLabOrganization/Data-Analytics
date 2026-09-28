const fs=require('fs'),path=require('path'),V=require('../tour_scoring/src/scoring-v4.cjs');
const base=require('../tour_scoring/examples/v4_domestic30female.json');
const csv=(rows)=>'\ufeff'+Object.keys(rows[0]).join(',')+'\n'+rows.map(r=>Object.values(r).map(x=>'"'+String(x??'').replaceAll('"','""')+'"').join(',')).join('\n')+'\n';
let cities=[],themes=[],regional=[],details=[];
for(let a=0;a<7;a++)for(let sex of ['male','female','unspecified']){
 let input={...base,answers:{...base.answers,0:a},demographics:{sex,enabled:true}},r=V.recommendV4(input);
 cities.push(...r.allCities.map(t=>({ageIndex:a,sex,index:t.index,region:t.region,name:t.name,v3Score:t.scoreBeforeRegional,regionalAgePart:t.regionalDemographics.agePart||0,regionalSexPart:t.regionalDemographics.sexPart||0,regionalEffectiveBonus:t.regionalDemographics.effectiveBonus,v4Score:t.score,selected:r.cityPicks.some(x=>x.index===t.index)})));
 themes.push(...r.allThemes.map(t=>({ageIndex:a,sex,theme:t.k,v3Score:t.scoreBeforeRegional,regionalRawBonus:t.regionalDemographics.score,regionalEffectiveBonus:t.regionalDemographics.effectiveBonus,v4Score:t.score})));
 for(let region of ['거제','평택','군산','양구','경주','부산','고성']){const x=V.regionalBonus(region,input.answers,input.demographics);regional.push({ageIndex:a,sex,region,...Object.fromEntries(['ageShare','ageBenchmark','ageEvidence','sexShare','sexBenchmark','sexEvidence','agePart','sexPart','score','reason'].map(k=>[k,x[k]??null]))});}
 if(a===2&&sex==='female')details=r.cityPicks;
}
fs.writeFileSync(path.join(__dirname,'results/city_scores_v4.csv'),csv(cities));fs.writeFileSync(path.join(__dirname,'results/theme_scores_v4.csv'),csv(themes));fs.writeFileSync(path.join(__dirname,'results/regional_score_examples.csv'),csv(regional));fs.writeFileSync(path.join(__dirname,'results/example_city_picks.json'),JSON.stringify(details,null,2));
console.log('Exported',cities.length,'city,',themes.length,'theme,',regional.length,'regional rows');
