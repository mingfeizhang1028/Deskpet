param(
    [string]$Godot = "",
    [string]$Output = ""
)

$project = Split-Path -Parent $PSScriptRoot
if (-not $Godot) {
    $Godot = Join-Path $project "Godot_v4.7.2-stable_win64.exe\Godot_v4.7.2-stable_win64_console.exe"
}
if (-not $Output) {
    $Output = Join-Path $project "output\godot\YayanPet.exe"
}
if (-not (Test-Path -LiteralPath $Godot)) {
    throw "找不到 Godot：$Godot"
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Output) | Out-Null
$taskTemp = Join-Path $project "tmp"
New-Item -ItemType Directory -Force -Path $taskTemp | Out-Null
$oldTemp = $env:TEMP
$oldTmp = $env:TMP
try {
    # Godot 的安全写入会先生成 tmpproject.binary；固定到项目可写目录，
    # 避免受限 Windows 临时目录导致损坏的 .pck 仍被报告为导出成功。
    $env:TEMP = $taskTemp
    $env:TMP = $taskTemp
    & $Godot --headless --path (Join-Path $project "godot") --export-release "Windows Desktop" $Output
    $exportExit = $LASTEXITCODE
}
finally {
    $env:TEMP = $oldTemp
    $env:TMP = $oldTmp
}
if ($exportExit -ne 0) { throw "Godot 导出失败，退出码 $exportExit" }
$pack = [IO.Path]::ChangeExtension($Output, ".pck")
if (-not (Test-Path -LiteralPath $pack)) { throw "导出缺少配套 pck：$pack" }
$smokeOut = Join-Path $taskTemp "godot-export-smoke.out"
$smokeErr = Join-Path $taskTemp "godot-export-smoke.err"
$smoke = Start-Process -FilePath $Output -WorkingDirectory (Split-Path -Parent $Output) `
    -ArgumentList @("--headless", "--quit-after", "1") `
    -RedirectStandardOutput $smokeOut -RedirectStandardError $smokeErr -Wait -PassThru
if ($smoke.ExitCode -ne 0) {
    $details = (Get-Content -LiteralPath $smokeErr -Tail 12 -ErrorAction SilentlyContinue) -join "`n"
    throw "导出包自检失败，退出码 $($smoke.ExitCode)：$details"
}
Write-Output "已生成：$Output"
Write-Output "已验证：$pack"
