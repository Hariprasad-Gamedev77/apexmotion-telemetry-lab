"""
config.py — Central configuration for ApexMotion Telemetry Lab
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All thresholds, valid ranges, unit labels and defaults live here.
This makes the rules visible, tunable, and testable in one place.

Nothing in this module reads or modifies data. It only defines
what "valid" means so other modules can reference it.
"""

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Canonical column names
# ---------------------------------------------------------------------------
# These are the internal names used everywhere after loading.
# The loader maps user-provided columns to these names.

CANONICAL_COLUMNS = {
    "time_s": "Time (seconds)",
    "distance_m": "Distance (metres)",
    "speed_kmh": "Speed (km/h)",
    "throttle_pct": "Throttle (%)",
    "brake_pct": "Brake (%)",
}

REQUIRED_COLUMNS = ["time_s", "distance_m", "speed_kmh"]
OPTIONAL_COLUMNS = ["throttle_pct", "brake_pct"]


# ---------------------------------------------------------------------------
# Unit conversion helpers
# ---------------------------------------------------------------------------
# Each entry: (source_unit_label, canonical_unit_label, conversion_function)

UNIT_CONVERSIONS = {
    "speed": {
        "km/h": lambda v: v,            # already canonical
        "m/s": lambda v: v * 3.6,       # m/s → km/h
        "mph": lambda v: v * 1.60934,   # mph → km/h
    },
    "distance": {
        "m":  lambda v: v,              # already canonical
        "km": lambda v: v * 1000.0,     # km → m
        "ft": lambda v: v * 0.3048,     # feet → m
    },
}


# ---------------------------------------------------------------------------
# Valid-range defaults
# ---------------------------------------------------------------------------
# These are *plausible* ranges, not hard physics limits. Values outside
# trigger a WARNING (heuristic suspicion), not an ERROR (definite fault).

@dataclass
class ChannelRange:
    """Defines the plausible range for a telemetry channel."""
    min_val: float
    max_val: float
    unit: str
    description: str


DEFAULT_RANGES: dict[str, ChannelRange] = {
    "speed_kmh": ChannelRange(0.0, 380.0, "km/h",
        "Plausible speed range for circuit racing"),
    "throttle_pct": ChannelRange(0.0, 100.0, "%",
        "Throttle position 0-100%"),
    "brake_pct": ChannelRange(0.0, 100.0, "%",
        "Brake pressure/position 0-100%"),
    "time_s": ChannelRange(0.0, 600.0, "s",
        "Lap time up to 10 minutes"),
    "distance_m": ChannelRange(0.0, 25000.0, "m",
        "Lap distance up to 25 km"),
}


# ---------------------------------------------------------------------------
# Quality-check thresholds
# ---------------------------------------------------------------------------

@dataclass
class QualityThresholds:
    """
    All tuneable thresholds for data-quality rules.

    Each field has a docstring-style comment above it explaining what it
    controls. You can override any of these when creating an instance.
    """

    # Maximum allowed time gap (seconds) between consecutive samples.
    # Gaps larger than this are flagged as "large gap".
    max_time_gap_s: float = 2.0

    # Minimum expected sampling interval (seconds).
    # Intervals much smaller than this suggest duplicate or burst data.
    min_sample_interval_s: float = 0.001

    # Tolerance factor for irregular sampling detection.
    # If an interval differs from the median by more than this factor,
    # it's flagged as irregular. E.g., 3.0 means "3× the median".
    irregular_sampling_factor: float = 3.0

    # Maximum allowed speed change (km/h) between consecutive samples.
    # Larger jumps trigger a WARNING (heuristic, not necessarily wrong).
    max_speed_jump_kmh: float = 80.0

    # Maximum allowed throttle change (%) between consecutive samples.
    max_throttle_jump_pct: float = 60.0

    # Maximum allowed brake change (%) between consecutive samples.
    max_brake_jump_pct: float = 60.0

    # Minimum number of samples required for meaningful analysis.
    min_sample_count: int = 10

    # Custom channel ranges (override defaults)
    channel_ranges: dict[str, ChannelRange] = field(default_factory=dict)

    def get_range(self, channel: str) -> Optional[ChannelRange]:
        """Get the valid range for a channel, preferring custom over default."""
        return self.channel_ranges.get(channel, DEFAULT_RANGES.get(channel))


# ---------------------------------------------------------------------------
# Column-mapping presets
# ---------------------------------------------------------------------------
# Common CSV column names mapped to our canonical names.
# Users can also provide their own mapping.

COMMON_COLUMN_ALIASES = {
    # time
    "time": "time_s",
    "time_s": "time_s",
    "time_sec": "time_s",
    "timestamp": "time_s",
    "t": "time_s",
    "elapsed": "time_s",
    "elapsed_time": "time_s",
    # distance
    "distance": "distance_m",
    "distance_m": "distance_m",
    "dist": "distance_m",
    "lap_distance": "distance_m",
    "lap_dist": "distance_m",
    "dist_m": "distance_m",
    # speed
    "speed": "speed_kmh",
    "speed_kmh": "speed_kmh",
    "speed_kph": "speed_kmh",
    "velocity": "speed_kmh",
    "vcar": "speed_kmh",
    # throttle
    "throttle": "throttle_pct",
    "throttle_pct": "throttle_pct",
    "throttle_pos": "throttle_pct",
    "tps": "throttle_pct",
    # brake
    "brake": "brake_pct",
    "brake_pct": "brake_pct",
    "brake_pos": "brake_pct",
    "brake_pressure": "brake_pct",
}


# ---------------------------------------------------------------------------
# Application metadata
# ---------------------------------------------------------------------------

APP_NAME = "ApexMotion Telemetry Lab"
APP_VERSION = "0.1.0"
DISCLAIMER = (
    "All demo data is synthetic and generated for demonstration purposes. "
    "This application does not use or claim to use real Formula 1 telemetry."
)
