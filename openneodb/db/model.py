from dataclasses import dataclass, field
from enum import IntEnum, IntFlag


class CameraType(IntEnum):
    """Object types recognised by RevM60; see README for the full table."""

    STRELKA = 0x01
    AVERAGE_SPEED_SECTION = 0x04
    STATIONARY_RADAR = 0x06
    POLICE_POST = 0x07
    DUMMY_CAMERA = 0x0B
    STRELKA_NO_RADAR = 0x0C
    AVERAGE_SPEED = 0x4A


class DirectionType(IntEnum):
    """Which traffic directions the camera controls."""

    ALL = 0  # any heading, e.g. circular cameras
    SINGLE = 1  # the heading in CameraRecord.direction
    BOTH = 2  # that heading and the opposite one


class CameraFlags(IntFlag):
    """Known bits of the record flags byte; other bits are kept as is."""

    RADARLESS = 0x02  # correlates with radarless complexes
    # Vendor marks circular cameras with it; RevM60 passes only flags & 0x1F on.
    CIRCULAR = 0x20


MIN_DIRECTION_TYPE = int(min(DirectionType))
MAX_DIRECTION_TYPE = int(max(DirectionType))

FALLBACK_CAMERA_TYPE = CameraType.STATIONARY_RADAR
# Alert distance byte is in decametres. RevM60 reads 0 or >200 as 500 m and
# <10 as 100 m, so representable distances are 100..2000 m.
MIN_ALERT_DISTANCE = 10
MAX_ALERT_DISTANCE = 200


@dataclass(frozen=True)
class CameraRecord:
    camera_type: int
    latitude: int
    longitude: int
    direction: int
    direction_type: int
    speed: int
    latitude2: int = 0
    longitude2: int = 0
    flags: int = 0
    tolerance: int = 0
    distance: int = 0


@dataclass
class ReaderStats:
    read: int = 0
    skipped: int = 0
    fallback: int = 0
    warning_messages: list[str] = field(default_factory=list)

    @property
    def warnings(self) -> int:
        return len(self.warning_messages)

    def warn(self, line_number: int, message: str) -> None:
        self.warning_messages.append(f"line {line_number}: {message}")

    def skip(self, line_number: int, reason: str) -> None:
        self.skipped += 1
        self.warn(line_number, f"{reason}, row skipped")


@dataclass(frozen=True)
class ReadResult:
    records: tuple[CameraRecord, ...]
    stats: ReaderStats
