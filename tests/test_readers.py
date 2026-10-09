import io
import unittest

from openneodb.cityguide import CityGuideFormatError, CityGuideReader
from openneodb.igo import IGoExtReader, IGoFormatError, IGoReader


class IGoReaderTest(unittest.TestCase):
    def test_reads_generic_types(self) -> None:
        source = (
            "IDX,X,Y,TYPE,SPEED,DIRTYPE,DIRECTION\r\n"
            "1,37.1,55.1,1,60,1,90\r\n"
            "2,37.2,55.2,3,60,1,90\r\n"
            "3,37.3,55.3,4,60,1,90\r\n"
            "4,37.4,55.4,5,60,1,90\r\n"
            "5,37.5,55.5,2,60,1,90\r\n"
        ).encode("utf-8-sig")

        result = IGoReader().read(io.BytesIO(source))

        self.assertEqual(
            [record.camera_type for record in result.records],
            [0x06, 0x01, 0x06, 0x4A, 0x06],
        )
        self.assertEqual([record.flags for record in result.records], [0, 0x02, 0, 0, 0])
        self.assertEqual(result.stats.fallback, 1)

    def test_rejects_igoext_file(self) -> None:
        source = (
            "IDX,X,Y,TYPE,SPEED,DIRTYPE,DIRECTION\n"
            "1,37.1,55.1,192,60,1,90\n"
            "2,37.2,55.2,68,60,1,90\n"
        ).encode()

        with self.assertRaisesRegex(IGoFormatError, "2 of 2 TYPE values"):
            IGoReader().read(io.BytesIO(source))


class IGoExtReaderTest(unittest.TestCase):
    def test_reads_mappings_directions_and_fallbacks(self) -> None:
        source = (
            "IDX,X,Y,TYPE,SPEED,DIRTYPE,DIRECTION\r\n"
            "1,37.12349,55.98769,68,60,2,359\r\n"
            "2,37.00009,55.00009,194,40,0,10\r\n"
            "3,37,55,,60,1,20\r\n"
        ).encode("utf-8-sig")

        result = IGoExtReader().read(io.BytesIO(source))

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

    def test_maps_secondary_types(self) -> None:
        source = (
            "IDX,X,Y,TYPE,SPEED,DIRTYPE,DIRECTION\n"
            "1,37.1,55.1,193,60,1,90\n"
            "2,37.2,55.2,197,60,1,90\n"
        ).encode()

        result = IGoExtReader().read(io.BytesIO(source))

        self.assertEqual(
            [(record.camera_type, record.flags) for record in result.records],
            [(0x4A, 0), (0x01, 0x02)],
        )
        self.assertEqual(result.stats.fallback, 0)

    def test_missing_optional_values_use_safe_defaults(self) -> None:
        source = (
            "IDX,X,Y,TYPE,SPEED,DIRTYPE,DIRECTION\n"
            "1,37.1,55.1,192,,,\n"
        ).encode()

        result = IGoExtReader().read(io.BytesIO(source))

        record = result.records[0]
        self.assertEqual(record.speed, 0)
        self.assertEqual(record.direction_type, 1)
        self.assertEqual(record.direction, 0)
        self.assertEqual(result.stats.warnings, 3)

    def test_rejects_igo_file(self) -> None:
        source = (
            "IDX,X,Y,TYPE,SPEED,DIRTYPE,DIRECTION\n"
            "1,37.1,55.1,1,60,1,90\n"
            "2,37.2,55.2,3,60,1,90\n"
        ).encode()

        with self.assertRaisesRegex(IGoFormatError, "unknown for iGoExt"):
            IGoExtReader().read(io.BytesIO(source))

    def test_rejects_missing_columns(self) -> None:
        with self.assertRaises(IGoFormatError):
            IGoExtReader().read(io.BytesIO(b"X,Y,TYPE\n37,55,192\n"))

    def test_rejects_invalid_csv_header(self) -> None:
        source = b'"' + b"a" * 200000 + b'"\n'
        with self.assertRaises(IGoFormatError):
            IGoExtReader().read(io.BytesIO(source))

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

        result = IGoExtReader().read(io.BytesIO(source))

        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.stats.read, 6)
        self.assertEqual(result.stats.skipped, 5)
        self.assertEqual(result.stats.warnings, 5)
        self.assertTrue(
            all("row skipped" in message for message in result.stats.warning_messages)
        )
        self.assertIn("line 2: SPEED=300", result.stats.warning_messages[0])


