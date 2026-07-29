const CACHE_NAME = 'familybook-v4.0';

const ASSETS = [
    '/static/css/main.css',
    '/static/css/style.css',
    '/static/app.js',
    '/static/manifest.json',
    '/static/offline.html',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
    '/static/sounds/notification.mp3'
];

// 1. Установка: Кэшируем ключевые ресурсы
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

// 2. Активация: Очистка старых версий кэша
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

// 3. Обработка сетевых запросов (Network First для навигации + Cache Fallback)
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // ✅ Игнорируем API, Auth и WebSocket запросы
    if (
        url.pathname.startsWith('/api/') || 
        url.pathname.startsWith('/posts/') ||
        url.pathname.includes('/auth/') ||
        url.pathname.includes('/ws/')
    ) {
        return;
    }

    // ✅ Стратегия для навигации (HTML страницы): Network First -> Fallback на offline.html
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request).catch(() => {
                return caches.match('/static/offline.html');
            })
        );
        return;
    }

    // ✅ Стратегия для статики (CSS, JS, Иконки, Шрифты): Stale-While-Revalidate
    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            const fetchPromise = fetch(event.request).then((networkResponse) => {
                if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
                    const responseToCache = networkResponse.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseToCache);
                    });
                }
                return networkResponse;
            }).catch(() => null);

            return cachedResponse || fetchPromise;
        })
    );
});

// ==========================================
// БЛОК PUSH-УВЕДОМЛЕНИЙ (Расширенный формат)
// ==========================================

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
        body: data.body || data.message || "У вас новое семейное уведомление",
        icon: '/static/icons/icon-192.png',
        badge: '/static/icons/icon-192.png',
        vibrate: [200, 100, 200, 100, 200],
        sound: '/static/sounds/notification.mp3',
        tag: data.tag || 'familybook-push-' + Date.now(),
        renotify: true,
        data: {
            url: data.url || data.link || '/'
        },
        actions: [
            { action: 'open', title: 'Открыть ➔' }
        ]
    };

    event.waitUntil(
        self.registration.showNotification(data.title || "FamilyBook", options)
    );
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    const urlToOpen = event.notification.data ? event.notification.data.url : '/';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
            for (let i = 0; i < windowClients.length; i++) {
                const client = windowClients[i];
                if (client.url.includes(urlToOpen) && 'focus' in client) {
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(urlToOpen);
            }
        })
    );
});