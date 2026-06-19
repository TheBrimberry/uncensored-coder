# Registers the Chrome Native Messaging host so the extension's
# "Start server" button can launch serve.py. Run via install_server_button.bat.

$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$hostName = "com.omni.trading.launcher"
$extId = "knaemjhcpncdliiclcpgcecpicnkgmdi"

# 1. Locate Python.
$py = $null
foreach ($cand in @("python", "py")) {
  $cmd = Get-Command $cand -ErrorAction SilentlyContinue
  if ($cmd) { $py = $cmd.Source; break }
}
if (-not $py) {
  Write-Host "ERROR: Python not found on PATH. Install Python and try again." -ForegroundColor Red
  exit 1
}
Write-Host "Using Python: $py"

# 2. Verify the agent files are here.
if (-not (Test-Path "$dir\serve.py")) {
  Write-Host "ERROR: serve.py not found in $dir. Run this from your agent folder." -ForegroundColor Red
  exit 1
}
if (-not (Test-Path "$dir\native_host.py")) {
  Write-Host "ERROR: native_host.py not found in $dir." -ForegroundColor Red
  exit 1
}

# 3. Write the launcher batch that Chrome will call (binary stdio passthrough).
$batPath = "$dir\native_host.bat"
$batContent = "@echo off`r`n`"$py`" `"$dir\native_host.py`" %*`r`n"
Set-Content -Path $batPath -Value $batContent -Encoding ASCII
Write-Host "Wrote launcher: $batPath"

# 4. Write the native messaging host manifest.
$manifest = [ordered]@{
  name           = $hostName
  description    = "Omniscient Trading Agent server launcher"
  path           = $batPath
  type           = "stdio"
  allowed_origins = @("chrome-extension://$extId/")
}
$manifestPath = "$dir\$hostName.json"
$manifest | ConvertTo-Json -Depth 5 | Set-Content -Path $manifestPath -Encoding UTF8
Write-Host "Wrote host manifest: $manifestPath"

# 5. Register the host for Chrome AND Edge (current user, no admin needed).
$targets = @(
  "HKCU:\Software\Google\Chrome\NativeMessagingHosts\$hostName",
  "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\$hostName"
)
foreach ($key in $targets) {
  New-Item -Path $key -Force | Out-Null
  Set-ItemProperty -Path $key -Name "(default)" -Value $manifestPath
  Write-Host "Registered: $key"
}

Write-Host ""
Write-Host "SUCCESS. Now reload the extension in chrome://extensions and click" -ForegroundColor Green
Write-Host "the green 'Start server' button in the extension's Settings tab." -ForegroundColor Green
