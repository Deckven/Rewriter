@echo off
REM Switch to Vertex AI (work: stanislav.shulha@paysera.net)
setx CLAUDE_CODE_USE_VERTEX 1 >nul
setx ANTHROPIC_VERTEX_PROJECT_ID vertex-darbuotojams >nul
setx CLOUD_ML_REGION global >nul
set CLAUDE_CODE_USE_VERTEX=1
set ANTHROPIC_VERTEX_PROJECT_ID=vertex-darbuotojams
set CLOUD_ML_REGION=global

REM Check if gcloud ADC is set up; if not, trigger login
gcloud auth application-default print-access-token >nul 2>&1
if %errorlevel% neq 0 (
    echo No application-default credentials found. Logging in...
    gcloud auth application-default login --account=stanislav.shulha@paysera.net
) else (
    echo gcloud ADC already configured.
)

echo.
echo Switched to Vertex AI (vertex-darbuotojams / global)
echo Restart Claude Code for changes to take effect.
