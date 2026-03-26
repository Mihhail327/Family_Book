# 🌳 FamilyBook v3.0 (Sentinel Edition)

Семейная социальная сеть с усиленной защитой, системой уведомлений в Telegram и поддержкой PWA.

## 🚀 Основные функции
* **Family Feed:** Общая лента историй с поддержкой фото (до 10 шт) и реакций.
* **Sentinel Security:** Защита от спам-ботов (Honeypot), XSS и SQL-инъекций.
* **Telegram Bot:** Мгновенные уведомления администратору о подозрительной активности и системных событиях.
* **PWA Ready:** Установка на смартфон, работа в офлайн-режиме и тактильная отдача (Vibration API).
* **Admin Panel:** Полный контроль над пользователями и контентом.

## 🛠 Технологический стек
* **Backend:** FastAPI, SQLModel (SQLAlchemy + Pydantic).
* **Database:** PostgreSQL (Production) / SQLite (Dev).
* **Frontend:** Jinja2 Templates, HTMX (для динамического обновления без перезагрузки).
* **Security:** JWT Auth, Passlib (bcrypt), Sentinel Middleware.
* **Deployment:** Render.com + Persistent Disk.

## ⚙️ Настройка окружения (Environment Variables)

Для работы приложения необходимо создать файл `.env` (или прописать переменные в панели Render):

| Ключ | Описание |
| :--- | :--- |
| `DATABASE_URL` | Ссылка на БД (Postgres или SQLite) |
| `SECRET_KEY` | Секретный код для генерации JWT-токенов |
| `BOT_TOKEN` | Токен от @BotFather |
| `ADMIN_CHAT_ID` | Ваш ID в Telegram для получения алертов |
| `APP_MODE` | `dev` или `prod` |
| `ENV` | `development` или `production` |

## 📦 Быстрый старт (Local Dev)

1. **Клонируйте репозиторий:**
   ```bash
   git clone [https://github.com/your-repo/family-book.git](https://github.com/your-repo/family-book.git)
   cd family-book
Установите зависимости (Poetry):

Bash
poetry install
Запустите тесты (обязательно!):

Bash
poetry run pytest -v
Запустите сервер:

Bash
poetry run uvicorn app.main:app --reload
🛡️ Безопасность (Sentinel)
Система автоматически блокирует запросы, если:

Заполнено скрытое поле confirm_email_address (Honeypot).

Обнаружена попытка доступа к админ-панели без прав.

Превышены лимиты загрузки файлов.
Все инциденты мгновенно отправляются в Telegram администратору.