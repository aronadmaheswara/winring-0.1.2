@echo off
REM Klik dua kali file ini. Butuh Python 3.10+ (python.org, centang "Add to PATH").
cd /d "%~dp0"
python -m venv .venv || goto :err
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip PySide6 pyinstaller || goto :err
python -m PyInstaller --noconsole --onefile --name WinRing winring.pyw || goto :err
echo.
echo Selesai! File: %~dp0dist\WinRing.exe
pause
exit /b 0
:err
echo Gagal. Pastikan Python terpasang dan internet aktif.
pause
