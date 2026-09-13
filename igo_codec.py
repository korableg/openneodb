"""Decoder for SpeedCamOnline iGoExt exports into the common db record shape
(see db_codec's module docstring). Encoding is handled by db_codec.encode()
on the returned data — this module only decodes.
"""
import csv

import common

TYPE_TO_B0 = {192: 0xA5, 68: 0xA2, 199: 0xE9, 206: 0xA4, 227: 0xA5}
DROP_TYPES = {193, 194, 197}


def decode(txt_path, donor):
    """Decode an iGoExt txt export into {date, build, ver, fname, recs, stats},
    using `donor` (a db_codec.decode() result) for meta fields and to inherit
    subtype/flags/alert-profile for cameras also present in it; new cameras
    get defaults per iGoExt TYPE.
    """
    donor_idx = common.donor_index(donor)
    defaults = common.defaults_picker(donor)
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
            lat = common.quant_lat(row["Y"])
            lon = common.quant_lon(row["X"])
            ang = int(row["DIRECTION"])
            spd = int(row["SPEED"])
            d = donor_idx.get((lat, lon, ang))
            if d is not None:
                inherited += 1
                recs.append(dict(d, lat=lat, lon=lon, angle=ang, speed=spd))
            else:
                created += 1
                recs.append(common.new_record(TYPE_TO_B0.get(ty, 0xA5), lat, lon, ang, spd, defaults))
    return dict(
        date=donor["date"], build=donor["build"], ver=donor["ver"], fname=donor["fname"],
        recs=recs, stats=dict(inherited=inherited, created=created, dropped=dropped),
    )
