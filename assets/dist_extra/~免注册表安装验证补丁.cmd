@echo off
chcp 65001>nul
setlocal enabledelayedexpansion
title 游戏环境注册工具

:: --- 权限检查与自动提权 ---
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] 正在请求管理员权限以写入注册表...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: --- 设置工作目录 ---
pushd "%~dp0"
set "APP_EXE=%CD%\G0WIN.EXE"
set "APP_PATH=%CD%"

echo ============================================
echo   正在初始化游戏运行环境...
echo ============================================

:: --- 写入 App Paths (解决系统找不到 EXE 的问题) ---
echo [+] 正在配置 App Paths...
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\G0WIN.EXE" /f /ve /t REG_SZ /d "!APP_EXE!" >nul
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\G0WIN.EXE" /f /v "Path" /t REG_SZ /d "!APP_PATH!" >nul

:: --- 写入游戏特定注册表 ---
:: 注意：WOW6432Node 是给 32 位程序在 64 位系统上用的
echo [+] 正在写入游戏版本信息...
reg add "HKLM\SOFTWARE\WOW6432Node\GROOMING\G0WIN\1.0" /f /v "VER" /t REG_SZ /d "1.00" >nul

if %errorLevel% equ 0 (
    echo.
    echo [成功] 环境修复完成！
) else (
    echo.
    echo [错误] 注册表写入失败，请检查杀毒软件是否拦截。
)

echo ============================================
pause