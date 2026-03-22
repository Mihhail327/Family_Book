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
    // Вибрируем только если это haptic-btn И у элемента НЕТ x-data (чтобы не мешать Alpine)
    if (target && !target.closest('[x-data]') && "vibrate" in navigator) {
        navigator.vibrate(15); 
    }
});

// ==========================================
// 3. УТИЛИТЫ И UI-ЭФФЕКТЫ
// ==========================================

// Превью изображений
window.handlePreview = function(event) {
    const area = document.getElementById("preview-area");
    if (!area) return;
    
    area.querySelectorAll('img').forEach(img => URL.revokeObjectURL(img.src));
    area.innerHTML = "";

    const files = Array.from(event.target.files);
    if (files.length === 0) {
        area.classList.add('hidden');
        return;
    }
    
    area.classList.remove('hidden');

    files.forEach((file) => {
        const url = URL.createObjectURL(file);
        const wrapper = document.createElement("div");
        wrapper.className = "relative group aspect-square animate-in zoom-in duration-300";
        
        wrapper.innerHTML = `
            <img src="${url}" class="w-full h-full object-cover rounded-xl border border-white/10 shadow-md">
            <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity rounded-xl flex items-center justify-center cursor-pointer">
                <span class="text-[10px] font-black text-white uppercase tracking-widest">Удалить</span>
            </div>
        `;

        wrapper.onclick = () => {
            wrapper.remove();
            if (area.children.length === 0) area.classList.add('hidden');
        };

        area.appendChild(wrapper);
    });
}

// Локальное время
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

// Инициализация при загрузке и после работы HTMX
document.addEventListener("DOMContentLoaded", window.convertToLocalTime);
document.addEventListener("htmx:afterSwap", window.convertToLocalTime);

// Эффект курсора (для десктопа)
document.addEventListener('mousemove', (e) => {
    const x = (e.clientX / window.innerWidth) * 100;
    const y = (e.clientY / window.innerHeight) * 100;
    document.documentElement.style.setProperty('--mouse-x', `${x}%`);
    document.documentElement.style.setProperty('--mouse-y', `${y}%`);
});

// Глобальная тема
window.toggleTheme = () => {
    const isDark = document.documentElement.classList.toggle('dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    if ('vibrate' in navigator) navigator.vibrate(10);
};

// Инициализация темы без вспышки
(function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
        document.documentElement.classList.add('dark');
    } else {
        document.documentElement.classList.remove('dark');
    }
})();

document.addEventListener('DOMContentLoaded', () => {
    const checkInput = setInterval(() => {
        const fileInput = document.getElementById('post-file-input');
        const previewArea = document.getElementById('preview-area');

        if (fileInput && previewArea) {
            clearInterval(checkInput);
            console.log("✅ Система превью Family_Book активирована!");

            fileInput.addEventListener('change', function(event) {
                const files = event.target.files;
                previewArea.innerHTML = '';
                
                if (files.length > 0) {
                    previewArea.style.display = 'grid';
                }

                Array.from(files).forEach(file => {
                    if (!file.type.startsWith('image/')) return;

                    const reader = new FileReader();
                    reader.onload = (e) => {
                        const div = document.createElement('div');
                        div.className = 'relative aspect-square rounded-xl overflow-hidden border border-white/10 shadow-xl bg-white/5 animate-in zoom-in duration-300';
                        div.innerHTML = `
                            <img src="${e.target.result}" class="w-full h-full object-cover">
                            <div class="absolute inset-0 bg-black/20 opacity-0 hover:opacity-100 transition-opacity flex items-center justify-center">
                                <span class="text-[10px] text-white font-bold uppercase tracking-widest">OK</span>
                            </div>
                        `;
                        previewArea.appendChild(div);
                    };
                    reader.readAsDataURL(file);
                });
            });
        }
    }, 500);
});

// Функция для отрисовки карточек превью
function createPreviewCard(src) {
    const div = document.createElement('div');
    div.className = 'relative aspect-square rounded-xl overflow-hidden border border-white/10 shadow-xl bg-white/5 animate-in zoom-in duration-300';
    div.innerHTML = `
        <img src="${src}" class="w-full h-full object-cover">
        <div class="absolute inset-0 bg-black/20 opacity-0 hover:opacity-100 transition-opacity flex items-center justify-center">
            <span class="text-[10px] text-white font-bold uppercase tracking-widest">OK</span>
        </div>
    `;
    return div;
}

// Главная логика инициализации
const initPhotoPreview = () => {
    const fileInput = document.getElementById('post-file-input');
    const previewArea = document.getElementById('preview-area');

    if (fileInput && previewArea && !fileInput.dataset.initialized) {
        fileInput.dataset.initialized = "true"; // Чтобы не вешать событие дважды
        
        fileInput.addEventListener('change', function(e) {
            const files = e.target.files;
            previewArea.innerHTML = '';
            
            if (files.length > 0) {
                previewArea.style.display = 'grid';
                previewArea.classList.remove('hidden');
            }

            Array.from(files).forEach(file => {
                if (!file.type.startsWith('image/')) return;
                const reader = new FileReader();
                reader.onload = (event) => {
                    const card = createPreviewCard(event.target.result);
                    previewArea.appendChild(card);
                };
                reader.readAsDataURL(file);
            });
            console.log("📸 Превью обновлено для " + files.length + " файлов");
        });
        
        console.log("✅ Система превью подключена к инпуту");
    }
};

// Следим за изменениями в DOM (когда Alpine открывает модалку)
const observer = new MutationObserver(() => {
    initPhotoPreview();
});

// Запускаем наблюдение
observer.observe(document.body, { childList: true, subtree: true });

// На всякий случай запускаем один раз при загрузке
document.addEventListener('DOMContentLoaded', initPhotoPreview);