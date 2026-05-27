# Module 1 Assignment — Packet Analysis
## Task 4: Wire-Level Protocol Annotation

**Student:** Mustafa Eren Soyhan
**Student ID:** 101045056
**Captures used:**
- `captures/mqtt.pcap` — 30 s, loopback (`lo`), 571 packets
- `captures/coap.pcap` — 30 s, loopback (`lo`), Observe + GET traffic

---

## 4.2 MQTT Packet Annotations

All values below are taken from **`captures/mqtt.pcap`** as decoded by Wireshark / `tshark -V -x`.

### CONNECT Packet (Frame 4)

MQTT payload begins at TCP byte offset `0x42` in the pcap. Raw bytes:

```
10 45 00 04 4D 51 54 54 04 2C 00 3C 00 1A
73 6D 61 72 74 66 61 63 74 6F 72 79 2D 70 75 62 6C 69 73 68 65 72 2D 30 30 31
00 14 66 61 63 74 6F 72 79 2F 6C 69 6E 65 31 2F 73 74 61 74 75 73
00 07 6F 66 66 6C 69 6E 65
```

| Field | Offset (bytes) | Raw Hex | Decoded Value |
|-------|---------------|---------|---------------|
| Frame type + flags (byte 1) | 0 | `10` | Type = CONNECT (`0001`), flags = `0000` |
| Remaining length (byte 2) | 1 | `45` | 69 bytes |
| Protocol name length | 2–3 | `00 04` | 4 |
| Protocol name | 4–7 | `4D 51 54 54` | "MQTT" |
| Protocol version | 8 | `04` | 4 (MQTT v3.1.1) |
| Connect flags | 9 | `2C` | See breakdown below |
| Keep-alive | 10–11 | `00 3C` | 60 seconds |
| Client ID length | 12–13 | `00 1A` | 26 |
| Client ID | 14–39 | `73 6D 61 72 74 66 61 63 74 6F 72 79 2D 70 75 62 6C 69 73 68 65 72 2D 30 30 31` | "smartfactory-publisher-001" |
| Will Topic length | 40–41 | `00 14` | 20 |
| Will Topic | 42–61 | `66 61 63 74 6F 72 79 2F 6C 69 6E 65 31 2F 73 74 61 74 75 73` | "factory/line1/status" |
| Will Message length | 62–63 | `00 07` | 7 |
| Will Message | 64–70 | `6F 66 66 6C 69 6E 65` | "offline" |

**Connect Flags byte breakdown** (`0x2C` = `0010 1100`):

| Bit | Name | Value | Meaning |
|-----|------|-------|---------|
| 7 | Username flag | 0 | No username supplied |
| 6 | Password flag | 0 | No password supplied |
| 5 | Will retain | 1 | LWT message will be retained by broker |
| 4–3 | Will QoS | 01 | LWT delivered at QoS 1 (at-least-once) |
| 2 | Will flag | 1 | LWT enabled (topic + message provided) |
| 1 | Clean session | 0 | **Persistent session — broker retains state across reconnects** |
| 0 | Reserved | 0 | — |

**Note:** Clean Session = 0 confirms the publisher requests a *persistent* MQTT session (matches the assignment spec and the publisher source code).

---

### QoS 1 PUBLISH Packet (Frame 8)

This is the initial **retained "online"** status PUBLISH the publisher emits right after CONNECT (Topic = `factory/line1/status`).

MQTT bytes (TCP offset `0x42`):

```
33 1E 00 14 66 61 63 74 6F 72 79 2F 6C 69 6E 65 31 2F 73 74 61 74 75 73
00 01 6F 6E 6C 69 6E 65
```

| Field | Offset (bytes) | Raw Hex | Decoded Value |
|-------|---------------|---------|---------------|
| Fixed header byte 1 | 0 | `33` | Type = PUBLISH(`0011`), DUP = 0, QoS = 1, RETAIN = 1 |
| Remaining length | 1 | `1E` | 30 bytes |
| Topic length | 2–3 | `00 14` | 20 |
| Topic string | 4–23 | `66 61 63 74 6F 72 79 2F 6C 69 6E 65 31 2F 73 74 61 74 75 73` | "factory/line1/status" |
| Packet Identifier | 24–25 | `00 01` | 1 |
| Payload | 26–31 | `6F 6E 6C 69 6E 65` | "online" |

**Fixed header byte 1 bit expansion** (`0x33` = `0011 0011`):

| Bits 7–4 (packet type) | Bit 3 (DUP) | Bits 2–1 (QoS) | Bit 0 (RETAIN) |
|------------------------|-------------|----------------|----------------|
| `0011` = PUBLISH (3)   | `0` = not a duplicate | `01` = QoS 1 (at-least-once) | `1` = retained |

---

