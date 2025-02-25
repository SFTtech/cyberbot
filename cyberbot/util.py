from __future__ import annotations

import asyncio
import logging
import traceback
from typing import Any, Coroutine, Sequence


async def run_tasks(coros: Sequence[Coroutine[Any, Any, Any]], timeout: float) -> Sequence[Any]:
    """
    launch multiple coroutines as tasks, wait for the timeout.
    if this is cancelled, the coros will also be cancelled.

    exceptions in the tasks are logged.
    """
    tasks: list[asyncio.Task] = [
        asyncio.create_task(coro) for coro in coros
    ]

    if not tasks:
        return []

    results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)
    for val in results:
        if isinstance(val, Exception):
            logging.error("task threw exception:\n%s", "\n".join(traceback.format_exception(val)))

    return results
