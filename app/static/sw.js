const CACHE_NAME = 'familybook-v3.0'; // Обновили версию для сброса циклов

const ASSETS = [
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
    '/static/sounds/notification.mp3'
];

// 1. Установка: Кэшируем по одному, чтобы отсутствие файла не ломало установку
self.addEventListener('install', (event) => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return Promise.allSettled(
                ASSETS.map(url => cache.add(url))
            );
        })
    );
});

// 2. Активация
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.map((key) => {
                    if (key !== CACHE_NAME) return caches.delete(key);
                })
            );
        })
    );
    return self.clients.claim();
});

// 3. Обработка запросов (БЕЗОПАСНАЯ)
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // ✅ ПРАВИЛО 1: НЕ кэшируем навигацию, API и загрузки
    // Это предотвращает бесконечный редирект между / и /login
    if (
        event.request.mode === 'navigate' || 
        url.pathname.startsWith('/api/') || 
        url.pathname.startsWith('/posts/') ||
        url.pathname.includes('/auth/') ||
        url.pathname.includes('/login')
    ) {
        return; 
    }

    // ✅ ПРАВИЛО 2: Для статики (иконки, звуки) - сначала кэш
    event.respondWith(
        caches.match(event.request).then((response) => {
            return response || fetch(event.request);
        })
    );
});

// ==========================================
// БЛОК PUSH-УВЕДОМЛЕНИЙ (МАСТЕР-ТЗ Раздел 5)
// ==========================================

// 4. Слушаем входящие Push-уведомления от сервера
self.addEventListener('push', (event) => {
    let data = { 
        title: "FamilyBook", 
        body: "Новая история в семье!", 
        url: "/" 
    };

    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            data.body = event.data.text();
        }
    }

    const options = {
        body: data.body,
        icon: '/static/icons/icon-192.png',
        badge: '/static/icons/badge.png', // Сделай прозрачную PNG 96x96 белого цвета
        vibrate: [200, 100, 200, 100, 200], // Haptics: тройная вибрация
        sound: '/static/sounds/notification.mp3', // Тот самый "Дзынь"
        data: {
            url: data.url || '/'
        }
    };

    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

// 5. Что делать, если пользователь тапнул по уведомлению
self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    const urlToOpen = event.notification.data.url;

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
            // Если вкладка FamilyBook уже открыта, просто фокусируемся на ней
            for (let i = 0; i < windowClients.length; i++) {
                const client = windowClients[i];
                if (client.url.includes(urlToOpen) && 'focus' in client) {
                    return client.focus();
                }
            }
            // Иначе открываем новую вкладку
            if (clients.openWindow) {
                return clients.openWindow(urlToOpen);
            }
        })
    );
});