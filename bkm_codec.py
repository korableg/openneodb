"""CityGuide (СитиГИД) Speedcam v2 codec (SpeedCam.bkm): decode
(bytes -> rows) and encode (rows -> bytes) are byte-exact inverses;
to_dbdata() maps the rows into the common db record shape (see db_codec).

The file is cp1251 text with CRLF line ends. Header line `2|Radars|1251`
= (format version, object class, codepage). Every object line is
`<type>|<id>|<lat>|<lon>|` followed by `<tag>|<value>|` pairs; an absent
attribute just omits its pair, the line always ends with `|`. Known tags:
1709 speed limit km/h (0 = uncontrolled), 1713 direction kind (0 one way,
1 both, 2 all), 1705 azimuth 0..359, 1706 alert distance in metres.

The 1705 azimuth is the camera's facing bearing, not the controlled
traffic direction: against the same-day SpeedCamOnline iGoExt export,
72717 of 72727 coordinate-matched rows differ from its DIRECTION by
exactly 180 deg. The db (like iGoExt) wants the traffic direction, so
to_dbdata() adds 180.
"""
import common
import db_codec

TAG_SPEED = "1709"
TAG_ANGLE = "1705"
TAG_DIRTYPE = "1713"
TAG_DIST = "1706"

# Fixed wrapper meta for from-scratch builds, taken from the 9000c
# reference release once and hardcoded — the date is overridable in the
# CLI, the rest is what the target firmware expects to see.
META_DATE = "140925"
META_BUILD = bytes.fromhex("3244f839")
META_VER = bytes.fromhex("000101")
META_FNAME = b""

# CityGuide object type -> db record type (byte 0), derived by coordinate
# match with the same-day iGoExt export and its §4.1 mapping: 18059/18951
# are the stationary-camera family (192 -> A5), 18952 mobile ambush
# (68 -> A2), 18958/18950 paired/average-speed control (199 -> E9).
# 18925 has no iGoExt counterpart (speed 0, ~50 m distance: stop-line /
# traffic-light control) and falls to the A5 default.
TYPE_TO_B0 = {"18059": 0xA5, "18951": 0xA5, "18952": 0xA2, "18958": 0xE9, "18950": 0xE9}
DEFAULT_B0 = 0xA5

ENCODING = "cp1251"


def decode(path):
    """Parse a .bkm into {header: (ver, label, codepage), rows}, each row
    {type, name, lat, lon, tags: [(tag, value), ...]} with every value kept
    as its original string so encode() can rebuild the file byte-exactly."""
    lines = open(path, "rb").read().decode(ENCODING).split("\r\n")
    if lines and lines[-1] == "":
        lines.pop()
    header = tuple(lines[0].split("|"))
    if len(header) != 3:
        raise ValueError(f"bad header line: {lines[0]!r}")
    rows = []
    for i, ln in enumerate(lines[1:], start=2):
        parts = ln.split("|")
        if parts[-1] != "" or len(parts) < 5 or len(parts) % 2 == 0:
            raise ValueError(f"line {i}: malformed row: {ln!r}")
        parts.pop()
        rows.append(dict(type=parts[0], name=parts[1], lat=parts[2], lon=parts[3],
                         tags=list(zip(parts[4::2], parts[5::2]))))
    return dict(header=header, rows=rows)


def encode(bkmdata):
    out = ["|".join(bkmdata["header"])]
    for r in bkmdata["rows"]:
        fields = [r["type"], r["name"], r["lat"], r["lon"]]
        for tag, val in r["tags"]:
            fields += [tag, val]
        out.append("|".join(fields) + "|")
    return ("\r\n".join(out) + "\r\n").encode(ENCODING)


def to_dbdata(bkmdata):
    """Build {date, build, ver, fname, recs} from bkm rows alone — no donor
    db. Every record field is derived from the bkm attributes (accuracy
    figures are vs 53k coordinate-matched records of the vendor base):
    coordinates, angle (+180°), speed and byte 23 (tag 1706 via
    db_codec.dist_to_b23; "not set" without the tag) are exact; b11 is 0
    (100%); flags are the two derivable bits — 0x02 non-radar complex for
    type 18952, 0x20 all-directions camera for 1713=2 (96% of dirtype-2
    records vs 0% otherwise) — which covers 97.5% of significant bits;
    b22 follows flags (99.6%). The vendor's fine-grained subtype of byte 0
    (~29 codes) is NOT derivable from the 6 bkm categories — TYPE_TO_B0
    hits the exact byte in ~31%, the alert class is right. Wrapper meta is
    the hardcoded 9000c reference release."""
    recs = []
    for r in bkmdata["rows"]:
        tags = dict(r["tags"])
        flags = 0
        if r["type"] == "18952":
            flags |= 0x02
        if tags.get(TAG_DIRTYPE) == "2":
            flags |= 0x20
        recs.append(dict(
            type=TYPE_TO_B0.get(r["type"], DEFAULT_B0),
            lat=common.quant_lat(r["lat"]),
            lon=common.quant_lon(r["lon"]),
            angle=(int(tags[TAG_ANGLE]) + 180) % 360 if TAG_ANGLE in tags else 0,
            speed=int(tags.get(TAG_SPEED, "0")),
            b11=0,
            flags=flags,
            b22=(0xEA if flags & 0x20 else 0xEF),
            b23=(db_codec.dist_to_b23(int(tags[TAG_DIST]))
                 if TAG_DIST in tags else db_codec.MASK_DIST),
        ))
    return dict(date=META_DATE, build=META_BUILD, ver=META_VER, fname=META_FNAME,
                recs=recs)
