# بناء النسخة المحمولة: dist\HADJ-NoTouch\ + dist\HADJ-NoTouch-portable.zip
#
#   powershell -ExecutionPolicy Bypass -File scripts\build.ps1                    # الوضع الافتراضي: python
#   powershell -ExecutionPolicy Bypass -File scripts\build.ps1 -Mode pyinstaller  # ملف تنفيذي واحد
#   ... -NoZip                                                                     # دون ضغط
#
# الوضعان:
#   python      : مفسّر Python الرسمي (موقَّع من Python Software Foundation) + الكود + المكتبات.
#                 يعمل مع "Smart App Control" في Windows 11 (الذي يمنع الملفات التنفيذية غير الموقَّعة).
#   pyinstaller : HADJ-NoTouch.exe. أنظف، لكنه غير موقَّع، فقد يمنعه Smart App Control
#                 إلا إذا وُقِّع بشهادة توقيع برمجيات.
#
# المتطلبات: .venv جاهزة (requirements.txt) والنماذج منزّلة (scripts\download_models.py).
param([ValidateSet("python", "pyinstaller")][string]$Mode = "python", [switch]$NoZip)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$py = Join-Path $root ".venv\Scripts\python.exe"
$dist = Join-Path $root "dist"
$app = Join-Path $dist "HADJ-NoTouch"

function Copy-Tree($from, $to, [string[]]$excludeDirs = @(), [string[]]$excludeFiles = @()) {
    $args_ = @($from, $to, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NP")
    if ($excludeDirs) { $args_ += "/XD"; $args_ += $excludeDirs }
    if ($excludeFiles) { $args_ += "/XF"; $args_ += $excludeFiles }
    robocopy @args_ | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "فشل النسخ: $from" }
}

if (-not (Test-Path $py)) { throw "لم يُعثر على .venv. أنشئها أولاً (انظر README)." }
foreach ($m in @("models\vosk\ar", "models\vosk\en", "models\mediapipe\hand_landmarker.task", "models\whisper\small\model.bin")) {
    if (-not (Test-Path (Join-Path $root $m))) { throw "نموذج ناقص: $m. شغّل scripts\download_models.py" }
}
if (Test-Path $app) { Remove-Item $app -Recurse -Force }
New-Item -ItemType Directory -Force $app | Out-Null

