"use strict";
// JS port of pmskit.normalize + pmskit.compare (kept faithful to the Python).
// Baseline = Reference PMS; Contractor is evaluated against it.

const _FRAC = {"½":0.5,"¼":0.25,"¾":0.75,"⅛":0.125};
function nps(size){
  if(size==null) return null;
  let s=String(size).trim(); if(!s) return null;
  for(const k in _FRAC) s=s.split(k).join(" "+_FRAC[k]);
  s=s.replace(/-/g," "); let total=0, any=false;
  for(const tok of s.split(/\s+/)){ if(!tok) continue;
    if(tok.includes("/")){const[a,b]=tok.split("/");const v=parseFloat(a)/parseFloat(b);if(!isNaN(v)){total+=v;any=true;}}
    else{const v=parseFloat(tok);if(!isNaN(v)){total+=v;any=true;}}}
  return any?total:null;
}
function overlap(alo,ahi,blo,bhi){ if(alo==null||blo==null) return false;
  ahi=ahi==null?alo:ahi; bhi=bhi==null?blo:bhi; return Math.max(alo,blo)<=Math.min(ahi,bhi);}

// --- normalize ---
const RX={
  material:/\b(?:ASTM\s*A?\d{2,4}[A-Z]?|API\s*5[A-Z]{1,3}\d*|API\s*\d{3})\b/i,
  grade:/\b(?:GR\.?\s*)?(WPB(?:-W)?|WPL6|WP\d+|TP\d+[LH]?N?|GR\.?\s*B|B7|2H|F\d+|CF8M|CF8|WCB|WCC|LCB|LCC)\b/i,
  end:/\b(BW|SW|NPT|MNPT|FNPT|PE|BE|PBE|PLE|TSE|BLE|PSE|FLGD|FLANGED|RTJ|RF|FF|THRD|SCRD)\b/i,
  radius:/\b(LR|SR|LONG RADIUS|SHORT RADIUS)\b/i,
  manuf:/\b(SMLS|SEAMLESS|WELDED|DSAW|SAW|ERW|EFW|FORGED|FORGING|CAST(?:ING)?)\b/i,
  sch:/\bSCH\.?\s*[0-9]{1,3}S?\b|\b(?:STD|XXS|XS)\b|\bCL\.?\s*\d{2,4}\b|\b\d+(?:\.\d+)?\s*MM(?:-?T)?\b|\bAS\s*PIPE\b/i,
  std:/\b(?:ASME|API|MSS(?:\s*SP)?|BS|EN|DIN)\s*[A-Z]*\s*[-\s]?\s*\d[\w.\-]*/ig
};
function up(x){return x==null?null:String(x).replace(/\s+/g,' ').trim().toUpperCase();}
function normalize(desc){
  const t=" "+(desc||"")+" ";
  let material=up((t.match(RX.material)||[])[0]);
  let grade=up((t.match(RX.grade)||[])[1]); if(grade)grade=grade.replace(/^GR\.?\s*/,'');
  let end=up((t.match(RX.end)||[])[1]);
  let radius=up((t.match(RX.radius)||[])[1]); radius={"LONG RADIUS":"LR","SHORT RADIUS":"SR"}[radius]||radius;
  let manuf=up((t.match(RX.manuf)||[])[1]); manuf={"SEAMLESS":"SMLS","FORGING":"FORGED","CASTING":"CAST"}[manuf]||manuf;
  let sch=up((t.match(RX.sch)||[])[0]); if(sch)sch=sch.replace(/\s+/g,'').replace('SCH.','SCH');
  let stds=[...t.matchAll(RX.std)].map(m=>m[0].replace(/\s+/g,' ').toUpperCase().trim())
     .filter(x=>!/^(?:ASTM|API)\s*A?\d/i.test(x)).filter(x=>/B\d|SP|API ?6|BS ?\d|EN ?\d|DIN/.test(x));
  stds=[...new Set(stds)].sort();
  return {material,grade,end,radius,manuf,rating_sch:sch,standards:stds};
}
const COMPARE_FIELDS=["material","grade","rating_sch","manuf","end","radius","standards"];
function canonTok(t){ if(t==null)return null; t=String(t).toUpperCase().replace(/[\s.]+/g,'');
  t=t.replace(/(B\d{2}\d+)M$/,'$1').replace(/(B\d+)M\b/,'$1'); return t;}
function cmpVal(v){ return Array.isArray(v)?JSON.stringify(v.map(canonTok).sort()):canonTok(v);}

// --- schedule rank ---
const SCH_RANK={"5":5,"5S":5,"10":10,"10S":10,"20":20,"30":30,"STD":40,"40":40,"40S":40,"60":60,
  "80":80,"80S":80,"XS":80,"100":100,"120":120,"140":140,"160":160,"XXS":200};
function schRank(v){ if(!v)return null; v=v.toUpperCase().replace("SCH","").replace(/\./g,"").trim();
  if(v in SCH_RANK)return SCH_RANK[v]; let m=/CL\s*(\d+)/.exec(v); if(m)return +m[1];
  m=/(\d+(?:\.\d+)?)\s*MM/.exec(v); if(m)return +m[1]*1000; return null;}
function ratingDir(ref,con){const r=schRank(ref),c=schRank(con); if(r==null||c==null)return null; return (c>r)-(c<r);}

