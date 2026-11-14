# Контракт интеграции с другими сервисами

## Catalog → Favorites / Playlists / Playback

`GET /api/v1/tracks/{track_id}` без авторизации, идентификатор — UUID.

Успех — `200 OK`:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Example Track",
  "artist": "Example Artist",
  "albumId": "770e8400-e29b-41d4-a716-446655440002",
  "durationSeconds": 215,
  "status": "approved"
}
```

Отсутствующий или неопубликованный трек — `404`, некорректный UUID — `400`.

Для альбомов: `GET /api/v1/albums/{album_id}` отдаёт поля `id`, `title`, `artist`, `trackIds` (массив UUID в порядке воспроизведения).

**Ограничение проверки:** исходный файл `mock-catalog/main.py` в переданных материалах отсутствует. Подтверждается совместимость по ключевым полям `id/title/artist`, описанным в практической №6, но не побайтовое совпадение с неизвестным mock-файлом.

## Playback → Subscription — согласовано с Юсубовым

Запрос от Playback Service:

```http
GET /api/v1/subscriptions/status?userId=770e8400-e29b-41d4-a716-446655440000 HTTP/1.1
Host: subscription-service:8005
Authorization: Bearer <service-JWT>
```

Ответ `200 OK` (активная подписка):

```json
{
  "userId": "770e8400-e29b-41d4-a716-446655440000",
  "isActive": true,
  "expiresAt": "2027-12-31T23:59:59Z"
}
```

Ответ `200 OK` (подписка отсутствует или неактивна):

```json
{
  "userId": "770e8400-e29b-41d4-a716-446655440000",
  "isActive": false,
  "expiresAt": null
}
```

Параметры согласования:
1. Имя сервиса: `subscription-service`, порт `8005`, URL в docker-compose: `http://subscription-service:8005`.
2. Контракт: `userId` (UUID), `isActive` (boolean), `expiresAt` (ISO-8601 UTC string или null).
3. Авторизация: `HS256`, общий `JWT_SECRET_KEY`, поддерживает как сервисный токен (`sub=playback-service`, `role=service`), так и пользовательские токены.
4. Поведение при отсутствии подписки: возвращается `200 OK` с `isActive: false`, `expiresAt: null`. При передаче невалидного UUID возвращается `400 Bad Request`.
5. Тестовый пользователь с активной seed-подпиской: `770e8400-e29b-41d4-a716-446655440000`.

## Favorites → Playlists — согласовано с Юсубовым

Запрос от Favorites Service:

```http
GET /api/v1/playlists/660e8400-e29b-41d4-a716-446655440000 HTTP/1.1
Host: playlists-service:8004
```

Успех — `200 OK`:

```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "name": "My Playlist",
  "ownerId": "770e8400-e29b-41d4-a716-446655440000",
  "description": "Default test playlist",
  "trackIds": [
    "550e8400-e29b-41d4-a716-446655440000"
  ],
  "createdAt": "2026-11-12T07:00:00Z"
}
```

Отсутствующий плейлист — `404 Not Found`, некорректный UUID — `400 Bad Request`.
Тестовый seed-плейлист: `660e8400-e29b-41d4-a716-446655440000`, владелец `770e8400-e29b-41d4-a716-446655440000`.

## Синхронное взаимодействие Playlists → Catalog

При добавлении трека в плейлист (`POST /api/v1/playlists/{playlist_id}/tracks`):
Playlists Service отправляет синхронный GET-запрос:
```http
GET /api/v1/tracks/{track_id} HTTP/1.1
Host: catalog-service:8003
```
- Если трек найден (200 OK), он добавляется в плейлист.
- Если трек отсутствует в каталоге (404 Not Found), Playlists Service возвращает клиенту `404 Not Found` с сообщением `"Трек отсутствует в каталоге"`.
- Если каталог недоступен или возвращает 5xx, Playlists Service возвращает `503 Service Unavailable` с сообщением `"Каталог недоступен"`.

## События RabbitMQ (из практической №5)

Обменник `music.events`, тип `direct`, очереди `playback.track.queue` и `playback.album.queue`, ключи `track.selected` и `album.selected`. Сообщения сохраняются (`delivery_mode=2`), очереди устойчивы (`durable=True`), потребитель подтверждает обработку через `basic_ack`.

Пример `TrackSelected`:

```json
{
  "eventId": "aa0e8400-e29b-41d4-a716-446655440006",
  "event": "TrackSelected",
  "userId": "770e8400-e29b-41d4-a716-446655440000",
  "trackId": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-11-12T07:00:00Z"
}
```

Для `AlbumSelected` заменяются `event` и `trackId` на `AlbumSelected` и `albumId`.

Статус `202 Accepted` означает, что **событие поставлено в очередь**, а не что плеер начал воспроизведение. Сервис Playback проверяет трек/альбом и подписку уже после приёма сообщения.

## JWT пользователей

Catalog `:select` и все 5 API-методов Playback требуют `Authorization: Bearer ...`; JWT должен быть подписан `HS256` общим ключом, содержать `exp` и UUID в `sub` (либо в `userId`). Эти допущения надо сверить с фактической реализацией Users Service — её исходники не были приложены.
