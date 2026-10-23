# Gmail 일정 메일 -> Google Calendar 등록 (Claude Code 구독 사용량 사용)
$dir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$prompt = Get-Content "$dir\prompt.txt" -Raw -Encoding UTF8
$log    = "$dir\sync.log"

"=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Out-File $log -Append -Encoding UTF8
# mcp__<서버이름> 접두어로 커넥터 도구 허용. 이름은 `claude mcp list`로 확인해 필요시 수정
claude -p $prompt `
  --allowedTools "mcp__claude_ai_Gmail" "mcp__claude_ai_Google_Calendar" `
  2>&1 | Out-File $log -Append -Encoding UTF8
