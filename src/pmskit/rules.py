# -*- coding: utf-8 -*-
"""Modular JSON rule engine (rule-master v1) - phase 1-3 of the rule-engine
migration. Evaluates declarative condition trees (a small, safe JSONLogic-like
dialect - never eval()) over a per-class context with engine-derived fields.

Shadow status: pmskit.validate remains the default engine. run_conventions()
must produce byte-identical findings; tests/test_rules_shadow.py enforces
parity on fixtures. Flip the default only after the parity gate has been green
in CI (see docs/rules.md).

Supported condition operators:
  {"var": "a.b"}                dotted context lookup (None if missing)
  {"truthy": X}                 bool(X)
  {"!": X}                      not X
  {"and": [..]} {"or": [..]}
  {"==":[a,b]} {"!=":[a,b]} {"<":[a,b]} {"<=":[a,b]} {">":[a,b]} {">=":[a,b]}
  {"in":[a,LIST]} {"!in":[a,LIST]}
  {"regex_match":[text, pattern]}   re.search, case-insensitive
  {"facts+": [name, ...]}       union of fact lists (from the pack's "facts")
  {"facts+var": [name, path]}   fact list plus one context value
  {"object": {...}}             literal object with resolved values (contexts)
"""
from __future__ import annotations
import json
import os
import re
from typing import Any, Dict, List, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_CLASS_RE = re.compile(r"\bCL\.?\s*(\d{2,4})\b", re.I)
_FACING_RE = re.compile(r"\b(RTJ|FFS|RJ|RF|FF|MFF|LMF|SMF)\b", re.I)


def load_rulepack(path: Optional[str] = None) -> Dict[str, Any]:
    path = path or os.path.join(_ROOT, "rules", "conventions.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---- context building (parsing/derivation lives in code, policy in rules) --
def _to_floats(arr):
    out = []
    for v in arr:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            return []
    return out


def class_context(c: Dict[str, Any]) -> Dict[str, Any]:
    flange = c.get("flange_rating_face") or ""
    m = _CLASS_RE.search(flange)
    fm = _FACING_RE.search(flange)
    t, p = c.get("temp_C"), c.get("press_barg")
    pt_len_equal = None
    if t and p:
        pt_len_equal = len(t) == len(p)
    mono = False
    if t and p and len(t) == len(p):
        pv = _to_floats(p)
        mono = bool(pv) and any(b - a > 1e-9 for a, b in zip(pv, pv[1:]))
    ctx = dict(c)
    ctx["derived"] = {
        "flange_class_number": int(m.group(1)) if m else None,
        "facing": fm.group(1).upper() if fm else None,
        "has_cl_token": bool(re.search(r"CL", flange, re.I)),
        "pt_len_equal": pt_len_equal,
        "pt_len": len(t) if t else 0,
        "press_len": len(p) if p else 0,
        "press_monotonic_violation": mono,
    }
    return ctx


def component_context(ctx: Dict[str, Any], comp: Dict[str, Any]) -> Dict[str, Any]:
    sub = dict(ctx)
    sub["comp"] = comp
    cm = _CLASS_RE.search(comp.get("description") or "")
    sub["derived"] = dict(ctx["derived"])
    sub["derived"]["component_class_number"] = int(cm.group(1)) if cm else None
    return sub


# ---- expression evaluation --------------------------------------------------
def _var(ctx, path):
    cur = ctx
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def evaluate(expr, ctx, facts):
    if not isinstance(expr, dict):
        return expr
    (op, arg), = expr.items()
    ev = lambda x: evaluate(x, ctx, facts)
    if op == "var":
        return _var(ctx, arg)
    if op == "truthy":
        return bool(ev(arg))
    if op == "!":
        return not bool(ev(arg))
    if op == "and":
        return all(bool(ev(a)) for a in arg)
    if op == "or":
        return any(bool(ev(a)) for a in arg)
    if op in ("==", "!="):
        a, b = ev(arg[0]), ev(arg[1])
        return (a == b) if op == "==" else (a != b)
    if op in ("<", "<=", ">", ">="):
        a, b = ev(arg[0]), ev(arg[1])
        if a is None or b is None:
            return False
        return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]
    if op in ("in", "!in"):
        a, lst = ev(arg[0]), ev(arg[1])
        res = a in (lst or [])
        return res if op == "in" else not res
    if op == "regex_match":
        text, pat = ev(arg[0]), arg[1]
        return bool(re.search(pat, text or "", re.I))
    if op == "facts+":
        out = []
        for name in arg:
            out += facts.get(name, [])
        return out
    if op == "facts+var":
        return list(facts.get(arg[0], [])) + [_var(ctx, arg[1])]
    if op == "object":
        return {k: ev(v) for k, v in arg.items()}
    raise ValueError(f"unknown rule operator: {op}")


_TPL = re.compile(r"\{([a-zA-Z0-9_.]+)\}")


def render(template, ctx):
    return _TPL.sub(lambda m: str(_var(ctx, m.group(1))), template)


# ---- runner -----------------------------------------------------------------
def run_rules(data: Dict[str, Any], pack: Optional[Dict[str, Any]] = None) -> List[dict]:
    pack = pack or load_rulepack()
    facts = pack.get("facts", {})
    findings: List[dict] = []
    for c in data.get("classes", []):
        ctx = class_context(c)
        for rule in pack.get("rules", []):
            if rule.get("enabled") is False:
                continue
            scopes = [ctx] if rule.get("scope", "class") == "class" else \
                     [component_context(ctx, x) for x in c.get("components", [])]
            for sctx in scopes:
                if evaluate(rule["when"], sctx, facts):
                    context = (evaluate(rule["context"], sctx, facts)
                               if rule.get("context") else None)
                    findings.append({"class": c.get("class"),
                                     "severity": rule["severity"],
                                     "code": rule["id"],
                                     "message": render(rule["message"], sctx),
                                     "context": context})
    return findings


def run_conventions(data: Dict[str, Any]) -> List[dict]:
    """Rule-engine equivalent of pmskit.validate.validate (shadow mode)."""
    return run_rules(data, load_rulepack())
