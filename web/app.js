"use strict";
// PMS Toolkit dashboard — dependency-free, GitHub-Pages friendly.
// Loads ./data/pms.json by default; supports importing another company's pms.json.

let DATA = {meta:{}, classes:[]};
let active = null, sortKey = null, sortDir = 1;

const $ = s => document.querySelector(s);
const $$ = s => Array.from(document.querySelectorAll(s));
const esc = s => (s==null?'':String(s)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function hl(s,q){s=esc(s);if(!q)return s;try{return s.replace(new RegExp('('+q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')','ig'),'<span class="hl">$1</span>')}catch(e){return s}}
const CLASSES = () => DATA.classes || [];

// ---------- data loading ----------
async function boot(){
  setData({meta:{}, classes:[]});      // start empty; the Get-started modal drives loading
  await loadDB();                       // preload schedule dims + sample stress data
  openModal(true);                      // first-run: show Get started
}
function setData(d){
  DATA = d && d.classes ? d : {meta:{}, classes:[]};
  active = CLASSES()[0] || null;
  $('#b-company').textContent = DATA.meta.company || 'PMS';
  $('#b-classes').textContent = CLASSES().length + ' classes';
  $('#b-comps').textContent = CLASSES().reduce((a,c)=>a+(c.component_count||0),0) + ' components';
  THK=null; SPEC=null;
  renderOverview(); renderList(); renderMain(); renderValidate(); renderExport();
}

// ---------- tabs ----------
$$('.tab').forEach(t=>t.onclick=()=>{
  $$('.tab').forEach(x=>x.classList.remove('active'));
  $$('.view').forEach(x=>x.classList.remove('active'));
  t.classList.add('active'); $('#'+t.dataset.v).classList.add('active');
  if(t.dataset.v==='schema') renderSchema();
  if(t.dataset.v==='deviation') renderDeviation();
  if(t.dataset.v==='thickness') renderThickness();
  if(t.dataset.v==='compliance') renderCompliance();
  if(t.dataset.v==='specbuilder') renderSpecBuilder();
});

// ---------- overview ----------
function distn(keyFn){
  const m={}; CLASSES().forEach(c=>{const k=keyFn(c)||'—'; m[k]=(m[k]||0)+1;});
  return Object.entries(m).sort((a,b)=>b[1]-a[1]);
}
function barChart(title, pairs){
  const max=Math.max(1,...pairs.map(p=>p[1]));
  const rows=pairs.slice(0,12).map(([k,v])=>`
    <div style="display:flex;align-items:center;gap:8px;margin:3px 0">
      <div style="width:150px;text-align:right;color:var(--mut);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(k)}</div>
      <div class="bar" style="width:${Math.round(220*v/max)}px"></div>
      <div style="font-size:12px">${v}</div>
    </div>`).join('');
  return `<div class="kv"><div class="k">${esc(title)}</div><div style="margin-top:8px">${rows||'<span class="muted">—</span>'}</div></div>`;
}
function ratingOf(c){const m=/CL\.?\s*(\d{2,4})/i.exec(c.flange_rating_face||'');return m?('CL'+m[1]):'—';}
function renderOverview(){
  const n=CLASSES().length, comps=CLASSES().reduce((a,c)=>a+(c.component_count||0),0);
  const fullHdr=CLASSES().filter(c=>c.service&&c.main_material&&c.flange_rating_face).length;
  const pt=CLASSES().filter(c=>c.temp_C&&c.press_barg).length;
  $('#overview').innerHTML = `
   <div class="cards">
     <div class="kv"><div class="k">Company</div><div class="v">${esc(DATA.meta.company||'—')}</div></div>
     <div class="kv"><div class="k">Pipe classes</div><div class="v">${n}</div></div>
     <div class="kv"><div class="k">Component rows</div><div class="v">${comps}</div></div>
     <div class="kv"><div class="k">Full header</div><div class="v">${n?Math.round(100*fullHdr/n):0}%</div></div>
     <div class="kv"><div class="k">With P-T table</div><div class="v">${pt}</div></div>
   </div>
   <div class="cards">
     ${barChart('Classes by main material', distn(c=>c.main_material))}
     ${barChart('Classes by flange rating', distn(ratingOf))}
     ${barChart('Component rows by part (top)', partDistn())}
   </div>`;
}
function partDistn(){
  const m={}; CLASSES().forEach(c=>(c.components||[]).forEach(x=>{if(x.part)m[x.part]=(m[x.part]||0)+1;}));
  return Object.entries(m).sort((a,b)=>b[1]-a[1]);
}

// ---------- explorer ----------
function renderList(filter=''){
  const q=filter.toLowerCase(), list=$('#cl-list'); if(!list)return; list.innerHTML='';
  CLASSES().filter(c=>!q||[c.class,c.service,c.main_material,c.flange_rating_face].some(v=>(v||'').toLowerCase().includes(q)))
   .forEach(c=>{const d=document.createElement('div');
     d.className='cl'+(active&&active.class===c.class?' active':'');
     d.innerHTML=`<div class="c">${esc(c.class)}</div><div class="m">${esc(c.main_material||'')} · ${esc(c.service||'')}</div>`;
     d.onclick=()=>{active=c;sortKey=null;renderList(filter);renderMain();};
     list.appendChild(d);});
}
function ptTable(c){
  if(!c.temp_C||!c.press_barg||!c.temp_C.length)return '';
  let th='<tr><th>Temp °C</th>',tr='<tr><td class="muted">Press barg</td>';
  const n=Math.min(c.temp_C.length,c.press_barg.length);
  for(let i=0;i<n;i++){th+=`<th>${esc(c.temp_C[i])}</th>`;tr+=`<td>${esc(c.press_barg[i])}</td>`;}
  return `<div class="pt"><div class="muted" style="margin:8px 0 4px">Pressure–Temperature rating</div><table>${th}</tr>${tr}</tr></table></div>`;
}
function compRows(comps,q){
  return comps.map(x=>`<tr><td>${hl(x.part||'',q)}</td><td class="sym">${hl(x.symbol||'',q)}</td>
    <td>${hl(x.size_from||'',q)}</td><td>${hl(x.size_to||'',q)}</td>
    <td class="desc">${hl(x.description||'',q)}</td><td class="muted">${esc((x.notes||[]).join(' '))}</td></tr>`).join('');
}
function sortComps(comps){if(!sortKey)return comps;const c=[...comps];
  c.sort((a,b)=>((a[sortKey]||'')+'').localeCompare((b[sortKey]||'')+'',undefined,{numeric:true})*sortDir);return c;}
function renderMain(){
  const m=$('#cl-main'); if(!m)return;
  if(!active){m.innerHTML='<p class="muted" style="padding:16px">Select a class on the left.</p>';return;}
  const c=active, cq=($('#compq')&&$('#compq').value||'').trim();
  let comps=c.components||[];
  if(cq)comps=comps.filter(x=>[x.part,x.symbol,x.size_from,x.size_to,x.description].some(v=>(v||'').toLowerCase().includes(cq.toLowerCase())));
  comps=sortComps(comps);
  m.innerHTML=`<h2>${esc(c.class)}</h2><div class="sub">${esc(c.service||'')}</div>
    <div class="cards">
      <div class="kv"><div class="k">Main material</div><div class="v" style="font-size:15px">${esc(c.main_material||'—')}</div></div>
      <div class="kv"><div class="k">Corr. allowance</div><div class="v" style="font-size:15px">${esc(c.corrosion_allowance||'—')}</div></div>
      <div class="kv"><div class="k">Flange rating & face</div><div class="v" style="font-size:15px">${esc(c.flange_rating_face||'—')}</div></div>
      <div class="kv"><div class="k">Components</div><div class="v">${c.component_count||0}</div></div>
    </div>${ptTable(c)}
    ${c.particular_notes?`<div class="notebox"><b>Particular notes:</b> ${esc(c.particular_notes)}</div>`:''}
    <div class="toolbar"><input id="compq" type="text" placeholder="Filter components…" value="${esc(cq)}" style="width:260px">
      <span class="count">${comps.length} rows</span></div>
    <table id="ct"><thead><tr>
      <th data-k="part">Part</th><th data-k="symbol">Sym</th><th data-k="size_from">From</th>
      <th data-k="size_to">To</th><th data-k="description">Description</th><th>Notes</th>
    </tr></thead><tbody>${compRows(comps,cq)}</tbody></table>`;
  const q=$('#compq'); q.oninput=()=>{const p=q.selectionStart;renderMain();const e=$('#compq');e.focus();e.setSelectionRange(p,p);};
  m.querySelectorAll('th[data-k]').forEach(th=>th.onclick=()=>{const k=th.dataset.k;sortDir=(sortKey===k?-sortDir:1);sortKey=k;renderMain();});
}
// global search
$('#global').oninput=e=>{
  const q=e.target.value.trim().toLowerCase();
  $$('.tab').forEach(x=>x.classList.remove('active'));$$('.view').forEach(x=>x.classList.remove('active'));
  document.querySelector('.tab[data-v=explorer]').classList.add('active');$('#explorer').classList.add('active');
  const m=$('#cl-main');
  if(!q){renderMain();return;}
  const rows=[];CLASSES().forEach(c=>(c.components||[]).forEach(x=>{
    if([c.class,x.part,x.symbol,x.size_from,x.size_to,x.description].some(v=>(v||'').toLowerCase().includes(q)))rows.push({c,x});}));
  const shown=rows.slice(0,600);
  m.innerHTML=`<h2>Global search</h2><div class="sub">${rows.length} matches${rows.length>600?' (first 600)':''} for “${esc(q)}”</div>
   <table><thead><tr><th>Class</th><th>Part</th><th>Sym</th><th>From</th><th>To</th><th>Description</th></tr></thead>
   <tbody>${shown.map(r=>`<tr><td>${esc(r.c.class)}</td><td>${hl(r.x.part||'',q)}</td><td class="sym">${hl(r.x.symbol||'',q)}</td>
     <td>${hl(r.x.size_from||'',q)}</td><td>${hl(r.x.size_to||'',q)}</td><td class="desc">${hl(r.x.description||'',q)}</td></tr>`).join('')}</tbody></table>`;
};
$('#cl-search') && ($('#cl-search').oninput=e=>renderList(e.target.value));

// ---------- validate (mirror of pmskit.validate) ----------
const ASME_CLASSES=new Set([150,300,400,600,900,1500,2500]), CI_CLASSES=new Set([125,250]);
const FACINGS=new Set(['RF','FF','RTJ','FFS','RJ','MFF','LMF','SMF']);
function classNum(t){const m=/\bCL\.?\s*(\d{2,4})\b/i.exec(t||'');return m?+m[1]:null;}
function facingOf(t){const m=/\b(RTJ|FFS|RJ|RF|FF|MFF|LMF|SMF)\b/i.exec(t||'');return m?m[1].toUpperCase():null;}
function toFloats(a){const o=[];for(const v of a){const f=parseFloat(v);if(isNaN(f))return[];o.push(f);}return o;}
function validate(){
  const F=[];const add=(cls,sev,code,msg,ctx)=>F.push({cls,sev,code,msg,ctx});
  CLASSES().forEach(c=>{
    const fl=c.flange_rating_face,num=classNum(fl),face=facingOf(fl);
    if(fl&&num!=null&&!ASME_CLASSES.has(num)&&!CI_CLASSES.has(num))add(c.class,'warning','FLANGE_CLASS_UNKNOWN',`Flange class CL${num} not a standard ASME B16.5/B16.1 class`,fl);
    if(fl&&!face&&/CL/i.test(fl))add(c.class,'info','FACING_MISSING','No standard facing (RF/FF/RTJ...) in flange rating',fl);
    else if(face&&!FACINGS.has(face))add(c.class,'warning','FACING_UNKNOWN',`Unrecognised facing '${face}'`,fl);
    if(num&&face==='RTJ'&&num<600)add(c.class,'warning','RTJ_LOW_CLASS',`RTJ unusual below Class 600 (CL${num})`,fl);
    if(num&&face==='FF'&&num>=300)add(c.class,'warning','FF_HIGH_CLASS',`Flat-face unusual at Class ${num}+`,fl);
    if(!c.corrosion_allowance)add(c.class,'info','CA_MISSING','Corrosion allowance not captured');
    const t=c.temp_C,p=c.press_barg;
    if(t&&p){ if(t.length!==p.length)add(c.class,'error','PT_LENGTH_MISMATCH',`Temp(${t.length})≠Press(${p.length})`);
      else{const pv=toFloats(p);if(pv.length&&pv.some((v,i)=>i&&v-pv[i-1]>1e-9))add(c.class,'warning','PT_NOT_MONOTONIC','Pressure rises with temperature (check data)');}}
    if(!c.component_count)add(c.class,'warning','NO_COMPONENTS','No parsed component rows');
  });
  return F;
}
function renderValidate(){
  const F=validate();const s={error:0,warning:0,info:0};F.forEach(f=>s[f.sev]++);
  $('#validate').innerHTML=`
   <div class="cards">
     <div class="kv"><div class="k">Errors</div><div class="v sev-error">${s.error}</div></div>
     <div class="kv"><div class="k">Warnings</div><div class="v sev-warning">${s.warning}</div></div>
     <div class="kv"><div class="k">Info</div><div class="v">${s.info}</div></div>
   </div>
   <p class="muted">Rule-based consistency checks only (standard flange classes, facings, P-T monotonicity). No copyrighted ASME/API tables are used or reproduced.</p>
   <table><thead><tr><th>Severity</th><th>Class</th><th>Code</th><th>Message</th></tr></thead>
   <tbody>${F.map(f=>`<tr><td class="sev-${f.sev}">${f.sev.toUpperCase()}</td><td>${esc(f.cls)}</td><td>${esc(f.code)}</td><td>${esc(f.msg)}</td></tr>`).join('')||'<tr><td colspan="4" class="muted">No findings.</td></tr>'}</tbody></table>`;
}

// ---------- schema / json ----------
async function renderSchema(){
  let schema='(schema not found — see schema/pms.schema.json in the repo)';
  try{const r=await fetch('../schema/pms.schema.json');if(r.ok)schema=JSON.stringify(await r.json(),null,2);}catch(e){}
  $('#schema').innerHTML=`<div class="toolbar">
     <button class="sec" onclick="dl('pms.schema.json',document.getElementById('schemaPre').textContent,'application/json')">Download schema</button>
     <button class="sec" onclick="dl((DATA.meta.company||'pms')+'.json',JSON.stringify(DATA,null,1),'application/json')">Download data JSON</button>
   </div>
   <h2 style="margin-top:0">Open PMS Schema</h2><pre id="schemaPre">${esc(schema)}</pre>
   <h2>Current data (raw)</h2><pre>${esc(JSON.stringify(DATA,null,1).slice(0,200000))}</pre>`;
}

// ---------- export ----------
function flatRows(){const H=['class','service','main_material','corrosion_allowance','flange_rating_face','part','symbol','size_from','size_to','description','notes'];
  const rows=[H];CLASSES().forEach(c=>(c.components||[]).forEach(x=>rows.push([c.class,c.service,c.main_material,c.corrosion_allowance,c.flange_rating_face,x.part,x.symbol,x.size_from,x.size_to,x.description,(x.notes||[]).join(' ')])));return rows;}
function toCSV(){const q=v=>'"'+String(v==null?'':v).replace(/"/g,'""')+'"';return '﻿'+flatRows().map(r=>r.map(q).join(',')).join('\r\n');}
function dl(name,txt,type){const b=new Blob([txt],{type});const u=URL.createObjectURL(b);const a=document.createElement('a');a.href=u;a.download=name;a.click();URL.revokeObjectURL(u);}
window.dl=dl; // used by inline buttons
function renderExport(){
  $('#export').innerHTML=`<h2 style="margin-top:0">Export</h2>
   <p class="muted">All exports are generated in your browser from the currently loaded data.</p>
   <div class="toolbar">
     <button id="e-json">Download JSON</button>
     <button id="e-csv" class="sec">Download CSV (Excel)</button>
   </div>
   <div class="drop" id="drop">Drag & drop a <code>pms.json</code> here to load another PMS,
     or use <b>Import JSON</b> at the top-right.</div>`;
  $('#e-json').onclick=()=>dl((DATA.meta.company||'pms')+'_pms.json',JSON.stringify(DATA,null,1),'application/json');
  $('#e-csv').onclick=()=>dl((DATA.meta.company||'pms')+'_pms.csv',toCSV(),'text/csv');
  wireDrop($('#drop'));
}

// ---------- import ----------
function loadFile(file){const r=new FileReader();r.onload=()=>{try{setData(JSON.parse(r.result));}catch(e){alert('Invalid JSON: '+e.message);}};r.readAsText(file);}
$('#file').onchange=e=>{if(e.target.files[0])loadFile(e.target.files[0]);};
function wireDrop(el){if(!el)return;
  el.ondragover=e=>{e.preventDefault();el.classList.add('hover');};
  el.ondragleave=()=>el.classList.remove('hover');
  el.ondrop=e=>{e.preventDefault();el.classList.remove('hover');if(e.dataTransfer.files[0])loadFile(e.dataTransfer.files[0]);};
}

// ---------- Deviation (Reference baseline vs Contractor) ----------
let REF=null, CON=null, DEV=null, devSevFilter='all';
function loadInto(which,file){const r=new FileReader();r.onload=()=>{try{const d=JSON.parse(r.result);
  if(which==='ref')REF=d;else CON=d;renderDeviation();}catch(e){alert('Invalid JSON: '+e.message);}};r.readAsText(file);}
function slot(which,data){
  const name=data?((data.meta&&data.meta.company||'loaded')+' · '+((data.classes||[]).length)+' classes'):'not loaded';
  const isRef=which==='ref';
  return `<div class="kv" style="border-left:3px solid ${isRef?'var(--acc2)':'var(--acc)'}">
     <div class="k">${isRef?'① Reference (baseline)':'② Contractor (detail design)'}</div>
     <div class="v" style="font-size:14px">${esc(name)}</div>
     <div style="margin-top:8px;display:flex;gap:6px">
       <label class="sec" style="padding:5px 9px;border-radius:7px;cursor:pointer;border:1px solid var(--edge);font-size:12px">
         Import…<input type="file" accept=".json,application/json" hidden onchange="_devPick('${which}',this)"></label>
       ${data?`<button class="sec" style="font-size:12px" onclick="_devClear('${which}')">Clear</button>`:''}
     </div></div>`;
}
window._devPick=(w,el)=>{if(el.files[0])loadInto(w,el.files[0]);};
window._devClear=(w)=>{if(w==='ref')REF=null;else CON=null;DEV=null;renderDeviation();};

function renderDeviation(){
  const m=$('#deviation');
  let head=`<h2 style="margin-top:0">Deviation List</h2>
    <div class="sub">Baseline rule: the <b style="color:var(--acc2)">Reference</b> PMS is the standard; the <b style="color:var(--acc)">Contractor</b> PMS is evaluated against it.</div>
    <div class="cards">${slot('ref',REF)}${slot('con',CON)}
      <div class="kv"><div class="k">Action</div>
        <button id="gen" ${REF&&CON?'':'disabled style="opacity:.5;cursor:not-allowed"'} style="margin-top:6px">Generate Deviation</button>
        <div class="muted" style="font-size:11px;margin-top:6px">${REF&&CON?'Ready.':'Load both PMS files.'}</div>
      </div></div>`;
  if(!DEV){ m.innerHTML=head+`<div class="drop">Import a <b>Reference</b> and a <b>Contractor</b> <code>pms.json</code> above, then Generate.
     Tip: generate each with <code>pmskit parse … -o pms.json</code>.</div>`;
     const g=$('#gen'); if(g)g.onclick=()=>{DEV=window.PMSCompare.compare(REF,CON,false);renderDeviation();};
     return; }
  const s=DEV.summary;
  const rows=DEV.rows.filter(r=>devSevFilter==='all'||r.severity===devSevFilter);
  head+=`<div class="cards">
     <div class="kv"><div class="k">Total</div><div class="v">${s.total}</div></div>
     <div class="kv"><div class="k">Major</div><div class="v sev-error">${s.major}</div></div>
     <div class="kv"><div class="k">Minor</div><div class="v sev-warning">${s.minor}</div></div>
     <div class="kv"><div class="k">Added / Removed / Changed</div><div class="v" style="font-size:15px">${s.added} / ${s.removed} / ${s.changed}</div></div>
   </div>
   <div class="toolbar">
     <select id="devsev">${['all','major','minor','info'].map(v=>`<option value="${v}"${v===devSevFilter?' selected':''}>${v}</option>`).join('')}</select>
     <button id="dev-csv" class="sec">Export CSV (Excel)</button>
     <span class="count">${rows.length} rows</span>
   </div>
   <table><thead><tr>
     <th>Item</th><th>Class</th><th>Component</th><th>Size</th><th>Reference (baseline)</th>
     <th>Contractor</th><th>Deviation</th><th>Severity</th><th>Std Ref</th><th>Consultant Remark</th>
   </tr></thead><tbody>${rows.map(r=>`<tr>
     <td>${r.item}</td><td>${esc(r.class)}</td><td>${esc(r.component)}</td><td>${esc(r.size)}</td>
     <td class="desc">${esc(r.reference)}</td><td class="desc">${esc(r.contractor)}</td>
     <td>${esc(r.deviation)}</td><td class="sev-${r.severity}">${r.severity.toUpperCase()}</td>
     <td class="muted">${esc(r.std_ref)}</td><td>${esc(r.remark)}</td></tr>`).join('')}</tbody></table>`;
  m.innerHTML=head;
  $('#gen').onclick=()=>{DEV=window.PMSCompare.compare(REF,CON,false);renderDeviation();};
  $('#devsev').onchange=e=>{devSevFilter=e.target.value;renderDeviation();};
  $('#dev-csv').onclick=()=>{
    const H=['Item','Class','Component','Size','Reference','Contractor','Deviation','Severity','Std Ref','Consultant Remark'];
    const K=['item','class','component','size','reference','contractor','deviation','severity','std_ref','remark'];
    const q=v=>'"'+String(v==null?'':v).replace(/"/g,'""')+'"';
    const lines=[H.join(',')].concat(DEV.rows.map(r=>K.map(k=>q(r[k])).join(',')));
    dl('deviation_list.csv','﻿'+lines.join('\r\n'),'text/csv');
  };
}

// ---------- Thickness (ASME B31.3) ----------
let SCHED=null, MATDB=null, THK=null, thkFilter='all';
async function loadDB(){
  if(SCHED&&MATDB) return;
  try{const a=await fetch('data/schedules.json');SCHED=a.ok?await a.json():{pipe:{},aliases:{}};}catch(e){SCHED={pipe:{},aliases:{}};}
  try{const b=await fetch('data/materials.sample.json');MATDB=b.ok?await b.json():{meta:{},materials:[]};}catch(e){MATDB={meta:{},materials:[]};}
}
async function renderThickness(){
  await loadDB();
  const m=$('#thickness');
  const warn=(MATDB.meta&&MATDB.meta.SYNTHETIC)?`<div class="notebox">⚠️ Using <b>SYNTHETIC</b> demo allowable-stress values (not real ASME data). For real results, load your own datapack via <b>Data → Load my data</b>.</div>`:'';
  m.innerHTML=`<h2 style="margin-top:0">ASME B31.3 — Wall Thickness</h2>
   <div class="sub">Pressure-design thickness (para. 304.1.2). The equation and Y-coefficient are the code method; allowable stress S is your input.</div>
   ${warn}
   <div class="cards"><div class="kv"><div class="k">Single calculation</div>
     <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px">
       <label>P (barg)<input id="t-P" type="text" value="20"></label>
       <label>OD D (mm)<input id="t-D" type="text" value="219.1"></label>
       <label>S (MPa)<input id="t-S" type="text" value="120"></label>
       <label>c allow. (mm)<input id="t-c" type="text" value="3"></label>
       <label>E<input id="t-E" type="text" value="1"></label>
       <label>W<input id="t-W" type="text" value="1"></label>
       <label>Temp (°C)<input id="t-T" type="text" value="38"></label>
       <label>Family<select id="t-fam"><option>ferritic</option><option>austenitic</option></select></label>
     </div>
     <button id="t-calc" style="margin-top:8px">Calculate</button>
     <div id="t-res" class="muted" style="margin-top:8px;font-size:13px"></div>
   </div>
   <div class="kv"><div class="k">Check a whole PMS?</div><div class="muted" style="font-size:12px;margin-top:6px">
     Use the <b>Compliance</b> tab to run this check on every PIPE row of the loaded PMS and export a report.</div></div></div>`;
  $('#t-calc').onclick=()=>{
    const num=id=>parseFloat($(id).value)||0;
    const Y=window.PMSThickness.yCoefficient($('#t-fam').value,num('#t-T'));
    const r=window.PMSThickness.requiredThickness(num('#t-P'),num('#t-D'),num('#t-S'),{E:num('#t-E'),W:num('#t-W'),Y:Y,c_mm:num('#t-c')});
    $('#t-res').innerHTML=`Y=${Y} · pressure design t=<b>${r.t} mm</b> · t+c=<b>${r.tm} mm</b> · nominal to order T=<b>${r.T} mm</b>`;
  };
}

// ---------- Compliance (ASME B31.3 schedule adequacy over the loaded PMS) ----------
async function renderCompliance(){
  await loadDB();
  const m=$('#compliance');
  const warn=(MATDB.meta&&MATDB.meta.SYNTHETIC)?`<div class="notebox">⚠️ Using <b>SYNTHETIC</b> demo allowable-stress values — results are illustrative. Load your real datapack via <b>Data → Load my data</b> for engineering use.</div>`:'';
  let head=`<h2 style="margin-top:0">Compliance — ASME B31.3 schedule adequacy</h2>
   <div class="sub">For each PIPE row of <b>${esc(DATA.meta.company||'—')}</b> (${CLASSES().length} classes), the required B31.3 wall at the class governing P-T is compared with the selected schedule.</div>
   ${warn}
   <div class="toolbar"><button id="c-run">Run B31.3 check</button>
     <span class="muted" style="font-size:12px">for a formatted Excel report use the CLI: <code>pmskit check pms.json --xlsx report.xlsx</code></span></div>`;
  if(!THK){ m.innerHTML=head+`<div class="drop">Press <b>Run B31.3 check</b> to evaluate the loaded PMS.</div>`;
    $('#c-run').onclick=()=>{THK=window.PMSThickness.checkPMS(DATA,SCHED,MATDB,{});renderCompliance();}; return; }
  const s=THK.summary;
  const rows=THK.rows.filter(r=>thkFilter==='all'||(thkFilter==='under'&&r.status==='UNDER-THICKNESS')||(thkFilter==='ok'&&r.status==='OK')||(thkFilter==='na'&&(r.status==='not-evaluated'||r.status==='no-schedule')));
  head+=`<div class="cards">
     <div class="kv"><div class="k">OK</div><div class="v" style="color:var(--acc2)">${s.ok}</div></div>
     <div class="kv"><div class="k">Under-thickness</div><div class="v sev-error">${s.under}</div></div>
     <div class="kv"><div class="k">Not evaluated</div><div class="v sev-warning">${s.not_evaluated}</div></div>
     <div class="kv"><div class="k">Total PIPE checks</div><div class="v">${s.total}</div></div>
   </div>
   <div class="toolbar">
     <select id="csev"><option value="all">all</option><option value="under">under-thickness</option><option value="ok">ok</option><option value="na">not-evaluated</option></select>
     <button id="c-csv" class="sec">Export CSV</button><span class="count">${rows.length} rows</span>
   </div>
   <table><thead><tr><th>Class</th><th>Size</th><th>Sch</th><th>Material</th><th>OD</th><th>Actual wall</th><th>Required</th><th>Margin</th><th>Status</th><th>Remark</th></tr></thead>
   <tbody>${rows.map(r=>`<tr>
     <td>${esc(r.class)}</td><td>${esc(r.size)}</td><td>${esc(r.schedule||'-')}</td>
     <td>${esc((r.material||'')+' '+(r.grade||''))}</td><td>${r.OD_mm??''}</td><td>${r.actual_wall_mm??''}</td>
     <td>${r.required_mm??''}</td><td>${r.margin_mm??''}</td>
     <td class="${r.status==='UNDER-THICKNESS'?'sev-error':(r.status==='OK'?'':'sev-warning')}">${r.status}</td>
     <td class="muted">${esc(r.remark||'')}</td></tr>`).join('')}</tbody></table>`;
  m.innerHTML=head;
  $('#c-run').onclick=()=>{THK=window.PMSThickness.checkPMS(DATA,SCHED,MATDB,{});renderCompliance();};
  $('#csev').onchange=e=>{thkFilter=e.target.value;renderCompliance();};
  $('#c-csv').onclick=()=>{
    const H=['Class','Size','Schedule','Material','Grade','OD_mm','Actual_wall_mm','Required_mm','Margin_mm','Status','Remark'];
    const K=['class','size','schedule','material','grade','OD_mm','actual_wall_mm','required_mm','margin_mm','status','remark'];
    const q=v=>'"'+String(v==null?'':v).replace(/"/g,'""')+'"';
    const lines=[H.join(',')].concat(THK.rows.map(r=>K.map(k=>q(r[k])).join(',')));
    dl('b31.3_compliance.csv','﻿'+lines.join('\r\n'),'text/csv');
  };
}

// ---------- Spec Builder (ASME B31.3) ----------
let SPEC=null;
async function renderSpecBuilder(){
  await loadDB();
  const m=$('#specbuilder');
  const warn=(MATDB.meta&&MATDB.meta.SYNTHETIC)?`<div class="notebox">⚠️ Using <b>SYNTHETIC</b> demo allowable-stress values. Proposed schedules are illustrative — load a real datapack locally for engineering use.</div>`:'';
  const mats=(MATDB.materials||[]).map(x=>`${x.spec}${x.grade?' '+x.grade:''}`);
  let out=`<h2 style="margin-top:0">Spec Builder</h2>
    <div class="sub">Propose a pipe class: for each size, the minimum standard schedule that satisfies ASME B31.3 at the class P-T.</div>
    ${warn}
    <div class="cards">
      <div class="kv"><div class="k">Inputs</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px">
          <label>Class code<input id="sb-name" type="text" value="A1B1"></label>
          <label>Service<input id="sb-svc" type="text" value="HYDROCARBON"></label>
          <label>Material<select id="sb-mat">${mats.map(x=>`<option>${esc(x)}</option>`).join('')}</select></label>
          <label>Flange rating & face<input id="sb-flg" type="text" value="CL.150 RF"></label>
          <label>Corrosion allow.<input id="sb-ca" type="text" value="3.0 MM"></label>
          <label>End<input id="sb-end" type="text" value="BE"></label>
          <label>Size from<input id="sb-sf" type="text" value="1/2"></label>
          <label>Size to<input id="sb-st" type="text" value="24"></label>
          <label>Temps °C (comma)<input id="sb-temp" type="text" value="38,200,400"></label>
          <label>Press barg (comma)<input id="sb-press" type="text" value="19.6,17.9,10.2"></label>
        </div>
        <button id="sb-gen" style="margin-top:8px">Generate spec</button>
      </div>
    </div>`;
  if(SPEC){
    const c=SPEC.classes[0];
    out+=`<div class="toolbar">
       <button id="sb-json" class="sec">Download class JSON</button>
       <button id="sb-add" class="sec">Add to loaded PMS</button>
       <span class="count">${c.component_count} PIPE rows</span></div>
      <h2>${esc(c.class)} — ${esc(c.main_material)} · ${esc(c.flange_rating_face)}</h2>
      ${c.particular_notes?`<div class="notebox">${esc(c.particular_notes)}</div>`:''}
      <table><thead><tr><th>From</th><th>To</th><th>Proposed description</th></tr></thead>
      <tbody>${c.components.map(x=>`<tr><td>${esc(x.size_from)}</td><td>${esc(x.size_to)}</td><td class="desc">${esc(x.description)}</td></tr>`).join('')}</tbody></table>
      <h2>Sizing detail</h2>
      <table><thead><tr><th>NPS</th><th>OD</th><th>Required (mm)</th><th>Chosen schedule</th><th>Wall (mm)</th><th>Status</th></tr></thead>
      <tbody>${SPEC.sizing_detail.map(d=>`<tr><td>${esc(d.nps)}</td><td>${d.OD_mm??''}</td><td>${d.required_mm?d.required_mm.toFixed(3):''}</td>
        <td>${esc(d.schedule||'-')}</td><td>${d.wall_mm??''}</td>
        <td class="${d.status==='OK'?'':'sev-error'}">${esc(d.status)}</td></tr>`).join('')}</tbody></table>`;
  }
  m.innerHTML=out;
  $('#sb-gen').onclick=()=>{
    const matSel=$('#sb-mat').value.split(' ');
    SPEC=window.PMSSpec.build({sch:SCHED,mat:MATDB,name:$('#sb-name').value,
      material_spec:matSel.slice(0,-1).join(' ')||matSel[0], grade:matSel.length>1?matSel[matSel.length-1]:null,
      service:$('#sb-svc').value, flange:$('#sb-flg').value, ca_txt:$('#sb-ca').value,
      temp:$('#sb-temp').value.split(',').map(x=>x.trim()), press:$('#sb-press').value.split(',').map(x=>x.trim()),
      size_from:$('#sb-sf').value, size_to:$('#sb-st').value, end:$('#sb-end').value, E:1,W:1,mt:0.125});
    renderSpecBuilder();
  };
  if($('#sb-json'))$('#sb-json').onclick=()=>dl(SPEC.classes[0].class+'_spec.json',JSON.stringify(SPEC,null,1),'application/json');
  if($('#sb-add'))$('#sb-add').onclick=()=>{
    const nc={...SPEC.classes[0]}; DATA.classes=(DATA.classes||[]).filter(c=>c.class!==nc.class).concat([nc]);
    setData(DATA); alert('Class '+nc.class+' added to the loaded PMS (in memory). Use Export to save.');
  };
}

// ---------- Get-started data modal ----------
let pendPMS=null, pendMAT=null;
function hasData(){return (DATA.classes||[]).length>0;}
function mShowStep(n){$('#modal-step1').style.display=n===1?'':'none';$('#modal-step2').style.display=n===2?'':'none';}
function openModal(step1){ $('#modal').classList.add('open'); mShowStep(step1?1:2);
  $('#modal-close').style.display=hasData()?'':'none'; }
function closeModal(){ if(hasData()) $('#modal').classList.remove('open'); }
async function useSample(){
  await loadDB();
  try{const r=await fetch('data/pms.json',{cache:'no-store'});if(r.ok)setData(await r.json());}catch(e){}
  try{const b=await fetch('data/materials.sample.json');if(b.ok)MATDB=await b.json();}catch(e){}
  $('#modal').classList.remove('open');
}
function readJSON(file,cb){const r=new FileReader();r.onload=()=>{try{cb(JSON.parse(r.result));}catch(e){alert('Invalid JSON: '+e.message);}};r.readAsText(file);}
function refreshRun(){const b=$('#modal-run'); if(!b)return; const on=!!pendPMS;
  b.disabled=!on; b.style.opacity=on?'1':'.5'; b.style.cursor=on?'pointer':'not-allowed';}

$('#data-btn').onclick=()=>openModal(true);
$('#modal-close').onclick=closeModal;
$('#opt-sample').onclick=useSample;
$('#opt-mine').onclick=()=>{mShowStep(2);};
$('#modal-back').onclick=()=>{mShowStep(1);};
$('#in-pms').onchange=e=>{const f=e.target.files[0];if(f)readJSON(f,d=>{pendPMS=d;
  $('#st-pms').innerHTML=`<span class="ok">✓ ${esc((d.meta&&d.meta.company)||'loaded')} · ${(d.classes||[]).length} classes</span>`;refreshRun();});};
$('#in-mat').onchange=e=>{const f=e.target.files[0];if(f)readJSON(f,d=>{pendMAT=d;
  const n=(d.materials||[]).length; $('#st-mat').innerHTML=`<span class="ok">✓ ${n} materials${(d.meta&&d.meta.SYNTHETIC)?' (synthetic)':''}</span>`;});};
$('#modal-run').onclick=async()=>{ if(!pendPMS)return; await loadDB();
  if(pendMAT)MATDB=pendMAT; setData(pendPMS); $('#modal').classList.remove('open'); };

boot();
