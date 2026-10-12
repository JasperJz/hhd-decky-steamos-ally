(function (D, R) {
  'use strict';
  const h = R.createElement;
  const maintenance = new Set(['hhd.settings.update_stable', 'hhd.settings.update_beta']);
  const controls = new Set(['bool', 'int', 'multiple', 'discrete', 'action', 'mode']);
  const get = (tree, path, fallback) => path.split('.').reduce((v, k) => v && v[k] !== undefined ? v[k] : undefined, tree) ?? fallback;
  function put(tree, path, value) {
    let n = tree; const p = path.split('.');
    for (let i = 0; i < p.length - 1; i++) n = n[p[i]] || (n[p[i]] = {});
    n[p[p.length - 1]] = value;
  }
  const copy = x => JSON.parse(JSON.stringify(x));
  function field(label, text, key) {
    return h(D.PanelSectionRow, {key}, h(D.Field, {label, description: text, children: null}));
  }
  function allLeaves(schema) {
    const out=[];
    function walk(n,p) {
      if (!n || typeof n !== 'object') return;
      if (n.type === 'container') Object.entries(n.children || {}).forEach(([k,v]) => walk(v,p+'.'+k));
      else if (n.type === 'mode') {out.push({path:p+'.mode',type:'mode',node:n});Object.entries(n.modes || {}).forEach(([k,v]) => walk(v,p+'.'+k));}
      else if (n.type) out.push({path:p,type:n.type,node:n});
      else Object.entries(n).forEach(([k,v]) => walk(v,p?p+'.'+k:k));
    }
    walk(schema,''); return out;
  }
  return D.definePlugin(server => {
    const api = async (method,args={}) => {
      let timeout;
      const r = await Promise.race([
        server.callPluginMethod(method,args),
        new Promise((_,reject) => {timeout=setTimeout(() => reject(Error('插件连接超时，请点刷新重试')), 12000);})
      ]).finally(()=>clearTimeout(timeout));
      if (!r.success) throw Error(r.result || 'Decky 后端调用失败');
      if (!r.result || !r.result.ok) throw Error(r.result?.error || 'HHD 没有返回有效结果');
      return r.result;
    };
    const saved=globalThis.__hhdNativeState||(globalThis.__hhdNativeState={data:null,error:'',status:'正在连接 HHD…',category:'tdp',advanced:true,busy:false,armed:'',profiles:[],profile:'',name:'Decky Profile'});
    const listeners=new Set();
    const setData=v=>{saved.data=v;listeners.forEach(fn=>fn());};
    const setError=v=>{saved.error=v;listeners.forEach(fn=>fn());};
    const setStatus=v=>{saved.status=v;listeners.forEach(fn=>fn());};
    const setCategory=v=>{saved.category=v;listeners.forEach(fn=>fn());};
    const setAdvanced=v=>{saved.advanced=v;listeners.forEach(fn=>fn());};
    const setBusy=v=>{saved.busy=v;listeners.forEach(fn=>fn());};
    const setArmed=v=>{saved.armed=v;listeners.forEach(fn=>fn());};
    const setProfiles=v=>{saved.profiles=v;listeners.forEach(fn=>fn());};
    const setProfile=v=>{saved.profile=v;listeners.forEach(fn=>fn());};
    const setName=v=>{saved.name=v;listeners.forEach(fn=>fn());};
    const current={current:saved.data},writing={current:false},queued={current:new Map()},timer={current:null},reading={current:false};
      const install = d => {current.current=d;if(true)setData(d);};
      async function refresh(manual=false) {
        if (writing.current || queued.current.size || reading.current) return;
        reading.current=true;
        try {const response=await api('snapshot',{known_version:current.current?.state?.version});const d={...current.current,...response};if(!writing.current&&!queued.current.size){install(d);setError('');if(manual)setStatus('已重新读取后台和硬件');}}
        catch(e){if(true)setError(e.message);}
        finally {reading.current=false;}
      }
      async function flush() {
        if(writing.current || !queued.current.size)return;
        const changes=[...queued.current].map(([path,value])=>({path,value}));queued.current.clear();writing.current=true;
        if(true){setBusy(true);setStatus('正在写入…');setError('');}
        try {
          const d=await api('apply',{changes});
          // Do not overwrite a second slider change queued while the first request was in flight.
          queued.current.forEach((value,path)=>put(d.state,path,value));
          install(d);if(true)setStatus('设置已被后台接受；硬件状态见下方');
        } catch(e) {if(true){setError(e.message);setStatus('未确认成功，请刷新核对');}}
        finally {writing.current=false;if(true)setBusy(false);if(queued.current.size)timer.current=setTimeout(flush,100);}
      }
      function change(path,value) {
        queued.current.set(path,value);
        if(current.current){const d={...current.current,state:copy(current.current.state)};put(d.state,path,value);install(d);}
        clearTimeout(timer.current);timer.current=setTimeout(flush,300);
      }
    function Content() {
      const [data,localData]=R.useState(saved.data);
      const [error,localError]=R.useState(saved.error);
      const [status,localStatus]=R.useState(saved.status);
      const [category,localCategory]=R.useState(saved.category);
      const [advanced,localAdvanced]=R.useState(saved.advanced);
      const [busy,localBusy]=R.useState(saved.busy);
      const [armed,localArmed]=R.useState(saved.armed);
      const [profiles,localProfiles]=R.useState(saved.profiles);
      const [profile,localProfile]=R.useState(saved.profile);
      const [name,localName]=R.useState(saved.name);
      R.useEffect(()=>{const sync=()=>{localData(saved.data);localError(saved.error);localStatus(saved.status);localCategory(saved.category);localAdvanced(saved.advanced);localBusy(saved.busy);localArmed(saved.armed);localProfiles(saved.profiles);localProfile(saved.profile);localName(saved.name);};listeners.add(sync);sync();refresh(true);const interval=setInterval(()=>refresh(),4000);return()=>{listeners.delete(sync);clearInterval(interval);};},[]);
      async function loadProfiles() {
        try {const d=await api('profiles');setProfiles(d.result || []);}catch(e){setError(e.message);}
      }
      R.useEffect(()=>{if(category==='__profiles')loadProfiles();},[category]);
      async function profileAction(operation) {
        const chosen=operation==='set'?name:profile;
        const action='profile:'+operation;
        if(['apply','del'].includes(operation) && armed!==action){setArmed(action);return;}
        setArmed('');setBusy(true);
        try {await api('profiles',{operation,name:chosen,state:operation==='set'?current.current.state:null,confirmed:true});setStatus('配置操作完成');setError('');await loadProfiles();if(operation==='apply')await refresh(true);}
        catch(e){setError(e.message);}finally{setBusy(false);}
      }
      function renderNode(n,path,depth=0) {
        if(!n || typeof n!=='object')return null;
        const tags=n.tags||[];
        if(tags.includes('hidden')||tags.includes('hide'))return null;
        if(!advanced&&(tags.includes('advanced')||tags.includes('expert')))return null;
        const value=get(data.state,path,n.default),label=n.title||path.split('.').pop();
        const help=[n.hint,advanced&&tags.includes('expert')?'高级选项':null].filter(Boolean).join(' ');
        if(n.type==='container') {
          const children=Object.entries(n.children||{}).map(([k,v])=>renderNode(v,path+'.'+k,depth+1)).filter(Boolean);
          if(!children.length)return n.hint?field(label,n.hint,path):null;
          return h(D.PanelSection,{title:tags.includes('hide-title')?undefined:label,key:path},children);
        }
        if(n.type==='mode') {
          const selected=get(data.state,path+'.mode',n.default);
          const options=Object.entries(n.modes||{}).map(([k,v])=>({data:k,label:v.title||k}));
          return h('div',{key:path},h(D.PanelSectionRow,null,h(D.DropdownItem,{label,description:help,rgOptions:options,selectedOption:selected,onChange:o=>change(path+'.mode',o.data),disabled:busy})),renderNode(n.modes?.[selected]?{...n.modes[selected],tags:[...(n.modes[selected].tags||[]),'hide-title']}:null,path+'.'+selected,depth+1));
        }
        if(n.type==='bool')return h(D.PanelSectionRow,{key:path},h(D.ToggleField,{label,description:help,checked:!!value,disabled:busy,onChange:v=>change(path,!!v)}));
        if(n.type==='int')return h(D.PanelSectionRow,{key:path},h(D.SliderField,{label,description:help,value:Number(value??n.min),min:n.min,max:n.max,step:n.step||1,showValue:true,valueSuffix:n.unit||'',disabled:busy,onChange:v=>change(path,Math.round(v))}));
        if(n.type==='multiple'||n.type==='discrete') {
          const options=n.type==='discrete'?(n.options||[]).map(v=>({data:v,label:String(v)+(n.unit||'')})):Object.entries(n.options||{}).map(([k,v])=>({data:k,label:typeof v==='string'?v:(v.title||k)}));
          return h(D.PanelSectionRow,{key:path},h(D.DropdownItem,{label,description:help,rgOptions:options,selectedOption:value,disabled:busy,onChange:o=>change(path,o.data)}));
        }
        if(n.type==='action') {
          if(maintenance.has(path))return field(label,'本机采用维护更新；已阻止会卸载功耗依赖并卡住后台的内置更新。',path);
          return h(D.PanelSectionRow,{key:path},h(D.ButtonItem,{description:help,layout:'below',disabled:busy,onClick:()=>{if(armed===path){setArmed('');change(path,true);}else setArmed(path);}},armed===path?'确认执行：'+label:label));
        }
        if(n.type==='display')return value===undefined||value===null||value===''?null:field(label,String(value),path);
        if(n.type==='version')return null;
        return field(label,'此项为后台内部数据，请在诊断页查看。',path);
      }
      const top=[h('div',{key:'status',style:{fontSize:'12px',opacity:0.75,marginBottom:'8px'}},error||status),error?h(D.ButtonItem,{key:'retry',onClick:()=>refresh(true)},'重新连接 / 刷新'):null];
      if(!data)return h('div',null,top);
      const options=Object.entries(data.sections||{}).filter(([k])=>Object.keys(data.settings[k]||{}).length).map(([data,label])=>({data,label}));
      options.push({data:'__profiles',label:'保存 / 应用配置'},{data:'__diagnostics',label:'诊断与硬件读回'});
      top.push(h(D.PanelSection,{key:'nav'},h(D.DropdownItem,{label:'设置分类',rgOptions:options,selectedOption:category,onChange:o=>{setCategory(o.data);setArmed('');}}),h(D.ToggleField,{label:'显示高级设置',checked:advanced,onChange:setAdvanced})));
      if(category==='__profiles') {
        top.push(h(D.PanelSection,{key:'profiles',title:'配置'},h(D.DropdownItem,{label:'已有配置',rgOptions:profiles.map(p=>({data:p,label:p})),selectedOption:profile,onChange:o=>setProfile(o.data)}),h(D.ButtonItem,{disabled:busy||!profile,onClick:()=>profileAction('apply')},armed==='profile:apply'?'确认应用配置':'应用配置'),h(D.ButtonItem,{disabled:busy||!profile,onClick:()=>profileAction('del')},armed==='profile:del'?'确认删除配置':'删除配置'),h(D.TextField,{label:'名称（英文 / 数字 / 空格）',value:name,onChange:setName}),h(D.ButtonItem,{disabled:busy||!name.trim(),onClick:()=>profileAction('set')},'保存当前设置')));
      } else if(category==='__diagnostics') {
        const leaves=allLeaves(data.settings),visible=leaves.filter(x=>!['hidden','hide'].some(t=>(x.node.tags||[]).includes(t)));
        top.push(h(D.PanelSection,{title:'接口覆盖',key:'coverage'},field('当前设置定义',leaves.length+' 项；'+visible.filter(x=>controls.has(x.type)).length+' 个可见控制项（含不同模式分支）','count'),field('版本',String(data.state.version),'version'),field('维护说明','内置自更新已替换为维护说明；启动、充电灯效等高级项已保留。','maintenance')));
        Object.entries(data.hardware||{}).forEach(([k,v])=>top.push(field(k,Array.isArray(v)?v.join(' / '):String(v??'不可读'),k)));
        leaves.filter(x=>['hidden','hide'].some(t=>(x.node.tags||[]).includes(t))).forEach(x=>top.push(field(x.path,String(get(data.state,x.path,'暂无读数')),x.path)));
        top.push(h(D.PanelSection,{key:'refresh'},h(D.ButtonItem,{onClick:()=>refresh(true)},'重新读取硬件')));
      } else Object.entries(data.settings[category]||{}).forEach(([k,n])=>top.push(renderNode(n,category+'.'+k)));
      const hw=data.hardware||{};
      top.push(h(D.PanelSection,{title:'硬件读回',key:'hardware'},field('TDP 快 / 慢 / 持续',[hw.ppt_fppt,hw.ppt_pl2_sppt,hw.ppt_pl1_spl].map(x=>x??'?').join(' / ')+' W','tdp'),field('CPU 动态加速（睿频）',hw.cpu_boost==='1'?'开启':hw.cpu_boost==='0'?'关闭':'不可读','boost'),field('风扇 RPM',(hw.fan_rpm||[]).join(' / '),'fans'),field('充电上限',hw.charge_limit==='0'?'固件默认':(hw.charge_limit??'?')+'%','charge')));
      return h('div',null,top);
    }
    return {title:h('div',{className:D.staticClasses.Title},'Handheld Daemon'),content:h(Content),icon:h('span',null,'HHD'),onDismount(){}};
  });
})(DFL, SP_REACT);
