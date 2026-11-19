@echo off
setlocal
cd /d "%~dp0"

py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul
if not errorlevel 1 goto use_py

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul
if not errorlevel 1 goto use_python

echo Python 3.8 or newer was not found.
echo Install Python from https://www.python.org/downloads/windows/
echo Then close this window and double-click start_windows.bat again.
pause
exit /b 1

:use_py
py -3 server.py --open %*
goto finished

:use_python
python server.py --open %*

:finished
set "viewer_exit=%errorlevel%"
if "%viewer_exit%"=="0" exit /b 0
echo.
echo The viewer stopped with exit code %viewer_exit%.
pause
exit /b %viewer_exit%
