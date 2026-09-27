import argparse
import logging
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Callable, Protocol, Sequence

from .cityguide import CityGuideFormatError, CityGuideReader
from .db import NeolineDBError, NeolineDBWriter, ReadResult
from .igo import IGoFormatError, IGoReader


class Reader(Protocol):
    def read(self, source: BinaryIO) -> ReadResult: ...


READERS: dict[str, tuple[Callable[[], Reader], str]] = {
    "igo": (IGoReader, "read a SpeedCamOnline iGoExt CSV export"),
    "cityguide": (CityGuideReader, "read a CityGuide Speedcam v2 BKM export"),
}


class StderrArgumentParser(argparse.ArgumentParser):
    def print_help(self, file=None) -> None:
        super().print_help(file or sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = StderrArgumentParser(
        prog="neodb",
        description="Convert CityGuide or iGo speed-camera data to Neoline DB",
    )
    subparsers = parser.add_subparsers(dest="format", required=True)
    for name, (_, help_text) in READERS.items():
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument(
            "-i", "--input", metavar="PATH", help="input file; default: stdin"
        )
        command.add_argument(
            "-o", "--output", metavar="PATH", help="output DB; default: stdout"
        )
        command.add_argument(
            "--date", metavar="DDMMYY", help="database date; default: local date"
        )
    return parser


def read_source(path: str | None, reader: Reader) -> ReadResult:
    if path is None:
        return reader.read(sys.stdin.buffer)
    with Path(path).open("rb") as source:
        return reader.read(source)


def write_database(path: str | None, data: bytes) -> None:
    if path is None:
        output: BinaryIO = sys.stdout.buffer
        output.write(data)
        output.flush()
        return
    target = Path(path)
    if target.exists() and not target.is_file():
        # Devices and pipes such as /dev/null cannot be replaced atomically.
        target.write_bytes(data)
        return
    descriptor, temporary = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, _new_file_mode())
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _new_file_mode() -> int:
    # mkstemp creates 0600; match what open() would have produced.
    umask = os.umask(0)
    os.umask(umask)
    return 0o666 & ~umask


def run(args: argparse.Namespace, logger: logging.Logger) -> None:
    writer = NeolineDBWriter(date=args.date or datetime.now().strftime("%d%m%y"))
    reader_factory, _ = READERS[args.format]
    result = read_source(args.input, reader_factory())
    data = writer.build(result.records)
    write_database(args.output, data)
    for message in result.stats.warning_messages:
        logger.warning(message)
    destination = args.output or "stdout"
    logger.info(
        "%s: %d records, %d input rows, %d skipped, %d fallback, "
        "%d warnings, %d bytes",
        destination,
        len(result.records),
        result.stats.read,
        result.stats.skipped,
        result.stats.fallback,
        result.stats.warnings,
        len(data),
    )


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger("neodb")
    args = build_parser().parse_args(argv)
    try:
        run(args, logger)
    except BrokenPipeError:
        # Keep the interpreter from failing again while flushing stdout at exit.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        logger.error("output pipe closed")
        return 1
    except (
        CityGuideFormatError,
        IGoFormatError,
        NeolineDBError,
        OSError,
    ) as error:
        logger.error("%s", error)
        return 1
    return 0
