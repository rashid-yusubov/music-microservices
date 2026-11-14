import json
import logging
import threading
from uuid import UUID

from .config import Settings
from .errors import ApiError
from .service import PlaybackService


logger = logging.getLogger(__name__)


class RabbitConsumer:
    def __init__(self, settings: Settings, service: PlaybackService):
        self.settings = settings
        self.service = service
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True, name="playback-rabbit-consumer")

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(timeout=5)

    def _handle_message(self, channel, method, properties, body: bytes) -> None:
        try:
            event = json.loads(body)
            event_type = event["event"]
            user_id = UUID(event["userId"])
            event_id = UUID(event["eventId"]) if event.get("eventId") else None
            if event_type == "TrackSelected":
                self.service.start_track(user_id, UUID(event["trackId"]), event_id=event_id)
            elif event_type == "AlbumSelected":
                self.service.start_album(user_id, UUID(event["albumId"]), event_id=event_id)
            else:
                raise ValueError("Неизвестный тип события")
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            logger.exception("Некорректное событие, сообщение удалено из очереди")
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except ApiError as exc:
            if exc.status_code in (502, 503):
                logger.warning("Временная ошибка зависимого сервиса: %s; повторная доставка", exc)
                self.stop_event.wait(2)
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            else:
                logger.warning("Событие отклонено: %s (%d)", exc, exc.status_code)
                channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception:
            logger.exception("Ошибка обработки события; сообщение будет доставлено повторно")
            self.stop_event.wait(2)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        else:
            channel.basic_ack(delivery_tag=method.delivery_tag)

    def _run(self) -> None:
        try:
            import pika
        except ImportError:
            logger.exception("Библиотека pika не установлена, RabbitMQ отключён")
            return
        while not self.stop_event.is_set():
            connection = None
            try:
                params = pika.URLParameters(self.settings.rabbitmq_url)
                params.socket_timeout = 3
                params.blocked_connection_timeout = 3
                params.connection_attempts = 1
                connection = pika.BlockingConnection(params)
                channel = connection.channel()
                channel.exchange_declare(exchange="music.events", exchange_type="direct", durable=True)
                for queue_name, key in (
                    ("playback.track.queue", "track.selected"),
                    ("playback.album.queue", "album.selected"),
                ):
                    channel.queue_declare(queue=queue_name, durable=True)
                    channel.queue_bind(exchange="music.events", queue=queue_name, routing_key=key)
                    channel.basic_consume(queue=queue_name, on_message_callback=self._handle_message,
                                          auto_ack=False)
                channel.basic_qos(prefetch_count=1)
                while not self.stop_event.is_set() and connection.is_open:
                    connection.process_data_events(time_limit=1)
            except Exception:
                if not self.stop_event.is_set():
                    logger.exception("Ошибка RabbitMQ, повторное подключение через 3 секунды")
            finally:
                if connection is not None and connection.is_open:
                    try:
                        connection.close()
                    except Exception:
                        logger.exception("Не удалось закрыть соединение RabbitMQ")
            self.stop_event.wait(3)
