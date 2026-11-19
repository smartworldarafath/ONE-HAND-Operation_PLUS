package com.samsung.android.sidegesturepad.compat;

import android.graphics.Color;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.view.View;

public class CompatBlurInfo {
    public final int blurMode;
    public final int backgroundColor;
    public final float cornerRadius;
    public final int radius;

    CompatBlurInfo(int blurMode, int backgroundColor, float cornerRadius, int radius) {
        this.blurMode = blurMode;
        this.backgroundColor = backgroundColor;
        this.cornerRadius = cornerRadius;
        this.radius = radius;
    }

    public static void apply(Object target, CompatBlurInfo info) {
        if (target == null || info == null) return;
        if (target instanceof View) {
            View v = (View) target;
            try {
                Drawable bg = v.getBackground();
                if (bg instanceof GradientDrawable && info.backgroundColor != 0) {
                    // Preserve existing XML rounded border / background if already set
                    return;
                }
                if (bg == null && info.backgroundColor != 0) {
                    GradientDrawable gd = new GradientDrawable();
                    gd.setColor(info.backgroundColor);
                    if (info.cornerRadius > 0f) {
                        gd.setCornerRadius(info.cornerRadius);
                    }
                    v.setBackground(gd);
                }
            } catch (Throwable ignored) {}
        }
    }

    public static class Builder {
        private final int mBlurMode;
        private int mBackgroundColor = Color.TRANSPARENT;
        private float mCornerRadius = 0f;
        private int mRadius = 0;

        public Builder(int blurMode) {
            this.mBlurMode = blurMode;
        }

        public Builder setBackgroundColor(int color) {
            this.mBackgroundColor = color;
            return this;
        }

        public Builder setBackgroundCornerRadius(float radius) {
            this.mCornerRadius = radius;
            return this;
        }

        public Builder setRadius(int radius) {
            this.mRadius = radius;
            return this;
        }

        public CompatBlurInfo build() {
            return new CompatBlurInfo(mBlurMode, mBackgroundColor, mCornerRadius, mRadius);
        }
    }
}
