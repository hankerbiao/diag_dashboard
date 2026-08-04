"""
DynamicSemaphore — 容量可动态调整的异步信号量。

asyncio.Semaphore 创建后容量不可修改，无法满足"设置页改并发数、实时生效"的
需求。本实现基于 asyncio.Lock + Future 等待者队列，把「限制值」作为 acquire
的判定条件：

- 调大：同步唤醒全部等待者，让它们重新竞争并按新容量放行；
- 调小：已持有的 token 继续执行完毕，新的 acquire 排队直到计数回落；
- 无瞬时超发：限制只是判定条件，不存在重建信号量导致的 token 回收问题。

实现说明：不使用 asyncio.Condition（其 notify_all 强制要求持有锁，无法在
同步的 set_limit/release 路径安全调用）；Future.set_result 在事件循环线程内
调用是线程安全的，等待者被唤醒后自行重新获取锁并重判。

仅适用于 asyncio 单线程事件循环（本项目全链路 async），线程安全不做保证。
"""

from __future__ import annotations

import asyncio
from typing import Self


class DynamicSemaphore:
    """容量可实时调整的异步信号量，支持 async with 上下文管理。"""

    def __init__(self, limit: int = 1):
        self._limit = max(1, int(limit))
        self._count = 0
        self._lock = asyncio.Lock()
        self._waiters: list[asyncio.Future] = []

    @property
    def limit(self) -> int:
        """当前并发上限。"""
        return self._limit

    @property
    def count(self) -> int:
        """当前已持有的 token 数。"""
        return self._count

    def set_limit(self, new_limit: int) -> None:
        """实时调整并发上限。

        调大时唤醒等待者重新判定；调小时不影响已持有 token，仅收紧后续准入。
        """
        new_limit = max(1, int(new_limit))
        if new_limit == self._limit:
            return
        increased = new_limit > self._limit
        self._limit = new_limit
        if increased:
            self._wake_waiters()

    def release(self) -> None:
        """释放一个 token 并唤醒等待者（调用方必须持有该 token）。"""
        if self._count > 0:
            self._count -= 1
            self._wake_waiters()

    async def acquire(self) -> None:
        """获取一个 token；容量已满时挂起等待。"""
        while True:
            async with self._lock:
                if self._count < self._limit:
                    self._count += 1
                    return
                waiter: asyncio.Future = asyncio.get_running_loop().create_future()
                self._waiters.append(waiter)
            await waiter

    async def __aenter__(self) -> Self:
        await self.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> None:
        self.release()

    def _wake_waiters(self) -> None:
        for waiter in self._waiters:
            if not waiter.done():
                waiter.set_result(None)
        self._waiters.clear()
