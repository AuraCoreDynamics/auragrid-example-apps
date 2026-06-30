$manifestsDir = "C:\tmp\grid-smoke-test\wal\manifests"
if (!(Test-Path $manifestsDir)) { New-Item -ItemType Directory -Force -Path $manifestsDir | Out-Null }

function Publish-PythonApp {
    param($AppDir)
    
    $manifestPath = "C:\projects\auracore\app-examples\$AppDir\app.manifest.json"
    if (Test-Path $manifestPath) {
        $json = Get-Content $manifestPath | ConvertFrom-Json
        $appId = $json.AppId
        $version = $json.Version
        $dest = "$manifestsDir\$appId\$version"
        if (!(Test-Path $dest)) { New-Item -ItemType Directory -Force -Path $dest | Out-Null }
        Copy-Item $manifestPath "$dest\app.manifest.json"
        Write-Host "Published Python App: $appId v$version"
    }
}

function Publish-CSharpApp {
    param($AppId, $Name, $BinDir, $ExeName)

    $version = "1.0.0"
    $dest = "$manifestsDir\$AppId\$version"
    if (!(Test-Path $dest)) { New-Item -ItemType Directory -Force -Path $dest | Out-Null }

    # Create a wrapper ps1 script
    $ps1Path = "$dest\run.ps1"
    Set-Content -Path $ps1Path -Value "& '$BinDir\$ExeName'"

    # Create manifest
    $manifest = @{
        AppId = $AppId
        Name = $Name
        Version = $version
        Description = "Automated package for $Name"
        Services = @(
            @{
                MasId = "$AppId-worker"
                DisplayName = "$Name Worker"
                Mode = "CellSingleton"
                Runtime = "PowerShell"
                PowerShellConfig = @{
                    ScriptPath = $ps1Path
                    WorkingDirectory = $BinDir
                }
                Remoting = @{
                    EnableGrpc = $true
                    EnableOpenApi = $false
                }
                RestartPolicy = "OnFailure"
                MaxRestartAttempts = 3
            }
        )
    }

    $manifestJson = $manifest | ConvertTo-Json -Depth 5
    Set-Content -Path "$dest\app.manifest.json" -Value $manifestJson
    Write-Host "Published C# App: $AppId v$version"
}

# 1. Publish Python Apps
Publish-PythonApp "tier1-sovereign-beacon"
Publish-PythonApp "tier2-grid-gauntlet\provocateur"
Publish-PythonApp "tier2-grid-gauntlet\sentinel"
Publish-PythonApp "tier3-sovereign-ledger"
Publish-PythonApp "tier4-cognitive-beacon"
Publish-PythonApp "tier4-model-foundry"
Publish-PythonApp "tier5-entropy-engine"
Publish-PythonApp "tier5-signed-chat"

# 2. Publish C# Apps
Publish-CSharpApp "tier4-direct-inference-bypass" "Direct Inference Worker" "C:\projects\auracore\app-examples\tier4-direct-inference-bypass\src\WorkerMas\bin\Debug\net10.0" "WorkerMas.exe"
Publish-CSharpApp "tier4-telemetry-torrent" "Telemetry Torrent Worker" "C:\projects\auracore\app-examples\tier4-telemetry-torrent\src\TorrentWorker\bin\Debug\net10.0" "TorrentWorker.exe"

# 3. Publish Go App (Tier 6) using its AgpBuilder
Write-Host "Publishing Tier 6 App..."
Set-Location "C:\projects\auracore\app-examples\tier6-container-resource-glutton\AgpBuilder"
dotnet run
# AgpBuilder writes tier6-container-resource-glutton-1.0.0.agp to tier6-container-resource-glutton folder
# It also creates an unzipped manifest in its staging folder. We can just copy the staging manifest
$t6Staging = "C:\projects\auracore\app-examples\tier6-container-resource-glutton\AgpBuilder\staging\app.manifest.json"
if (Test-Path $t6Staging) {
    $t6Dest = "$manifestsDir\tier6-container-resource-glutton\1.0.0"
    if (!(Test-Path $t6Dest)) { New-Item -ItemType Directory -Force -Path $t6Dest | Out-Null }
    Copy-Item $t6Staging "$t6Dest\app.manifest.json"
    Write-Host "Published Tier 6 App: tier6-container-resource-glutton v1.0.0"
}
