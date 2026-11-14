import json
import logging
from uuid import uuid4


logger = logging.getLogger(__name__)


class BrokerUnavailable(Exception):
    pass


class RabbitPublisher:
    def __init__(self, url: str):
        self.url = url

    def publish(self, event: dict, routing_key: str) -> None:
        try:
            import pika

            params = pika.URLParameters(self.url)
            params.socket_timeout = 3
            params.blocked_connection_timeout = 3
            params.connection_attempts = 1
            connection = pika.BlockingConnection(params)
            try:
                channel = connection.channel()
                channel.exchange_declare(exchange="music.events", exchange_type="direct", durable=True)
                for queue_name, key in (
                    ("playback.track.queue", "track.selected"),
                    ("playback.album.queue", "album.selected"),
                ):
                    channel.queue_declare(queue=queue_name, durable=True)
                    channel.queue_bind(exchange="music.events", queue=queue_name, routing_key=key)
                channel.confirm_delivery()
                channel.basic_publish(
                    exchange="music.events", routing_key=routing_key,
                    body=json.dumps(event).encode("utf-8"), mandatory=True,
                    properties=pika.BasicProperties(delivery_mode=2, content_type="application/json",
                                                   message_id=event["eventId"]),
                )
            finally:
                if connection.is_open:
                    connection.close()
        except Exception as exc:
            logger.exception("Не удалось опубликовать событие в RabbitMQ")
            raise BrokerUnavailable("RabbitMQ недоступен или отклонил сообщение") from exc
