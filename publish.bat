@echo off
REM 더블클릭하면 사이트에 올라갑니다. 안내는 publish.py 가 합니다.
cd /d "%~dp0"
python publish.py
