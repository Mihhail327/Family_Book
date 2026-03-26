let lastNotificationId = null;
// ==========================================
// 1. PWA SERVICE WORKER
// ==========================================
if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
        navigator.serviceWorker
            .register("/static/sw.js")
            .then(() => console.log("🛡️ SW активирован"))
            .catch((err) => console.error("❌ PWA Error:", err));
    });
}

// ==========================================
// 2. ГЛОБАЛЬНАЯ ТАКТИЛЬНОСТЬ (Haptics)
// ==========================================
document.addEventListener('click', (e) => {
    const target = e.target.closest('.haptic-btn');
    if (target && "vibrate" in navigator) {
        navigator.vibrate(15); 
    }
});

// ==========================================
// 3. УТИЛИТЫ (Время и Темы)
// ==========================================

// Локальное время (Jinja2 передает UTC, мы превращаем в местное)
window.convertToLocalTime = function() {
    document.querySelectorAll(".local-time").forEach((el) => {
        let utcData = el.getAttribute("data-utc");
        if (!utcData) return;
        if (!utcData.endsWith("Z") && !utcData.includes("+")) utcData += "Z";

        const date = new Date(utcData);
        if (!isNaN(date.getTime())) {
            el.textContent = date.toLocaleString("ru-RU", {
                day: "2-digit", month: "2-digit", year: "numeric",
                hour: "2-digit", minute: "2-digit",
            }).replace(",", " •");
        }
    });
}

document.addEventListener("DOMContentLoaded", window.convertToLocalTime);
document.addEventListener("htmx:afterSwap", window.convertToLocalTime);

// Глобальная тема
window.toggleTheme = () => {
    const isDark = document.documentElement.classList.toggle('dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    if ('vibrate' in navigator) navigator.vibrate(10);
};

(function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
        document.documentElement.classList.add('dark');
    }
})();

// Эффект курсора (Mouse Glow)
document.addEventListener('mousemove', (e) => {
    const x = (e.clientX / window.innerWidth) * 100;
    const y = (e.clientY / window.innerHeight) * 100;
    document.documentElement.style.setProperty('--mouse-x', `${x}%`);
    document.documentElement.style.setProperty('--mouse-y', `${y}%`);
});

// ==========================================
// 4. СИСТЕМА УВЕДОМЛЕНИЙ (Real-time)
// ==========================================

async function checkGlobalNotifications() {
    try {
        const res = await fetch('/admin/api/notifications/latest'); 
        if (res.ok) {
            const data = await res.json();
            
            // ПРОВЕРКА: Если уведомления нет или ID совпадает с прошлым — выходим
            if (!data || !data.new_message || data.id === lastNotificationId) {
                return;
            }

            // Запоминаем ID текущего уведомления
            lastNotificationId = data.id;

            // Теперь уведомление сработает только один раз
            window.dispatchEvent(new CustomEvent('new-broadcast', { 
                detail: { 
                    message: data.message,
                    category: data.category || 'info',
                    new_count: data.count || 1 
                } 
            }));

            // Проигрываем звук (один раз!)
            const audio = document.getElementById('notificationSound');
            if (audio) audio.play().catch(() => {});

        }
    } catch (e) {
        console.error("Ошибка уведомлений:", e);
    }
}

// Запускаем проверку раз в 45 секунд
setInterval(checkGlobalNotifications, 45000);

console.log("🚀 Family_Book UI Core Loaded");

// ==========================================
// 5. АДМИН-ФУНКЦИИ (Broadcast)
// ==========================================

window.sendBroadcast = async function(e) {
    const form = e.target;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    
    // Кнопка отправки для индикации загрузки
    const btn = form.querySelector('button[type="submit"]');
    const originalText = btn.innerHTML;
    
    try {
        btn.disabled = true;
        btn.innerHTML = '🚀 Отправка...';

        const res = await fetch('/admin/broadcast', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });

        if (res.ok) {
            // Очищаем форму
            form.reset();
            // Можно вызвать системное уведомление, если оно у тебя есть
            alert('Рассылка успешно отправлена во все устройства Семьи!');
        } else {
            const err = await res.json();
            alert('Ошибка: ' + (err.detail || 'Не удалось отправить'));
        }
    } catch (error) {
        console.error('Broadcast Error:', error);
        alert('Критическая ошибка сети');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
};