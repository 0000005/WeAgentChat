@echo off
setlocal
echo =======================================================
echo   Deploying WeAgentChat Website to Cloudflare Pages
echo =======================================================

:: 切换到脚本所在目录的上级目录下的 website 文件夹
cd /d "%~dp0..\website"

:: 执行部署命令
:: --project-name weagentchat: 指定项目名称
:: --commit-dirty=true: 允许在有未提交代码的情况下部署（跳过 git 检查警告）
call npx -y wrangler pages deploy . --project-name weagentchat --branch main --commit-dirty=true

echo.
if %errorlevel% equ 0 (
    echo [SUCCESS] Deployment completed successfully!
    echo Visit your site at: https://weagentchat.pages.dev
) else (
    echo [ERROR] Deployment failed with error code %errorlevel%.
)

echo.
pause
