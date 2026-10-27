# AuraGrid PowerShell Launcher – TorrentWorker
# Launched by the grid's NativeProcessExecutor. Env vars AURAGRID_IPC_PORT and AURAGRID_IPC_TOKEN
# are injected by the grid and forwarded to the dotnet process.

$project = "$PSScriptRoot\src\TorrentWorker\TorrentWorker.csproj"

Write-Host "[launch-worker.ps1] Starting TorrentWorker via dotnet run..."
dotnet run --project $project --no-build
