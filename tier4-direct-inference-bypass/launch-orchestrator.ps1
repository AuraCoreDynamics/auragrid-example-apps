# AuraGrid PowerShell Launcher – InferenceOrchestrator
# Launched by the grid's NativeProcessExecutor. Env vars AURAGRID_IPC_PORT and AURAGRID_IPC_TOKEN
# are injected by the grid and forwarded to the dotnet process.

$project = "C:\projects\auracore\app-examples\tier4-direct-inference-bypass\src\OrchestratorMas\OrchestratorMas.csproj"

Write-Host "[launch-orchestrator.ps1] Starting InferenceOrchestrator via dotnet run..."
dotnet run --project $project --no-build
