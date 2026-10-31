@echo off
rem One-click dev restart (bypass execution policy for this process only)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev-restart.ps1" %*
