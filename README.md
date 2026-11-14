# Музыкальная микросервисная платформа (Music Microservices Platform)

Комплексная событийно-ориентированная микросервисная платформа для стриминга музыки, разработанная в соответствии с требованиями практических работ №4–8 (РТУ МИРЭА). 

Архитектура построена на принципах **Domain-Driven Design (DDD)**, чистой слоистой архитектуры (**Clean Architecture**), асинхронном событийно-ориентированном взаимодействии (**Event-Driven Architecture**) через RabbitMQ и централизованной маршрутизации трафика через **API Gateway (Nginx)** с поддержкой CORS.

---

## 🏛 Архитектура системы

В платформе выделено 6 независимых ограниченных контекстов (Bounded Contexts), объединённых через шлюз API Gateway, общую сеть Docker и шину сообщений RabbitMQ:

```mermaid
flowchart TD
    Client(["Клиент / Frontend / Мобильное приложение"])

    subgraph Gateway ["Входной шлюз"]
        APIGW["API Gateway (Nginx Reverse Proxy)<br/>Порт: 8080 (Внешний) -> 80 (Внутренний)<br/>CORS, Префлайт OPTIONS, Маршрутизация"]
    end

    Client -->|HTTP / REST (JWT)| APIGW

    subgraph CoreServices ["Микросервисы платформы"]
        direction TB

        Users["Users Service (:8001)<br/>Аутентификация & JWT<br/><i>(Трисветов Р. В.)</i>"]
        Favorites["Favorites Service (:8002)<br/>Избранные треки и плейлисты<br/><i>(Трисветов Р. В.)</i>"]
        Catalog["Catalog Service (:8003)<br/>Каталог, модерация, события<br/><i>(Скворцов М. А.)</i>"]
        Playlists["Playlists Service (:8004)<br/>Управление плейлистами<br/><i>(Юсубов Р. Х.)</i>"]
        Subscription["Subscription Service (:8005)<br/>Жизненный цикл подписок<br/><i>(Юсубов Р. Х.)</i>"]
        Playback["Playback Service (:8006)<br/>Плеер, очередь, история<br/><i>(Скворцов М. А.)</i>"]
    end

    APIGW -->|/api/v1/auth/*| Users
    APIGW -->|/api/v1/favorites/*| Favorites
    APIGW -->|/api/v1/tracks, /api/v1/albums| Catalog
    APIGW -->|/api/v1/playlists/*| Playlists
    APIGW -->|/api/v1/subscriptions/*| Subscription
    APIGW -->|/api/v1/playback/*| Playback

    subgraph DataStorage ["Хранилища данных"]
        PG[("PostgreSQL 16<br/>users_db (:5433)")]
        SQLiteFav[("SQLite Volume<br/>favorites.sqlite3")]
        SQLiteCat[("SQLite Volume<br/>catalog.sqlite3")]
        SQLitePl[("SQLite Volume<br/>playlists.sqlite3")]
        SQLiteSub[("SQLite Volume<br/>subscription.sqlite3")]
        SQLitePb[("SQLite Volume<br/>playback.sqlite3")]
    end

    Users -->|SQLAlchemy| PG
    Favorites --> SQLiteFav
    Catalog --> SQLiteCat
    Playlists --> SQLitePl
    Subscription --> SQLiteSub
    Playback --> SQLitePb

    subgraph SyncHTTP ["Синхронные HTTP-контракты"]
        Favorites -.->|"GET /api/v1/tracks/{id}"| Catalog
        Favorites -.->|"GET /api/v1/playlists/{id}"| Playlists
        Playlists -.->|"GET /api/v1/tracks/{id}"| Catalog
        Playback -.->|"GET /api/v1/subscriptions/status"| Subscription
        Playback -.->|"GET /api/v1/tracks/{id}, /albums/{id}"| Catalog
    end

    subgraph MessageBroker ["Шина асинхронных сообщений"]
        RMQ{{"RabbitMQ 4.1<br/>Direct Exchange: music.events"}}
        QueueTrack[("playback.track.queue<br/>key: track.selected")]
        QueueAlbum[("playback.album.queue<br/>key: album.selected")]
    end

    Catalog -->|"Публикация TrackSelected / AlbumSelected"| RMQ
    RMQ --> QueueTrack
    RMQ --> QueueAlbum
    QueueTrack -->|"Потребление (basic_ack)"| Playback
    QueueAlbum -->|"Потребление (basic_ack)"| Playback
```

