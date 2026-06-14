import json
from collections.abc import AsyncGenerator

from datastar_py.sse import ServerSentEventGenerator
from datastar_py.starlette import DatastarEvent


async def flash_ui_message_after_redirect(
    ui_message: dict[str, str],
) -> AsyncGenerator[DatastarEvent, None]:
    yield ServerSentEventGenerator.execute_script(
        f"localStorage.setItem('sld:flash', '{json.dumps(ui_message)}');"
    )


async def flash_ui_message_same_page(
    ui_message: dict[str, str],
) -> AsyncGenerator[DatastarEvent, None]:
    yield ServerSentEventGenerator.execute_script(
        f"showFlash({json.dumps(ui_message)})"
    )
