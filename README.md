# Android TV ADB Media Session

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)

A [Home Assistant](https://www.home-assistant.io/) custom integration for [HACS](https://hacs.xyz/) that tracks active media playback state, app, and position on Android TV, Google TV, and Fire TV devices via pure Python ADB.

## The Problem

Existing Home Assistant solutions for Android TV have notable drawbacks:

- **Android TV Remote Integration**: Relies on the TV's Input Method Editor (IME) service, which can interfere with on-screen keyboard input, does not work reliably across all apps or TV software, and often lacks accurate playback state or position tracking.
- **Standard Android Debug Bridge Integration**: Polling foreground window/app state via ADB is frequently delayed or fails to detect the running media app altogether, while providing no media playback position or reliable playing/paused states for third-party media apps.

## How It Works

1. **ADB Command**: Connects over TCP using pure Python (`adb-shell`) and executes a single shell command per poll interval: `cat /proc/uptime; dumpsys media_session`.
2. **Parse Output**: Reads the raw Android `MediaSession` objects to determine the active app, playback state (`playing`, `paused`, `buffering`, `idle`), and calculates real-time playback position using system uptime.
3. **Read-Only Media Player**: Exposes the parsed status directly as a read-only Home Assistant `media_player` entity.

## Limitations

Since the integration relies on the `dumpsys media_session` shell command, only apps that expose a media session will be detected. This includes most, but not all apps. Not detected media sessions will result in the media player entity being `idle`.

## Installation

### 1. HACS Custom Repository
1. Open **HACS** in Home Assistant.
2. Click the three dots menu in the top-right corner and select **Custom repositories**.
3. Add repository URL `https://github.com/stieglthomas/hacs-adb-media-session` and select category **Integration**.
4. Search for **ADB Media Session** and download it.
5. Restart Home Assistant.

### 2. Integration Setup

> [!NOTE]
> Make sure **Network Debugging / ADB Debugging** is enabled in Developer Options on your TV, that your TV is powered on and connected to the same network as your Home Assistant instance. You can find your TV's IP address in your router's connected devices list or on the TV's network settings page.

1. In Home Assistant, go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **ADB Media Session**.
3. Enter the TV's IP address (default port `5555`).
4. Accept the ADB authorization prompt on your TV screen (check *"Always allow from this computer"*).

## Entity Attributes

Exposes `media_player.adb_media_session`:

- **States**: `playing`, `paused`, `buffering`, `idle`, `off`, `unavailable`
- **Attributes**:
  - `app_id`: Package ID of the active application (e.g. `org.smarttube.stable`, `com.netflix.ninja`)
  - `app_name`: Human-readable name of the active application (e.g. `SmartTube`, `Netflix`)
  - `media_position`: Extrapolated playback position in seconds
  - `media_position_updated_at`: Timestamp when position was last updated
  - `playback_speed`: Playback rate multiplier
