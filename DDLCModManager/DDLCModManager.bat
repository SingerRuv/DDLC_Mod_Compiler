@echo off
cd /d "%~dp0"
python "DDLCModManager.py"
if errorlevel 1 pause
