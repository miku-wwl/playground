$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryDirectory = Split-Path -Parent $PSScriptRoot
Push-Location $repositoryDirectory
$archiveProcess = $null
$initialConsumerProcess = $null
$publisherProcess = $null
$recoveryConsumerProcess = $null
$runDirectory = $null

function Start-Phase3Process
{
    param(
        [Parameter(Mandatory = $true)][string]$MainClass,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $stdoutPath = Join-Path $runDirectory "$Name.stdout.log"
    $stderrPath = Join-Path $runDirectory "$Name.stderr.log"
    $argumentText = '--add-opens=java.base/jdk.internal.misc=ALL-UNNAMED -cp "' +
        $script:classPath + '" ' + $MainClass
    foreach ($argument in $Arguments)
    {
        $argumentText += ' "' + $argument.Replace('"', '\"') + '"'
    }

    Start-Process -FilePath $script:javaPath `
        -ArgumentList $argumentText `
        -PassThru `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath
}

function Wait-ForMarker
{
    param(
        [Parameter(Mandatory = $true)][string]$Marker,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds,
        [System.Diagnostics.Process]$MonitorProcess
    )

    $markerPath = Join-Path $runDirectory $Marker
    $deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTimeOffset]::UtcNow -lt $deadline)
    {
        if (Test-Path -LiteralPath $markerPath)
        {
            return
        }
        if ($null -ne $MonitorProcess)
        {
            $MonitorProcess.Refresh()
            if ($MonitorProcess.HasExited)
            {
                throw "Process $($MonitorProcess.Id) exited before writing $Marker (exit=$($MonitorProcess.ExitCode))."
            }
        }
        Start-Sleep -Milliseconds 100
    }
    throw "Timed out waiting for marker $Marker."
}

function Wait-ForProcess
{
    param(
        [Parameter(Mandatory = $true)][System.Diagnostics.Process]$Process,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds
    )

    if (-not $Process.WaitForExit($TimeoutSeconds * 1000))
    {
        throw "Process $($Process.Id) did not exit within $TimeoutSeconds seconds."
    }
    if ($Process.ExitCode -ne 0)
    {
        throw "Process $($Process.Id) failed with exit code $($Process.ExitCode)."
    }
}

function Stop-Phase3Process
{
    param([System.Diagnostics.Process]$Process)
    if ($null -ne $Process)
    {
        $Process.Refresh()
        if (-not $Process.HasExited)
        {
            $Process.Kill()
            [void]$Process.WaitForExit(5000)
        }
    }
}

try
{
    mvn test
    if ($LASTEXITCODE -ne 0)
    {
        throw "mvn test failed with exit code $LASTEXITCODE."
    }

    mvn -q dependency:build-classpath '-Dmdep.outputFile=target/phase3-classpath.txt'
    if ($LASTEXITCODE -ne 0)
    {
        throw "Could not build the Java dependency classpath (exit=$LASTEXITCODE)."
    }

    $javaCommand = Get-Command java -ErrorAction Stop
    $script:javaPath = $javaCommand.Source
    $dependencies = (Get-Content -Raw -LiteralPath 'target/phase3-classpath.txt').Trim()
    $script:classPath = (Join-Path $repositoryDirectory 'target/classes') + ';' + $dependencies

    $runRoot = Join-Path $repositoryDirectory 'target/aeron-phase3-runs'
    New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
    $runName = 'run-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
    $runDirectory = Join-Path $runRoot $runName
    New-Item -ItemType Directory -Path $runDirectory | Out-Null
    Write-Host "RUN_DIRECTORY=$runDirectory"

    $archiveProcess = Start-Phase3Process `
        -MainClass 'dev.playground.replaylab.phase3.Phase3ArchiveProcess' `
        -Arguments @($runDirectory) `
        -Name 'archive'
    Wait-ForMarker -Marker 'archive.ready' -TimeoutSeconds 20 -MonitorProcess $archiveProcess

    $initialConsumerProcess = Start-Phase3Process `
        -MainClass 'dev.playground.replaylab.phase3.Phase3ConsumerProcess' `
        -Arguments @($runDirectory, 'initial') `
        -Name 'consumer-initial'
    Wait-ForMarker -Marker 'consumer.initial.ready' -TimeoutSeconds 20 -MonitorProcess $initialConsumerProcess

    $publisherProcess = Start-Phase3Process `
        -MainClass 'dev.playground.replaylab.phase3.Phase3PublisherProcess' `
        -Arguments @($runDirectory) `
        -Name 'publisher'
    Wait-ForMarker -Marker 'consumer.initial.done' -TimeoutSeconds 30 -MonitorProcess $initialConsumerProcess
    $initialConsumerProcess.Refresh()
    if ($initialConsumerProcess.HasExited)
    {
        throw 'Initial consumer exited before the harness could simulate its crash.'
    }
    $initialConsumerProcess.Kill()
    if (-not $initialConsumerProcess.WaitForExit(5000))
    {
        throw "Initial consumer process $($initialConsumerProcess.Id) did not stop after the crash simulation."
    }
    Write-Host "INITIAL_CONSUMER_CRASH_SIMULATED pid=$($initialConsumerProcess.Id)"
    Wait-ForMarker -Marker 'publisher.replay-boundary.ready' -TimeoutSeconds 30 -MonitorProcess $publisherProcess

    $recoveryConsumerProcess = Start-Phase3Process `
        -MainClass 'dev.playground.replaylab.phase3.Phase3ConsumerProcess' `
        -Arguments @($runDirectory, 'recover') `
        -Name 'consumer-recovery'
    Wait-ForMarker -Marker 'consumer.recovery.done' -TimeoutSeconds 40 -MonitorProcess $recoveryConsumerProcess
    Wait-ForProcess -Process $publisherProcess -TimeoutSeconds 10
    Wait-ForProcess -Process $recoveryConsumerProcess -TimeoutSeconds 10

    Set-Content -LiteralPath (Join-Path $runDirectory 'archive.stop') -Value 'stop' -NoNewline
    Wait-ForProcess -Process $archiveProcess -TimeoutSeconds 15
    $archiveProcess = $null

    Write-Host 'PHASE3_PROCESS_RESULTS_BEGIN'
    Get-Content -Encoding UTF8 -LiteralPath (Join-Path $runDirectory 'archive.stdout.log')
    Get-Content -Encoding UTF8 -LiteralPath (Join-Path $runDirectory 'publisher.stdout.log')
    Get-Content -Encoding UTF8 -LiteralPath (Join-Path $runDirectory 'consumer-initial.stdout.log')
    Get-Content -Encoding UTF8 -LiteralPath (Join-Path $runDirectory 'consumer-recovery.stdout.log')
    Write-Host 'PHASE3_PROCESS_RESULTS_END'
    Write-Host 'PHASE3_RECOVERY=PASS'
}
finally
{
    if ($null -ne $runDirectory -and (Test-Path -LiteralPath $runDirectory))
    {
        $stopMarker = Join-Path $runDirectory 'archive.stop'
        if ($null -ne $archiveProcess -and -not $archiveProcess.HasExited -and
            -not (Test-Path -LiteralPath $stopMarker))
        {
            Set-Content -LiteralPath $stopMarker -Value 'stop' -NoNewline
            [void]$archiveProcess.WaitForExit(5000)
        }
    }
    Stop-Phase3Process -Process $recoveryConsumerProcess
    Stop-Phase3Process -Process $publisherProcess
    Stop-Phase3Process -Process $initialConsumerProcess
    Stop-Phase3Process -Process $archiveProcess
    Pop-Location
}
