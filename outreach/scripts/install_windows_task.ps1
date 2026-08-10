$ErrorActionPreference = 'Stop'
$OutreachRoot = Split-Path -Parent $PSScriptRoot
$Python = if ($env:ELIORA_OUTREACH_PYTHON) { $env:ELIORA_OUTREACH_PYTHON } else { Join-Path $OutreachRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path $Python)) { throw "Missing $Python. Create outreach/.venv and install outreach first." }
$Action = New-ScheduledTaskAction -Execute $Python -Argument '-m eliora_outreach run-if-due' -WorkingDirectory (Split-Path -Parent $OutreachRoot)
$AtLogon = New-ScheduledTaskTrigger -AtLogOn
$Hourly = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(5)) -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)
Register-ScheduledTask -TaskName 'EliOra-Outreach' -Action $Action -Trigger @($AtLogon, $Hourly) -Description 'EliOra local outreach due check' -Force | Out-Null
Write-Output 'Installed current-user EliOra-Outreach task.'
