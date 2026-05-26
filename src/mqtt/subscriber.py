"""
Module 1 Assignment — Task 1.2
MQTT Wildcard Subscriber

Complete all TODO sections. Do not modify the function signatures.
"""

import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import paho.mqtt.client as mqtt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
BROKER_HOST  = "localhost"
BROKER_PORT  = 1883
CLIENT_ID    = "smartfactory-subscriber-001"

TOPIC_ALL        = "factory/#"                  # all factory messages (wildcard)
TOPIC_TEMP       = "factory/+/temperature"      # all temperatures (any line)

CRITICAL_TEMP    = 85.0
SUMMARY_INTERVAL = 30   # seconds

# paho-mqtt 2.x compatibility (see publisher.py for explanation)
try:
    _PAHO_V2_KWARGS = {"callback_api_version": mqtt.CallbackAPIVersion.VERSION1}
except AttributeError:
    _PAHO_V2_KWARGS = {}


class SmartFactorySubscriber:
    """Subscribes to SmartFactory sensor topics and processes incoming data."""

    def __init__(self, broker_host: str = BROKER_HOST, broker_port: int = BROKER_PORT):
        self.broker_host  = broker_host
        self.broker_port  = broker_port
        self._client      = mqtt.Client(
            **_PAHO_V2_KWARGS,
            client_id=CLIENT_ID,
            clean_session=False,
        )
        self._msg_counts: dict[str, int] = defaultdict(int)
        self._last_summary = time.time()
        self._alerts_fired = 0

        self._client.on_connect = self.on_connect
        self._client.on_message = self.on_message

    # ── Connection ─────────────────────────────────────────────────────────────

    def on_connect(self, client, userdata, flags, rc: int) -> None:
        """Subscribe to wildcard and temperature topics on successful connect."""
        if rc == 0:
            log.info("Connected to broker")
            # Subscribe to ALL factory traffic at QoS 1
            client.subscribe(TOPIC_ALL, qos=1)
            # SEPARATE subscription for temperature at the strongest QoS (2)
            client.subscribe(TOPIC_TEMP, qos=2)
            log.info(f"Subscribed: {TOPIC_ALL} (QoS 1) and {TOPIC_TEMP} (QoS 2)")
        else:
            log.error(f"Connection failed (rc={rc})")

    # ── Message Handling ───────────────────────────────────────────────────────

    def on_message(self, client, userdata, msg: mqtt.MQTTMessage) -> None:
        """Handle every incoming message: count, parse, display, check alerts."""
        self._msg_counts[msg.topic] += 1

        # Try JSON-parse the payload; fall back to raw string
        try:
            payload = json.loads(msg.payload)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            try:
                payload = msg.payload.decode(errors="replace")
            except AttributeError:
                payload = str(msg.payload)

        self._print_message(msg, payload)

        if msg.topic.endswith("/temperature"):
            self._check_temperature_alert(msg.topic, payload)

        # Periodic summary
        if time.time() - self._last_summary >= SUMMARY_INTERVAL:
            self._print_summary()
            self._last_summary = time.time()

    def _print_message(self, msg: mqtt.MQTTMessage, payload: Any) -> None:
        """Format and log one received message."""
        ts = datetime.now().strftime("%H:%M:%S")
        if isinstance(payload, dict) and "value" in payload:
            val_str = f"{payload['value']}"
            if "unit" in payload:
                val_str = f"{payload['value']} {payload['unit']}"
        else:
            val_str = str(payload)
        log.info(
            f"[{ts}] {msg.topic}  val={val_str}  "
            f"QoS={msg.qos}  retain={bool(msg.retain)}"
        )

    def _check_temperature_alert(self, topic: str, payload: Any) -> None:
        """Fire a CRITICAL ALERT banner if temperature > 85°C."""
        if not isinstance(payload, dict):
            return
        value = payload.get("value")
        if not isinstance(value, (int, float)):
            return
        if value > CRITICAL_TEMP:
            self._alerts_fired += 1
            ts = payload.get("timestamp", datetime.now(timezone.utc).isoformat())
            print()
            print("╔══════════════════════════════════════════════════════════╗")
            print(f"║  ⚠ CRITICAL ALERT — {topic}")
            print(f"║  Temperature: {value}°C  (threshold: {CRITICAL_TEMP}°C)")
            print(f"║  Time: {ts}")
            print("╚══════════════════════════════════════════════════════════╝")
            print()

    def _print_summary(self) -> None:
        """Print a per-topic message count summary."""
        print()
        print("── Message Summary ──────────────────────────────────────")
        total = 0
        for topic, count in sorted(self._msg_counts.items()):
            print(f"  {topic:<50}  {count:>6} msgs")
            total += count
        print(f"  Total: {total} messages  |  Alerts fired: {self._alerts_fired}")
        print("─────────────────────────────────────────────────────────")
        print()

    # ── Run ────────────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Connect and block until interrupted."""
        self._client.connect(self.broker_host, self.broker_port, keepalive=60)
        log.info("Listening for messages (Ctrl-C to stop)")
        try:
            self._client.loop_forever()
        except KeyboardInterrupt:
            log.info("Subscriber stopped")
        finally:
            self._client.disconnect()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sub = SmartFactorySubscriber()
    sub.run()