if ($Mode -eq "pyinstaller") {
    & $py -m PyInstaller --version *> $null
    if ($LASTEXITCODE -ne 0) { & $py -m pip install pyinstaller; if ($LASTEXITCODE -ne 0) { throw "فشل تثبيت PyInstaller" } }
    Write-Host "[1/5] الأيقونة"
    & $py (Join-Path $root "scripts\make_icon.py")
    if ($LASTEXITCODE -ne 0) { throw "فشل توليد الأيقونة" }
    Write-Host "[2/5] PyInstaller (قد يستغرق عدة دقائق)"
    & $py -m PyInstaller --noconfirm --clean --log-level WARN `
        --distpath $dist --workpath (Join-Path $root "build\pyi") (Join-Path $root "scripts\hadj.spec")
    if ($LASTEXITCODE -ne 0) { throw "فشل PyInstaller" }
} else {
    Write-Host "[1/5] مفسّر Python الموقَّع"
    $base = & $py -c "import sys; print(sys.base_prefix)"
    $rt = Join-Path $app "runtime"
    New-Item -ItemType Directory -Force $rt | Out-Null
    Get-ChildItem $base -File | Where-Object { $_.Name -match '^(python(w)?\.exe|python3\d*\.dll|vcruntime.*\.dll|LICENSE\.txt)$' } |
        Copy-Item -Destination $rt
    Copy-Tree (Join-Path $base "DLLs") (Join-Path $rt "DLLs") -excludeFiles @("_tkinter.pyd", "tcl*.dll", "tk*.dll")
    Copy-Tree (Join-Path $base "Lib") (Join-Path $rt "Lib") `
        -excludeDirs @("site-packages", "test", "idlelib", "tkinter", "turtledemo", "ensurepip", "__pycache__", "lib2to3")

    Write-Host "[2/5] المكتبات (مع حذف ما لا يحتاجه التطبيق)"
    $sp = Join-Path $rt "Lib\site-packages"
    Copy-Tree (Join-Path $root ".venv\Lib\site-packages") $sp `
        -excludeDirs @("__pycache__", "pip", "pyinstaller*", "PyInstaller", "_pyinstaller_hooks_contrib", "pytest", "_pytest",
                       "pip-*.dist-info", "pytest-*.dist-info", "pyinstaller-*.dist-info", "sounddevice*", "_sounddevice_data")
    # وحدات Qt كبيرة غير مستخدمة (الواجهة تحتاج QtCore وQtGui وQtWidgets فقط)
    $qt = Join-Path $sp "PySide6"
    $unused = "WebEngine|WebView|WebChannel|WebSockets|Quick|Qml|3D|Multimedia|Pdf|Designer|Charts|DataVisualization|Graphs|" +
              "Location|Positioning|Sensors|SerialBus|SerialPort|Bluetooth|Nfc|RemoteObjects|Scxml|SpatialAudio|StateMachine|" +
              "TextToSpeech|VirtualKeyboard|Test|Sql|Help|UiTools|HttpServer|ShaderTools|Lottie|Canvas"
    Get-ChildItem $qt -File | Where-Object { $_.Name -match "^(Qt6?)($unused)" -or $_.Name -match "^(av|sw)[a-z]*-\d+\.dll$" -or
        $_.Name -match "^(designer|linguist|assistant|QtWebEngineProcess|qmllint|qmlls|lupdate|lrelease|balsam|qml)[a-z]*\.exe$" } |
        Remove-Item -Force
    foreach ($d in "resources", "translations\qtwebengine_locales", "qml", "examples", "include", "doc", "typesystems", "glue", "scripts") {
        $p = Join-Path $qt $d
        if (Test-Path $p) { Remove-Item $p -Recurse -Force }
    }

    Write-Host "[3/5] الكود والمشغّل"
    Copy-Tree (Join-Path $root "src") (Join-Path $app "app") -excludeDirs @("__pycache__")
    # -s -E: لا مكتبات المستخدم ولا متغيرات PYTHON* من الجهاز (عزل تام)
    Set-Content (Join-Path $app "HADJ-NoTouch.bat") -Encoding ASCII -Value @(
        '@echo off',
        'start "" "%~dp0runtime\pythonw.exe" -s -E "%~dp0app\main.py" %*')
    Set-Content (Join-Path $app "HADJ-NoTouch-debug.bat") -Encoding ASCII -Value @(
        '@echo off',
        'rem runs with a console window and a detailed log (user_data\logs\app.log)',
        '"%~dp0runtime\python.exe" -s -E "%~dp0app\main.py" --debug %*',
        'pause')
}

Write-Host "[4/5] النماذج والوثائق"
Copy-Tree (Join-Path $root "models") (Join-Path $app "models")
Copy-Item (Join-Path $root "README.md") $app -Force
Copy-Item (Join-Path $root "scripts\offline_test.ps1") $app -Force
New-Item -ItemType Directory -Force (Join-Path $app "user_data") | Out-Null   # الإعدادات والسجلات

if (-not $NoZip) {
    Write-Host "[5/5] الضغط"
    $zip = Join-Path $dist "HADJ-NoTouch-portable.zip"
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Push-Location $dist
    # tar الخاص بـ Windows صراحةً: نسخة GNU (من Git) تتجاهل -a وتنتج tar غير مضغوط باسم .zip
    try { & "$env:SystemRoot\System32\tar.exe" -a -c -f $zip "HADJ-NoTouch" } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw "فشل الضغط" }
    "{0}  ({1:N0} MB)" -f $zip, ((Get-Item $zip).Length / 1MB)
}
$size = (Get-ChildItem $app -Recurse | Measure-Object Length -Sum).Sum / 1MB
"الناتج ({0}): {1}  ({2:N0} MB)" -f $Mode, $app, $size
