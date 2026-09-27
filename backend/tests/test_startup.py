"""Exercise the real launcher with isolated local server processes."""
import json
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "backend" / "run.py"


def test_launcher_configuration_from_backend_directory():
    result = subprocess.run([sys.executable, str(LAUNCHER), "--check"], cwd=ROOT / "backend", capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "TLS certificate/key are valid" in result.stdout


def test_launcher_serves_https_and_second_launch_reuses_it():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    process = subprocess.Popen([sys.executable, str(LAUNCHER), "--port", str(port)], cwd=ROOT / "frontend", stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=flags)
    try:
        context = ssl.create_default_context(cafile=str(ROOT / "backend/.certs/localhost-cert.pem"))
        deadline = time.monotonic() + 20
        while True:
            try:
                with urlopen(f"https://localhost:{port}/health", context=context, timeout=1) as response:
                    assert json.load(response) == {"status": "ok"}
                break
            except OSError:
                assert process.poll() is None, "Test server exited before becoming healthy"
                if time.monotonic() >= deadline:
                    raise AssertionError("Test server did not become healthy")
                time.sleep(.1)
        result = subprocess.run([sys.executable, str(LAUNCHER), "--port", str(port)], cwd=ROOT, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        assert "already running" in result.stdout
        assert "No second server" in result.stdout
    finally:
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
    assert "10048" not in stderr
    assert "10054" not in stderr
