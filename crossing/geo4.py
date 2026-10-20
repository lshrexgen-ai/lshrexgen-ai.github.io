# -*- coding: utf-8 -*-
r"""geo4.py — OSM에 선로·도로 교차가 없는 시골 구간용 좌표 재산출 (카카오 로드뷰 지점 스캔 방식)

핵심 아이디어
  OSM은 시골 도로가 빠져 있어도 **선로(railway=rail) 기하는 대부분 있음**.
  카카오 로드뷰 차량은 **실제 도로**만 달림 → 선로를 따라 로드뷰 지점을 스캔하다가
  선로에서 10m 이내에 로드뷰 지점이 있으면 그 자리는 "도로가 선로를 건너는 곳".
  그 후보들을 공단 km 순서로 정렬·매칭하면 OSM 도로 없이도 건널목 좌표가 나옴.
  (고가/지하는 OSM 선로 bridge/tunnel 태그·도로 bridge 태그로 제외 표시)

입력 : list.json, coords.json, (있으면) review_v2.json
출력 : coords4.json  (no, lat, lon, how="rv-scan", conf, s_m, cand)
       cand4.md      (개소별 후보 top3 + 로드뷰 URL — 폰에서 탭해서 확인)
       cache4.json   (Overpass/카카오 응답 캐시, 재실행 시 이어서)
사용 :
  python geo4.py                       # review_v2.json 의 ✗/△/좌표없음 대상
  python geo4.py --only 10 11 21       # 지정 번호만
  python geo4.py --all                 # 94곳 전부 (✓ 는 앵커로만 사용, 좌표 유지)
  python geo4.py --apply               # coords4.json 의 conf>=0.5 를 coords.json 에 반영
                                       #   (coords_v3.json 백업, out\result.json 해당 항목 삭제) → 이후 python cap.py
"""
import io, json, math, os, re, sys, time, argparse, heapq
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
LOG = open("geo4.log", "a", encoding="utf-8")
def log(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); LOG.write(s + "\n"); LOG.flush()

# ---------------- 설정 ----------------
STEP_M      = 90      # 선로 따라 스캔 간격 (RAD 50 두 번이 겹치게)
RV_RAD      = 50      # 로드뷰 지점 검색 반경
NEAR_RAIL_M = 10      # 로드뷰 지점이 선로에서 이 거리 이내면 "도로가 선로 위를 지남"
CLUSTER_M   = 30      # 같은 건널목으로 묶는 선로상 거리
MATCH_TOL_M = 450     # 예측 위치와 후보 사이 허용 거리
PAD_DEG     = 0.03    # 역 사이 bbox 여유
KAKAO_DELAY = 0.25
OVERPASS    = ["https://overpass-api.de/api/interpreter",
               "https://overpass.kumi.systems/api/interpreter",
               "https://overpass.private.coffee/api/interpreter"]
HDR_KAKAO   = {"Referer": "https://map.kakao.com/", "User-Agent": "Mozilla/5.0"}

# ---------------- 캐시 ----------------
CACHE_F = "cache4.json"
cache = json.load(open(CACHE_F, encoding="utf-8")) if os.path.exists(CACHE_F) else {}
_dirty = 0
def cache_save(force=False):
    global _dirty
    _dirty += 1
    if force or _dirty >= 40:
        json.dump(cache, open(CACHE_F, "w", encoding="utf-8"), ensure_ascii=False)
        _dirty = 0

# ---------------- 지오 유틸 ----------------
R = 6371000.0
def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(h))
def brg(a, b):
    la1, la2 = math.radians(a[0]), math.radians(b[0]); dl = math.radians(b[1]-a[1])
    x = math.sin(dl)*math.cos(la2); y = math.cos(la1)*math.sin(la2)-math.sin(la1)*math.cos(la2)*math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360
def dest(a, bearing, d):
    la1, lo1, br = math.radians(a[0]), math.radians(a[1]), math.radians(bearing)
    la2 = math.asin(math.sin(la1)*math.cos(d/R) + math.cos(la1)*math.sin(d/R)*math.cos(br))
    lo2 = lo1 + math.atan2(math.sin(br)*math.sin(d/R)*math.cos(la1), math.cos(d/R)-math.sin(la1)*math.sin(la2))
    return (math.degrees(la2), math.degrees(lo2))
def angdiff(a, b):
    d = abs((a-b) % 360); return min(d, 360-d)
def interp(a, b, t): return (a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t)