// --- pairing ---
function pairComponents(refC,conC){
  const used=new Set(), pairs=[];
  refC.forEach(rc=>{
    const rp=(rc.part||"").toUpperCase(), rlo=nps(rc.size_from), rhi=nps(rc.size_to);
    let best=null;
    for(let i=0;i<conC.length;i++){ if(used.has(i))continue; const cc=conC[i];
      if((cc.part||"").toUpperCase()!==rp)continue;
      const clo=nps(cc.size_from),chi=nps(cc.size_to);
      if(overlap(rlo,rhi,clo,chi)||(rlo==null&&clo==null)){best=i;break;}}
    if(best!=null){used.add(best);pairs.push([rc,conC[best]]);} else pairs.push([rc,null]);
  });
  conC.forEach((cc,i)=>{ if(!used.has(i))pairs.push([null,cc]); });
  return pairs;
}
function sizeLabel(row){ if(!row)return""; const a=row.size_from,b=row.size_to; return (b&&b!==a)?`${a}–${b}`:(a||"");}

function compareRow(ref,con){
  if(ref&&!con) return ["Removed","major","Item present in reference, missing in contractor"];
  if(con&&!ref) return ["Added","minor","Item added by contractor (not in reference)"];
  const nr=normalize(ref.description), nc=normalize(con.description);
  const changed=COMPARE_FIELDS.filter(f=>cmpVal(nr[f])!==cmpVal(nc[f]));
  if(!changed.length) return ["Equal","info","Equivalent after normalization"];
  let sev="minor"; const rem=[];
  if(changed.some(f=>["material","grade","manuf"].includes(f))) sev="major";
  changed.forEach(f=>{ const a=nr[f],b=nc[f];
    if(f==="rating_sch"){const d=ratingDir(a,b);
      if(d!=null&&d<0){sev="major";rem.push(`Schedule/rating REDUCED ${a}→${b}`);}
      else if(d!=null&&d>0)rem.push(`Schedule/rating increased ${a}→${b}`);
      else rem.push(`Schedule/rating changed ${a}→${b} (review)`);}
    else if(f==="standards")rem.push(`Standard ${JSON.stringify(a)}→${JSON.stringify(b)}`);
    else rem.push(`${f} ${a}→${b}`);});
  return ["Changed",sev,rem.join("; ")];
}
function stdRef(ref,con){const s=ref||con; return s?normalize(s.description).standards.join(", "):"";}
function canon(s){return (s||"").toUpperCase().replace(/[\s.]+/g,'');}
function pt(c){const t=c.temp_C||[],p=c.press_barg||[];return t.map((x,i)=>`${x}C:${p[i]}`).join("; ");}

function compare(reference,contractor,includeEqual){
  const refBy={},conBy={};
  (reference.classes||[]).forEach(c=>refBy[canon(c.class)]=c);
  (contractor.classes||[]).forEach(c=>conBy[canon(c.class)]=c);
  const codes=[...new Set([...Object.keys(refBy),...Object.keys(conBy)])];
  const rows=[]; let seq=0;
  const push=(cls,comp,size,rv,cv,dev,sev,sr,rem)=>rows.push(
    {item:++seq,class:cls,component:comp,size,reference:rv,contractor:cv,deviation:dev,severity:sev,std_ref:sr,remark:rem});
  codes.forEach(code=>{
    const rc=refBy[code], cc=conBy[code], name=(rc||cc).class;
    if(rc&&!cc){push(name,"WHOLE CLASS","","present","—","Removed","major","","Entire class missing in contractor");return;}
    if(cc&&!rc){push(name,"WHOLE CLASS","","—","present","Added","minor","","Class added by contractor (not in reference)");return;}
    [["main_material","Main material"],["flange_rating_face","Flange rating & face"],["corrosion_allowance","Corrosion allowance"]]
      .forEach(([k,lbl])=>{ if(canon(rc[k])!==canon(cc[k])) push(name,`CLASS HEADER — ${lbl}`,"",rc[k]||"",cc[k]||"","Changed","major","",`${lbl} changed`);});
    if(pt(rc)!==pt(cc)) push(name,"CLASS HEADER — P-T rating","",pt(rc),pt(cc),"Changed","major","","Pressure-temperature rating differs");
    pairComponents(rc.components||[],cc.components||[]).forEach(([r,c])=>{
      const[dev,sev,rem]=compareRow(r,c); if(dev==="Equal"&&!includeEqual)return;
      push(name,(r||c).part||"",sizeLabel(r)||sizeLabel(c),
        r?r.description:"—", c?c.description:"—", dev,sev,stdRef(r,c),rem);
    });
  });
  const summary={total:rows.length,
    major:rows.filter(x=>x.severity==="major").length,
    minor:rows.filter(x=>x.severity==="minor").length,
    info:rows.filter(x=>x.severity==="info").length,
    added:rows.filter(x=>x.deviation==="Added").length,
    removed:rows.filter(x=>x.deviation==="Removed").length,
    changed:rows.filter(x=>x.deviation==="Changed").length};
  return {meta:{reference:(reference.meta||{}).company||"Reference",
    contractor:(contractor.meta||{}).company||"Contractor",baseline:"reference"},summary,rows};
}
window.PMSCompare={compare,normalize,nps};
