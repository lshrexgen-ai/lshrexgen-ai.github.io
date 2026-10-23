# Gmail → Calendar 자동등록 (로컬 Claude Code)

API 키 없이 Claude Code 구독 사용량으로 10분마다 실행됩니다. PC가 켜져 있어야 합니다.

## 준비
1. claude.ai 설정 → 커넥터에서 Gmail, Google Calendar 연결 (rexgenshlee@gmail.com 계정)
2. `claude mcp list`로 커넥터 이름 확인 → `run.ps1`의 `--allowedTools` 이름과 다르면 수정
3. 수동 테스트: `powershell -File run.ps1` 후 `sync.log` 확인

## 등록 / 해제
- 등록: `powershell -ExecutionPolicy Bypass -File install.ps1`
- 해제: `schtasks /Delete /TN ClaudeCalendarSync /F`
