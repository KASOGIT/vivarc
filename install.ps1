# Vivarc: one-line install, update and repair for Windows.
#
#   irm https://raw.githubusercontent.com/KASOGIT/vivarc/main/install.ps1 | iex
#
# It downloads the latest Vivarc release into ~\.vivarc\app and runs its installer. Running it again updates
# Vivarc and re-applies it after a Vivaldi update. When run as a file, extra arguments go to `vivarc.py install`
# (for example --no-peek). $env:VIVARC_TARBALL_URL picks another zip (a URL or a local file).
#
# Everything runs inside a function: under `irm | iex` an `exit` would close the user's PowerShell window.

function Install-Vivarc {
  $ErrorActionPreference = "Stop"
  $ProgressPreference = "SilentlyContinue"  # the progress bar makes downloads very slow on Windows PowerShell
  $repo = "KASOGIT/vivarc"
  $dest = Join-Path ([Environment]::GetFolderPath("UserProfile")) ".vivarc\app"

  $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
  if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) -and -not $env:VIVARC_ALLOW_ADMIN) {
    Write-Host ("error: Do not run this as administrator: Vivarc belongs in your own user folder. Open a normal " +
                "PowerShell window and run the command again.") -ForegroundColor Red
    return 1
  }

  # Python: the py launcher first, then python on PATH. The Microsoft Store stub (WindowsApps\python.exe) does not count.
  $python = $null
  $pythonArgs = @()
  if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -c "import sys" 2>$null
    if ($LASTEXITCODE -eq 0) { $python = "py"; $pythonArgs = @("-3") }
  }
  if (-not $python) {
    $found = Get-Command python -ErrorAction SilentlyContinue | Where-Object { $_.Source -notlike "*\WindowsApps\*" } |
      Select-Object -First 1
    if ($found) { $python = $found.Source }
  }
  if (-not $python) {
    Write-Host "Vivarc needs Python 3. Install it with:"
    Write-Host "  winget install Python.Python.3.13"
    Write-Host "(or from https://www.python.org/downloads/), then open a new PowerShell window and run this command again."
    return 1
  }

  $tmp = Join-Path ([IO.Path]::GetTempPath()) ("vivarc-" + [Guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Path $tmp | Out-Null
  try {
    $url = $env:VIVARC_TARBALL_URL
    if (-not $url) {
      Write-Host "Looking for the latest Vivarc release..."
      $tag = ""
      try {
        $latest = Invoke-WebRequest -Uri "https://github.com/$repo/releases/latest" -UseBasicParsing -Method Head
        $final = $latest.BaseResponse.ResponseUri                                       # Windows PowerShell 5.1
        if (-not $final) { $final = $latest.BaseResponse.RequestMessage.RequestUri }   # PowerShell 7
        $tag = ($final.AbsoluteUri -split "/")[-1]
      } catch { }
      if ($tag -notmatch "^v[0-9]") {
        Write-Host "error: Could not find the latest release. Check your internet connection." -ForegroundColor Red
        return 1
      }
      Write-Host "Downloading Vivarc $tag..."
      $url = "https://github.com/$repo/archive/refs/tags/$tag.zip"
    }
    $zip = Join-Path $tmp "vivarc.zip"
    if (Test-Path -LiteralPath $url) {
      Copy-Item -LiteralPath $url $zip
    } else {
      try { Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing }
      catch { Write-Host "error: Download failed. Check your internet connection." -ForegroundColor Red; return 1 }
    }
    $unpacked = Join-Path $tmp "src"
    Expand-Archive -Path $zip -DestinationPath $unpacked
    # A GitHub archive holds one top folder (vivarc-0.1.18); a flat zip works too.
    $root = $unpacked
    $inner = @(Get-ChildItem $unpacked -Directory)
    if (-not (Test-Path (Join-Path $root "vivarc.py")) -and $inner.Count -eq 1) { $root = $inner[0].FullName }
    if (-not (Test-Path (Join-Path $root "vivarc.py"))) {
      Write-Host "error: The download does not look like Vivarc." -ForegroundColor Red
      return 1
    }

    New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
    if (Test-Path $dest) {
      # Move the old copy aside first: a file in use cannot be deleted, but its folder can still be renamed.
      $old = "$dest.old-" + [Guid]::NewGuid().ToString("N").Substring(0, 8)
      Rename-Item $dest (Split-Path $old -Leaf)
      Remove-Item $old -Recurse -Force -ErrorAction SilentlyContinue
    }
    Move-Item $root $dest
  } finally {
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
  }

  # Out-Host: inside a function, output would otherwise become the return value instead of reaching the screen.
  & $python @pythonArgs (Join-Path $dest "vivarc.py") install @args | Out-Host
  return $LASTEXITCODE
}

$code = Install-Vivarc @args
if ($PSCommandPath) { exit $code }  # run as a file (vivarc.py update): pass the result on; under iex, keep the window
