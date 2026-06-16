"""将同步 SSE 生成器桥接到 FastAPI，并在客户端断开时取消底层 CLI。"""

from __future__ import annotations

import asyncio
import threading
from typing import AsyncIterator, Callable, Generator, Optional, TypeVar

from starlette.requests import Request

T = TypeVar("T")


async def stream_with_cancel(
    request: Request,
    producer: Callable[[threading.Event], Generator[T, None, None]],
) -> AsyncIterator[T]:
    """在后台线程消费同步 generator；客户端断开时设置 cancel 事件。"""
    cancel = threading.Event()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Optional[T]] = asyncio.Queue()
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            for item in producer(cancel):
                if cancel.is_set():
                    break
                asyncio.run_coroutine_threadsafe(queue.put(item), loop).result()
        except BaseException as exc:
            errors.append(exc)
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    try:
        while True:
            if await request.is_disconnected():
                cancel.set()
                break
            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.25)
            except asyncio.TimeoutError:
                continue
            if item is None:
                break
            yield item
    finally:
        cancel.set()
        thread.join(timeout=5.0)

    if errors:
        raise errors[0]


async def stream_background_on_disconnect(
    request: Request,
    producer: Callable[[threading.Event], Generator[T, None, None]],
) -> AsyncIterator[T]:
    """桥接同步 generator；客户端断开时仅结束 HTTP，不取消 producer（后台继续）。"""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Optional[T]] = asyncio.Queue()
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            for item in producer(threading.Event()):
                asyncio.run_coroutine_threadsafe(queue.put(item), loop).result()
        except BaseException as exc:
            errors.append(exc)
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.25)
            except asyncio.TimeoutError:
                continue
            if item is None:
                break
            yield item
    finally:
        thread.join(timeout=2.0)

    if errors:
        raise errors[0]