---

## 📦 Спецификация микросервисов

| Сервис | Порт | База данных | Ответственный | Назначение и функциональность |
|---|:---:|:---:|:---:|---|
| **API Gateway** | `8080` (host) $\rightarrow$ `80` (nginx) | — | — | Единая точка входа, обратный прокси, маршрутизация запросов к микросервисам, обработка preflight-запросов `OPTIONS`, настройка CORS-заголовков для web-клиентов. |
| **Users Service** | `8001` | PostgreSQL 16 | Трисветов Р. В. | Регистрация пользователей, хеширование паролей (Argon2), вход с генерацией Bearer JWT (HS256), отзыв токенов (logout) с сохранением отозванных токенов в БД. |
| **Favorites Service** | `8002` | SQLite (`favorites.sqlite3`) | Трисветов Р. В. | Управление пользовательским избранным (треки и плейлисты). Синхронная проверка существования треков в `catalog-service` и плейлистов в `playlists-service` перед добавлением. |
| **Catalog Service** | `8003` | SQLite (`catalog.sqlite3`) | Скворцов М. А. | Каталог треков и альбомов, фильтрация и пагинация, подача треков на модерацию (`pending`), одобрение (`approve`) и отклонение (`reject`), публикация событий выбора треков/альбомов в RabbitMQ. |
| **Playlists Service** | `8004` | SQLite (`playlists.sqlite3`) | Юсубов Р. Х. | Создание и редактирование плейлистов, добавление треков с синхронной валидацией через `catalog-service`, удаление треков, изменение порядка воспроизведения, смена обложки, закрепление (`pin`/`unpin`). |
| **Subscription Service** | `8005` | SQLite (`subscription.sqlite3`) | Юсубов Р. Х. | Управление подписками пользователей: оформление, продление (`renew`), досрочное завершение (`complete`), отмена (`cancel`). Предоставление сервисного эндпоинта проверки статуса подписки для `playback-service`. |
| **Playback Service** | `8006` | SQLite (`playback.sqlite3`) | Скворцов М. А. | Движок воспроизведения: обработка асинхронных событий RabbitMQ, проверка статуса подписки и метаданных треков через HTTP, управление плеером (`pause`, `resume`, `stop`, `seek`, `next`, `previous`), управление очередью воспроизведения. |

---

## 📑 Полная спецификация REST API

Все микросервисы предоставляют стандартизированный REST API с кодами ответов `200`, `201`, `202`, `204`, `400`, `401`, `403`, `404`, `409`, `502`, `503`.

### 1. Users Service (Аутентификация и пользователи)
| Метод | Путь | Авторизация | Описание | Успешный статус |
|---|---|:---:|---|:---:|
| `POST` | `/api/v1/auth/register` | Нет | Регистрация нового пользователя (`username`, `email`, `password`) | `201 Created` |
| `POST` | `/api/v1/auth/login` | Нет | Аутентификация пользователя, получение `access_token` (JWT) | `200 OK` |
| `POST` | `/api/v1/auth/logout` | Bearer JWT | Выход из системы и добавление токена в черный список | `200 OK` |

### 2. Favorites Service (Избранное)
| Метод | Путь | Авторизация | Описание | Успешный статус |
|---|---|:---:|---|:---:|
| `PUT` | `/api/v1/favorites/tracks/{track_id}` | Bearer JWT | Добавление трека в избранное (синхронная проверка в Catalog) | `204 No Content` |
| `DELETE` | `/api/v1/favorites/tracks/{track_id}` | Bearer JWT | Удаление трека из избранного | `204 No Content` |
| `PUT` | `/api/v1/favorites/playlists/{playlist_id}` | Bearer JWT | Добавление плейлиста в избранное (проверка в Playlists) | `204 No Content` |
| `DELETE` | `/api/v1/favorites/playlists/{playlist_id}` | Bearer JWT | Удаление плейлиста из избранного | `204 No Content` |

