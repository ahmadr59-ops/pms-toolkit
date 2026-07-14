"use strict";
// JS port of pmskit.thickness + pmskit.compliance (faithful to the Python).
// Contains NO copyrighted stress tables; stress comes from a loaded material datapack.

function barToMpa(b){return b*0.1;}
function yCoefficient(family,T){
  const f=(family||'ferritic').toLowerCase();
  if(f.includes('austen')||f.includes('stainless')||f==='ss'){
    if(T<=566)return 0.4; if(T<=593)return 0.5; return 0.7;}
  if(T<=482)return 0.4; if(T<=510)return 0.5; return 0.7;
}
function requiredThickness(Pbar,Dmm,Smpa,o){o=o||{};
  const E=o.E??1,W=o.W??1,Y=o.Y??0.4,c=o.c_mm??0,mt=o.mill_tol??0.125;
  const P=barToMpa(Pbar), denom=2*(Smpa*E*W+P*Y);
  const t=denom>0?P*Dmm/denom:Infinity, tm=t+c, T=mt<1?tm/(1-mt):Infinity;
  return {pressure_MPa:+P.toFixed(4),t:+t.toFixed(3),tm:+tm.toFixed(3),T:+T.toFixed(3)};
}
function governingCase(pts,Dmm,sAt,o){o=o||{};let worst=null;
  for(const [T,P] of pts){const S=sAt(T); if(S==null||S<=0)continue;
    const Y=yCoefficient(o.family,T);
    const r=requiredThickness(P,Dmm,S,{E:o.E,W:o.W,Y:Y,c_mm:o.c_mm,mill_tol:o.mill_tol});
    r.temp_C=T; r.press_barg=P; r.S_MPa=+S.toFixed(2); r.Y=Y;
    if(!worst||r.tm>worst.tm)worst=r;}
  return worst;
}
// --- DB helpers ---
const NPS_ORDER=["1/2","3/4","1","1-1/4","1-1/2","2","2-1/2","3","4","5","6","8","10","12","14","16","18","20","24","26","30","36","42","48"];
function npsVal(s){return window.PMSCompare?window.PMSCompare.nps(s):null;}
function sizesInRange(f,t){const a=npsVal(f);let b=npsVal(t);if(a==null)return [];if(b==null)b=a;
  return NPS_ORDER.filter(x=>{const v=npsVal(x);return v!=null&&v>=a-1e-9&&v<=b+1e-9;});}
function canonSched(tok,aliases){if(!tok)return null;let t=tok.toUpperCase().replace(/\s/g,'').replace('SCH.','SCH');
  if(aliases[t])return aliases[t]; const t2=t.replace('SCH',''); return t2||t;}
function wallThickness(sch,nps,tok){const p=(sch.pipe||{})[nps];if(!p)return null;
  const key=canonSched(tok,sch.aliases||{}); const w=p.wall||{}; if(w[key]!=null)return w[key];
  return w[(tok||'').toUpperCase().trim()]??null;}
function outerDiameter(sch,nps){const p=(sch.pipe||{})[nps];return p?p.od:null;}
function findMaterial(mat,spec,grade){if(!spec)return null;
  const nz=s=>(s||'').toUpperCase().replace(/[\s.]+/g,''); const ns=nz(spec); let best=null;
  for(const m of (mat.materials||[])){if(nz(m.spec)===ns){if(grade&&nz(m.grade)===nz(grade))return m; best=best||m;}}
  return best;}
function allowableStress(m,T){let pts=m&&m.s;if(!pts||!pts.length)return null;
  pts=pts.map(p=>[+p[0],+p[1]]).sort((a,b)=>a[0]-b[0]);
  if(T<=pts[0][0])return pts[0][1]; if(T>=pts[pts.length-1][0])return pts[pts.length-1][1];
  for(let i=0;i<pts.length-1;i++){const[t0,s0]=pts[i],[t1,s1]=pts[i+1];
    if(T>=t0&&T<=t1)return s0+(s1-s0)*(T-t0)/(t1-t0);} return pts[pts.length-1][1];}
function schedOf(row){const m=/SCH\.?\s*\d+S?|\bXXS\b|\bXS\b|\bSTD\b/.exec((row.description||'').toUpperCase());return m?m[0]:null;}
function mm(s){const m=/([0-9.]+)/.exec(s||'');return m?+m[1]:0;}

function checkPMS(data,sch,mat,o){o=o||{};const E=o.E??1,W=o.W??1,mt=o.mill_tol??0.125;
  const rows=[];let seq=0;
  (data.classes||[]).forEach(c=>{
    const temps=c.temp_C||[],press=c.press_barg||[];
    const pts=[];for(let i=0;i<Math.min(temps.length,press.length);i++){const t=+temps[i],p=+press[i];if(!isNaN(t)&&!isNaN(p))pts.push([t,p]);}
    const ca=mm(c.corrosion_allowance);
    (c.components||[]).forEach(x=>{ if((x.part||'').toUpperCase()!=='PIPE')return;
      const n=window.PMSCompare.normalize(x.description); const m=findMaterial(mat,n.material,n.grade); const s=schedOf(x);
      sizesInRange(x.size_from,x.size_to).forEach(nps=>{ seq++;
        const D=outerDiameter(sch,nps), actual=s?wallThickness(sch,nps,s):null;
        const base={item:seq,class:c.class,size:nps,schedule:s,material:n.material,grade:n.grade,OD_mm:D,actual_wall_mm:actual};
        if(!pts.length||!m||D==null){base.status='not-evaluated';base.required_mm=null;base.margin_mm=null;
          base.remark='Not evaluated: '+[!pts.length?'no P-T':'',!m?'material not in datapack':'',D==null?'size not in table':''].filter(Boolean).join(', ');rows.push(base);return;}
        const g=governingCase(pts,D,T=>allowableStress(m,T),{E,W,family:m.family||'ferritic',c_mm:ca,mill_tol:mt});
        if(!g){base.status='not-evaluated';base.required_mm=null;base.margin_mm=null;base.remark='No usable stress';rows.push(base);return;}
        const req=g.tm;
        if(actual==null){base.status='no-schedule';base.required_mm=req;base.margin_mm=null;base.remark='Schedule not in dimension table';}
        else{const eff=actual*(1-mt);const margin=+(eff-req).toFixed(3);base.status=margin>=0?'OK':'UNDER-THICKNESS';
          base.required_mm=req;base.margin_mm=margin;base.governing=g;
          base.remark=`Gov ${g.temp_C}C/${g.press_barg}barg S=${g.S_MPa}MPa; req ${req} vs eff ${eff.toFixed(3)}`;}
        rows.push(base);
      });
    });
  });
  const summary={total:rows.length,under:rows.filter(r=>r.status==='UNDER-THICKNESS').length,
    ok:rows.filter(r=>r.status==='OK').length,
    not_evaluated:rows.filter(r=>['not-evaluated','no-schedule'].includes(r.status)).length,
    synthetic:!!(mat.meta&&mat.meta.SYNTHETIC),source:mat.meta&&mat.meta._source};
  return {summary,rows};
}
window.PMSThickness={requiredThickness,yCoefficient,governingCase,checkPMS,outerDiameter,wallThickness};
