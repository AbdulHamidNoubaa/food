@echo off
setlocal
chcp 65001 >nul
title Food Safety
set "ROOT=%~dp0"
set "APP=%ROOT%food_safety"
set "PY=%ROOT%venv\Scripts\python.exe"

if not exist "%PY%" (
  echo Python virtual environment was not found:
  echo %PY%
  pause
  exit /b 1
)

cd /d "%APP%"
"%PY%" -c "import socket;s=socket.socket();r=s.connect_ex(('127.0.0.1',8000));s.close();raise SystemExit(0 if r==0 else 1)"
if %errorlevel%==0 (
  start "" "http://127.0.0.1:8000/"
  exit /b 0
)

start "Food Safety Server" cmd /k cd /d "%APP%" ^& "%PY%" manage.py runserver 127.0.0.1:8000
ping 127.0.0.1 -n 5 >nul
start "" "http://127.0.0.1:8000/"
endlocal
