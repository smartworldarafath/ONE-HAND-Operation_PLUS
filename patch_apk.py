#!/usr/bin/env python3
"""Patch decoded Samsung One Hand Operation+ (9.4.23.0) smali & manifest for non-Samsung Android 14–16+ devices."""
import os
import re
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
BAK = os.path.join(BASE, "apktool_orig_bak")
APK_OUT = os.path.join(BASE, "apktool_out")
SMALI = os.path.join(APK_OUT, "smali")
COMPAT = "Lcom/samsung/android/sidegesturepad/compat/VivoCompat;"
ACC = "Lcom/samsung/android/sidegesturepad/compat/SGPCompatAccessibilityService;"


def restore_from_backup():
    if os.path.exists(BAK):
        shutil.copy2(os.path.join(BAK, "AndroidManifest.xml"), os.path.join(APK_OUT, "AndroidManifest.xml"))
        if os.path.exists(SMALI):
            shutil.rmtree(SMALI)
        shutil.copytree(os.path.join(BAK, "smali"), SMALI)
    a11y_xml_src = os.path.join(BASE, "resources", "res", "xml", "sgp_accessibility_service.xml")
    if os.path.exists(a11y_xml_src):
        a11y_xml_dst = os.path.join(APK_OUT, "res", "xml", "sgp_accessibility_service.xml")
        os.makedirs(os.path.dirname(a11y_xml_dst), exist_ok=True)
        shutil.copy2(a11y_xml_src, a11y_xml_dst)


def replace_regex(text, pattern, repl, label, count=1):
    matches = list(re.finditer(pattern, text, re.DOTALL))
    if len(matches) != count:
        raise RuntimeError(f"[{label}] Expected {count} regex matches, found {len(matches)}:\n{pattern[:200]}")
    return re.sub(pattern, repl, text, flags=re.DOTALL)


def read_text(rel_path):
    p = os.path.join(APK_OUT, rel_path)
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def write_text(rel_path, content):
    p = os.path.join(APK_OUT, rel_path)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def replace_exact(text, old, new, label, count=1):
    actual = text.count(old)
    if actual != count:
        raise RuntimeError(f"[{label}] Expected {count} occurrences, found {actual}:\n{old[:200]}")
    return text.replace(old, new)


