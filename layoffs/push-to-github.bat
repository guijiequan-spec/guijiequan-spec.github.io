@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Push layoffs dashboard to GitHub Pages

echo ============================================================
echo   China Layoffs Dashboard -^> GitHub Pages
echo ============================================================
echo.

set "TOKENFILE=..\.workbuddy\github_token.txt"

if exist "%TOKENFILE%" goto runpush

echo [Step 1] Token file not found.
echo          Paste your fine-grained PAT (starts with github_pat_)
echo          then press Enter. Input is NOT hidden.
echo.
set "TOKEN="
set /p TOKEN=
if "!TOKEN!"=="" goto fail
> "%TOKENFILE%" echo !TOKEN!
echo.
echo [OK] Saved to %TOKENFILE%
echo.

:runpush
echo [Step 2] Pushing...
echo.
python "scripts\push_github.py"
echo.
echo ------------------------------------------------------------
echo  Done. Check the messages above.
echo  Site: https://guijiequan-spec.github.io/layoffs/
echo ------------------------------------------------------------
echo.
pause
exit /b 0

:fail
echo.
echo [FAIL] No token entered. Aborted.
echo.
pause
exit /b 1
