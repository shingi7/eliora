$ErrorActionPreference = 'Stop'
Unregister-ScheduledTask -TaskName 'EliOra-Outreach' -Confirm:$false -ErrorAction SilentlyContinue
Write-Output 'Removed current-user EliOra-Outreach task. Private data was preserved.'
