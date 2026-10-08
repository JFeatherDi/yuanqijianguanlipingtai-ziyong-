<#
  Components Inventory System - Windows one-click launcher (invoked by the .bat next to it)

  Double-click the .bat in this folder; this script then:
    find Python -> create venv -> install deps -> init DB -> start service -> open browser

  Note: all messages are ASCII on purpose. Windows PowerShell 5.1 reads .ps1 files
  without a BOM as ANSI/GBK, which would corrupt Chinese text and break parsing.

  Parameters:
    -Port 5000     listen port (default 5000, or env APP_PORT)
    -NoBrowser     do not open the browser
    -Reinstall     reinstall dependencies
  Environment variables:
    APP_PASSWORD   admin password (default swust350351 - change it!)
    APP_USERNAME   admin account (default IOTAT)
    APP_HOST       bind address (default 0.0.0.0 = LAN reachable)
    APP_PYTHON     full path to python.exe (optional)
#>
[CmdletBinding()]
param(
  [int]$Port = 0,
  [switch]$NoBrowser,
  [switch]$Reinstall,
  [switch]$NonInteractive
)

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$Root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv    = Join-Path $Root 'venv'
$VenvPy  = Join-Path $Venv 'Scripts\python.exe'
$LogDir  = Join-Path $Root 'logs'
$LogFile = Join-Path $LogDir 'app.log'
$Req     = Join-Path $Root 'backend\requirements.txt'
$PyLibs  = Join-Path $Root '.pylibs'
$Host2   = if ($env:APP_HOST) { $env:APP_HOST } else { '0.0.0.0' }
$Port2   = if ($Port -gt 0) { $Port } elseif ($env:APP_PORT) { [int]$env:APP_PORT } else { 5000 }
# Mirror first: lab networks in China reach it far faster than pypi.org.
# Override with APP_PIP_INDEX (company mirror, or a local wheelhouse).
$PipIndex = if ($env:APP_PIP_INDEX) { $env:APP_PIP_INDEX } else { 'https://pypi.tuna.tsinghua.edu.cn/simple' }
# Short timeout + no retries: an unreachable mirror must fail in seconds,
# not hang the window forever.
$PipArgs = @('--disable-pip-version-check', '--quiet', '--timeout', '15', '--retries', '1', '--index-url', $PipIndex)
# Drop wheel files into a "wheels" folder next to this script for offline installs:
#   pip download -r backend/requirements.txt -d wheels
$WheelDir = Join-Path $Root 'wheels'
if (Test-Path -LiteralPath $WheelDir) { $PipArgs += @('--find-links', $WheelDir) }

function Say([string]$m)     { Write-Host $m }
function Ok([string]$m)      { Write-Host "  [OK] $m" -ForegroundColor Green }
function Warn2([string]$m)   { Write-Host "  [!] $m" -ForegroundColor Yellow }
function Fail([string]$m)    { Write-Host "  [X] $m" -ForegroundColor Red }
function Step([string]$m)    { Write-Host "`n$m" -ForegroundColor Cyan }
function Pause-Exit([int]$c) {
  if ($NonInteractive) { exit $c }
  [void](Read-Host 'Press Enter to exit')
  exit $c
}

function Ask([string]$prompt) {
  # Non-interactive runs must never block on input
  if ($NonInteractive) { return '' }
  return (Read-Host $prompt)
}

function Find-Python {
  $list = @()
  if ($env:APP_PYTHON) { $list += $env:APP_PYTHON }
  foreach ($n in 'python', 'python3') {
    $c = Get-Command $n -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c) { $list += $c.Source }
  }
  $c = Get-Command py -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($c) { $list += $c.Source }
  $list += (Join-Path $env:USERPROFILE '.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe')

  $seen = @{}
  foreach ($p in $list) {
    if (-not $p -or $seen.ContainsKey($p)) { continue }
    $seen[$p] = $true
    if (Test-Path -LiteralPath $p) { return $p }
    $c = Get-Command $p -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c) { return $c.Source }
  }
  return $null
}

