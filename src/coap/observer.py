"""
Module 1 Assignment — Task 2.2
CoAP Observer Client

Subscribes to two temperature resources concurrently, detects stale
Observe notifications (per RFC 7641 reordering rule), then fetches a
Block2 manifest. Runs for OBSERVE_DURATION seconds before cleanly
deregistering.

Run with:  python -m src.coap.observer
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

import aiocoap
from aiocoap import Message, Code

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
log = logging.getLogger(__name__)

SERVER_BASE = "coap://localhost"
OBSERVE_DURATION = 60   # seconds before clean deregister

# RFC 7641 §3.4: Observe option wraps at 2^24
OBSERVE_WRAP = 1 << 24
HALF_WINDOW  = 1 << 23   # used for the "is newer" comparison


class FactoryObserver:
    """Observes CoAP sensor resources and reassembles a Block2 manifest."""

    def __init__(self):
        self._ctx = None
        self._last_seq:    dict[str, int] = {}   # uri -> last observe sequence
        self._stale_count: dict[str, int] = {}   # uri -> count of stale notifications

    # ── Setup ──────────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Create the aiocoap client context."""
        self._ctx = await aiocoap.Context.create_client_context()

    async def stop(self) -> None:
        """Clean up the context."""
        if self._ctx:
            await self._ctx.shutdown()

    # ── Observation ────────────────────────────────────────────────────────────

    async def observe_resource(self, uri: str) -> None:
        """
        Subscribe to one observable resource for OBSERVE_DURATION seconds,
        then cancel the observation cleanly.
        """
        log.info(f"Registering Observe on {uri}")
        request = Message(code=Code.GET, uri=uri, observe=0)
        pr = self._ctx.request(request)

        async def _loop() -> None:
            try:
                # First response — also confirms the Observe registration
                first = await pr.response
                self._handle_notification(uri, first)
                # Subsequent server-pushed notifications
                async for response in pr.observation:
                    self._handle_notification(uri, response)
            except Exception as e:
                log.error(f"Observation error on {uri}: {e}")

        try:
            await asyncio.wait_for(_loop(), timeout=OBSERVE_DURATION)
        except asyncio.TimeoutError:
            log.info(f"{OBSERVE_DURATION}s elapsed for {uri} — deregistering")
        finally:
            # Cancel local observation. aiocoap handles graceful teardown:
            # the next notification will not be ACKed, and the server will
            # remove us from its observer list per RFC 7641 §3.6.
            try:
                pr.observation.cancel()
            except Exception:
                pass
            log.info(f"Deregistered from {uri}")

    def _handle_notification(self, uri: str, response: Message) -> None:
        """Validate sequence, log, and optionally count stale notifications."""
        seq = response.opt.observe   # None if the resource isn't observable

        if seq is not None and uri in self._last_seq:
            last = self._last_seq[uri]
            # RFC 7641 §3.4 freshness check (handles wrap-around at 2^24)
            is_fresh = (
                (last < seq and seq - last < HALF_WINDOW) or
                (last > seq and last - seq > HALF_WINDOW)
            )
            if not is_fresh:
                self._stale_count[uri] = self._stale_count.get(uri, 0) + 1
                log.warning(f"STALE notification on {uri}: seq={seq} <= last={last}")
                return

        if seq is not None:
            self._last_seq[uri] = seq

        # Parse the JSON payload (best-effort)
        try:
            data = json.loads(response.payload)
            value = data.get("value", "?")
            unit  = data.get("unit", "")
            ts    = data.get("ts", "?")
        except (json.JSONDecodeError, AttributeError):
            value, unit, ts = response.payload, "", "?"

        arrival = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log.info(f"[OBSERVE] {uri}  seq={seq}  val={value} {unit}  @ {arrival}")

    # ── Block2 Transfer ────────────────────────────────────────────────────────

    async def fetch_manifest(self) -> None:
        """
        GET /factory/manifest and let aiocoap reassemble Block2 transparently.
        Log byte count, entry count, and (best-effort) the final block index.
        """
        uri = f"{SERVER_BASE}/factory/manifest"
        log.info(f"Fetching Block2 manifest from {uri}")
        request = Message(code=Code.GET, uri=uri)
        response = await self._ctx.request(request).response

        n_bytes = len(response.payload)
        log.info(f"Manifest received: {n_bytes} bytes")

        # Parse and count firmware entries
        try:
            data = json.loads(response.payload)
            if isinstance(data, dict) and "firmware_entries" in data:
                count = len(data["firmware_entries"])
            elif isinstance(data, list):
                count = len(data)
            else:
                count = 1
            log.info(f"Firmware entries in manifest: {count}")
        except json.JSONDecodeError as e:
            log.warning(f"Manifest is not valid JSON: {e}")

        # Best-effort Block2 metadata. aiocoap reassembles internally, so the
        # final response carries only the *last* Block2 option.
        block2 = response.opt.block2
        if block2 is not None:
            block_size = 1 << (block2.size_exponent + 4)
            total_blocks = block2.block_number + 1
            log.info(
                f"Block2: block_size=2^{block2.size_exponent + 4}={block_size}B, "
                f"final block #{block2.block_number} → ~{total_blocks} blocks total"
            )
        else:
            log.info("Block2: response was small enough to fit a single block")

        log.info("Block2 transfer complete")

    # ── Run ────────────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Run both observations concurrently, then fetch the manifest."""
        await self.start()
        try:
            log.info("Starting concurrent Observe on line1 + line2 temperature")
            await asyncio.gather(
                self.observe_resource(f"{SERVER_BASE}/factory/line1/temperature"),
                self.observe_resource(f"{SERVER_BASE}/factory/line2/temperature"),
            )

            log.info("All observations ended — fetching firmware manifest")
            await self.fetch_manifest()

            # Final summary
            log.info("─" * 60)
            log.info("Observer Summary")
            log.info(f"  Notifications tracked on {len(self._last_seq)} resources")
            if self._stale_count:
                for uri, count in self._stale_count.items():
                    log.info(f"  Stale notifications on {uri}: {count}")
            else:
                log.info("  No stale notifications detected")
            log.info("─" * 60)
        finally:
            await self.stop()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    observer = FactoryObserver()
    asyncio.run(observer.run())