### PUBACK Packet (Frame 9)

Tiny MQTT acknowledgement — only 4 bytes total. Raw hex:

```
40 02 00 01
```

| Field | Offset | Raw Hex | Decoded Value |
|-------|--------|---------|---------------|
| Fixed header | 0 | `40` | Type = PUBACK (`0100 0000`) |
| Remaining length | 1 | `02` | 2 bytes |
| Packet Identifier | 2–3 | `00 01` | 1 |

**Packet Identifier match:** PUBLISH PKT ID = **1** ; PUBACK PKT ID = **1** ; **Match? ✅ YES**

This is the at-least-once guarantee in action: the publisher will not consider its message delivered until it sees this PUBACK carrying the same Packet Identifier. If the PUBACK is lost (e.g., network drop), paho will retransmit the PUBLISH with the DUP flag set.

---

## 4.3 CoAP Packet Annotations

All values below come from **`captures/coap.pcap`**.

### CON GET Request (Frame 1)

UDP payload (43 bytes). Raw hex:

```
42 01 EF 66 06 DA 39 6C 6F 63 61 6C 68 6F 73 74
30 57 66 61 63 74 6F 72 79 05 6C 69 6E 65 32 0B
74 65 6D 70 65 72 61 74 75 72 65
```

Structure annotated:

```
42  01  EF 66   06 DA   39 6C..74   30   57 66..79   05 6C..32   0B 74..65
[H] [C] [ MID ] [Token] [Uri-Host  ][Obs][Uri-Path][Uri-Path  ][Uri-Path ]
```

| Field | Bits/Bytes | Raw Value | Decoded Value |
|-------|-----------|-----------|---------------|
| Version (bits 7–6) | 2 bits | `01` | 1 (always 1) |
| Type (bits 5–4) | 2 bits | `00` | 0 = CON (Confirmable) |
| TKL (bits 3–0) | 4 bits | `0010` | Token length = 2 |
| Code (byte 1) | 8 bits | `01` | 0.01 = GET |
| Message ID (bytes 2–3) | 16 bits | `EF 66` | 61286 |
| Token (bytes 4–5) | 2 bytes | `06 DA` | 0x06DA |
| Option #1 header | 1 byte | `39` | Delta = 3, Length = 9 → Option 3 = **Uri-Host** |
| Option #1 value | 9 bytes | `6C 6F 63 61 6C 68 6F 73 74` | "localhost" |
| Option #2 header | 1 byte | `30` | Delta = 3, Length = 0 → Option 6 = **Observe** |
| Option #2 value | 0 bytes | _(none)_ | Observe = 0 → **Register subscription** |
| Option #3 header | 1 byte | `57` | Delta = 5, Length = 7 → Option 11 = **Uri-Path** |
| Option #3 value | 7 bytes | `66 61 63 74 6F 72 79` | "factory" |
| Option #4 header | 1 byte | `05` | Delta = 0 (same option), Length = 5 |
| Option #4 value | 5 bytes | `6C 69 6E 65 32` | "line2" |
| Option #5 header | 1 byte | `0B` | Delta = 0 (same option), Length = 11 |
| Option #5 value | 11 bytes | `74 65 6D 70 65 72 61 74 75 72 65` | "temperature" |

**Byte 0 full expansion** (`0x42` = `0100 0010`):

| Bit 7 | Bit 6 | Bit 5 | Bit 4 | Bit 3 | Bit 2 | Bit 1 | Bit 0 |
|-------|-------|-------|-------|-------|-------|-------|-------|
| Ver   | Ver   | T     | T     | TKL   | TKL   | TKL   | TKL   |
| `0`   | `1`   | `0`   | `0`   | `0`   | `0`   | `1`   | `0`   |

**Delta encoding observation:** CoAP options are encoded *relative* to the previous option number, so each new option header carries only the *increment* in option number plus the value length. The three consecutive `Uri-Path` options for "factory" → "line2" → "temperature" all share option number 11; the second and third therefore use delta = 0, an extremely compact encoding compared to repeating the full option number each time.

---

### ACK 2.05 Content Response (Frame 2)

CoAP bytes (UDP payload, 82 bytes total). Header section:

```
62 45 EF 66 06 DA 60 61 32 FF { "value": 73.319, "unit": "C", "ts": "..." }
[H][C][ MID ][Token][Obs][CF ][PM][............JSON payload............]
```