### 3. Catalog Service (Каталог и модерация)
| Метод | Путь | Авторизация | Описание | Успешный статус |
|---|---|:---:|---|:---:|
| `GET` | `/api/v1/tracks` | Нет | Поиск треков с фильтрами (`query`, `artistId`, `albumId`, `offset`, `count`) | `200 OK` |
| `POST` | `/api/v1/tracks` | Bearer JWT | Загрузка трека на модерацию (статус `pending`) | `201 Created` |
| `GET` | `/api/v1/tracks/{track_id}` | Нет | Получение метаданных трека (используется другими сервисами) | `200 OK` |
| `PATCH` | `/api/v1/tracks/{track_id}` | Bearer JWT | Обновление метаданных трека | `200 OK` |
| `POST` | `/api/v1/tracks/{track_id}:approve` | Bearer JWT | Одобрение трека модератором (перевод в `approved`) | `200 OK` |
| `POST` | `/api/v1/tracks/{track_id}:reject` | Bearer JWT | Отклонение трека модератором с указанием причины | `200 OK` |
| `GET` | `/api/v1/albums` | Нет | Поиск опубликованных музыкальных альбомов | `200 OK` |
| `GET` | `/api/v1/albums/{album_id}` | Нет | Получение альбома и упорядоченного списка `trackIds` | `200 OK` |
| `POST` | `/api/v1/tracks/{track_id}:select` | Bearer JWT | Выбор трека пользователем (публикация `TrackSelected` в RabbitMQ) | `202 Accepted` |
| `POST` | `/api/v1/albums/{album_id}:select` | Bearer JWT | Выбор альбома пользователем (публикация `AlbumSelected` в RabbitMQ) | `202 Accepted` |

### 4. Playlists Service (Управление плейлистами)
| Метод | Путь | Авторизация | Описание | Успешный статус |
|---|---|:---:|---|:---:|
| `GET` | `/api/v1/playlists` | Нет | Получение списка плейлистов с пагинацией | `200 OK` |
| `POST` | `/api/v1/playlists` | Bearer JWT | Создание нового плейлиста | `201 Created` |
| `GET` | `/api/v1/playlists/{playlist_id}` | Нет | Получение плейлиста (используется Favorites Service) | `200 OK` |
| `PATCH` | `/api/v1/playlists/{playlist_id}` | Bearer JWT | Изменение названия и описания плейлиста | `200 OK` |
| `DELETE` | `/api/v1/playlists/{playlist_id}` | Bearer JWT | Удаление плейлиста | `204 No Content` |
| `POST` | `/api/v1/playlists/{playlist_id}/tracks` | Bearer JWT | Добавление трека с синхронной валидацией в Catalog | `201 Created` |
| `DELETE` | `/api/v1/playlists/{playlist_id}/tracks/{track_id}` | Bearer JWT | Удаление трека из плейлиста | `204 No Content` |
| `PATCH` | `/api/v1/playlists/{playlist_id}/tracks/order` | Bearer JWT | Изменение порядка композиций в плейлисте | `200 OK` |
| `PUT` | `/api/v1/playlists/{playlist_id}/cover` | Bearer JWT | Обновление URL обложки плейлиста | `200 OK` |
| `PUT` | `/api/v1/playlists/{playlist_id}/pin` | Bearer JWT | Закрепление плейлиста в профиле пользователя | `200 OK` |
| `DELETE` | `/api/v1/playlists/{playlist_id}/pin` | Bearer JWT | Снятие закрепления с плейлиста | `204 No Content` |

### 5. Subscription Service (Управление подписками)
| Метод | Путь | Авторизация | Описание | Успешный статус |
|---|---|:---:|---|:---:|
| `GET` | `/api/v1/subscriptions/status` | Bearer JWT | Проверка статуса подписки по `?userId={uuid}` (для Playback) | `200 OK` |
| `POST` | `/api/v1/subscriptions` | Bearer JWT | Оформление новой подписки пользователя | `201 Created` |
| `GET` | `/api/v1/subscriptions/my` | Bearer JWT | Просмотр текущей подписки авторизованного пользователя | `200 OK` |
| `POST` | `/api/v1/subscriptions/cancel` | Bearer JWT | Отмена действующей подписки текущего пользователя | `200 OK` |
| `POST` | `/api/v1/subscriptions/{subscription_id}/renew` | Bearer JWT | Продление подписки по её ID | `200 OK` |
| `POST` | `/api/v1/subscriptions/{subscription_id}/complete` | Bearer JWT | Завершение подписки по её ID | `200 OK` |
| `POST` | `/api/v1/subscriptions/{subscription_id}/cancel` | Bearer JWT | Отмена подписки по её ID | `200 OK` |

