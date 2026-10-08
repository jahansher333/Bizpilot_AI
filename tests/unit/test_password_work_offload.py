"""Argon2 work runs in worker threads, bounded, never on the event loop (SEC-P1 F4)."""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

from app.core.config import Settings
from app.modules.auth.password import HASHING_CONCURRENCY, PasswordService, run_password_work


@pytest.mark.asyncio
async def test_password_work_runs_off_the_event_loop_thread() -> None:
    loop_thread = threading.get_ident()
    worker_thread = await run_password_work(threading.get_ident)
    assert worker_thread != loop_thread


@pytest.mark.asyncio
async def test_password_work_is_capped_at_four_concurrent_jobs() -> None:
    assert HASHING_CONCURRENCY == 4
    lock = threading.Lock()
    state = {"running": 0, "peak": 0}

    def job() -> None:
        with lock:
            state["running"] += 1
            state["peak"] = max(state["peak"], state["running"])
        time.sleep(0.05)
        with lock:
            state["running"] -= 1

    await asyncio.gather(*(run_password_work(job) for _ in range(12)))
    assert state["peak"] == HASHING_CONCURRENCY


@pytest.mark.asyncio
async def test_event_loop_keeps_serving_while_hashing() -> None:
    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0.01)

    task = asyncio.create_task(ticker())
    await run_password_work(time.sleep, 0.3)
    task.cancel()
    # A blocked loop would tick once or twice; a free loop ticks roughly 30 times in 0.3 s.
    assert ticks >= 10


@pytest.mark.asyncio
async def test_errors_from_password_work_propagate() -> None:
    def fail() -> None:
        raise ValueError("policy violation")

    with pytest.raises(ValueError, match="policy violation"):
        await run_password_work(fail)


def test_service_construction_does_not_hash() -> None:
    """Services are built per request; building one must not run Argon2 on the caller's thread."""
    settings = Settings(
        environment="test",
        database={"url": "postgresql://user:pw@localhost:5432/bizpilot"},
        auth={"signing_secret": "test-only-signing-secret", "argon2_time_cost": 50, "argon2_memory_cost_kib": 65536},
    )
    started = time.perf_counter()
    PasswordService(settings)
    assert time.perf_counter() - started < 0.2


@pytest.mark.asyncio
async def test_real_hash_and_verify_round_trip_through_worker_threads() -> None:
    settings = Settings(
        environment="test",
        database={"url": "postgresql://user:pw@localhost:5432/bizpilot"},
        auth={
            "signing_secret": "test-only-signing-secret",
            "argon2_time_cost": 1,
            "argon2_memory_cost_kib": 8192,
            "argon2_parallelism": 1,
        },
    )
    service = PasswordService(settings)
    hashed = await run_password_work(service.hash_password, "Correct Horse Battery 42")
    assert (await run_password_work(service.verify_password, "Correct Horse Battery 42", hashed)).valid
    assert not (await run_password_work(service.verify_password, "wrong password value", hashed)).valid
    await run_password_work(service.verify_dummy)
