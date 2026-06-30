# AuraGrid PowerShell Launcher – InferenceWorker
# Launched by the grid's NativeProcessExecutor. Env vars AURAGRID_IPC_PORT and AURAGRID_IPC_TOKEN
# are injected by the grid and forwarded to the dotnet process.

$project = "C:\projects\auracore\app-examples\tier4-direct-inference-bypass\src\WorkerMas\WorkerMas.csproj"

Write-Host "[launch-worker.ps1] Starting InferenceWorker via dotnet run..."
dotnet run --project $project --no-build