def replace_method_body(text, signature_prefix, new_body, label):
    pattern = re.compile(
        r"(\.method [^\n]*" + re.escape(signature_prefix) + r"[^\n]*\n)(.*?)(\n\.end method)",
        re.DOTALL,
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(f"[{label}] Expected 1 method match for {signature_prefix}, found {len(matches)}")
    m = matches[0]
    return text[: m.start(2)] + new_body + text[m.end(2) :]


def patch_manifest():
    rel = "AndroidManifest.xml"
    t = read_text(rel)

    # Add required permissions
    if "android.permission.SYSTEM_ALERT_WINDOW" not in t:
        t = replace_exact(
            t,
            '    <uses-permission android:name="android.permission.INJECT_EVENTS"/>',
            '    <uses-permission android:name="android.permission.INJECT_EVENTS"/>\n'
            '    <uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW"/>\n'
            '    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_SPECIAL_USE"/>\n'
            '    <uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>',
            "manifest permissions",
        )

    # Make Samsung-only uses-feature non-required
    t = replace_exact(
        t,
        '<uses-feature android:name="com.samsung.android.api.version.2402"/>',
        '<uses-feature android:name="com.samsung.android.api.version.2402" android:required="false"/>',
        "feature api 2402",
    )
    t = replace_exact(
        t,
        '<uses-feature android:name="com.samsung.feature.samsung_experience_mobile"/>',
        '<uses-feature android:name="com.samsung.feature.samsung_experience_mobile" android:required="false"/>',
        "feature sep",
    )

    # SGPService foregroundServiceType="specialUse" and relax permission gate so AccessibilityService/Tile can bind/start cleanly
    t = replace_exact(
        t,
        '        <service android:exported="true" android:label="@string/app_name" android:name="com.samsung.android.sidegesturepad.SGPService" android:permission="android.permission.WRITE_SECURE_SETTINGS">\n'
        '            <intent-filter>\n'
        '                <action android:name="com.samsung.action.SIDEGESTUREPAD_SERVICE"/>\n'
        '            </intent-filter>\n'
        '        </service>',
        '        <service android:exported="true" android:foregroundServiceType="specialUse" android:label="@string/app_name" android:name="com.samsung.android.sidegesturepad.SGPService">\n'
        '            <intent-filter>\n'
        '                <action android:name="com.samsung.action.SIDEGESTUREPAD_SERVICE"/>\n'
        '            </intent-filter>\n'
        '            <property android:name="android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE" android:value="edge_gesture_overlay"/>\n'
        '        </service>\n'
        '        <service android:exported="true" android:label="@string/app_name" android:name="com.samsung.android.sidegesturepad.compat.SGPCompatAccessibilityService" android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE">\n'
        '            <intent-filter>\n'
        '                <action android:name="android.accessibilityservice.AccessibilityService"/>\n'
        '            </intent-filter>\n'
        '            <meta-data android:name="android.accessibilityservice" android:resource="@xml/sgp_accessibility_service"/>\n'
        '        </service>',
        "manifest SGPService + AccessibilityService",
    )

    write_text(rel, t)
    print("Patched AndroidManifest.xml")


def patch_s6_d():
    rel = "smali/s6/d.smali"
    t = read_text(rel)

    # Neutralize <clinit> safely without touching Android-missing SemFloatingFeature / SEM_PLATFORM_INT
    clinit_body = (
        "    .locals 1\n\n"
        "    const/4 v0, 0x0\n"
        "    sput-boolean v0, Ls6/d;->a:Z\n"
        "    sput-boolean v0, Ls6/d;->b:Z\n"
        "    sput-boolean v0, Ls6/d;->c:Z\n"
        "    sput-boolean v0, Ls6/d;->d:Z\n"
        "    sput-boolean v0, Ls6/d;->e:Z\n"
        "    sput-boolean v0, Ls6/d;->f:Z\n"
        "    sput-boolean v0, Ls6/d;->g:Z\n"
        "    sput-boolean v0, Ls6/d;->h:Z\n"
        "    sput-boolean v0, Ls6/d;->i:Z\n"
        "    sput-boolean v0, Ls6/d;->j:Z\n"
        "    sput-boolean v0, Ls6/d;->k:Z\n"
        "    sput-boolean v0, Ls6/d;->l:Z\n"
        "    const/4 v0, 0x0\n"
        "    sput v0, Ls6/d;->m:F\n"
        "    const/4 v0, 0x1\n"
        "    sput-boolean v0, Ls6/d;->n:Z\n"
        '    const-string v0, ";\\u0007"\n'
        "    sput-object v0, Ls6/d;->o:Ljava/lang/String;\n"
        '    const-string v0, "|\\u0007"\n'
        "    sput-object v0, Ls6/d;->p:Ljava/lang/String;\n"
        '    const-string v0, "[;][\\u0007]"\n'
        "    sput-object v0, Ls6/d;->q:Ljava/lang/String;\n"
        '    const-string v0, "[\\\\|][\\u0007]"\n'
        "    sput-object v0, Ls6/d;->r:Ljava/lang/String;\n"
        '    const-string v0, "content://com.samsung.app.honeyspace.edge.settings.EdgeSettingProvider"\n'
        "    invoke-static {v0}, Landroid/net/Uri;->parse(Ljava/lang/String;)Landroid/net/Uri;\n"
        "    move-result-object v0\n"
        "    sput-object v0, Ls6/d;->s:Landroid/net/Uri;\n"
        "    return-void"
    )
    t = replace_method_body(t, "static constructor <clinit>()V", clinit_body, "s6/d <clinit>")
    t = replace_exact(
        t,
        "invoke-static {v0}, Landroid/os/SemSystemProperties;->get(Ljava/lang/String;)Ljava/lang/String;",
        f"invoke-static {{v0}}, {COMPAT}->getSystemProperty(Ljava/lang/String;)Ljava/lang/String;",
        "s6/d a() SemSystemProperties",
    )
    write_text(rel, t)
    print("Patched s6/d.smali")


def patch_sgp_service():
    rel = "smali/com/samsung/android/sidegesturepad/SGPService.smali"
    t = read_text(rel)

    # b(Z) -> ensureForegroundService when true
    b_body = (
        "    .locals 1\n\n"
        "    if-eqz p1, :cond_0\n"
        "    iget-object v0, p0, Lcom/samsung/android/sidegesturepad/SGPService;->h:Lcom/samsung/android/sidegesturepad/SGPService;\n"
        f"    invoke-static {{v0}}, {COMPAT}->ensureForegroundService(Landroid/app/Service;)V\n"
        "    :cond_0\n"
        "    return-void"
    )
    t = replace_method_body(t, "public final b(Z)V", b_body, "SGPService b(Z)")

    # semDisplayDeviceType -> 0
    t = replace_exact(
        t,
        "    iget v4, v2, Landroid/content/res/Configuration;->semDisplayDeviceType:I",
        "    const/4 v4, 0x0",
        "SGPService onConfigurationChanged semDisplayDeviceType v4",
    )
    t = replace_exact(
        t,
        "    iget v5, p1, Landroid/content/res/Configuration;->semDisplayDeviceType:I",
        "    const/4 v5, 0x0",
        "SGPService onConfigurationChanged semDisplayDeviceType v5",
    )

    # Call ensureForegroundService right inside onCreate (after super.onCreate)
    t = replace_regex(
        t,
        r"(\.method public final onCreate\(\)V\s+\.locals \d+\s+(?:\.line \d+\s+)?invoke-super \{p0\}, Landroid/app/Service;->onCreate\(\)V)",
        rf"\1\n    invoke-static {{p0}}, {COMPAT}->ensureForegroundService(Landroid/app/Service;)V",
        "SGPService onCreate ensureForegroundService",
    )
    # Also ensureForegroundService in onStartCommand (right after move-object/from16 v1, p0)
    t = replace_regex(
        t,
        r"(\.method public final onStartCommand\(Landroid/content/Intent;II\)I\s+\.locals 39\s+(?:\.line \d+\s+)?move-object/from16 v1, p0)",
        rf"\1\n    invoke-static {{v1}}, {COMPAT}->ensureForegroundService(Landroid/app/Service;)V",
        "SGPService onStartCommand ensureForegroundService",
    )

    write_text(rel, t)
    print("Patched SGPService.smali")


def patch_s6_z():
    rel = "smali/s6/z.smali"
    t = read_text(rel)

    # 1. OS check g1(Context) -> VivoCompat.isSupportedOS
    t = replace_method_body(
        t,
        "public static g1(Landroid/content/Context;)Z",
        f"    .locals 1\n\n    invoke-static {{p0}}, {COMPAT}->isSupportedOS(Landroid/content/Context;)Z\n    move-result v0\n    return v0",
        "s6/z g1",
    )

    # 2. Static Sem helpers
    t = replace_method_body(
        t,
        "public static A()I",
        "    .locals 1\n\n    const/4 v0, 0x0\n    return v0",
        "s6/z A()",
    )
    t = replace_method_body(
        t,
        "public static b1()Z",
        "    .locals 1\n\n    const/4 v0, 0x0\n    return v0",
        "s6/z b1()",
    )
    t = replace_method_body(
        t,
        "public static h1()Z",
        "    .locals 1\n\n    const/4 v0, 0x0\n    return v0",
        "s6/z h1()",
    )
    t = replace_method_body(
        t,
        "public static y0()Z",
        "    .locals 1\n\n    const/4 v0, 0x1\n    return v0",
        "s6/z y0()",
    )

    # 3. n(AppWidgetProviderInfo) -> configure
    t = replace_exact(
        t,
        "iget-object v0, p0, Landroid/appwidget/AppWidgetProviderInfo;->semConfigure:Landroid/content/ComponentName;",
        "iget-object v0, p0, Landroid/appwidget/AppWidgetProviderInfo;->configure:Landroid/content/ComponentName;",
        "s6/z n() semConfigure",
    )

    # 4. semDisplayDeviceType -> 0
    t = replace_exact(
        t,
        "    iget p0, p0, Landroid/content/res/Configuration;->semDisplayDeviceType:I",
        "    const/4 p0, 0x0",
        "s6/z z0 semDisplayDeviceType",
    )
    t = replace_exact(
        t,
        "    iget p1, p1, Landroid/content/res/Configuration;->semDisplayDeviceType:I",
        "    const/4 p1, 0x0",
        "s6/z updateConfig semDisplayDeviceType",
    )

    # 5. A0() desktop mode -> false
    t = replace_method_body(
        t,
        "public final A0()Z",
        "    .locals 1\n\n    const/4 v0, 0x0\n    return v0",
        "s6/z A0()",
    )
    # Remove remaining semDesktopModeEnabled refs inside constructor/methods
    t = replace_exact(
        t,
        "    iget v3, v3, Landroid/content/res/Configuration;->semDesktopModeEnabled:I",
        "    const/4 v3, 0x0",
        "s6/z semDesktopModeEnabled v3",
    )
    t = replace_exact(
        t,
        "    iget v4, v4, Landroid/content/res/Configuration;->semDesktopModeEnabled:I",
        "    const/4 v4, 0x0",
        "s6/z semDesktopModeEnabled v4",
    )
    # Replace SemDesktopModeManager check in r0/update
    t = replace_regex(
        t,
        r"    const-class v5, Lcom/samsung/android/desktopmode/SemDesktopModeManager;(?:(?!\.method).){1,900}if-ne v3, v6, :cond_9(?:\s+\.line \d+)*\s+move v3, v5(?:\s+\.line \d+)*\s+goto :goto_7",
        "    const/4 v5, 0x1\n    const/4 v3, 0x0\n    goto :goto_7",
        "s6/z SemDesktopModeManager",
    )

    # 6. SemStatusBarManager init inside r0(Context) -> remove class lookup + change field type to Object so ART never resolves SemStatusBarManager
    t = t.replace("Landroid/app/SemStatusBarManager;", "Ljava/lang/Object;")
    t = replace_regex(
        t,
        r"    const-class v1, Ljava/lang/Object;(?:(?!\.method).){1,400}iput-object p1, p0, Ls6/z;->l:Ljava/lang/Object;",
        "    const/4 p1, 0x0\n    iput-object p1, p0, Ls6/z;->l:Ljava/lang/Object;",
        "s6/z r0 SemStatusBarManager",
    )
    t = replace_regex(
        t,
        r"    iget-object (v\d+|p\d+), (p\d+), Ls6/z;->l:Ljava/lang/Object;(?:\s+\.line \d+)*\s+invoke-virtual \{\1\}, Ljava/lang/Object;->isPanelExpanded\(\)Z",
        rf"    invoke-static {{}}, {COMPAT}->isPanelExpanded()Z",
        "s6/z inline isPanelExpanded",
        count=6,
    )

    # 7. StatusBar panel methods -> VivoCompat
    t = replace_method_body(
        t,
        "public final W0()Z",
        f"    .locals 1\n\n    invoke-static {{}}, {COMPAT}->isPanelExpanded()Z\n    move-result v0\n    return v0",
        "s6/z W0",
    )
    t = replace_method_body(
        t,
        "public final q0()V",
        f"    .locals 1\n\n    iget-object v0, p0, Ls6/z;->b:Landroid/content/Context;\n    invoke-static {{v0}}, {COMPAT}->collapsePanels(Landroid/content/Context;)V\n    return-void",
        "s6/z q0",
    )
    t = replace_method_body(
        t,
        "public final q1()V",
        "    .locals 1\n\n"
        f"    invoke-static {{}}, {COMPAT}->isPanelExpanded()Z\n"
        "    move-result v0\n"
        "    if-eqz v0, :cond_0\n"
        "    iget-object v0, p0, Ls6/z;->b:Landroid/content/Context;\n"
        f"    invoke-static {{v0}}, {COMPAT}->collapsePanels(Landroid/content/Context;)V\n"
        "    return-void\n"
        "    :cond_0\n"
        "    iget-object v0, p0, Ls6/z;->b:Landroid/content/Context;\n"
        f"    invoke-static {{v0}}, {COMPAT}->expandNotificationsPanel(Landroid/content/Context;)V\n"
        "    return-void",
        "s6/z q1",
    )
    t = replace_method_body(
        t,
        "public final r1()V",
        "    .locals 1\n\n"
        f"    invoke-static {{}}, {COMPAT}->isPanelExpanded()Z\n"
        "    move-result v0\n"
        "    if-eqz v0, :cond_0\n"
        "    iget-object v0, p0, Ls6/z;->b:Landroid/content/Context;\n"
        f"    invoke-static {{v0}}, {COMPAT}->collapsePanels(Landroid/content/Context;)V\n"
        "    return-void\n"
        "    :cond_0\n"
        "    iget-object v0, p0, Ls6/z;->b:Landroid/content/Context;\n"
        f"    invoke-static {{v0}}, {COMPAT}->expandQuickSettingsPanel(Landroid/content/Context;)V\n"
        "    return-void",
        "s6/z r1",
    )

    # 8. StartService / StartForegroundService calls
    t = t.replace(
        "invoke-virtual {v0, v1}, Landroid/content/Context;->startService(Landroid/content/Intent;)Landroid/content/ComponentName;",
        f"invoke-static {{v0, v1}}, {COMPAT}->startServiceCompat(Landroid/content/Context;Landroid/content/Intent;)Landroid/content/ComponentName;",
    )
    t = t.replace(
        "invoke-virtual {p0, v0}, Landroid/content/Context;->startService(Landroid/content/Intent;)Landroid/content/ComponentName;",
        f"invoke-static {{p0, v0}}, {COMPAT}->startServiceCompat(Landroid/content/Context;Landroid/content/Intent;)Landroid/content/ComponentName;",
    )
    t = t.replace(
        "invoke-virtual {p0, v1}, Landroid/content/Context;->startService(Landroid/content/Intent;)Landroid/content/ComponentName;",
        f"invoke-static {{p0, v1}}, {COMPAT}->startServiceCompat(Landroid/content/Context;Landroid/content/Intent;)Landroid/content/ComponentName;",
    )

    # 9. v1(IIII)V (key injection) & w1(IIIJ)V / c(MotionEvent)V (touch injection)
    t = replace_method_body(
        t,
        "public final v1(IIII)V",
        "    .locals 1\n\n"
        "    iget-object v0, p0, Ls6/z;->b:Landroid/content/Context;\n"
        f"    invoke-static {{v0, p1, p2, p3, p4}}, {COMPAT}->injectKeyEvent(Landroid/content/Context;IIII)V\n"
        "    return-void",
        "s6/z v1",
    )
    t = replace_method_body(
        t,
        "public final c(Landroid/view/MotionEvent;)V",
        "    .locals 1\n\n"
        "    iget-object v0, p0, Ls6/z;->b:Landroid/content/Context;\n"
        f"    invoke-static {{v0, p1}}, {COMPAT}->injectTouchMotion(Landroid/content/Context;Landroid/view/MotionEvent;)V\n"
        "    return-void",
        "s6/z c(MotionEvent)",
    )

    # 10. Brightness min/max, timeout, ringer, hotspot, rotation, sound mode, vibrator
    t = replace_method_body(
        t,
        "public final L()I",
        f"    .locals 1\n\n    invoke-static {{}}, {COMPAT}->getMaxBrightness()I\n    move-result v0\n    return v0",
        "s6/z L()",
    )
    t = replace_method_body(
        t,
        "public final M()I",
        f"    .locals 1\n\n    invoke-static {{}}, {COMPAT}->getMinBrightness()I\n    move-result v0\n    return v0",
        "s6/z M()",
    )
    t = replace_method_body(
        t,
        "public final U()I",
        f"    .locals 1\n\n    iget-object v0, p0, Ls6/z;->b:Landroid/content/Context;\n    invoke-static {{v0}}, {COMPAT}->getScreenTimeoutSec(Landroid/content/Context;)I\n    move-result v0\n    return v0",
        "s6/z U()",
    )
    t = replace_method_body(
        t,
        "public final Y0()Z",
        f"    .locals 1\n\n    iget-object v0, p0, Ls6/z;->b:Landroid/content/Context;\n    invoke-static {{v0}}, {COMPAT}->isRotationLocked(Landroid/content/Context;)Z\n    move-result v0\n    return v0",
        "s6/z Y0()",
    )
    t = replace_method_body(
        t,
        "public static synthetic a(Ls6/z;Z)V",
        f"    .locals 1\n\n    iget-object v0, p0, Ls6/z;->b:Landroid/content/Context;\n    invoke-static {{v0, p1}}, {COMPAT}->toggleUserRotation(Landroid/content/Context;Z)V\n    return-void",
        "s6/z a(Z)",
    )
    t = replace_method_body(
        t,
        "public final c2()Z",
        f"    .locals 1\n\n    iget-object v0, p0, Ls6/z;->b:Landroid/content/Context;\n    invoke-static {{v0}}, {COMPAT}->toggleRotation(Landroid/content/Context;)Z\n    move-result v0\n    return v0",
        "s6/z c2() toggleRotation",
    )
    t = replace_method_body(
        t,
        "public final H0()Z",
        "    .locals 1\n\n    const/4 v0, 0x0\n    return v0",
        "s6/z H0()",
    )
    t = replace_method_body(
        t,
        "public final b2()V",
        f"    .locals 1\n\n    iget-object v0, p0, Ls6/z;->b:Landroid/content/Context;\n    invoke-static {{v0}}, {COMPAT}->toggleHotspot(Landroid/content/Context;)V\n    return-void",
        "s6/z b2()",
    )
    t = replace_method_body(
        t,
        "public final e2()V",
        f"    .locals 1\n\n    iget-object v0, p0, Ls6/z;->b:Landroid/content/Context;\n    invoke-static {{v0}}, {COMPAT}->toggleSoundMode(Landroid/content/Context;)V\n    return-void",
        "s6/z e2()",
    )
    t = replace_method_body(
        t,
        "public final d2()V",
        f"    .locals 2\n\n    iget-object v0, p0, Ls6/z;->b:Landroid/content/Context;\n    const-string v1, \"Screen recording unavailable via OHO+ on Vivo\"\n    const/4 p0, 0x0\n    invoke-static {{v0, v1, p0}}, Landroid/widget/Toast;->makeText(Landroid/content/Context;Ljava/lang/CharSequence;I)Landroid/widget/Toast;\n    move-result-object p0\n    invoke-virtual {{p0}}, Landroid/widget/Toast;->show()V\n    return-void",
        "s6/z d2()",
    )
    t = replace_method_body(
        t,
        "public final i2(Landroid/view/View;)V",
        "    .locals 2\n\n"
        "    iget-object v0, p0, Ls6/z;->J:Ls6/c;\n"
        "    iget-boolean v1, v0, Ls6/c;->c:Z\n"
        "    if-eqz v1, :cond_0\n"
        "    iget v1, v0, Ls6/c;->u:I\n"
        "    if-lez v1, :cond_1\n"
        "    iget-object p0, p0, Ls6/z;->b:Landroid/content/Context;\n"
        f"    invoke-static {{p0, v1}}, {COMPAT}->vibrateCustom(Landroid/content/Context;I)V\n"
        "    return-void\n"
        "    :cond_0\n"
        "    iget-object p0, p0, Ls6/z;->b:Landroid/content/Context;\n"
        f"    invoke-static {{p0}}, {COMPAT}->vibrateNormal(Landroid/content/Context;)V\n"
        "    :cond_1\n"
        "    return-void",
        "s6/z i2(View)",
    )

    # 11. Replace inline sem* calls in s6/z
    t = t.replace(
        "invoke-virtual {p1}, Landroid/media/AudioManager;->semGetRingerModeInternal()I",
        f"invoke-static {{p1}}, {COMPAT}->getRingerMode(Landroid/media/AudioManager;)I",
    )
    t = t.replace(
        "invoke-virtual {p0}, Landroid/media/AudioManager;->semGetRingerModeInternal()I",
        f"invoke-static {{p0}}, {COMPAT}->getRingerMode(Landroid/media/AudioManager;)I",
    )
    t = replace_regex(
        t,
        r"    invoke-virtual \{p0\}, Landroid/os/Vibrator;->semGetSupportedVibrationType\(\)I(?:\s+\.line \d+)*\s+move-result p0",
        "    const/4 p0, 0x0",
        "s6/z semGetSupportedVibrationType",
    )
    t = t.replace(
        "invoke-virtual {p1}, Landroid/app/KeyguardManager;->semIsKeyguardShowingAndNotOccluded()Z",
        f"invoke-static {{p1}}, {COMPAT}->isKeyguardShowingAndNotOccluded(Landroid/app/KeyguardManager;)Z",
    )
    t = t.replace(
        "invoke-virtual {p0}, Landroid/view/inputmethod/InputMethodManager;->semForceHideSoftInput()Z",
        f"invoke-static {{p0}}, {COMPAT}->forceHideSoftInput(Landroid/view/inputmethod/InputMethodManager;)Z",
    )
    t = t.replace(
        "invoke-virtual {p0, p1, v2}, Landroid/content/pm/PackageManager;->semGetActivityIconForIconTray(Landroid/content/ComponentName;I)Landroid/graphics/drawable/Drawable;",
        f"invoke-static {{p0, p1}}, {COMPAT}->getActivityIcon(Landroid/content/pm/PackageManager;Landroid/content/ComponentName;)Landroid/graphics/drawable/Drawable;",
    )
    t = t.replace(
        "invoke-static {}, Landroid/app/ActivityManager;->semGetCurrentUser()I",
        f"invoke-static {{}}, {COMPAT}->getCurrentUserId()I",
    )
    t = t.replace(
        "invoke-static {p3}, Landroid/os/UserHandle;->semOf(I)Landroid/os/UserHandle;",
        f"invoke-static {{}}, {COMPAT}->getOwnerUserHandle()Landroid/os/UserHandle;",
    )
    t = t.replace(
        "invoke-static {p2}, Landroid/os/UserHandle;->semOf(I)Landroid/os/UserHandle;",
        f"invoke-static {{}}, {COMPAT}->getOwnerUserHandle()Landroid/os/UserHandle;",
    )
    t = t.replace(
        "invoke-static {v3}, Landroid/os/UserHandle;->semOf(I)Landroid/os/UserHandle;",
        f"invoke-static {{}}, {COMPAT}->getOwnerUserHandle()Landroid/os/UserHandle;",
    )
    t = t.replace(
        "invoke-static {v8}, Landroid/os/UserHandle;->semOf(I)Landroid/os/UserHandle;",
        f"invoke-static {{}}, {COMPAT}->getOwnerUserHandle()Landroid/os/UserHandle;",
    )
    t = t.replace(
        "invoke-static {v4}, Landroid/os/SemSystemProperties;->get(Ljava/lang/String;)Ljava/lang/String;",
        f"invoke-static {{v4}}, {COMPAT}->getSystemProperty(Ljava/lang/String;)Ljava/lang/String;",
    )
    t = t.replace(
        "invoke-static {v1, v4, v2, v3}, Landroid/provider/Settings$System;->semPutIntForUser(Landroid/content/ContentResolver;Ljava/lang/String;II)Z",
        "invoke-static {v1, v4, v2}, Landroid/provider/Settings$System;->putInt(Landroid/content/ContentResolver;Ljava/lang/String;I)Z",
    )
    t = t.replace(
        "invoke-static {p0, v1, v2, v3}, Landroid/provider/Settings$System;->semPutIntForUser(Landroid/content/ContentResolver;Ljava/lang/String;II)Z",
        "invoke-static {p0, v1, v2}, Landroid/provider/Settings$System;->putInt(Landroid/content/ContentResolver;Ljava/lang/String;I)Z",
    )
    t = t.replace(
        "invoke-static {v0, v1, v2, v3}, Landroid/provider/Settings$System;->semGetIntForUser(Landroid/content/ContentResolver;Ljava/lang/String;II)I",
        "invoke-static {v0, v1, v2}, Landroid/provider/Settings$System;->getInt(Landroid/content/ContentResolver;Ljava/lang/String;I)I",
    )
    t = t.replace(
        "invoke-virtual {v2, v0, v1}, Landroid/content/Intent;->semSetLaunchOverTargetTask(IZ)V",
        "nop",
    )
    t = replace_regex(
        t,
        r'    const-string v0, "persona"(?:(?!\.method).){1,400}invoke-virtual \{v0\}, Lcom/samsung/android/knox/SemPersonaManager;->getFocusedKnoxId\(\)I(?:\s+\.line \d+)*\s+move-result v2',
        "    const/4 v2, 0x0",
        "s6/z SemPersonaManager",
    )
    t = replace_regex(
        t,
        r"    invoke-static \{v2\}, Lcom/samsung/android/app/SemDualAppManager;->isDualAppId\(I\)Z(?:\s+\.line \d+)*\s+move-result (v\d+)",
        r"    const/4 \1, 0x0",
        "s6/z SemDualAppManager",
        count=1,
    )
    t = t.replace(
        "invoke-virtual {p0, v0, v1}, Landroid/content/Context;->semStartServiceAsUser(Landroid/content/Intent;Landroid/os/UserHandle;)Landroid/content/ComponentName;",
        f"invoke-static {{p0, v0}}, {COMPAT}->startServiceAsUserCompat(Landroid/content/Context;Landroid/content/Intent;)Landroid/content/ComponentName;",
    )
    # 12. StartActivityAsUser reflection fallback in SGP shortcut / widget / previous app launchers -> standard startActivity
    t = replace_regex(
        t,
        r'    const-string v5, "startActivityAsUser"(?:(?!\.method).){1,400}invoke-virtual \{v0, p0, v5, v4, p2\}, Lg5/a;->t\(Ljava/lang/Object;Ljava/lang/String;\[Ljava/lang/Class;\[Ljava/lang/Object;\)Ljava/lang/Object;',
        "    invoke-virtual {p0, v2}, Landroid/content/Context;->startActivity(Landroid/content/Intent;)V",
        "s6/z startActivityAsUser 1",
    )
    if "invoke-virtual {v3, p0, v4, p2, p1}, Lg5/a;->t" in t:
        t = replace_exact(
            t,
            "    invoke-virtual {v3, p0, v4, p2, p1}, Lg5/a;->t(Ljava/lang/Object;Ljava/lang/String;[Ljava/lang/Class;[Ljava/lang/Object;)Ljava/lang/Object;",
            "    invoke-virtual {p0, v2}, Landroid/content/Context;->startActivity(Landroid/content/Intent;)V",
            "s6/z startActivityAsUser 2",
        )

    # Route setEdgeBackGestureDisablePolicy -> VivoCompat.setEdgeBackGestureDisabled
    t = replace_regex(
        t,
        r"    iget-object p0, p0, Ls6/z;->b:Landroid/content/Context;(?:\s+\.line \d+)*\s+invoke-virtual \{p0\}, Landroid/content/Context;->getContentResolver\(\)Landroid/content/ContentResolver;(?:(?!\.method).){1,400}\"navigation_bar_gesture_disabled_by_policy\"(?:\s+\.line \d+)*\s+invoke-static \{p0, v0, p1\}, Landroid/provider/Settings\$Global;->putInt\(Landroid/content/ContentResolver;Ljava/lang/String;I\)Z",
        f"    iget-object p0, p0, Ls6/z;->b:Landroid/content/Context;\n    invoke-static {{p0, p1}}, {COMPAT}->setEdgeBackGestureDisabled(Landroid/content/Context;Z)V",
        "s6/z setEdgeBackGestureDisablePolicy",
    )

    # Wire f1(String) -> VivoCompat.isActionSupported + allow run_searcle (Circle to Search)
    t = replace_regex(
        t,
        r"(\.method public final f1\(Ljava/lang/String;\)Z\s+\.locals 13\s+(?:\.line \d+\s+)?)",
        rf"\1iget-object v0, p0, Ls6/z;->b:Landroid/content/Context;\n"
        rf"    invoke-static {{v0, p1}}, {COMPAT}->isActionSupported(Landroid/content/Context;Ljava/lang/String;)Z\n"
        r"    move-result v0\n"
        r"    if-nez v0, :cond_vivo_sup\n"
        r"    const/4 v0, 0x0\n"
        r"    return v0\n"
        r"    :cond_vivo_sup\n",
        "s6/z f1 isActionSupported",
    )
    t = replace_regex(
        t,
        r'    const-string v0, "run_searcle"(?:\s+\.line \d+)*\s+invoke-virtual \{v0, p1\}, Ljava/lang/String;->equals\(Ljava/lang/Object;\)Z(?:\s+\.line \d+)*\s+move-result v0(?:\s+\.line \d+)*\s+if-eqz v0, :cond_1f(?:\s+\.line \d+)*\s+(?:goto/16|goto) :goto_a',
        '    const-string v0, "run_searcle"\n'
        '    invoke-virtual {v0, p1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n'
        '    move-result v0\n'
        '    if-eqz v0, :cond_1f\n'
        '    goto/16 :goto_9',
        "s6/z f1 allow run_searcle",
    )

    write_text(rel, t)
    print("Patched s6/z.smali")


def patch_w5_f():
    rel = "smali/w5/f.smali"
    t = read_text(rel)

    v_start = t.index(".method public final V(")
    v_end = t.index("\n.end method", v_start) + len("\n.end method")
    v = t[v_start:v_end]

    v = replace_exact(
        v,
        "    move-object/from16 v5, p5",
        f"    move-object/from16 v5, p5\n    invoke-static {{v2, v0, v3}}, {COMPAT}->recordActionDebug(Ljava/lang/String;II)V",
        "w5/f recordActionDebug",
    )

    # actionLaunchAssist (:pswitch_1) -> VivoCompat.launchAssistant(v12)
    v = replace_regex(
        v,
        r"    :cond_64(?:\s+\.line \d+)*\s+new-instance v0, Lw5/a;(?:(?!\.method).){1,350}invoke-virtual \{v15, v0, v1, v2\}, Landroid/os/Handler;->postDelayed\(Ljava/lang/Runnable;J\)Z(?:\s+\.line \d+)*\s+return v17",
        f"    :cond_64\n    invoke-static {{v12}}, {COMPAT}->launchAssistant(Landroid/content/Context;)V\n    return v17",
        "w5/f actionLaunchAssist",
    )

    # actionCircleToSearch (:pswitch_36) -> VivoCompat.launchSearcle(v12)
    v = replace_regex(
        v,
        r"    :cond_b4(?:\s+\.line \d+)*\s+iget-object v0, v10, Ls6/z;->j:Landroid/os/Handler;(?:(?!\.method).){1,350}invoke-virtual \{v0, v1\}, Landroid/os/Handler;->post\(Ljava/lang/Runnable;\)Z(?:\s+\.line \d+)*\s+return v2",
        f"    :cond_b4\n    invoke-static {{v12}}, {COMPAT}->launchSearcle(Landroid/content/Context;)V\n    return v2",
        "w5/f actionCircleToSearch",
    )

    # actionToggleFlash (:pswitch_7) -> replace body inside :pswitch_7 (preserving :goto_22)
    flash_start = v.index("    :pswitch_7\n")
    flash_end = v.index("    :pswitch_8\n")
    v = (
        v[:flash_start]
        + "    :pswitch_7\n"
        "    const/16 v17, 0x1\n"
        f"    invoke-static {{v12}}, {COMPAT}->toggleFlashlight(Landroid/content/Context;)Z\n"
        "    move-result v0\n"
        "    iput-boolean v0, v10, Ls6/z;->Y:Z\n"
        "    invoke-virtual {v1}, Lw5/f;->Y()V\n"
        "    return v17\n"
        "    :goto_22\n"
        "    const/4 v2, 0x1\n"
        "    return v2\n\n"
        + v[flash_end:]
    )

    # actionToggleAirplaneMode (:pswitch_3) -> VivoCompat.toggleAirplane
    ap_start = v.index("    :pswitch_3\n")
    ap_end = v.index("    :pswitch_4\n")
    v = (
        v[:ap_start]
        + "    :pswitch_3\n"
        "    const/16 v17, 0x1\n"
        f"    invoke-static {{v12}}, {COMPAT}->toggleAirplane(Landroid/content/Context;)V\n"
        "    invoke-virtual {v1}, Lw5/f;->Y()V\n"
        "    return v17\n\n"
        + v[ap_end:]
    )

    # actionToggleWifi (:pswitch_4) -> VivoCompat.toggleWifi
    wifi_start = v.index("    :pswitch_4\n")
    wifi_end = v.index("    :pswitch_5\n")
    v = (
        v[:wifi_start]
        + "    :pswitch_4\n"
        "    const/16 v17, 0x1\n"
        f"    invoke-static {{v12}}, {COMPAT}->toggleWifi(Landroid/content/Context;)V\n"
        "    invoke-virtual {v1}, Lw5/f;->Y()V\n"
        "    return v17\n\n"
        + v[wifi_end:]
    )

    # actionToggleDndMode (:pswitch_b) -> VivoCompat.toggleDnd
    dnd_start = v.index("    :pswitch_b\n")
    dnd_end = v.index("    :pswitch_c\n")
    v = (
        v[:dnd_start]
        + "    :pswitch_b\n"
        "    const/16 v17, 0x1\n"
        f"    invoke-static {{v12}}, {COMPAT}->toggleDnd(Landroid/content/Context;)V\n"
        "    invoke-virtual {v1}, Lw5/f;->Y()V\n"
        "    return v17\n\n"
        + v[dnd_end:]
    )

    # actionToggleMobileData (:pswitch_0) -> VivoCompat.toggleMobileData
    md_start = v.index("    :pswitch_0\n")
    md_end = v.index("    :pswitch_1\n")
    v = (
        v[:md_start]
        + "    :pswitch_0\n"
        "    const/16 v17, 0x1\n"
        f"    invoke-static {{v12}}, {COMPAT}->toggleMobileData(Landroid/content/Context;)V\n"
        "    invoke-virtual {v1}, Lw5/f;->Y()V\n"
        "    return v17\n\n"
        + v[md_end:]
    )

    # actionToggleNFC (:pswitch_a) -> VivoCompat.toggleNfc
    nfc_start = v.index("    :pswitch_a\n")
    nfc_end = v.index("    :pswitch_b\n")
    v = (
        v[:nfc_start]
        + "    :pswitch_a\n"
        "    const/16 v17, 0x1\n"
        f"    invoke-static {{v12}}, {COMPAT}->toggleNfc(Landroid/content/Context;)V\n"
        "    invoke-virtual {v1}, Lw5/f;->Y()V\n"
        "    return v17\n\n"
        + v[nfc_end:]
    )

    # actionToggleNavibar (:pswitch_c) -> VivoCompat.toggleNavBar
    nav_start = v.index("    :pswitch_c\n")
    nav_end = v.index("    :pswitch_d\n")
    v = (
        v[:nav_start]
        + "    :pswitch_c\n"
        "    const/16 v17, 0x1\n"
        f"    invoke-static {{v12}}, {COMPAT}->toggleNavBar(Landroid/content/Context;)V\n"
        "    invoke-virtual {v1}, Lw5/f;->Y()V\n"
        "    return v17\n\n"
        + v[nav_end:]
    )

    # actionColorInversion (:pswitch_14) -> VivoCompat.toggleColorInversion
    ci_start = v.index("    :pswitch_14\n")
    ci_end = v.index("    :pswitch_15\n")
    v = (
        v[:ci_start]
        + "    :pswitch_14\n"
        "    const/16 v17, 0x1\n"
        f"    invoke-static {{v12}}, {COMPAT}->toggleColorInversion(Landroid/content/Context;)V\n"
        "    invoke-virtual {v1}, Lw5/f;->Y()V\n"
        "    return v17\n\n"
        + v[ci_end:]
    )

    # actionToggleBlueLightFilter (:pswitch_1b) -> VivoCompat.toggleBlueLightFilter
    v = replace_regex(
        v,
        r"    :cond_ae(?:\s+\.line \d+)*\s+invoke-virtual \{v12\}, Landroid/content/Context;->getContentResolver\(\)Landroid/content/ContentResolver;(?:(?!\.method).){1,700}invoke-virtual \{v1\}, Lw5/f;->Y\(\)V",
        f"    :cond_ae\n    invoke-static {{v12}}, {COMPAT}->toggleBlueLightFilter(Landroid/content/Context;)V\n    invoke-virtual {{v1}}, Lw5/f;->Y()V",
        "w5/f actionToggleBlueLightFilter",
    )

    t = t[:v_start] + v + t[v_end:]

    # Replace helper methods on w5/f
    t = replace_method_body(
        t,
        "public final A()V",
        f"    .locals 1\n\n    iget-object v0, p0, Lw5/f;->a:Landroid/content/Context;\n    invoke-static {{v0}}, {COMPAT}->expandQuickSettingsPanel(Landroid/content/Context;)V\n    invoke-virtual {{p0}}, Lw5/f;->Y()V\n    return-void",
        "w5/f A() split_quick_panel",
    )
    t = replace_method_body(
        t,
        "public final i()V",
        f"    .locals 1\n\n    invoke-virtual {{p0}}, Lw5/f;->O()Z\n    move-result v0\n    if-eqz v0, :cond_0\n    return-void\n    :cond_0\n    iget-object v0, p0, Lw5/f;->a:Landroid/content/Context;\n    invoke-static {{v0}}, {COMPAT}->toggleSplitScreen(Landroid/content/Context;)V\n    invoke-virtual {{p0}}, Lw5/f;->Y()V\n    return-void",
        "w5/f i() split_view",
    )
    t = replace_method_body(
        t,
        "public final k()V",
        f"    .locals 1\n\n    invoke-virtual {{p0}}, Lw5/f;->O()Z\n    move-result v0\n    if-eqz v0, :cond_0\n    return-void\n    :cond_0\n    iget-object v0, p0, Lw5/f;->a:Landroid/content/Context;\n    invoke-static {{v0}}, {COMPAT}->launchPreviousApp(Landroid/content/Context;)V\n    invoke-virtual {{p0}}, Lw5/f;->Y()V\n    return-void",
        "w5/f k() previous_app",
    )
    t = replace_method_body(
        t,
        "public final r()V",
        f"    .locals 1\n\n    iget-object v0, p0, Lw5/f;->a:Landroid/content/Context;\n    invoke-static {{v0}}, {COMPAT}->showGlobalActions(Landroid/content/Context;)V\n    invoke-virtual {{p0}}, Lw5/f;->Y()V\n    return-void",
        "w5/f r() global_actions",
    )
    t = replace_method_body(
        t,
        "public final y()V",
        f"    .locals 1\n\n    iget-object v0, p0, Lw5/f;->a:Landroid/content/Context;\n    invoke-static {{v0}}, {COMPAT}->toggleNightMode(Landroid/content/Context;)V\n    invoke-virtual {{p0}}, Lw5/f;->Y()V\n    return-void",
        "w5/f y() night_mode",
    )
    t = replace_method_body(
        t,
        "public final m()V",
        "    .locals 3\n\n"
        "    iget-object v0, p0, Lw5/f;->c:Lr6/f;\n"
        "    const-wide/16 v1, 0x190\n"
        "    if-eqz v0, :cond_0\n"
        "    invoke-virtual {v0, v1, v2}, Lr6/f;->k(J)V\n"
        "    :cond_0\n"
        "    iget-object v0, p0, Lw5/f;->d:Lr6/f;\n"
        "    if-eqz v0, :cond_1\n"
        "    invoke-virtual {v0, v1, v2}, Lr6/f;->k(J)V\n"
        "    :cond_1\n"
        "    iget-object v0, p0, Lw5/f;->a:Landroid/content/Context;\n"
        f"    invoke-static {{v0}}, {COMPAT}->takeScreenshot(Landroid/content/Context;)V\n"
        "    invoke-virtual {p0}, Lw5/f;->Y()V\n"
        "    return-void",
        "w5/f m() screen_capture",
    )
    t = replace_method_body(
        t,
        "public final w()V",
        "    .locals 1\n\n"
        "    iget-object v0, p0, Lw5/f;->a:Landroid/content/Context;\n"
        f"    invoke-static {{v0}}, {COMPAT}->toggleBluetooth(Landroid/content/Context;)V\n"
        "    invoke-virtual {p0}, Lw5/f;->Y()V\n"
        "    return-void",
        "w5/f w() bluetooth",
    )
    t = replace_regex(
        t,
        r"    :pswitch_10[\s\S]*?invoke-virtual \{v1, v0\}, Lw5/f;->p\(I\)V(?:\s+\.line \d+)*\s+return v3",
        "    :pswitch_10\n"
        "    iget-object v0, v1, Lw5/f;->a:Landroid/content/Context;\n"
        f"    invoke-static {{v0}}, {COMPAT}->expandNotificationsPanel(Landroid/content/Context;)V\n"
        "    invoke-virtual {v1}, Lw5/f;->Y()V\n"
        "    const/4 v3, 0x1\n"
        "    return v3",
        "w5/f :pswitch_10 notipanel",
    )

    write_text(rel, t)
    print("Patched w5/f.smali")


def patch_other_smali():
    # 1. z5/c.smali (Quick Tools brightness, fine volume, icon tray)
    rel = "smali/z5/c.smali"
    t = read_text(rel)
    t = replace_exact(
        t,
        "    invoke-virtual {v1, v4, v5}, Landroid/content/pm/PackageManager;->semGetActivityIconForIconTray(Landroid/content/ComponentName;I)Landroid/graphics/drawable/Drawable;",
        f"    invoke-static {{v1, v4}}, {COMPAT}->getActivityIcon(Landroid/content/pm/PackageManager;Landroid/content/ComponentName;)Landroid/graphics/drawable/Drawable;",
        "z5/c icon",
    )
    t = replace_exact(
        t,
        "    invoke-virtual {p0, v0}, Landroid/media/AudioManager;->semGetFineVolume(I)I",
        f"    invoke-static {{p0}}, {COMPAT}->getFineVolume(Landroid/media/AudioManager;)I",
        "z5/c getFineVolume",
    )
    t = replace_exact(
        t,
        "    invoke-virtual {p0, v0, p1, v1}, Landroid/media/AudioManager;->semSetFineVolume(III)V",
        f"    invoke-static {{p0, p1}}, {COMPAT}->setFineVolume(Landroid/media/AudioManager;I)V",
        "z5/c setFineVolume",
    )
    t = replace_exact(
        t,
        "    invoke-virtual {v0}, Landroid/os/PowerManager;->semGetMinimumScreenBrightnessSetting()I",
        f"    invoke-static {{}}, {COMPAT}->getMinBrightness()I",
        "z5/c minBrightness",
    )
    t = replace_exact(
        t,
        "    invoke-virtual {v0}, Landroid/os/PowerManager;->semGetMaximumScreenBrightnessSetting()I",
        f"    invoke-static {{}}, {COMPAT}->getMaxBrightness()I",
        "z5/c maxBrightness",
    )
    t = replace_method_body(
        t,
        "public final c()I",
        f"    .locals 1\n\n    iget-object v0, p0, Lz5/c;->a:Landroid/content/Context;\n    invoke-static {{v0}}, {COMPAT}->getBrightness(Landroid/content/Context;)I\n    move-result v0\n    return v0",
        "z5/c getBrightnessLevel",
    )
    t = replace_method_body(
        t,
        "public final m(IZ)V",
        f"    .locals 1\n\n    iget-object v0, p0, Lz5/c;->a:Landroid/content/Context;\n    invoke-static {{v0, p1}}, {COMPAT}->setBrightness(Landroid/content/Context;I)V\n    return-void",
        "z5/c setBrightnessLevel",
    )
    t = replace_method_body(
        t,
        "public final l(I)Z",
        "    .locals 1\n\n"
        "    iget-object v0, p0, Lz5/c;->a:Landroid/content/Context;\n"
        f"    invoke-static {{v0, p1}}, {COMPAT}->handleMediaKey(Landroid/content/Context;I)Z\n"
        "    move-result v0\n"
        "    return v0",
        "z5/c l(I)Z mediaKey",
    )
    write_text(rel, t)

    # 2. s6/m.smali and q1/a.smali icons
    rel = "smali/s6/m.smali"
    t = read_text(rel)
    t = replace_exact(
        t,
        "    invoke-virtual {v6, p1, v4}, Landroid/content/pm/PackageManager;->semGetActivityIconForIconTray(Landroid/content/ComponentName;I)Landroid/graphics/drawable/Drawable;",
        f"    invoke-static {{v6, p1}}, {COMPAT}->getActivityIcon(Landroid/content/pm/PackageManager;Landroid/content/ComponentName;)Landroid/graphics/drawable/Drawable;",
        "s6/m activityIcon",
    )
    t = replace_exact(
        t,
        "    invoke-virtual {v8, v7, v4}, Landroid/content/pm/PackageManager;->semGetApplicationIconForIconTray(Landroid/content/pm/ApplicationInfo;I)Landroid/graphics/drawable/Drawable;",
        f"    invoke-static {{v8, v7}}, {COMPAT}->getApplicationIcon(Landroid/content/pm/PackageManager;Landroid/content/pm/ApplicationInfo;)Landroid/graphics/drawable/Drawable;",
        "s6/m appIcon",
    )
    write_text(rel, t)

    rel = "smali/q1/a.smali"
    t = read_text(rel)
    t = replace_exact(
        t,
        "    invoke-virtual {v2, v3, v4}, Landroid/content/pm/PackageManager;->semGetApplicationIconForIconTray(Ljava/lang/String;I)Landroid/graphics/drawable/Drawable;",
        f"    invoke-static {{v2, v3}}, {COMPAT}->getApplicationIcon(Landroid/content/pm/PackageManager;Ljava/lang/String;)Landroid/graphics/drawable/Drawable;",
        "q1/a appIcon",
    )
    write_text(rel, t)

    # 3. f5/f.smali & f5/a.smali & a4/h.smali
    rel = "smali/f5/a.smali"
    t = read_text(rel)
    t = replace_exact(
        t,
        "    invoke-static {}, Landroid/os/UserHandle;->semGetMyUserId()I",
        f"    invoke-static {{}}, {COMPAT}->getCurrentUserId()I",
        "f5/a semGetMyUserId",
    )
    write_text(rel, t)

    rel = "smali/f5/f.smali"
    t = read_text(rel)
    t = replace_exact(
        t,
        "    invoke-virtual {v6, v7, v10}, Landroid/content/pm/PackageManager;->semGetDrawableForIconTray(Landroid/graphics/drawable/Drawable;I)Landroid/graphics/drawable/Drawable;",
        f"    invoke-static {{v7}}, {COMPAT}->getDrawableForIconTray(Landroid/graphics/drawable/Drawable;)Landroid/graphics/drawable/Drawable;",
        "f5/f iconTray",
    )
    t = replace_exact(
        t,
        "    sget-object v2, Landroid/os/UserHandle;->SEM_OWNER:Landroid/os/UserHandle;",
        f"    invoke-static {{}}, {COMPAT}->getOwnerUserHandle()Landroid/os/UserHandle;\n    move-result-object v2",
        "f5/f SEM_OWNER",
    )
    t = replace_exact(
        t,
        "    invoke-static {}, Landroid/app/ActivityManager;->semGetCurrentUser()I",
        f"    invoke-static {{}}, {COMPAT}->getCurrentUserId()I",
        "f5/f semGetCurrentUser",
    )
    t = replace_regex(
        t,
        r"    new-instance v4, Lcom/samsung/android/app/SemMultiWindowManager;(?:(?!\.method).){1,250}invoke-virtual \{v4\}, Lcom/samsung/android/app/SemMultiWindowManager;->getMode\(\)I(?:\s+\.line \d+)*\s+move-result v5",
        "    const/4 v5, 0x0",
        "f5/f SemMultiWindowManager.getMode",
    )
    t = replace_regex(
        t,
        r"    invoke-virtual \{v4, p0\}, Lcom/samsung/android/app/SemMultiWindowManager;->getSupportedModes\(Landroid/content/pm/ResolveInfo;\)I(?:\s+\.line \d+)*\s+move-result p0",
        "    const/4 p0, 0x2",
        "f5/f SemMultiWindowManager.getSupportedModes",
    )
    # Remove SemExecutableManager check-cast that causes ClassCastException or NoClassDefFoundError
    t = t.replace("    check-cast v7, Lcom/samsung/android/app/SemExecutableManager;", "    nop")
    t = t.replace("    check-cast p0, Lcom/samsung/android/app/SemExecutableManager;", "    const/4 p0, 0x0")
    write_text(rel, t)

    # a4/h.smali -> fallback to VivoCompat.populateRecentTasks when list Lf5/f;->i is empty
    rel = "smali/a4/h.smali"
    t = read_text(rel)
    t = replace_regex(
        t,
        r"    :goto_e(?:\s+\.line \d+)*\s+new-instance v0, Ljava/lang/StringBuilder;",
        "    :goto_e\n"
        "    iget-object v3, v1, La4/h;->h:Ljava/lang/Object;\n"
        "    check-cast v3, Lf5/f;\n"
        "    iget-object v4, v3, Lf5/f;->i:Ljava/util/ArrayList;\n"
        "    if-eqz v4, :cond_vivo_recents_done\n"
        "    invoke-virtual {v4}, Ljava/util/ArrayList;->size()I\n"
        "    move-result v5\n"
        "    const/4 v6, 0x2\n"
        "    if-gt v5, v6, :cond_vivo_recents_done\n"
        "    iget-object v5, v3, Lf5/f;->g:Landroid/content/Context;\n"
        "    const/16 v6, 0x60\n"
        f"    invoke-static {{v5, v4, v6}}, {COMPAT}->populateRecentTasks(Landroid/content/Context;Ljava/util/List;I)V\n"
        "    :cond_vivo_recents_done\n"
        "    new-instance v0, Ljava/lang/StringBuilder;",
        "a4/h populateRecentTasks",
    )
    write_text(rel, t)

    # 4. s6/b.smali (SEM_OWNER), s6/p.smali (SEM_OWNER & SemExecutableManager)
    rel = "smali/s6/b.smali"
    t = read_text(rel)
    t = replace_exact(
        t,
        "    sget-object v3, Landroid/os/UserHandle;->SEM_OWNER:Landroid/os/UserHandle;",
        f"    invoke-static {{}}, {COMPAT}->getOwnerUserHandle()Landroid/os/UserHandle;\n    move-result-object v3",
        "s6/b SEM_OWNER",
        count=2,
    )
    write_text(rel, t)

    rel = "smali/s6/p.smali"
    t = read_text(rel)
    t = replace_exact(
        t,
        "    sget-object v1, Landroid/os/UserHandle;->SEM_OWNER:Landroid/os/UserHandle;",
        f"    invoke-static {{}}, {COMPAT}->getOwnerUserHandle()Landroid/os/UserHandle;\n    move-result-object v1",
        "s6/p SEM_OWNER v1",
    )
    t = replace_exact(
        t,
        "    sget-object v2, Landroid/os/UserHandle;->SEM_OWNER:Landroid/os/UserHandle;",
        f"    invoke-static {{}}, {COMPAT}->getOwnerUserHandle()Landroid/os/UserHandle;\n    move-result-object v2",
        "s6/p SEM_OWNER v2",
        count=3,
    )
    t = t.replace("    check-cast p0, Lcom/samsung/android/app/SemExecutableManager;", "    const/4 p0, 0x0")
    write_text(rel, t)

    # 5. s5/c.smali -> safe return on z(SGPService) so SemWindowManager doesn't crash
    rel = "smali/s5/c.smali"
    t = read_text(rel)
    t = replace_method_body(
        t,
        "public static z(Lcom/samsung/android/sidegesturepad/SGPService;)V",
        "    .locals 0\n\n    return-void",
        "s5/c z(SGPService)",
    )
    write_text(rel, t)

    # 6. d6/l.smali -> disable SemWindowManager screenshot call so ScreenMoveView doesn't crash
    rel = "smali/d6/l.smali"
    t = read_text(rel)
    t = replace_regex(
        t,
        r"    invoke-static \{\}, Lcom/samsung/android/view/SemWindowManager;->getInstance\(\)Lcom/samsung/android/view/SemWindowManager;(?:\s+\.line \d+)*\s+move-result-object v1",
        "    const/4 v1, 0x0",
        "d6/l SemWindowManager.getInstance",
    )
    t = replace_exact(
        t,
        "    const-class v0, Lcom/samsung/android/view/SemWindowManager;",
        "    const/4 v0, 0x0",
        "d6/l SemWindowManager.class",
    )
    write_text(rel, t)

    # 7. a7/c.smali
    rel = "smali/a7/c.smali"
    t = read_text(rel)
    t = replace_exact(
        t,
        "    invoke-static {v3}, Landroid/os/SemSystemProperties;->get(Ljava/lang/String;)Ljava/lang/String;",
        f"    invoke-static {{v3}}, {COMPAT}->getSystemProperty(Ljava/lang/String;)Ljava/lang/String;",
        "a7/c SemSystemProperties",
    )
    write_text(rel, t)

    # 8. SGPMoreSettingActivity semDisplayDeviceType + un-gate System back gesture (use_system_gesture)
    rel = "smali/com/samsung/android/sidegesturepad/settings/SGPMoreSettingActivity.smali"
    t = read_text(rel)
    t = replace_exact(
        t,
        "    iget p1, p1, Landroid/content/res/Configuration;->semDisplayDeviceType:I",
        "    const/4 p1, 0x0",
        "SGPMoreSettingActivity semDisplayDeviceType",
    )
    t = replace_regex(
        t,
        r"    :cond_8(?:\s+\.line \d+)*\s+invoke-static \{\}, Ls6/z;->u0\(\)Z(?:\s+\.line \d+)*\s+move-result p1",
        "    :cond_8\n    const/4 p1, 0x1",
        "SGPMoreSettingActivity show use_system_gesture",
    )
    t = replace_regex(
        t,
        r"    sget-object v0, Ls6/c;->E:Ls6/c;(?:\s+\.line \d+)*\s+invoke-static \{\}, Ls6/z;->u0\(\)Z(?:\s+\.line \d+)*\s+move-result v1",
        "    sget-object v0, Ls6/c;->E:Ls6/c;\n    const/4 v1, 0x1",
        "SGPMoreSettingActivity check use_system_gesture",
    )
    write_text(rel, t)

    # 9. Widget choosers semGetCallingUserId
    for wfile in [
        "smali/com/samsung/android/sidegesturepad/settings/widget/SGPSeslWidgetChooserActivity.smali",
        "smali/com/samsung/android/sidegesturepad/settings/widgetpopup/SGPGlanceWidgetChooserActivity.smali",
        "smali/com/samsung/android/sidegesturepad/settings/widgets/SGPWidgetChooserActivity.smali",
    ]:
        t = read_text(wfile)
        t = replace_exact(
            t,
            "    invoke-static {}, Landroid/os/UserHandle;->semGetCallingUserId()I",
            f"    invoke-static {{}}, {COMPAT}->getCurrentUserId()I",
            wfile,
        )
        write_text(wfile, t)

    # 9b. r6/f.smali: keep LayoutParams.alpha = 1.0f (hide view via View.setAlpha) AND route overlay WM via AccessibilityService (TYPE_ACCESSIBILITY_OVERLAY = 2032) so edge handles sit above Vivo's SideSlideGestureBar!
    rel = "smali/r6/f.smali"
    t = read_text(rel)
    t = replace_regex(
        t,
        r"    :goto_5(?:\s+\.line \d+)*\s+iput v14, v5, Landroid/view/WindowManager\$LayoutParams;->alpha:F",
        "    :goto_5\n"
        "    move-object/from16 v10, p0\n"
        "    iget-object v10, v10, Lr6/f;->c:Landroid/view/View;\n"
        f"    invoke-static {{v10, v5, v14}}, {COMPAT}->applyHandleAlpha(Landroid/view/View;Landroid/view/WindowManager$LayoutParams;F)V",
        "r6/f applyHandleAlpha",
    )
    t = replace_exact(
        t,
        "    invoke-interface {v4, v0, v5}, Landroid/view/ViewManager;->addView(Landroid/view/View;Landroid/view/ViewGroup$LayoutParams;)V",
        f"    invoke-static {{v4, v0, v5}}, {COMPAT}->addHandlerOverlayView(Landroid/view/WindowManager;Landroid/view/View;Landroid/view/ViewGroup$LayoutParams;)V",
        "r6/f addView",
    )
    t = replace_exact(
        t,
        "    invoke-interface {v1, v5, v10}, Landroid/view/ViewManager;->updateViewLayout(Landroid/view/View;Landroid/view/ViewGroup$LayoutParams;)V",
        f"    invoke-static {{v1, v5, v10}}, {COMPAT}->updateHandlerOverlayView(Landroid/view/WindowManager;Landroid/view/View;Landroid/view/ViewGroup$LayoutParams;)V",
        "r6/f updateViewLayout 1",
    )
    t = replace_exact(
        t,
        "    invoke-interface {v1, v2, p0}, Landroid/view/ViewManager;->updateViewLayout(Landroid/view/View;Landroid/view/ViewGroup$LayoutParams;)V",
        f"    invoke-static {{v1, v2, p0}}, {COMPAT}->updateHandlerOverlayView(Landroid/view/WindowManager;Landroid/view/View;Landroid/view/ViewGroup$LayoutParams;)V",
        "r6/f updateViewLayout 2",
    )
    t = replace_exact(
        t,
        "    invoke-interface {v2, v0}, Landroid/view/WindowManager;->removeViewImmediate(Landroid/view/View;)V",
        f"    invoke-static {{v2, v0}}, {COMPAT}->removeHandlerOverlayView(Landroid/view/WindowManager;Landroid/view/View;)V",
        "r6/f removeViewImmediate",
    )
    t = replace_regex(
        t,
        r"    sget-object v7, Ls6/c;->E:Ls6/c;(?:\s+\.line \d+)*\s+invoke-static \{\}, Ls6/z;->u0\(\)Z(?:\s+\.line \d+)*\s+move-result v8",
        "    sget-object v7, Ls6/c;->E:Ls6/c;\n    const/4 v8, 0x1",
        "r6/f f() un-gate use_system_gesture",
    )
    t = replace_regex(
        t,
        r"    :goto_2(?:\s+\.line \d+)*\s+if-nez v7, :cond_4",
        "    :goto_2\n    goto :cond_4",
        "r6/f f() always use handle bounds for touchableRegion",
    )
    write_text(rel, t)

    # 9b2. w5/a.smali: un-gate use_system_gesture (c.x) in touchableRegion check
    rel = "smali/w5/a.smali"
    t = read_text(rel)
    t = replace_regex(
        t,
        r"    invoke-static \{\}, Ls6/z;->u0\(\)Z(?:\s+\.line \d+)*\s+move-result v4(?:\s+\.line \d+)*\s+const/4 v5, 0x0(?:\s+\.line \d+)*\s+if-eqz v4, :cond_3",
        "    const/4 v5, 0x0",
        "w5/a un-gate use_system_gesture",
    )
    write_text(rel, t)

    # 9b3. d6/y.smali: promote Virtual Touch Pad edge docked pill to TYPE_ACCESSIBILITY_OVERLAY (2032)
    rel = "smali/d6/y.smali"
    t = read_text(rel)
    t = replace_exact(
        t,
        "    invoke-interface {v0, v1, v2}, Landroid/view/ViewManager;->addView(Landroid/view/View;Landroid/view/ViewGroup$LayoutParams;)V",
        f"    invoke-static {{v0, v1, v2}}, {COMPAT}->addHandlerOverlayView(Landroid/view/WindowManager;Landroid/view/View;Landroid/view/ViewGroup$LayoutParams;)V",
        "d6/y addView",
    )
    t = replace_exact(
        t,
        "    invoke-interface {v0, v1, p0}, Landroid/view/ViewManager;->updateViewLayout(Landroid/view/View;Landroid/view/ViewGroup$LayoutParams;)V",
        f"    invoke-static {{v0, v1, p0}}, {COMPAT}->updateHandlerOverlayView(Landroid/view/WindowManager;Landroid/view/View;Landroid/view/ViewGroup$LayoutParams;)V",
        "d6/y updateViewLayout",
    )
    t = replace_exact(
        t,
        "    invoke-interface {v1, v2}, Landroid/view/WindowManager;->removeViewImmediate(Landroid/view/View;)V",
        f"    invoke-static {{v1, v2}}, {COMPAT}->removeHandlerOverlayView(Landroid/view/WindowManager;Landroid/view/View;)V",
        "d6/y removeViewImmediate",
    )
    write_text(rel, t)

    # 9c. a6/y.smali: guard against null ViewGroup k or RecyclerView in :pswitch_4 delayed runnable
    rel = "smali/a6/y.smali"
    t = read_text(rel)
    t = replace_regex(
        t,
        r"    :pswitch_4(?:\s+\.line \d+)*\s+sget v0, Lcom/samsung/android/sidegesturepad/fastaction/SGPFastActionView;->K:I(?:\s+\.line \d+)*\s+invoke-virtual \{p0\}, Lcom/samsung/android/sidegesturepad/fastaction/SGPFastActionView;->h\(\)V(?:\s+\.line \d+)*\s+iget-object v0, p0, Lcom/samsung/android/sidegesturepad/fastaction/SGPFastActionView;->k:Landroid/view/ViewGroup;(?:\s+\.line \d+)*\s+const v1, 0x7f0900e6(?:\s+\.line \d+)*\s+invoke-virtual \{v0, v1\}, Landroid/view/View;->findViewById\(I\)Landroid/view/View;(?:\s+\.line \d+)*\s+move-result-object v0(?:\s+\.line \d+)*\s+check-cast v0, Landroidx/recyclerview/widget/RecyclerView;",
        "    :pswitch_4\n"
        "    sget v0, Lcom/samsung/android/sidegesturepad/fastaction/SGPFastActionView;->K:I\n"
        "    invoke-virtual {p0}, Lcom/samsung/android/sidegesturepad/fastaction/SGPFastActionView;->h()V\n"
        "    iget-object v0, p0, Lcom/samsung/android/sidegesturepad/fastaction/SGPFastActionView;->k:Landroid/view/ViewGroup;\n"
        "    if-eqz v0, :cond_0\n"
        "    const v1, 0x7f0900e6\n"
        "    invoke-virtual {v0, v1}, Landroid/view/View;->findViewById(I)Landroid/view/View;\n"
        "    move-result-object v0\n"
        "    check-cast v0, Landroidx/recyclerview/widget/RecyclerView;\n"
        "    if-eqz v0, :cond_0",
        "a6/y null-guard FastActionView RecyclerView",
    )
    write_text(rel, t)

    # 9d. u7/c.smali: replace Samsung-only toggle_navibar default in Quick Tools with quick_dnd
    rel = "smali/u7/c.smali"
    t = read_text(rel)
    t = replace_exact(
        t,
        '    const-string v0, ",toggle_navibar"',
        '    const-string v0, ",quick_dnd"',
        "u7/c quick_tools default toggle_navibar -> quick_dnd",
    )
    write_text(rel, t)

    # 9e. a/a.smali: route x(Context, MotionEvent) touch injection to VivoCompat.injectTouchMotion
    rel = "smali/a/a.smali"
    t = read_text(rel)
    t = replace_method_body(
        t,
        "public static x(Landroid/content/Context;Landroid/view/MotionEvent;)V",
        f"    .locals 0\n\n    invoke-static {{p0, p1}}, {COMPAT}->injectTouchMotion(Landroid/content/Context;Landroid/view/MotionEvent;)V\n    return-void",
        "a/a injectTouchMotion",
    )
    write_text(rel, t)

    # 9f. a6/s.smali: edge tap timeout 200ms -> 500ms AND pass through touches outside handle bounds
    rel = "smali/a6/s.smali"
    t = read_text(rel)
    t = replace_regex(
        t,
        r"(    sub-long/2addr v2, v4(?:\s+\.line \d+)*\s+const-wide/16 v18,) 0xc8",
        r"\1 0x1f4",
        "a6/s tap timeout 200ms -> 500ms",
        count=2,
    )
    t = replace_regex(
        t,
        r"    :cond_10(?:\s+\.line \d+)*\s+if-ne v15, v7, :cond_11(?:\s+\.line \d+)*\s+:goto_7(?:\s+\.line \d+)*\s+move/from16 v5, v16(?:\s+\.line \d+)*\s+goto :goto_8(?:\s+\.line \d+)*\s+:cond_11(?:\s+\.line \d+)*\s+move v5, v7\n",
        "    :cond_10\n"
        "    iget-object v0, v4, Lr6/f;->m:Landroidx/fragment/app/y;\n"
        "    invoke-virtual {v0, v1}, Landroidx/fragment/app/y;->a(Landroid/view/MotionEvent;)V\n"
        "    const/4 v0, 0x0\n"
        "    return v0\n\n"
        "    :goto_7\n"
        "    iget-object v0, v4, Lr6/f;->m:Landroidx/fragment/app/y;\n"
        "    invoke-virtual {v0, v1}, Landroidx/fragment/app/y;->a(Landroid/view/MotionEvent;)V\n"
        "    const/4 v0, 0x0\n"
        "    return v0\n\n"
        "    :cond_11\n"
        "    iget-object v0, v4, Lr6/f;->m:Landroidx/fragment/app/y;\n"
        "    invoke-virtual {v0, v1}, Landroidx/fragment/app/y;->a(Landroid/view/MotionEvent;)V\n"
        "    const/4 v0, 0x0\n"
        "    return v0\n",
        "a6/s pass through touches outside active handle bounds",
    )
    write_text(rel, t)

    # 10. All SeekBar.semSetMode(I)V, AlertDialog.semSetBackgroundBlurEnabled(Z)V, SemBlurInfo blocks, semConfigure, 0xa29/0x8e8
    for dp, _, fns in os.walk(SMALI):
        rel_dp = os.path.relpath(dp, SMALI)
        if rel_dp.startswith(("androidx", "com\\google", "kotlin", "kotlinx", "okhttp", "okio")):
            continue
        for fn in fns:
            if not fn.endswith(".smali"):
                continue
            p = os.path.join(dp, fn)
            rel_p = os.path.relpath(p, APK_OUT).replace("\\", "/")
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                orig = f.read()
            new = orig
            new = re.sub(
                r"invoke-virtual \{(\w+), (\w+), (\w+), (\w+)\}, Landroid/content/ContentResolver;->registerContentObserver\(Landroid/net/Uri;ZLandroid/database/ContentObserver;\)V",
                f"invoke-static {{\\1, \\2, \\3, \\4}}, {COMPAT}->registerContentObserverSafe(Landroid/content/ContentResolver;Landroid/net/Uri;ZLandroid/database/ContentObserver;)V",
                new,
            )
            new = re.sub(
                r"invoke-virtual \{(\w+), (\w+)\}, Landroid/widget/SeekBar;->semSetMode\(I\)V",
                f"invoke-static {{\\1, \\2}}, {COMPAT}->setSeekBarMode(Landroid/widget/SeekBar;I)V",
                new,
            )
            new = re.sub(
                r"invoke-virtual \{(\w+), (\w+)\}, Landroid/app/AlertDialog;->semSetBackgroundBlurEnabled\(Z\)V",
                "nop",
                new,
            )
            new = new.replace(
                "Landroid/appwidget/AppWidgetProviderInfo;->semConfigure:Landroid/content/ComponentName;",
                "Landroid/appwidget/AppWidgetProviderInfo;->configure:Landroid/content/ComponentName;",
            )
            new = re.sub(r"const/16 (\w+), (?:0xa29|0x8e8)\b", r"const/16 \1, 0x7f6", new)

            # Route SemBlurInfo$Builder + semSetBlurInfo cleanly to CompatBlurInfo so registers & control flow stay 100% intact
            if "SemBlurInfo" in new:
                new = new.replace(
                    "Landroid/view/SemBlurInfo$Builder;",
                    "Lcom/samsung/android/sidegesturepad/compat/CompatBlurInfo$Builder;",
                )
                new = new.replace(
                    "Landroid/view/SemBlurInfo;",
                    "Lcom/samsung/android/sidegesturepad/compat/CompatBlurInfo;",
                )
                new = re.sub(
                    r"invoke-virtual \{(\w+), (\w+)\}, L[^;]+;->semSetBlurInfo\(Lcom/samsung/android/sidegesturepad/compat/CompatBlurInfo;\)V",
                    r"invoke-static {\1, \2}, Lcom/samsung/android/sidegesturepad/compat/CompatBlurInfo;->apply(Ljava/lang/Object;Lcom/samsung/android/sidegesturepad/compat/CompatBlurInfo;)V",
                    new,
                )

            if new != orig:
                write_text(rel_p, new)

    print("Patched all other smali files cleanly.")


SPR_VECTOR_ICONS = {
    "assistant_ic_screen_off": (
        "M17,1.01L7,1C5.9,1 5,1.9 5,3v18c0,1.1 0.9,2 2,2h10c1.1,0 2,-0.9 2,-2V3C19,1.9 18.1,1.01 17,1.01z "
        "M17,19H7V5h10V19z "
        "M14.5,11H14v-1c0,-1.1 -0.9,-2 -2,-2s-2,0.9 -2,2v1H9.5C9.22,11 9,11.22 9,11.5v4c0,0.28 0.22,0.5 0.5,0.5h5"
        "c0.28,0 0.5,-0.22 0.5,-0.5v-4C15,11.22 14.78,11 14.5,11z M13,11h-2v-1c0,-0.55 0.45,-1 1,-1s1,0.45 1,1V11z"
    ),
    "ic_app_secure_badge": (
        "M12,2L4,5v6.09c0,5.05 3.41,9.76 8,10.91c4.59,-1.15 8,-5.86 8,-10.91V5L12,2z "
        "M15,11.5v4c0,0.28 -0.22,0.5 -0.5,0.5h-5c-0.28,0 -0.5,-0.22 -0.5,-0.5v-4c0,-0.28 0.22,-0.5 0.5,-0.5H10v-1"
        "c0,-1.1 0.9,-2 2,-2s2,0.9 2,2v1h0.5C14.78,11 15,11.22 15,11.5z M13,11v-1c0,-0.55 -0.45,-1 -1,-1s-1,0.45 -1,1v1H13z"
    ),
    "ic_qp_oho": (
        "M17,2H7C5.9,2 5,2.9 5,4v16c0,1.1 0.9,2 2,2h10c1.1,0 2,-0.9 2,-2V4C19,2.9 18.1,2 17,2z "
        "M17,19H7V5h10V19z M9,12l3.5,-3.5v2.25H16v2.5h-3.5v2.25L9,12z"
    ),
    "quick_panel_icon_brightness": (
        "M12,7c-2.76,0 -5,2.24 -5,5s2.24,5 5,5s5,-2.24 5,-5S14.76,7 12,7z "
        "M11,1h2v3h-2V1z M11,20h2v3h-2V20z M3.51,4.93l1.41,-1.41l2.12,2.12L5.64,7.05L3.51,4.93z "
        "M16.95,18.36l1.41,-1.41l2.12,2.12l-1.41,1.41L16.95,18.36z "
        "M20,11h3v2h-3V11z M1,11h3v2H1V11z "
        "M5.64,16.95l1.41,1.41l-2.12,2.12l-1.41,-1.41L5.64,16.95z "
        "M18.36,7.05l-1.41,-1.41l2.12,-2.12l1.41,1.41L18.36,7.05z"
    ),
    "quick_panel_icon_data_connection": (
        "M9,3L5,7h3v7h2V7h3L9,3z M16,17v-7h-2v7h-3l4,4l4,-4H16z"
    ),
    "quick_panel_icon_multiwindow": (
        "M4,4h16c1.1,0 2,0.9 2,2v5H2V6C2,4.9 2.9,4 4,4z M2,13h20v5c0,1.1 -0.9,2 -2,2H4c-1.1,0 -2,-0.9 -2,-2V13z"
    ),
    "quick_panel_icon_navigation_bar": (
        "M4,4h16c1.1,0 2,0.9 2,2v12c0,1.1 -0.9,2 -2,2H4c-1.1,0 -2,-0.9 -2,-2V6C2,4.9 2.9,4 4,4z "
        "M4,6v9h16V6H4z M7,16.5h2v1.5H7V16.5z M11,16.5h2v1.5h-2V16.5z M15,16.5h2v1.5h-2V16.5z"
    ),
    "quick_panel_icon_task_bar": (
        "M4,4h16c1.1,0 2,0.9 2,2v12c0,1.1 -0.9,2 -2,2H4c-1.1,0 -2,-0.9 -2,-2V6C2,4.9 2.9,4 4,4z "
        "M4,6v8h16V6H4z M6,15.5h2.5v2.5H6V15.5z M10.75,15.5h2.5v2.5h-2.5V15.5z M15.5,15.5H18v2.5h-2.5V15.5z"
    ),
    "sec_tw_list_icon_reorder": (
        "M4,8h16v2H4V8z M4,14h16v2H4V14z"
    ),
    "tw_ic_ab_setting_mtrl": (
        "M19.14,12.94c0.04,-0.3 0.06,-0.61 0.06,-0.94c0,-0.32 -0.02,-0.64 -0.07,-0.94l2.03,-1.58c0.18,-0.14 0.23,-0.41 0.12,-0.61"
        "l-1.92,-3.32c-0.12,-0.22 -0.37,-0.29 -0.59,-0.22l-2.39,0.96c-0.5,-0.38 -1.03,-0.7 -1.62,-0.94L14.4,2.81"
        "c-0.04,-0.24 -0.24,-0.41 -0.48,-0.41h-3.84c-0.24,0 -0.43,0.17 -0.47,0.41L9.25,5.35C8.66,5.59 8.12,5.92 7.63,6.29"
        "L5.24,5.33c-0.22,-0.08 -0.47,0 -0.59,0.22L2.74,8.87C2.62,9.08 2.66,9.34 2.86,9.48l2.03,1.58C4.84,11.36 4.8,11.69 4.8,12"
        "s0.02,0.64 0.07,0.94l-2.03,1.58c-0.18,0.14 -0.23,0.41 -0.12,0.61l1.92,3.32c0.12,0.22 0.37,0.29 0.59,0.22l2.39,-0.96"
        "c0.5,0.38 1.03,0.7 1.62,0.94l0.36,2.54c0.05,0.24 0.24,0.41 0.48,0.41h3.84c0.24,0 0.44,-0.17 0.47,-0.41l0.36,-2.54"
        "c0.59,-0.24 1.13,-0.56 1.62,-0.94l2.39,0.96c0.22,0.08 0.47,0 0.59,-0.22l1.92,-3.32c0.12,-0.22 0.07,-0.47 -0.12,-0.61"
        "L19.14,12.94z M12,15.6c-1.98,0 -3.6,-1.62 -3.6,-3.6s1.62,-3.6 3.6,-3.6s3.6,1.62 3.6,3.6S13.98,15.6 12,15.6z"
    ),
    "universal_ic_view_power_key_menu": (
        "M13,3h-2v10h2V3z M17.83,5.17l-1.42,1.42C17.99,7.86 19,9.81 19,12c0,3.87 -3.13,7 -7,7s-7,-3.13 -7,-7"
        "c0,-2.19 1.01,-4.14 2.58,-5.42L6.17,5.17C4.23,6.82 3,9.26 3,12c0,4.97 4.03,9 9,9s9,-4.03 9,-9"
        "C21,9.26 19.77,6.82 17.83,5.17z"
    ),
}


def patch_styles():
    styles_rel = "res/values/styles.xml"
    t = read_text(styles_rel)
    replacements = {
        'Theme.QuickToolsSettingActivity': '#ff2e65d4',
        'Theme.QuickToolsSettingActivityDark': '#ff598fff',
        'Theme.SettingsActivity': '#ff2e65d4',
        'Theme.SettingsActivityDark': '#ff598fff',
    }
    changed = False
    for style_name, accent in replacements.items():
        pat = re.compile(
            r'(<style name="' + re.escape(style_name) + r'"[^>]*>)(.*?)(</style>)',
            re.DOTALL,
        )
        m = pat.search(t)
        if not m:
            raise RuntimeError(f"Style {style_name} not found in {styles_rel}")
        body = m.group(2)
        if 'name="android:colorPrimaryDark"' not in body:
            inject = (
                f'\n        <item name="android:colorPrimaryDark">{accent}</item>'
                f'\n        <item name="colorPrimaryDark">{accent}</item>'
            )
            t = t[: m.start(2)] + body + inject + t[m.end(2) :]
            changed = True
    if changed:
        write_text(styles_rel, t)
    print("Patched styles.xml OneUI primary accents.")


def patch_spr_drawables():
    drawable_dir = os.path.join(APK_OUT, "res", "drawable")
    replaced = 0
    for name, path_data in SPR_VECTOR_ICONS.items():
        bmp_path = os.path.join(drawable_dir, f"{name}.bmp")
        xml_path = os.path.join(drawable_dir, f"{name}.xml")
        if os.path.exists(bmp_path):
            os.remove(bmp_path)
        xml_content = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
            '    android:width="24.0dp"\n'
            '    android:height="24.0dp"\n'
            '    android:viewportWidth="24.0"\n'
            '    android:viewportHeight="24.0">\n'
            f'    <path android:fillColor="#ffffffff" android:pathData="{path_data}" />\n'
            '</vector>\n'
        )
        with open(xml_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(xml_content)
        replaced += 1
    print(f"Replaced {replaced} Samsung SPR .bmp drawables with VectorDrawable XMLs.")


if __name__ == "__main__":
    restore_from_backup()
    patch_manifest()
    patch_styles()
    patch_spr_drawables()
    patch_s6_d()
    patch_sgp_service()
    patch_s6_z()
    patch_w5_f()
    patch_other_smali()
    print("ALL PATCHES APPLIED SUCCESSFULLY!")
