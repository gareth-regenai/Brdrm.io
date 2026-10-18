import re, itertools
M = {"cash":1378000,"burn":78100,"runway":17.6,"prior_runway":19.1,"coverage":2.4,
     "revenue":412000,"plan_revenue":450000,"headcount":23}
M["pct_of_plan"] = M["revenue"]/M["plan_revenue"]*100   # 91.56

MONTHS="January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
def strip_labels(t):
    t=re.sub(r"\b(%s)\b"%MONTHS,"",t)           # month names
    t=re.sub(r"\b\d{1,2}\s*(?=)","\\g<0>",t)
    return t
NUM=re.compile(r"£?(\d+(?:,\d{3})*(?:\.\d+)?)\s*(k|m|%|x)?(?![A-Za-z])",re.I)

def figures(text, ignore_labels):
    out=[]
    for m in NUM.finditer(text):
        s=m.group(0); v=float(m.group(1).replace(",","")); u=(m.group(2) or "").lower()
        before=text[max(0,m.start()-1):m.start()]
        if ignore_labels:
            if before in ("Q",): continue                         # Q3, Q4
            if re.match(r"\d{1,2}\s+(%s)"%MONTHS,text[m.start():],re.I): continue  # 12 December
            if re.match(r"(19|20)\d\d$",m.group(1)): continue     # years
            if re.match(r"(two|one)",s): continue
        if s.startswith("£") or u in("k","m"):
            v*= {"k":1e3,"m":1e6}.get(u,1)
        decimals=len(m.group(1).split(".")[1]) if "." in m.group(1) else 0
        out.append((s.strip(),v,decimals,u))
    return out

def strict_ok(v):
    return any(abs(v-x)<1e-9 for x in M.values())

def lenient_ok(v,decimals,u):
    cands=list(M.values())
    for a,b in itertools.permutations(M.values(),2):
        cands.append(abs(a-b))                      # a difference
    for c in cands:
        # matches if the claimed figure is the real one rounded to the precision written
        if u in("k","m"):
            scale={"k":1e3,"m":1e6}[u]; w=round(c/scale,decimals)*scale
            if abs(w-v)<1e-6: return True
        elif round(c,decimals)==v or abs(c-v)<1e-9: return True
    return False

SENT=[
 "Runway is 17.6 months: £1.378m cash over £78.1k average burn.",
 "Cash is about £1.4m.",
 "Runway fell 1.5 months since last quarter.",
 "Revenue was 92% of plan.",
 "Two enterprise deals are expected to sign by 12 December, in Q4.",
 "Pipeline coverage is 2.4x.",
 "Runway is 18.6 months.",
 "Cash is £1.9m.",
]
for t in SENT:
    s=[f for f in figures(t,False)]
    l=[f for f in figures(t,True)]
    sp=all(strict_ok(v) for _,v,_,_ in s) if s else True
    lp=all(lenient_ok(v,d,u) for _,v,d,u in l) if l else True
    bad_s=[n for n,v,_,_ in s if not strict_ok(v)]
    bad_l=[n for n,v,d,u in l if not lenient_ok(v,d,u)]
    print(f"{t}\n   STRICT : {'PASS' if sp else 'REJECT '+str(bad_s)}\n   PROPOSED: {'PASS' if lp else 'REJECT '+str(bad_l)}\n")
