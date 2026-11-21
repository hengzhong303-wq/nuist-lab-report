@echo off
setlocal
chcp 65001 >nul
title NUIST Lab Report Studio
cd /d "%~dp0"

rem ---------- 1. Locate Python: bundled runtime first ----------
set "PY="
set "PYQ="
if exist "runtime\python.exe" (
  set "PY=%~dp0runtime\python.exe"
  set "PYQ=1"
)
if not defined PY (
  where py >nul 2>nul && set "PY=py -3"
)
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo [ERROR] Python runtime not found.
  echo   If you double-clicked start.bat INSIDE the zip file, please
  echo   extract the whole zip to a folder first, then run start.bat there.
  echo   Or install Python 3.9+ ^(tick "Add to PATH"^) and retry.
  echo   See the README ^(使用说明.md^) for details.
  pause
  exit /b 1
)
if defined PYQ (
  set "PYCMD="%PY%""
) else (
  set "PYCMD=%PY%"
)

set "PYTHONIOENCODING=utf-8"

rem ---------- 2. Runtime integrity check ----------
%PYCMD% -c "import sys" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] The bundled Python cannot run.
  echo   Possible reasons: blocked by antivirus, or incomplete extraction.
  echo   1^) Add this folder to your antivirus whitelist and retry
  echo   2^) Re-extract the zip completely ^(the runtime folder must exist^)
  pause
  exit /b 1
)

rem ---------- 3. Dependencies (bundled runtime ships them) ----------
%PYCMD% -c "import docx, PIL" >nul 2>nul
if errorlevel 1 (
  echo [First run] Installing dependencies python-docx / Pillow ...
  %PYCMD% -m pip install -r requirements.txt -q
)

echo ==============================================
echo   NUIST Lab Report Studio is starting...
echo   The browser will open automatically.
echo   Keep this window open while using the app;
echo   close it to stop the server.
echo ==============================================
set PORT=8765
%PYCMD% server.py
echo.
echo [Server stopped] If red errors appeared above, please screenshot them.
echo Run SelfCheck.bat to verify your environment.
pause
