"""Parser for dumpsys media_session output and proc uptime."""

from __future__ import annotations

from dataclasses import dataclass, field
import re


from enum import Enum

class MediaPlayerState(str, Enum):
    """Media player states compatible with Home Assistant MediaPlayerState."""
    PLAYING = "playing"
    PAUSED = "paused"
    BUFFERING = "buffering"
    IDLE = "idle"
    OFF = "off"

    def __str__(self) -> str:
        return self.value


_ANDROID_STATE_MAP: dict[int | str, MediaPlayerState] = {
    3: MediaPlayerState.PLAYING,
    4: MediaPlayerState.PLAYING,
    5: MediaPlayerState.PLAYING,
    2: MediaPlayerState.PAUSED,
    6: MediaPlayerState.BUFFERING,
    "PLAYING": MediaPlayerState.PLAYING,
    "FAST_FORWARDING": MediaPlayerState.PLAYING,
    "REWINDING": MediaPlayerState.PLAYING,
    "PAUSED": MediaPlayerState.PAUSED,
    "BUFFERING": MediaPlayerState.BUFFERING,
}


@dataclass(frozen=True)
class MediaSession:
    """Dataclass representing a parsed Android media session."""
    name: str
    package: str | None
    active: bool
    state: MediaPlayerState
    position_ms: int | None
    updated_ms: int | None
    speed: float | None
    error: str | None

    def calculate_current_position(self, uptime_seconds: float | None) -> float | None:
        """Calculate the corrected current position in seconds."""
        if self.position_ms is None:
            return None

        reported_sec = self.position_ms / 1000.0

        if (
            self.state == MediaPlayerState.PLAYING
            and uptime_seconds is not None
            and self.updated_ms is not None
            and uptime_seconds > 0
        ):
            updated_sec = self.updated_ms / 1000.0
            elapsed_sec = uptime_seconds - updated_sec
            if elapsed_sec > 0:
                speed = self.speed if self.speed is not None else 1.0
                return max(0.0, reported_sec + (elapsed_sec * speed))

        return max(0.0, reported_sec)


@dataclass
class ParsedMediaSessionData:
    """Dataclass holding all parsed media session output."""
    uptime_seconds: float | None
    media_button_session_pkg: str | None
    sessions: list[MediaSession] = field(default_factory=list)
    primary_session: MediaSession | None = None


def parse_playback_state(val: str | int | None) -> MediaPlayerState:
    """Parse raw Android dumpsys state into Home Assistant MediaPlayerState."""
    if val is None:
        return MediaPlayerState.IDLE

    if isinstance(val, int):
        return _ANDROID_STATE_MAP.get(val, MediaPlayerState.IDLE)

    val_str = str(val).strip().upper()
    if val_str.isdigit():
        return _ANDROID_STATE_MAP.get(int(val_str), MediaPlayerState.IDLE)

    return _ANDROID_STATE_MAP.get(val_str, MediaPlayerState.IDLE)


