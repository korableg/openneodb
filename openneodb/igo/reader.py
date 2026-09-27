import csv
import io
from typing import BinaryIO

from ..db import (
    MAX_DIRECTION_TYPE,
    MIN_DIRECTION_TYPE,
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


class IGoFormatError(ValueError):
    pass


class _IGoCSVReader:
    """iGo and iGoExt share one CSV layout and differ only in TYPE codes."""

    FORMAT_NAME: str
    TYPE_MAPPING: dict[int, CameraType]
    # Source types of radarless complexes, marked with CameraFlags.RADARLESS.
    RADARLESS_TYPES: frozenset[int]
    REQUIRED_COLUMNS = (
        "IDX",
        "X",
        "Y",
        "TYPE",
        "SPEED",
        "DIRTYPE",
        "DIRECTION",
    )
    def read(self, source: BinaryIO) -> ReadResult:
        try:
            text = source.read().decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise IGoFormatError("iGo input must be UTF-8 text") from error
        rows = csv.DictReader(io.StringIO(text, newline=""))
        records = []
        stats = ReaderStats()
        try:
            self._validate_header(rows.fieldnames)
            for row in rows:
                line_number = rows.line_num
                stats.read += 1
                try:
                    records.append(self._record(row, line_number, stats))
                except RowError as error:
                    stats.skip(line_number, str(error))
        except csv.Error as error:
            raise IGoFormatError(f"invalid CSV: {error}") from error
        if stats.fallback * 2 > len(records):
            raise IGoFormatError(
                f"{stats.fallback} of {len(records)} TYPE values are unknown "
                f"for {self.FORMAT_NAME}; the file is likely in the other "
                "format (iGo or iGoExt)"
            )
        return ReadResult(tuple(records), stats)

    def _record(
        self, row: dict[str, str], line_number: int, stats: ReaderStats
    ) -> CameraRecord:
        if None in row:
            raise RowError("too many CSV columns")
        source_type = self._value(row, "TYPE")
        if not source_type:
            raise RowError("blank TYPE")
        camera_type_value = parse_integer(source_type, "TYPE")
        longitude = parse_coordinate(self._value(row, "X"), "X", MAX_LONGITUDE)
        latitude = parse_coordinate(self._value(row, "Y"), "Y", MAX_LATITUDE)
        speed = self._optional_integer(row, "SPEED", 0, line_number, stats)
        direction_type = self._optional_integer(
            row, "DIRTYPE", DirectionType.SINGLE, line_number, stats
        )
        direction = self._optional_integer(row, "DIRECTION", 0, line_number, stats)
        check_range(speed, "SPEED", 0, 255)
        check_range(
            direction_type, "DIRTYPE", MIN_DIRECTION_TYPE, MAX_DIRECTION_TYPE
        )
        check_range(direction, "DIRECTION", 0, 359)
        return CameraRecord(
            camera_type=map_camera_type(
                self.TYPE_MAPPING, camera_type_value, "TYPE", line_number, stats
            ),
            latitude=latitude,
            longitude=longitude,
            direction=direction,
            direction_type=DirectionType(direction_type),
            speed=speed,
            flags=(
                CameraFlags.RADARLESS
                if camera_type_value in self.RADARLESS_TYPES
                else CameraFlags(0)
            ),
        )

    def _optional_integer(
        self,
        row: dict[str, str],
        name: str,
        default: int,
        line_number: int,
        stats: ReaderStats,
    ) -> int:
        return optional_integer(
            self._value(row, name), name, default, line_number, stats
        )

    @staticmethod
    def _validate_header(fieldnames: list[str] | None) -> None:
        if fieldnames is None:
            raise IGoFormatError("missing CSV header")
        missing = [
            name
            for name in _IGoCSVReader.REQUIRED_COLUMNS
            if name not in fieldnames
        ]
        if missing:
            raise IGoFormatError(f"missing CSV columns: {', '.join(missing)}")
        if len(fieldnames) != len(set(fieldnames)):
            raise IGoFormatError("duplicate CSV columns")

    @staticmethod
    def _value(row: dict[str, str], name: str) -> str:
        value = row.get(name)
        return "" if value is None else value.strip()


class IGoReader(_IGoCSVReader):
    """iGo: five generic classes."""

    FORMAT_NAME = "iGo"
    TYPE_MAPPING = {
        1: CameraType.STATIONARY_RADAR,
        3: CameraType.STRELKA,
        4: CameraType.STATIONARY_RADAR,
        5: CameraType.AVERAGE_SPEED,
    }
    RADARLESS_TYPES = frozenset({3})


class IGoExtReader(_IGoCSVReader):
    """iGoExt: detailed types, e.g. police posts are separate."""

    FORMAT_NAME = "iGoExt"
    TYPE_MAPPING = {
        192: CameraType.STATIONARY_RADAR,
        68: CameraType.STRELKA,
        197: CameraType.STRELKA,
        193: CameraType.AVERAGE_SPEED,
        199: CameraType.AVERAGE_SPEED,
        206: CameraType.POLICE_POST,
        227: CameraType.STATIONARY_RADAR,
    }
    RADARLESS_TYPES = frozenset({68, 197})
