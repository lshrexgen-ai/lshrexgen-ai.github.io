# 건널목 94개소 현장사진 자동화 — Claude Code 인수인계 (v2)

작성: 2026-10-20 21:22 (이승훈 차장 / 영업2팀) · **v2 보완: 2026-10-20 (Claude)** · 작업 PC: SHLEE-DESKTOP · 폴더: `C:\crossing`

> v2에서 추가된 절: **2-1 검수 판정 기준**, **4-1 환경·의존성**, **6-1 알려진 실패 유형별 대처**, **7 절차 구체화(명령 포함)**, **9 롤백/백업**, **10 보고서 요구사항 체크리스트**, **11 Claude 연결(원격 자동화) 설정**, **12 미확정 사항**. 기존 내용은 그대로 두고 보강만 했음.

## 1. 목적
국가철도공단 입찰 제2026-03-000242-00 「경의선 남가좌리 건널목 외 93개소 지장물검지 지능형(AI) 영상분석시스템 구매설치」
→ 과업구간 94개 건널목마다 **위성사진 1장 + 로드뷰 2장(건널목 양쪽 진입방향, 차단기 보이게)** 을 모아 **Word 보고서**로 제출용 정리.

## 2. 사용자 요구사항 (반드시 지킬 것)
- 토큰 아끼기: 화면 캡처·클릭 반복 금지. **PC에서 스크립트로 일괄 실행**하고 결과만 확인.
- **베스트 화각 = 1번 남가좌리 로드뷰 A**: 건널목 기준 약 **26m** 떨어진 지점에서 건널목 **정면**을 봄. 문형 높이제한 구조물·차단기·경보기·표지판이 한 화면에 다 들어옴. 너무 먼 사진은 싫어함.
- 사진에 **차단기·경보기·건널목 관리건물 등 시설이 안 보이면 위치가 틀린 것** → 반드시 검수하고 수정.
- 사진 찍은 **각도·거리·좌표는 모두 저장**(재현 가능하게).
- 답변은 핵심만 간결하게.

### 2-1. 검수 판정 기준 (v2 추가 — 전수 검수 시 개소마다 아래 코드 하나 부여)
| 코드 | 뜻 | 판정 조건 |
|---|---|---|
| **OK** | 합격 | A·B 모두 ① 선로가 화면을 가로지르고 ② 차단기 또는 경보기(X자 표지·경광등) 중 하나 이상 보이고 ③ 거리 12~45m |
| **OK-1** | 부분합격 | A 또는 B 한 장만 위 조건 충족 (반대편 도로 로드뷰 미제공 등). 보고서에 "반대방향 로드뷰 미제공" 명시 |
| **FAR** | 거리 과다 | 시설은 보이나 45m 초과 또는 건널목이 화면 1/3 이하 크기 → `pick` 재선정 대상 |
| **ANG** | 각도 불량 | 시설은 보이나 정면이 아님(도로가 아닌 옆에서 봄, pan 오류) → pan 재계산 |
| **WRONG** | 위치 오류 | 차단기·경보기·관리건물 전혀 없음, 또는 고가·지하차도·국도 본선 → 좌표 재산출 (6-1절) |
| **NORV** | 로드뷰 없음 | 50m 반경 로드뷰 지점 없음 → 위성만, 보고서에 "로드뷰 미제공(위성만)" |
| **DUP** | 중복 | 다른 개소와 같은 사진/좌표 (예: 15 신망1 = 16 와초1) → km 순서 재확인 |

검수 결과는 `review.json` 에 `{ "no": 10, "code": "WRONG", "memo": "고가 위" }` 형태로 저장 → `mkdoc.py` 의 **현장확인 열**과 재촬영 대상 추출에 사용 (7절 3~4단계).

