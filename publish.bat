@echo off
REM Double-click to publish. All messages come from publish.py (UTF-8 safe).
cd /d "%~dp0"
python publish.py
