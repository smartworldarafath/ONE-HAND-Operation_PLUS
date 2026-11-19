$ErrorActionPreference = "Stop"
$base = $PSScriptRoot
$sdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } elseif ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } else { Join-Path $env:LOCALAPPDATA "Android\Sdk" }
$adb = Join-Path $sdk "platform-tools\adb.exe"
$bt = Get-ChildItem (Join-Path $sdk "build-tools") | Sort-Object Name -Descending | Select-Object -First 1 -ExpandProperty FullName
$androidJar = Get-ChildItem (Join-Path $sdk "platforms\android-*\android.jar") | Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
$apktoolCmd = Get-Command apktool -ErrorAction SilentlyContinue
$apktool = if ($apktoolCmd) { $apktoolCmd.Source } else { Join-Path $env:APPDATA "npm\apktool.bat" }

New-Item -ItemType Directory -Force -Path "$base\dist", "$base\compat_build\classes", "$base\compat_build\dex" | Out-Null

Write-Host "[1/6] Compiling compat Java -> DEX..."
$javaFiles = Get-ChildItem -Filter "*.java" "$base\compat_src\com\samsung\android\sidegesturepad\compat" | ForEach-Object { $_.FullName }
javac --release 11 -cp $androidJar -d "$base\compat_build\classes" $javaFiles
if ($LASTEXITCODE -ne 0) { throw "javac failed" }
$classFiles = Get-ChildItem -Recurse -Filter "*.class" "$base\compat_build\classes" | ForEach-Object { $_.FullName }
& "$bt\d8.bat" --min-api 34 --lib $androidJar --output "$base\compat_build\dex" $classFiles
if ($LASTEXITCODE -ne 0) { throw "d8 failed" }

Write-Host "[2/6] Building APK with apktool..."
& $apktool b "$base\apktool_out" -o "$base\dist\sgp_raw.apk"
if ($LASTEXITCODE -ne 0) { throw "apktool build failed" }

Write-Host "[3/6] Injecting classes2.dex..."
python -c "
import zipfile, shutil
src = r'$base\dist\sgp_raw.apk'
dst = r'$base\dist\sgp_with_dex2.apk'
dex = r'$base\compat_build\dex\classes.dex'
with zipfile.ZipFile(src, 'r') as zin, zipfile.ZipFile(dst, 'w') as zout:
    for item in zin.infolist():
        if item.filename == 'classes2.dex' or item.filename.startswith('META-INF/') or item.filename.startswith('assets/dexopt/'):
            continue
        data = zin.read(item.filename)
        zout.writestr(item, data)
    with open(dex, 'rb') as f:
        zi = zipfile.ZipInfo('classes2.dex')
        zi.compress_type = zipfile.ZIP_STORED
        zout.writestr(zi, f.read())
"
if ($LASTEXITCODE -ne 0) { throw "dex injection failed" }

Write-Host "[4/6] Aligning APK..."
& "$bt\zipalign.exe" -p -f 4 "$base\dist\sgp_with_dex2.apk" "$base\dist\sgp_aligned.apk"
if ($LASTEXITCODE -ne 0) { throw "zipalign failed" }

Write-Host "[5/6] Signing APK..."
$ks = "$base\debug.keystore"
if (-not (Test-Path $ks)) {
    keytool -genkey -v -keystore $ks -storepass android -alias androiddebugkey -keypass android -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Android Debug,O=Android,C=US"
}
& "$bt\apksigner.bat" sign --ks $ks --ks-pass pass:android --key-pass pass:android --out "$base\dist\sgp_signed.apk" "$base\dist\sgp_aligned.apk"
if ($LASTEXITCODE -ne 0) { throw "apksigner failed" }

Write-Host "[6/6] Installing and granting permissions on connected Android device..."
$ErrorActionPreference = "Continue"
& $adb start-server | Out-Null
& $adb install --no-incremental -r "$base\dist\sgp_signed.apk"
if ($LASTEXITCODE -ne 0) {
    & $adb uninstall com.samsung.android.sidegesturepad 2>&1 | Out-Null
    & $adb install --no-incremental "$base\dist\sgp_signed.apk"
    if ($LASTEXITCODE -ne 0) { throw "adb install failed" }
}

$pkg = "com.samsung.android.sidegesturepad"
& $adb shell pm grant $pkg android.permission.WRITE_SECURE_SETTINGS
& $adb shell pm grant $pkg android.permission.POST_NOTIFICATIONS 2>$null
& $adb shell pm grant $pkg android.permission.BLUETOOTH_CONNECT 2>$null
& $adb shell pm grant $pkg android.permission.BLUETOOTH_SCAN 2>$null
& $adb shell pm grant $pkg android.permission.BLUETOOTH_ADVERTISE 2>$null
& $adb shell appops set $pkg android:get_usage_stats allow
& $adb shell appops set $pkg SYSTEM_ALERT_WINDOW allow
& $adb shell appops set $pkg WRITE_SETTINGS allow
& $adb shell cmd notification allow_dnd $pkg
& $adb shell dumpsys deviceidle whitelist +$pkg | Out-Null
& $adb shell settings put global hidden_api_policy 1

$accSvc = "$pkg/com.samsung.android.sidegesturepad.compat.SGPCompatAccessibilityService"
$cur = (& $adb shell settings get secure enabled_accessibility_services).Trim()
if ($cur -eq "null" -or [string]::IsNullOrWhiteSpace($cur)) {
    $newAcc = $accSvc
} elseif ($cur -notlike "*$accSvc*") {
    $newAcc = "$cur`:$accSvc"
} else {
    $newAcc = $cur
}
& $adb shell settings put secure enabled_accessibility_services $newAcc
& $adb shell settings put secure accessibility_enabled 1

Write-Host "DONE! Installed, granted permissions, and enabled SGPCompatAccessibilityService."
