(function (D, R) {
  'use strict';
  const h = R.createElement;
  const button = (props,...children) => h(D.DialogButton,{...props,style:{width:"100%",minWidth:0,maxWidth:"100%",boxSizing:"border-box",whiteSpace:"normal",marginBottom:8}},...children);
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
    // Keep lifecycle hooks outside Content: the QAM panel unmounts when closed.
    let colorDisposed=false,colorRestoreRunning=false,colorRestorePending=false;
    const colorHooks=[];
    async function restoreColor() {
      if(colorDisposed)return;
      colorRestorePending=true;
      if(colorRestoreRunning)return;
      colorRestoreRunning=true;
      try {
        // Merge synchronous event bursts without a debounce timer.
        await Promise.resolve();
        while(colorRestorePending&&!colorDisposed) {
          colorRestorePending=false;
          try {
            const result=await api('color_restore');
            if(result.error)console.warn('[HHD color]',result.error);
          } catch(e) {console.warn('[HHD color]',e.message);}
        }
      } finally {colorRestoreRunning=false;}
    }
    const steam=globalThis.SteamClient;
    for(const [owner,name] of [
      [steam?.UI,'RegisterForStartupFinished'],
      [steam?.UI,'RegisterForUIModeChanged'],
      [steam?.GameSessions,'RegisterForAppLifetimeNotifications'],
      [steam?.System,'RegisterForOnResumeFromSuspend']
    ]) {
      try {if(typeof owner?.[name]==='function')colorHooks.push(owner[name](()=>{void restoreColor();}));}
      catch(e) {console.warn('[HHD color] hook '+name,e.message);}
    }
    void restoreColor();
    const saved=globalThis.__hhdNativeState||(globalThis.__hhdNativeState={data:null,error:'',status:'正在连接 HHD…',category:'__home',advanced:false,busy:false,armed:'',profiles:[],profile:'',name:'My 15W'});
    if(typeof saved.name!=='string')saved.name='My 15W';
    const modules=[
      ['tdp','功耗与电池','TDP · 充电上限'],
      ['__compute','CPU 与 GPU','频率 · 动态加速 · 能效'],
      ['__fans','散热风扇','自动散热 · 自定义曲线'],
      ['rgb','灯光','颜色 · 亮度 · 灯效'],
      ['__screen','屏幕色彩','预设 · 饱和度 · 对比度'],
      ['__hud','性能监控','MangoHud · 显示项目 · 即时生效'],
      ['controllers','控制器','手柄模式 · 摇杆 · 振动'],
      ['shortcuts','快捷操作','手柄 · 触屏 · 键盘'],
      ['gamemode','系统操作','电源 · 触屏'],
      ['__profiles','配置管理','保存 · 读取 · 应用'],
      ['hhd','后台设置','功能开关 · 维护'],
      ['__diagnostics','诊断','连接状态 · 硬件读回']
    ];
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
        if(path==='tdp.asus.tdp_v2.custom.tdp') {
          queued.current.set('tdp.asus.tdp_v2.mode','custom');
          if(current.current)put(current.current.state,'tdp.asus.tdp_v2.mode','custom');
        }
        queued.current.set(path,value);
        if(current.current){const d={...current.current,state:copy(current.current.state)};put(d.state,path,value);install(d);}
        clearTimeout(timer.current);timer.current=setTimeout(flush,300);
      }
    function ColorPanel({advanced=false}={}) {
      const [color,setColor]=R.useState(null),[message,setMessage]=R.useState('正在读取屏幕调色…');
      const pending=R.useRef({}),timer=R.useRef(null),running=R.useRef(false),alive=R.useRef(true);
      const load=async()=>{try{const d=await api('color');if(alive.current){setColor(d);setMessage(d.error||'');}}catch(e){if(alive.current)setMessage(e.message);}};
      async function flush() {
        if(running.current||!Object.keys(pending.current).length)return;
        const args=pending.current;pending.current={};running.current=true;
        try{const d=await api('color',args);if(alive.current){setColor({...d,color:{...d.color,...pending.current.changes}});setMessage('调色已应用并保存');}}
        catch(e){if(alive.current){setMessage(e.message);await load();}}
        finally{running.current=false;if(Object.keys(pending.current).length)flush();}
      }
      function send(args) {
        pending.current={...pending.current,...args, ...(args.changes?{changes:{...pending.current.changes,...args.changes}}:{})};
        if(args.preset)delete pending.current.changes;
        clearTimeout(timer.current);timer.current=setTimeout(flush,args.changes?300:0);
        if(args.changes)setColor(c=>({...c,color:{...c.color,...args.changes}}));
      }
      R.useEffect(()=>{alive.current=true;load();return()=>{alive.current=false;clearTimeout(timer.current);flush();};},[]);
      if(!color)return field('屏幕色彩',message,'color-loading');
      const names={native:'原生 / 关闭',natural:'自然增强',vivid:'鲜艳（120 / 10）',soft:'柔和鲜艳'};
      const labels={saturation:'饱和度',contrast:'对比度',vibrance:'自然饱和度',temperature:'色温（正值偏暖）',gamma:'暗部亮度',black:'黑位',gain_r:'红色增益',gain_g:'绿色增益',gain_b:'蓝色增益'};
      const neutral={saturation:100,contrast:0,vibrance:0,temperature:0,gamma:0,black:0,gain_r:100,gain_g:100,gain_b:100};
      const selected=Object.keys(names).find(k=>k==='native'?!color.enabled:color.enabled&&Object.entries({...neutral,...{natural:{saturation:110,contrast:5},vivid:{saturation:120,contrast:10},soft:{saturation:110,contrast:5,vibrance:15}}[k]}).every(([f,v])=>color.color[f]===v))||'custom';
      return h(D.PanelSection,{title:'屏幕色彩'},
        field('状态',message||color.error||(color.applied?'已应用':'等待应用'),'color-status'),
        h(D.ToggleField,{label:'启用屏幕调色',checked:color.enabled,disabled:!color.supported,onChange:v=>send({enabled:!!v})}),
        h(D.DropdownItem,{label:'预设',rgOptions:[...Object.entries(names).map(([data,label])=>({data,label})),{data:'custom',label:'自定义'}],selectedOption:selected,disabled:!color.supported,onChange:o=>{if(o.data!=='custom')send({preset:o.data});}}),
        ...Object.entries(labels).filter(([key])=>advanced||['saturation','contrast','vibrance'].includes(key)).map(([key,label])=>h(D.PanelSectionRow,{key:'color-'+key},h(D.SliderField,{label,value:color.color[key],min:color.ranges[key][0],max:color.ranges[key][1],step:1,showValue:true,disabled:!color.supported||!color.enabled,onChange:v=>send({changes:{[key]:Math.round(v)}})}))),
        button({onClick:load},'重新读取调色状态'),
        field('说明','适用于 SDR 游戏；调色不会让 LCD 获得 OLED 的纯黑。原生预设可随时恢复。','color-help'));
    }
    function HudPanel() {
      const [hud,setHud]=R.useState(null),[error,setHudError]=R.useState(''),[pending,setPending]=R.useState(false);
      const chain=R.useRef(Promise.resolve()),alive=R.useRef(true);
      const load=()=>{setHudError('');api('hud').then(d=>{if(alive.current)setHud(d);}).catch(e=>{if(alive.current)setHudError(e.message);});};
      R.useEffect(()=>{alive.current=true;load();return()=>{alive.current=false;};},[]);
      const send=args=>{
        setPending(true);setHudError('');
        chain.current=chain.current.catch(()=>{}).then(()=>api('hud',args)).then(d=>{if(alive.current)setHud(d);}).catch(e=>{if(alive.current)setHudError(e.message);}).finally(()=>{if(alive.current)setPending(false);});
      };
      if(!hud)return h('div',null,field('性能监控',error||'正在读取 MangoHud…','hud-loading'),error?button({onClick:load},'重试读取监控'):null);
      return h('div',{'data-hhd-hud':true},
        error?h('div',{role:'alert',style:{color:'#ffb2a9',overflowWrap:'anywhere'}},error):null,
        h(D.PanelSection,{title:'显示设置'},h(D.PanelSectionRow,null,h(D.ToggleField,{label:'显示性能监控',checked:hud.enabled,disabled:pending,onChange:v=>send({enabled:!!v})})),field('即时更新',hud.notice,'hud-help')),
        ...hud.groups.map(group=>h(D.PanelSection,{key:group.title,title:group.title},...group.items.map(item=>h(D.PanelSectionRow,{key:item.key},h(D.ToggleField,{label:item.label,checked:!!hud.selected[item.key],disabled:pending,onChange:v=>send({changes:{[item.key]:!!v}})}))))));
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
        try {
          clearTimeout(timer.current);
          await flush();
          while(writing.current||queued.current.size)await new Promise(r=>setTimeout(r,50));
          if(saved.error)throw Error('设置尚未确认成功，请刷新后再操作配置');
          await api('profiles',{operation,name:chosen,state:operation==='set'?current.current.state:null,confirmed:true});
          setStatus(operation==='set'?'配置已保存：'+chosen:'配置操作完成');setError('');
          await loadProfiles();if(operation==='set')setProfile(chosen);if(operation==='del')setProfile('');
          if(operation==='apply')await refresh(true);
        }
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
          return h('div',{key:path,style:{marginBottom:12}},!tags.includes('hide-title')?h('div',{style:{fontSize:14,fontWeight:600,margin:'12px 0 8px',opacity:.85}},label):null,children);
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
          return h(D.PanelSectionRow,{key:path},button({description:help,layout:'below',disabled:busy,onClick:()=>{if(armed===path){setArmed('');change(path,true);}else setArmed(path);}},armed===path?'确认执行：'+label:label));
        }
        if(n.type==='display')return value===undefined||value===null||value===''?null:field(label,String(value),path);
        if(n.type==='version')return null;
        return field(label,'此项为后台内部数据，请在诊断页查看。',path);
      }
      const top=[h('div',{key:'status',role:error?'alert':'status',style:{fontSize:12,lineHeight:1.5,color:error?'#ffb2a9':'#b8c5d6',margin:'0 0 12px',overflowWrap:'anywhere'}},error||status),error?button({key:'retry',onClick:()=>refresh(true)},'重新连接 / 刷新'):null];
      if(!data)return h('div',null,top);
      const navigate=page=>{setCategory(page);setArmed('');};
      const hw=data.hardware||{};
      const activeModule=modules.find(([id])=>id===category);
      if(!activeModule) {
        top.push(h('div',{key:'summary',style:{background:'#1e2c3c',borderRadius:8,padding:14,marginBottom:14}},
          h('div',{style:{fontSize:24,fontWeight:700}},(hw.ppt_pl1_spl??'—')+' W'),
          h('div',{style:{fontSize:12,opacity:.8,marginTop:4}},'持续功耗上限 · '+(get(data.state,'tdp.asus.tdp_v2.mode')==='custom'?'自定义':'预设模式'))));
        top.push(h(D.Focusable,{key:'modules',style:{display:'grid',gridTemplateColumns:'repeat(2, minmax(0, 1fr))',gap:8}},
          ...modules.filter(([id])=>id.startsWith('__')||data.settings[id]).map(([id,title,description])=>
            h(D.DialogButton,{key:id,'data-hhd-module':id,style:{width:'100%',minWidth:0,maxWidth:'100%',height:'100%',padding:'12px 6px',boxSizing:'border-box',whiteSpace:'normal',textAlign:'left'},onClick:()=>navigate(id)},
              h('div',{style:{fontSize:14,fontWeight:600,lineHeight:1.5}},title),
              h('div',{style:{fontSize:10,lineHeight:1.5,opacity:.65,marginTop:4}},description)))));
        return h('div',{'data-hhd-page':'home',style:{padding:'0 8px 12px'}},top);
      }
      top.push(h(D.PanelSection,{key:'nav'},h(D.PanelSectionRow,null,button({onClick:()=>navigate('__home')},'‹ 返回模块')),
        h('div',{style:{fontSize:20,fontWeight:700,margin:'12px 0 4px'}},activeModule[1]),
        h('div',{style:{fontSize:12,opacity:.65,marginBottom:12}},activeModule[2]),
        !['__profiles','__diagnostics','__hud'].includes(category)?h(D.PanelSectionRow,null,h(D.ToggleField,{label:'高级选项',checked:advanced,onChange:setAdvanced})):null));
      if(category==='__hud') {
        top.push(h(HudPanel,{key:'performance-hud'}));
      } else if(category==='__screen') {
        top.push(h(ColorPanel,{key:'screen-color',advanced}));
      } else if(category==='__profiles') {
        top.push(h(D.PanelSection,{key:'profiles',title:'配置'},h(D.DropdownItem,{label:'已有配置',rgOptions:profiles.map(p=>({data:p,label:p})),selectedOption:profile,onChange:o=>setProfile(o.data)}),button({disabled:busy||!profile,onClick:()=>profileAction('apply')},armed==='profile:apply'?'确认应用配置':'应用配置'),button({disabled:busy||!profile,onClick:()=>profileAction('del')},armed==='profile:del'?'确认删除配置':'删除配置'),h(D.TextField,{label:'名称（英文 / 数字 / 空格）',value:name,onChange:e=>setName(typeof e==='string'?e:e.currentTarget?.value??e.target?.value??'')}),button({disabled:busy||!name.trim(),onClick:()=>profileAction('set')},'保存当前设置')));
      } else if(category==='__diagnostics') {
        const leaves=allLeaves(data.settings),visible=leaves.filter(x=>!['hidden','hide'].some(t=>(x.node.tags||[]).includes(t)));
        top.push(h(D.PanelSection,{title:'接口覆盖',key:'coverage'},field('当前设置定义',leaves.length+' 项；'+visible.filter(x=>controls.has(x.type)).length+' 个可见控制项（含不同模式分支）','count'),field('版本',String(data.state.version),'version'),field('维护说明','内置自更新已替换为维护说明；启动、充电灯效等高级项已保留。','maintenance')));
        Object.entries(data.hardware||{}).forEach(([k,v])=>top.push(field(k,Array.isArray(v)?v.join(' / '):String(v??'不可读'),k)));
        leaves.filter(x=>['hidden','hide'].some(t=>(x.node.tags||[]).includes(t))).forEach(x=>top.push(field(x.path,String(get(data.state,x.path,'暂无读数')),x.path)));
        top.push(h(D.PanelSection,{key:'refresh'},button({onClick:()=>refresh(true)},'重新读取硬件')));
      } else if(category==='tdp') {
        const asus=data.settings.tdp?.asus?.children||{};
        const tdp=asus.tdp_v2;
        if(tdp) {
          top.push(h(D.PanelSection,{key:'power',title:'功耗上限'},
            field('实际硬件上限',[hw.ppt_pl1_spl,hw.ppt_pl2_sppt,hw.ppt_fppt].map(x=>x??'?').join(' / ')+' W（持续 / 慢速 / 快速）','power-readback'),
            h(D.PanelSectionRow,{key:'tdp.asus.tdp_v2.custom.tdp'},h(D.SliderField,{label:'目标功耗',value:get(data.state,'tdp.asus.tdp_v2.custom.tdp',15),min:tdp.modes.custom.children.tdp.min,max:tdp.modes.custom.children.tdp.max,step:1,showValue:true,valueSuffix:' W',description:'调整即启用自定义功耗；上限不等于整机实时耗电。',onChange:v=>change('tdp.asus.tdp_v2.custom.tdp',Math.round(v))})),
            h(D.PanelSectionRow,null,button({disabled:busy,onClick:()=>{change('tdp.asus.tdp_v2.custom.boost',false);change('tdp.asus.tdp_v2.custom.tdp',15);}},'一键固定 15W')),
            renderNode(tdp.modes.custom.children.boost,'tdp.asus.tdp_v2.custom.boost'),
            advanced?renderNode({...tdp,modes:Object.fromEntries(Object.entries(tdp.modes).map(([k,v])=>[k,{...v,children:{}}]))},'tdp.asus.tdp_v2'):null));
        }
        if(data.settings.tdp?.battery)top.push(h(D.PanelSection,{key:'battery',title:'电池与充电'},renderNode(data.settings.tdp.battery,'tdp.battery')));
        if(advanced)Object.entries(asus).filter(([k])=>!['tdp_v2','fan'].includes(k)).forEach(([k,n])=>top.push(renderNode(n,'tdp.asus.'+k)));
        if(advanced)Object.entries(data.settings.tdp||{}).filter(([k])=>!['asus','battery','amd_energy'].includes(k)).forEach(([k,n])=>top.push(renderNode(n,'tdp.'+k)));
      } else if(category==='__fans') {
        const n=data.settings.tdp?.asus?.children?.fan;
        top.push(h(D.PanelSection,{key:'fan',title:'风扇控制'},field('实时转速',(hw.fan_rpm||[]).join(' / ')+' RPM','fans'),n?renderNode(n,'tdp.asus.fan'):field('状态','当前设备没有提供风扇控制','fan-unavailable')));
      } else if(category==='__compute') {
        if(data.settings.tdp?.amd_energy)top.push(h(D.PanelSection,{key:'compute'},renderNode(data.settings.tdp.amd_energy,'tdp.amd_energy')));
      } else Object.entries(data.settings[category]||{}).forEach(([k,n])=>top.push(h(D.PanelSection,{key:k},renderNode(n,category+'.'+k))));
      if(!['__profiles','__diagnostics'].includes(category))top.push(h(D.PanelSection,{key:'refresh'},h(D.PanelSectionRow,null,button({disabled:busy,onClick:()=>refresh(true)},'刷新当前状态'))));
      return h('div',{key:category,'data-hhd-page':category,style:{padding:'0 8px 12px'}},top);
    }
    return {title:h('div',{className:D.staticClasses.Title},'Handheld Daemon'),content:h(Content),icon:h('span',null,'HHD'),onDismount(){colorDisposed=true;colorRestorePending=false;for(const hook of colorHooks){try{hook?.unregister();}catch(e){console.warn('[HHD color] unregister',e.message);}}}};
  });
})(DFL, SP_REACT);
