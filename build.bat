@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" python -m venv .venv
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m PyInstaller --noconfirm XXTTodoAssistant.spec
if errorlevel 1 goto fail
echo 完成，请打开 dist\XXTTodoAssistant\XXTTodoAssistant.exe
pause
exit /b 0
:fail
echo 构建失败，请保留上方错误信息。
pause
exit /b 1