| Field | Bytes | Raw Hex | Decoded Value |
|-------|-------|---------|---------------|
| Fixed header byte 0 | 0 | `62` | Ver = 01, T = 10 (ACK), TKL = 2 |
| Code byte 1 | 1 | `45` | 0x45 = (class 2, detail 5) = **2.05 Content** |
| Message ID | 2–3 | `EF 66` | 61286 (matches GET request? **✅ YES**) |
| Token | 4–5 | `06 DA` | 0x06DA (matches GET request? **✅ YES**) |
| Option: Observe | 6 | `60` | Delta = 6, Length = 0 → Option 6 = Observe (empty: server uses MID for ordering on first ACK) |
| Option: Content-Format | 7–8 | `61 32` | Delta = 6, Length = 1 → Option 12 = Content-Format; Value = `0x32` = **50 = application/json** |
| Payload Marker | 9 | `FF` | 0xFF — separates options from payload |
| Payload | 10–81 | `7B 22 76 61 6C 75 65 22 3A 20 37 33 2E 33 31 39 …` | `{"value": 73.319, "unit": "C", "ts": "2026-05-26T11:54:59.835433+00:00"}` |

**Correlation note:** CoAP correlates request and response at **two** levels: MID (Message ID) handles the CON/ACK pairing at transport level (same MID = same hop), and Token handles the logical request/response pairing at application level (survives across observation notifications and Block-wise transfers). Both match perfectly here.

---

### Observe Notification (Frame 5)

A server-pushed update — this is the *second* notification on the line1 temperature observation (token 0x06DB). It arrives ~3.39 s after the initial GET/ACK pair (matches the sensor's 5-second update loop).

CoAP bytes:

```
42 45 3C 65 06 DB 61 01 61 32 FF { "value": 70.597, "unit": "C", "ts": "..." }
```

| Field | Value |
|-------|-------|
| Observe option number | 6 |
| Observe sequence value | **1** (first push after the initial register response which carried seq = 0) |
| Message type | **CON** (Confirmable — aiocoap requests an ACK back from the observer) |
| Response code | **2.05 Content** (`0x45`) |
| Token | `06 DB` (line1 observation; the parallel line2 observation uses `06 DA`) |
| Message ID | 0x3C65 = 15461 |

**Why CON for the notification?** aiocoap defaults to Confirmable observe notifications, meaning the observer must ACK each push. This costs an extra UDP packet per update but guarantees the server learns about silent observers (a missing ACK eventually triggers de-registration per RFC 7641 §3.6). For high-frequency telemetry, switching to NON (Non-Confirmable) would halve the packet count at the cost of silent observation drops going undetected.

---

## 4.4 AMQP Frame Annotations

**Not applicable — AMQP (Task 3) is out of scope for this submission per the assignment instructions ("IGNORE AMQP"). No AMQP capture or annotations were produced.**

---

## Summary of evidence captured

| Evidence | Value | Where it appears |
|---|---|---|
| MQTT persistent session confirmed | Connect Flags bit 1 = 0 | CONNECT byte 9 = `0x2C` |
| MQTT LWT correctly configured | "offline" on `factory/line1/status`, QoS 1, retain | CONNECT trailing bytes |
| MQTT QoS 1 round-trip verified | PUBLISH id=1 ↔ PUBACK id=1 | Frames 8 + 9 |
| Retained message flag observed | PUBLISH byte 0 = `0x33` (RETAIN bit set) | Frame 8 |
| CoAP version, type, TKL extracted from a single byte | `0x42` = Ver 1 + CON + TKL 2 | Frame 1 byte 0 |
| CoAP request/response correlation works at MID + Token | Both match `EF66` / `06DA` | Frames 1 + 2 |
| CoAP option delta-encoding observed | 3 × Uri-Path with deltas 5, 0, 0 | Frame 1 options block |
| CoAP Observe pushes work | seq number 1 received on token `06DB` | Frame 5 |
| Content-Format = 50 (application/json) | Option 12, value `0x32` | Frame 2 |

---

*Module 1 Assignment — Real-Time Data Analytics for IoT*

---

## Appendix A — Test Suite Execution Record

The full pytest output collected on the reference environment (Ubuntu 24.04 WSL2, Python 3.12, paho-mqtt 2.1, aiocoap 0.4.17) is preserved verbatim in [`report/test_results.txt`](test_results.txt). Summary:

- `tests/mqtt/test_publisher.py` — **11 / 11 passed** (publisher persistent session, topic format, per-sensor QoS, LWT, subscriber wildcard, QoS 2 temperature sub, critical alert above threshold, no false alert below, message count tracking)
- `tests/coap/test_server.py` — **10 / 10 passed** (temperature/vibration/power GET on both lines, actuator PUT ON/OFF/invalid, Block2 manifest size + valid JSON, `.well-known/core` discovery)
- `tests/mqtt/test_qos_loss.py` — **1 / 1 passed** (60-second QoS comparison harness; results table reproduced in Section 5.1 of `comparison_report.md`)

**Total: 22 passed, 0 failed.** AMQP tests under `tests/amqp/` were not executed because the corresponding implementation is out of scope per instructor guidance.
