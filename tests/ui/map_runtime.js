'use strict';
// Exercise the actual map renderer without a browser or external tile requests.
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../../src/constructionsight/command_center');
class Node {
 constructor(){this.style={setProperty(){}};this.children=[];this.value='';this.textContent='';this.innerHTML='';this.clientWidth=821;this.clientHeight=353;this.isConnected=true;}
 replaceChildren(){this.children=[];}
 append(node){this.children.push(node);}
 remove(){this.isConnected=false;}
 setAttribute(){}
 insertAdjacentHTML(position,html){this.innerHTML+=html;}
}
function renderer(options={}){
 const nodes=new Map();
 const node=id=>{if(!nodes.has(id))nodes.set(id,new Node());return nodes.get(id);};
 const context=vm.createContext({
  document:{getElementById:node,querySelector:node,querySelectorAll:()=>[],addEventListener(){},documentElement:new Node()},
  window:{addEventListener(){}},innerWidth:1672,innerHeight:941,URLSearchParams,
  localStorage:{getItem:()=>options.mode||null},Image:Node,icon:()=>'',renderHighwayShields(){},refreshOpenInvestigationDossier:async()=>{},
 });
 vm.runInContext(fs.readFileSync(path.join(root,'usgs_map.js'),'utf8'),context);
 vm.runInContext(fs.readFileSync(path.join(root,'app.js'),'utf8'),context);
 context.fixture={rows:[],map_settings:{url_template:null},...options.data};
 vm.runInContext('data=fixture;online=Boolean(data.map_settings.url_template);drawMap();',context);
 return {nodes,context,images:()=>nodes.get('tiles').children.filter(n=>n.isConnected)};
}
for(const mode of [null,'usgs-imagery-topo','usgs-imagery','usgs-topo']){
 const app=renderer({mode}),service=mode==='usgs-imagery'?'USGSImageryOnly':mode==='usgs-topo'?'USGSTopo':'USGSImageryTopo';
 assert.ok(app.images().length,'Map did not draw tiles in '+mode);
 assert.ok(app.images().every(i=>i.src.startsWith('https://basemap.nationalmap.gov/arcgis/rest/services/'+service+'/MapServer/tile/')));
 assert.equal(vm.runInContext('basemapMode',app.context),mode||'auto','Effective provider changed the saved operator preference');
 const generation=vm.runInContext('mapGeneration',app.context);
 app.images()[0].onerror();
 assert.equal(vm.runInContext('basemapFailed',app.context),true);
 assert.equal(vm.runInContext('tileElements.size',app.context),0,'Failed provider remained in tile cache');
 assert.ok(vm.runInContext('mapGeneration',app.context)>generation);
 assert.ok(app.nodes.get('attribution').innerHTML.includes('offline fallback'));
}
assert.equal(renderer({mode:'offline'}).images().length,0,'Offline preference requested remote tiles');
assert.equal(renderer({data:{mockup_parity:true}}).images().length,0,'Reference capture requested remote tiles');
const local=renderer({data:{local_map:{shields:[]}}});
assert.ok(local.images().every(i=>i.src.startsWith('/api/offline-map/'))&&local.images().length,'Automatic mode lost the installed local basemap');
const configured=renderer({data:{map_settings:{url_template:'https://tiles.example.test/{z}/{x}/{y}.png'}}});
assert.ok(configured.images().every(i=>i.src.startsWith('https://tiles.example.test/'))&&configured.images().length,'Automatic mode replaced the configured provider');
console.log('Actual map renderer: automatic/explicit USGS, outage fallback, offline, reference, local and configured providers PASS');
(async()=>{
 const app=renderer({mode:'offline'}),{context,nodes}=app;
 assert.ok(!nodes.get('map-coverage').textContent.includes('scan complete'),'An unqueried store asserted complete coverage');
 context.api=async()=>({available:false});
 await vm.runInContext('refreshOverviewInvestigationMap()',context);
 assert.ok(nodes.get('map-coverage').textContent.includes('store unavailable'));
 assert.ok(!nodes.get('map-coverage').textContent.includes('scan complete'),'An unavailable store asserted complete coverage');
 let release,calls=[],regions;
 context.investigationRegionOptions=rows=>{regions=rows;};
 const row={investigation_id:'retained:river',title:'Retained Riverside claim',points:[{latitude:34.05,longitude:-117.25}]};
 context.api=url=>{
  calls.push(url);
  if(calls.length===1)return new Promise(resolve=>{release=resolve;});
  return Promise.resolve(url.includes('revision=1')?{available:true,event_cursor:'current'}:
   {available:true,event_cursor:'current',rows:[row],has_more:false});
 };
 const old=vm.runInContext('refreshOverviewInvestigationMap(true)',context);
 nodes.get('county').value='Riverside';
 await vm.runInContext('refreshOverviewInvestigationMap(true)',context);
 release({available:true,event_cursor:'previous'});
 await old;
 for(let i=0;i<8;i++)await Promise.resolve();
 assert.equal(vm.runInContext('overviewInvestigationMap.scope',context),'Riverside','Region change waited for the next poll instead of refreshing');
 assert.equal(calls.length,3,'Superseded region fetched unnecessary source pages');
 assert.ok(calls[2].includes('county=Riverside'));
 assert.equal(regions[0],row,'Committed shared source regions never reached the existing selector');
 assert.ok(nodes.get('points').innerHTML.includes('retained:river'));
 nodes.get('county').value='San Bernardino';
 vm.runInContext('drawMap()',context);
 assert.ok(!nodes.get('points').innerHTML.includes('retained:river'),'A previous-region investigation leaked into the selected map');
 assert.ok(!nodes.get('map-coverage').textContent.includes('scan complete'),'An unqueried region asserted complete coverage');
 nodes.get('county').value='Riverside';
 const restored={...row,title:'Different restored history at the same sequence'};
 let dossierRevision=null;
 context.refreshOpenInvestigationDossier=async revision=>{dossierRevision=revision;};
 context.api=url=>Promise.resolve(url.includes('revision=1')?{available:true,event_cursor:'current',event_anchor:'restored-tip'}:
  {available:true,event_cursor:'current',event_anchor:'restored-tip',rows:[restored],has_more:false});
 await vm.runInContext('refreshOverviewInvestigationMap()',context);
 assert.equal(vm.runInContext('overviewInvestigationMap.rows[0].title',context),restored.title,'Equal event counts hid a restored history');
 assert.equal(dossierRevision.event_anchor,'restored-tip','The open overview dossier was left at its old revision');
 context.api=url=>Promise.resolve(url.includes('revision=1')?{available:true,event_cursor:'current',event_anchor:'new-tip'}:
  {available:true,event_cursor:'current',event_anchor:'other-tip',rows:[row],has_more:false});
 await vm.runInContext('refreshOverviewInvestigationMap()',context);
 assert.equal(vm.runInContext('overviewInvestigationMap.anchor',context),'restored-tip','A mixed-lineage snapshot replaced the last committed projection');
 assert.ok(nodes.get('map-coverage').textContent.includes('refresh failed'),'Mixed-lineage projection was not marked stale');
 console.log('Actual overview projection: absent store, in-flight region change, shared region options and stale-region exclusion PASS');
 console.log('Restored-history anchors: equal-count refresh, open dossier revision and mixed-snapshot rejection PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
