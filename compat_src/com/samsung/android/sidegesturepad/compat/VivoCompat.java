package com.samsung.android.sidegesturepad.compat;

import android.accessibilityservice.AccessibilityService;
import android.app.ActivityManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.SearchManager;
import android.app.UiModeManager;
import android.app.usage.UsageStats;
import android.app.usage.UsageStatsManager;
import android.bluetooth.BluetoothAdapter;
import android.content.ComponentName;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.LauncherActivityInfo;
import android.content.pm.LauncherApps;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.content.pm.ShortcutInfo;
import android.graphics.PointF;
import android.graphics.drawable.Drawable;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.hardware.input.InputManager;
import android.media.AudioManager;
import android.media.session.MediaController;
import android.media.session.MediaSessionManager;
import android.net.Uri;
import android.net.wifi.WifiManager;
import android.nfc.NfcAdapter;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.Process;
import android.os.SystemClock;
import android.os.UserHandle;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.provider.Settings;
import android.text.TextUtils;
import android.util.Log;
import android.view.InputEvent;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;
import android.widget.SeekBar;
import android.widget.Toast;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class VivoCompat {
    private static final String TAG = "VivoCompat";
    private static final String CHANNEL_ID = "sgp_service_channel";
    private static final int NOTIF_ID = 9423;

    private static volatile boolean sTorchEnabled = false;
    private static volatile boolean sTorchCallbackRegistered = false;
    private static String sTorchCameraId = null;

    private static final List<PointF> sPendingTouchPoints = new ArrayList<>();
    private static long sPendingTouchDownTime = -1L;
    private static boolean sPendingTouchSawUp = false;
    private static Runnable sPendingTapFallback = null;
    private static volatile boolean sHandlersPassThrough = false;
    private static volatile int sPassThroughGen = 0;
    private static long sLastPassThroughTime = 0L;
    private static final Handler sMainHandler = new Handler(Looper.getMainLooper());

    private VivoCompat() {}

    public static boolean isSupportedOS(Context ctx) {
        return true;
    }

    public static int getOverlayWindowType(int requestedType) {
        if (requestedType >= 2000 && requestedType <= 2999) {
            return WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY; // 2038
        }
        return requestedType;
    }

    public static void ensureForegroundService(android.app.Service service) {
        if (service == null) return;
        try {
            NotificationManager nm = (NotificationManager) service.getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm != null) {
                NotificationChannel ch = new NotificationChannel(
                        CHANNEL_ID,
                        "One Hand Operation+ Service",
                        NotificationManager.IMPORTANCE_MIN
                );
                ch.setShowBadge(false);
                ch.enableLights(false);
                ch.enableVibration(false);
                ch.setSound(null, null);
                nm.createNotificationChannel(ch);
            }
            int iconRes = service.getApplicationInfo().icon;
            if (iconRes == 0) {
                iconRes = android.R.drawable.ic_menu_compass;
            }
            Notification notif = new Notification.Builder(service, CHANNEL_ID)
                    .setSmallIcon(iconRes)
                    .setContentTitle("One Hand Operation +")
                    .setContentText("Gesture handles active")
                    .setOngoing(true)
                    .setForegroundServiceBehavior(Notification.FOREGROUND_SERVICE_IMMEDIATE)
                    .build();
            service.startForeground(NOTIF_ID, notif);
        } catch (Throwable t) {
            Log.e(TAG, "ensureForegroundService failed", t);
        }
    }

    public static ComponentName startServiceCompat(Context ctx, Intent intent) {
        if (ctx == null || intent == null) return null;
        try {
            String opt = intent.getStringExtra("option");
            boolean isStop = "stop".equals(opt);
            if (!isStop && Build.VERSION.SDK_INT >= 26) {
                return ctx.startForegroundService(intent);
            }
            return ctx.startService(intent);
        } catch (Throwable t) {
            Log.e(TAG, "startServiceCompat fallback startService", t);
            try {
                return ctx.startService(intent);
            } catch (Throwable t2) {
                Log.e(TAG, "startServiceCompat failed", t2);
                return null;
            }
        }
    }

    // --- Accessibility-backed Global Actions ---

    private static void toastOnMain(final Context ctx, final String msg) {
        if (ctx == null || TextUtils.isEmpty(msg)) return;
        new Handler(Looper.getMainLooper()).post(new Runnable() {
            @Override
            public void run() {
                try {
                    Toast.makeText(ctx.getApplicationContext(), msg, Toast.LENGTH_SHORT).show();
                } catch (Throwable ignored) {}
            }
        });
    }

    private static boolean requireAccessibility(Context ctx) {
        if (SGPCompatAccessibilityService.isConnected()) {
            return true;
        }
        toastOnMain(ctx, "Enable One Hand Operation+ Accessibility service");
        try {
            Intent i = new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS);
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            ctx.startActivity(i);
        } catch (Throwable t) {
            Log.e(TAG, "Failed opening accessibility settings", t);
        }
        return false;
    }

    public static boolean isPanelExpanded() {
        return SGPCompatAccessibilityService.isPanelExpanded();
    }

    public static void expandNotificationsPanel(Context ctx) {
        if (SGPCompatAccessibilityService.isConnected()) {
            if (SGPCompatAccessibilityService.isPanelExpanded()) {
                collapsePanels(ctx);
            } else {
                SGPCompatAccessibilityService.performGlobal(AccessibilityService.GLOBAL_ACTION_NOTIFICATIONS);
            }
            return;
        }
        try {
            Object sb = ctx.getSystemService("statusbar");
            if (sb != null) {
                Method m = sb.getClass().getMethod("expandNotificationsPanel");
                m.invoke(sb);
                return;
            }
        } catch (Throwable t) {
            Log.w(TAG, "statusbar expandNotificationsPanel failed", t);
        }
        requireAccessibility(ctx);
    }

    public static void expandQuickSettingsPanel(Context ctx) {
        if (SGPCompatAccessibilityService.isConnected()) {
            if (SGPCompatAccessibilityService.isPanelExpanded()) {
                collapsePanels(ctx);
            } else {
                SGPCompatAccessibilityService.performGlobal(AccessibilityService.GLOBAL_ACTION_QUICK_SETTINGS);
            }
            return;
        }
        try {
            Object sb = ctx.getSystemService("statusbar");
            if (sb != null) {
                Method m = sb.getClass().getMethod("expandSettingsPanel");
                m.invoke(sb);
                return;
            }
        } catch (Throwable t) {
            Log.w(TAG, "statusbar expandSettingsPanel failed", t);
        }
        requireAccessibility(ctx);
    }

    public static void collapsePanels(Context ctx) {
        if (SGPCompatAccessibilityService.isPanelExpanded() && SGPCompatAccessibilityService.isConnected()) {
            // 15 = GLOBAL_ACTION_DISMISS_NOTIFICATION_SHADE (Android 12+)
            if (!SGPCompatAccessibilityService.performGlobal(15)) {
                SGPCompatAccessibilityService.performGlobal(AccessibilityService.GLOBAL_ACTION_BACK);
            }
        }
    }

    public static void showGlobalActions(Context ctx) {
        if (requireAccessibility(ctx)) {
            SGPCompatAccessibilityService.performGlobal(AccessibilityService.GLOBAL_ACTION_POWER_DIALOG);
        }
    }

    public static void takeScreenshot(Context ctx) {
        if (requireAccessibility(ctx)) {
            // 9 = GLOBAL_ACTION_TAKE_SCREENSHOT (Android 9+)
            SGPCompatAccessibilityService.performGlobal(9);
        }
    }

    public static void toggleSplitScreen(Context ctx) {
        if (requireAccessibility(ctx)) {
            if (!SGPCompatAccessibilityService.performGlobal(AccessibilityService.GLOBAL_ACTION_TOGGLE_SPLIT_SCREEN)) {
                toastOnMain(ctx, "Split screen not available for this app");
            }
        }
    }

    public static void injectKeyEvent(Context ctx, int keyCode, int action, int flags, int metaState) {
        if (action != KeyEvent.ACTION_DOWN) return;
        // Skip standalone modifier press events when called as a sequence (Alt/Shift/Ctrl/Meta)
        if (keyCode == KeyEvent.KEYCODE_SHIFT_LEFT || keyCode == KeyEvent.KEYCODE_SHIFT_RIGHT
                || keyCode == KeyEvent.KEYCODE_CTRL_LEFT || keyCode == KeyEvent.KEYCODE_CTRL_RIGHT
                || keyCode == KeyEvent.KEYCODE_ALT_LEFT || keyCode == KeyEvent.KEYCODE_ALT_RIGHT
                || keyCode == KeyEvent.KEYCODE_META_LEFT || keyCode == KeyEvent.KEYCODE_META_RIGHT) {
            return;
        }
        if (keyCode == KeyEvent.KEYCODE_HOME && (flags & KeyEvent.FLAG_LONG_PRESS) != 0) {
            launchAssistant(ctx);
            return;
        }
        injectKey(ctx, keyCode);
    }

    public static void injectKey(Context ctx, int keyCode) {
        Log.i(TAG, "injectKey(" + keyCode + ")");
        switch (keyCode) {
            case KeyEvent.KEYCODE_BACK: // 4
                if (requireAccessibility(ctx)) {
                    SGPCompatAccessibilityService.performGlobal(AccessibilityService.GLOBAL_ACTION_BACK);
                }
                return;
            case KeyEvent.KEYCODE_HOME: // 3
                if (requireAccessibility(ctx)) {
                    SGPCompatAccessibilityService.performGlobal(AccessibilityService.GLOBAL_ACTION_HOME);
                }
                return;
            case KeyEvent.KEYCODE_APP_SWITCH: // 187
                if (requireAccessibility(ctx)) {
                    SGPCompatAccessibilityService.performGlobal(AccessibilityService.GLOBAL_ACTION_RECENTS);
                }
                return;
            case 1003: // notification panel key code in Samsung SGP
                expandNotificationsPanel(ctx);
                return;
            case KeyEvent.KEYCODE_POWER: // 26
            case 1004: // screenshot key code in SGPController
                if (keyCode == 1004) {
                    takeScreenshot(ctx);
                } else if (requireAccessibility(ctx)) {
                    // 8 = GLOBAL_ACTION_LOCK_SCREEN (Android 9+)
                    SGPCompatAccessibilityService.performGlobal(8);
                }
                return;
            case KeyEvent.KEYCODE_VOLUME_UP: // 24
                adjustVolume(ctx, AudioManager.ADJUST_RAISE);
                return;
            case KeyEvent.KEYCODE_VOLUME_DOWN: // 25
                adjustVolume(ctx, AudioManager.ADJUST_LOWER);
                return;
            case KeyEvent.KEYCODE_VOLUME_MUTE: // 164
                adjustVolume(ctx, AudioManager.ADJUST_TOGGLE_MUTE);
                return;
            case KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE: // 85
            case KeyEvent.KEYCODE_MEDIA_NEXT: // 87
            case KeyEvent.KEYCODE_MEDIA_PREVIOUS: // 88
            case KeyEvent.KEYCODE_MEDIA_PLAY: // 126
            case KeyEvent.KEYCODE_MEDIA_PAUSE: // 127
                dispatchMediaKey(ctx, keyCode);
                return;
            case KeyEvent.KEYCODE_SEARCH: // 84
                launchSearch(ctx);
                return;
            case 284: // KEYCODE_ALL_APPS
                launchHomeApps(ctx);
                return;
            default:
                tryInjectRawKey(ctx, keyCode);
                return;
        }
    }

    private static void adjustVolume(Context ctx, int direction) {
        try {
            AudioManager am = (AudioManager) ctx.getSystemService(Context.AUDIO_SERVICE);
            if (am != null) {
                am.adjustStreamVolume(AudioManager.STREAM_MUSIC, direction, AudioManager.FLAG_SHOW_UI);
            }
        } catch (Throwable t) {
            Log.e(TAG, "adjustVolume failed", t);
        }
    }

    public static boolean handleMediaKey(Context ctx, int keyCode) {
        if (ctx == null) return false;
        long now = SystemClock.uptimeMillis();
        AudioManager am = (AudioManager) ctx.getSystemService(Context.AUDIO_SERVICE);
        if (am != null) {
            try {
                am.dispatchMediaKeyEvent(new KeyEvent(now, now, KeyEvent.ACTION_DOWN, keyCode, 0));
                am.dispatchMediaKeyEvent(new KeyEvent(now, now + 10, KeyEvent.ACTION_UP, keyCode, 0));
                return true;
            } catch (Throwable t) {
                Log.w(TAG, "dispatchMediaKeyEvent failed: " + t.getMessage());
            }
        }
        try {
            MediaSessionManager msm = (MediaSessionManager) ctx.getSystemService(Context.MEDIA_SESSION_SERVICE);
            if (msm != null) {
                List<MediaController> list = msm.getActiveSessions(null);
                if (list != null && !list.isEmpty()) {
                    for (MediaController mc : list) {
                        try {
                            mc.dispatchMediaButtonEvent(new KeyEvent(now, now, KeyEvent.ACTION_DOWN, keyCode, 0));
                            mc.dispatchMediaButtonEvent(new KeyEvent(now, now + 10, KeyEvent.ACTION_UP, keyCode, 0));
                            return true;
                        } catch (Throwable ignored) {}
                    }
                }
            }
        } catch (Throwable ignored) {}
        return false;
    }

    private static void dispatchMediaKey(Context ctx, int keyCode) {
        handleMediaKey(ctx, keyCode);
    }

    private static void launchSearch(Context ctx) {
        try {
            Intent intent = new Intent(Intent.ACTION_WEB_SEARCH);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            ctx.startActivity(intent);
        } catch (Throwable t) {
            launchAssistant(ctx);
        }
    }

    private static void launchHomeApps(Context ctx) {
        if (SGPCompatAccessibilityService.isConnected()) {
            SGPCompatAccessibilityService.performGlobal(AccessibilityService.GLOBAL_ACTION_HOME);
        }
    }

    private static void tryInjectRawKey(Context ctx, int keyCode) {
        try {
            InputManager im = (InputManager) ctx.getSystemService(Context.INPUT_SERVICE);
            Method m = InputManager.class.getMethod("injectInputEvent", InputEvent.class, int.class);
            long now = SystemClock.uptimeMillis();
            KeyEvent down = new KeyEvent(now, now, KeyEvent.ACTION_DOWN, keyCode, 0);
            KeyEvent up = new KeyEvent(now, now + 10, KeyEvent.ACTION_UP, keyCode, 0);
            m.invoke(im, down, 0);
            m.invoke(im, up, 0);
        } catch (Throwable t) {
            Log.w(TAG, "tryInjectRawKey(" + keyCode + ") blocked without INJECT_EVENTS: " + t.getMessage());
            toastOnMain(ctx, "Action requires root/system permission on Vivo");
        }
    }

    public static void injectTouchMotion(Context ctx, MotionEvent ev) {
        if (ev == null) return;
        int action = ev.getActionMasked();
        float x = ev.getRawX();
        float y = ev.getRawY();
        if (x == 0f && y == 0f) {
            x = ev.getX();
            y = ev.getY();
        }
        x = Math.max(1f, x);
        y = Math.max(1f, y);
        if (action == MotionEvent.ACTION_DOWN) {
            sPendingTouchPoints.clear();
            final long downTime = ev.getDownTime();
            sPendingTouchDownTime = downTime;
            sPendingTouchSawUp = false;
            sPendingTouchPoints.add(new PointF(x, y));

            if (sPendingTapFallback != null) {
                sMainHandler.removeCallbacks(sPendingTapFallback);
                sPendingTapFallback = null;
            }
            final PointF downPt = new PointF(x, y);
            sPendingTapFallback = () -> {
                if (sPendingTouchDownTime == downTime && !sPendingTouchSawUp && sPendingTouchPoints.size() <= 4) {
                    sPendingTouchPoints.clear();
                    sPendingTouchDownTime = -1L;
                    List<PointF> tap = new ArrayList<>(2);
                    tap.add(downPt);
                    tap.add(downPt);
                    dispatchPassThroughStroke(tap, 40L);
                }
            };
            sMainHandler.postDelayed(sPendingTapFallback, 400L);
        } else if (action == MotionEvent.ACTION_MOVE) {
            if (sPendingTouchDownTime == ev.getDownTime()) {
                if (sPendingTouchPoints.size() < 64) {
                    sPendingTouchPoints.add(new PointF(x, y));
                }
                PointF first = sPendingTouchPoints.get(0);
                float dx = x - first.x;
                float dy = y - first.y;
                if (dx * dx + dy * dy > 1024f) { // > 32px movement: gesture active, cancel tap fallback
                    if (sPendingTapFallback != null) {
                        sMainHandler.removeCallbacks(sPendingTapFallback);
                        sPendingTapFallback = null;
                    }
                }
            }
        } else if (action == MotionEvent.ACTION_UP) {
            if (sPendingTapFallback != null) {
                sMainHandler.removeCallbacks(sPendingTapFallback);
                sPendingTapFallback = null;
            }
            if (sPendingTouchDownTime == ev.getDownTime() && !sPendingTouchPoints.isEmpty()) {
                sPendingTouchSawUp = true;
                sPendingTouchPoints.add(new PointF(x, y));
                List<PointF> copy = new ArrayList<>(sPendingTouchPoints);
                sPendingTouchPoints.clear();
                sPendingTouchDownTime = -1L;

                PointF first = copy.get(0);
                float maxDistSq = 0f;
                for (int i = 1; i < copy.size(); i++) {
                    float dx = copy.get(i).x - first.x;
                    float dy = copy.get(i).y - first.y;
                    float dSq = dx * dx + dy * dy;
                    if (dSq > maxDistSq) maxDistSq = dSq;
                }
                if (maxDistSq < 1024f) { // < 32px movement: treat as clean tap
                    List<PointF> tap = new ArrayList<>(2);
                    tap.add(new PointF(x, y));
                    tap.add(new PointF(x, y));
                    dispatchPassThroughStroke(tap, 40L);
                }
            }
        } else if (action == MotionEvent.ACTION_CANCEL) {
            if (sPendingTapFallback != null) {
                sMainHandler.removeCallbacks(sPendingTapFallback);
                sPendingTapFallback = null;
            }
            sPendingTouchPoints.clear();
            sPendingTouchDownTime = -1L;
            sPendingTouchSawUp = false;
        }
    }

    private static void dispatchPassThroughStroke(final List<PointF> points, final long dur) {
        if (!SGPCompatAccessibilityService.isConnected() || points == null || points.isEmpty()) {
            return;
        }
        long now = SystemClock.uptimeMillis();
        sLastPassThroughTime = now;
        final int gen = ++sPassThroughGen;
        setHandlerOverlaysTouchable(false);
        PointF p0 = points.get(0);
        recordDebugEvent("passThrough (" + (int) p0.x + "," + (int) p0.y + ") pts=" + points.size() + " dur=" + dur);
        sMainHandler.postDelayed(() -> {
            if (sPassThroughGen != gen) {
                return;
            }
            sMainHandler.postDelayed(() -> {
                if (sPassThroughGen == gen) {
                    setHandlerOverlaysTouchable(true);
                }
            }, dur + 80L);
            SGPCompatAccessibilityService.dispatchStroke(points, dur, () -> sMainHandler.post(() -> {
                if (sPassThroughGen == gen) {
                    setHandlerOverlaysTouchable(true);
                }
            }));
        }, 35L);
    }

    private static void setHandlerOverlaysTouchable(boolean touchable) {
        sHandlersPassThrough = !touchable;
        java.util.List<java.util.Map.Entry<View, TrackedOverlay>> entries;
        synchronized (sOverlays) {
            entries = new java.util.ArrayList<>(sOverlays.entrySet());
        }
        for (java.util.Map.Entry<View, TrackedOverlay> e : entries) {
            View v = e.getKey();
            TrackedOverlay t = e.getValue();
            if (v == null || t == null || t.activeWm == null) continue;
            CharSequence title = t.lastParams.getTitle();
            if (title == null || !title.toString().startsWith("ThumbsUpHandler")) continue;
            if (v.getParent() == null && !v.isAttachedToWindow()) continue;
            try {
                WindowManager.LayoutParams tmp = new WindowManager.LayoutParams();
                tmp.copyFrom(t.lastParams);
                if (!touchable) {
                    tmp.flags |= WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE;
                } else {
                    tmp.flags &= ~WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE;
                }
                t.activeWm.updateViewLayout(v, tmp);
            } catch (Throwable ignored) {}
        }
    }

    public static void launchAssistant(Context ctx) {
        try {
            Intent intent = new Intent(Intent.ACTION_VOICE_COMMAND);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            ctx.startActivity(intent);
        } catch (Throwable t) {
            try {
                Intent assist = new Intent(Intent.ACTION_ASSIST);
                assist.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                ctx.startActivity(assist);
            } catch (Throwable t2) {
                Log.e(TAG, "launchAssistant failed", t2);
            }
        }
    }

    public static void launchSearcle(Context ctx) {
        try {
            // Try Google Assistant / Lens / Vivo Search fallback
            PackageManager pm = ctx.getPackageManager();
            Intent lens = new Intent(Intent.ACTION_VIEW, Uri.parse("googleapp://lens"));
            lens.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            if (lens.resolveActivity(pm) != null) {
                ctx.startActivity(lens);
                return;
            }
        } catch (Throwable ignored) {}
        launchAssistant(ctx);
    }

    // --- Recent Apps & Previous App via UsageStatsManager + Accessibility ---

    public static void launchPreviousApp(final Context ctx) {
        String current = getForegroundPackage(ctx);
        String launcherPkg = getDefaultLauncherPackage(ctx);

        // 1. Try accessibility history first
        List<String> hist = SGPCompatAccessibilityService.getRecentPackageHistory();
        for (String pkg : hist) {
            if (!TextUtils.isEmpty(pkg) && !pkg.equals(current) && !pkg.equals(launcherPkg)
                    && !pkg.equals(ctx.getPackageName()) && !pkg.equals("com.android.systemui")) {
                if (launchPackage(ctx, pkg)) return;
            }
        }

        // 2. Try UsageStatsManager recent history
        List<String> usage = getRecentLaunchablePackages(ctx, 10);
        for (String pkg : usage) {
            if (!pkg.equals(current) && !pkg.equals(launcherPkg) && !pkg.equals(ctx.getPackageName())) {
                if (launchPackage(ctx, pkg)) return;
            }
        }

        // 3. Fallback: double Recents via AccessibilityService
        if (requireAccessibility(ctx)) {
            SGPCompatAccessibilityService.performGlobal(AccessibilityService.GLOBAL_ACTION_RECENTS);
            new Handler(Looper.getMainLooper()).postDelayed(new Runnable() {
                @Override
                public void run() {
                    SGPCompatAccessibilityService.performGlobal(AccessibilityService.GLOBAL_ACTION_RECENTS);
                }
            }, 220L);
        }
    }

    private static boolean launchPackage(Context ctx, String pkg) {
        try {
            Intent launch = ctx.getPackageManager().getLaunchIntentForPackage(pkg);
            if (launch != null) {
                launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
                ctx.startActivity(launch);
                return true;
            }
        } catch (Throwable t) {
            Log.w(TAG, "launchPackage(" + pkg + ") failed", t);
        }
        return false;
    }

    public static String getForegroundPackage(Context ctx) {
        String top = SGPCompatAccessibilityService.getTopPackage();
        if (!TextUtils.isEmpty(top)) {
            return top;
        }
        List<String> rec = getRecentLaunchablePackages(ctx, 1);
        return rec.isEmpty() ? "" : rec.get(0);
    }

    public static String getDefaultLauncherPackage(Context ctx) {
        try {
            Intent intent = new Intent(Intent.ACTION_MAIN);
            intent.addCategory(Intent.CATEGORY_HOME);
            ResolveInfo ri = ctx.getPackageManager().resolveActivity(intent, PackageManager.MATCH_DEFAULT_ONLY);
            if (ri != null && ri.activityInfo != null) {
                return ri.activityInfo.packageName;
            }
        } catch (Throwable ignored) {}
        return "";
    }

    public static List<String> getRecentLaunchablePackages(Context ctx, int maxCount) {
        List<String> out = new ArrayList<>();
        try {
            UsageStatsManager usm = (UsageStatsManager) ctx.getSystemService(Context.USAGE_STATS_SERVICE);
            if (usm == null) return out;
            long now = System.currentTimeMillis();
            List<UsageStats> stats = usm.queryUsageStats(UsageStatsManager.INTERVAL_DAILY, now - 86400_000L, now);
            if (stats == null || stats.isEmpty()) return out;
            Map<String, UsageStats> dedup = new HashMap<>();
            for (UsageStats u : stats) {
                if (u == null || u.getLastTimeUsed() <= 0) continue;
                UsageStats prev = dedup.get(u.getPackageName());
                if (prev == null || u.getLastTimeUsed() > prev.getLastTimeUsed()) {
                    dedup.put(u.getPackageName(), u);
                }
            }
            List<UsageStats> sorted = new ArrayList<>(dedup.values());
            Collections.sort(sorted, new Comparator<UsageStats>() {
                @Override
                public int compare(UsageStats a, UsageStats b) {
                    return Long.compare(b.getLastTimeUsed(), a.getLastTimeUsed());
                }
            });
            PackageManager pm = ctx.getPackageManager();
            String launcher = getDefaultLauncherPackage(ctx);
            for (UsageStats u : sorted) {
                String pkg = u.getPackageName();
                if (pkg.equals(ctx.getPackageName()) || pkg.equals(launcher) || "com.android.systemui".equals(pkg)) {
                    continue;
                }
                if (pm.getLaunchIntentForPackage(pkg) != null) {
                    out.add(pkg);
                    if (out.size() >= maxCount) break;
                }
            }
        } catch (Throwable t) {
            Log.e(TAG, "getRecentLaunchablePackages failed", t);
        }
        return out;
    }

    // --- System Settings & Hardware Toggles ---

    public static boolean toggleFlashlight(Context ctx) {
        try {
            final CameraManager cm = (CameraManager) ctx.getSystemService(Context.CAMERA_SERVICE);
            if (cm == null) return false;
            if (!sTorchCallbackRegistered) {
                sTorchCallbackRegistered = true;
                try {
                    cm.registerTorchCallback(new CameraManager.TorchCallback() {
                        @Override
                        public void onTorchModeChanged(String cameraId, boolean enabled) {
                            if (cameraId != null && cameraId.equals(sTorchCameraId)) {
                                sTorchEnabled = enabled;
                            }
                        }
                    }, new Handler(Looper.getMainLooper()));
                } catch (Throwable ignored) {}
            }
            if (sTorchCameraId == null) {
                for (String id : cm.getCameraIdList()) {
                    CameraCharacteristics chars = cm.getCameraCharacteristics(id);
                    Boolean hasFlash = chars.get(CameraCharacteristics.FLASH_INFO_AVAILABLE);
                    Integer facing = chars.get(CameraCharacteristics.LENS_FACING);
                    if (Boolean.TRUE.equals(hasFlash) && facing != null && facing == CameraCharacteristics.LENS_FACING_BACK) {
                        sTorchCameraId = id;
                        break;
                    }
                }
                if (sTorchCameraId == null && cm.getCameraIdList().length > 0) {
                    sTorchCameraId = cm.getCameraIdList()[0];
                }
            }
            if (sTorchCameraId != null) {
                boolean next = !sTorchEnabled;
                cm.setTorchMode(sTorchCameraId, next);
                sTorchEnabled = next;
                return true;
            }
        } catch (Throwable t) {
            Log.e(TAG, "toggleFlashlight failed", t);
        }
        return false;
    }

    public static void toggleBlueLightFilter(Context ctx) {
        try {
            ContentResolver cr = ctx.getContentResolver();
            int cur = Settings.Secure.getInt(cr, "night_display_activated", 0);
            int next = cur == 1 ? 0 : 1;
            Settings.Secure.putInt(cr, "night_display_activated", next);
            toastOnMain(ctx, "Eye Comfort : " + (next == 1 ? "On" : "Off"));
        } catch (Throwable t) {
            Log.e(TAG, "toggleBlueLightFilter failed", t);
            try {
                ctx.startActivity(new Intent(Settings.ACTION_NIGHT_DISPLAY_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            } catch (Throwable ignored) {}
        }
    }

    public static void toggleNightMode(Context ctx) {
        try {
            UiModeManager um = (UiModeManager) ctx.getSystemService(Context.UI_MODE_SERVICE);
            if (um != null) {
                boolean isDark = (ctx.getResources().getConfiguration().uiMode & 48) == 32;
                int next = isDark ? UiModeManager.MODE_NIGHT_NO : UiModeManager.MODE_NIGHT_YES;
                um.setNightMode(next);
                return;
            }
        } catch (Throwable t) {
            Log.e(TAG, "toggleNightMode failed", t);
        }
    }

    public static boolean toggleRotation(Context ctx) {
        try {
            ContentResolver cr = ctx.getContentResolver();
            int autoRot = Settings.System.getInt(cr, Settings.System.ACCELEROMETER_ROTATION, 0);
            int next = autoRot == 1 ? 0 : 1;
            Settings.System.putInt(cr, Settings.System.ACCELEROMETER_ROTATION, next);
            recordDebugEvent("toggleRotation -> auto=" + next);
            return next == 0; // returns true if locked (matches Y0() semantics)
        } catch (Throwable t) {
            Log.e(TAG, "toggleRotation failed", t);
            return false;
        }
    }

    public static boolean isRotationLocked(Context ctx) {
        try {
            return Settings.System.getInt(ctx.getContentResolver(), Settings.System.ACCELEROMETER_ROTATION, 0) == 0;
        } catch (Throwable t) {
            return false;
        }
    }

    public static void toggleUserRotation(Context ctx, boolean left) {
        try {
            ContentResolver cr = ctx.getContentResolver();
            Settings.System.putInt(cr, Settings.System.ACCELEROMETER_ROTATION, 0);
            int rot = Settings.System.getInt(cr, Settings.System.USER_ROTATION, 0);
            int next = (rot == 0) ? (left ? 3 : 1) : 0;
            Settings.System.putInt(cr, Settings.System.USER_ROTATION, next);
        } catch (Throwable t) {
            Log.e(TAG, "toggleUserRotation failed", t);
        }
    }

    public static int getRingerMode(AudioManager am) {
        return am != null ? am.getRingerMode() : AudioManager.RINGER_MODE_NORMAL;
    }

    public static void toggleSoundMode(Context ctx) {
        try {
            AudioManager am = (AudioManager) ctx.getSystemService(Context.AUDIO_SERVICE);
            if (am == null) return;
            NotificationManager nm = (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
            boolean canSilent = nm != null && nm.isNotificationPolicyAccessGranted();
            int cur = am.getRingerMode();
            int next;
            if (canSilent) {
                next = (cur == AudioManager.RINGER_MODE_NORMAL) ? AudioManager.RINGER_MODE_VIBRATE
                        : (cur == AudioManager.RINGER_MODE_VIBRATE) ? AudioManager.RINGER_MODE_SILENT
                        : AudioManager.RINGER_MODE_NORMAL;
            } else {
                next = (cur == AudioManager.RINGER_MODE_NORMAL)
                        ? AudioManager.RINGER_MODE_VIBRATE
                        : AudioManager.RINGER_MODE_NORMAL;
            }
            am.setRingerMode(next);
            recordDebugEvent("toggleSoundMode " + cur + "->" + am.getRingerMode());
        } catch (Throwable t) {
            Log.e(TAG, "toggleSoundMode failed", t);
        }
    }

    public static void toggleDnd(Context ctx) {
        try {
            NotificationManager nm = (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm == null) return;
            if (!nm.isNotificationPolicyAccessGranted()) {
                Intent intent = new Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS);
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                ctx.startActivity(intent);
                toastOnMain(ctx, "Grant Do Not Disturb access for One Hand Operation+");
                return;
            }
            int cur = nm.getCurrentInterruptionFilter();
            int next = (cur == NotificationManager.INTERRUPTION_FILTER_ALL)
                    ? NotificationManager.INTERRUPTION_FILTER_PRIORITY
                    : NotificationManager.INTERRUPTION_FILTER_ALL;
            nm.setInterruptionFilter(next);
        } catch (Throwable t) {
            Log.e(TAG, "toggleDnd failed", t);
        }
    }

    public static void toggleWifi(Context ctx) {
        try {
            Intent panel = new Intent("android.settings.panel.action.WIFI");
            panel.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            ctx.startActivity(panel);
        } catch (Throwable t) {
            try {
                ctx.startActivity(new Intent(Settings.ACTION_WIFI_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            } catch (Throwable ignored) {}
        }
    }

    public static void toggleMobileData(Context ctx) {
        try {
            Intent panel = new Intent("android.settings.panel.action.INTERNET_CONNECTIVITY");
            panel.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            ctx.startActivity(panel);
        } catch (Throwable t) {
            try {
                Intent i = new Intent(Settings.ACTION_DATA_ROAMING_SETTINGS);
                i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                ctx.startActivity(i);
            } catch (Throwable ignored) {
                toastOnMain(ctx, "Open Mobile Data settings to toggle data");
            }
        }
    }

    public static void toggleNfc(Context ctx) {
        try {
            android.nfc.NfcAdapter adapter = android.nfc.NfcAdapter.getDefaultAdapter(ctx);
            if (adapter == null) {
                toastOnMain(ctx, "NFC not supported on this device");
                return;
            }
            boolean enabled = adapter.isEnabled();
            try {
                Method m = android.nfc.NfcAdapter.class.getMethod(enabled ? "disable" : "enable");
                Object res = m.invoke(adapter);
                if (res instanceof Boolean && ((Boolean) res)) {
                    recordDebugEvent("toggleNfc -> " + !enabled);
                    return;
                }
            } catch (Throwable ignored) {}
            Intent i = new Intent(Settings.ACTION_NFC_SETTINGS);
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            ctx.startActivity(i);
        } catch (Throwable t) {
            Log.e(TAG, "toggleNfc failed", t);
        }
    }

    public static void toggleColorInversion(Context ctx) {
        try {
            ContentResolver cr = ctx.getContentResolver();
            int cur = Settings.Secure.getInt(cr, "accessibility_display_inversion_enabled", 0);
            int next = cur == 1 ? 0 : 1;
            Settings.Secure.putInt(cr, "accessibility_display_inversion_enabled", next);
            recordDebugEvent("toggleColorInversion -> " + next);
        } catch (SecurityException se) {
            try {
                Intent i = new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS);
                i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                ctx.startActivity(i);
                toastOnMain(ctx, "Enable Color inversion in Accessibility settings");
            } catch (Throwable ignored) {}
        } catch (Throwable t) {
            Log.e(TAG, "toggleColorInversion failed", t);
        }
    }

    public static void toggleNavBar(Context ctx) {
        try {
            Intent i = new Intent("com.android.settings.GESTURE_NAVIGATION_SETTINGS");
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            if (ctx.getPackageManager().resolveActivity(i, 0) != null) {
                ctx.startActivity(i);
                return;
            }
        } catch (Throwable ignored) {}
        toastOnMain(ctx, "System navigation bar cannot be hidden by apps on OriginOS");
    }

    public static void toggleBluetooth(Context ctx) {
        try {
            BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
            if (adapter != null) {
                boolean enabled = adapter.isEnabled();
                boolean ok = enabled ? adapter.disable() : adapter.enable();
                if (ok) return;
            }
        } catch (Throwable t) {
            Log.w(TAG, "Bluetooth direct toggle restricted: " + t.getMessage());
        }
        try {
            Class<?> smClass = Class.forName("android.os.ServiceManager");
            Method getService = smClass.getMethod("getService", String.class);
            android.os.IBinder binder = (android.os.IBinder) getService.invoke(null, "bluetooth_manager");
            if (binder != null) {
                Class<?> bmStub = Class.forName("android.bluetooth.IBluetoothManager$Stub");
                Method asInterface = bmStub.getMethod("asInterface", android.os.IBinder.class);
                Object bm = asInterface.invoke(null, binder);
                if (bm != null) {
                    BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
                    boolean enabled = adapter != null && adapter.isEnabled();
                    if (enabled) {
                        try {
                            Method disable = bm.getClass().getMethod("disable", String.class, boolean.class);
                            disable.invoke(bm, ctx.getPackageName(), true);
                            return;
                        } catch (Throwable ignored) {}
                    } else {
                        try {
                            Method enable = bm.getClass().getMethod("enable", String.class);
                            enable.invoke(bm, ctx.getPackageName());
                            return;
                        } catch (Throwable ignored) {}
                    }
                }
            }
        } catch (Throwable t2) {
            Log.w(TAG, "IBluetoothManager reflection failed: " + t2.getMessage());
        }
        try {
            ctx.startActivity(new Intent(Settings.ACTION_BLUETOOTH_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        } catch (Throwable ignored) {}
    }

    public static void toggleHotspot(Context ctx) {
        try {
            Intent intent = new Intent();
            intent.setClassName("com.android.settings", "com.android.settings.TetherSettings");
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            ctx.startActivity(intent);
        } catch (Throwable t) {
            try {
                ctx.startActivity(new Intent(Settings.ACTION_WIRELESS_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            } catch (Throwable ignored) {}
        }
    }

    public static void toggleAirplane(Context ctx) {
        try {
            ctx.startActivity(new Intent(Settings.ACTION_AIRPLANE_MODE_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        } catch (Throwable t) {
            Log.e(TAG, "toggleAirplane failed", t);
        }
    }

    public static int getScreenTimeoutSec(Context ctx) {
        try {
            return Settings.System.getInt(ctx.getContentResolver(), Settings.System.SCREEN_OFF_TIMEOUT, 30000) / 1000;
        } catch (Throwable t) {
            return 30;
        }
    }

    public static void setScreenTimeoutSec(Context ctx, int sec) {
        try {
            Settings.System.putInt(ctx.getContentResolver(), Settings.System.SCREEN_OFF_TIMEOUT, sec * 1000);
        } catch (Throwable t) {
            Log.e(TAG, "setScreenTimeoutSec failed", t);
        }
    }

    public static int getMinBrightness() { return 0; }
    public static int getMaxBrightness() { return 255; }

    public static int getBrightness(Context ctx) {
        try {
            float f = Settings.System.getFloat(ctx.getContentResolver(), "screen_brightness_float", -1f);
            if (f >= 0.0f && f <= 1.0f) {
                return Math.max(0, Math.min(255, Math.round(f * 255.0f)));
            }
            return Math.max(0, Math.min(255,
                    Settings.System.getInt(ctx.getContentResolver(), Settings.System.SCREEN_BRIGHTNESS, 100)));
        } catch (Throwable t) {
            return 100;
        }
    }

    public static void setBrightness(Context ctx, int level) {
        try {
            int clamped = Math.max(0, Math.min(255, level));
            android.content.ContentResolver cr = ctx.getContentResolver();
            Settings.System.putInt(cr, Settings.System.SCREEN_BRIGHTNESS, clamped);
            Settings.System.putFloat(cr, "screen_brightness_float", clamped / 255.0f);
        } catch (Throwable t) {
            Log.e(TAG, "setBrightness failed", t);
        }
    }

    public static int getFineVolume(AudioManager am) {
        if (am == null) return 0;
        int max = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
        int cur = am.getStreamVolume(AudioManager.STREAM_MUSIC);
        if (max <= 0) return 0;
        return Math.round((cur * 150.0f) / max);
    }

    public static void setFineVolume(AudioManager am, int fineVol) {
        if (am == null) return;
        int max = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
        if (max <= 0) return;
        int vol = Math.round((fineVol * max) / 150.0f);
        vol = Math.max(0, Math.min(max, vol));
        am.setStreamVolume(AudioManager.STREAM_MUSIC, vol, 0);
    }

    public static void vibrateNormal(Context ctx) {
        vibrateCustom(ctx, 18);
    }

    public static void vibrateCustom(Context ctx, int ms) {
        if (ctx == null || ms <= 0) return;
        try {
            Vibrator v = (Vibrator) ctx.getSystemService(Context.VIBRATOR_SERVICE);
            if (v != null && v.hasVibrator()) {
                v.vibrate(VibrationEffect.createOneShot(Math.max(5, ms), VibrationEffect.DEFAULT_AMPLITUDE));
            }
        } catch (Throwable t) {
            Log.w(TAG, "vibrate failed", t);
        }
    }

    // --- Icon / Shortcut / User / UI helpers ---

    public static Drawable getActivityIcon(PackageManager pm, ComponentName cn) {
        if (pm == null || cn == null) return null;
        try {
            return pm.getActivityIcon(cn);
        } catch (Throwable t) {
            try {
                return pm.getApplicationIcon(cn.getPackageName());
            } catch (Throwable t2) {
                return null;
            }
        }
    }

    public static Drawable getActivityIcon(Context ctx, ComponentName cn) {
        if (ctx == null || cn == null) return null;
        return getActivityIcon(ctx.getPackageManager(), cn);
    }

    public static Drawable getApplicationIcon(PackageManager pm, ApplicationInfo info) {
        if (pm == null || info == null) return null;
        try {
            return info.loadIcon(pm);
        } catch (Throwable t) {
            return null;
        }
    }

    public static Drawable getApplicationIcon(PackageManager pm, String pkg) {
        if (pm == null || pkg == null) return null;
        try {
            return pm.getApplicationIcon(pkg);
        } catch (Throwable t) {
            return null;
        }
    }

    public static Drawable getDrawableForIconTray(Drawable d) {
        return d;
    }

    public static int getCurrentUserId() {
        try {
            return Process.myUserHandle().hashCode() == 0 ? 0 : 0;
        } catch (Throwable t) {
            return 0;
        }
    }

    public static boolean startActivityCompat(Context ctx, ComponentName cn, Bundle options) {
        if (ctx == null || cn == null) return false;
        try {
            Intent i = Intent.makeMainActivity(cn);
            if (i == null) i = new Intent(Intent.ACTION_MAIN);
            i.addCategory(Intent.CATEGORY_LAUNCHER);
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
            if (options != null) {
                ctx.startActivity(i, options);
            } else {
                ctx.startActivity(i);
            }
            return true;
        } catch (Throwable t) {
            Log.e(TAG, "startActivityCompat failed for " + cn, t);
            return false;
        }
    }

    private static final class TrackedOverlay {
        final WindowManager fallbackWm;
        final WindowManager.LayoutParams lastParams;
        WindowManager activeWm;

        TrackedOverlay(WindowManager fallbackWm, WindowManager.LayoutParams lp, WindowManager activeWm) {
            this.fallbackWm = fallbackWm;
            this.lastParams = new WindowManager.LayoutParams();
            this.lastParams.copyFrom(lp);
            this.activeWm = activeWm;
        }
    }

    private static final java.util.WeakHashMap<View, TrackedOverlay> sOverlays = new java.util.WeakHashMap<>();
    private static final java.util.ArrayDeque<String> sDebugEvents = new java.util.ArrayDeque<>(64);
    private static volatile long sLastEnsure2032Ms = 0L;

    public static void recordDebugEvent(String msg) {
        synchronized (sDebugEvents) {
            if (sDebugEvents.size() >= 64) sDebugEvents.removeFirst();
            sDebugEvents.addLast(android.os.SystemClock.uptimeMillis() + ": " + msg);
        }
    }

    public static void recordActionDebug(String action, int pos, int type) {
        recordDebugEvent("action=" + action + " pos=" + pos + " type=" + type);
    }

    public static void dumpDebugState(java.io.PrintWriter pw) {
        synchronized (sOverlays) {
            pw.println("TrackedOverlays=" + sOverlays.size());
            for (java.util.Map.Entry<View, TrackedOverlay> e : sOverlays.entrySet()) {
                View v = e.getKey();
                TrackedOverlay t = e.getValue();
                pw.println("  view=" + v + " parent=" + (v != null ? v.getParent() : null)
                        + " attached=" + (v != null && v.isAttachedToWindow())
                        + " type=" + (t != null ? t.lastParams.type : -1)
                        + " activeWm=" + (t != null ? t.activeWm : null));
            }
        }
        synchronized (sDebugEvents) {
            pw.println("RecentDebugEvents=" + sDebugEvents.size());
            for (String s : sDebugEvents) {
                pw.println("  " + s);
            }
        }
    }

    public static void applyHandleAlpha(View mainView, WindowManager.LayoutParams lp, float requestedAlpha) {
        if (mainView != null) {
            mainView.setAlpha(requestedAlpha);
        }
        if (lp != null) {
            lp.alpha = 1.0f;
        }
    }

    public static void addHandlerOverlayView(WindowManager fallbackWm, View view, android.view.ViewGroup.LayoutParams rawParams) {
        WindowManager.LayoutParams lp = (WindowManager.LayoutParams) rawParams;
        lp.alpha = 1.0f;
        WindowManager a11yWm = SGPCompatAccessibilityService.getAccessibilityWindowManager();
        WindowManager directA11yWm = SGPCompatAccessibilityService.getDirectWindowManager();
        TrackedOverlay existing;
        synchronized (sOverlays) { existing = sOverlays.get(view); }
        if (view != null && (view.getParent() != null || view.isAttachedToWindow())) {
            boolean alreadyOnA11y = (a11yWm != null && existing != null && existing.activeWm == a11yWm)
                    || (directA11yWm != null && existing != null && existing.activeWm == directA11yWm);
            boolean noA11y = (a11yWm == null && directA11yWm == null && existing != null && existing.activeWm == fallbackWm);
            if (alreadyOnA11y || noA11y) {
                existing.lastParams.copyFrom(lp);
                lp.type = alreadyOnA11y
                        ? WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY
                        : WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY;
                try {
                    existing.activeWm.updateViewLayout(view, lp);
                } catch (Throwable ignored) {}
                return;
            }
            if (existing != null && existing.activeWm != null) {
                try { existing.activeWm.removeViewImmediate(view); } catch (Throwable ignored) {}
            }
            if ((view.getParent() != null || view.isAttachedToWindow()) && fallbackWm != null) {
                try { fallbackWm.removeViewImmediate(view); } catch (Throwable ignored) {}
            }
        }
        int origType = lp.type;
        WindowManager[] a11yCandidates = new WindowManager[] { a11yWm, directA11yWm };
        for (WindowManager cand : a11yCandidates) {
            if (cand == null) continue;
            try {
                lp.token = null;
                lp.type = WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY;
                cand.addView(view, lp);
                synchronized (sOverlays) { sOverlays.put(view, new TrackedOverlay(fallbackWm, lp, cand)); }
                String msg = "Added overlay " + lp.getTitle() + " via 2032 wm=" + cand;
                Log.i(TAG, msg);
                recordDebugEvent(msg);
                return;
            } catch (Throwable t) {
                String msg = "2032 failed (" + lp.getTitle() + ", wm=" + cand + "): " + t.getMessage();
                Log.w(TAG, msg);
                recordDebugEvent(msg);
                lp.type = origType;
            }
        }
        if (fallbackWm == null) return;
        lp.token = null;
        lp.type = WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY;
        fallbackWm.addView(view, lp);
        synchronized (sOverlays) { sOverlays.put(view, new TrackedOverlay(fallbackWm, lp, fallbackWm)); }
        String msg = "Added overlay " + lp.getTitle() + " via fallback 2038";
        Log.i(TAG, msg);
        recordDebugEvent(msg);
        if (SGPCompatAccessibilityService.isConnected()) {
            refreshOverlaysForAccessibility(true, 1);
        }
    }

    public static void updateHandlerOverlayView(WindowManager fallbackWm, View view, android.view.ViewGroup.LayoutParams rawParams) {
        WindowManager.LayoutParams lp = (WindowManager.LayoutParams) rawParams;
        lp.alpha = 1.0f;
        TrackedOverlay entry;
        synchronized (sOverlays) { entry = sOverlays.get(view); }
        if (entry == null) {
            addHandlerOverlayView(fallbackWm, view, lp);
            return;
        }
        WindowManager a11yWm = SGPCompatAccessibilityService.getAccessibilityWindowManager();
        WindowManager directWm = SGPCompatAccessibilityService.getDirectWindowManager();
        boolean hasA11y = (a11yWm != null || directWm != null);
        boolean isCurrently2032 = entry.lastParams.type == WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY
                && ((a11yWm != null && entry.activeWm == a11yWm) || (directWm != null && entry.activeWm == directWm));
        entry.lastParams.copyFrom(lp);
        boolean attached = view != null && (view.getParent() != null || view.isAttachedToWindow());
        if (!attached || (hasA11y && !isCurrently2032)) {
            if (attached && entry.activeWm != null) {
                try { entry.activeWm.removeViewImmediate(view); } catch (Throwable ignored) {}
            }
            addHandlerOverlayView(fallbackWm, view, lp);
            return;
        }
        lp.type = isCurrently2032
                ? WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY
                : WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY;
        entry.lastParams.type = lp.type;
        if (sHandlersPassThrough) {
            CharSequence title = lp.getTitle();
            if (title != null && title.toString().startsWith("ThumbsUpHandler")) {
                lp.flags |= WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE;
            }
        }
        try {
            entry.activeWm.updateViewLayout(view, lp);
        } catch (Throwable t) {
            Log.w(TAG, "updateHandlerOverlayView failed, re-adding: " + t.getMessage());
            addHandlerOverlayView(fallbackWm, view, lp);
        }
    }

    public static void removeHandlerOverlayView(WindowManager fallbackWm, View view) {
        TrackedOverlay entry;
        synchronized (sOverlays) { entry = sOverlays.remove(view); }
        WindowManager wm = entry != null ? entry.activeWm : fallbackWm;
        if (wm != null && view != null) {
            try { wm.removeViewImmediate(view); } catch (Throwable ignored) {}
        }
    }

    public static void onAccessibilityConnectionChanged(boolean connected) {
        sLastEnsure2032Ms = 0L;
        refreshOverlaysForAccessibility(connected, 0);
    }

    public static void ensure2032IfNeeded() {
        if (!SGPCompatAccessibilityService.isConnected()) return;
        long now = SystemClock.uptimeMillis();
        if (now - sLastEnsure2032Ms < 1500L) return;
        sLastEnsure2032Ms = now;
        WindowManager a11yWm = SGPCompatAccessibilityService.getAccessibilityWindowManager();
        WindowManager directWm = SGPCompatAccessibilityService.getDirectWindowManager();
        if (a11yWm == null && directWm == null) return;
        boolean needsHeal = false;
        synchronized (sOverlays) {
            for (java.util.Map.Entry<View, TrackedOverlay> e : sOverlays.entrySet()) {
                View v = e.getKey();
                TrackedOverlay t = e.getValue();
                if (v == null || t == null) continue;
                boolean is2032 = t.lastParams.type == WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY
                        && ((a11yWm != null && t.activeWm == a11yWm) || (directWm != null && t.activeWm == directWm))
                        && (v.getParent() != null || v.isAttachedToWindow());
                if (!is2032) {
                    needsHeal = true;
                    break;
                }
            }
        }
        if (needsHeal) {
            refreshOverlaysForAccessibility(true, 1);
        }
    }

    private static void refreshOverlaysForAccessibility(boolean connected, int attempt) {
        long delayMs = connected ? (attempt == 0 ? 150L : (attempt == 1 ? 500L : 1000L)) : 0L;
        new Handler(Looper.getMainLooper()).postDelayed(() -> {
            if (connected) {
                if (attempt > 0) {
                    SGPCompatAccessibilityService.refreshAccessibilityWindowManager();
                }
                if (SGPCompatAccessibilityService.getAccessibilityWindowManager() == null) {
                    return;
                }
            }
            java.util.List<java.util.Map.Entry<View, TrackedOverlay>> entries;
            synchronized (sOverlays) {
                entries = new java.util.ArrayList<>(sOverlays.entrySet());
            }
            WindowManager a11yWm = SGPCompatAccessibilityService.getAccessibilityWindowManager();
            WindowManager directWm = SGPCompatAccessibilityService.getDirectWindowManager();
            boolean needsRetry = false;
            for (java.util.Map.Entry<View, TrackedOverlay> e : entries) {
                View v = e.getKey();
                TrackedOverlay t = e.getValue();
                if (v == null || t == null) continue;
                try {
                    boolean already2032 = connected
                            && t.lastParams.type == WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY
                            && ((a11yWm != null && t.activeWm == a11yWm) || (directWm != null && t.activeWm == directWm))
                            && (v.getParent() != null || v.isAttachedToWindow());
                    if (already2032) {
                        continue;
                    }
                    if (v.getParent() != null || v.isAttachedToWindow()) {
                        if (t.activeWm != null) {
                            try { t.activeWm.removeViewImmediate(v); } catch (Throwable ignored) {}
                        }
                        if (v.getParent() != null && t.fallbackWm != null && t.fallbackWm != t.activeWm) {
                            try { t.fallbackWm.removeViewImmediate(v); } catch (Throwable ignored) {}
                        }
                    }
                    addHandlerOverlayView(t.fallbackWm, v, t.lastParams);
                    if (connected && (a11yWm != null || directWm != null)) {
                        TrackedOverlay updated;
                        synchronized (sOverlays) { updated = sOverlays.get(v); }
                        if (updated == null || updated.lastParams.type != WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY) {
                            needsRetry = true;
                        }
                    }
                } catch (Throwable err) {
                    Log.w(TAG, "Failed to refresh overlay on a11y change", err);
                    recordDebugEvent("refresh err: " + err.getMessage());
                    if (connected) needsRetry = true;
                }
            }
            if (connected && needsRetry && attempt < 5) {
                refreshOverlaysForAccessibility(true, attempt + 1);
            }
        }, delayMs);
    }

    public static void setEdgeBackGestureDisabled(Context ctx, boolean disable) {
        if (ctx == null) return;
        try {
            Settings.Global.putInt(ctx.getContentResolver(), "navigation_bar_gesture_disabled_by_policy", disable ? 2 : 0);
        } catch (Throwable ignored) {}
        try {
            // OriginOS / Vivo uses navigation_gesture_slide_back (1=enabled, 0=disabled)
            Settings.Secure.putInt(ctx.getContentResolver(), "navigation_gesture_slide_back", disable ? 0 : 1);
            Log.i(TAG, "setEdgeBackGestureDisabled(" + disable + ") -> navigation_gesture_slide_back=" + (disable ? 0 : 1));
        } catch (Throwable t) {
            Log.w(TAG, "Failed to update navigation_gesture_slide_back: " + t.getMessage());
        }
    }

    public static void registerContentObserverSafe(
            android.content.ContentResolver cr,
            android.net.Uri uri,
            boolean notifyForDescendants,
            android.database.ContentObserver observer) {
        if (cr == null || uri == null || observer == null) return;
        try {
            cr.registerContentObserver(uri, notifyForDescendants, observer);
        } catch (Throwable t) {
            Log.w(TAG, "Skipping unreachable ContentProvider observer for " + uri + ": " + t.getMessage());
        }
    }

    public static void setSeekBarMode(SeekBar sb, int mode) {
        // No-op on non-Samsung SESL SeekBar
    }

    public static void setBlurDisabled(Object v) {
        // No-op fallback for SemBlurInfo / semSetBackgroundBlurEnabled on Views and Dialogs
    }

    public static String getSystemProperty(String key) {
        if (TextUtils.isEmpty(key)) return "";
        try {
            Class<?> sp = Class.forName("android.os.SystemProperties");
            Method m = sp.getMethod("get", String.class, String.class);
            Object r = m.invoke(null, key, "");
            return r != null ? r.toString() : "";
        } catch (Throwable t) {
            return "";
        }
    }

    public static boolean forceHideSoftInput(android.view.inputmethod.InputMethodManager imm) {
        if (imm == null) return false;
        try {
            return imm.hideSoftInputFromWindow(null, 0);
        } catch (Throwable t) {
            return false;
        }
    }

    public static ComponentName startServiceAsUserCompat(Context ctx, Intent intent) {
        return startServiceCompat(ctx, intent);
    }

    public static boolean isKeyguardShowingAndNotOccluded(android.app.KeyguardManager km) {
        return km != null && km.isKeyguardLocked();
    }

    public static UserHandle getOwnerUserHandle() {
        return Process.myUserHandle();
    }

    public static void populateRecentTasks(Context ctx, List<Object> outList, int iconSizePx) {
        if (ctx == null || outList == null) return;
        try {
            PackageManager pm = ctx.getPackageManager();
            Class<?> itemCls = Class.forName("f5.e");
            java.lang.reflect.Field fCn = itemCls.getField("a");
            java.lang.reflect.Field fLabel = itemCls.getField("b");
            java.lang.reflect.Field fIcon = itemCls.getField("c");
            java.lang.reflect.Field fValid = itemCls.getField("d");
            java.lang.reflect.Field fTaskId = itemCls.getField("e");
            java.lang.reflect.Field fUserId = itemCls.getField("f");
            java.lang.reflect.Field fLocked = itemCls.getField("g");
            java.lang.reflect.Field fCanSplit = itemCls.getField("h");

            java.util.HashSet<String> seen = new java.util.HashSet<>();
            for (Object existing : outList) {
                if (existing == null) continue;
                Object cnObj = fCn.get(existing);
                if (cnObj instanceof String) {
                    ComponentName existingCn = ComponentName.unflattenFromString((String) cnObj);
                    if (existingCn != null) {
                        seen.add(existingCn.getPackageName());
                    }
                }
            }
            seen.add(ctx.getPackageName());
            seen.add("com.android.systemui");
            String launcherPkg = getDefaultLauncherPackage(ctx);
            if (!TextUtils.isEmpty(launcherPkg)) seen.add(launcherPkg);

            ArrayList<String> orderedPkgs = new ArrayList<>();
            for (String p : SGPCompatAccessibilityService.getRecentPackageHistory()) {
                if (!TextUtils.isEmpty(p) && seen.add(p)) {
                    orderedPkgs.add(p);
                }
            }
            for (String p : getRecentLaunchablePackages(ctx, 25)) {
                if (!TextUtils.isEmpty(p) && seen.add(p)) {
                    orderedPkgs.add(p);
                }
            }
            if (orderedPkgs.isEmpty()) return;

            int idx = 1;
            int iconPx = Math.max(96, iconSizePx);
            for (String pkg : orderedPkgs) {
                Intent launch = pm.getLaunchIntentForPackage(pkg);
                if (launch == null || launch.getComponent() == null) continue;
                ComponentName cn = launch.getComponent();
                ApplicationInfo ai = pm.getApplicationInfo(pkg, 0);
                String label = pm.getApplicationLabel(ai).toString();
                Drawable d = pm.getActivityIcon(cn);
                android.graphics.Bitmap bmp = drawableToBitmap(d, iconPx);
                android.graphics.drawable.BitmapDrawable bd = new android.graphics.drawable.BitmapDrawable(ctx.getResources(), bmp);

                Object item = itemCls.getDeclaredConstructor().newInstance();
                fCn.set(item, cn.flattenToString());
                fLabel.set(item, label);
                fIcon.set(item, bd);
                fValid.setBoolean(item, true);
                fTaskId.setInt(item, -1000 - idx);
                fUserId.setInt(item, 0);
                fLocked.setBoolean(item, false);
                fCanSplit.setBoolean(item, true);
                outList.add(item);
                idx++;
                if (idx > 20) break;
            }
            recordDebugEvent("populateRecentTasks added=" + (idx - 1));
        } catch (Throwable t) {
            Log.e(TAG, "populateRecentTasks failed", t);
        }
    }

    private static android.graphics.Bitmap drawableToBitmap(Drawable d, int size) {
        if (d instanceof android.graphics.drawable.BitmapDrawable) {
            android.graphics.Bitmap b = ((android.graphics.drawable.BitmapDrawable) d).getBitmap();
            if (b != null) return b;
        }
        android.graphics.Bitmap b = android.graphics.Bitmap.createBitmap(size, size, android.graphics.Bitmap.Config.ARGB_8888);
        android.graphics.Canvas c = new android.graphics.Canvas(b);
        d.setBounds(0, 0, size, size);
        d.draw(c);
        return b;
    }

    public static boolean isActionSupported(Context ctx, String action) {
        if (TextUtils.isEmpty(action)) return false;
        // Hide only truly Samsung-exclusive hardware/system actions that have no Vivo equivalent
        switch (action) {
            case "toggle_privacydisplay":
            case "smart_select":
            case "smartcapture_rect":
            case "smartcapture_oval":
            case "smartcapture_gif":
            case "smartcapture_pin":
            case "screen_recorder":
            case "show_edge":
            case "samsung_wallet":
            case "manual_routine":
            case "quick_gametools":
            case "run_finder":
            case "toggle_taskbar":
            case "toggle_navibar":
            case "reduce_screen":
            case "move_screen_down":
            case "screen_magnifier":
            case "launch_memory":
            case "launch_modes":
            case "kill_app":
            case "run_popup_view":
            case "min_popup_view":
                return false;
            default:
                return true;
        }
    }
}
