import json, subprocess, sys
SYMS = sys.argv[1:] or ["NVDA","SPY","HOOD","GS","AAPL"]
ENG="/Users/georgigaydarov/Projects/gesh-project-trading"
PRD="/Users/georgigaydarov/Projects/gesh-project"
ONE = ("import json,sys,consensus;"
       "r=consensus.run_consensus_holding(sys.argv[1],1000,100000,100,120);"
       "print('PARITY',json.dumps({'raw':r.get('raw_score'),'verdict':r.get('verdict'),'active':r.get('active_nodes')}))")
def run(repo, sym):
    try:
        out=subprocess.run([f"{repo}/venv/bin/python","-c",ONE,sym],cwd=repo,
                           capture_output=True,text=True,timeout=120).stdout
        for line in out.splitlines():
            if line.startswith("PARITY"): return json.loads(line[6:])
    except Exception as e: return {"err":str(e)}
    return {"err":"no output"}
print(f"{'SYM':6} {'ENGINE':>22} {'PRODUCT':>22} {'Δraw':>7} {'match':>6}")
for s in SYMS:
    e=run(ENG,s); p=run(PRD,s)
    er=e.get("raw"); pr=p.get("raw")
    d = abs(er-pr) if (isinstance(er,(int,float)) and isinstance(pr,(int,float))) else None
    em = f"{e.get('verdict','?')} {er if er is None else round(er,3)}"
    pm = f"{p.get('verdict','?')} {pr if pr is None else round(pr,3)}"
    ok = "✓" if (d is not None and d<=0.05) else ("~" if d is not None else "ERR")
    print(f"{s:6} {em:>22} {pm:>22} {('—' if d is None else round(d,3)):>7} {ok:>6}")
