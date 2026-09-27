from typing import BinaryIO

from ..db import (
    MAX_ALERT_DISTANCE,
    MIN_ALERT_DISTANCE,
    CameraRecord,
    ReaderStats,
    ReadResult,
)
from ..rows import (
    MAX_LATITUDE,
    MAX_LONGITUDE,
    RowError,
    check_range,
    map_camera_type,
    optional_integer,
    parse_coordinate,
    parse_integer,
)


class CityGuideFormatError(ValueError):
    pass


class CityGuideReader:
    HEADER = "2|Radars|1251"
    TYPE_MAPPING = {
        "18059": 0x06,
        "18925": 0x06,
        "18950": 0x4A,
        "18951": 0x06,
        "18952": 0x01,
        "18958": 0x4A,
    }
    # 0 and 1 are both a single controlled direction (likely head-on versus
    # rear shooting); opposite directions are separate rows. 2 is circular.
    DIRECTION_TYPE_MAPPING = {0: 1, 1: 1, 2: 0}

    def read(self, source: BinaryIO) -> ReadResult:
        try:
            text = source.read().decode("cp1251")
        except UnicodeDecodeError as error:
            raise CityGuideFormatError("CityGuide input must use CP1251") from error
        lines = text.splitlines()
        if not lines:
            raise CityGuideFormatError("empty CityGuide input")
        if lines[0] != self.HEADER:
            raise CityGuideFormatError(
                f"invalid CityGuide header {lines[0]!r}, expected {self.HEADER!r}"
            )
        records = []
        stats = ReaderStats()
        for line_number, line in enumerate(lines[1:], start=2):
            if not line.strip():
                continue
            stats.read += 1
            try:
                records.append(self._record(line, line_number, stats))
            except RowError as error:
                stats.skip(line_number, str(error))
        return ReadResult(tuple(records), stats)

    def _record(self, line: str, line_number: int, stats: ReaderStats) -> CameraRecord:
        parts = line.split("|")
        if parts[-1] != "" or len(parts) < 5 or len(parts) % 2 == 0:
            raise RowError("malformed CityGuide row")
        source_type = parts[0].strip()
        if not source_type:
            raise RowError("blank camera type")
        tags = self._tags(parts[4:-1], line_number, stats)
        latitude = parse_coordinate(parts[2].strip(), "latitude", MAX_LATITUDE)
        longitude = parse_coordinate(parts[3].strip(), "longitude", MAX_LONGITUDE)
        speed = self._tag_integer(tags, "1709", 0, line_number, stats)
        check_range(speed, "tag 1709", 0, 255)
        source_direction_type = self._tag_integer(tags, "1713", 0, line_number, stats)
        check_range(source_direction_type, "tag 1713", 0, 2)
        direction = self._direction(tags, line_number, stats)
        distance_metres = self._tag_integer(tags, "1706", 0, line_number, stats)
        if distance_metres < 0:
            raise RowError(f"tag 1706={distance_metres} must not be negative")
        return CameraRecord(
            camera_type=map_camera_type(
                self.TYPE_MAPPING, source_type, "camera type", line_number, stats
            ),
            latitude=latitude,
            longitude=longitude,
            direction=direction,
            direction_type=self.DIRECTION_TYPE_MAPPING[source_direction_type],
            speed=speed,
            flags=0x02 if source_type == "18952" else 0,
            distance=self._distance(distance_metres, line_number, stats),
        )

    @staticmethod
    def _direction(tags: dict[str, str], line_number: int, stats: ReaderStats) -> int:
        value = tags.get("1705", "").strip()
        if not value:
            stats.warn(line_number, "missing tag 1705, using direction 0")
            return 0
        source_direction = parse_integer(value, "tag 1705")
        check_range(source_direction, "tag 1705", 0, 359)
        # Tag 1705 is the camera heading; Neoline stores the traffic heading.
        return (source_direction + 180) % 360

    @staticmethod
    def _distance(metres: int, line_number: int, stats: ReaderStats) -> int:
        distance = metres // 10
        if metres and distance == 0:
            # 0 means the 500 m default, not "closer than 10 m".
            stats.warn(
                line_number,
                f"tag 1706={metres} raised to {MIN_ALERT_DISTANCE * 10} metres",
            )
            return MIN_ALERT_DISTANCE
        if distance > MAX_ALERT_DISTANCE:
            stats.warn(
                line_number,
                f"tag 1706={metres} clamped to {MAX_ALERT_DISTANCE * 10} metres",
            )
            return MAX_ALERT_DISTANCE
        return distance

    @staticmethod
    def _tags(
        fields: list[str], line_number: int, stats: ReaderStats
    ) -> dict[str, str]:
        tags = {}
        for tag, value in zip(fields[0::2], fields[1::2]):
            if tag in tags:
                stats.warn(line_number, f"duplicate tag {tag}, using last value")
            tags[tag] = value
        return tags

    @staticmethod
    def _tag_integer(
        tags: dict[str, str],
        tag: str,
        default: int,
        line_number: int,
        stats: ReaderStats,
    ) -> int:
        return optional_integer(
            tags.get(tag, "").strip(), f"tag {tag}", default, line_number, stats
        )
