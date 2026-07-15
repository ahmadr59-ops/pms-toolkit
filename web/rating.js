"use strict";
// JS port of pmskit.rating (faithful to the Python).
// ASME B16.5 / B16.34 P-T rating *method* only — contains NO copyrighted rating
// tables; values come from a loaded flange datapack (flange-master v1).
//
// Rating semantics: curve = ascending [temp_C, pressure] points; linear
// interpolation between points; constant below the first temperature; not
// rated (null) above the last.

const STANDARD_CLASSES = [150, 300, 400, 600, 900, 1500, 2500];

// Unifies grade/class markers so "A350 Gr. LF2" matches "A350 LF2", and
// "Cl. 1" / "Class 1" / the common "CI. 1" transcription typo become "CL1".
function normSpec(s){
  s = (s||"").toUpperCase();
  s = s.replace(/\b(GRADE|GR)\b\.?/g, " ");
  s = s.replace(/\b(CLASS|CL|CI)\b\.?\s*(?=\d)/g, "CL");
  return s.replace(/[^A-Z0-9]/g, "");
}

function findGroup(pack, text){
  if(!text) return null;
  const groups = (pack && pack.material_groups) || [];
  const t = String(text).trim();
  for(const g of groups) if(g.group === t) return g;      // exact group code
  const tn = normSpec(t);
  let best = null, bestLen = 0;
  for(const g of groups){
    for(const spec of (g.specs||[])){
      const sn = normSpec(spec);
      if(sn && tn.includes(sn) && sn.length > bestLen){ best = g; bestLen = sn.length; }
    }
  }
  return best;
}

function ratedPressure(group, cls, tempC){
  const curve = ((group && group.ratings) || {})[String(cls)];
  if(!curve || !curve.length) return null;
  const pts = curve.map(([a,b])=>[+a,+b]).sort((x,y)=>x[0]-y[0]);
  if(tempC <= pts[0][0]) return pts[0][1];
  if(tempC > pts[pts.length-1][0]) return null;
  for(let i=0;i<pts.length-1;i++){
    const [t1,p1]=pts[i], [t2,p2]=pts[i+1];
    if(t1<=tempC && tempC<=t2){
      if(t2===t1) return Math.min(p1,p2);
      return p1 + (p2-p1)*(tempC-t1)/(t2-t1);
    }
  }
  return null;
}

function selectClass(group, points, classes){
  if(!points || !points.length) return null;
  const cl = (classes || STANDARD_CLASSES).slice().sort((a,b)=>a-b);
  for(const cls of cl){
    let ok = true;
    for(const [t,p] of points){
      const r = ratedPressure(group, cls, t);
      if(r == null || r < p){ ok = false; break; }
    }
    if(ok) return cls;
  }
  return null;
}

const CLASS_RE = /\bCL\.?\s*(\d{2,4})\b/i;

function ptPoints(c){
  const temps = c.temp_C || [], press = c.press_barg || [], out = [];
  for(let i=0;i<Math.min(temps.length, press.length);i++){
    const t = parseFloat(temps[i]), p = parseFloat(press[i]);
    if(isFinite(t) && isFinite(p)) out.push([t,p]);
  }
  return out;
}

// One adequacy row per pipe class; never a false pass.
function flangeAdequacy(data, pack){
  const synthetic = !!((pack && pack.meta) || {}).SYNTHETIC;
  const rows = [];
  for(const c of (data.classes || [])){
    const flangeTxt = c.flange_rating_face || "";
    const m = CLASS_RE.exec(flangeTxt);
    const clsNum = m ? parseInt(m[1], 10) : null;
    const group = findGroup(pack, c.main_material || "");
    const pts = ptPoints(c);
    const base = { class: c.class, flange: flangeTxt, class_number: clsNum,
                   material_group: group ? group.group : null, synthetic_data: synthetic };
    if(clsNum == null || !group || !pts.length){
      const why = clsNum == null ? "no CL.### in flange text"
        : !group ? "material group not resolved from main_material"
        : "no numeric P-T design points";
      rows.push({...base, status:"not-evaluated", worst:null, margin_pct:null,
                 suggested_class:null, remark:why});
      continue;
    }
    let worst = null, worstMargin = null, evaluated = true;
    for(const [t,p] of pts){
      const r = ratedPressure(group, clsNum, t);
      if(r == null){ evaluated = false; worst = {temp_C:t, press_barg:p, rated_barg:null}; break; }
      const margin = p > 0 ? (r - p) / p * 100 : Infinity;
      if(worstMargin == null || margin < worstMargin){
        worstMargin = margin;
        worst = {temp_C:t, press_barg:p, rated_barg:+r.toFixed(2)};
      }
    }
    if(!evaluated){
      rows.push({...base, status:"not-evaluated", worst, margin_pct:null, suggested_class:null,
                 remark:`class ${clsNum} not rated at ${worst.temp_C}C for group ${group.group}`});
      continue;
    }
    const status = worstMargin >= 0 ? "adequate" : "inadequate";
    const suggested = status === "inadequate" ? selectClass(group, pts) : null;
    rows.push({...base, status, worst, margin_pct:+worstMargin.toFixed(1),
               suggested_class:suggested,
               remark: status === "adequate" ? "OK"
                 : `rated below design at ${worst.temp_C}C; smallest adequate class: ${suggested ?? "none listed"}`});
  }
  return rows;
}

// Offline bundles (tools/build_offline.py) embed datapacks as
// <script type="application/json" id="datapack-<name>"> blocks.
// Online, the dashboard fetches web/data/<name>.json instead.
function loadEmbeddedDatapack(name){
  const el = document.getElementById("datapack-" + name);
  if(!el) return null;
  try { return JSON.parse(el.textContent); } catch(e){ return null; }
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { STANDARD_CLASSES, findGroup, ratedPressure, selectClass,
                     flangeAdequacy, loadEmbeddedDatapack };
}
