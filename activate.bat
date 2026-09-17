@echo off
if exist "%~dp0bellion_music_bot\Scripts\activate.bat" (
    call "%~dp0bellion_music_bot\Scripts\activate.bat"
    goto :eof
)
if exist "%~dp0.venv\Scripts\activate.bat" (
    call "%~dp0.venv\Scripts\activate.bat"
    goto :eof
)
if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
    goto :eof
)
if exist "%~dp0env\Scripts\activate.bat" (
    call "%~dp0env\Scripts\activate.bat"
    goto :eof
)
echo [WARNING] No virtual environment found.