"use strict";
// JS mirror of pmskit/rules.py (rule-master v1). Same operators, same derived
// context, same message templating - byte-identical findings are enforced by
// tools/check_rules_parity.py (Python <-> Node cross-check).
// No eval(): conditions are a tiny structured dialect evaluated recursively.

const RULE_CLASS_RE = /\bCL\.?\s*(\d{2,4})\b/i;
const RULE_FACING_RE = /\b(RTJ|FFS|RJ|RF|FF|MFF|LMF|SMF)\b/i;

function _toFloats(arr){
  const out=[];
  for(const v of (arr||[])){
    const f=parseFloat(v);
    if(!isFinite(f)) return [];
    out.push(f);
  }
  return out;
}

function classContext(c){
  const flange=c.flange_rating_face||"";
  const m=RULE_CLASS_RE.exec(flange), fm=RULE_FACING_RE.exec(flange);
  const t=c.temp_C, p=c.press_barg;
  let ptLenEqual=null;
  if(t&&t.length&&p&&p.length) ptLenEqual=(t.length===p.length);
  let mono=false;
  if(t&&p&&t.length&&p.length&&t.length===p.length){
    const pv=_toFloats(p);
    mono=pv.length>0 && pv.some((v,i)=>i>0 && v-pv[i-1]>1e-9);
  }
  return {...c, derived:{
    flange_class_number: m?parseInt(m[1],10):null,
    facing: fm?fm[1].toUpperCase():null,
    has_cl_token: /CL/i.test(flange),
    pt_len_equal: ptLenEqual,
    pt_len: t?t.length:0,
    press_len: p?p.length:0,
    press_monotonic_violation: mono}};
}

function componentContext(ctx, comp){
  const cm=RULE_CLASS_RE.exec(comp.description||"");
  return {...ctx, comp,
          derived:{...ctx.derived,
                   component_class_number: cm?parseInt(cm[1],10):null}};
}

function _rvar(ctx, path){
  let cur=ctx;
  for(const part of path.split(".")){
    if(cur===null||typeof cur!=="object"||!(part in cur)) return null;
    cur=cur[part];
  }
  return cur===undefined?null:cur;
}

function ruleEval(expr, ctx, facts){
  if(expr===null||typeof expr!=="object"||Array.isArray(expr)) return expr;
  const op=Object.keys(expr)[0], arg=expr[op];
  const ev=x=>ruleEval(x,ctx,facts);
  switch(op){
    case "var": return _rvar(ctx,arg);
    case "truthy": return !!ev(arg);
    case "!": return !ev(arg);
    case "and": return arg.every(a=>!!ev(a));
    case "or": return arg.some(a=>!!ev(a));
    case "==": return ev(arg[0])===ev(arg[1]);
    case "!=": return ev(arg[0])!==ev(arg[1]);
    case "<": case "<=": case ">": case ">=": {
      const a=ev(arg[0]), b=ev(arg[1]);
      if(a===null||b===null) return false;
      return op==="<"?a<b:op==="<="?a<=b:op===">"?a>b:a>=b;
    }
    case "in": case "!in": {
      const a=ev(arg[0]), lst=ev(arg[1])||[];
      const res=lst.includes(a);
      return op==="in"?res:!res;
    }
    case "regex_match": return new RegExp(arg[1],"i").test(ev(arg[0])||"");
    case "facts+": return arg.reduce((o,n)=>o.concat(facts[n]||[]),[]);
    case "facts+var": return (facts[arg[0]]||[]).concat([_rvar(ctx,arg[1])]);
    case "object": {
      const o={};
      for(const k of Object.keys(arg)) o[k]=ev(arg[k]);
      return o;
    }
    default: throw new Error("unknown rule operator: "+op);
  }
}

function ruleRender(tpl, ctx){
  return tpl.replace(/\{([a-zA-Z0-9_.]+)\}/g,(_,p)=>{
    const v=_rvar(ctx,p);
    return v===null?"None":String(v);
  });
}

function runRules(data, pack){
  const facts=pack.facts||{}, findings=[];
  for(const c of (data.classes||[])){
    const ctx=classContext(c);
    for(const rule of (pack.rules||[])){
      if(rule.enabled===false) continue;
      const scopes=(rule.scope||"class")==="class"
        ? [ctx] : (c.components||[]).map(x=>componentContext(ctx,x));
      for(const sctx of scopes){
        if(ruleEval(rule.when,sctx,facts)){
          findings.push({class:c.class??null, severity:rule.severity,
            code:rule.id, message:ruleRender(rule.message,sctx),
            context: rule.context?ruleEval(rule.context,sctx,facts):null});
        }
      }
    }
  }
  return findings;
}

if (typeof module!=="undefined" && module.exports){
  module.exports={runRules, classContext, ruleEval, ruleRender};
}
