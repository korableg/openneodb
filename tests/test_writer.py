import struct
import unittest

from openneodb.db import CameraRecord, NeolineDBError, NeolineDBWriter


def decode_record(raw: bytes) -> bytes:
    return bytes(value ^ key for value, key in zip(raw, NeolineDBWriter.XOR_KEY))


class NeolineDBWriterTest(unittest.TestCase):
    def test_builds_header_metadata_records_and_stable_sort(self) -> None:
        records = (
            CameraRecord(0x06, 500000, 300000, 10, 1, 60, distance=15),
            CameraRecord(0x01, 600000, 400000, 20, 2, 80, flags=0x02),
            CameraRecord(0x4A, 500000, 350000, 30, 0, 90),
        )

        data = NeolineDBWriter("270926").build(records)

        self.assertEqual(len(data), 0x440 + 3 * 24)
        self.assertEqual(data[:16], NeolineDBWriter.MAGIC)
        self.assertEqual(data[0x100:0x107], NeolineDBWriter.SUBHEADER)
        self.assertEqual(struct.unpack_from("<I", data, 0x107)[0], 0x40 + 3 * 24)
        self.assertEqual(
            data[0x200:0x400].split(b"\x00")[0],
            b"https://github.com/korableg/openneodb",
        )
        self.assertFalse(any(data[0x200 + len(NeolineDBWriter.FILENAME):0x400]))
        self.assertEqual(data[0x410:0x418], b"270926\x00\x00")
        self.assertEqual(data[0x420:0x424], NeolineDBWriter.BUILD)
        self.assertEqual(data[0x424:0x427], NeolineDBWriter.VERSION)
        self.assertEqual(struct.unpack_from("<I", data, 0x430)[0], 3)

        decoded = [
            decode_record(data[offset:offset + 24])
            for offset in range(0x440, len(data), 24)
        ]
        self.assertEqual([record[0] for record in decoded], [0x01, 0x06, 0x4A])
        self.assertEqual(int.from_bytes(decoded[0][1:5], "big"), 600000)
        self.assertEqual(decoded[0][11], 2)
        self.assertEqual(decoded[0][21], 0x02)
        self.assertEqual(decoded[1][23], 15)
        self.assertEqual(int.from_bytes(decoded[0][5:9], "big"), 400000)
        self.assertEqual(int.from_bytes(decoded[0][9:11], "big"), 20)
        self.assertEqual(decoded[0][12], 80)

    def test_max_records_fit_device_file_size_limit(self) -> None:
        size = NeolineDBWriter.HEADER_SIZE + NeolineDBWriter.MAX_RECORDS * 24
        self.assertLessEqual(size, NeolineDBWriter.MAX_FILE_SIZE)
        self.assertGreater(size + 24, NeolineDBWriter.MAX_FILE_SIZE)

    def test_rejects_invalid_record_range(self) -> None:
        record = CameraRecord(0x06, 500000, 300000, 360, 1, 60)
        with self.assertRaises(NeolineDBError):
            NeolineDBWriter("270926").build((record,))

    def test_rejects_record_count_above_device_limit(self) -> None:
        record = CameraRecord(0x06, 500000, 300000, 10, 1, 60)
        records = [record] * (NeolineDBWriter.MAX_RECORDS + 1)
        with self.assertRaises(NeolineDBError):
            NeolineDBWriter("270926").build(records)

    def test_rejects_invalid_date(self) -> None:
        with self.assertRaises(NeolineDBError):
            NeolineDBWriter("310226")


if __name__ == "__main__":
    unittest.main()
