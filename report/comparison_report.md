# Module 1 Assignment — Protocol Comparison Report

**Student Name:** Mustafa Eren Soyhan
**Student ID:** 101045056
**Date:** 26/05/2026
**Course:** Real-Time Data Analytics for IoT
**Note on scope:** Per instructor guidance, AMQP (Task 3) is excluded from grading. This report covers MQTT (Task 1), CoAP (Task 2), and the comparative analysis based on those two protocols. The AMQP row in Section 5.1 is therefore marked N/A.

---

## 5.1 QoS Comparison Results Table

The table below records measurements taken from `tests/mqtt/test_qos_loss.py` over a 60-second window, with 100 messages sent at each MQTT QoS level. The CoAP rows summarise behaviour observed during the live `src.coap.observer` run against `src.coap.server` (no failure simulation was applied; values describe normal-condition delivery).

| Protocol / QoS | Sent | Received | Lost (%) | Duplicates | Avg Latency (ms) |
|----------------|------|----------|----------|------------|------------------|
| MQTT QoS 0 | 100 | 100 | 0.0% | 0 | 0.6 |
| MQTT QoS 1 | 100 | 100 | 0.0% | 0 | 0.7 |
| MQTT QoS 2 | 100 | 100 | 0.0% | 0 | 1.6 |
| CoAP NON | n/a (server uses CON for Observe) | — | — | — | — |
| CoAP CON | 26 notifications | 26 | 0.0% | 0 (no stale notifications detected by RFC 7641 §3.4 freshness check) | < 5 ms |
| AMQP (confirms off) | N/A — out of scope | N/A | N/A | N/A | N/A |

**Note on environment:** all tests were executed over Linux loopback (`lo`) on Ubuntu 24.04 inside WSL2. Kernel-internal loopback delivery is effectively lossless, so all three MQTT QoS levels recorded 0% loss. The meaningful empirical signal is therefore the **latency trend**: 0.6 ms (QoS 0) → 0.7 ms (QoS 1) → 1.6 ms (QoS 2). The ~2.5× jump at QoS 2 is consistent with the 4-step PUBLISH → PUBREC → PUBREL → PUBCOMP handshake (vs. PUBLISH + PUBACK for QoS 1, vs. fire-and-forget for QoS 0). Under a real network with non-zero loss, QoS 1 and QoS 2 would also distinguish themselves on `Lost (%)` and `Duplicates` — QoS 1 may produce duplicates due to retransmission, while QoS 2 guarantees exactly-once.

For CoAP, all 26 server-pushed Observe notifications were received and applied in correct sequence order; no stale notifications were flagged. This is again expected on loopback, but confirms that the freshness logic implemented in `src/coap/observer.py` (RFC 7641 §3.4 wrap-around comparison) executes without false positives.

---

## 5.1.1 CoAP Reliability Under Simulated Loss

The clean-loopback table above measures delivery, not resilience. To compare the reliability of **CoAP CON** (confirmable, retransmitted on missing ACK) against **CoAP NON** (fire-and-forget), `scripts/coap_loss_experiment.py` sends 100 GET requests of each type to `/factory/line1/power` with a 10% per-attempt drop probability injected in the client; CON requests get up to 3 retransmission attempts, NON gets one. Loss was injected in-process because `sudo tc qdisc add dev lo root netem loss 10%` was verified to have no effect on the WSL2 loopback interface.

| Protocol | Sent | Received | Lost (%) | Avg Latency (ms) |
|----------|------|----------|----------|------------------|
| CoAP NON | 100  | 87       | 13.0%    | 1.7              |
| CoAP CON | 100  | 100      | 0.0%     | 1.8              |

The 13% NON loss tracks the 10% injection rate within expected statistical noise for N=100. The CoAP CON row demonstrates the value of confirmable messaging directly: although CON faced the *same* 10% drop probability, every message was eventually received because each dropped attempt triggered a retransmission — with three retries available, the probability of total loss is ≈ 0.10³ = 0.001, so 0/100 is consistent with theory. Latencies are statistically indistinguishable because, for messages that arrived on the first attempt, both types incur identical round-trip costs; CON only pays its retransmission cost on the actual drops.

---

## 5.2 CoAP–HTTP Proxy Mapping

The course's `test_proxy.py` was not bundled in the provided starter kit, so a live CoAP→HTTP proxy run was not performed. The table below documents the mappings prescribed by **RFC 8075 (Guidelines for Mapping Implementations: HTTP to the Constrained Application Protocol)**, with "Observed Value" filled in based on the actual headers a proxy in front of our CoAP server (`src.coap.server`) would emit for a GET on `/factory/line1/temperature`. Our server's responses carry Content-Format 50 (application/json) and no Max-Age or ETag options, which determines several of the columns below.

