@echo off
title Research Rabbit Launcher 🐰
echo ============================================================
echo   Research Rabbit - Local AI Web Research Assistant 🐰
echo ============================================================
echo.
echo Starting local FastAPI backend server...
echo.
echo Opening default web browser to http://127.0.0.1:8000...
echo.
echo Press Ctrl+C in this terminal window to shut down the server.
echo.

:: Wait a brief moment for startup and open the browser
start "" "http://127.0.0.1:8000"

:: Start the Python backend server
".venv\Scripts\python.exe" -m research_rabbit.gui

pause
