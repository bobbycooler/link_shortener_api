# Link Shortener API

Современный сервис для сокращения ссылок с поддержкой авторизации, статистики переходов и автоматического удаления просроченных ссылок.

## Описание проекта
Сервис позволяет преобразовывать длинные URL в короткие идентификаторы. 
**Основные фишки:**
*   **Авторизация:** JWT-токены (регистрация/логин).
*   **Гибкость:** Создание случайных или кастомных (alias) ссылок.
*   **Статистика:** Отслеживание количества переходов и даты последнего клика.
*   **TTL (Time To Live):** Установка срока жизни ссылки.
*   **Производительность:** Кэширование редиректов в Redis.
*   **Автоматизация:** Фоновая очистка базы от неиспользуемых и просроченных ссылок по TTL.

## Технологии
*   Python 3.9, FastAPI, SQLAlchemy, PostgreSQL, Redis (кэширование и ускорение редиректов), FastAPI Users (JWT Strategy), Docker, Alembic.

## Структура БД
Проект использует две основные таблицы:
1.  **User**: Данные пользователей (email, hashed_password, status).
2.  **URL**: 
    *   `long_url`: Оригинальный адрес.
    *   `short_url`: Уникальный короткий код.
    *   `clicks_count`: Счетчик переходов.
    *   `created_at` / `last_watched_at`: Временные метки.
    *   `expires_at`: Дата автоматического удаления.
    *   `author_id`: Связь с пользователем (может быть NULL для ссылок, созданных анонимами).

## Инструкция по запуску
1.  **Клонируйте репозиторий:**
2.  **Настройте окружение:**
    Создайте файл `.env` в корне проекта и заполните его:
    ```ini
    SECRET=your_super_secret_key
    POSTGRES_USER=postgres
    POSTGRES_PASSWORD=pass
    POSTGRES_DB=shortener
    DATABASE_URL=postgresql+asyncpg://postgres:pass@db:5432/shortener
    REDIS_URL=redis://redis:6379
    ```
3.  **Запустите проект:**
    ```bash
    docker-compose up --build
    ```
    *API будет доступно по адресу: `http://localhost:8000`*
    *Документация Swagger: `http://localhost:8000/docs`*

## Примеры запросов
*Полная документация Swagger: `http://localhost:8000/docs`*
### 1.  Генерация короткой ссылки
**POST** `/links/shorten`
```json
{
  "long_url": "https://longurl.com",
  "custom_alias": "short",
  "expires_at": "2026-05-20T15:00:00"
}
```

### 2.  Получение статистики по ссылке
**GET** `/links/{short_code}/stats`
```json
{
  "id": 12,
  "short_url": "short",
  "long_url": "https://longurl.com",
  "created_at": "2026-03-09T12:00:00Z",
  "expires_at": "2026-05-20T15:00:00Z",
  "clicks_count": 154,
  "last_watched_at": "2026-03-09T14:30:15Z",
  "author_id": 1
}
```

### 3.  Получение всех коротких ссылок большой ссылки
**GET** `/links/search?original_url={short_code}`
```json
[
  { "short_url": "test1", "clicks_count": 50 },
  { "short_url": "test2", "clicks_count": 12 }
]
```

### 4.  Изменение alias ссылки
**PUT** `/links/{short_code}`
```json
{
  "new_short_code": "new-cool-alias"
}
```

### 5.  Получение user token
**POST** `/auth/jwt/login`
```json
{
    "username": "user@example.com",
    "password": "secret_password"
}
```