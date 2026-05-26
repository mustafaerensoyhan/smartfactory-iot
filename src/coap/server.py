"""
Module 1 Assignment — Task 2.1
CoAP Sensor Resource Server

Complete all TODO sections. The resource classes must match the
URIs and behaviours listed in the assignment spec.

Run with:  python -m src.coap.server
"""

import asyncio
import json
import logging
import random
from datetime import datetime, timezone

import aiocoap
import aiocoap.resource as resource
from aiocoap import Code, Message

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
log = logging.getLogger(__name__)

# ── Sensor simulation helpers ─────────────────────────────────────────────────

SENSOR_CONFIG = {
    "temperature": {"unit": "C",    "base": 70.0, "noise": 3.0},
    "vibration":   {"unit": "mm/s", "base": 1.2,  "noise": 0.3},
    "power":       {"unit": "kW",   "base": 45.0, "noise": 5.0},
}

# CoAP Content-Format identifier for application/json (RFC 7252 + IANA)
CF_JSON = 50


def _sim(sensor: str) -> dict:
    cfg = SENSOR_CONFIG[sensor]
    return {
        "value": round(cfg["base"] + random.gauss(0, cfg["noise"]), 3),
        "unit":  cfg["unit"],
        "ts":    datetime.now(timezone.utc).isoformat(),
    }


def _json(data: dict) -> bytes:
    return json.dumps(data).encode()


# ── Observable Sensor Resource ────────────────────────────────────────────────

class SensorResource(resource.ObservableResource):
    """
    A CoAP resource representing one sensor on one production line.

    Inherits ObservableResource so clients can register Observe (RFC 7641):
    the server then pushes a fresh notification whenever updated_state() is
    called. The background _update_loop simulates a new reading every 5 s.
    """

    def __init__(self, line: str, sensor_type: str):
        super().__init__()
        self.line        = line
        self.sensor_type = sensor_type
        self._reading    = _sim(sensor_type)
        # Schedule the per-resource update loop on the running event loop.
        # ensure_future works here because __init__ runs inside build_server(),
        # which is itself awaited from asyncio.run(main()).
        self._task = asyncio.ensure_future(self._update_loop())

    async def _update_loop(self) -> None:
        """Refresh the reading every 5 s and notify all subscribed observers."""
        try:
            while True:
                await asyncio.sleep(5)
                self._reading = _sim(self.sensor_type)
                # Tell aiocoap to push a fresh notification to every observer
                self.updated_state()
        except asyncio.CancelledError:
            log.debug(f"Update loop cancelled for {self.line}/{self.sensor_type}")

    async def render_get(self, request: Message) -> Message:
        """Return the current sensor reading as JSON with content-format 50."""
        return Message(
            code=Code.CONTENT,
            payload=_json(self._reading),
            content_format=CF_JSON,
        )


# ── Actuator Resource ─────────────────────────────────────────────────────────

class ActuatorResource(resource.Resource):
    """
    A non-observable resource representing a cooling fan.
    GET returns current state; PUT changes it (only ON/OFF accepted).
    """

    def __init__(self):
        super().__init__()
        self._state = "OFF"

    async def render_get(self, request: Message) -> Message:
        return Message(
            code=Code.CONTENT,
            payload=_json({"state": self._state}),
            content_format=CF_JSON,
        )

    async def render_put(self, request: Message) -> Message:
        # Try to parse the body; reject any malformed input with 4.00.
        try:
            data = json.loads(request.payload)
        except (json.JSONDecodeError, AttributeError):
            return Message(
                code=Code.BAD_REQUEST,
                payload=_json({"error": "payload must be JSON"}),
                content_format=CF_JSON,
            )

        state = data.get("state") if isinstance(data, dict) else None
        if state not in ("ON", "OFF"):
            return Message(
                code=Code.BAD_REQUEST,
                payload=_json({"error": "state must be 'ON' or 'OFF'"}),
                content_format=CF_JSON,
            )

        self._state = state
        log.info(f"Fan state changed → {state}")
        return Message(
            code=Code.CHANGED,
            payload=_json({"state": state}),
            content_format=CF_JSON,
        )


# ── Block-wise Manifest Resource ──────────────────────────────────────────────

class ManifestResource(resource.Resource):
    """
    A resource large enough (>= 3 KB) to trigger Block2 fragmentation.
    aiocoap auto-chunks the response into Block2 blocks based on the
    negotiated block size — we just return the full payload.
    """

    async def render_get(self, request: Message) -> Message:
        manifest = {
            "schema_version": "1.0",
            "factory_id":     "SMARTFACTORY-001",
            "generated_at":   datetime.now(timezone.utc).isoformat(),
            "firmware_entries": [
                {
                    "device_id":       f"sensor-{i:04d}",
                    "device_type":     ["temperature", "vibration", "power"][i % 3],
                    "line":            f"line{(i % 2) + 1}",
                    "current_version": f"2.{i % 10}.{i % 20}",
                    "target_version":  "3.0.0",
                    "checksum_sha256": f"a1b2c3d4e5f67890{i:048x}",
                    "update_url":      f"coap://updates.smartfactory.local/fw/sensor-{i:04d}-v3.0.0.bin",
                    "size_bytes":      1024 * (i + 1),
                    "mandatory":       (i % 5 == 0),
                }
                for i in range(50)
            ],
        }
        payload = _json(manifest)
        # Safety: make sure we are actually big enough to trigger Block2
        assert len(payload) >= 3072, f"Manifest only {len(payload)} bytes — needs >= 3072"
        return Message(code=Code.CONTENT, payload=payload, content_format=CF_JSON)


# ── Resource Tree & Server Setup ──────────────────────────────────────────────

async def build_server() -> aiocoap.Context:
    """Build the CoAP resource tree and create the server context."""
    root = resource.Site()

    # Sensor resources (all 4 are observable per the spec)
    root.add_resource(['factory', 'line1', 'temperature'],
                      SensorResource('line1', 'temperature'))
    root.add_resource(['factory', 'line1', 'vibration'],
                      SensorResource('line1', 'vibration'))
    root.add_resource(['factory', 'line1', 'power'],
                      SensorResource('line1', 'power'))
    root.add_resource(['factory', 'line2', 'temperature'],
                      SensorResource('line2', 'temperature'))

    # Actuator
    root.add_resource(['actuator', 'line1', 'fan'], ActuatorResource())

    # Block-wise manifest (large)
    root.add_resource(['factory', 'manifest'], ManifestResource())

    # CoRE Link Format discovery endpoint
    root.add_resource(['.well-known', 'core'],
                      resource.WKCResource(root.get_resources_as_linkheader))

    context = await aiocoap.Context.create_server_context(root)
    return context


async def main() -> None:
    context = await build_server()
    log.info("CoAP server running on coap://localhost:5683")
    log.info("Resources: /factory/line{1,2}/{temperature,vibration,power}, /actuator/line1/fan, /factory/manifest")
    log.info("Discovery: coap://localhost/.well-known/core")
    # Run forever until Ctrl-C
    await asyncio.get_event_loop().create_future()


if __name__ == "__main__":
    asyncio.run(main())
