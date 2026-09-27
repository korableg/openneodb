import re
import struct
from datetime import datetime
from typing import Iterable

from .model import MAX_DIRECTION_TYPE, MIN_DIRECTION_TYPE, CameraRecord


class NeolineDBError(ValueError):
    pass


class NeolineDBWriter:
    MAGIC = b"BRMSC\x00\x00JHKIM\x00\x00\x00\x00"
    SUBHEADER = bytes.fromhex("24000200000000")
    XOR_KEY = bytes.fromhex("a3aecb2c7d9980464a0013ad8a3a563c0c5a08733b6fef78")
    FILENAME_OFFSET = 0x200
    FILENAME = b"https://github.com/korableg/openneodb"
    METADATA_OFFSET = 0x400
    HEADER_SIZE = 0x440
    RECORD_SIZE = 24
    # RevM60 ignores database files larger than 3 MiB.
    MAX_FILE_SIZE = 0x300000
    MAX_RECORDS = (MAX_FILE_SIZE - HEADER_SIZE) // RECORD_SIZE
    BUILD = bytes.fromhex("3244f839")
    VERSION = bytes.fromhex("000101")

    def __init__(self, date: str) -> None:
        self.date = self._validate_date(date)

    def build(self, records: Iterable[CameraRecord]) -> bytes:
        source_records = list(records)
        if len(source_records) > self.MAX_RECORDS:
            raise NeolineDBError(
                f"record count {len(source_records)} exceeds {self.MAX_RECORDS}"
            )
        for index, record in enumerate(source_records):
            self._validate_record(record, index)
        ordered_records = sorted(source_records, key=lambda record: -record.latitude)
        record_blob = b"".join(self._encode_record(record) for record in ordered_records)
        metadata = self._build_metadata(len(ordered_records))
        header = bytearray(self.METADATA_OFFSET)
        header[:16] = self.MAGIC
        header[0x100:0x107] = self.SUBHEADER
        struct.pack_into("<I", header, 0x107, len(metadata) + len(record_blob))
        header[self.FILENAME_OFFSET:self.FILENAME_OFFSET + len(self.FILENAME)] = (
            self.FILENAME
        )
        return bytes(header) + metadata + record_blob

    def _build_metadata(self, record_count: int) -> bytes:
        return (
            b"\xff" * 16
            + self.date.encode("ascii")
            + b"\x00\x00"
            + b"\xff" * 8
            + self.BUILD
            + self.VERSION
            + b"\xff" * 9
            + struct.pack("<I", record_count)
            + b"\xff" * 12
        )

    def _encode_record(self, record: CameraRecord) -> bytes:
        raw = bytearray(self.RECORD_SIZE)
        raw[0] = record.camera_type
        raw[1:5] = record.latitude.to_bytes(4, "big")
        raw[5:9] = record.longitude.to_bytes(4, "big")
        raw[9:11] = record.direction.to_bytes(2, "big")
        raw[11] = record.direction_type
        raw[12] = record.speed
        raw[13:17] = record.latitude2.to_bytes(4, "big")
        raw[17:21] = record.longitude2.to_bytes(4, "big")
        raw[21] = record.flags
        raw[22] = record.tolerance
        raw[23] = record.distance
        return bytes(value ^ key for value, key in zip(raw, self.XOR_KEY))

    @staticmethod
    def _validate_date(value: str) -> str:
        if not re.fullmatch(r"\d{6}", value):
            raise NeolineDBError("date must use DDMMYY format")
        try:
            datetime.strptime(value, "%d%m%y")
        except ValueError as error:
            raise NeolineDBError(f"invalid DDMMYY date {value!r}") from error
        return value

    @staticmethod
    def _validate_record(record: CameraRecord, index: int) -> None:
        if not isinstance(record, CameraRecord):
            raise NeolineDBError(f"record {index} is not a CameraRecord")
        fields = (
            ("camera_type", record.camera_type, 0, 0xFF),
            ("latitude", record.latitude, 0, 0xFFFFFFFF),
            ("longitude", record.longitude, 0, 0xFFFFFFFF),
            ("direction", record.direction, 0, 359),
            (
                "direction_type",
                record.direction_type,
                MIN_DIRECTION_TYPE,
                MAX_DIRECTION_TYPE,
            ),
            ("speed", record.speed, 0, 0xFF),
            ("latitude2", record.latitude2, 0, 0xFFFFFFFF),
            ("longitude2", record.longitude2, 0, 0xFFFFFFFF),
            ("flags", record.flags, 0, 0xFF),
            ("tolerance", record.tolerance, 0, 0xFF),
            ("distance", record.distance, 0, 0xFF),
        )
        for name, value, minimum, maximum in fields:
            if isinstance(value, bool) or not isinstance(value, int):
                raise NeolineDBError(f"record {index} {name} must be an integer")
            if not minimum <= value <= maximum:
                raise NeolineDBError(
                    f"record {index} {name}={value} is outside {minimum}..{maximum}"
                )
