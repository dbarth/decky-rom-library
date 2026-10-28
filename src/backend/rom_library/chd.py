"""Read MAME's CHD images, version 5: the hunk map and the zlib, LZMA and Huffman codecs, for disc
images of CDs, GD-ROMs and DVDs. FLAC and Zstandard hunks cannot be read: Decky's Python lacks them.

Written from the format as MAME's chd.cpp documents it (BSD-3-Clause)."""
import binascii
import lzma
import re
import struct
import zlib

HEADER_V5 = 124
CD_FRAME = 2448
CD_SECTOR = 2352
CD_SUBCODE = 96
SYNC = b"\x00" + b"\xff" * 10 + b"\x00"
# chdman starts each track of a CD on a multiple of 4 frames.
CD_TRACK_PADDING = 4
# Map entry kinds after decoding.
CODEC_0, CODEC_3, NONE, SELF, PARENT = 0, 3, 4, 5, 6
RLE_SMALL, RLE_LARGE, SELF_0, SELF_1, PARENT_SELF, PARENT_0, PARENT_1 = 7, 8, 9, 10, 11, 12, 13
TRACK = re.compile(rb"(\w+):(\S+)")
# The Reed-Solomon parity of a Mode 1 sector, from ECMA-130 annex A, over GF(2^8) with
# x^8 + x^4 + x^3 + x^2 + 1. P covers 86 columns of 24 bytes from offset 12, Q 52 diagonals of 43
# bytes over the same bytes and P.
GF_DOUBLE = bytes(((i << 1) ^ (0x11D if i & 0x80 else 0)) & 0xFF for i in range(256))
GF_THIRD = bytearray(256)
for _i in range(256):
    GF_THIRD[GF_DOUBLE[_i] ^ _i] = _i
