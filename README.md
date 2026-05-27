# SmartFactory IoT Pipeline

A simulated real-time IoT data pipeline for a factory with two production lines. Sensors publish telemetry through **MQTT** and **CoAP**; subscribers consume and process the streams; packet-level traces and a comparative analysis are included.

Submission for **Module 1 — Real-Time Data Analytics for IoT** (Graduate, Ontario Tech University).

---

## Scenario

The simulated factory has two production lines (`line1`, `line2`), each with three sensors and one cooling-fan actuator:

| Sensor | Unit | Update rate |
|---|---|---|
| Temperature | °C | 1 Hz (MQTT) · every 5 s (CoAP) |
| Vibration | mm/s | 1 Hz · 5 s |
| Power | kW | 1 Hz · 5 s |

A critical alert fires when any temperature reading exceeds **85 °C**. Cooling fans are addressable via CoAP PUT.

The pipeline is implemented twice (MQTT and CoAP) so the two protocols can be compared on the same workload. AMQP (Task 3) is intentionally out of scope for this submission per instructor guidance; the corresponding starter scaffolding remains under `src/amqp/` but is not implemented.

---

## Repository layout

```
smartfactory-iot/
├── src/
│   ├── mqtt/
│   │   ├── publisher.py        # Persistent session, LWT, retained status, per-sensor QoS
│   │   └── subscriber.py       # Wildcard + QoS-2 temperature sub, critical-alert detection
│   └── coap/
│       ├── server.py           # 6 observable resources + actuator + Block2 manifest
│       └── observer.py         # Concurrent observers + stale-notification (RFC 7641 §3.4)
├── tests/                      # Pytest suite (unmodified from starter kit)
├── captures/
│   ├── mqtt.pcap               # 30-second loopback capture, port 1883
│   └── coap.pcap               # 30-second loopback capture, UDP port 5683
├── report/
│   ├── packet_analysis.md      # Task 4 — wire-level annotations of CONNECT, PUBLISH, PUBACK, CON GET, ACK 2.05, Observe
│   └── comparison_report.md    # Task 5 — QoS table, proxy mapping, recommendations, reflection
├── config/mosquitto.conf
├── docker-compose.yml          # Mosquitto + RabbitMQ + InfluxDB (only Mosquitto required)
├── requirements.txt
├── pytest.ini
└── setup.sh
```

---

## What was implemented

### Task 1 — MQTT (`src/mqtt/`)

- Publisher connects with `clean_session=False`, declares Last Will & Testament on `factory/line1/status` (`offline`, QoS 1, retained), publishes retained `online` on startup, then streams six sensors at 1 Hz with per-sensor QoS (temperature = 1, vibration = 0, power = 2).
- Subscriber registers both a `factory/#` wildcard (QoS 1) and a `factory/+/temperature` subscription (QoS 2), parses JSON payloads, detects temperatures > 85 °C, and prints a per-topic summary every 30 s.
- QoS comparison experiment in `tests/mqtt/test_qos_loss.py` produces the latency table referenced in the report.

### Task 2 — CoAP (`src/coap/`)

- `SensorResource` (observable) — refreshes its reading every 5 s and notifies subscribers via `updated_state()`.
- `ActuatorResource` — accepts `{"state":"ON"|"OFF"}` via PUT, returns 2.04 Changed on success or 4.00 Bad Request on invalid input.
- `ManifestResource` — returns a ≥3 KB JSON document with 50 firmware entries, automatically fragmented by aiocoap into Block2 chunks.
- `FactoryObserver` — registers two concurrent Observe subscriptions, runs for 60 s, then cleanly deregisters; performs RFC 7641 §3.4 freshness checks on the 24-bit sequence number; finally fetches and reassembles the Block2 manifest.

### Task 4 — Packet capture and annotation

Captures were produced live on the loopback interface using `tshark`. Each annotated packet in `report/packet_analysis.md` includes the raw hex, byte-by-byte field breakdown, and (where applicable) bit-level expansion of header bytes such as the MQTT Connect Flags byte and the CoAP version/type/TKL byte.

### Task 5 — Comparison report

`report/comparison_report.md` contains the measured QoS results, the CoAP→HTTP proxy header mapping per RFC 8075, four protocol recommendations each justified by specific evidence from the captures and tests, and a reflection on implementation challenges.

---

## Running locally

Tested on Ubuntu 24.04 (WSL2 on Windows 11). Requires Docker, Python ≥ 3.10, and `tshark` if reproducing the packet captures.

```bash
# Environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Broker
docker compose up -d mosquitto
```

### MQTT

```bash
# Terminal 1
python -m src.mqtt.subscriber

# Terminal 2
python -m src.mqtt.publisher
```

### CoAP

```bash
# Terminal 1
python -m src.coap.server

# Terminal 2
python -m src.coap.observer
```

### Packet captures

```bash
tshark -i lo -f "port 1883"        -w captures/mqtt.pcap -a duration:30
tshark -i lo -f "udp port 5683"    -w captures/coap.pcap -a duration:30
```

---

## Testing

```bash
# Full test suite (MQTT + CoAP)
pytest tests/mqtt/test_publisher.py tests/coap/test_server.py -v
```

All 21 tests pass on the reference environment (11 MQTT + 10 CoAP). The CoAP tests require `asyncio_default_fixture_loop_scope = module` in `pytest.ini` (already set) for the module-scoped server fixture to share an event loop with its tests under `pytest-asyncio` ≥ 1.4.

To reproduce the QoS comparison results from Section 5.1 of the report:

```bash
pytest tests/mqtt/test_qos_loss.py -v -s
```

---

## Tech stack

- **Python 3.12** · **paho-mqtt 2.1** (with VERSION1 callback compatibility shim) · **aiocoap 0.4.17**
- **Eclipse Mosquitto 2.0** broker (Docker)
- **tshark / Wireshark 4.2** for live captures
- **pytest 9.0** with `pytest-asyncio` and `pytest-timeout`

---

## AI assistance disclosure

AI assistance was used during development for code implementation, refactoring and troubleshooting guidance, and assistance drafting readme. All environment setup, packet captures, test execution, and verification of outputs were performed by the author in the local WSL2 environment, and every captured value reported in `report/packet_analysis.md` corresponds to packets present in the included `.pcap` files.

---

*Module 1 · Real-Time Data Analytics for IoT · Ontario Tech University*
