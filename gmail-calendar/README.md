# Gmail → Google Calendar 자동 등록

일정 요청 메일을 Claude로 분석해 `rexgenshlee@gmail.com` 캘린더에 등록합니다.

## 설치
1. `rexgenshlee@gmail.com`으로 https://script.google.com → 새 프로젝트
2. `Code.gs` 붙여넣기, 설정(⚙) → "appsscript.json 표시" 체크 후 `appsscript.json` 내용 교체
3. 프로젝트 설정 → 스크립트 속성 추가
   - `ANTHROPIC_API_KEY` = (키)
   - `CALENDAR_ID` = `rexgenshlee@gmail.com` (선택)
4. `processInbox` 1회 실행 → 권한 승인
5. `installTrigger` 실행 → 5분마다 자동 실행

## 동작
- 최근 2일 받은편지함 중 일정 키워드 메일만 대상 (`cal-processed` 라벨로 중복 방지)
- 확신도 0.7 미만이면 `[확인필요]` 접두 + 주황색
- API 키는 코드에 넣지 말 것 (공개 저장소)
