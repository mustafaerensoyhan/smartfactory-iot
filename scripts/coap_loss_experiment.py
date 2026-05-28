#!/usr/bin/env python3
"""
coap_loss_experiment.py
=======================
Controlled comparison of CoAP NON vs CON message delivery under simulated
packet loss.

WHY IN-PROCESS LOSS (and not tc/netem):
    On WSL2, `tc qdisc add dev lo root netem loss 10%` has NO effect on the
    loopback interface -- the virtualised network stack does not honour netem
    on `lo` (verified empirically: all rows show 0% loss even with netem
    applied). The only reliable way to inject loss on this setup is in-process:
    we randomly decide, per request, whether to "drop" it.

WHAT EACH MESSAGE TYPE DOES UNDER LOSS:
    NON (Non-confirmable): fire-and-forget. A dropped NON is gone, no
        retransmission, so it directly reduces the received count.
    CON (Confirmable): acknowledged. A dropped CON is retried up to
        MAX_RETRIES times; it only counts as lost if every attempt is dropped.

Run (CoAP server must be up in another terminal):
    # Terminal 1
    python -m src.coap.server
    # Terminal 2
    source .venv/bin/activate
    python scripts/coap_loss_experiment.py
"""

import asyncio
import random
import time
from statistics import mean

import aiocoap
from aiocoap import Message, Code
from aiocoap.numbers.types import Type

# --- Experiment parameters --------------------------------------------------
N_MESSAGES = 100        # requests per message type
LOSS_RATE = 0.10        # 10% simulated packet loss
MAX_RETRIES = 3         # CON retransmission attempts before giving up
TARGET = "coap://localhost/factory/line1/power"
SEED = 42               # fixed seed -> reproducible numbers


def dropped() -> bool:
    """Return True if this packet should be 'lost' (probability = LOSS_RATE)."""
    return random.random() < LOSS_RATE


async def send_one(ctx, confirmable: bool) -> tuple[bool, float]:
    """Send a single GET. Returns (received, latency_ms).

       NON: one attempt. If dropped(), it never arrives -> (False, 0).
       CON: up to MAX_RETRIES attempts; each attempt may be dropped.
            Succeeds if any attempt survives the drop test.
    """
    mtype = Type.CON if confirmable else Type.NON
    attempts = MAX_RETRIES if confirmable else 1

    t0 = time.time()
    for _ in range(attempts):
        if dropped():
            continue  # lost on the wire; CON retries, NON gives up
        msg = Message(code=Code.GET, uri=TARGET, mtype=mtype)
        try:
            await asyncio.wait_for(ctx.request(msg).response, timeout=2.0)
            return True, (time.time() - t0) * 1000.0
        except asyncio.TimeoutError:
            continue
    return False, 0.0


async def run_batch(confirmable: bool) -> dict:
    """Send N_MESSAGES of one type and tally results."""
    ctx = await aiocoap.Context.create_client_context()
    received = 0
    latencies = []
    for _ in range(N_MESSAGES):
        ok, lat = await send_one(ctx, confirmable)
        if ok:
            received += 1
            latencies.append(lat)
        await asyncio.sleep(0.01)
    await ctx.shutdown()

    lost = N_MESSAGES - received
    return {
        "sent": N_MESSAGES,
        "received": received,
        "lost": lost,
        "pct": lost / N_MESSAGES * 100.0,
        "lat_ms": mean(latencies) if latencies else 0.0,
    }


async def main():
    random.seed(SEED)
    print(f"CoAP loss experiment: {N_MESSAGES} msgs/type, "
          f"{int(LOSS_RATE*100)}% simulated loss, CON retries={MAX_RETRIES}\n")

    non = await run_batch(confirmable=False)
    con = await run_batch(confirmable=True)

    print("| Protocol | Sent | Received | Lost (%) | Avg Latency (ms) |")
    print("|----------|------|----------|----------|------------------|")
    for label, r in (("CoAP NON", non), ("CoAP CON", con)):
        print(f"| {label} | {r['sent']} | {r['received']} "
              f"| {r['pct']:.1f}% | {r['lat_ms']:.1f} |")


if __name__ == "__main__":
    asyncio.run(main())
