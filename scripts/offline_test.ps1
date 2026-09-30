# اختبار العمل دون إنترنت للنسخة المحمولة.
#
#   powershell -ExecutionPolicy Bypass -File offline_test.ps1            # مراقبة: يسجّل كل اتصال شبكي للتطبيق
#   (كمسؤول) powershell -ExecutionPolicy Bypass -File offline_test.ps1 -Block
#       # حظر: قاعدة جدار حماية مؤقتة تمنع التطبيق من الشبكة كلياً، ثم تُحذف تلقائياً
#
# النجاح = التطبيق يصل إلى "جاهز" (الصوت والكاميرا) دون أي اتصال خارجي.
param([switch]$Block, [int]$Seconds = 60)
$ErrorActionPreference = "Stop"
$appDir = $PSScriptRoot
if (-not (Test-Path (Join-Path $appDir "models"))) { $appDir = Join-Path (Split-Path $PSScriptRoot -Parent) "dist\HADJ-NoTouch" }
$exe = Join-Path $appDir "HADJ-NoTouch.exe"                  # نسخة PyInstaller
$pyw = Join-Path $appDir "runtime\pythonw.exe"               # نسخة Python الموقَّعة
$main = Join-Path $appDir "app\main.py"
if (Test-Path $exe) { $program = $exe; $argv = @() }
elseif (Test-Path $pyw) { $program = $pyw; $argv = @("-s", "-E", "`"$main`"") }
else { throw "لم يُعثر على التطبيق في $appDir" }
$log = Join-Path $appDir "user_data\logs\app.log"
$ruleName = "HADJ-NoTouch offline test"

if ($Block) {
    $admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $admin) { throw "-Block يحتاج تشغيل PowerShell كمسؤول" }
    New-NetFirewallRule -DisplayName $ruleName -Direction Outbound -Program $program -Action Block | Out-Null
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Program $program -Action Block | Out-Null
    Write-Host "✓ قاعدة الحظر مفعّلة: $program"
}

function AppPids {
    (Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($appDir) }).ProcessId
}

try {
    if (Test-Path $log) { Remove-Item $log -Force }
    $proc = Start-Process $program -ArgumentList ($argv + @("--exit-after", $Seconds, "--vision-dry-run")) -PassThru
    Write-Host "التطبيق يعمل ($Seconds ث)… المؤشر لن يتحرك في هذا الاختبار."
    $external = @{}
    $end = (Get-Date).AddSeconds($Seconds + 20)
    while ((Get-Date) -lt $end -and (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) {
        $pids = AppPids
        if ($pids) {
            Get-NetTCPConnection -OwningProcess $pids -ErrorAction SilentlyContinue |
                Where-Object { $_.RemoteAddress -notin @("0.0.0.0", "::", "127.0.0.1", "::1") } |
                ForEach-Object { $external["tcp $($_.RemoteAddress):$($_.RemotePort)"] = $_.State }
            Get-NetUDPEndpoint -OwningProcess $pids -ErrorAction SilentlyContinue |
                Where-Object { $_.LocalAddress -notin @("0.0.0.0", "::", "127.0.0.1", "::1") } |
                ForEach-Object { $external["udp $($_.LocalAddress):$($_.LocalPort)"] = "bound" }
        }
        Start-Sleep -Milliseconds 500
    }
    Wait-Process -Id $proc.Id -Timeout 30 -ErrorAction SilentlyContinue

    Write-Host "`n=== النتيجة ==="
    $text = if (Test-Path $log) { Get-Content $log -Raw -Encoding UTF8 } else { "" }
    $audioOk = $text -match "حالة audio: ready"
    $visionOk = $text -match "حالة vision: (ready|tracking|slow)"
    Write-Host ("الصوت جاهز:     " + $(if ($audioOk) { "✓" } else { "✗" }))
    Write-Host ("الكاميرا جاهزة: " + $(if ($visionOk) { "✓" } else { "✗ (قد تكون مشغولة أو غير موجودة)" }))
    if ($external.Count -eq 0) {
        Write-Host "اتصالات خارجية: لا شيء ✓"
    } else {
        Write-Host "اتصالات خارجية مرصودة ✗:"
        $external.GetEnumerator() | ForEach-Object { Write-Host "  $($_.Key) [$($_.Value)]" }
    }
    if ($audioOk -and $external.Count -eq 0) { Write-Host "`n✓ يعمل دون إنترنت"; exit 0 } else { exit 1 }
} finally {
    if ($Block) {
        Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
        Write-Host "قاعدة الحظر حُذفت."
    }
}
