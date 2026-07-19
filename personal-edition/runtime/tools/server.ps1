# Birth Chart Museum — Personal Edition local server (Windows / PowerShell 5.1+)
# Serves the ./app directory on http://localhost:<port>/ . Local-only: binds to
# localhost, sends nothing anywhere. Close this window to stop the museum.
param(
  [int]$Port = 0,
  [string]$Root = "",
  [string]$OpenPath = "/"
)

$ErrorActionPreference = "Stop"

if (-not $Root) {
  $base = Split-Path -Parent $PSScriptRoot
  $Root = Join-Path $base "app"
}
if (-not (Test-Path $Root -PathType Container)) {
  Write-Host "app フォルダが見つかりません: $Root"
  Write-Host "The app folder was not found. Keep start.bat next to the app folder."
  exit 1
}
$Root = [System.IO.Path]::GetFullPath($Root)

$mime = @{
  ".html"  = "text/html; charset=utf-8"
  ".css"   = "text/css; charset=utf-8"
  ".js"    = "text/javascript; charset=utf-8"
  ".mjs"   = "text/javascript; charset=utf-8"
  ".json"  = "application/json; charset=utf-8"
  ".yaml"  = "text/yaml; charset=utf-8"
  ".yml"   = "text/yaml; charset=utf-8"
  ".svg"   = "image/svg+xml"
  ".woff2" = "font/woff2"
  ".png"   = "image/png"
  ".jpg"   = "image/jpeg"
  ".jpeg"  = "image/jpeg"
  ".webp"  = "image/webp"
  ".ico"   = "image/x-icon"
  ".txt"   = "text/plain; charset=utf-8"
  ".md"    = "text/plain; charset=utf-8"
}

# Find a free port (localhost prefixes need no admin rights)
$listener = $null
$candidates = @()
if ($Port -gt 0) { $candidates = @($Port) } else { $candidates = 8787..8796 }
foreach ($p in $candidates) {
  $l = New-Object System.Net.HttpListener
  $l.Prefixes.Add("http://localhost:$p/")
  try {
    $l.Start()
    $listener = $l
    $Port = $p
    break
  } catch {
    $l.Close()
  }
}
if (-not $listener) {
  Write-Host "空きポートが見つかりませんでした (8787-8796)。他のアプリを閉じて再実行してください。"
  Write-Host "No free port found (8787-8796)."
  exit 1
}

$OpenPath = "/" + $OpenPath.TrimStart("/")
$url = "http://localhost:$Port$OpenPath"
Write-Host ""
Write-Host "  BIRTH CHART MUSEUM — Personal Edition"
Write-Host "  ------------------------------------------------"
Write-Host "  URL: $url"
Write-Host "  ブラウザが自動で開きます。開かない場合は上のURLをブラウザに貼ってください。"
Write-Host "  この黒いウィンドウを閉じるとミュージアムは終了します。"
Write-Host "  (Close this window to stop the museum.)"
Write-Host ""
Start-Process $url

while ($listener.IsListening) {
  $ctx = $listener.GetContext()
  try {
    $res = $ctx.Response
    $relPath = [System.Uri]::UnescapeDataString($ctx.Request.Url.AbsolutePath)
    $ok = $true
    if ($relPath.Contains("..")) { $ok = $false }
    $fsPath = $null
    if ($ok) {
      $joined = Join-Path $Root ($relPath.TrimStart("/") -replace "/", "\")
      $fsPath = [System.IO.Path]::GetFullPath($joined)
      if (-not ($fsPath.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase))) { $ok = $false }
    }
    if ($ok -and (Test-Path $fsPath -PathType Container)) {
      $fsPath = Join-Path $fsPath "index.html"
    }
    if ($ok -and (Test-Path $fsPath -PathType Leaf)) {
      $ext = [System.IO.Path]::GetExtension($fsPath).ToLowerInvariant()
      $ct = $mime[$ext]
      if (-not $ct) { $ct = "application/octet-stream" }
      $bytes = [System.IO.File]::ReadAllBytes($fsPath)
      $res.StatusCode = 200
      $res.ContentType = $ct
      $res.ContentLength64 = $bytes.Length
      $res.OutputStream.Write($bytes, 0, $bytes.Length)
    } else {
      $body = [System.Text.Encoding]::UTF8.GetBytes("404 Not Found")
      $res.StatusCode = 404
      $res.ContentType = "text/plain; charset=utf-8"
      $res.ContentLength64 = $body.Length
      $res.OutputStream.Write($body, 0, $body.Length)
    }
  } catch {
    # Ignore per-request errors (client aborts etc.); keep serving.
  } finally {
    try { $ctx.Response.Close() } catch {}
  }
}
