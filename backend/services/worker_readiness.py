"""Executable worker preflight; avoids generated Python in rollout helpers."""
import asyncio
import inspect
import sys

from services.jobs import get_pool, ingest_document


async def check_ready() -> None:
    if "public_reference" not in inspect.signature(ingest_document).parameters:
        raise RuntimeError("Worker lacks explicit shared-reference scope")
    async with asyncio.timeout(8):
        pool = await get_pool()
        try:
            if not await pool.ping():
                raise RuntimeError("Worker Redis readiness failed")
        finally:
            await pool.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(check_ready())
    except Exception as exc:
        # Exception messages can contain connection credentials. Report type only.
        print("WORKER_READINESS_FAILED:" + type(exc).__name__, file=sys.stderr)
        sys.exit(1)
    print("WORKER_READINESS_PASS")
