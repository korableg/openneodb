#!/usr/bin/env python3
"""Neoline X-COP *_Baza_GPS.db toolkit CLI.

Usage:
  neodb.py encode-igo <igoext.txt> <out.db> [--date DDMMYY] [--fname NAME]
  neodb.py encode-db  <source.db>  <out.db> [--date DDMMYY] [--fname NAME]
  neodb.py verify     <file.db>                # parse + byte-exact roundtrip self-check

encode-igo builds a db straight from a SpeedCamOnline iGoExt export
(IDX,X,Y,TYPE,SPEED,DIRTYPE,DIRECTION), using reference/X-COP_9000c_Baza_GPS.db
as the donor for meta fields (date/build/ver/fname, overridable) and for
fine-grained subtype/flags/alert-profile inheritance. Cameras also present in
the donor (same coordinates+bearing) inherit its subtype, flags and alert
profile; new cameras get defaults per iGoExt TYPE (192->a5, 68->a2, 199->e9,
206->a4, 227->a5; 193/194/197 are dropped, as the vendor does).

encode-db takes its records straight from another (e.g. newer-firmware) db
file as-is, but re-stamps meta (date/build/ver/fname) from the same fixed
reference donor, overridable via --date/--fname — the record schema itself
is already valid, only the wrapper the target device expects changes.
"""
import argparse
import sys
from pathlib import Path

import db_codec
import igo_codec

REFERENCE_DB = Path(__file__).resolve().parent / "reference" / "X-COP_9000c_Baza_GPS.db"


def cmd_encode_igo(args):
    donor = db_codec.decode(REFERENCE_DB)
    dbdata = igo_codec.decode(args.txt, donor)
    if args.date:
        dbdata["date"] = args.date
    if args.fname:
        dbdata["fname"] = args.fname.encode()
    stats = dbdata.pop("stats")
    out = db_codec.encode(dbdata)
    Path(args.out).write_bytes(out)
    print(f"{args.out}: {len(dbdata['recs'])} records "
          f"({stats['inherited']} inherited from donor, {stats['created']} new, "
          f"{stats['dropped']} dropped), {len(out)} bytes")


def cmd_encode_db(args):
    src = db_codec.decode(args.src)
    donor = db_codec.decode(REFERENCE_DB)
    dbdata = dict(src)
    dbdata["date"] = args.date or donor["date"]
    dbdata["build"] = donor["build"]
    dbdata["ver"] = donor["ver"]
    dbdata["fname"] = args.fname.encode() if args.fname else donor["fname"]
    out = db_codec.encode(dbdata)
    Path(args.out).write_bytes(out)
    print(f"{args.out}: {len(dbdata['recs'])} records from {args.src}, "
          f"meta from donor (date={dbdata['date']}), {len(out)} bytes")


def cmd_verify(args):
    dbdata = db_codec.decode(args.db)
    rebuilt = db_codec.encode(dbdata)
    orig = Path(args.db).read_bytes()
    same = rebuilt == orig
    print(f"{args.db}: date={dbdata['date']} records={len(dbdata['recs'])} "
          f"roundtrip={'BYTE-IDENTICAL' if same else 'MISMATCH'}")
    sys.exit(0 if same else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("encode-igo"); g.add_argument("txt"); g.add_argument("out")
    g.add_argument("--date", help="DDMMYY, default: donor's date")
    g.add_argument("--fname", help="internal filename field, default: donor's")
    g.set_defaults(fn=cmd_encode_igo)
    e = sub.add_parser("encode-db"); e.add_argument("src"); e.add_argument("out")
    e.add_argument("--date", help="DDMMYY, default: donor's date")
    e.add_argument("--fname", help="internal filename field, default: donor's")
    e.set_defaults(fn=cmd_encode_db)
    v = sub.add_parser("verify"); v.add_argument("db"); v.set_defaults(fn=cmd_verify)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
