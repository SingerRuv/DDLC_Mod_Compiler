@echo off
cd /d "%~dp0"
python "DDLCModCompiler.py"
if errorlevel 1 pause
