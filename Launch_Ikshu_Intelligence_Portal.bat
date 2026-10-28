@echo off
title Ikshu Intelligence - Gangamai Sugar Mill Command Center
echo ====================================================================
echo        IKSHU INTELLIGENCE - GANGAMAI COMMAND PORTAL
echo ====================================================================
echo.
echo Starting local high-speed portal with Google Maps Radar and 38 Model Parameters...
cd /d "%~dp0site-editor"
start "" http://localhost:5173/portal
npm.cmd run dev
pause
