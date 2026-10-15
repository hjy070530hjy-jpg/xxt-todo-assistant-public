@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "dist\XXTTodoAssistant\XXTTodoAssistant.exe" (
 start "" "dist\XXTTodoAssistant\XXTTodoAssistant.exe"
 exit /b
)
if exist ".venv\Scripts\pythonw.exe" (
 start "" ".venv\Scripts\pythonw.exe" "main.py"
 exit /b
)
echo 请先运行 build.bat 安装依赖并打包。
pause
