"""Shared helpers for building db records from external exports: vendor
coordinate quantization, donor-db lookup index and per-(type, speed)
default alert profiles (see db_codec's module docstring for the record
shape). Used by igo_codec and bkm_codec.
"""
from collections import Counter, defaultdict
from decimal import Decimal


def quant_lat(s):
    """Vendor coordinate quantization: lat -> ceil(y*1e4)."""
    return int((Decimal(s) * 10000).to_integral_value(rounding="ROUND_CEILING"))


def quant_lon(s):
    """Vendor coordinate quantization: lon -> floor(x*1e4)."""
    return int((Decimal(s) * 10000).to_integral_value(rounding="ROUND_FLOOR"))


def donor_index(donor):
    """(lat, lon, angle) -> donor record, for subtype/flags inheritance."""
    return {(c["lat"], c["lon"], c["angle"]): c for c in donor["recs"]}


def defaults_picker(donor):
    """Return defaults(b0, speed) -> (flags, b23): the donor's modal alert
    profile for that (type, speed), falling back to the type's biggest
    profile, then to (0, 0x66)."""
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

    return defaults


def new_record(b0, lat, lon, angle, speed, defaults):
    """Fresh record with donor-derived default flags/b22/b23."""
    flg, b23 = defaults(b0, speed)
    return dict(type=b0, lat=lat, lon=lon, angle=angle, speed=speed,
                b11=0, flags=flg, b22=(0xEA if flg & 0x20 else 0xEF), b23=b23)
