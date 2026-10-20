# -*- coding: utf-8 -*-
r"""C:\crossing 후속 자동 실행 스크립트 (Windows, 표준 라이브러리만 사용)

하는 일
 1) run_all.log 에 'run3 all done' 이 있는지 확인
    - 없고 run3.py/geo3.py 가 아직 돌고 있으면 끝날 때까지 대기
    - 없고 아무것도 안 돌고 있으면 python run3.py 재실행 (geo3 는 cache 로 이어서 함,
      이후 좌표 병합 -> 94곳 재촬영(cap) -> 시트 -> 보고서 까지 run3 가 자동 수행)
 2) 끝나면 geo3.log / out\result.json / 산출물 을 요약해 status.txt 로 저장하고 화면에 출력

사용: cd C:\crossing ; python next.py
      (옵션) python next.py --force-cap   : run3 완료 후에도 python cap.py 한 번 더 실행
      (옵션) python next.py --force-doc   : 마지막에 python mkdoc.py 한 번 더 실행
"""
import io, json, os, re, subprocess, sys, time
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
PY = sys.executable
FORCE_CAP = "--force-cap" in sys.argv
FORCE_DOC = "--force-doc" in sys.argv

def log(msg):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    with open("next.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")

def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return ""

def running(*names):
    """names 중 하나라도 명령줄에 포함된 python 프로세스가 있으면 True"""
    cmd = ["powershell", "-NoProfile", "-Command",
           "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
           "Select-Object -ExpandProperty CommandLine"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout
    except Exception as e:
        log(f"프로세스 확인 실패: {e}")
        return False
    return any(n in out for n in names)

def run(script, log_file):
    log(f"실행: python {script}  (로그 {log_file})")
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"\n===== next.py start {datetime.now()} =====\n")
        lf.flush()
        rc = subprocess.call([PY, script], stdout=lf, stderr=subprocess.STDOUT)
    log(f"종료: {script} rc={rc}")
    return rc

# ---------- 1) run3 완료 여부 ----------
def run3_done():
    return "run3 all done" in read("run_all.log")

if run3_done():
    log("run_all.log: run3 all done 확인됨")
else:
    if running("run3.py", "geo3.py", "cap.py"):
        log("run3/geo3/cap 실행 중 -> 완료 대기 (60초 간격)")
        last = ""
        while running("run3.py", "geo3.py", "cap.py") and not run3_done():
            tail = read("geo3.log").strip().splitlines()[-1:] or read("cap.log").strip().splitlines()[-1:]
            tail = tail[0] if tail else ""
            if tail != last:
                log("진행: " + tail[:120])
                last = tail
            time.sleep(60)
        log("대기 종료")
    if not run3_done():
        log("run3 미완료 & 실행 중 아님 -> python run3.py 재실행 (cache 로 이어서 진행)")
        run("run3.py", "run_all.log")

if not run3_done():
    log("경고: run3.py 가 끝났지만 'run3 all done' 이 없음. run_all.log 끝부분:")
    for l in read("run_all.log").strip().splitlines()[-15:]:
        log("  " + l)

# ---------- 2) 선택 재실행 ----------
if FORCE_CAP:
    run("cap.py", "cap.log")
if FORCE_DOC:
    run("mkdoc.py", "mkdoc.log")

# ---------- 3) 요약 ----------
S = []
def add(s=""):
    S.append(s)

add(f"# crossing 상태 요약  {datetime.now():%Y-%m-%d %H:%M}")
add(f"run3 all done: {run3_done()}")

g = read("geo3.log")
if g:
    est = [l for l in g.splitlines() if "km추정" in l]
    add(f"\n## geo3.log  (km추정/교차점없음 {len(est)}건)")
    for l in est[:40]:
        add("  " + l.strip()[:140])
    moved = []
    for l in g.splitlines():
        m = re.search(r"moved_m\D*(\d+(?:\.\d+)?)", l)
        if m:
            moved.append((float(m.group(1)), l.strip()))
    moved.sort(reverse=True)
    big = [x for x in moved if x[0] >= 100]
    add(f"\n## moved_m >= 100m : {len(big)}건 (상위 30)")
    for d, l in big[:30]:
        add(f"  {d:7.0f}m  {l[:130]}")
else:
    add("\ngeo3.log 없음")

rp = os.path.join("out", "result.json")
if os.path.exists(rp):
    try:
        R = json.load(open(rp, encoding="utf-8"))
        items = R.values() if isinstance(R, dict) else R
        items = list(items)
        done = [x for x in items if x.get("done")]
        v2 = [x for x in items if x.get("v") == 2]
        norv = [x for x in items if not x.get("rv")]
        onerv = [x for x in items if x.get("rv") and len(x["rv"]) == 1]
        err = [x for x in items if x.get("err")]
        key = lambda x: x.get("no") or x.get("name")
        add(f"\n## out/result.json  총 {len(items)} / done {len(done)} / v=2(신기준 25m) {len(v2)}")
        add(f"로드뷰 없음 {len(norv)}곳: " + ", ".join(str(key(x)) for x in norv))
        add(f"로드뷰 1장만 {len(onerv)}곳: " + ", ".join(str(key(x)) for x in onerv))
        add(f"오류 {len(err)}곳: " + ", ".join(f"{key(x)}({str(x.get('err'))[:30]})" for x in err))
        add("\n## 개소별 A/B 거리(m)")
        for x in items:
            rv = x.get("rv") or []
            d = " ".join(f"{r.get('dir')}:{r.get('dist','?')}m" for r in rv)
            add(f"  {key(x)} {x.get('name','')[:12]:<12} how={x.get('how','')} v={x.get('v','')} {d}")
    except Exception as e:
        add(f"\nresult.json 파싱 실패: {e}")
else:
    add("\nout/result.json 없음")

add("\n## 산출물")
for p in ["out\\94개소_현장사진_보고서.docx", "out\\sheet_all.jpg", "out\\sheet_changed.jpg",
          "sheet_all.jpg", "sheet_changed.jpg", "coords.json", "coords3.json"]:
    if os.path.exists(p):
        st = os.stat(p)
        add(f"  {p}  {st.st_size//1024}KB  {datetime.fromtimestamp(st.st_mtime):%m-%d %H:%M}")
    else:
        add(f"  {p}  (없음)")

text = "\n".join(S)
with open("status.txt", "w", encoding="utf-8") as f:
    f.write(text)
print("\n" + text)
print("\n>>> 위 내용은 status.txt 에도 저장됨. status.txt 와 sheet_all.jpg 를 Claude 에 올려 주면 검수 진행.")