def parse_media_session_output(output: str) -> ParsedMediaSessionData:
    """Parse combined output of 'cat /proc/uptime; dumpsys media_session'."""
    uptime_seconds: float | None = None
    media_button_pkg: str | None = None
    sessions: list[MediaSession] = []

    lines = output.splitlines()
    remaining_lines = list(lines)

    # 1. Parse uptime from proc uptime line
    if remaining_lines:
        first_line = remaining_lines[0].strip()
        uptime_match = re.match(r"^(\d+(?:\.\d+)?)\s+\d+(?:\.\d+)?", first_line)
        if uptime_match:
            uptime_seconds = float(uptime_match.group(1))
            remaining_lines.pop(0)

    full_text = "\n".join(remaining_lines)

    # 2. Parse media button session
    btn_match = re.search(
        r"Media button session is\s+(?:SessionToken\s*\{[^}]*pkg=([^\s,}]+)|([a-zA-Z0-9._]+))",
        full_text,
    )
    if btn_match:
        pkg = btn_match.group(1) or btn_match.group(2)
        if pkg and pkg.lower() != "null":
            media_button_pkg = pkg

    # 3. Parse individual media session blocks
    # Blocks in dumpsys media_session usually start with "Session " or "SessionToken " or indent level
    session_blocks = re.split(r"\n(?=\s*(?:Sessions Stack:|SessionToken\s*\{|Session\s+))", full_text)

    for block in session_blocks:
        parsed_session = _parse_session_block(block)
        if parsed_session:
            sessions.append(parsed_session)

    # If splitting by header didn't catch sessions, try splitting by package/active lines
    if not sessions:
        # Fallback block parsing by package / Name presence
        alt_blocks = re.split(r"\n(?=\s*(?:package=|Name=))", full_text)
        for block in alt_blocks:
            parsed_session = _parse_session_block(block)
            if parsed_session:
                sessions.append(parsed_session)

    # Deduplicate sessions by package & name if necessary
    unique_sessions: list[MediaSession] = []
    seen = set()
    for s in sessions:
        key = (s.package, s.name)
        if key not in seen:
            seen.add(key)
            unique_sessions.append(s)

    primary = select_primary_session(unique_sessions, media_button_pkg)

    return ParsedMediaSessionData(
        uptime_seconds=uptime_seconds,
        media_button_session_pkg=media_button_pkg,
        sessions=unique_sessions,
        primary_session=primary,
    )


def format_package_name(package: str) -> str:
    """Format package name into clean human-readable title dynamically."""
    parts = package.split(".")
    ignore_tlds = {"com", "org", "net", "de", "tv", "io", "co", "uk", "app"}
    meaningful = [p for p in parts if p.lower() not in ignore_tlds]
    if not meaningful:
        meaningful = parts

    filtered = []
    for i, p in enumerate(meaningful):
        if i < len(meaningful) - 1 and meaningful[i + 1].lower().startswith(p.lower()):
            continue
        filtered.append(p)

    ignore_words = {"ninja", "stable", "beta", "livingroom", "android", "androidtv"}
    result = []
    for p in filtered:
        p_lower = p.lower()
        if p_lower in ignore_words:
            continue
        if p_lower.endswith("plus") and len(p_lower) > 4:
            result.append(f"{p_lower[:-4].title()}+")
        else:
            result.append(p.title())

    return " ".join(result) if result else package.title()


def clean_session_tag(tag: str | None, package: str) -> str:
    """Dynamically extract and format human-readable app name from session tag or package."""
    if tag:
        tag = tag.strip()
        if tag.lower().startswith("media button session") or tag.lower().startswith("volume key") or tag.lower().startswith("media key"):
            tag = None
        else:
            for suffix in (" media session", " mediasession", " MediaSession", "MediaBrowserService", " Session"):
                if tag.lower().endswith(suffix.lower()) and len(tag) > len(suffix):
                    tag = tag[:-len(suffix)].strip()
                    break

            words = tag.split()
            if len(words) > 1 and words[1].lower().startswith(words[0].lower()):
                tag = words[1]

            if not ("." in tag or tag.startswith("com.") or tag.startswith("org.") or tag.startswith("tv.")):
                if tag.lower().endswith("plus") and len(tag) > 4:
                    return f"{tag[:-4].capitalize()}+"
                return tag

    return format_package_name(package)