## 3. 파일 구조 (`C:\crossing`)
| 파일 | 역할 |
|---|---|
| `list.json` | 94개소 목록 `[no, 노선, 시점역, 종점역, km, 건널목명]` |
| `geo.py` | 1차 좌표 산출 (카카오 검색 → 위키 역 km + OSM 선로 경로로 km 위치 → OSM 건널목 노드 매칭). `cache.json`에 모든 외부조회 캐시 |
| `fix.py`, `fix2.py` | 좌표 실패분 보완 (카카오 재검색 / 넓은 bbox·OSM 역 검색) |
| `geo3.py` | **새 방식** 좌표 재산출 → `coords3.json` (아래 4절) |
| `coords.json` | 현재 확정 좌표 (no, lat, lon, how, err_m …). `coords_v1.json` = geo3 적용 전 백업(run3가 생성) |
| `cap.py` | Playwright(headless) 촬영 → `out\NN_이름\위성.jpg, 로드뷰_A.jpg, 로드뷰_B.jpg`, `out\result.json` |
| `backfill.py` | 기존 result.json에 로드뷰 지점좌표·pan·URL 보강 (완료) |
| `sheet.py` / `sheet2.py` | 검수용 썸네일 시트 (전체 / 지정 번호) |
| `mkdoc.py` | Word 보고서 → `out\94개소_현장사진_보고서.docx` |
| `run3.py` | 자동 파이프라인 (fix2 대기 → geo3 → 좌표 병합 → 재촬영 → 시트 → 보고서) |
| `next.py` | **(v2 추가)** run3 완료 확인/대기/재실행 후 `status.txt` 요약 생성. `python next.py [--force-cap] [--force-doc]` |
| `review.json` | **(v2 추가 예정)** 2-1절 검수 결과 |
| 로그 | `run_all.log`(파이프라인), `geo.log`, `fix2.log`, `geo3.log`, `cap.log`, `next.log` |

