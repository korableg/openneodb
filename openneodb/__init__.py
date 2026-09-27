from .cityguide import CityGuideFormatError, CityGuideReader
from .db import (
    FALLBACK_CAMERA_TYPE,
    MAX_ALERT_DISTANCE,
    MIN_ALERT_DISTANCE,
    CameraRecord,
    NeolineDBError,
    NeolineDBWriter,
    ReaderStats,
    ReadResult,
)
from .igo import IGoFormatError, IGoReader

try:
    from ._version import __version__
except ImportError:
    # Running from a source checkout without installation.
    __version__ = "0.0.0+unknown"

__all__ = (
    "FALLBACK_CAMERA_TYPE",
    "MAX_ALERT_DISTANCE",
    "MIN_ALERT_DISTANCE",
    "CameraRecord",
    "CityGuideFormatError",
    "CityGuideReader",
    "IGoFormatError",
    "IGoReader",
    "NeolineDBError",
    "NeolineDBWriter",
    "ReaderStats",
    "ReadResult",
    "__version__",
)