P_PARITY, Q_PARITY = 2076, 2248
P_VECTORS = [[12 + 86 * m + b for m in range(24)] for b in range(86)]
Q_VECTORS = [[12 + 2 * ((44 * m + 43 * (b // 2)) % 1118) + b % 2 for m in range(43)] for b in range(52)]


class Unreadable(Exception):
    pass


class Bits:
    """Read a byte string as a stream of bits, the most significant first."""

    def __init__(self, data):
        self.data = data
        self.pos = 0

    def read(self, n):
        if n == 0:
            return 0
        start, end = self.pos >> 3, (self.pos + n + 7) >> 3
        chunk = int.from_bytes(self.data[start:end].ljust(end - start, b"\0"), "big")
        shift = (end << 3) - self.pos - n
        self.pos += n
        return (chunk >> shift) & ((1 << n) - 1)

    def peek(self, n):
        value = self.read(n)
        self.pos -= n
        return value


class Huffman:
    """A canonical Huffman decoder as MAME's huffman.cpp builds it."""

    def __init__(self, codes, maxbits):
        self.codes = codes
        self.maxbits = maxbits
        self.lengths = [0] * codes
        self.lookup = None

    def build(self):
        count = [0] * 33
        for n in self.lengths:
            if n > self.maxbits:
                raise Unreadable("Huffman code too long")
            count[n] += 1
        # Codes go from the longest to the shortest, each length starting where the longer ones end.
        start = 0
        for n in range(32, 0, -1):
            following = (start + count[n]) >> 1
            if n != 1 and following * 2 != start + count[n]:
                raise Unreadable("bad Huffman tree")
            count[n] = start
            start = following
        lookup = [(0, 0)] * (1 << self.maxbits)
        for symbol, n in enumerate(self.lengths):
            if n:
                code = count[n]
                count[n] += 1
                shift = self.maxbits - n
                for i in range(code << shift, (code + 1) << shift):
                    lookup[i] = (symbol, n)
        self.lookup = lookup

    def decode(self, bits):
        symbol, n = self.lookup[bits.peek(self.maxbits)]
        bits.pos += n
        return symbol

    def import_rle(self, bits):
        width = 5 if self.maxbits >= 16 else 4 if self.maxbits >= 8 else 3
        i = 0
        while i < self.codes:
            n = bits.read(width)
            if n != 1:
                self.lengths[i] = n
                i += 1
                continue
            n = bits.read(width)
            if n == 1:
                self.lengths[i] = 1
                i += 1
                continue
            repeat = bits.read(width) + 3
            for _ in range(repeat):
                if i < self.codes:
                    self.lengths[i] = n
                    i += 1
        self.build()

    def import_huffman(self, bits):
        # A small tree of 24 codes encodes the code lengths of the big one.
        small = Huffman(24, 6)
        small.lengths[0] = bits.read(3)
        start = bits.read(3) + 1
        count = 0
        for i in range(1, 24):
            if i < start or count == 7:
                small.lengths[i] = 0
            else:
                count = bits.read(3)
                small.lengths[i] = 0 if count == 7 else count
        small.build()
        rle_bits = (self.codes - 9).bit_length()
        i, last = 0, 0
        while i < self.codes:
            value = small.decode(bits)
            if value:
                last = value - 1
                self.lengths[i] = last
                i += 1
            else:
                repeat = bits.read(3) + 2
                if repeat == 9:
                    repeat += bits.read(rle_bits)
                while repeat and i < self.codes:
                    self.lengths[i] = last
                    i += 1
                    repeat -= 1
        self.build()


def inflate(data, size):
    return zlib.decompressobj(-15).decompress(data, size)


def unlzma(data, size, hunk_bytes):
    # chdman writes raw LZMA at level 9 with the dictionary cut to the hunk size.
    dictionary = max(4096, 1 << (hunk_bytes - 1).bit_length())
    filters = [{"id": lzma.FILTER_LZMA1, "dict_size": dictionary, "lc": 3, "lp": 0, "pb": 2}]
    return lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=filters).decompress(data, size)


def unhuff(data, size):
    bits = Bits(data)
    tree = Huffman(256, 16)
    tree.import_huffman(bits)
    return bytes(tree.decode(bits) for _ in range(size))


def fill_parity(sector, vectors, at):
    """Write the two parity bytes of each vector: their sum and their sum weighted by powers of 2
    in GF(2^8) come to zero."""
    for b, vector in enumerate(vectors):
        weighted = total = 0
        for i in vector:
            total ^= sector[i]
            weighted = GF_DOUBLE[weighted ^ sector[i]]
        first = GF_THIRD[GF_DOUBLE[weighted] ^ total]
        sector[at + b] = first
        sector[at + len(vectors) + b] = total ^ first


def fill_ecc(sector):
    """Write the P and Q parity of a raw Mode 1 sector. Q covers P: P comes first."""
    fill_parity(sector, P_VECTORS, P_PARITY)
    fill_parity(sector, Q_VECTORS, Q_PARITY)


class Chd:
    def __init__(self, path):
        self.f = open(path, "rb")
        head = self.f.read(HEADER_V5)
        if head[:8] != b"MComprHD":
            raise Unreadable("not a CHD image")
        version = struct.unpack(">I", head[12:16])[0]
        if version != 5:
            raise Unreadable(f"CHD version {version}")
        self.codecs = [head[16 + 4 * i:20 + 4 * i] for i in range(4)]
        self.size, self.map_offset, self.meta_offset = struct.unpack(">QQQ", head[32:56])
        self.hunk_bytes, self.unit_bytes = struct.unpack(">II", head[56:64])
        self.parent = head[84:104].strip(b"\0")
        self.hunks = (self.size + self.hunk_bytes - 1) // self.hunk_bytes
        self.map = None

    def close(self):
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def metadata(self):
        """Return [(tag, data)] for each metadata entry, in order."""
        out, offset = [], self.meta_offset
        while offset and len(out) < 1000:
            self.f.seek(offset)
            head = self.f.read(16)
            length = int.from_bytes(head[5:8], "big")
            out.append((head[:4], self.f.read(length)))
            offset = int.from_bytes(head[8:16], "big")
        return out

    def read_map(self):
        """Decode the compressed map into (kind, length, offset, crc) per hunk."""
        if self.map is not None:
            return self.map
        if not any(self.codecs):
            raise Unreadable("uncompressed CHD")
        self.f.seek(self.map_offset)
        head = self.f.read(16)
        map_bytes = struct.unpack(">I", head[:4])[0]
        offset = int.from_bytes(head[4:10], "big")
        length_bits, self_bits, parent_bits = head[12], head[13], head[14]
        bits = Bits(self.f.read(map_bytes))
        tree = Huffman(16, 8)
        tree.import_rle(bits)
        kinds, last, repeat = [], 0, 0
        for _ in range(self.hunks):
            if repeat:
                kinds.append(last)
                repeat -= 1
                continue
            value = tree.decode(bits)
            # A run repeats the last kind for this hunk and the count that follows.
            if value == RLE_SMALL:
                repeat = 2 + tree.decode(bits)
            elif value == RLE_LARGE:
                repeat = 2 + 16 + (tree.decode(bits) << 4)
                repeat += tree.decode(bits)
            else:
                last = value
            kinds.append(last)
        entries, last_self, last_parent = [], 0, 0
        for hunk, kind in enumerate(kinds):
            at, length, crc = offset, 0, None
            if kind <= CODEC_3:
                length = bits.read(length_bits)
                offset += length
                crc = bits.read(16)
            elif kind == NONE:
                length = self.hunk_bytes
                offset += length
                crc = bits.read(16)
            elif kind == SELF:
                at = last_self = bits.read(self_bits)
            elif kind == PARENT:
                at = last_parent = bits.read(parent_bits)
            elif kind in (SELF_0, SELF_1):
                if kind == SELF_1:
                    last_self += 1
                kind, at = SELF, last_self
            elif kind == PARENT_SELF:
                kind = PARENT
                at = last_parent = hunk * self.hunk_bytes // self.unit_bytes
            elif kind in (PARENT_0, PARENT_1):
                if kind == PARENT_1:
                    last_parent += self.hunk_bytes // self.unit_bytes
                kind, at = PARENT, last_parent
            entries.append((kind, length, at, crc))
        self.map = entries
        return entries

    def hunk(self, index, depth=0):
        """Return the bytes of one hunk."""
        kind, length, at, crc = self.read_map()[index]
        if kind == SELF:
            if depth > 8:
                raise Unreadable("self reference loop")
            return self.hunk(at, depth + 1)
        if kind == PARENT:
            raise Unreadable("the image needs its parent CHD")
        self.f.seek(at)
        data = self.f.read(length)
        if kind == NONE:
            out = data
        else:
            out = self.decompress(self.codecs[kind], data)
        if crc is not None and binascii.crc_hqx(out, 0xFFFF) != crc:
            raise Unreadable(f"hunk {index} fails its CRC")
        return out

    def decompress(self, codec, data):
        size = self.hunk_bytes
        if codec == b"zlib":
            return inflate(data, size)
        if codec == b"lzma":
            return unlzma(data, size, size)
        if codec == b"huff":
            return unhuff(data, size)
        if codec in (b"cdzl", b"cdlz"):
            return self.decompress_cd(codec, data)
        raise Unreadable(f"{codec.decode(errors='replace')} hunks are not supported")

    def decompress_cd(self, codec, data):
        """Rebuild the frames of a CD hunk: sector data, then subcode. chdman drops the sync header
        and ECC of a sector whose ECC checks: a bit per frame marks them, and the CRC covers them."""
        frames = self.hunk_bytes // CD_FRAME
        length_bytes = 2 if self.hunk_bytes < 65536 else 3
        ecc_bytes = (frames + 7) // 8
        head = ecc_bytes + length_bytes
        base_length = int.from_bytes(data[ecc_bytes:head], "big")
        base = data[head:head + base_length]
        sectors_size = frames * CD_SECTOR
        if codec == b"cdzl":
            sectors = inflate(base, sectors_size)
        else:
            sectors = unlzma(base, sectors_size, sectors_size)
        subcode = inflate(data[head + base_length:], frames * CD_SUBCODE)
        subcode = subcode.ljust(frames * CD_SUBCODE, b"\0")
        out = bytearray()
        for i in range(frames):
            sector = bytearray(sectors[i * CD_SECTOR:(i + 1) * CD_SECTOR])
            if data[i // 8] & (1 << (i % 8)):
                sector[:12] = SYNC
                fill_ecc(sector)
            out += sector + subcode[i * CD_SUBCODE:(i + 1) * CD_SUBCODE]
        return bytes(out)

    # Byte and frame access

    def read(self, offset, size):
        """Return size bytes of the logical image from offset."""
        out = bytearray()
        while size > 0 and offset < self.size:
            index, skip = divmod(offset, self.hunk_bytes)
            data = self.hunk(index)[skip:skip + size]
            out += data
            offset += len(data)
            size -= len(data)
        return bytes(out)

    def tracks(self):
        """Return the tracks of a CD or GD-ROM: [{track, type, frames, start}], start being the
        first frame of the track in the image."""
        out, start = [], 0
        for tag, data in self.metadata():
            if tag not in (b"CHT2", b"CHGD", b"CHTR", b"CHCD"):
                continue
            fields = {k.decode(): v.decode() for k, v in TRACK.findall(data)}
            if "FRAMES" not in fields:
                continue
            frames = int(fields["FRAMES"])
            out.append({"track": int(fields.get("TRACK", len(out) + 1)), "type": fields.get("TYPE", ""),
                        "frames": frames, "start": start})
            start += -(-frames // CD_TRACK_PADDING) * CD_TRACK_PADDING
        return out

    def frame(self, index):
        """Return one raw frame of a CD image: 2352 bytes of sector, then 96 of subcode."""
        return self.read(index * CD_FRAME, CD_FRAME)
