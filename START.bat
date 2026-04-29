@echo off
:: Windows launcher — double-click this to start the bot dashboard
cd /d "%~dp0"
call venv\Scripts\activate
start "" http://localhost:8765
python server.py
