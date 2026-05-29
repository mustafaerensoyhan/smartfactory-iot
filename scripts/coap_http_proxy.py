#!/usr/bin/env python3
"""
coap_http_proxy.py — minimal CoAP→HTTP forward proxy for Section 5.2 evidence.

Stands up an HTTP server on port 8080 that translates each request into a
CoAP GET against the local CoAP server. Used to capture the real HTTP
headers emitted for a CoAP resource (per RFC 8075).

Run:
    # Terminal 1: CoAP server
    python -m src.coap.server

    # Terminal 2: this proxy
    python scripts/coap_http_proxy.py

    # Terminal 3: probe and capture headers
    curl -i http://localhost:8080/factory/line1/temperature
"""
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import aiocoap
from aiocoap import Message, Code


COAP_BASE = "coap://localhost"


class CoAPBridge(BaseHTTPRequestHandler):
    def do_GET(self):
        # Forward the path to the CoAP server
        coap_uri = f"{COAP_BASE}{self.path}"
        try:
            response = asyncio.run(self._coap_get(coap_uri))
        except Exception as e:
            self.send_error(502, f"CoAP error: {e}")
            return

        # Map CoAP response code (2.05 Content -> HTTP 200)
        http_status = 200 if response.code.is_successful() else 500
        self.send_response(http_status)

        # Map CoAP Content-Format (option 12) -> HTTP Content-Type
        if response.opt.content_format == 50:
            self.send_header("Content-Type", "application/json")

        # Map CoAP Max-Age (option 14, default 60) -> HTTP Cache-Control
        max_age = response.opt.max_age if response.opt.max_age is not None else 60
        self.send_header("Cache-Control", f"max-age={max_age}")

        # Map CoAP ETag (option 4) -> HTTP ETag, if present
        if response.opt.etag:
            self.send_header("ETag", response.opt.etag.hex())

        self.send_header("Content-Length", str(len(response.payload)))
        self.end_headers()
        self.wfile.write(response.payload)

    async def _coap_get(self, uri):
        ctx = await aiocoap.Context.create_client_context()
        try:
            resp = await asyncio.wait_for(
                ctx.request(Message(code=Code.GET, uri=uri)).response,
                timeout=2.0,
            )
            return resp
        finally:
            await ctx.shutdown()

    def log_message(self, fmt, *args):
        pass  # silence default access log


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8080), CoAPBridge)
    print("HTTP proxy listening on http://localhost:8080")
    print("Routes each path to coap://localhost{path}")
    print("Stop with Ctrl-C.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nproxy stopped.")