class Path:
    """선로 경로 (좌표 리스트 + 누적거리 + 각 세그먼트의 way 태그)"""
    def __init__(self, pts, tags):
        self.pts = pts; self.tags = tags  # tags[i] = i번째 세그먼트(pts[i]→pts[i+1])의 way 태그
        self.cum = [0.0]
        for i in range(1, len(pts)): self.cum.append(self.cum[-1] + hav(pts[i-1], pts[i]))
        self.length = self.cum[-1]
    def at(self, s):
        s = max(0, min(s, self.length)); i = max(0, min(len(self.pts)-2, _bisect(self.cum, s)))
        seg = self.cum[i+1]-self.cum[i]; t = 0 if seg == 0 else (s-self.cum[i])/seg
        return interp(self.pts[i], self.pts[i+1], t), i
    def project(self, p):
        """점 p 를 경로에 투영 → (s, 수직거리, 세그idx, 좌/우 부호)"""
        best = (None, 1e18, 0, 0)
        # 거친 탐색: 가까운 세그먼트만
        for i in range(len(self.pts)-1):
            a, b = self.pts[i], self.pts[i+1]
            if abs(a[0]-p[0]) > 0.01 or abs(a[1]-p[1]) > 0.013: continue
            # 로컬 평면 근사
            ky = 111320.0; kx = 111320.0*math.cos(math.radians(a[0]))
            ax, ay = 0.0, 0.0; bx, by = (b[1]-a[1])*kx, (b[0]-a[0])*ky; px, py = (p[1]-a[1])*kx, (p[0]-a[0])*ky
            L2 = bx*bx+by*by
            t = 0 if L2 == 0 else max(0, min(1, (px*bx+py*by)/L2))
            qx, qy = bx*t, by*t; d = math.hypot(px-qx, py-qy)
            if d < best[1]:
                side = 1 if (bx*py - by*px) > 0 else -1
                best = (self.cum[i] + t*(self.cum[i+1]-self.cum[i]), d, i, side)
        return best
def _bisect(arr, x):
    lo, hi = 0, len(arr)-1
    while lo < hi:
        mid = (lo+hi+1)//2
        if arr[mid] <= x: lo = mid
        else: hi = mid-1
    return lo

# ---------------- 외부 조회 ----------------
def overpass(q, key):
    k = "op:" + key
    if k in cache: return cache[k]
    for url in OVERPASS:
        for _ in range(2):
            try:
                r = requests.post(url, data={"data": q}, timeout=180)
                if r.status_code == 200:
                    j = r.json(); cache[k] = j; cache_save(True); return j
                log(f"  overpass {url} HTTP {r.status_code}"); time.sleep(5)
            except Exception as e:
                log(f"  overpass {url} err {e}"); time.sleep(5)
    return None

def kakao_rv(lat, lon, rad=RV_RAD):
    k = f"rv:{lat:.5f},{lon:.5f},{rad}"
    if k in cache: return cache[k]
    url = (f"https://rv.map.kakao.com/roadview-search/v2/nodes?PX={lon}&PY={lat}&RAD={rad}"
           f"&PAGE_SIZE=100&INPUT=wgs&TYPE=w&SERVICE=glpano")
    out = []
    for _ in range(3):
        try:
            r = requests.get(url, headers=HDR_KAKAO, timeout=20)
            if r.status_code == 200:
                j = r.json(); lst = _find_key(j, "streetList") or []
                for n in lst:
                    try:
                        out.append({"id": str(n.get("id")), "lat": float(n.get("wgsy")), "lon": float(n.get("wgsx")),
                                    "angle": float(n.get("angle") or 0), "date": str(n.get("shot_date") or "")[:6]})
                    except Exception: pass
                break
            time.sleep(2)
        except Exception as e:
            time.sleep(2)
    time.sleep(KAKAO_DELAY)
    cache[k] = out; cache_save(); return out

def _find_key(o, key):
    if isinstance(o, dict):
        if key in o: return o[key]
        for v in o.values():
            r = _find_key(v, key)
            if r is not None: return r
    elif isinstance(o, list):
        for v in o:
            r = _find_key(v, key)
            if r is not None: return r
    return None

