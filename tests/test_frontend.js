// Exercises the shipped renderer and its actual callbacks with an isolated React/Decky harness.
// This harness never connects to hardware; live_tests.py verifies the real backend separately.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const settings=JSON.parse(fs.readFileSync(__dirname+'/fixtures/schema.json','utf8'));
const original=JSON.parse(fs.readFileSync(__dirname+'/fixtures/state.json','utf8'));
const clone=x=>JSON.parse(JSON.stringify(x));
const get=(x,p)=>p.split('.').reduce((v,k)=>v?.[k],x);
function put(x,p,v){const a=p.split('.');let n=x;for(let i=0;i<a.length-1;i++)n=n[a[i]]||(n[a[i]]={});n[a.at(-1)]=v;}
let states=[],refs=[],si=0,ri=0,writes=[];
const snapshot=()=>({ok:true,state:clone(original),settings,sections:{tdp:'TDP',rgb:'RGB',controllers:'控制器',gamemode:'通用',shortcuts:'快捷',hhd:'设置'},hardware:{}});
const R={createElement:(type,props,...children)=>({type,props:props||{},children}),useState:init=>{const i=si++;if(!(i in states))states[i]=init;return [states[i],v=>{states[i]=typeof v==='function'?v(states[i]):v;}];},useRef:init=>{const i=ri++;return refs[i]||(refs[i]={current:init});},useEffect:fn=>{fn();}};
const D=new Proxy({definePlugin:fn=>fn,staticClasses:{Title:'title'}},{get:(o,k)=>o[k]||k});
const context={DFL:D,SP_REACT:R,console,Set,Map,Promise,Error,JSON,Math,Number,String,Object,Array,clearTimeout,setInterval,clearInterval,setTimeout:(f,ms)=>setTimeout(f,ms===300||ms===100?0:ms)};
const colorHooks=new Map();let restores=0,unregistered=0;
const register=name=>callback=>{colorHooks.set(name,callback);return {unregister(){unregistered++;}};};
context.SteamClient={UI:{RegisterForStartupFinished:register('startup'),RegisterForUIModeChanged:register('mode')},GameSessions:{RegisterForAppLifetimeNotifications:register('game')},System:{RegisterForOnResumeFromSuspend:register('resume')}};
const factory=vm.runInNewContext(fs.readFileSync(__dirname+'/../dist/index.js','utf8'),context);
const plugin=factory({callPluginMethod:async(method,args)=>{
  if(method==='color_restore'){restores++;return {success:true,result:{ok:true}};}
  if(method==='snapshot')return {success:true,result:clone(states[0]||snapshot())};
  if(method==='apply'){writes.push(args.changes);const d=clone(states[0]);for(const c of args.changes)put(d.state,c.path,c.value);return {success:true,result:{...d,ok:true}};}
  if(method==='color'){
    if(Object.keys(args).length)writes.push({color:args});
    return {success:true,result:{ok:true,supported:true,enabled:true,applied:true,color:{saturation:120,contrast:10,vibrance:0,temperature:0,gamma:0,black:0,gain_r:100,gain_g:100,gain_b:100},ranges:{saturation:[0,150],contrast:[-20,20],vibrance:[0,40],temperature:[-40,40],gamma:[-20,20],black:[-10,10],gain_r:[80,120],gain_g:[80,120],gain_b:[80,120]}}};
  }
  return {success:true,result:snapshot()};
}});
function render(){si=ri=0;return plugin.content.type();}
function find(n,predicate){if(!n)return null;if(Array.isArray(n)){for(const v of n){let r=find(v,predicate);if(r)return r;}return null;}if(typeof n!=='object')return null;if(predicate(n))return n;return find(n.children,predicate);}
let cases=[];
function walk(n,path='',requirements=[]){
  if(!n||typeof n!=='object')return;
  if((n.tags||[]).some(t=>t==='hidden'||t==='hide'))return;
  if(n.type==='container')Object.entries(n.children||{}).forEach(([k,v])=>walk(v,path+'.'+k,requirements));
  else if(n.type==='mode'){
    cases.push({path:path+'.mode',wrapper:path,node:n,requirements});
    Object.entries(n.modes||{}).forEach(([k,v])=>walk(v,path+'.'+k,[...requirements,[path+'.mode',k]]));
  }else if(['bool','int','multiple','discrete','action'].includes(n.type)&&!path.startsWith('hhd.settings.update_'))cases.push({path,wrapper:path,node:n,requirements});
  else if(!n.type)Object.entries(n).forEach(([k,v])=>walk(v,path?path+'.'+k:k,requirements));
}
walk(settings);
(async()=>{
 await new Promise(r=>setImmediate(r));
 assert.strictEqual(restores,1,'Plugin load must restore saved color without opening QAM');
 for(const name of ['startup','mode','game','resume']){
   const before=restores;colorHooks.get(name)();
   await new Promise(r=>setImmediate(r));
   assert.strictEqual(restores,before+1,'Missing lifecycle restore: '+name);
 }
 const beforeBurst=restores;for(const callback of colorHooks.values())callback();
 await new Promise(r=>setImmediate(r));assert.strictEqual(restores,beforeBurst+1,'Event burst must coalesce');
 const beforeIdle=restores;await new Promise(r=>setTimeout(r,20));assert.strictEqual(restores,beforeIdle,'Idle must not restore');
 for(const c of cases){
  states=[];refs=[];states[0]=snapshot();states[3]=c.path.split('.')[0];states[4]=true;refs[0]={current:states[0]};
  for(const [p,v] of c.requirements)put(states[0].state,p,v);
  Object.assign(context.__hhdNativeState,{data:states[0],category:states[3],advanced:true,armed:'',busy:false});
  let tree=render(),row=find(tree,n=>n.props.key===c.wrapper);assert(row,'Missing UI control '+c.path);
  let control=find(row,n=>['ToggleField','SliderField','DropdownItem','ButtonItem'].includes(n.type));assert(control,'Missing interactive field '+c.path);
  let value;
  if(c.node.type==='bool')value=!get(states[0].state,c.path);
  else if(c.node.type==='int')value=c.node.min;
  else if(c.node.type==='discrete')value=c.node.options[0];
  else if(c.node.type==='mode')value=Object.keys(c.node.modes)[0];
  else if(c.node.type==='multiple')value=Object.keys(c.node.options)[0];
  else value=true;
  const before=writes.length;
  if(c.node.type==='action'){
   control.props.onClick();assert.strictEqual(writes.length,before,'Action executed before confirmation');
   tree=render();row=find(tree,n=>n.props.key===c.wrapper);control=find(row,n=>n.type==='ButtonItem');control.props.onClick();
  }else control.props.onChange(control.type==='DropdownItem'?{data:value}:value);
  await new Promise(r=>setTimeout(r,8));
  assert.strictEqual(writes.length,before+1,'No dispatched write '+c.path);
  const result=writes.at(-1)[0];assert.strictEqual(result.path,c.path);assert.strictEqual(result.value,value);
 }
 console.log('PASS: rendered and exercised '+cases.length+' native control callbacks across all mode branches');
 assert(cases.some(c=>c.path==='controllers.rog_ally.rgb_boot'));
 assert(cases.some(c=>c.path==='controllers.rog_ally.rgb_charging'));
 console.log('PASS: advanced boot/charging RGB controls present; actions require confirmation');
 let tree=render();let rgb=find(tree,n=>n.type==='DropdownItem'&&n.props.label==='设置分类');assert(rgb);rgb.props.onChange({data:'rgb'});states=[];refs=[];tree=render();assert.strictEqual(states[3],'rgb','Category lost after remount');console.log('PASS: RGB category survives full Content remount');
 context.__hhdNativeState.category='__screen';states=[];refs=[];states[0]=snapshot();
 tree=render();const panel=find(tree,n=>typeof n.type==='function'&&n.type.name==='ColorPanel');assert(panel,'Screen color page missing');
 states=[];refs=[];let mounted=false;R.useEffect=fn=>{if(!mounted){mounted=true;fn();}};
 function renderColor(){si=ri=0;return panel.type();}
 renderColor();await new Promise(r=>setTimeout(r,8));tree=renderColor();
 const preset=find(tree,n=>n.type==='DropdownItem'&&n.props.label==='预设');assert(preset);preset.props.onChange({data:'natural'});
 await new Promise(r=>setTimeout(r,8));assert.strictEqual(writes.at(-1).color.preset,'natural');
 tree=renderColor();const slider=find(tree,n=>n.type==='SliderField'&&n.props.label==='饱和度');assert(slider);
 const initial=writes.length;slider.props.onChange(115);slider.props.onChange(118);
 await new Promise(r=>setTimeout(r,8));assert.strictEqual(writes.length,initial+1);assert.strictEqual(writes.at(-1).color.changes.saturation,118);
 console.log('PASS: screen-color page presets and debounced slider callbacks');
 plugin.onDismount();assert.strictEqual(unregistered,4);
 const beforeUnload=restores;for(const callback of colorHooks.values())callback();
 await new Promise(r=>setImmediate(r));assert.strictEqual(restores,beforeUnload);
 console.log('PASS: event-driven color restore, event coalescing, idle and hook cleanup');
 process.exit(0);
})().catch(e=>{console.error(e);process.exit(1);});
