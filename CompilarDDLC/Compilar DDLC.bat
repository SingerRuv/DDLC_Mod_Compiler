@echo off
cd /d "%~dp0"
python "CompilarDDLC.py"
if errorlevel 1 pause
