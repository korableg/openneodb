"""Neoline X-COP *_Baza_GPS.db binary codec: decode (bytes -> records) and
encode (records -> bytes). See FORMAT.md for the field-level spec.

Both directions share the same record shape, the common interface also
produced by igo_codec.decode():
  {date, build, ver, fname, recs}
  recs: list of dict(type, lat, lon, angle, speed, b11, flags, b22, b23)
"""
import struct

MAGIC = b"BRMSC\x00\x00JHKIM\x00\x00\x00\x00"
SUBHDR = bytes.fromhex("24000200000000")
MASK_LAT = 0xC4D382
MASK_LON = 0x80464A
MASK_ANGLE = 0x0013
MASK_SPEED = 0x8A
MASK_DIST = 0x78  # byte 23: alert distance in decametres, XORed
MASK_B11 = 0xAC
MASK_FLAGS = 0x6F
CONST_B1 = 0xAE
CONST_B5 = 0x99
CONST_B13_20 = bytes.fromhex("3a563c0c5a08733b")
LAT_BIAS = 0x100000


def dist_to_b23(dist_m):
    """Alert distance in metres -> raw byte 23 ((dist div 10) XOR 0x78);
    0x78 itself means "not set". recs keep b23 raw for byte-exact roundtrip,
    so the XOR is applied here, not in decode()/encode()."""
    return ((dist_m // 10) ^ MASK_DIST) & 0xFF


def b23_to_dist(b23):
    """Raw byte 23 -> alert distance in metres."""
    return (b23 ^ MASK_DIST) * 10


def decode(path):
    data = open(path, "rb").read()
    if data[:16] != MAGIC:
        raise ValueError("bad magic")
    if data[0x100:0x107] != SUBHDR:
        raise ValueError("bad subheader")
    (payload_len,) = struct.unpack_from("<I", data, 0x107)
    if payload_len != len(data) - 0x400:
        raise ValueError("payload length mismatch")
    fname = data[0x200:0x400].split(b"\x00")[0]
    meta = data[0x400:0x440]
    date = meta[16:24].rstrip(b"\x00").decode()
    build = meta[32:36]
    ver = meta[36:39]
    (count,) = struct.unpack_from("<I", meta, 48)
    blob = data[0x440:]
    if len(blob) != count * 24:
        raise ValueError("record area size mismatch")
    recs = []
    for i in range(count):
        r = blob[i * 24 : (i + 1) * 24]
        if r[1] != CONST_B1 or r[5] != CONST_B5 or r[13:21] != CONST_B13_20:
            raise ValueError(f"record {i}: unexpected constant bytes: {r.hex()}")
        recs.append(
            dict(
                type=r[0],
                lat=(LAT_BIAS - ((r[2] << 16 | r[3] << 8 | r[4]) ^ MASK_LAT)),
                lon=((r[6] << 16 | r[7] << 8 | r[8]) ^ MASK_LON),
                angle=((r[9] << 8 | r[10]) ^ MASK_ANGLE),
                speed=r[12] ^ MASK_SPEED,
                b11=r[11] ^ MASK_B11,
                flags=r[21] ^ MASK_FLAGS,
                b22=r[22],
                b23=r[23],
            )
        )
    return dict(date=date, build=build, ver=ver, fname=fname, recs=recs)


def _encode_record(c):
    r = bytearray(24)
    r[0] = c["type"]
    r[1] = CONST_B1
    latv = (LAT_BIAS - c["lat"]) ^ MASK_LAT
    r[2:5] = latv.to_bytes(3, "big")
    r[5] = CONST_B5
    r[6:9] = (c["lon"] ^ MASK_LON).to_bytes(3, "big")
    r[9:11] = (c["angle"] ^ MASK_ANGLE).to_bytes(2, "big")
    r[11] = c["b11"] ^ MASK_B11
    r[12] = c["speed"] ^ MASK_SPEED
    r[13:21] = CONST_B13_20
    r[21] = c["flags"] ^ MASK_FLAGS
    r[22] = c["b22"]
    r[23] = c["b23"]
    return bytes(r)


def encode(dbdata):
    recs = sorted(dbdata["recs"], key=lambda c: -c["lat"])  # lat DESC, stable
    blob = b"".join(_encode_record(c) for c in recs)
    date = dbdata["date"].encode().ljust(8, b"\x00")
    meta = (
        b"\xff" * 16
        + date
        + b"\xff" * 8
        + dbdata["build"]
        + dbdata["ver"]
        + b"\xff" * 9
        + struct.pack("<I", len(recs))
        + b"\xff" * 12
    )
    head = bytearray(0x400)
    head[0:16] = MAGIC
    head[0x100:0x107] = SUBHDR
    struct.pack_into("<I", head, 0x107, len(meta) + len(blob))
    fn = dbdata.get("fname") or b""
    head[0x200 : 0x200 + len(fn)] = fn
    return bytes(head) + meta + blob
