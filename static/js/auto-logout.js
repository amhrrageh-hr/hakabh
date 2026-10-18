/**
 * نظام تسجيل الخروج التلقائي عند عدم النشاط (Inactivity Auto-Logout)
 * - المهلة: 5 دقائق (300,000 مللي ثانية)
 * - مراقبة حركة الماوس، لوحة المفاتيح، التمرير، واللمس على شاشات الجوال
 * - مزامنة الخمول عبر علامات التبويب المتعددة (Cross-tab sync via localStorage)
 * - فحص فوري عند عودة التركيز أو استيقاظ الجهاز من وضع السكون (Page Visibility & Focus)
 */
(function () {
    'use strict';

    // المهلة الزمنية: 5 دقائق
    const IDLE_TIMEOUT_MS = 5 * 60 * 1000;
    const STORAGE_KEY = 'hakbah_last_user_activity';

    let lastActivityTime = Date.now();
    try {
        localStorage.setItem(STORAGE_KEY, String(lastActivityTime));
    } catch (e) {
        // في حال كان التخزين المحلي غير متاح
    }

    let isLoggingOut = false;

    function performAutoLogout() {
        if (isLoggingOut) return;
        isLoggingOut = true;

        try {
            localStorage.removeItem(STORAGE_KEY);
            sessionStorage.clear();
        } catch (e) {}

        // إعادة التوجيه الفوري لمسار تسجيل الخروج مع وسم timeout
        window.location.replace('/logout?timeout=1');
    }

    function recordActivity() {
        const now = Date.now();
        // تقليل وتيرة التحديث (Throttle) إلى مرة واحدة كل ثانية لتوفير الأداء
        if (now - lastActivityTime > 1000) {
            lastActivityTime = now;
            try {
                localStorage.setItem(STORAGE_KEY, String(now));
            } catch (e) {}
        }
    }

    function checkInactivity() {
        if (isLoggingOut) return;

        let latest = lastActivityTime;
        try {
            const stored = parseInt(localStorage.getItem(STORAGE_KEY) || '0', 10);
            if (stored > latest) {
                latest = stored;
                lastActivityTime = stored;
            }
        } catch (e) {}

        const elapsed = Date.now() - latest;
        if (elapsed >= IDLE_TIMEOUT_MS) {
            performAutoLogout();
        }
    }

    // الاستماع لأحداث تفاعل المستخدم
    const activityEvents = [
        'mousedown', 'mousemove', 'keydown',
        'scroll', 'touchstart', 'click', 'wheel'
    ];

    activityEvents.forEach(eventType => {
        window.addEventListener(eventType, recordActivity, { passive: true });
    });

    // مزامنة النشاط عبر علامات التبويب المتعددة
    window.addEventListener('storage', (event) => {
        if (event.key === STORAGE_KEY && event.newValue) {
            const remoteTime = parseInt(event.newValue, 10);
            if (remoteTime > lastActivityTime) {
                lastActivityTime = remoteTime;
            }
        }
    });

    // فحص فوري عند عودة المستخدم للصفحة أو استيقاظ الجهاز من السكون
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            checkInactivity();
        }
    });

    window.addEventListener('focus', checkInactivity);

    // فحص دوري كل ثانيتين للتأكد من عدم تجاوز المهلة
    setInterval(checkInactivity, 2000);
})();
