# 한 번만 실행: 10분마다 run.ps1 실행하는 작업 스케줄러 등록
$script = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'run.ps1'
schtasks /Create /TN "ClaudeCalendarSync" /SC MINUTE /MO 10 /F `
  /TR "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
