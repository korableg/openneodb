# neoline

Reference codec + CLI for Neoline X-COP `*_Baza_GPS.db` camera database
files. Reverse-engineered from official update files — full field-level spec
in [FORMAT.md](FORMAT.md).

Lets you build your own `*_Baza_GPS.db` from a SpeedCamOnline iGoExt export,
or repackage a db from another device/firmware version so the target device
accepts it.

## Layout

- `neodb.py` — CLI entry point (argparse, dispatch).
- `db_codec.py` — binary `.db` codec: `decode()` (bytes -> records) and
  `encode()` (records -> bytes). Both directions and `igo_codec.decode()`
  share one record shape: `{date, build, ver, fname, recs}`, `recs` = list of
  `dict(type, lat, lon, angle, speed, b11, flags, b22, b23)`.
- `igo_codec.py` — decoder only: turns a SpeedCamOnline iGoExt export into
  that same record shape, using a donor db to inherit subtype/flags/alert
  profile for matching cameras.
- `reference/X-COP_9000c_Baza_GPS.db` — fixed donor used by every `encode-*`
  command for meta fields (date/build/ver/fname) and, for `encode-igo`, for
  per-camera profile inheritance.

No third-party dependencies — stdlib only (Python 3.7+).

## Usage

```
python3 neodb.py encode-igo <igoext.txt> <out.db> [--date DDMMYY] [--fname NAME]
python3 neodb.py encode-db  <source.db>  <out.db> [--date DDMMYY] [--fname NAME]
python3 neodb.py verify     <file.db>
```

**encode-igo** — build a db from a SpeedCamOnline iGoExt export
(`IDX,X,Y,TYPE,SPEED,DIRTYPE,DIRECTION`). Cameras matching the donor by
(lat, lon, bearing) inherit its subtype/flags/b23; new cameras get defaults
by iGoExt TYPE (192→`a5`, 68→`a2`, 199→`e9`, 206→`a4`, 227→`a5`;
193/194/197 dropped, as the vendor does). Meta comes from the donor, unless
overridden.

```
python3 neodb.py encode-igo SpeedCamOnline.ru_2026-08-22_iGoExt_Rus.txt out.db
```

**encode-db** — take records as-is from another db (e.g. a newer firmware
release) and re-stamp meta (date/build/ver/fname) from the donor, so the
result matches the wrapper the target device expects. No coordinate
matching — the source records are already valid.

```
python3 neodb.py encode-db X-COP_R750_Baza_GPS.db out.db
```

**verify** — parse a db and rebuild it, checking the result is byte-identical
to the original. Exits non-zero on mismatch.

```
python3 neodb.py verify X-COP_R750_Baza_GPS.db
```

## Spec

See [FORMAT.md](FORMAT.md) for the header/record byte layout, XOR masks,
camera type mapping, and open questions.