| HTTP Header | CoAP Option | Observed Value |
|---|---|---|
| `Content-Type` | Content-Format (Option 12) | `application/json` (CoAP option value `0x32` = 50) |
| `Cache-Control: max-age` | Max-Age (Option 14) | Not set by our server → proxy would emit the CoAP default of `max-age=60` (RFC 7252 §5.10.5) |
| `ETag` | ETag (Option 4) | Not set — our resources are observable and update every 5 s, so ETag caching is intentionally avoided |
| `Location` | Location-Path (Option 8) + Location-Query (Option 20) | Not used for GET responses (these options apply to 2.01 Created responses from POST/PUT) |

**Why the proxy mapping matters:** CoAP options are numerically identified and binary-encoded for size; HTTP headers are textual and ASCII. The proxy translates representations bidirectionally but preserves semantics. Content-Format `50` is a single numeric token on the CoAP side compared with the ~16-byte ASCII string `application/json` on the HTTP side — a vivid example of why CoAP is preferred over constrained links. Conversely, Max-Age has a meaningful default (60 s) in CoAP that the proxy must surface explicitly as `Cache-Control: max-age=60` in HTTP, otherwise an HTTP/1.1 client would treat the response as non-cacheable.

---

## 5.3 Protocol Selection Recommendation

The four data paths below cover the bulk of the SmartFactory's communication needs. Each recommendation cites the specific empirical evidence collected during this assignment.

### Data path 1 — Sensor → Cloud (high frequency, <100 ms latency)

**Recommendation: MQTT, predominantly at QoS 0, with QoS 1 reserved for status topics.**

The MQTT broker model decouples N producers (sensors) from M consumers (cloud ingestors, dashboards, archival writers). A new consumer joins by subscribing — no sensor reconfiguration required. From our measurements, MQTT QoS 0 round-trip latency was **0.6 ms** on loopback; even adding two orders of magnitude for real WAN conditions still keeps a healthy budget under the 100 ms requirement. Telemetry that is sampled at 1 Hz tolerates occasional QoS-0 loss without consequence, since the *next* reading is already on its way 1 s later — there is no information value in retransmitting a stale reading. The wildcard topic structure observed in our capture (`factory/+/temperature`, `factory/#`) lets consumers tap arbitrary slices of the data stream without breaking the publisher. Retained messages, demonstrated by our retained `online`/`offline` status PUBLISHes (frame 8, byte 0 = `0x33`, retain bit set), give late-joining consumers an immediate snapshot of every line's state.

### Data path 2 — Actuator commands (safety-critical, exactly-once)

**Recommendation: CoAP CON with idempotent PUT, or MQTT QoS 2.**

Actuator commands have very different reliability requirements from telemetry: a missed "open valve" command can damage equipment, and a duplicated "open valve" command can do the same. Either of two protocol patterns delivers exactly-once semantics. The first, demonstrated in our `src/coap/server.py::ActuatorResource`, is a CoAP CON PUT to `/actuator/line1/fan` with payload `{"state":"ON"}`. The server returns 2.04 Changed on success and 4.00 Bad Request for any invalid input; idempotency means an accidentally retransmitted PUT produces no extra state change. Our tests confirmed this for both ON and OFF transitions (see `test_put_actuator_on` / `test_put_actuator_off` in `tests/coap/test_server.py`, both passing). The second option, MQTT QoS 2, uses the four-message handshake (PUBLISH → PUBREC → PUBREL → PUBCOMP) to guarantee exactly-once. Our latency measurements put QoS 2 at 1.6 ms — over twice QoS 0 but still well under any safety-relevant deadline. For a small command surface (one fan per line), CoAP PUT is the simpler choice because the request/response round-trip is naturally exposed and uniformly addressable.

### Data path 3 — Backend service-to-service routing

**Recommendation: AMQP would be the natural fit, but is out of scope here. Of the protocols implemented, MQTT with topic-based segregation is the workable alternative.**

This is the data path where AMQP exchange-based routing would normally win — fanout, header-based routing, and dead-letter queues are first-class concepts. Within the MQTT-only scope of this assignment, the same outcome can be approximated by careful topic hierarchy: `factory/{line}/{sensor}` for raw telemetry, `factory/{line}/{sensor}/critical` for alert-tagged versions, and dedicated consumer groups via session persistence (`clean_session=False`, verified at byte offset 9 of our CONNECT packet, flag value `0x2C`). For SmartFactory at its current scale (two lines, six sensors), MQTT topic routing is sufficient. If the routing rules grow — for example, separate persistence tiers for different sensor types, or multi-stage transformation pipelines — migrating that path to AMQP would be the next step.