### 6. Playback Service (Воспроизведение и управление плеером)
| Метод | Путь | Авторизация | Описание | Успешный статус |
|---|---|:---:|---|:---:|
| `GET` | `/api/v1/playback/state` | Bearer JWT | Получение текущего состояния плеера пользователя | `200 OK` |
| `POST` | `/api/v1/playback:pause` | Bearer JWT | Приостановка воспроизведения | `200 OK` |
| `POST` | `/api/v1/playback:resume` | Bearer JWT | Возобновление воспроизведения | `200 OK` |
| `POST` | `/api/v1/playback:stop` | Bearer JWT | Остановка воспроизведения и сброс позиции | `204 No Content` |
| `POST` | `/api/v1/playback:seek` | Bearer JWT | Перемотка на указанную позицию в секундах | `200 OK` |
| `POST` | `/api/v1/playback:next` | Bearer JWT | Переход к следующему треку (из очереди или альбома) | `200 OK` |
| `POST` | `/api/v1/playback:previous` | Bearer JWT | Возврат к предыдущему воспроизведенному треку | `200 OK` |
| `GET` | `/api/v1/playback/queue` | Bearer JWT | Получение текущей очереди треков пользователя | `200 OK` |
| `POST` | `/api/v1/playback/queue` | Bearer JWT | Добавление композиции в очередь | `201 Created` |
| `DELETE` | `/api/v1/playback/queue/{queue_item_id}` | Bearer JWT | Удаление композиции из очереди | `204 No Content` |

---

## 🔄 Межсервисные контракты и интеграции

### 1. Синхронные HTTP-взаимодействия
- **Playback $\rightarrow$ Subscription**: Проверка активности подписки пользователя перед стартом воспроизведения трека/альбома (`GET /api/v1/subscriptions/status?userId={userId}`). Если подписка не активна, воспроизведение блокируется (`403 Forbidden`). Если сервис подписок недоступен — возвращается `502 Bad Gateway`.
- **Playback $\rightarrow$ Catalog**: Запрос сведений о треке (`GET /api/v1/tracks/{trackId}`) для получения длительности и статуса модерации (`approved`), а также состава альбома (`GET /api/v1/albums/{albumId}`).
- **Playlists $\rightarrow$ Catalog**: Синхронная проверка существования трека в каталоге (`GET /api/v1/tracks/{trackId}`) перед его добавлением в плейлист. Если трек отсутствует — клиенту возвращается `404 Not Found` с информативным сообщением.
- **Favorites $\rightarrow$ Catalog & Playlists**: Проверка существования трека или плейлиста перед добавлением сущности в избранное.

### 2. Асинхронная шина событий (RabbitMQ)
- **Топология брокера**:
  - Exchange: `music.events` (`direct`, `durable=True`).
  - Очередь треков: `playback.track.queue` (routing key: `track.selected`, `durable=True`).
  - Очередь альбомов: `playback.album.queue` (routing key: `album.selected`, `durable=True`).
- **Свойства надежности**:
  - Сообщения публикуются с `delivery_mode=2` (Persistent).
  - Ручное подтверждение обработки (`basic_ack`) после успешной синхронной проверки подписки и записи состояния в базу данных.
  - Контроль идемпотентности: в `playback-service` регистрируются идентификаторы обработанных событий (`processed_events`), исключая повторные запуски при ределивери.

---

## 🚀 Быстрый старт с Docker Compose

### 1. Предварительные требования
- Установленный **Docker** (24+) и **Docker Compose** (v2+).
- Свободные порты на хосте: `8080` (API Gateway), `8001–8006` (микросервисы), `5433` (Postgres), `15672` (RabbitMQ Management).

### 2. Настройка переменных окружения
Создайте файл `.env` на основе примера:
```bash
cp .env.example .env
```

