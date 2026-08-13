"""Diagnostics support for ADB Media Session integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.diagnostics import async_redact_data

from .const import DOMAIN
from .coordinator import AdbMediaCoordinator

TO_REDACT = {"private_key", "public_key", "password", "token"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: AdbMediaCoordinator = data["coordinator"]

    coord_data = coordinator.data
    sessions_diag = []
    if coord_data:
        for s in coord_data.sessions:
            sessions_diag.append(
                {
                    "name": s.name,
                    "package": s.package,
                    "active": s.active,
                    "state": str(s.state) if s.state else None,
                    "position_ms": s.position_ms,
                    "updated_ms": s.updated_ms,
                    "speed": s.speed,
                    "error": s.error,
                }
            )

    diagnostics: dict[str, Any] = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "connection": {
            "is_connected": coordinator.client.is_connected,
            "consecutive_failures": coordinator.client.consecutive_failures,
            "host": coordinator.client.host,
            "port": coordinator.client.port,
        },
        "coordinator_data": {
            "uptime_seconds": coord_data.uptime_seconds if coord_data else None,
            "media_button_session_pkg": coord_data.media_button_session_pkg if coord_data else None,
            "primary_session": (
                {
                    "name": coord_data.primary_session.name,
                    "package": coord_data.primary_session.package,
                    "state": str(coord_data.primary_session.state) if coord_data and coord_data.primary_session and coord_data.primary_session.state else None,
                }
                if coord_data and coord_data.primary_session
                else None
            ),
            "sessions": sessions_diag,
        },
    }

    return diagnostics
