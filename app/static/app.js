let lastNotificationId = null;
// ==========================================
//  PWA SERVICE WORKER
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
//  ГЛОБАЛЬНАЯ ТАКТИЛЬНОСТЬ (Haptics)
// ==========================================
document.addEventListener('click', (e) => {
    const target = e.target.closest('.haptic-btn');
    if (target && "vibrate" in navigator) {
        navigator.vibrate(15); 
    }
});

// ==========================================
//  УТИЛИТЫ (Время и Темы)
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
//  АДМИН-ФУНКЦИИ (Broadcast)
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
            form.reset();
            
            // Вместо серого окошка вызываем твое стильное уведомление
            window.dispatchEvent(new CustomEvent('new-broadcast', { 
                detail: { 
                    title: 'Успех!',
                    message: 'Рассылка успешно запущена для всей семьи! 🚀',
                    category: 'success'
                } 
            }));

        } else {
            const err = await res.json();
            
            // Уведомление об ошибке
            window.dispatchEvent(new CustomEvent('new-broadcast', { 
                detail: { 
                    title: 'Ошибка',
                    message: err.detail || 'Не удалось отправить рассылку',
                    category: 'error'
                } 
            }));
        }
    } catch (error) {
        console.error('Broadcast Error:', error);
        window.dispatchEvent(new CustomEvent('new-broadcast', { 
            detail: { 
                message: 'Критическая ошибка сети 🌐',
                category: 'error'
            } 
        }));
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }}