@echo off
rem Renders the next video and schedules it on YouTube. Run by Windows Task Scheduler.
cd /d "%~dp0.."
if not exist logs mkdir logs
echo [%date% %time%] start >> logs\daily.log
.venv\Scripts\python -m autoshort daily --count 1 >> logs\daily.log 2>&1
