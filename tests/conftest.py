"""pytest configuration and mocks for standalone unit testing."""

import sys
from unittest.mock import MagicMock

# Mock homeassistant and adb_shell modules if not installed in the test environment
MODULES_TO_MOCK = [
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
    "adb_shell",
    "adb_shell.adb_device_async",
    "adb_shell.auth",
    "adb_shell.auth.keygen",
    "adb_shell.auth.sign_pythonrsa",
    "adb_shell.exceptions",
]

from enum import Enum

class DummyMediaPlayerState(str, Enum):
    PLAYING = "playing"
    PAUSED = "paused"
    BUFFERING = "buffering"
    IDLE = "idle"
    OFF = "off"

    def __str__(self) -> str:
        return self.value

class DummyEntity:
    pass

class DummyCoordinatorEntity(DummyEntity):
    def __init__(self, coordinator=None):
        self.coordinator = coordinator

class DummyMediaPlayerEntity(DummyEntity):
    pass

for mod in MODULES_TO_MOCK:
    if mod not in sys.modules:
        try:
            __import__(mod)
        except ImportError:
            sys.modules[mod] = MagicMock()

# Wire mock classes
ha_update_coord = sys.modules.get("homeassistant.helpers.update_coordinator")
if isinstance(ha_update_coord, MagicMock):
    ha_update_coord.CoordinatorEntity = DummyCoordinatorEntity

ha_media_player = sys.modules.get("homeassistant.components.media_player")
if isinstance(ha_media_player, MagicMock):
    ha_media_player.MediaPlayerEntity = DummyMediaPlayerEntity
    ha_media_player.MediaPlayerEntityFeature = MagicMock(side_effect=lambda x: x)
    ha_media_player.MediaPlayerState = DummyMediaPlayerState
