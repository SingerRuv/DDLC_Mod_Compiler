@echo off
cd /d "%~dp0"
python "DDLCCompiler.py"
if errorlevel 1 pause
