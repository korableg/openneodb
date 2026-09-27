import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "-m", "openneodb"]


class CLITest(unittest.TestCase):
    def test_file_input_and_output(self) -> None:
        source = (
            "IDX,X,Y,TYPE,SPEED,DIRTYPE,DIRECTION\r\n"
            "1,37.1,55.1,192,60,1,90\r\n"
        ).encode()
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "source.txt"
            output_path = Path(directory) / "result.db"
            input_path.write_bytes(source)

            process = subprocess.run(
                [
                    *CLI,
                    "igo",
                    "-i",
                    str(input_path),
                    "-o",
                    str(output_path),
                    "--date",
                    "270926",
                ],
                cwd=ROOT,
                capture_output=True,
                check=False,
            )

            self.assertEqual(process.returncode, 0, process.stderr.decode())
            self.assertEqual(process.stdout, b"")
            self.assertTrue(output_path.read_bytes().startswith(b"BRMSC"))
            self.assertIn(b"1 records", process.stderr)

    def test_stdin_stdout_are_binary_clean(self) -> None:
        source = (
            "2|Radars|1251\r\n"
            "18059|RU-1|55.1|37.1|1709|60|1713|0|1705|270|1706|150|\r\n"
        ).encode("cp1251")

        process = subprocess.run(
            [*CLI, "cityguide", "--date", "270926"],
            cwd=ROOT,
            input=source,
            capture_output=True,
            check=False,
        )

        self.assertEqual(process.returncode, 0, process.stderr.decode())
        self.assertTrue(process.stdout.startswith(b"BRMSC"))
        self.assertNotIn(b"records", process.stdout)
        self.assertIn(b"1 records", process.stderr)

    def test_structural_error_does_not_touch_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "bad.txt"
            output_path = Path(directory) / "result.db"
            input_path.write_bytes(b"bad header\n")
            output_path.write_bytes(b"existing")

            process = subprocess.run(
                [
                    *CLI,
                    "igo",
                    "-i",
                    str(input_path),
                    "-o",
                    str(output_path),
                ],
                cwd=ROOT,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(process.returncode, 0)
            self.assertEqual(process.stdout, b"")
            self.assertEqual(output_path.read_bytes(), b"existing")
            self.assertIn(b"ERROR", process.stderr)

    def test_invalid_date_fails_before_reading_input(self) -> None:
        process = subprocess.run(
            [*CLI, "igo", "--date", "999999"],
            cwd=ROOT,
            input=b"bad header\n",
            capture_output=True,
            check=False,
        )

        self.assertEqual(process.returncode, 1)
        self.assertIn(b"DDMMYY", process.stderr)

    def test_output_replaces_file_without_leftovers(self) -> None:
        source = b"IDX,X,Y,TYPE,SPEED,DIRTYPE,DIRECTION\n1,37.1,55.1,192,60,1,90\n"
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "result.db"
            output_path.write_bytes(b"existing")

            process = subprocess.run(
                [*CLI, "igo", "-o", str(output_path), "--date", "270926"],
                cwd=ROOT,
                input=source,
                capture_output=True,
                check=False,
            )

            self.assertEqual(process.returncode, 0, process.stderr.decode())
            self.assertTrue(output_path.read_bytes().startswith(b"BRMSC"))
            self.assertEqual(list(Path(directory).iterdir()), [output_path])

    def test_help_is_written_to_stderr(self) -> None:
        process = subprocess.run(
            [*CLI, "--help"],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )

        self.assertEqual(process.returncode, 0)
        self.assertEqual(process.stdout, b"")
        self.assertIn(b"usage:", process.stderr)


if __name__ == "__main__":
    unittest.main()
