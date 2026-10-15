@echo off
echo Stopping background Academic Paper PDF Renamer...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*rename_papers.py*--watch*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host 'Stopped watcher process ID:' $_.ProcessId }"
echo Done.
pause