## 4. 핵심 기술
- **로드뷰 지점 검색 (키 불필요)**: `https://rv.map.kakao.com/roadview-search/v2/nodes?PX={lon}&PY={lat}&RAD=50&PAGE_SIZE=100&INPUT=wgs&TYPE=w&SERVICE=glpano` (헤더 Referer: https://map.kakao.com/) → `streetList[].id, wgsx, wgsy, angle(차량 진행방향), shot_date`
- **로드뷰 화면 고정 URL**: `https://map.kakao.com/?panoid={id}&pan={방위각}&tilt=0&zoom=0&map_type=TYPE_MAP&map_attribute=ROADVIEW` (pan: 정북 0°, 지점→건널목 방위각)
- **위성**: `https://map.kakao.com/link/map/x,{lat},{lon}` → `a.skyview` 클릭 → 정보창(`.InfoWindow,.AddressInfoWindow,.coordinateInfoWindow`) JS로 숨김 → clip 캡처
- **로드뷰 2지점 선택(cap.py pick)**: 건널목에서 **12~45m**, 차량 진행방향(angle)이 건널목 쪽 ±30°(=건널목을 지나는 도로 위), 거리 **25m에 가장 가까운** 지점 A, A와 반대편(방위차 >120°) 지점 B. 결과에 `v=2` 기록(구버전은 재촬영 대상).
- **geo3 좌표 방식**: 구간(시점역~종점역) 단위로 Overpass에서 선로+도로 way 수집 → **선로·도로 평면교차 노드**(bridge/tunnel/layer≠0 제외, 보행로 제외) + `railway=level_crossing` 노드를 후보로 → 역간 선로 경로거리에 투영 → 공단 km로 예측위치 계산 → **구간 내 순서보존 DP 정렬**(스케일 0.95~1.05·오프셋 ±200m 보정, 3개소 이상 구간만)로 중복 없이 매칭. 카카오 등록 좌표는 그 위치를 예측값으로 사용.
- 외부: Overpass(overpass-api.de, 느림 30s+/요청, 미러는 타임아웃 잦음), 카카오 검색 `search.map.kakao.com/mapsearch/map.daum?q=`, 위키 원문 `ko.wikipedia.org/w/index.php?title={역}역&action=raw` (`영업거리N`에서 `<ref>` 제거 후 첫 km)

### 4-1. 환경·의존성 (v2 추가 — 다른 PC에서 재현할 때)
- Python 3.x (64bit). 패키지: `playwright`, `requests`, `python-docx`, `Pillow` → `pip install playwright requests python-docx pillow` 후 `python -m playwright install chromium`
- 외부 API는 모두 **비공식/무키** 엔드포인트. 요청 간 지연 유지(카카오 1초, Overpass 결과 캐시 필수). 차단되면 `cache.json` 덕분에 재실행으로 이어짐.
- 로드뷰 `shot_date` 가 **2019년 이전**이면 시설이 바뀌었을 수 있음 → 검수 시 날짜 함께 확인(result.json `rv[].date`).

## 5. 저장되는 데이터 (`out\result.json`, 개소별)
`name, how, lat, lon, v, rv:[{dir(A/B), panoid, pano_lat, pano_lon, pan, tilt, from_brg(건널목 기준 지점 방위), dist(m), date(촬영월), url}], err, done`

## 6. 진행 상황 (21:22 기준)
- 1차 촬영 90곳 완료(구 기준 30m). 검수 결과:
  - 시설 확인 OK 다수(1~5,7,8,12,17~19,24,26,27,31~39,47~49,53~58,62~64,66~72,74,79~81,84,85,89 등)
  - **위치 틀림(시설 안 보임) 13곳**: 10 서빙고남부(고가), 11 신원2, 21 발한(해안도로), 25 제철1, 29 방제, 30 신안·50 산양(지하차도), 51 금남(국도), 52 용궁1, 61 화지1, 65 간방, 73 반구2, 90 용원
  - **15 신망1 = 16 와초1 동일 사진**(좌표 겹침)
  - 로드뷰 없음 21곳, 좌표 미확보 13곳(40,43,44,45,78,82,83,86,87,91~94 — 화물선 위주, fix2로 일부 보완됨)
- 지금 실행 중: `run3.py` → `geo3.py`(10/94 진행, Overpass 느림). 끝나면 자동으로 좌표 병합 → **94곳 전부 새 기준(25m)으로 재촬영** → `sheet_changed.jpg`, `sheet_all.jpg` → 보고서 갱신.
- 시험 확인: 5번·8번 신규 거리로 촬영 OK.

### 6-1. 알려진 실패 유형별 대처 (v2 추가)
| 유형 | 예 | 원인 추정 | 대처 |
|---|---|---|---|
| 고가·지하차도·국도 본선 | 10, 30, 50, 51 | geo3 이전 방식이 입체교차를 평면교차로 잡음 | geo3는 bridge/tunnel/layer 제외하므로 **재산출 결과 우선 확인**. 그래도 틀리면 같은 선로 km ±300m 내 `railway=level_crossing` 노드를 수동 선택 |
| 좌표 중복 (DUP) | 15=16 | 두 개소 km 차이가 작아 같은 노드에 매칭 | geo3 DP 정렬이 중복 금지. 남으면 list.json km 오기 여부 확인 → 위성에서 인접 교차점 2개를 순서대로 배정 |
| 해안도로·역 근처 | 21 | 카카오 검색이 지명(마을)을 반환 | `how` 가 `kakao` 인 건은 신뢰도 낮음 → geo3(km 기반) 값으로 교체 |
| 화물선·좌표 미확보 | 40,43,44,45,78,82~87,91~94 | 위키에 역 km 없음 / OSM 선로 불완전 | 공단 **건널목 위치도·주소**를 받아 수동 입력. 공공데이터포털 "건널목 현황"(소재지 주소 포함) 데이터셋도 후보 — 받으면 `how=manual` 로 기록 |
| 로드뷰 없음 (NORV) | 21곳 | 사도·농로, 카카오 미촬영 | RAD 를 50→80m 로 1회 재시도(원거리 사진은 FAR 로 표기). 그래도 없으면 위성만 |
| 로드뷰는 있으나 각도 ±30° 밖 | 일부 | 건널목 진입로가 선로와 비스듬 | pick 각도 허용을 ±45° 로 완화하는 옵션 추가 검토 |

## 7. 다음에 할 일 (v2: 명령 포함으로 구체화)
1. **파이프라인 완료 확인**: `python next.py` → `status.txt` 생성. `run3 all done` 없고 프로세스도 없으면 next.py가 `run3.py` 재실행(geo3는 cache로 이어짐).
2. **geo3 결과 점검**: `status.txt` 의 `km추정(교차점없음)` 목록과 `moved_m ≥ 100m` 목록 확인. moved_m 큰 건은 반드시 사진으로 재검수.
3. **전수 검수**: `sheet_all.jpg` 를 구간별로 잘라 보며 2-1절 코드 부여 → `review.json` 작성.
   - 13 WRONG 후보 + 15/16 DUP + moved_m 큰 건 우선.
4. **틀린 곳 수정 루프** (개소당):
   ```powershell
   # ① coords.json 에서 해당 no 의 lat/lon 을 새 값으로, how 를 "manual" 로 수정 (.py 패치로)
   # ② out\result.json 에서 해당 항목 삭제 (done 초기화)
   # ③ 재촬영 (cap.py 는 result.json 에 없는/미완 항목만 촬영)
   python cap.py
   # ④ 해당 번호만 시트로 확인
   python sheet2.py 10 11 21
   ```
   후보 좌표 찾는 법: 카카오맵 위성에서 선로·도로 교차 지점 클릭 → 좌표 복사. 또는 Overpass `node["railway"="level_crossing"](around:300,{lat},{lon});`
5. **로드뷰 없는 곳**: 보고서에 "로드뷰 미제공(위성만)" 명시 (review.json code=NORV 로 자동 처리되게 mkdoc 수정).
6. **mkdoc.py 보강**: ① 현장확인 열(OK=✓, WRONG/FAR/ANG=✗, NORV=－) ② 로드뷰 URL(result.json `rv[].url`) ③ 촬영월 ④ 좌표출처(`how`) → `python mkdoc.py` → 최종본 전달.
7. 좌표 산출 신뢰도 낮은 곳(km추정, how=kakao)은 공단 건널목 위치도·주소 받으면 바로 반영.

## 8. 주의
- PowerShell에는 heredoc 없음 → 패치는 .py 파일로 작성해 실행.
- 한글 출력은 `sys.stdout.reconfigure(encoding='utf-8')` + 파일로 저장 후 `Get-Content -Encoding UTF8`.
- 백그라운드 실행: `Start-Process -WindowStyle Hidden python -ArgumentList '...'`
- `claude` CLI는 PATH에 없음(데스크톱 앱 내장 `%APPDATA%\Claude\claude-code\2.1.299\...\claude.exe`), remote-control은 `claude auth login` 필요.
- 손으로 찍은 기존 사진(1~6,8,9번)은 클라우드 작업공간에만 있음 — 자동촬영본으로 대체.
- **(v2)** 로그·JSON 전체를 Claude에 붙여넣지 말 것(토큰). `status.txt` 요약과 썸네일 시트만 전달.
- **(v2)** `cap.py` 를 run3와 동시에 돌리지 말 것 — 같은 `result.json` 을 둘이 쓰면 깨짐. `next.py` 가 실행 중 여부를 먼저 확인함.

## 9. 롤백·백업 (v2 추가)
- 좌표: `coords_v1.json`(geo3 이전) → 되돌리려면 `copy coords_v1.json coords.json` 후 `out\result.json` 삭제, `python cap.py`.
- 사진: 재촬영 전 `out\` 을 `out_YYYYMMDD\` 로 복사해 둘 것(run3 재촬영은 덮어씀). 1차본(30m 기준)은 비교용으로 보관.
- 캐시: `cache.json` 은 지우지 말 것(Overpass 재조회 수십 분). 특정 개소만 재조회하려면 해당 키만 삭제.

## 10. 보고서(docx) 요구사항 체크리스트 (v2 추가)
- [ ] 표지: 사업명·입찰번호·작성일·작성자(영업2팀 이승훈)
- [ ] 개소별 1페이지: 번호·노선·구간(시점역~종점역)·km·건널목명 / 위성 1 + 로드뷰 A·B / 좌표(lat,lon)·좌표출처·현장확인(✓✗－)·로드뷰 촬영월·로드뷰 URL
- [ ] 로드뷰 미제공 개소: "로드뷰 미제공(위성만)" 문구
- [ ] 끝: 요약표(94행: 번호·명·확인코드·비고) + 출처 주석(카카오맵 위성/로드뷰, OSM, 촬영일)
- [ ] 파일명 `out\94개소_현장사진_보고서.docx`, 용량 확인(사진 JPG 품질 80 이하로 50MB 이내 권장)

## 11. Claude가 PC에서 직접 돌리게 하려면 (v2 추가)
현재 클라우드 세션은 `C:\crossing` 에 접근 불가. 아래 중 하나:
- **Claude Desktop 앱**에서 `C:\crossing` 폴더를 열고 작업 → 앱 내장 브라우저·터미널 사용 가능.
- **Remote Control**: PowerShell에서
  ```powershell
  & "$env:APPDATA\Claude\claude-code\2.1.299\<경로>\claude.exe" auth login
  cd C:\crossing; & "...\claude.exe" remote-control
  ```
  → 폰/웹 Claude Code 앱에 PC 세션이 나타남. 그 세션에 "README_인수인계.md 읽고 7절 이어서" 로 지시.
- 연결 없이 쓸 때: `python next.py` 결과(`status.txt`) + 시트 이미지를 클라우드 세션에 올리면 검수·좌표 제안까지 가능(실행만 PC에서).

## 12. 미확정 사항 (v2 추가 — 확인 필요)
- `run3.py` 가 이미 끝난 단계(geo3 완료, 촬영 완료)를 건너뛰는지 여부 → 코드 확인 전엔 완료 후 재실행 금지.
- `cap.py` 가 `result.json` 의 `done` 항목을 건너뛰는지(7절 4단계 전제) → 첫 수정 루프에서 확인.
- 입찰 제출 마감일·보고서 제출 형식(PDF 변환 필요 여부) → 사용자 확인.
- 공단에서 건널목 위치도·주소 수령 가능 여부(13곳 좌표 미확보 해결의 핵심).
