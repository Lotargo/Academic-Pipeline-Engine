@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\service-dev.ps1" %*
exit /b %ERRORLEVEL%
