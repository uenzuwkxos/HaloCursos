<#
  Halo Cursors installer engine. Run it through Install.bat or Restore.bat.
  Options: -Theme Light|Dark   -Accent Red|Cyan|...   -Size 1..15 (pointer size)   -Restore
#>
param(
    [ValidateSet('Light', 'Dark')][string]$Theme,
    [ValidateSet('Default', 'Red', 'Cyan', 'Green', 'Magenta', 'Blue', 'Yellow', 'Violet', 'Orange')][string]$Accent = 'Default',
    [ValidateRange(1, 15)][int]$Size,
    [switch]$Restore
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$map = [ordered]@{
    Arrow       = '01-pointer.cur'
    Help        = '02-help.cur'
    AppStarting = '03-working.ani'
    Wait        = '04-busy.ani'
    Crosshair   = '05-precision.cur'
    IBeam       = '06-text.cur'
    NWPen       = '07-handwriting.cur'
    No          = '08-unavailable.cur'
    SizeNS      = '09-vertical.cur'
    SizeWE      = '10-horizontal.cur'
    SizeNWSE    = '11-diagonal1.cur'
    SizeNESW    = '12-diagonal2.cur'
    SizeAll     = '13-move.cur'
    UpArrow     = '14-alternate.cur'
    Hand        = '15-link.cur'
    Pin         = '16-pin.cur'
    Person      = '17-person.cur'
}

Add-Type -Namespace Win32 -Name Native -MemberDefinition '[DllImport("user32.dll", SetLastError=true)] public static extern bool SystemParametersInfo(uint uiAction, uint uiParam, IntPtr pvParam, uint fWinIni);'
function Update-Cursors { [void][Win32.Native]::SystemParametersInfo(0x0057, 0, [IntPtr]::Zero, 0x03) }

$regPath = 'HKCU:\Control Panel\Cursors'

function Set-PointerSize([int]$n) {
    $base = 16 * ($n + 1)
    Set-ItemProperty -Path $regPath -Name 'CursorBaseSize' -Value $base -Type DWord
    try { [void][Win32.Native]::SystemParametersInfo(0x2029, 0, [IntPtr]$base, 0x03) } catch { }
    Update-Cursors
    Write-Host "Pointer size: $n ($base px base)."
    Write-Host 'If it does not change right away, use Settings > Accessibility > Mouse pointer and touch > Size.'
}

if ($Restore) {
    foreach ($k in $map.Keys) { Set-ItemProperty -Path $regPath -Name $k -Value '' }
    Set-ItemProperty -Path $regPath -Name '(default)' -Value 'Windows Default'
    Update-Cursors
    Write-Host 'Windows default cursors restored.'
    return
}

$wantSize = $PSBoundParameters.ContainsKey('Size')

if ($wantSize -and -not $Theme) {
    Set-PointerSize $Size
    return
}

if (-not $Theme) {
    $opts = @('Light', 'Dark')
    for ($i = 0; $i -lt $opts.Count; $i++) { Write-Host ("  {0}) {1}" -f ($i + 1), $opts[$i]) }
    $n = [int](Read-Host 'Choose a theme (1-2)')
    if ($n -lt 1 -or $n -gt 2) { throw 'Invalid option.' }
    $Theme = $opts[$n - 1]
    $accents = @('Default', 'Red', 'Cyan', 'Green', 'Magenta', 'Blue', 'Yellow', 'Violet', 'Orange')
    Write-Host ''
    for ($i = 0; $i -lt $accents.Count; $i++) { Write-Host ("  {0}) {1}" -f ($i + 1), $accents[$i]) }
    $a = [int](Read-Host 'Choose an accent color (1-9, Default = yellow on Light, blue on Dark)')
    if ($a -lt 1 -or $a -gt $accents.Count) { throw 'Invalid option.' }
    $Accent = $accents[$a - 1]
    $s = Read-Host 'Pointer size from 1 to 15 (press Enter to keep the current one)'
    if ($s -match '^\d+$' -and [int]$s -ge 1 -and [int]$s -le 15) { $Size = [int]$s; $wantSize = $true }
}

if ($Accent -eq 'Default') { $name = $Theme; $src = Join-Path $root $Theme }
else { $name = "$Accent-$Theme"; $src = Join-Path $root "Colors\$name" }
if (-not (Test-Path $src)) { throw "Theme folder not found: $src" }
$dest = Join-Path $env:LOCALAPPDATA "HaloCursors\$name"
New-Item -ItemType Directory -Path $dest -Force | Out-Null
Copy-Item -Path (Join-Path $src '*.cur'), (Join-Path $src '*.ani') -Destination $dest -Force

$schemeName = "Halo " + $name.Replace('-', ' ')
$paths = @()
foreach ($k in $map.Keys) {
    $full = Join-Path $dest $map[$k]
    Set-ItemProperty -Path $regPath -Name $k -Value $full
    $paths += $full
}
Set-ItemProperty -Path $regPath -Name '(default)' -Value $schemeName

$schemes = "$regPath\Schemes"
if (-not (Test-Path $schemes)) { New-Item -Path $schemes -Force | Out-Null }
New-ItemProperty -Path $schemes -Name $schemeName -Value ($paths -join ',') -PropertyType ExpandString -Force | Out-Null

Update-Cursors
Write-Host "Theme '$schemeName' applied."
if ($wantSize) { Set-PointerSize $Size }
