@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if exist "runtime\python.exe" (
  set "PYTHONIOENCODING=utf-8"
  "%~dp0runtime\python.exe" tools\diagnose.py
) else (
  where python >nul 2>nul && (python tools\diagnose.py) || (
    echo [ERROR] No Python available for the self-check.
    pause
  )
)
