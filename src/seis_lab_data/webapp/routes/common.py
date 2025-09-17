import asyncio
import json
import logging

from datastar_py import ServerSentEventGenerator
from datastar_py.consts import ElementPatchMode
from redis.asyncio import Redis
from starlette.requests import Request

from seis_lab_data import (
    constants,
    schemas,
)

logger = logging.getLogger(__name__)


async def produce_event_stream_for_topic(
    redis_client: Redis,
    request: Request,
    topic_name: str,
    success_redirect_url: str,
    timeout_seconds: int = 30,
):
    async with redis_client.pubsub() as pubsub:
        await pubsub.subscribe(topic_name)
        try:
            while True:
                if await request.is_disconnected():
                    logger.info(f"client disconnected from topic {topic_name!r}")
                    break
                try:
                    if message := await pubsub.get_message(
                        ignore_subscribe_messages=False, timeout=timeout_seconds
                    ):
                        if message["type"] == "subscribe":
                            logger.debug(f"Subscribed to topic {topic_name!r}")
                        elif message["type"] == "message":
                            processing_message = schemas.ProcessingMessage(
                                **json.loads(message["data"])
                            )
                            logger.debug(f"Received message: {processing_message!r}")
                            yield ServerSentEventGenerator.patch_elements(
                                f"<li>{processing_message.status.get_translated_value()} "
                                f"- {processing_message.message}</li>",
                                selector="#feedback > ul",
                                mode=ElementPatchMode.APPEND,
                            )
                            if processing_message.status in (
                                constants.ProcessingStatus.SUCCESS,
                                constants.ProcessingStatus.FAILED,
                            ):
                                if (
                                    processing_message.status
                                    == constants.ProcessingStatus.SUCCESS
                                ):
                                    yield ServerSentEventGenerator.patch_elements(
                                        "<li>Processing completed successfully - you will be redirected shortly</li>",
                                        selector="#feedback > ul",
                                        mode=ElementPatchMode.APPEND,
                                    )
                                    await asyncio.sleep(1)
                                    yield ServerSentEventGenerator.redirect(
                                        success_redirect_url
                                    )
                                break
                    else:
                        logging.info(
                            f"pubsub listener for topic {topic_name!r} timed out after {timeout_seconds} seconds"
                        )
                        break
                except asyncio.CancelledError:
                    logger.info(
                        f"pubsub listener for topic {topic_name!r} was cancelled"
                    )
                    raise
        finally:
            await pubsub.unsubscribe(topic_name)