def station_coord(name):
    """역 좌표: OSM(station/halt 이름) → 실패 시 카카오 검색"""
    nm = re.sub(r"역$", "", name.strip())
    k = "st:" + nm
    if k in cache: return tuple(cache[k]) if cache[k] else None
    q = f'[out:json][timeout:60];node["railway"~"station|halt|stop"]["name"~"^{nm}(역)?$"](33,124,39,132);out;'
    j = overpass(q, "st_" + nm)
    pt = None
    if j and j.get("elements"):
        e = j["elements"][0]; pt = (e["lat"], e["lon"])
    if not pt:
        try:
            r = requests.get("https://search.map.kakao.com/mapsearch/map.daum", params={"q": nm + "역", "msFlag": "A", "sort": "0"},
                             headers=HDR_KAKAO, timeout=20)
            j = r.json(); pl = _find_key(j, "place") or []
            for p in pl:
                if "역" in str(p.get("name", "")) and p.get("y") and p.get("x"):
                    pt = (float(p["y"]), float(p["x"])); break
        except Exception as e:
            log(f"  kakao station {nm} err {e}")
    cache[k] = list(pt) if pt else None; cache_save(True)
    return pt

# ---------------- 선로 경로 ----------------
def rail_path(stA, stB, key):
    """두 역 사이 bbox 의 rail way 로 그래프 → 최단경로(Path). 실패 시 None"""
    s, n = min(stA[0], stB[0])-PAD_DEG, max(stA[0], stB[0])+PAD_DEG
    w, e = min(stA[1], stB[1])-PAD_DEG, max(stA[1], stB[1])+PAD_DEG
    q = f'[out:json][timeout:170];way["railway"~"^(rail|narrow_gauge|light_rail)$"]["service"!~"yard|spur|siding"]({s},{w},{n},{e});(._;>;);out body;'
    j = overpass(q, "rail_" + key)
    if not j: return None
    nodes = {el["id"]: (el["lat"], el["lon"]) for el in j["elements"] if el["type"] == "node"}
    adj = defaultdict(list); segtag = {}
    for el in j["elements"]:
        if el["type"] != "way": continue
        t = el.get("tags", {}); nd = el["nodes"]
        for a, b in zip(nd, nd[1:]):
            if a in nodes and b in nodes:
                d = hav(nodes[a], nodes[b]); adj[a].append((b, d)); adj[b].append((a, d))
                segtag[(a, b)] = t; segtag[(b, a)] = t
    if not nodes: return None
    def nearest(pt):
        return min(nodes, key=lambda i: hav(nodes[i], pt))
    a0, b0 = nearest(stA), nearest(stB)
    # Dijkstra
    dist = {a0: 0.0}; prev = {}; pq = [(0.0, a0)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == b0: break
        if d > dist.get(u, 1e18): continue
        for v, w_ in adj[u]:
            nd = d + w_
            if nd < dist.get(v, 1e18): dist[v] = nd; prev[v] = u; heapq.heappush(pq, (nd, v))
    if b0 not in dist: return None
    seq = [b0]
    while seq[-1] != a0: seq.append(prev[seq[-1]])
    seq.reverse()
    pts = [nodes[i] for i in seq]; tags = [segtag.get((seq[i], seq[i+1]), {}) for i in range(len(seq)-1)]
    return Path(pts, tags)

def rail_path_around(center, radius_m, key):
    """역 정보 없이 좌표 주변 선로만 (단일 개소용): 중심에서 가장 가까운 way 들로 연결 경로"""
    d = radius_m/111320.0
    q = f'[out:json][timeout:120];way["railway"~"^(rail|narrow_gauge)$"]["service"!~"yard|spur|siding"]({center[0]-d},{center[1]-d*1.3},{center[0]+d},{center[1]+d*1.3});(._;>;);out body;'
    j = overpass(q, "railaround_" + key)
    if not j: return None
    nodes = {el["id"]: (el["lat"], el["lon"]) for el in j["elements"] if el["type"] == "node"}
    ways = [el for el in j["elements"] if el["type"] == "way"]
    if not ways: return None
    # 중심에 가장 가까운 노드를 지나는 way 부터 양쪽으로 이어붙이기 (가장 먼 두 끝 사이 최단경로)
    adj = defaultdict(list); segtag = {}
    for el in ways:
        t = el.get("tags", {}); nd = el["nodes"]
        for a, b in zip(nd, nd[1:]):
            if a in nodes and b in nodes:
                dd = hav(nodes[a], nodes[b]); adj[a].append((b, dd)); adj[b].append((a, dd)); segtag[(a, b)] = t; segtag[(b, a)] = t
    c0 = min(nodes, key=lambda i: hav(nodes[i], center))
    def far(src):
        dist = {src: 0.0}; prev = {}; pq = [(0.0, src)]
        while pq:
            d_, u = heapq.heappop(pq)
            if d_ > dist[u]: continue
            for v, w_ in adj[u]:
                if d_+w_ < dist.get(v, 1e18): dist[v] = d_+w_; prev[v] = u; heapq.heappush(pq, (d_+w_, v))
        return dist, prev
    d1, _ = far(c0); e1 = max(d1, key=d1.get)
    d2, p2 = far(e1); e2 = max(d2, key=d2.get)
    seq = [e2]
    while seq[-1] != e1: seq.append(p2[seq[-1]])
    pts = [nodes[i] for i in seq]; tags = [segtag.get((seq[i], seq[i+1]), {}) for i in range(len(seq)-1)]
    return Path(pts, tags)

def road_bridges(path, key):
    """경로 bbox 안의 도로 교량/터널 way 노드 좌표 (후보가 입체교차인지 표시용)"""
    lats = [p[0] for p in path.pts]; lons = [p[1] for p in path.pts]
    q = (f'[out:json][timeout:120];(way["highway"]["bridge"]({min(lats)-0.005},{min(lons)-0.005},{max(lats)+0.005},{max(lons)+0.005});'
         f'way["highway"]["tunnel"]({min(lats)-0.005},{min(lons)-0.005},{max(lats)+0.005},{max(lons)+0.005}););(._;>;);out body;')
    j = overpass(q, "rb_" + key)
    if not j: return []
    return [(el["lat"], el["lon"]) for el in j["elements"] if el["type"] == "node"]

# ---------------- 로드뷰 스캔 → 후보 ----------------
def scan_candidates(path, s_from, s_to, bridges):
    s_from = max(0, s_from); s_to = min(path.length, s_to)
    seen = {}; s = s_from
    while s <= s_to + 1:
        pt, _ = path.at(s)
        for n in kakao_rv(pt[0], pt[1]):
            seen[n["id"]] = n
        s += STEP_M
    # 선로 근접 노드 → 클러스터
    near = []
    for n in seen.values():
        ps, d, i, side = path.project((n["lat"], n["lon"]))
        if ps is None: continue
        n["s"], n["d"], n["seg"], n["side"] = ps, d, i, side
        if d <= NEAR_RAIL_M: near.append(n)
    near.sort(key=lambda n: n["s"])
    clusters = []
    for n in near:
        if clusters and n["s"] - clusters[-1][-1]["s"] <= CLUSTER_M: clusters[-1].append(n)
        else: clusters.append([n])
    cands = []
    allnodes = list(seen.values())
    for cl in clusters:
        s_c = sum(n["s"] for n in cl)/len(cl); pt, i = path.at(s_c)
        t = path.tags[min(i, len(path.tags)-1)] if path.tags else {}
        rail_grade = not (t.get("bridge") or t.get("tunnel") or (t.get("layer") not in (None, "0")))
        nb = [n for n in allnodes if abs(n.get("s", -1e9) - s_c) <= 60 and 4 < n.get("d", 0) <= 50]
        sides = {n["side"] for n in nb}
        road_br = any(hav(b, pt) < 25 for b in bridges)
        # 도로 방향 vs 선로 방향 (수직에 가까울수록 건널목답다)
        a, _ = path.at(max(0, s_c-15)); b, _ = path.at(min(path.length, s_c+15)); rail_b = brg(a, b)
        angs = [angdiff(n["angle"], rail_b) for n in cl]; cross = sum(min(x, 180-x) for x in angs)/len(angs) if angs else 0
        date = max((n["date"] for n in cl), default="")
        cands.append({"s": s_c, "lat": round(pt[0], 6), "lon": round(pt[1], 6), "n": len(cl), "both": len(sides) == 2,
                      "rail_grade": rail_grade, "road_bridge": road_br, "cross_deg": round(cross), "date": date,
                      "pano": cl[0]["id"], "pano_lat": cl[0]["lat"], "pano_lon": cl[0]["lon"]})
    return cands

def cand_url(c):
    pan = round(brg((c["pano_lat"], c["pano_lon"]), (c["lat"], c["lon"])))
    return f"https://map.kakao.com/?panoid={c['pano']}&pan={pan}&tilt=0&zoom=0&map_type=TYPE_MAP&map_attribute=ROADVIEW"

def cand_score(c, pred_s, tol):
    if pred_s is None: base = 0.5
    else:
        dd = abs(c["s"] - pred_s)
        if dd > tol: return 0.0
        base = 1.0 - dd/tol
    if c["both"]: base += 0.25
    if not c["rail_grade"] or c["road_bridge"]: base -= 0.5
    base += min(c["cross_deg"], 90)/90*0.15
    return max(0.0, min(1.0, base))

# ---------------- 메인 ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", type=int); ap.add_argument("--all", action="store_true"); ap.add_argument("--apply", action="store_true")
    ap.add_argument("--tol", type=float, default=MATCH_TOL_M)
    args = ap.parse_args()

    L = json.load(open("list.json", encoding="utf-8"))
    items = [{"no": int(x[0]), "line": x[1], "stA": x[2], "stB": x[3], "km": float(x[4]) if x[4] not in (None, "") else None, "name": x[5]} for x in L]
    C = json.load(open("coords.json", encoding="utf-8")) if os.path.exists("coords.json") else []
    if isinstance(C, dict): C = list(C.values())
    coords = {int(c["no"]): c for c in C if c.get("lat")}
    review = {}
    if os.path.exists("review_v2.json"):
        rv = json.load(open("review_v2.json", encoding="utf-8"))
        if isinstance(rv, dict): review = {int(k): (v if isinstance(v, str) else v.get("code", "")) for k, v in rv.items()}
        else: review = {int(x["no"]): x.get("code", "") for x in rv}
    good = {n for n, c in review.items() if "✓" in c or c.upper() == "OK"}

    if args.only: targets = set(args.only)
    elif args.all: targets = {i["no"] for i in items}
    else:
        targets = {i["no"] for i in items if i["no"] not in good}  # ✗ △ － 좌표없음 전부
        if not review: targets = {i["no"] for i in items if i["no"] not in coords}

    if args.apply: return apply(coords, C)

    out = {}; md = ["# geo4 후보 (탭해서 로드뷰 확인)\n"]
    segs = defaultdict(list)
    for it in items: segs[(it["line"], it["stA"], it["stB"])].append(it)

    for (line, sa, sb), its in segs.items():
        its.sort(key=lambda x: (x["km"] is None, x["km"]))
        tg = [i for i in its if i["no"] in targets]
        if not tg: continue
        key = re.sub(r"\W+", "_", f"{line}_{sa}_{sb}")
        log(f"\n== {line} {sa}~{sb}: 대상 {[i['no'] for i in tg]}")
        A, B = station_coord(sa), station_coord(sb)
        path = rail_path(A, B, key) if (A and B) else None
        anchors = []
        if path:
            log(f"  선로경로 {path.length/1000:.1f}km")
            for i in its:
                c = coords.get(i["no"])
                if c and i["km"] is not None and (i["no"] in good):
                    s, d, _, _ = path.project((c["lat"], c["lon"]))
                    if s is not None and d < 60: anchors.append((i["km"]*1000, s))
        else:
            # 역 좌표/경로 실패 → 개소별 기존 좌표 주변 1.5km 선로
            log("  역 경로 실패 → 개소별 주변 선로 사용")
        # km→s 변환 (앵커 있으면 중앙값 오프셋, 방향 ±)
        def km2s(km):
            if km is None or not anchors: return None
            for sign in (1, -1):
                offs = sorted(s - sign*k for k, s in anchors); off = offs[len(offs)//2]
                spread = max(offs)-min(offs) if len(offs) > 1 else 0
                if spread < 600: return sign*km*1000 + off
            return None
        bridges = road_bridges(path, key) if path else []
        used = set()
        for it in tg:
            no = it["no"]; c0 = coords.get(no); pred_s = None; P = path
            if P:
                pred_s = km2s(it["km"])
                if pred_s is None and c0:
                    s, d, _, _ = P.project((c0["lat"], c0["lon"]))
                    if s is not None and d < 800: pred_s = s
            if not P and c0:
                P = rail_path_around((c0["lat"], c0["lon"]), 1500, f"{no}")
                if P:
                    s, d, _, _ = P.project((c0["lat"], c0["lon"])); pred_s = s if s is not None else None
                    bridges = road_bridges(P, f"{no}")
            if not P:
                log(f"  [{no}] {it['name']}: 선로 경로 없음 → 수동"); md.append(f"## {no} {it['name']} — 선로 경로 못 찾음(역 좌표/OSM 선로 없음)\n"); continue
            if pred_s is None:
                s_from, s_to = 0, P.length; tol = 1e9
            else:
                s_from, s_to = pred_s - args.tol*1.5, pred_s + args.tol*1.5; tol = args.tol
            cands = [c for c in scan_candidates(P, s_from, s_to, bridges) if round(c["s"]) not in used]
            for c in cands: c["score"] = round(cand_score(c, pred_s, tol), 2)
            cands.sort(key=lambda c: -c["score"])
            top = cands[:3]
            log(f"  [{no}] {it['name']} km={it['km']} pred_s={None if pred_s is None else round(pred_s)} 후보 {len(cands)}: " +
                "; ".join(f"s={round(c['s'])} sc={c['score']} both={c['both']} grade={c['rail_grade']} rb={c['road_bridge']}" for c in top))
            md.append(f"## {no} {it['name']} ({line} {sa}~{sb} km {it['km']})  예측 s={None if pred_s is None else round(pred_s)}m")
            if not top: md.append("- 후보 없음 (로드뷰가 선로 근처에 없음 → 위성 수동)\n"); continue
            for r_, c in enumerate(top, 1):
                flag = "" if (c["rail_grade"] and not c["road_bridge"]) else " ⚠입체교차 의심"
                md.append(f"- {r_}. 점수 {c['score']} | 예측과 {('?' if pred_s is None else str(round(abs(c['s']-pred_s))))}m | 양쪽로드뷰 {'O' if c['both'] else 'X'} | 교차각 {c['cross_deg']}° | {c['date']}{flag}  \n"
                          f"  {c['lat']},{c['lon']}  [로드뷰]({cand_url(c)})")
            md.append("")
            best = top[0]
            if best["score"] >= 0.5:
                used.add(round(best["s"]))
                out[no] = {"no": no, "name": it["name"], "lat": best["lat"], "lon": best["lon"], "how": "rv-scan",
                           "conf": best["score"], "s_m": round(best["s"]), "cand": top}
            else:
                out[no] = {"no": no, "name": it["name"], "lat": best["lat"], "lon": best["lon"], "how": "rv-scan-weak",
                           "conf": best["score"], "s_m": round(best["s"]), "cand": top}
        cache_save(True)

    json.dump(list(out.values()), open("coords4.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open("cand4.md", "w", encoding="utf-8").write("\n".join(md))
    strong = sum(1 for v in out.values() if v["conf"] >= 0.5)
    log(f"\n완료: 대상 {len(targets)} / 후보 산출 {len(out)} / conf>=0.5 {strong} → coords4.json, cand4.md")
    log("다음: cand4.md 의 링크로 확인 → python geo4.py --apply → python cap.py")

def apply(coords, C):
    if not os.path.exists("coords4.json"): log("coords4.json 없음"); return
    new = json.load(open("coords4.json", encoding="utf-8"))
    import shutil
    shutil.copy("coords.json", "coords_v3.json")
    picks = {}
    if os.path.exists("picks.json"):  # {"10": 2} 처럼 후보 순위를 수동 지정하면 그걸 우선
        picks = {int(k): int(v) for k, v in json.load(open("picks.json", encoding="utf-8")).items()}
    changed = []
    for n in new:
        no = n["no"]
        if no in picks:
            c = n["cand"][picks[no]-1]; lat, lon, how = c["lat"], c["lon"], "rv-scan-pick"
        elif n["conf"] >= 0.5: lat, lon, how = n["lat"], n["lon"], "rv-scan"
        else: continue
        tgt = coords.get(no)
        if tgt is None:
            tgt = {"no": no, "name": n["name"]}; C.append(tgt); coords[no] = tgt
        if abs(tgt.get("lat", 0)-lat) < 1e-6 and abs(tgt.get("lon", 0)-lon) < 1e-6: continue
        tgt.update({"lat": lat, "lon": lon, "how": how, "err_m": 15}); changed.append(no)
    json.dump(C, open("coords.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rp = os.path.join("out", "result.json")
    if os.path.exists(rp):
        Rj = json.load(open(rp, encoding="utf-8"))
        if isinstance(Rj, dict):
            for k in list(Rj):
                if int(Rj[k].get("no", k) if str(Rj[k].get("no", k)).isdigit() else -1) in changed: del Rj[k]
        else:
            Rj = [x for x in Rj if int(x.get("no", -1)) not in changed]
        json.dump(Rj, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"coords.json 갱신 {len(changed)}곳: {changed} (백업 coords_v3.json). 이제 python cap.py")

if __name__ == "__main__":
    main()