### Data path 4 — OTA firmware delivery to constrained MCU (Class 2)

**Recommendation: CoAP with Block2 transfer.**

This is the strongest case for CoAP in the entire factory. Class 2 devices (per RFC 7228) have ≤50 KB RAM and ≤250 KB flash; they cannot afford TCP, TLS, or string-heavy headers. CoAP runs over UDP, has 4-byte fixed headers, and uses binary option codes with delta-encoded option numbers — our CON GET request (frame 1 of `coap.pcap`) used delta encoding on three consecutive Uri-Path options (deltas 5, 0, 0) to compress `/factory/line2/temperature` into roughly 30 bytes of options. For payloads exceeding the UDP MTU, CoAP's Block2 fragments the response into numbered chunks. The observer's manifest fetch produced exactly this behaviour: a 16,854-byte JSON manifest reassembled from 17 Block2 chunks of 1024 bytes each, with the final block carrying `more=0` to signal end-of-transfer. The constrained device only ever holds one block in memory at a time and writes each block to flash as it arrives. MQTT cannot do this — its model is "one message, one payload," and a 16 KB MQTT message would not fit on a Class 2 device.

---

## 5.4 Reflection

### One technical challenge encountered

The biggest single time sink was a **pytest-asyncio fixture scope mismatch** during Task 2 testing. The starter kit declared `coap_server` as a `module`-scoped async fixture (so one CoAP server serves all 10 tests), but pytest-asyncio 1.4 defaults to `function`-scoped event loops — meaning each test ran in a fresh loop while the server was bound to the module-creation loop. Every test failed with `aiocoap.error.LibraryShutdown` because aiocoap saw its loop as already closed. The fix turned out to be two lines in `pytest.ini` — `asyncio_default_fixture_loop_scope = module` and `asyncio_default_test_loop_scope = module` — but identifying that this was the cause (versus a bug in my server code) required reading both the pytest-asyncio changelog and the aiocoap protocol module to confirm the loop binding. The lesson: when async tests fail in puzzling ways, suspect the test-harness configuration before suspecting the code under test.

### Most surprising observation from packet capture

Two surprises tied for first place. The first: **how much TCP costs MQTT compared with how little UDP costs CoAP**. The MQTT CONNECT packet in my capture was 137 bytes on the wire (frame 4), of which only **71 bytes** were actual MQTT — the rest were Ethernet/IP/TCP framing including the 3-way handshake that had to complete before MQTT could even open. The CoAP CON GET (frame 1) was 85 bytes total, of which **43 bytes** were CoAP. For long-lived publishers this overhead amortises to nothing, but for an MCU that wakes up to send a single reading then sleeps, the TCP setup cost is a significant fraction of the energy budget.

The second surprise was **how compact CoAP option delta encoding is**. Three consecutive `Uri-Path` options for `/factory/line2/temperature` were encoded as three header bytes (`57`, `05`, `0B`) plus the three string segments — total option overhead about 3 bytes for what HTTP would have spent a multi-byte header name plus delimiter on. This is exactly the kind of micro-optimisation that explains CoAP's existence: every byte saved is energy not spent transmitting it.

### Most complex protocol to implement correctly

**CoAP**, by a wide margin. MQTT publish/subscribe is straightforward — connect, publish, subscribe, handle messages, done. The MQTT 5.0 spec adds complexity but the 3.1.1 surface we used is small. CoAP looks deceptively similar to HTTP from a distance but is significantly harder once you actually implement it. Three things in particular: (1) **Asynchronous resource updates** required scheduling a per-resource background task (`asyncio.ensure_future(self._update_loop())`) inside the resource's `__init__`, which only works because aiocoap creates resources inside an already-running event loop — a subtle dependency. (2) **Observable notifications** required calling `self.updated_state()` after every reading change, and *then* understanding that aiocoap defaults to CON notifications, which means the observer must ACK each one or eventually get unsubscribed. (3) **RFC 7641 §3.4 freshness checking** requires comparing observe sequence numbers across a 24-bit wrap window — `(last < new AND new - last < 2^23) OR (last > new AND last - new > 2^23)` — which is not obvious from a casual read of the spec. Getting all three of these right took longer than implementing the entire MQTT publisher + subscriber combined.

---

*Module 1 Assignment — Real-Time Data Analytics for IoT*
