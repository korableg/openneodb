"""Decoder for SpeedCamOnline iGoExt exports into the common db record shape
(see db_codec's module docstring). Encoding is handled by db_codec.encode()
on the returned data — this module only decodes.
"""
import csv
from collections import Counter, defaultdict
from decimal import Decimal

TYPE_TO_B0 = {192: 0xA5, 68: 0xA2, 199: 0xE9, 206: 0xA4, 227: 0xA5}
DROP_TYPES = {193, 194, 197}


def _quant(s, mode):
    """Vendor coordinate quantization: lat -> ceil(y*1e4), lon -> floor(x*1e4)."""
    v = Decimal(s) * 10000
    return int(v.to_integral_value(rounding="ROUND_CEILING" if mode == "ceil" else "ROUND_FLOOR"))


def decode(txt_path, donor):
    """Decode an iGoExt txt export into {date, build, ver, fname, recs, stats},
    using `donor` (a db_codec.decode() result) for meta fields and to inherit
    subtype/flags/alert-profile for cameras also present in it; new cameras
    get defaults per iGoExt TYPE.
    """
    donor_idx = {}
    for c in donor["recs"]:
        donor_idx[(c["lat"], c["lon"], c["angle"])] = c
    prof = defaultdict(Counter)
    for c in donor["recs"]:
        prof[(c["type"], c["speed"])][(c["flags"], c["b23"])] += 1

    def defaults(b0, spd):
        key = (b0, spd)
        if key not in prof:
            key = max((k for k in prof if k[0] == b0), key=lambda k: sum(prof[k].values()), default=None)
        if key is None:
            return 0, 0x66
        return prof[key].most_common(1)[0][0]

    recs, inherited, created, dropped = [], 0, 0, 0
    with open(txt_path, newline="") as f:
        for row in csv.DictReader(f):
            if not row["TYPE"]:
                dropped += 1
                continue
            ty = int(row["TYPE"])
            if ty in DROP_TYPES:
                dropped += 1
                continue
            lat = _quant(row["Y"], "ceil")
            lon = _quant(row["X"], "floor")
            ang = int(row["DIRECTION"])
            spd = int(row["SPEED"])
            d = donor_idx.get((lat, lon, ang))
            if d is not None:
                inherited += 1
                recs.append(dict(d, lat=lat, lon=lon, angle=ang, speed=spd))
            else:
                created += 1
                b0 = TYPE_TO_B0.get(ty, 0xA5)
                flg, b23 = defaults(b0, spd)
                recs.append(dict(type=b0, lat=lat, lon=lon, angle=ang, speed=spd,
                                 b11=0, flags=flg, b22=(0xEA if flg & 0x20 else 0xEF),
                                 b23=b23))
    return dict(
        date=donor["date"], build=donor["build"], ver=donor["ver"], fname=donor["fname"],
        recs=recs, stats=dict(inherited=inherited, created=created, dropped=dropped),
    )
