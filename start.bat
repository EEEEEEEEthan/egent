@echo off
cd /d "%~dp0"
python -m pip install -e ".[dev]"
if errorlevel 1 exit /b 1
python examples/example_agent.py
