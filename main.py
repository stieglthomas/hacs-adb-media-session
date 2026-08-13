"""CLI tool to test direct ADB communication and media session parsing with an Android TV."""

import sys
from unittest.mock import MagicMock

from enum import Enum

class DummyMediaPlayerState(str, Enum):
    PLAYING = "playing"
    PAUSED = "paused"
    BUFFERING = "buffering"
    IDLE = "idle"
    OFF = "off"

    def __str__(self) -> str:
        return self.value

for mod in [
    "homeassistant",
    "homeassistant.components",
    "homeassistant.components.diagnostics",
    "homeassistant.components.media_player",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.data_entry_flow",
    "homeassistant.helpers",
    "homeassistant.helpers.config_validation",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.storage",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.util",
    "homeassistant.util.dt",
]:
    if mod not in sys.modules:
        try:
            __import__(mod)
        except ImportError:
            sys.modules[mod] = MagicMock()

ha_mp = sys.modules.get("homeassistant.components.media_player")
if isinstance(ha_mp, MagicMock):
    ha_mp.MediaPlayerState = DummyMediaPlayerState

import asyncio
import os
import tempfile

from adb_shell.adb_device_async import AdbDeviceTcpAsync
from adb_shell.auth.keygen import keygen
from adb_shell.auth.sign_pythonrsa import PythonRSASigner

from custom_components.adb_media_session.parser import parse_media_session_output


async def run_live_test(host: str, port: int = 5555) -> None:
    """Connect directly to TV via ADB, query media sessions, and display parsed output."""
    print(f"Connecting to ADB device at {host}:{port}...")

    key_path = os.path.abspath(".adbkey")
    if not os.path.exists(key_path):
        print("Generating persistent RSA key pair at .adbkey...")
        keygen(key_path)

    with open(key_path, "r", encoding="utf-8") as f:
        priv = f.read()
    with open(f"{key_path}.pub", "r", encoding="utf-8") as f:
        pub = f.read()

    signer = PythonRSASigner(pub, priv)
    device = AdbDeviceTcpAsync(host, port, default_transport_timeout_s=10)

    try:
        await device.connect(rsa_keys=[signer], auth_timeout_s=10)
        print("Successfully connected and authorized!")
        print("Fetching uptime and media_session dumpsys...\n")

        output = await device.shell("cat /proc/uptime; dumpsys media_session")
        if not output:
            print("Error: Received empty response from device.")
            return

        parsed = parse_media_session_output(output)

        print("==================== PARSED STATUS ====================")
        print(f"System Uptime:         {parsed.uptime_seconds:.2f} seconds")
        print(f"Media Button Package:  {parsed.media_button_session_pkg}")
        print(f"Total Media Sessions:  {len(parsed.sessions)}")

        primary = parsed.primary_session
        if primary:
            cur_pos = primary.calculate_current_position(parsed.uptime_seconds)
            print("\n--- Primary Active Session ---")
            print(f"  Title/Name:   {primary.name}")
            print(f"  Package:      {primary.package}")
            print(f"  State:        {primary.state}")
            print(f"  Position:     {cur_pos:.2f}s")
            print(f"  Speed:        {primary.speed}")
        else:
            print("\n--- Primary Active Session ---")
            print("  None (TV is idle or no active session found)")

        print("\n--- All Discovered Sessions ---")
        for i, s in enumerate(parsed.sessions, 1):
            err_info = f" (Error: {s.error})" if s.error else ""
            print(f"  {i}. [{s.state}] {s.package}{err_info}")
        print("=======================================================")

    except Exception as err:
        print(f"\nConnection or command failed: {err}")
        print("Make sure Network ADB is enabled on the TV and check for an authorization popup on your TV screen.")
    finally:
        await device.close()


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage:   uv run python main.py <TV_IP_ADDRESS> [PORT]")
        print("Example: uv run python main.py 192.168.1.50")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5555
    asyncio.run(run_live_test(host, port))


if __name__ == "__main__":
    main()
