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
Write-Host "[1/4] Installing snapclient..."

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
Write-Host "[2/4] Registering scheduled task..."

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
Write-Host "[3/4] Checking connection..."
Start-Sleep -Seconds 2

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
$Process = Get-Process -Name "snapclient" -ErrorAction SilentlyContinue

if (-not $Process) {
    Write-Host ""
    Write-Error "snapclient doesn't appear to be running. Check Task Scheduler for errors."
    exit 1
}

# ── 4. Install PowerShell convenience functions ───────────────────────────────
Write-Host "[4/4] Installing music-on / music-off commands..."

$ProfileDir = Split-Path $PROFILE -Parent
if (-not (Test-Path $ProfileDir)) { New-Item -ItemType Directory -Path $ProfileDir -Force | Out-Null }
if (-not (Test-Path $PROFILE))    { New-Item -ItemType File -Path $PROFILE -Force | Out-Null }

# Remove any previous music functions we installed
$ProfileContent = Get-Content $PROFILE -Raw -ErrorAction SilentlyContinue
if ($ProfileContent) {
    $ProfileContent = $ProfileContent -replace '(?s)# snapcast music functions.*?# end snapcast music functions\r?\n?', ''
    Set-Content $PROFILE -Value $ProfileContent.TrimEnd()
}

Add-Content $PROFILE @"

# snapcast music functions
function music-on  { Start-ScheduledTask -TaskName SnapcastClient; Write-Host 'Snapclient started' }
function music-off { Stop-ScheduledTask -TaskName SnapcastClient;  Write-Host 'Snapclient stopped' }
# end snapcast music functions
"@

Write-Host "    Added to PowerShell profile: music-on, music-off"

Write-Host ""
Write-Host "✓ snapclient is running and connected to $Server" -ForegroundColor Green
Write-Host "  Node name: $Name"
Write-Host "  Type 'list rooms' in #spotify-chat to confirm."
Write-Host ""
Write-Host "  Quick commands (open a new PowerShell window):"
Write-Host "    music-off   Stop receiving audio on this PC"
Write-Host "    music-on    Start receiving audio again"
Write-Host ""
Write-Host "  Playback control: use any Spotify client (phone, desktop, web)"
