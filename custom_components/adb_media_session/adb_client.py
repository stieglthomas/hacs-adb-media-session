"""Pure-Python ADB Client for ADB Media Session integration."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from typing import Any

from adb_shell.adb_device_async import AdbDeviceTcpAsync
from adb_shell.auth.keygen import keygen
from adb_shell.auth.sign_pythonrsa import PythonRSASigner
from adb_shell.exceptions import AdbCommandFailureException, DeviceAuthError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import COMMAND_TIMEOUT, MAX_CONSECUTIVE_FAILURES, STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


async def async_get_or_create_rsa_key(hass: HomeAssistant, key_id: str = "global") -> tuple[str, str]:
    """Retrieve or generate an RSA key pair for the integration in HA storage."""
    store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load()

    if data is None or "keys" not in data:
        data = {"version": STORAGE_VERSION, "keys": {}}

    keys = data.get("keys", {})
    if key_id in keys:
        priv = keys[key_id]["private_key"]
        pub = keys[key_id]["public_key"]
        return priv, pub

    # Backward compatibility: reuse first existing key if present
    if keys:
        first_existing_key_id = next(iter(keys))
        priv = keys[first_existing_key_id]["private_key"]
        pub = keys[first_existing_key_id]["public_key"]
        keys[key_id] = {
            "private_key": priv,
            "public_key": pub,
        }
        data["keys"] = keys
        await store.async_save(data)
        return priv, pub

    # Generate new RSA keypair in executor to avoid blocking I/O
    def _generate_keys() -> tuple[str, str]:
        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = os.path.join(tmpdir, "adbkey")
            keygen(key_path)
            with open(key_path, "r", encoding="utf-8") as f:
                priv_key = f.read()
            with open(f"{key_path}.pub", "r", encoding="utf-8") as f:
                pub_key = f.read()
            return priv_key, pub_key

    priv_key, pub_key = await hass.async_add_executor_job(_generate_keys)

    keys[key_id] = {
        "private_key": priv_key,
        "public_key": pub_key,
    }
    data["keys"] = keys
    await store.async_save(data)

    return priv_key, pub_key


async def async_remove_rsa_key(hass: HomeAssistant, key_id: str = "global") -> None:
    """Remove stored RSA key when requested."""
    store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load()
    if data and "keys" in data and key_id in data["keys"]:
        del data["keys"][key_id]
        await store.async_save(data)



class ADBClient:
    """Async ADB Client using adb-shell."""

    def __init__(self, host: str, port: int, priv_key: str, pub_key: str) -> None:
        """Initialize the ADB client."""
        self.host = host
        self.port = port
        self.signer = PythonRSASigner(pub_key, priv_key)
        self._device: AdbDeviceTcpAsync | None = None
        self.is_connected = False
        self.consecutive_failures = 0

    async def connect(self, timeout: float = COMMAND_TIMEOUT) -> None:
        """Connect and authorize ADB TCP session."""
        if self.is_connected and self._device is not None:
            return

        _LOGGER.debug("Connecting to ADB TV at %s:%s", self.host, self.port)
        self._device = AdbDeviceTcpAsync(
            self.host,
            self.port,
            default_transport_timeout_s=timeout,
        )

        try:
            await self._device.connect(
                rsa_keys=[self.signer],
                auth_timeout_s=timeout,
            )
            self.is_connected = True
            self.consecutive_failures = 0
            _LOGGER.info("ADB connection established to %s:%s", self.host, self.port)
        except DeviceAuthError as err:
            self.is_connected = False
            _LOGGER.warning("ADB authentication required or rejected on %s:%s: %s", self.host, self.port, err)
            raise
        except Exception as err:
            self.is_connected = False
            _LOGGER.error("Failed to connect ADB socket to %s:%s: %s", self.host, self.port, err)
            await self.close()
            raise

    async def close(self) -> None:
        """Close the ADB TCP device connection."""
        self.is_connected = False
        if self._device is not None:
            try:
                await self._device.close()
            except Exception as err:
                _LOGGER.debug("Error while closing ADB socket: %s", err)
            finally:
                self._device = None

    async def shell(self, command: str, timeout: float = COMMAND_TIMEOUT) -> str:
        """Execute shell command on the TV."""
        if not self.is_connected or self._device is None:
            await self.connect(timeout=timeout)

        assert self._device is not None

        try:
            output = await self._device.shell(command, timeout_s=timeout)
            self.consecutive_failures = 0
            return output if output is not None else ""
        except Exception as err:
            self.consecutive_failures += 1
            _LOGGER.warning(
                "ADB command '%s' failed (failure count %d/%d): %s",
                command,
                self.consecutive_failures,
                MAX_CONSECUTIVE_FAILURES,
                err,
            )
            if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                _LOGGER.error("Disconnecting ADB due to consecutive failures threshold reached")
                await self.close()
            raise
