@echo off
title Retail Demand Forecasting & Inventory Planning - PyQt6 Desktop App
echo =====================================================================
echo  STARTING PYQT6 DESKTOP APPLICATION (UEL ML IN BUSINESS ANALYTICS)
echo =====================================================================
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" PyQt6_Du_bao_ban_le\app.py
) else (
    python PyQt6_Du_bao_ban_le\app.py
)
if errorlevel 1 pause