Содержимое `.env`:
```dotenv
# Общий секрет для валидации JWT токенов между микросервисами
JWT_SECRET_KEY=your-secure-shared-jwt-secret-key-32-chars-minimum

# Внутренние URL микросервисов для межсервисного HTTP-взаимодействия
SUBSCRIPTION_URL=http://subscription-service:8005
CATALOG_URL=http://catalog-service:8003
PLAYLISTS_URL=http://playlists-service:8004
```

### 3. Сборка и запуск контейнеров
Запустите все сервисы в фоновом режиме:
```bash
docker compose up --build -d
```

Проверьте статус запущенных контейнеров:
```bash
docker compose ps
```

Должны успешно работать 9 контейнеров:
- `music-api-gateway` (Nginx, порт `8080`)
- `music-postgres` (PostgreSQL 16, порт `5433`)
- `music-microservices-rabbitmq-1` (RabbitMQ 4.1, порт `15672`)
- `music-microservices-users-service-1` (порт `8001`)
- `music-microservices-favorites-service-1` (порт `8002`)
- `music-microservices-catalog-service-1` (порт `8003`)
- `music-microservices-playlists-service-1` (порт `8004`)
- `music-microservices-subscription-service-1` (порт `8005`)
- `music-microservices-playback-service-1` (порт `8006`)

Просмотр логов в реальном времени:
```bash
docker compose logs -f
```

Остановка всех сервисов с сохранением данных в volumes:
```bash
docker compose down
```

---

## 🌐 Интерактивная документация (Swagger UI)

Каждый микросервис автоматически генерирует документацию OpenAPI / Swagger:

