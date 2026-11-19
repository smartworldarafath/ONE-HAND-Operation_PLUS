package com.samsung.android.sidegesturepad.compat;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.AccessibilityServiceInfo;
import android.accessibilityservice.GestureDescription;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Path;
import android.graphics.PointF;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.text.TextUtils;
import android.util.Log;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityEvent;
import java.util.ArrayList;
import java.util.LinkedList;
import java.util.List;

public class SGPCompatAccessibilityService extends AccessibilityService {
    private static final String TAG = "SGPCompatA11y";
    private static volatile SGPCompatAccessibilityService sInstance;
    private static volatile WindowManager sA11yWm;
    private static volatile boolean sPanelExpanded = false;
    private static volatile String sTopPackage = "";
    private static volatile String sTopClass = "";
    private static final LinkedList<String> sRecentPackages = new LinkedList<>();
    private static volatile ForegroundListener sListener;

    public interface ForegroundListener {
        void onForegroundChanged(String pkg, String cls);
    }

    public static void setForegroundListener(ForegroundListener listener) {
        sListener = listener;
    }

    public static SGPCompatAccessibilityService getInstance() {
        return sInstance;
    }

    public static boolean isConnected() {
        return sInstance != null;
    }

    public static boolean isPanelExpanded() {
        return sPanelExpanded;
    }

    public static String getTopPackage() {
        return sTopPackage;
    }

    public static String getTopClass() {
        return sTopClass;
    }

    public static List<String> getRecentPackageHistory() {
        synchronized (sRecentPackages) {
            return new ArrayList<>(sRecentPackages);
        }
    }

    public static boolean performGlobal(int action) {
        SGPCompatAccessibilityService svc = sInstance;
        if (svc == null) {
            Log.w(TAG, "performGlobal(" + action + ") failed: service not connected");
            return false;
        }
        try {
            boolean ok = svc.performGlobalAction(action);
            Log.i(TAG, "performGlobal(" + action + ") -> " + ok);
            return ok;
        } catch (Throwable t) {
            Log.e(TAG, "performGlobal(" + action + ") error", t);
            return false;
        }
    }

    public static boolean dispatchTap(float x, float y, long durationMs) {
        List<PointF> pts = new ArrayList<>(2);
        pts.add(new PointF(x, y));
        pts.add(new PointF(x, y));
        return dispatchStroke(pts, Math.max(20L, durationMs));
    }

    public static boolean dispatchStroke(List<PointF> points, long durationMs) {
        return dispatchStroke(points, durationMs, null);
    }

    public static boolean dispatchStroke(List<PointF> points, long durationMs, final Runnable onDone) {
        SGPCompatAccessibilityService svc = sInstance;
        if (svc == null || points == null || points.isEmpty()) {
            if (onDone != null) onDone.run();
            return false;
        }
        try {
            Path path = new Path();
            PointF first = points.get(0);
            path.moveTo(first.x, first.y);
            boolean hasLength = false;
            for (int i = 1; i < points.size(); i++) {
                PointF p = points.get(i);
                float dx = p.x - first.x;
                float dy = p.y - first.y;
                if (dx * dx + dy * dy >= 1.0f) hasLength = true;
                path.lineTo(p.x, p.y);
            }
            if (!hasLength) {
                path.lineTo(first.x, first.y + 1.0f);
            }
            long dur = Math.max(30L, Math.min(durationMs, 3000L));
            GestureDescription.StrokeDescription stroke = new GestureDescription.StrokeDescription(path, 0L, dur);
            GestureDescription desc = new GestureDescription.Builder().addStroke(stroke).build();
            AccessibilityService.GestureResultCallback cb = null;
            if (onDone != null) {
                cb = new AccessibilityService.GestureResultCallback() {
                    @Override
                    public void onCompleted(GestureDescription gestureDescription) {
                        onDone.run();
                    }

                    @Override
                    public void onCancelled(GestureDescription gestureDescription) {
                        onDone.run();
                    }
                };
            }
            boolean ok = svc.dispatchGesture(desc, cb, null);
            if (!ok && onDone != null) {
                onDone.run();
            }
            return ok;
        } catch (Throwable t) {
            Log.e(TAG, "dispatchStroke failed", t);
            if (onDone != null) onDone.run();
            return false;
        }
    }

    public static boolean isServiceEnabledInSettings(Context ctx) {
        try {
            String enabled = Settings.Secure.getString(ctx.getContentResolver(), Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);
            if (TextUtils.isEmpty(enabled)) return false;
            String expected = new ComponentName(ctx.getPackageName(), SGPCompatAccessibilityService.class.getName()).flattenToString();
            String shortName = ctx.getPackageName() + "/.compat.SGPCompatAccessibilityService";
            return enabled.contains(expected) || enabled.contains(shortName);
        } catch (Throwable t) {
            return false;
        }
    }

    public static WindowManager getAccessibilityWindowManager() {
        return sA11yWm;
    }

