"""DynamicSemaphore 单元测试 — 容量可动态调整的异步信号量行为。"""
import asyncio

import pytest

from app.services.log_processing.dynamic_semaphore import DynamicSemaphore


class TestDynamicSemaphore:
    @pytest.mark.asyncio
    async def test_caps_concurrency_at_initial_limit(self):
        sem = DynamicSemaphore(2)
        active = 0
        peak = 0

        async def worker():
            nonlocal active, peak
            async with sem:
                active += 1
                peak = max(peak, active)
                await asyncio.sleep(0.01)
                active -= 1

        await asyncio.gather(*(worker() for _ in range(8)))
        assert peak == 2

    @pytest.mark.asyncio
    async def test_expands_when_limit_increased(self):
        sem = DynamicSemaphore(1)
        entered: list[int] = []

        async def worker(index: int):
            async with sem:
                entered.append(index)
                await asyncio.sleep(0.05)

        first = asyncio.create_task(worker(1))
        await asyncio.sleep(0.01)
        second = asyncio.create_task(worker(2))
        await asyncio.sleep(0.01)
        assert entered == [1]

        sem.set_limit(2)  # 调大后第二个等待者应立即放行
        await asyncio.gather(first, second)
        assert sorted(entered) == [1, 2]

    @pytest.mark.asyncio
    async def test_shrinking_blocks_new_acquires_until_release(self):
        sem = DynamicSemaphore(2)
        await sem.acquire()
        await sem.acquire()
        sem.set_limit(1)  # 调小：已持有者继续，新 acquire 排队

        waiter = asyncio.create_task(sem.acquire())
        await asyncio.sleep(0.05)
        assert not waiter.done()

        sem.release()  # count 2 -> 1，仍达到上限，等待者继续阻塞
        await asyncio.sleep(0.02)
        assert not waiter.done()

        sem.release()  # count 1 -> 0，等待者放行
        await asyncio.wait_for(waiter, timeout=1)

    @pytest.mark.asyncio
    async def test_set_limit_same_value_is_noop(self):
        sem = DynamicSemaphore(3)
        gen_snapshot = (sem.limit, sem.count)
        sem.set_limit(3)
        assert (sem.limit, sem.count) == gen_snapshot

    def test_limit_is_clamped_to_at_least_one(self):
        assert DynamicSemaphore(0).limit == 1
        assert DynamicSemaphore(-5).limit == 1