function Test-VenvPy([string]$Py) {
  # A venv folder existing does not mean it is usable (may be half-built, no pip).
  & $Py -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" 2>$null
  if ($LASTEXITCODE -ne 0) { return $false }
  & $Py -m pip --version *> $null
  return ($LASTEXITCODE -eq 0)
}

function Enable-PyLibs {
  # Dependencies installed by the fallback live in the project, not in the venv.
  if (Test-Path -LiteralPath $PyLibs) {
    $env:PYTHONPATH = if ($env:PYTHONPATH) { "$PyLibs;$env:PYTHONPATH" } else { $PyLibs }
  }
}

function Missing-Deps([string]$Py) {
  # Returns a comma separated list of import names the given interpreter cannot
  # import, or $null when everything is available. Distinguishes "packages
  # missing" from "python itself is broken".
  $script:missingOut = ''
  & $Py -c "import importlib.util as u; print(','.join([n for n in ('flask','waitress','openpyxl') if u.find_spec(n) is None]))" 2>&1 |
    ForEach-Object { $script:missingOut = "$_" }
  if ($LASTEXITCODE -ne 0) { return 'interpreter error' }
  $res = "$script:missingOut".Trim()
  if ($res) { return $res }
  return $null
}

function Find-PipPython([string]$Preferred) {
  # Return the first interpreter that can actually run pip. On locked-down hosts
  # `python -m venv` can succeed yet leave the venv without pip (ensurepip cannot
  # unpack), so we must be able to borrow the base interpreter's pip.
  foreach ($cand in @($Preferred, $Py)) {
    if (-not $cand -or -not (Test-Path -LiteralPath $cand)) { continue }
    & $cand -m pip --version 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { return $cand }
  }
  return $null
}

function Test-IndexReachable {
  # Probe the package index before handing control to pip: pip can sit for a long
  # time on an unreachable TLS endpoint, which looks like a frozen window.
  if (Test-Path -LiteralPath $WheelDir) { return $true }
  try { $hostName = ([uri]$PipIndex).Host } catch { return $true }
  if (-not $hostName) { return $true }
  try {
    return (Test-NetConnection -ComputerName $hostName -Port 443 -InformationLevel Quiet -WarningAction SilentlyContinue)
  } catch { return $true }
}

function Install-Deps([string]$Preferred) {
  $pipPy = Find-PipPython $Preferred
  if (-not $pipPy) {
    Fail 'No usable pip found (neither in the venv nor in the base Python).'
    return $false
  }
  if (-not (Test-IndexReachable)) {
    Fail "Package index is unreachable: $PipIndex"
    Say '    Options:'
    Say '      1) Check the network / proxy, then run this launcher again'
    Say '      2) Use another mirror:  set APP_PIP_INDEX=https://mirrors.aliyun.com/pypi/simple'
    Say '      3) Offline: on a machine WITH internet run'
    Say '           pip download -r backend\requirements.txt -d wheels'
    Say '         copy the wheels folder next to this launcher, then run it again'
    return $false
  }
  & $pipPy -m pip install @PipArgs -r $Req 2>&1 |
    ForEach-Object { Write-Host "    $_" }
  if ($LASTEXITCODE -eq 0) { return $true }

  # Fallback: install into a project-local folder and load it with PYTHONPATH.
  # Needed when the system temp dir is not writable (pip fails while unpacking).
  Warn2 'pip install failed. Falling back to project-local dependencies (.pylibs)...'
  if (Test-Path -LiteralPath $PyLibs) {
    Remove-Item -LiteralPath $PyLibs -Recurse -Force -ErrorAction SilentlyContinue
  }
  New-Item -ItemType Directory -Path $PyLibs -Force | Out-Null
  & $pipPy -m pip install @PipArgs --upgrade --target $PyLibs -r $Req 2>&1 |
    ForEach-Object { Write-Host "    $_" }
  if ($LASTEXITCODE -ne 0) { return $false }
  Enable-PyLibs
  Ok "Dependencies installed into $PyLibs (loaded via PYTHONPATH)"
  return $true
}