    public static WindowManager refreshAccessibilityWindowManager() {
        SGPCompatAccessibilityService svc = sInstance;
        if (svc == null) return null;
        try {
            Context wc = svc.createWindowContext(WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY, null);
            sA11yWm = wc.getSystemService(WindowManager.class);
        } catch (Throwable t) {
            try {
                sA11yWm = (WindowManager) svc.getSystemService(Context.WINDOW_SERVICE);
            } catch (Throwable ignored) {}
        }
        VivoCompat.recordDebugEvent("refreshA11yWm -> " + sA11yWm);
        return sA11yWm;
    }

    public static WindowManager getDirectWindowManager() {
        SGPCompatAccessibilityService svc = sInstance;
        if (svc == null) return null;
        try {
            return (WindowManager) svc.getSystemService(Context.WINDOW_SERVICE);
        } catch (Throwable t) {
            return null;
        }
    }

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        sInstance = this;
        try {
            AccessibilityServiceInfo info = getServiceInfo();
            if (info == null) {
                info = new AccessibilityServiceInfo();
            }
            info.eventTypes = AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED;
            info.feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC;
            info.notificationTimeout = 50;
            info.flags |= AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS
                    | AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS;
            setServiceInfo(info);
        } catch (Throwable t) {
            Log.e(TAG, "setServiceInfo failed", t);
        }
        refreshAccessibilityWindowManager();
        Log.i(TAG, "onServiceConnected() wm=" + sA11yWm);
        VivoCompat.onAccessibilityConnectionChanged(true);

        // Start SGPService if user had One Hand Operation+ enabled
        try {
            SharedPreferences prefs = getSharedPreferences("sidegesturepad_prefs", MODE_PRIVATE);
            if (prefs.getBoolean("sidegesturepad_enabled", false)) {
                Intent svcIntent = new Intent("com.samsung.action.SIDEGESTUREPAD_SERVICE");
                svcIntent.setComponent(new ComponentName(getPackageName(), "com.samsung.android.sidegesturepad.SGPService"));
                svcIntent.putExtra("option", "start");
                VivoCompat.startServiceCompat(this, svcIntent);
            }
        } catch (Throwable t) {
            Log.e(TAG, "auto-start SGPService failed", t);
        }
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        if (event == null) return;
        VivoCompat.ensure2032IfNeeded();
        if (event.getEventType() != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) return;

        CharSequence pkgCs = event.getPackageName();
        CharSequence clsCs = event.getClassName();
        if (pkgCs == null) return;
        String pkg = pkgCs.toString();
        String cls = clsCs != null ? clsCs.toString() : "";

        // Ignore our own overlay windows
        if ("com.samsung.android.sidegesturepad".equals(pkg)) {
            if (!cls.contains("Activity")) {
                return;
            }
        }

        // Track SystemUI / Vivo Control Center panel state
        if ("com.android.systemui".equals(pkg) || "com.vivo.systemuiplugin".equals(pkg)) {
            String lower = cls.toLowerCase();
            if (lower.contains("notification") || lower.contains("panel") || lower.contains("shade")
                    || lower.contains("supercenter") || lower.contains("control") || lower.contains("quicksettings")) {
                sPanelExpanded = true;
                return;
            }
            // Volume dialog / toast / etc. shouldn't overwrite foreground app
            return;
        }

        // Ignore IME windows
        if (cls.contains("InputMethod") || cls.contains("SoftKeyboard")) {
            return;
        }

        sPanelExpanded = false;
        if (!pkg.equals(sTopPackage)) {
            sTopPackage = pkg;
            sTopClass = cls;
            synchronized (sRecentPackages) {
                sRecentPackages.remove(pkg);
                sRecentPackages.addFirst(pkg);
                while (sRecentPackages.size() > 20) {
                    sRecentPackages.removeLast();
                }
            }
        } else {
            sTopClass = cls;
        }

        ForegroundListener l = sListener;
        if (l != null) {
            try {
                l.onForegroundChanged(pkg, cls);
            } catch (Throwable ignored) {}
        }
    }

    @Override
    public void onInterrupt() {
        Log.i(TAG, "onInterrupt()");
    }

    @Override
    public boolean onUnbind(Intent intent) {
        Log.i(TAG, "onUnbind()");
        if (sInstance == this) {
            sInstance = null;
            sA11yWm = null;
            VivoCompat.onAccessibilityConnectionChanged(false);
        }
        return super.onUnbind(intent);
    }

    @Override
    protected void dump(java.io.FileDescriptor fd, java.io.PrintWriter pw, String[] args) {
        super.dump(fd, pw, args);
        pw.println("--- SGPCompatAccessibilityService Debug ---");
        pw.println("sInstance=" + sInstance + " sA11yWm=" + sA11yWm + " sTopPackage=" + sTopPackage);
        VivoCompat.dumpDebugState(pw);
    }

    @Override
    public void onDestroy() {
        Log.i(TAG, "onDestroy()");
        if (sInstance == this) {
            sInstance = null;
            sA11yWm = null;
            VivoCompat.onAccessibilityConnectionChanged(false);
        }
        super.onDestroy();
    }
}
