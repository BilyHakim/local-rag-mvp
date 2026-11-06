import asyncio
import importlib.util
import socket
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def launcher():
    spec = importlib.util.spec_from_file_location("instagram_launcher", Path(__file__).resolve().parents[1] / "scripts/run_instagram_prototype.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_occupied_port_exits_before_network_or_config(launcher, monkeypatch, tmp_path):
    executable = tmp_path / "cloudflared.exe"
    executable.touch()
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        monkeypatch.setattr(sys, "argv", ["prototype", "--cloudflared", str(executable), "--media-port", str(port), "--port", str(port + 1 if port < 65535 else port - 1)])
        runner = AsyncMock()
        monkeypatch.setattr(launcher, "run", runner)
        with pytest.raises(SystemExit, match=f"Port {port} tidak tersedia"):
            asyncio.run(launcher.main())
        runner.assert_not_called()


def test_same_ports_rejected_before_network(launcher, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prototype", "--cloudflared", "unused.exe", "--port", "8021", "--media-port", "8021"])
    with pytest.raises(SystemExit, match="must be different"):
        asyncio.run(launcher.main())


def test_missing_cloudflared_exits_before_network(launcher, monkeypatch, tmp_path):
    missing = tmp_path / "missing.exe"
    monkeypatch.setattr(sys, "argv", ["prototype", "--cloudflared", str(missing)])
    runner = AsyncMock()
    monkeypatch.setattr(launcher, "run", runner)
    with pytest.raises(SystemExit, match="cloudflared tidak ditemukan"):
        asyncio.run(launcher.main())
    runner.assert_not_called()
