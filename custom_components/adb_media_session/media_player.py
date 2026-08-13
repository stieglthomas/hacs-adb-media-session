"""Media player platform for ADB Media Session integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CONF_NAME, DEFAULT_NAME, DOMAIN
from .coordinator import AdbMediaCoordinator
from .parser import MediaSession

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ADB media player entity from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: AdbMediaCoordinator = data["coordinator"]
    name: str = entry.data.get(CONF_NAME, DEFAULT_NAME)

    async_add_entities([AdbMediaPlayer(coordinator, entry, name)], update_before_add=True)


class AdbMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Read-only Media Player entity for ADB Media Session."""

    _attr_has_entity_name = True
    _attr_supported_features = MediaPlayerEntityFeature(0)

    def __init__(
        self,
        coordinator: AdbMediaCoordinator,
        entry: ConfigEntry,
        name: str,
    ) -> None:
        """Initialize the media player entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_media_player"

    @property
    def _primary_session(self) -> MediaSession | None:
        """Return the primary active session if available."""
        if self.coordinator.data:
            return self.coordinator.data.primary_session
        return None

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current playback state of the primary session."""
        if not self.coordinator.last_update_success or self.coordinator.data is None:
            return None

        session = self._primary_session
        return session.state if session else MediaPlayerState.IDLE

    @property
    def app_id(self) -> str | None:
        """Return the current application package ID."""
        session = self._primary_session
        return session.package if session else None

    @property
    def app_name(self) -> str | None:
        """Return the human-readable application name."""
        session = self._primary_session
        return session.name if session else None

    @property
    def media_position(self) -> float | None:
        """Return the corrected media position in seconds."""
        session = self._primary_session
        if not session or not self.coordinator.data:
            return None

        pos = session.calculate_current_position(self.coordinator.data.uptime_seconds)
        return round(pos, 3) if pos is not None else None

    @property
    def media_position_updated_at(self) -> datetime | None:
        """Return the timestamp when position was updated."""
        session = self._primary_session
        if not session or not self.coordinator.data:
            return None

        uptime = self.coordinator.data.uptime_seconds

        if session.updated_ms is not None and uptime is not None and uptime > 0:
            elapsed_ago_sec = uptime - (session.updated_ms / 1000.0)
            if elapsed_ago_sec >= 0:
                return dt_util.utcnow() - timedelta(seconds=elapsed_ago_sec)

        return dt_util.utcnow()

    @property
    def media_duration(self) -> int | None:
        """Return duration (null for now as per spec)."""
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        session = self._primary_session
        if not session:
            return None

        return {
            "playback_speed": session.speed if session.speed is not None else 1.0,
        }