class CityGuideReaderTest(unittest.TestCase):
    def test_reads_tags_and_single_direction_for_all_beam_types(self) -> None:
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
        self.assertEqual(third.direction_type, 1)
        self.assertEqual(third.flags, 0)
        self.assertEqual(third.tolerance, 0)

    def test_intersection_cameras_match_igoext_traffic_directions(self) -> None:
        cityguide_source = (
            "2|Radars|1251\r\n"
            "18952|RU-59973|55.0815145|82.8970894|1709|60|1713|2|1705|316|1706|200|\r\n"
            "18952|RU-59974|55.0811575|82.8979155|1709|60|1713|2|1705|136|1706|200|\r\n"
            "18952|RU-59975|55.0808929|82.8971323|1709|60|1713|2|1705|188|1706|200|\r\n"
        ).encode("cp1251")
        igoext_source = (
            "IDX,X,Y,TYPE,SPEED,DIRTYPE,DIRECTION\r\n"
            "69973,82.8970894,55.0815145,68,60,1,136\r\n"
            "69974,82.8979155,55.0811575,68,60,1,316\r\n"
            "69975,82.8971323,55.0808929,68,60,1,8\r\n"
        ).encode("utf-8-sig")

        cityguide = CityGuideReader().read(io.BytesIO(cityguide_source))
        igoext = IGoExtReader().read(io.BytesIO(igoext_source))

        self.assertEqual(len(cityguide.records), 3)
        self.assertEqual(len(igoext.records), 3)
        self.assertEqual(cityguide.stats.warnings, 0)
        self.assertEqual(igoext.stats.warnings, 0)
        self.assertEqual(
            [record.direction for record in cityguide.records], [136, 316, 8]
        )
        for actual, expected in zip(cityguide.records, igoext.records):
            with self.subTest(latitude=actual.latitude, longitude=actual.longitude):
                self.assertEqual(actual.latitude, expected.latitude)
                self.assertEqual(actual.longitude, expected.longitude)
                self.assertEqual(actual.speed, expected.speed)
                self.assertEqual(actual.direction, expected.direction)
                self.assertEqual(actual.direction_type, expected.direction_type)
                self.assertEqual(actual.direction_type, 1)

    def test_skips_blank_type_and_defaults_missing_tags(self) -> None:
        source = (
            "2|Radars|1251\r\n"
            "|RU-1|55.1|37.1|1709|60|\r\n"
            "99999|RU-2|55.2|37.2|\r\n"
        ).encode("cp1251")

        result = CityGuideReader().read(io.BytesIO(source))

        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].camera_type, 0x06)
        self.assertEqual(result.records[0].direction_type, 0)
        self.assertEqual(result.stats.skipped, 1)
        self.assertEqual(result.stats.fallback, 1)
        self.assertEqual(result.stats.warnings, 6)

    def test_cameras_without_azimuths_match_igoext_all_directions(self) -> None:
        cityguide_source = (
            "2|Radars|1251\r\n"
            "18950|RU-30030|60.1448699|64.7317165|1709|60|1713|0|\r\n"
            "18950|RU-30068|60.8953664|71.7732188|1709|90|1713|0|\r\n"
            "18950|RU-30084|60.7609516|72.8298068|1709|90|1713|0|\r\n"
        ).encode("cp1251")
        igoext_source = (
            "IDX,X,Y,TYPE,SPEED,DIRTYPE,DIRECTION\r\n"
            "30030,64.7317165,60.1448699,199,60,0,0\r\n"
            "30068,71.7732188,60.8953664,199,90,0,0\r\n"
            "30084,72.8298068,60.7609516,199,90,0,0\r\n"
        ).encode("utf-8-sig")

        cityguide = CityGuideReader().read(io.BytesIO(cityguide_source))
        igoext = IGoExtReader().read(io.BytesIO(igoext_source))

        self.assertEqual(len(cityguide.records), 3)
        self.assertEqual(len(igoext.records), 3)
        self.assertEqual(cityguide.stats.skipped, 0)
        for actual, expected in zip(cityguide.records, igoext.records):
            with self.subTest(latitude=actual.latitude, longitude=actual.longitude):
                self.assertEqual(actual.latitude, expected.latitude)
                self.assertEqual(actual.longitude, expected.longitude)
                self.assertEqual(actual.camera_type, expected.camera_type)
                self.assertEqual(actual.speed, expected.speed)
                self.assertEqual(actual.direction, expected.direction)
                self.assertEqual(actual.direction_type, expected.direction_type)
                self.assertEqual(actual.direction_type, 0)

    def test_missing_empty_and_blank_azimuths_use_all_directions(self) -> None:
        for beam_type in (0, 1, 2):
            for azimuth_tags in ("", "1705||1707||", "1705|  |1707|  |"):
                with self.subTest(beam_type=beam_type, azimuth_tags=azimuth_tags):
                    source = (
                        "2|Radars|1251\r\n"
                        f"18059|RU-1|55.1|37.1|1709|60|1713|{beam_type}|"
                        f"1706|200|{azimuth_tags}\r\n"
                    ).encode("cp1251")

                    result = CityGuideReader().read(io.BytesIO(source))

                    self.assertEqual(len(result.records), 1)
                    record = result.records[0]
                    self.assertEqual(record.direction_type, 0)
                    self.assertEqual(record.direction, 0)
                    self.assertEqual(record.distance, 20)
                    self.assertEqual(result.stats.warnings, 1)
                    self.assertIn(
                        "using all directions", result.stats.warning_messages[0]
                    )

    def test_zero_azimuth_is_a_single_north_facing_direction(self) -> None:
        for direction_tag, distance_tag in (("1705", "1706"), ("1707", "1708")):
            with self.subTest(direction_tag=direction_tag):
                source = (
                    "2|Radars|1251\r\n"
                    "18059|RU-1|55.1|37.1|1709|60|1713|0|"
                    f"{direction_tag}|0|{distance_tag}|200|\r\n"
                ).encode("cp1251")

                result = CityGuideReader().read(io.BytesIO(source))

                self.assertEqual(len(result.records), 1)
                record = result.records[0]
                self.assertEqual(record.direction_type, 1)
                self.assertEqual(record.direction, 180)
                self.assertEqual(record.distance, 20)
                self.assertEqual(result.stats.warnings, 0)

    def test_two_azimuths_preserve_independent_directions_and_distances(self) -> None:
        source = (
            "2|Radars|1251\r\n"
            "18952|RU-1|55.1|37.1|1709|60|1713|2|"
            "1705|10|1706|200|1707|75|1708|400|\r\n"
        ).encode("cp1251")

        result = CityGuideReader().read(io.BytesIO(source))

        self.assertEqual(len(result.records), 2)
        first, second = result.records
        self.assertEqual(
            (first.direction, first.direction_type, first.distance), (190, 1, 20)
        )
        self.assertEqual(
            (second.direction, second.direction_type, second.distance), (255, 1, 40)
        )
        self.assertEqual(first.latitude, second.latitude)
        self.assertEqual(first.longitude, second.longitude)
        self.assertEqual(
            (first.camera_type, first.flags, first.speed), (0x01, 0x02, 60)
        )
        self.assertEqual(
            (second.camera_type, second.flags, second.speed), (0x01, 0x02, 60)
        )
        self.assertEqual(result.stats.read, 1)
        self.assertEqual(result.stats.skipped, 0)
        self.assertEqual(result.stats.warnings, 0)

    def test_second_azimuth_without_first_uses_its_distance(self) -> None:
        source = (
            "2|Radars|1251\r\n"
            "18059|RU-1|55.1|37.1|1709|60|1713|1|"
            "1705| |1706|100|1707|359|1708|400|\r\n"
        ).encode("cp1251")

        result = CityGuideReader().read(io.BytesIO(source))

        self.assertEqual(len(result.records), 1)
        record = result.records[0]
        self.assertEqual(
            (record.direction, record.direction_type, record.distance), (179, 1, 40)
        )
        self.assertEqual(result.stats.warnings, 0)

    def test_missing_second_distance_defaults_to_zero_with_warning(self) -> None:
        source = (
            "2|Radars|1251\r\n"
            "18059|RU-1|55.1|37.1|1709|60|1713|0|1707|20|\r\n"
        ).encode("cp1251")

        result = CityGuideReader().read(io.BytesIO(source))

        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].direction, 200)
        self.assertEqual(result.records[0].direction_type, 1)
        self.assertEqual(result.records[0].distance, 0)
        self.assertEqual(result.stats.warnings, 1)
        self.assertIn("tag 1708", result.stats.warning_messages[0])

    def test_second_distance_follows_firmware_limits(self) -> None:
        for metres, expected in ((5, 10), (2500, 200)):
            with self.subTest(metres=metres):
                source = (
                    "2|Radars|1251\r\n"
                    "18059|RU-1|55.1|37.1|1709|60|1713|0|"
                    f"1707|180|1708|{metres}|\r\n"
                ).encode("cp1251")

                result = CityGuideReader().read(io.BytesIO(source))

                self.assertEqual(result.records[0].distance, expected)
                self.assertEqual(result.stats.warnings, 1)
                self.assertIn("tag 1708", result.stats.warning_messages[0])

    def test_invalid_second_fields_skip_the_entire_row(self) -> None:
        for second_tags in (
            "1707|-1|1708|400|",
            "1707|360|1708|400|",
            "1707|bad|1708|400|",
            "1707|75|1708|-1|",
            "1707|75|1708|bad|",
        ):
            with self.subTest(second_tags=second_tags):
                source = (
                    "2|Radars|1251\r\n"
                    "18059|RU-1|55.1|37.1|1709|60|1713|0|"
                    f"1705|10|1706|200|{second_tags}\r\n"
                ).encode("cp1251")

                result = CityGuideReader().read(io.BytesIO(source))

                self.assertEqual(result.records, ())
                self.assertEqual(result.stats.read, 1)
                self.assertEqual(result.stats.skipped, 1)
                self.assertIn("row skipped", result.stats.warning_messages[-1])

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
        self.assertEqual(first.direction_type, 1)
        self.assertEqual(second.direction_type, 1)
        self.assertEqual(third.direction_type, 0)
        self.assertEqual(third.distance, 5)


if __name__ == "__main__":
    unittest.main()