- **Users Service**: [http://localhost:8001/docs](http://localhost:8001/docs)
- **Favorites Service**: [http://localhost:8002/docs](http://localhost:8002/docs)
- **Catalog Service**: [http://localhost:8003/docs](http://localhost:8003/docs)
- **Playlists Service**: [http://localhost:8004/docs](http://localhost:8004/docs)
- **Subscription Service**: [http://localhost:8005/docs](http://localhost:8005/docs)
- **Playback Service**: [http://localhost:8006/docs](http://localhost:8006/docs)
- **RabbitMQ Web Management**: [http://localhost:15672](http://localhost:15672) (логин: `guest`, пароль: `guest`)
- **API Gateway Healthcheck**: [http://localhost:8080/health](http://localhost:8080/health)

---

## 🧪 Запуск автоматических тестов

В проекте реализован полный набор модульных и интеграционных тестов с использованием фреймворка **pytest** и **FastAPI TestClient**. 

Тесты проверяют:
- Полное соблюдение межсервисных контрактов (Catalog, Playlists, Subscription, Favorites, Playback).
- Корректность валидации и генерации JWT токенов.
- Сценарии ошибок (`400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`, `502 Bad Gateway`, `503 Service Unavailable`).
- Сохранение и персистентность данных в SQLite.
- Идемпотентность и обработку асинхронных событий RabbitMQ.

### Запуск тестов локально:
```bash
# 1. Активация виртуального окружения (при наличии)
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

# 2. Установка зависимостей
pip install -r requirements-dev.txt

# 3. Запуск тестов
pytest -v
```

Все 28 тестов выполняются успешно:
```text
tests/test_catalog.py ......................... PASSED [ 25%]
tests/test_favorites_integration.py .......... PASSED [ 32%]
tests/test_playback.py ........................ PASSED [ 60%]
tests/test_playlists.py ....................... PASSED [ 85%]
tests/test_subscription.py .................... PASSED [100%]

======================== 28 passed in 5.5s ========================
```

---

## 💻 Примеры использования API через Gateway (`:8080`)

Все запросы к системе рекомендуется отправлять через центральный шлюз `http://localhost:8080`.

### 1. Регистрация и авторизация пользователя
```bash
# Регистрация
curl -X POST http://localhost:8080/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "johndoe", "email": "john@example.com", "password": "SecurePassword123!"}'

# Вход и получение токена
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "john@example.com", "password": "SecurePassword123!"}'
# В ответе вернется: {"accessToken": "<TOKEN>", "tokenType": "bearer", "expiresIn": 1800}
```

Сохраните полученный токен в переменную:
```bash
TOKEN="<ваш_полученный_jwt_токен>"
```

### 2. Поиск треков в каталоге
```bash
curl -X GET "http://localhost:8080/api/v1/tracks?query=Example"
```

### 3. Добавление трека в избранное
```bash
curl -X PUT "http://localhost:8080/api/v1/favorites/tracks/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Создание плейлиста и добавление трека
```bash
# Создание плейлиста
curl -X POST http://localhost:8080/api/v1/playlists \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Мой Рок-плейлист", "description": "Лучшие треки", "coverUrl": "https://example.com/cover.jpg"}'

# Добавление трека в плейлист
curl -X POST http://localhost:8080/api/v1/playlists/<PLAYLIST_ID>/tracks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"trackId": "550e8400-e29b-41d4-a716-446655440000"}'
```

### 5. Выбор трека и воспроизведение (Event-Driven)
```bash
# Инициировать событие воспроизведения трека через брокер сообщений
curl -X POST http://localhost:8080/api/v1/tracks/550e8400-e29b-41d4-a716-446655440000:select \
  -H "Authorization: Bearer $TOKEN"

# Проверить текущее состояние плеера
curl -X GET http://localhost:8080/api/v1/playback/state \
  -H "Authorization: Bearer $TOKEN"

# Поставить на паузу
curl -X POST http://localhost:8080/api/v1/playback:pause \
  -H "Authorization: Bearer $TOKEN"
```

---

## 📁 Структура проекта

```text
c:\music-microservices\
├── gateway/
│   └── nginx.conf                 # Конфигурация Nginx API Gateway с CORS и reverse proxy
├── users-service/                 # Сервис пользователей и токенов (PostgreSQL 16)
│   ├── models/                    # Pydantic & SQLAlchemy модели пользователей
│   ├── services/                  # Хеширование паролей и выпуск JWT
│   ├── database.py                # Подключение к PostgreSQL
│   ├── Dockerfile
│   └── main.py
├── favorites-service/             # Сервис избранного (SQLite)
│   ├── clients/                   # HTTP-клиенты для Catalog и Playlists
│   ├── models/                    # Модели избранного
│   ├── repositories/              # SQLite репозиторий с персистентным хранением
│   ├── services/                  # Бизнес-логика добавления/удаления
│   ├── Dockerfile
│   └── main.py
├── catalog-service/               # Сервис каталога и модерации (SQLite + RabbitMQ)
│   └── catalog_service/
│       ├── database.py            # SQLite схема и seed-данные треков/альбомов
│       ├── messaging.py           # Публикация событий в RabbitMQ
│       ├── models.py
│       ├── repository.py
│       └── service.py
├── playlists-service/             # Сервис плейлистов (SQLite + HTTP-клиент)
│   └── playlists_service/
│       ├── database.py            # SQLite схема плейлистов
│       ├── integrations.py        # Синхронный CatalogGateway (HTTPX)
│       ├── models.py
│       ├── repository.py
│       └── service.py
├── subscription-service/          # Сервис подписок (SQLite)
│   └── subscription_service/
│       ├── database.py            # SQLite схема подписок
│       ├── models.py
│       ├── repository.py
│       └── service.py
├── playback-service/              # Сервис воспроизведения (SQLite + HTTP + RabbitMQ)
│   └── playback_service/
│       ├── database.py            # SQLite схема плеера и очереди
│       ├── integrations.py        # Клиенты каталога и подписок
│       ├── messaging.py           # Потребитель очередей RabbitMQ
│       ├── models.py
│       ├── repository.py
│       └── service.py
├── tests/                         # Модульные и интеграционные тесты
│   ├── conftest.py                # Общие фикстуры, seed UUID и генераторы JWT
│   ├── test_catalog.py
│   ├── test_favorites_integration.py
│   ├── test_playback.py
│   ├── test_playlists.py
│   └── test_subscription.py
├── docs/
│   └── integration-contract.md    # Спецификация межсервисных контрактов
├── scripts/
│   └── demo_token.py              # Скрипт генерации тестовых JWT для отладки
├── docker-compose.yml             # Оркестрация всех 9 сервисов и хранилищ
├── .dockerignore
├── .gitignore
├── .env.example
├── requirements-dev.txt
└── README.md
```
