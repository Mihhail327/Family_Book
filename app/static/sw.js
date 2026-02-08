const CACHE_NAME = 'familybook-v1.1'; // Меняй версию здесь при крупных обновлениях

const ASSETS = [
    '/',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png'
];

// 1. Установка: Кэшируем самое необходимое
self.addEventListener('install', (event) => {
    self.skipWaiting(); // Принудительно активируем новый SW
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('SW: Кэшируем базовые файлы');
            return cache.addAll(ASSETS);
        })
    );
});

// 2. Активация: Удаляем старый кэш предыдущих версий
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cache) => {
                    if (cache !== CACHE_NAME) {
                        console.log('SW: Удаляем старый кэш:', cache);
                        return caches.delete(cache);
                    }
                })
            );
        })
    );
    return self.clients.claim();
});

// 3. Обработка запросов: "Сначала сеть, при ошибке — кэш"
self.addEventListener('fetch', (event) => {
    // Если запрос идет к загруженным картинкам, НЕ КЭШИРУЕМ их пока что
    if (event.request.url.includes('/uploads/')) {
        return; // Пусть браузер берет их напрямую из сети
    }

    event.respondWith(
        fetch(event.request).catch(() => {
            return caches.match(event.request);
        })
    );
});