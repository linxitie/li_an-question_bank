@echo off
chcp 65001 >nul
echo ==========================================
echo     砺安题库 - 三端系统启动
echo ==========================================
echo.

echo [1/3] 构建前端...
cd /d %~dp0
call npx vite build 2>nul
if %errorlevel% neq 0 (
    echo 构建失败，请检查错误信息
    pause
    exit /b 1
)
echo 前端构建完成

echo.
echo [2/3] 启动后端服务 (端口 8000)...
start "砺安题库-后端" cmd /c "cd /d %~dp0backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo.
echo 等待服务启动...
timeout /t 5 /nobreak >nul

echo.
echo ==========================================
echo     系统已启动！
echo.
echo     请在浏览器打开：http://localhost:8000
echo ==========================================
echo.
echo 测试账号:
echo   教师端: ycc5678 / ycc5678
echo   管理员: cbrycc / cbrycc
echo   学生端: 注册新账号
echo.
echo 前后端统一端口 8000，无需启动 Vite。
echo ==========================================
pause
