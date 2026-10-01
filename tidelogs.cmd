@echo off
rem Runs tidelogs.ps1 from a Command Prompt or by double-click, passing any options through,
rem e.g.  tidelogs -Follow   or   tidelogs -Errors -Lines 20
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tidelogs.ps1" %*
if "%~1"=="" pause
