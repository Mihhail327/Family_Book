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
// Любой элемент с классом haptic-btn будет приятно вибрировать при клике
document.addEventListener('click', (e) => {
    if (e.target.closest('.haptic-btn') && "vibrate" in navigator) {
        navigator.vibrate(15); // Очень легкая, премиальная вибрация
    }
});

// ==========================================
// 3. ЛАЙКИ (AJAX + Confetti + Ripple)
// ==========================================
async function toggleLike(btn, postId) {
    if (btn.dataset.loading === "true") return;
    btn.dataset.loading = "true";

    const iconSpan = btn.querySelector(".heart-icon");
    const countSpan = btn.querySelector(".count");

    if (!iconSpan || !countSpan) return;

    const isLiked = iconSpan.textContent.includes("❤️");

    // Эффект «Волны» (Ripple Effect)
    const ripple = document.createElement("span");
    ripple.className = "absolute inset-0 rounded-full bg-rose-500/30 animate-ping pointer-events-none";
    btn.classList.add("relative"); 
    btn.appendChild(ripple);
    setTimeout(() => ripple.remove(), 600);

    // Оптимистичное обновление UI (чтобы юзер не ждал ответа сервера)
    iconSpan.textContent = isLiked ? "🤍" : "❤️";
    
    // Проверяем настройки: стреляем конфетти, только если юзер не выключил это
    const heartsEnabled = localStorage.getItem('hearts_enabled') !== 'false';
    if (!isLiked && heartsEnabled) {
        const rect = btn.getBoundingClientRect();
        triggerConfetti(
            (rect.left + rect.width / 2) / window.innerWidth,
            (rect.top + rect.height / 2) / window.innerHeight
        );
    }

    try {
        const res = await fetch(`/posts/${postId}/like`, { method: "POST" });
        if (res.status === 401) {
            if (!window.location.pathname.includes('/login')) {
                window.location.href = "/login";
            }
            return;
    }
        
        // Читаем точный ответ от сервера и обновляем счетчик 100% достоверно
        const data = await res.json();
        countSpan.textContent = data.likes_count;
        
    } catch (e) {
        console.error("Like error:", e);
        // Откат (Rollback) при ошибке сети
        iconSpan.textContent = isLiked ? "❤️" : "🤍";
    } finally {
        setTimeout(() => btn.dataset.loading = "false", 300);
    }
}

function triggerConfetti(x, y) {
    if (typeof confetti !== "function") return;
    confetti({
        particleCount: 40,
        spread: 80,
        origin: { x, y },
        shapes: [confetti.shapeFromText({ text: "❤️", scalar: 2 })],
        colors: ["#ef4444", "#ec4899", "#f472b6"],
        zIndex: 10000,
    });
}

// ==========================================
// 4. ДОЛГОЕ НАЖАТИЕ (LONG PRESS)
// ==========================================
let longPressTimer;

function startLongPress(postId) {
    longPressTimer = setTimeout(() => {
        if ("vibrate" in navigator) navigator.vibrate([30, 50, 30]); 
        openReactionsMenu(postId); 
    }, 500); 
}

function cancelLongPress() {
    clearTimeout(longPressTimer);
}

function openReactionsMenu(postId) {
    console.log("Открываем меню реакций для поста:", postId);
    // TODO: Интеграция с HTMX для вызова модалки реакций
}

// ==========================================
// 5. УТИЛИТЫ И UI-ЭФФЕКТЫ
// ==========================================
function handlePreview(event) {
    const area = document.getElementById("preview-area");
    if (!area) return;
    area.innerHTML = "";

    Array.from(event.target.files).forEach((file) => {
        const url = URL.createObjectURL(file);
        const img = document.createElement("img");
        img.src = url;
        img.className = "w-24 h-24 object-cover rounded-lg border border-white/10 shadow-sm";
        area.appendChild(img);
    });
}

function convertToLocalTime() {
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

// Инициализация времени при загрузке
document.addEventListener("htmx:afterSwap", (e) => {
    convertToLocalTime();
});

// Отслеживание курсора для эффекта золотого фона (Glassmorphism)
document.addEventListener('mousemove', (e) => {
    const x = (e.clientX / window.innerWidth) * 100;
    const y = (e.clientY / window.innerHeight) * 100;
    document.documentElement.style.setProperty('--mouse-x', `${x}%`);
    document.documentElement.style.setProperty('--mouse-y', `${y}%`);
});

// --- Глобальная система смены темы (Dark/Light) ---
window.toggleTheme = () => {
    const isDark = document.documentElement.classList.toggle('dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    
    // Легкая вибрация при переключении (Haptic feedback)
    if ('vibrate' in navigator) navigator.vibrate(10);
    
    console.log(`Тема изменена на: ${isDark ? 'Dark' : 'Light'}`);
};

// Инициализация темы при загрузке страницы (чтобы не было белой вспышки)
(function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
        document.documentElement.classList.add('dark');
    } else {
        document.documentElement.classList.remove('dark');
    }
})();