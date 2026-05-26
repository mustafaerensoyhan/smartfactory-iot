# Module 1 Assignment — Packet Analysis
## Task 4: Wire-Level Protocol Annotation

---

## 4.2 MQTT Packet Annotations

### CONNECT Packet

| Field | Offset (bytes) | Raw Hex | Decoded Value |
|-------|---------------|---------|---------------|
| Frame type + flags (byte 1) | 0 | `__` | Type=CONNECT (____), flags=____ |
| Remaining length (byte 2) | 1 | `__` | ___ bytes |
| Protocol name length | 2–3 | `__ __` | 4 |
| Protocol name | 4–7 | `4D 51 54 54` | "MQTT" |
| Protocol version | 8 | `__` | __ (MQTT ___) |
| Connect flags | 9 | `__` | See breakdown below |
| Keep-alive | 10–11 | `__ __` | ___ seconds |
| Client ID length | 12–13 | `__ __` | ___ |
| Client ID | 14–… | `__ …` | "_______" |

**Connect Flags byte breakdown:**

| Bit | Name | Value | Meaning |
|-----|------|-------|---------|
| 7 | Username flag | __ | ________ |
| 6 | Password flag | __ | ________ |
| 5 | Will retain | __ | ________ |
| 4–3 | Will QoS | __ | ________ |
| 2 | Will flag | __ | ________ |
| 1 | Clean session | __ | ________ |
| 0 | Reserved | 0 | — |

---

### QoS 1 PUBLISH Packet

| Field | Offset (bytes) | Raw Hex | Decoded Value |
|-------|---------------|---------|---------------|
| Fixed header byte 1 | 0 | `__` | Type=PUBLISH(____), DUP=_, QoS=__, RETAIN=_ |
| Remaining length | 1 | `__` | ___ bytes |
| Topic length | 2–3 | `__ __` | ___ |
| Topic string | 4–… | `__ …` | "_______" |
| Packet Identifier | … | `__ __` | ___ |
| Payload | … | `__ …` | "_______" |

**Fixed header byte 1 bit expansion:**

| Bits 7–4 (packet type) | Bit 3 (DUP) | Bits 2–1 (QoS) | Bit 0 (RETAIN) |
|------------------------|-------------|----------------|----------------|
| `____` = PUBLISH (3)  | `_` = ___   | `__` = QoS _   | `_` = ___      |

---

### PUBACK Packet

| Field | Offset | Raw Hex | Decoded Value |
|-------|--------|---------|---------------|
| Fixed header | 0 | `__` | Type=PUBACK (0100) |
| Remaining length | 1 | `02` | 2 bytes |
| Packet Identifier | 2–3 | `__ __` | ___ |

**Packet Identifier match:** PUBLISH PKT ID = ___ ; PUBACK PKT ID = ___ ; **Match? ___**

---

## 4.3 CoAP Packet Annotations

### CON GET Request

```
Bytes: __ __ __ __  __ __ __ __  __ ...
       [   Header   ] [  Token  ] [Options...]
```

| Field | Bits/Bytes | Raw Value | Decoded Value |
|-------|-----------|-----------|---------------|
| Version (bits 7–6) | 2 bits | `__` | __ (always 1) |
| Type (bits 5–4) | 2 bits | `__` | __ = CON |
| TKL (bits 3–0) | 4 bits | `__` | Token length = __ |
| Code (byte 1) | 8 bits | `__` | _.___ = GET |
| Message ID (bytes 2–3) | 16 bits | `__ __` | ___ |
| Token (bytes 4–TKL+3) | TKL bytes | `__ …` | 0x______ |
| Option Delta | 4 bits | `__` | Delta = __, Option# = __ (___) |
| Option Length | 4 bits | `__` | ___ |
| Option Value | ___ bytes | `__ …` | "________" (Uri-Path) |

**Byte 0 full expansion:**

| Bit 7 | Bit 6 | Bit 5 | Bit 4 | Bit 3 | Bit 2 | Bit 1 | Bit 0 |
|-------|-------|-------|-------|-------|-------|-------|-------|
| Ver   | Ver   | T     | T     | TKL   | TKL   | TKL   | TKL   |
| `_`   | `_`   | `_`   | `_`   | `_`   | `_`   | `_`   | `_`   |

---

### ACK 2.05 Content Response

| Field | Bytes | Raw Hex | Decoded Value |
|-------|-------|---------|---------------|
| Fixed header byte 0 | 0 | `__` | Ver=01, T=10 (ACK), TKL=__ |
| Code byte 1 | 1 | `__` | 2.05 = Content |
| Message ID | 2–3 | `__ __` | ___ (matches request? ___) |
| Token | 4–… | `__ …` | 0x______ (matches request? ___) |
| Option: Content-Format | … | `__ __` | Option# = 12, Value = __ (___) |
| Payload Marker | … | `FF` | 0xFF |
| Payload | … | `__ …` | "_______" |

---

### Observe Notification

| Field | Value |
|-------|-------|
| Observe option number | ___ |
| Observe sequence value | ___ |
| Message type | ___ (CON / NON) |
| Response code | ___ |

---

## 4.4 AMQP Frame Annotations

### basic.publish Method Frame

```
Bytes: 01  00 01  00 00 00 NN  [payload]  CE
       [T] [Ch] [Payload Sz] [.........] [End]
```

| Field | Bytes | Raw Hex | Decoded Value |
|-------|-------|---------|---------------|
| Frame Type | 0 | `__` | __ = Method |
| Channel | 1–2 | `__ __` | __ |
| Payload Size | 3–6 | `__ __ __ __` | ___ |
| Class ID | 7–8 | `__ __` | __ = basic (60) |
| Method ID | 9–10 | `__ __` | __ = basic.publish (40) |
| Reserved (ticket) | 11–12 | `00 00` | — |
| Exchange name length | 13 | `__` | __ |
| Exchange name | 14–… | `__ …` | "_______" |
| Routing key length | … | `__` | __ |
| Routing key | … | `__ …` | "_______" |
| Mandatory + Immediate | … | `__` | mandatory=_, immediate=_ |
| Frame End | last | `CE` | 0xCE ✓ |

---

### Content Header Frame

| Field | Bytes | Raw Hex | Decoded Value |
|-------|-------|---------|---------------|
| Frame Type | 0 | `02` | 2 = Header |
| Channel | 1–2 | `__ __` | __ |
| Payload Size | 3–6 | `__ __ __ __` | ___ |
| Class ID | 7–8 | `__ __` | 60 = basic |
| Weight | 9–10 | `00 00` | (unused) |
| Body Size | 11–18 | `__ … __` | ___ bytes |
| Property Flags | 19–20 | `__ __` | bits set: _______________ |
| delivery_mode | … | `__` | __ (1=transient, 2=persistent) |
| content_type length | … | `__` | __ |
| content_type | … | `__ …` | "_______" |
| Frame End | last | `CE` | 0xCE ✓ |

---

### Heartbeat Frame

| Field | Value |
|-------|-------|
| Frame Type | __ |
| Channel | __ |
| Payload Size | __ |
| Payload | _(empty)_ |
| Frame End | `CE` |

**Why is the Heartbeat payload empty?**

> _Your answer here (1–2 sentences)_

---

*Module 1 Assignment — Real-Time Data Analytics for IoT*
