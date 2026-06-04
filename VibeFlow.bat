@echo off
REM Portable launcher — resolves paths relative to this file's location,
REM so it works wherever the repo is cloned. Expects a virtual environment
REM named "venv" in the repo root (see README).
cd /d "%~dp0src"
call "%~dp0venv\Scripts\activate.bat"
start /min python -m medasr