def _parse_session_block(block: str) -> MediaSession | None:
    """Parse a single session block text."""
    header_match = re.search(r"^\s*([^\n:]+?)\s+([a-zA-Z0-9._]+)/[^\n(]+\(userId=\d+\)", block, re.MULTILINE)
    if header_match:
        cand_tag = header_match.group(1).strip()
        if not (cand_tag.lower().startswith("media button session") or cand_tag.lower().startswith("volume key")):
            tag = cand_tag
            package = header_match.group(2).strip()
        else:
            tag = None
            pkg_match = re.search(r"(?:package=|pkg=)([a-zA-Z0-9._]+)", block)
            if not pkg_match:
                return None
            package = pkg_match.group(1)
    else:
        pkg_match = re.search(r"(?:package=|pkg=)([a-zA-Z0-9._]+)", block)
        if not pkg_match:
            return None
        package = pkg_match.group(1)
        tag = None

        name_match = re.search(r"Name=([^\n,]+)", block)
        if name_match:
            tag = name_match.group(1).strip()

    # Find active status
    active_match = re.search(r"active=(true|false)", block, re.IGNORECASE)
    active = active_match.group(1).lower() == "true" if active_match else False

    name = clean_session_tag(tag, package)

    # Find state block
    # e.g., state=PlaybackState {state=3, position=107708, speed=1.0, updated=123400000, error=...}
    # or state=PAUSED, position=107708
    state: PlaybackState | None = None
    position_ms: int | None = None
    updated_ms: int | None = None
    speed: float | None = None
    error: str | None = None

    state_block_match = re.search(r"PlaybackState\s*\{([^}]+)\}", block)
    if state_block_match:
        content = state_block_match.group(1)

        # Parse state inside PlaybackState
        st_match = re.search(r"state=(\d+|[A-Z_]+)", content)
        if st_match:
            state = parse_playback_state(st_match.group(1))

        # Parse position
        pos_match = re.search(r"position=(-?\d+)", content)
        if pos_match:
            position_ms = int(pos_match.group(1))

        # Parse updated timestamp
        upd_match = re.search(r"updated=(\d+)", content)
        if upd_match:
            updated_ms = int(upd_match.group(1))

        # Parse speed
        sp_match = re.search(r"speed=([\d.]+)", content)
        if sp_match:
            speed = float(sp_match.group(1))

        # Parse error
        err_match = re.search(r"error=([^\n,}]+)", content)
        if err_match:
            err_str = err_match.group(1).strip()
            if err_str and err_str.lower() != "null" and err_str != "0":
                error = err_str

    else:
        # Loose search in block
        st_match = re.search(r"state=(\d+|[A-Z_]+)", block)
        if st_match:
            state = parse_playback_state(st_match.group(1))

        pos_match = re.search(r"position=(-?\d+)", block)
        if pos_match:
            position_ms = int(pos_match.group(1))

        upd_match = re.search(r"updated=(\d+)", block)
        if upd_match:
            updated_ms = int(upd_match.group(1))

        sp_match = re.search(r"speed=([\d.]+)", block)
        if sp_match:
            speed = float(sp_match.group(1))

        err_match = re.search(r"error=([^\n,}]+)", block)
        if err_match:
            err_str = err_match.group(1).strip()
            if err_str and err_str.lower() != "null" and err_str != "0":
                error = err_str

    # Ensure block contains real session fields and isn't just a header line
    if state is None and position_ms is None and not name_match and "PlaybackState" not in block:
        return None

    return MediaSession(
        name=name,
        package=package,
        active=active,
        state=state,
        position_ms=position_ms,
        updated_ms=updated_ms,
        speed=speed,
        error=error,
    )



def select_primary_session(
    sessions: list[MediaSession],
    media_button_pkg: str | None,
) -> MediaSession | None:
    """Select primary media session according to strict priority rules.

    Priority:
    1. Session matching media_button_pkg
    2. Active session in PLAYING state
    3. Active session in BUFFERING state
    4. Active session in PAUSED state
    5. Any other active session
    6. No session -> None
    """
    if not sessions:
        return None

    # Filter out inactive error-only sessions (e.g. disconnected Bluetooth)
    valid_sessions = [
        s for s in sessions
        if not (s.state == MediaPlayerState.IDLE and s.error is not None)
    ]

    # Priority 1: Session matching media_button_pkg
    if media_button_pkg:
        for s in valid_sessions:
            if s.package == media_button_pkg:
                return s

    # Priority 2: Session in PLAYING state
    for s in valid_sessions:
        if s.state == MediaPlayerState.PLAYING:
            return s

    # Priority 3: Session in BUFFERING state
    for s in valid_sessions:
        if s.state == MediaPlayerState.BUFFERING:
            return s

    # Priority 4: Session in PAUSED state
    for s in valid_sessions:
        if s.state == MediaPlayerState.PAUSED:
            return s

    # Priority 5: Any non-error session
    if valid_sessions:
        return valid_sessions[0]

    return None
