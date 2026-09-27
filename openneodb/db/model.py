from dataclasses import dataclass, field

FALLBACK_CAMERA_TYPE = 0x06
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
