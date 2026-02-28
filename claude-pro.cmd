@echo off
REM Switch to Claude Pro (personal: sv.shulha@gmail.com)
setx CLAUDE_CODE_USE_VERTEX "" >nul
setx ANTHROPIC_VERTEX_PROJECT_ID "" >nul
setx CLOUD_ML_REGION "" >nul
set CLAUDE_CODE_USE_VERTEX=
set ANTHROPIC_VERTEX_PROJECT_ID=
set CLOUD_ML_REGION=

REM Check if Claude auth credentials exist; if not, trigger login
if not exist "%USERPROFILE%\.claude\.credentials.json" (
    echo No Claude credentials found. Logging in...
    claude auth login
) else (
    echo Claude credentials already configured.
)

echo.
echo Switched to Claude Pro (personal)
echo Restart Claude Code for changes to take effect.
