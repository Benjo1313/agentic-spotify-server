# setup-windows-node.ps1 — Install and configure snapclient on a Windows node
#
# Usage (run in PowerShell as Administrator):
#   irm https://raw.githubusercontent.com/Benjo1313/agentic-spotify-server/main/scripts/setup-windows-node.ps1 | iex
#   OR after cloning:
#   .\scripts\setup-windows-node.ps1 -Server 192.168.1.10 -Name "office"
#
# Requirements: winget (included in Windows 10 1709+ / Windows 11)

param(
    [Parameter(Mandatory=$true)]
    [string]$Server,

    [string]$Name = $env:COMPUTERNAME,

    [switch]$Help
)

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path
    exit 0
}

Write-Host "=== Snapcast Node Setup (Windows) ===" -ForegroundColor Cyan
Write-Host "Server:    $Server"
Write-Host "Node name: $Name"
Write-Host ""

# ── 1. Install snapclient via winget ────────────────────────────────────────
Write-Host "[1/3] Installing snapclient..."

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Error "winget is not available. Install the App Installer from the Microsoft Store."
    exit 1
}

winget install --id badaix.Snapcast --source winget --silent --accept-package-agreements --accept-source-agreements

# Locate the installed binary
$SnapclientPath = Join-Path $env:ProgramFiles "Snapcast\snapclient.exe"
if (-not (Test-Path $SnapclientPath)) {
    # Fallback: search common locations
    $SnapclientPath = Get-ChildItem "C:\Program Files*" -Filter "snapclient.exe" -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}

if (-not $SnapclientPath) {
    Write-Error "snapclient.exe not found after install. Check winget output above."
    exit 1
}

Write-Host "    Found: $SnapclientPath"

# ── 2. Create a Windows Task Scheduler task for auto-start ──────────────────
Write-Host "[2/3] Registering scheduled task..."

$TaskName = "SnapcastClient"
$Action   = New-ScheduledTaskAction -Execute $SnapclientPath `
                -Argument "--host $Server --hostID $Name"
$Trigger  = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) `
                -ExecutionTimeLimit ([TimeSpan]::Zero)
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Limited

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
    -Settings $Settings -Principal $Principal -Force | Out-Null

# Start it immediately
Start-ScheduledTask -TaskName $TaskName

# ── 3. Verify ────────────────────────────────────────────────────────────────
Write-Host "[3/3] Checking connection..."
Start-Sleep -Seconds 2

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
$Process = Get-Process -Name "snapclient" -ErrorAction SilentlyContinue

if ($Process) {
    Write-Host ""
    Write-Host "✓ snapclient is running and connected to $Server" -ForegroundColor Green
    Write-Host "  Node name: $Name"
    Write-Host "  Type 'list rooms' in #spotify-chat to confirm."
    Write-Host ""
    Write-Host "  To stop:    Stop-ScheduledTask -TaskName SnapcastClient"
    Write-Host "  To remove:  Unregister-ScheduledTask -TaskName SnapcastClient"
} else {
    Write-Host ""
    Write-Error "snapclient doesn't appear to be running. Check Task Scheduler for errors."
    exit 1
}
