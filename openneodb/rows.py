from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from typing import Mapping, TypeVar

from .db import FALLBACK_CAMERA_TYPE, ReaderStats

MAX_LATITUDE = 90
MAX_LONGITUDE = 180

SourceType = TypeVar("SourceType")


class RowError(ValueError):
    """Invalid source row; readers skip the row with a warning."""


def parse_integer(value: str, name: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise RowError(f"invalid {name} value {value!r}") from error


def optional_integer(
    value: str, name: str, default: int, line_number: int, stats: ReaderStats
) -> int:
    if not value:
        stats.warn(line_number, f"missing {name}, using {default}")
        return default
    return parse_integer(value, name)


def parse_coordinate(value: str, name: str, maximum: int) -> int:
    """Degrees to Neoline units: floor(value * 10^4), northern/eastern only."""
    if not value:
        raise RowError(f"blank {name}")
    try:
        coordinate = Decimal(value)
    except InvalidOperation as error:
        raise RowError(f"invalid {name} {value!r}") from error
    if not coordinate.is_finite():
        raise RowError(f"invalid {name} {value!r}")
    if not 0 <= coordinate <= maximum:
        raise RowError(f"{name}={value} is outside 0..{maximum} (N/E only)")
    return int((coordinate * 10000).to_integral_value(rounding=ROUND_FLOOR))


def check_range(value: int, name: str, minimum: int, maximum: int) -> None:
    if not minimum <= value <= maximum:
        raise RowError(f"{name}={value} is outside {minimum}..{maximum}")


def map_camera_type(
    mapping: Mapping[SourceType, int],
    source_type: SourceType,
    name: str,
    line_number: int,
    stats: ReaderStats,
) -> int:
    camera_type = mapping.get(source_type)
    if camera_type is None:
        stats.fallback += 1
        stats.warn(
            line_number,
            f"unknown {name} {source_type!r}, using 0x{FALLBACK_CAMERA_TYPE:02X}",
        )
        return FALLBACK_CAMERA_TYPE
    return camera_type
