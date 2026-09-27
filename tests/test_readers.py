import io
import unittest

from openneodb.cityguide import CityGuideFormatError, CityGuideReader
from openneodb.igo import IGoFormatError, IGoReader


class IGoReaderTest(unittest.TestCase):
    def test_reads_mappings_directions_and_fallbacks(self) -> None:
        source = (
            "IDX,X,Y,TYPE,SPEED,DIRTYPE,DIRECTION\r\n"
            "1,37.12349,55.98769,68,60,2,359\r\n"
            "2,37.00009,55.00009,193,40,0,10\r\n"
            "3,37,55,,60,1,20\r\n"
        ).encode("utf-8-sig")

        result = IGoReader().read(io.BytesIO(source))

        self.assertEqual(len(result.records), 2)
        first, second = result.records
        self.assertEqual(first.camera_type, 0x01)
        self.assertEqual(first.flags, 0x02)
        self.assertEqual(first.direction_type, 2)
        self.assertEqual(first.direction, 359)
        self.assertEqual(first.latitude, 559876)
        self.assertEqual(first.longitude, 371234)
        self.assertEqual(second.camera_type, 0x06)
        self.assertEqual(second.direction_type, 0)
        self.assertEqual(result.stats.read, 3)
        self.assertEqual(result.stats.skipped, 1)
        self.assertEqual(result.stats.fallback, 1)
        self.assertEqual(result.stats.warnings, 2)

    def test_missing_optional_values_use_safe_defaults(self) -> None:
        source = (
            "IDX,X,Y,TYPE,SPEED,DIRTYPE,DIRECTION\n"
            "1,37.1,55.1,192,,,\n"
        ).encode()

        result = IGoReader().read(io.BytesIO(source))

        record = result.records[0]
        self.assertEqual(record.speed, 0)
        self.assertEqual(record.direction_type, 1)
        self.assertEqual(record.direction, 0)
        self.assertEqual(result.stats.warnings, 3)

    def test_rejects_missing_columns(self) -> None:
        with self.assertRaises(IGoFormatError):
            IGoReader().read(io.BytesIO(b"X,Y,TYPE\n37,55,192\n"))

    def test_rejects_invalid_csv_header(self) -> None:
        source = b'"' + b"a" * 200000 + b'"\n'
        with self.assertRaises(IGoFormatError):
            IGoReader().read(io.BytesIO(source))

    def test_skips_invalid_rows_with_warnings(self) -> None:
        source = (
            "IDX,X,Y,TYPE,SPEED,DIRTYPE,DIRECTION\n"
            "1,37.1,55.1,192,300,1,90\n"
            "2,-37.1,55.1,192,60,1,90\n"
            "3,555.1,95.1,192,60,1,90\n"
            "4,37.1,55.1,192,60,1,90,extra\n"
            "5,37.1,55.1,abc,60,1,90\n"
            "6,37.1,55.1,192,60,1,90\n"
        ).encode()

        result = IGoReader().read(io.BytesIO(source))

        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.stats.read, 6)
        self.assertEqual(result.stats.skipped, 5)
        self.assertEqual(result.stats.warnings, 5)
        self.assertTrue(
            all("row skipped" in message for message in result.stats.warning_messages)
        )
        self.assertIn("line 2: SPEED=300", result.stats.warning_messages[0])


class CityGuideReaderTest(unittest.TestCase):
    def test_reads_tags_direction_mapping_and_rev_m60_omnidirection(self) -> None:
        source = (
            "2|Radars|1251\r\n"
            "18952|RU-1|55.98769|37.12349|1709|60|1713|0|1705|277|1706|150|\r\n"
            "18958|RU-2|55.00009|37.00009|1709|80|1713|1|1705|10|1706|200|\r\n"
            "18925|RU-3|54.1|36.1|1709|0|1713|2|1705|180|1706|50|\r\n"
        ).encode("cp1251")

        result = CityGuideReader().read(io.BytesIO(source))

        first, second, third = result.records
        self.assertEqual(first.camera_type, 0x01)
        self.assertEqual(first.flags, 0x02)
        self.assertEqual(first.direction, 97)
        self.assertEqual(first.direction_type, 1)
        self.assertEqual(first.distance, 15)
        self.assertEqual(first.latitude, 559876)
        self.assertEqual(first.longitude, 371234)
        self.assertEqual(second.camera_type, 0x4A)
        self.assertEqual(second.direction_type, 1)
        self.assertEqual(third.camera_type, 0x06)
        self.assertEqual(third.direction_type, 0)
        self.assertEqual(third.flags, 0)
        self.assertEqual(third.tolerance, 0)

    def test_skips_blank_type_and_defaults_missing_tags(self) -> None:
        source = (
            "2|Radars|1251\r\n"
            "|RU-1|55.1|37.1|1709|60|\r\n"
            "99999|RU-2|55.2|37.2|\r\n"
        ).encode("cp1251")

        result = CityGuideReader().read(io.BytesIO(source))

        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].camera_type, 0x06)
        self.assertEqual(result.records[0].direction_type, 1)
        self.assertEqual(result.stats.skipped, 1)
        self.assertEqual(result.stats.fallback, 1)
        self.assertEqual(result.stats.warnings, 6)

    def test_skips_malformed_and_invalid_rows(self) -> None:
        source = (
            b"2|Radars|1251\r\n"
            b"18059|RU-1|55.1|37.1\r\n"
            b"18059|RU-2|55.1|37.1|1713|5|\r\n"
            b"\r\n"
            b"18059|RU-3|55.1|37.1|1709|60|\r\n"
            b"\r\n"
        )

        result = CityGuideReader().read(io.BytesIO(source))

        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.stats.read, 3)
        self.assertEqual(result.stats.skipped, 2)

    def test_rejects_invalid_header(self) -> None:
        with self.assertRaises(CityGuideFormatError):
            CityGuideReader().read(io.BytesIO(b"1|Radars|1251\r\n"))

    def test_direction_wraps_and_distance_follows_firmware_limits(self) -> None:
        source = (
            "2|Radars|1251\r\n"
            "18059|RU-1|55.1|37.1|1709|60|1713|0|1705|0|1706|5|\r\n"
            "18059|RU-2|55.1|37.1|1709|60|1713|0|1705|180|1706|2500|\r\n"
            "18059|RU-3|55.1|37.1|1709|60|1713|0|1706|50|\r\n"
        ).encode("cp1251")

        first, second, third = CityGuideReader().read(io.BytesIO(source)).records

        self.assertEqual(first.direction, 180)
        self.assertEqual(first.distance, 10)
        self.assertEqual(second.direction, 0)
        self.assertEqual(second.distance, 200)
        self.assertEqual(third.direction, 0)
        self.assertEqual(third.distance, 5)


if __name__ == "__main__":
    unittest.main()
