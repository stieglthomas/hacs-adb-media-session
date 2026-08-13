"""DataUpdateCoordinator for ADB Media Session integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .adb_client import ADBClient
from .parser import ParsedMediaSessionData, parse_media_session_output

_LOGGER = logging.getLogger(__name__)


class AdbMediaCoordinator(DataUpdateCoordinator[ParsedMediaSessionData]):
    """Coordinator for updating Android TV media session data."""

    def __init__(self, hass: HomeAssistant, client: ADBClient, interval: int) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name="ADB media session",
            update_interval=timedelta(seconds=interval),
        )
        self.client = client

    async def _async_update_data(self) -> ParsedMediaSessionData:
        """Fetch media session and uptime data via ADB shell."""
        try:
            output = await self.client.shell("cat /proc/uptime; dumpsys media_session")
            return parse_media_session_output(output)
        except Exception as err:
            _LOGGER.debug("Data update failed for ADB media session: %s", err)
            raise UpdateFailed(f"Error communicating with Android TV via ADB: {err}") from err
