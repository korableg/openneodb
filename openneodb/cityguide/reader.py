from typing import BinaryIO

from ..db import (
    MAX_ALERT_DISTANCE,
    MIN_ALERT_DISTANCE,
    CameraFlags,
    CameraRecord,
    CameraType,
    DirectionType,
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
        "18059": CameraType.STATIONARY_RADAR,
        "18925": CameraType.STATIONARY_RADAR,
        "18950": CameraType.AVERAGE_SPEED,
        "18951": CameraType.STATIONARY_RADAR,
        "18952": CameraType.STRELKA,
        "18958": CameraType.AVERAGE_SPEED,
    }
    # Source types of radarless complexes, marked with CameraFlags.RADARLESS.
    RADARLESS_TYPES = frozenset({"18952"})

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
                records.extend(self._records(line, line_number, stats))
            except RowError as error:
                stats.skip(line_number, str(error))
        return ReadResult(tuple(records), stats)

    def _records(
        self, line: str, line_number: int, stats: ReaderStats
    ) -> tuple[CameraRecord, ...]:
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
        beam_type = self._tag_integer(tags, "1713", 0, line_number, stats)
        check_range(beam_type, "tag 1713", 0, 2)
        directions = self._directions(tags, line_number, stats)
        camera_type = map_camera_type(
            self.TYPE_MAPPING, source_type, "camera type", line_number, stats
        )
        flags = (
            CameraFlags.RADARLESS
            if source_type in self.RADARLESS_TYPES
            else CameraFlags(0)
        )
        return tuple(
            CameraRecord(
                camera_type=camera_type,
                latitude=latitude,
                longitude=longitude,
                direction=direction,
                direction_type=direction_type,
                speed=speed,
                flags=flags,
                distance=distance,
            )
            for direction, direction_type, distance in directions
        )

    def _directions(
        self, tags: dict[str, str], line_number: int, stats: ReaderStats
    ) -> tuple[tuple[int, DirectionType, int], ...]:
        directions = []
        for direction_tag, distance_tag in (("1705", "1706"), ("1707", "1708")):
            direction = self._direction(tags, direction_tag)
            if direction is None:
                continue
            distance = self._tag_distance(tags, distance_tag, line_number, stats)
            directions.append((direction, DirectionType.SINGLE, distance))
        if not directions:
            stats.warn(
                line_number, "missing tags 1705 and 1707, using all directions"
            )
            distance = self._tag_distance(tags, "1706", line_number, stats)
            directions.append((0, DirectionType.ALL, distance))
        return tuple(directions)

    @staticmethod
    def _direction(tags: dict[str, str], tag: str) -> int | None:
        value = tags.get(tag, "").strip()
        if not value:
            return None
        source_direction = parse_integer(value, f"tag {tag}")
        check_range(source_direction, f"tag {tag}", 0, 359)
        # CityGuide stores camera headings; Neoline stores traffic headings.
        return (source_direction + 180) % 360

    def _tag_distance(
        self, tags: dict[str, str], tag: str, line_number: int, stats: ReaderStats
    ) -> int:
        metres = self._tag_integer(tags, tag, 0, line_number, stats)
        if metres < 0:
            raise RowError(f"tag {tag}={metres} must not be negative")
        return self._distance(metres, tag, line_number, stats)

    @staticmethod
    def _distance(metres: int, tag: str, line_number: int, stats: ReaderStats) -> int:
        distance = metres // 10
        if metres and distance == 0:
            # 0 means the 500 m default, not "closer than 10 m".
            stats.warn(
                line_number,
                f"tag {tag}={metres} raised to {MIN_ALERT_DISTANCE * 10} metres",
            )
            return MIN_ALERT_DISTANCE
        if distance > MAX_ALERT_DISTANCE:
            stats.warn(
                line_number,
                f"tag {tag}={metres} clamped to {MAX_ALERT_DISTANCE * 10} metres",
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
