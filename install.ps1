<#
  Claude Compass - friendly Windows installer.

  Run it one of these ways:
    - Right-click this file -> "Run with PowerShell", OR
    - In a terminal:  powershell -ExecutionPolicy Bypass -File .\install.ps1

  No admin rights needed - it installs just for you.
#>

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Say($text, $color = "Gray") { Write-Host "  $text" -ForegroundColor $color }

Write-Host ""
Say "Claude Compass - let's get you set up" "Cyan"
Write-Host ""

$py = $null
foreach ($cand in @("python", "py")) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) { $py = $cand; break }
}
if (-not $py) {
    Say "I couldn't find Python on this machine." "Red"
    Say "Grab it from https://www.python.org/downloads/ (tick 'Add Python to PATH')," "Red"
    Say "then run me again. I'll be right here." "Red"
    exit 1
}
Say "Found Python. Installing Compass (just for you, no admin needed)..."

& $py -m pip install --user . | Out-Null
if ($LASTEXITCODE -ne 0) {
    Say "The install hit a snag - the pip output above should say why." "Red"
    exit 1
}
Say "Installed cleanly." "Green"

& $py -m claude_compass init | Out-Null

Write-Host ""
Say "All set - your compass is calibrating. A few friendly next steps:" "Green"
Write-Host ""
Say "  1. Answer a question:    $py -m claude_compass ask"
Say "  2. Share your profile:   $py -m claude_compass sync"
Say "  3. See the dashboard:    $py -m claude_compass dashboard"
Say "  4. Make it automatic:    $py -m claude_compass install-hook"
Write-Host ""
Say "Tip: from this folder you can also just type  .\compass ask  etc." "DarkGray"
Write-Host ""