Say ''
Say '========================================'
Say '   IOTAT Components Platform - launcher'
Say '========================================'
Say "   Project : $Root"

# ---------- 1/5 Python ----------
Step '[1/5] Checking Python...'
$Py = Find-Python
if (-not $Py) {
  Fail 'Python not found. Do one of these and retry:'
  Say '    1) Install Python 3.8+ and tick "Add python.exe to PATH"'
  Say '       https://www.python.org/downloads/windows/'
  Say '    2) Set APP_PYTHON to the full path of python.exe'
  Pause-Exit 1
}
$ver = 'unknown'
try {
  $ver = (& $Py -c "import sys; print(str(sys.version_info[0]) + '.' + str(sys.version_info[1]) + '.' + str(sys.version_info[2]))" 2>$null)
} catch { }
if (-not $ver) { $ver = 'unknown' }
Ok "Python $ver  ($Py)"

# ---------- 2/5 venv ----------
Step '[2/5] Preparing venv...'
if ($Reinstall -and (Test-Path -LiteralPath $Venv)) {
  Remove-Item -LiteralPath $Venv -Recurse -Force -ErrorAction SilentlyContinue
  Warn2 'Removed existing venv as requested'
}
if ((Test-Path -LiteralPath $VenvPy) -and (Test-VenvPy $VenvPy)) {
  Ok 'Reusing existing venv'
} else {
  if (Test-Path -LiteralPath $Venv) {
    Remove-Item -LiteralPath $Venv -Recurse -Force -ErrorAction SilentlyContinue
  }
  & $Py -m venv $Venv
  if (-not (Test-Path -LiteralPath $VenvPy)) {
    Fail 'Failed to create venv. Check that this user can write to the project folder.'
    Pause-Exit 1
  }
  if (-not (Test-VenvPy $VenvPy)) {
    Warn2 'venv has no working pip; trying ensurepip...'
    & $VenvPy -m ensurepip --upgrade *> $null
  }
  Ok 'venv created'
}

# ---------- 3/5 dependencies ----------
Step '[3/5] Checking dependencies (flask / waitress / openpyxl)...'
Enable-PyLibs
$needInstall = [bool]$Reinstall
if (-not $needInstall) { $needInstall = $null -ne (Missing-Deps $VenvPy) }
if ($needInstall) {
  if (-not (Install-Deps $VenvPy)) {
    Fail 'Dependency install failed. Try manually with a Python that has pip:'
    Say "    `"$Py`" -m pip install --target `"$PyLibs`" -r `"$Req`""
    Say '    If the host has no internet, pre-download wheels on another machine.'
    Pause-Exit 1
  }
  # The venv may still not see them (e.g. pip lived only in the base Python and
  # installed into its own site-packages). Fall back to project-local deps.
  $missing = Missing-Deps $VenvPy
  if ($missing) {
    Warn2 "venv still cannot import: $missing"
    Warn2 'Switching to project-local dependencies (.pylibs)...'
    $pipPy = Find-PipPython $Py
    if (-not $pipPy) {
      Fail 'No usable pip found to perform the fallback install.'
      Pause-Exit 1
    }
    if (Test-Path -LiteralPath $PyLibs) {
      Remove-Item -LiteralPath $PyLibs -Recurse -Force -ErrorAction SilentlyContinue
    }
    New-Item -ItemType Directory -Path $PyLibs -Force | Out-Null
    & $pipPy -m pip install @PipArgs --upgrade --target $PyLibs -r $Req 2>&1 |
      ForEach-Object { Write-Host "    $_" }
    if ($LASTEXITCODE -ne 0) {
      Fail 'Fallback dependency install failed.'
      Pause-Exit 1
    }
    Enable-PyLibs
    $missing = Missing-Deps $VenvPy
    if ($missing) {
      Fail "Still missing after fallback: $missing"
      Pause-Exit 1
    }
    Ok "Dependencies installed into $PyLibs (loaded via PYTHONPATH)"
  } else {
    Ok 'Dependencies installed'
  }
} else {
  Ok 'Dependencies already satisfied'
}
if (Test-Path -LiteralPath $PyLibs) { Enable-PyLibs }

