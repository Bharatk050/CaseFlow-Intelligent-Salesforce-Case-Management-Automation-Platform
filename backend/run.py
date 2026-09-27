"""Start RQC from any working directory: python <path-to-backend>/run.py."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import socket
import ssl
import sys
from urllib.request import urlopen

BACKEND = Path(__file__).resolve().parent
PROJECT = BACKEND.parent


def create_event_loop() -> asyncio.AbstractEventLoop:
    # The Windows Proactor transport can raise WinError 10054 during socket
    # shutdown after browser disconnects. This single-process HTTP server uses
    # no asyncio subprocesses, so the selector loop is sufficient.
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop()
    return asyncio.new_event_loop()


def existing_server(port: int, certificate: Path) -> bool:
    context = ssl.create_default_context(cafile=str(certificate))
    try:
        with urlopen(f"https://localhost:{port}/openapi.json", context=context, timeout=3) as response:
            schema = json.load(response)
        return schema.get("info", {}).get("title") == "Support Triage API"
    except (OSError, ValueError):
        return False


def occupied(port: int) -> bool:
    for host in ("127.0.0.1", "::1"):
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            pass
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local RQC HTTPS backend.")
    parser.add_argument("--port", type=int, default=8012)
    parser.add_argument("--check", action="store_true", help="Validate imports and TLS files without starting a server.")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")

    cert = BACKEND / ".certs" / "localhost-cert.pem"
    key = BACKEND / ".certs" / "localhost-key.pem"
    if not cert.is_file() or not key.is_file():
        print("Missing localhost TLS files in backend/.certs. Restore the certificate and key before starting.", file=sys.stderr)
        return 1
    try:
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(cert, key)
    except (OSError, ssl.SSLError):
        print("Unable to load the localhost TLS certificate/key pair.", file=sys.stderr)
        return 1

    sys.path.insert(0, str(PROJECT))
    try:
        import uvicorn
        from backend.code.main import app
    except ImportError as error:
        print(f"Backend import failed ({error}). Install dependencies with: python -m pip install -r \"{BACKEND / 'requirements.txt'}\"", file=sys.stderr)
        return 1
    if args.check:
        print("Backend imports and TLS certificate/key are valid.")
        return 0
    if occupied(args.port):
        if existing_server(args.port, cert):
            print(f"RQC is already running at https://localhost:{args.port}. No second server was started.")
            return 0
        print(f"Port {args.port} is already in use. Stop its existing server before starting RQC.", file=sys.stderr)
        return 1
    config = uvicorn.Config(app, host="localhost", port=args.port, ssl_keyfile=str(key), ssl_certfile=str(cert), access_log=False)
    server = uvicorn.Server(config)
    try:
        with asyncio.Runner(loop_factory=create_event_loop) as runner:
            runner.run(server.serve())
    except KeyboardInterrupt:
        pass
    except OSError as error:
        print(f"Backend could not start: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
