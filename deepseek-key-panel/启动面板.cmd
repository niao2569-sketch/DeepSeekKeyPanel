@echo off
chcp 65001 >nul 2>nul
title DeepSeek Key Panel
setlocal
cd /d "%~dp0"

echo.
echo   DeepSeek Key Panel
echo   ------------------
echo.

set "PYEXE="
where py >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE (
  where python >nul 2>nul && set "PYEXE=python"
)

if not defined PYEXE (
  echo   [ERROR] Python not found on PATH.
  echo.
  echo   Use DeepSeekKeyPanel.exe instead - it runs without Python.
  echo   Or install Python 3.8+ from https://www.python.org/downloads/
  echo.
  pause
  exit /b 1
)

%PYEXE% run_panel.py %%

if errorlevel 1 (
  echo.
  echo   [ERROR] exited unexpectedly.
  pause
)

endlocal