# ---------- 4/5 port and database ----------
Step "[4/5] Checking port $Port2 and database..."
$env:APP_PORT = "$Port2"
$env:APP_HOST = $Host2
if (-not $env:APP_DB_PATH) { $env:APP_DB_PATH = Join-Path $Root 'backend\data.db' }

$oldPid = $null
try {
  $conn = Get-NetTCPConnection -LocalPort $Port2 -State Listen -ErrorAction Stop | Select-Object -First 1
  if ($conn) { $oldPid = $conn.OwningProcess }
} catch { $oldPid = $null }

if ($oldPid) {
  $procName = 'unknown'
  $p = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
  if ($p) { $procName = $p.ProcessName }
  Warn2 "Port $Port2 is already in use by PID $oldPid ($procName)"
  $ans = Ask '  Stop that process and take over the port? (Y/N)'
  if ($ans -match '^[Yy]') {
    Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    Ok 'Previous process stopped'
  } else {
    Warn2 "Change the port instead: start.bat -Port 5001"
    Pause-Exit 1
  }
}

if (Test-Path -LiteralPath $env:APP_DB_PATH) {
  Ok "Database found (will be reused): $($env:APP_DB_PATH)"
} else {
  Ok "Database will be created on first access: $($env:APP_DB_PATH)"
}

# Drop the session key that shipped in the zip: it came from a dev machine,
# so anyone holding the package could forge sessions.
$shippedKey = Join-Path $Root 'backend\secret_key'
$keyMarker  = Join-Path $Root '.secret_key.shipped'
if ((Test-Path -LiteralPath $shippedKey) -and -not (Test-Path -LiteralPath $keyMarker)) {
  Remove-Item -LiteralPath $shippedKey -Force -ErrorAction SilentlyContinue
  New-Item -ItemType File -Path $keyMarker -Force | Out-Null
  Warn2 'Removed the shipped backend/secret_key; a fresh one is generated on this start'
}

# ---------- 5/5 start ----------
Step '[5/5] Starting service...'
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
Say "   URL (local) : http://localhost:$Port2"
Say "   URL (LAN)   : http://<this-machine-ip>:$Port2"
$adminUser = if ($env:APP_USERNAME) { $env:APP_USERNAME } else { 'IOTAT' }
Say "   Account     : $adminUser"
if ($env:APP_PASSWORD) {
  Ok 'Admin password taken from APP_PASSWORD'
} else {
  Warn2 'Admin password is the built-in default swust350351 - set APP_PASSWORD for real use'
}
Say "   Log         : $LogFile"
Say '   Stop        : press Ctrl+C in this window, or just close it'
Say ''

$app = Start-Process -FilePath $VenvPy -ArgumentList '-m', 'backend.app' `
  -WorkingDirectory $Root -NoNewWindow -PassThru `
  -RedirectStandardOutput $LogFile -RedirectStandardError "$LogFile.err"

# Wait until the service actually answers before opening the browser (max 30s)
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
  if ($app.HasExited) { break }
  try {
    $r = Invoke-WebRequest "http://127.0.0.1:$Port2/api/health" -UseBasicParsing -TimeoutSec 2
    if ($r.StatusCode -eq 200) { $ready = $true; break }
  } catch { }
  Start-Sleep -Milliseconds 500
}

if ($ready) {
  Ok 'Service is up'
  if (-not $NoBrowser) { Start-Process "http://localhost:$Port2" }
} else {
  Fail 'Service did not become ready within 30s. Log tail:'
  if (Test-Path -LiteralPath "$LogFile.err") { Get-Content "$LogFile.err" -Tail 20 }
  if (Test-Path -LiteralPath $LogFile) { Get-Content $LogFile -Tail 20 }
}

# Stay attached so closing this window stops the service
try { Wait-Process -Id $app.Id } catch { }
Say ''
Say 'Service stopped.'
Pause-Exit 0
