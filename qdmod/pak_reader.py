"""Read-only access to Unreal Engine 4 .pak files (unencrypted).

Two index layouts are supported:
  * version 11 (UE 4.27 "path hash + full directory" index) - the game's main pak
  * versions 1-7 "legacy" index - what our own mod pak (version 3) uses

The main pak is only ever opened for reading.
"""
import hashlib
import os
import struct
import zlib

from .binio import Reader

PAK_MAGIC = 0x5A6F12E1
ENTRY_HEADER_SIZE_UNCOMPRESSED = 53  # serialized FPakEntry in front of each file's data


class PakError(Exception):
    """The file is not a pak we understand (corrupt, encrypted, unexpected version...)."""


class PakEntry:
    __slots__ = ("path", "offset", "size", "usize", "comp", "encrypted", "blocks", "sha1")

    def __init__(self, path, offset, size, usize, comp, encrypted, blocks, sha1=None):
        self.path, self.offset, self.size, self.usize = path, offset, size, usize
        self.comp, self.encrypted, self.blocks, self.sha1 = comp, encrypted, blocks, sha1

    @property
    def data_offset(self):
        if not self.comp:
            return self.offset + ENTRY_HEADER_SIZE_UNCOMPRESSED
        return self.offset + ENTRY_HEADER_SIZE_UNCOMPRESSED + 4 + 16 * len(self.blocks)


class PakFile:
    """Open a pak and expose `entries` ({full path: PakEntry}) and `read(path)`.

    Paths include the mount point, e.g. '../../../QueensDomain/Content/Foo.uasset'.
    """

    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        try:
            self.file_size = os.fstat(self.f.fileno()).st_size
            self._read_footer()
            self._read_index()
        except PakError:
            self.f.close()
            raise
        except (ValueError, struct.error, UnicodeDecodeError, MemoryError) as e:
            self.f.close()
            raise PakError(f"{os.path.basename(path)} looks damaged or is not a pak file ({e})") from e

    # ----------------------------------------------------------------- footer
    # (footer size, has key guid, has encrypted flag, frozen-index byte, compression name slots, versions)
    _FOOTERS = (
        (221, True, True, False, 5, (10, 11)),
        (222, True, True, True, 5, (9,)),
        (189, True, True, False, 4, (8,)),
        (61, True, True, False, 0, (7,)),
        (45, False, True, False, 0, (4, 5, 6)),
        (44, False, False, False, 0, (1, 2, 3)),
    )

    def _read_footer(self):
        for size, has_guid, has_enc, frozen, n_names, versions in self._FOOTERS:
            if self.file_size < size:
                continue
            self.f.seek(self.file_size - size)
            r = Reader(self.f.read(size))
            if has_guid:
                r.take(16)
            encrypted_index = r.u8() if has_enc else 0
            if r.u32() != PAK_MAGIC:
                continue
            self.version = r.u32()
            if self.version not in versions:
                continue
            self.index_offset = r.i64()
            self.index_size = r.i64()
            self.index_hash = bytes(r.take(20))
            if frozen:
                r.u8()
            self.compression = [bytes(r.take(32)).rstrip(b"\0").decode("ascii", "replace")
                                for _ in range(n_names)]
            if encrypted_index:
                raise PakError("this pak has an encrypted index, which is not supported")
            if not (0 < self.index_offset and self.index_offset + self.index_size <= self.file_size):
                raise PakError("pak footer points outside the file")
            self.footer_size = size
            return
        raise PakError(f"{os.path.basename(self.path)} is not a valid .pak file (no pak footer found)")

    # ------------------------------------------------------------------ index
    def _read_index(self):
        self.f.seek(self.index_offset)
        self.index_bytes = self.f.read(self.index_size)
        if len(self.index_bytes) != self.index_size:
            raise PakError("pak index is truncated")
        if self.version >= 10:
            self._read_index_v10plus()
        else:
            self._read_index_legacy()

    def _read_index_legacy(self):
        r = Reader(self.index_bytes)
        self.mount = r.fstr()
        count = r.i32()
        self.entries = {}
        for _ in range(count):
            name = r.fstr()
            e = self._read_full_entry(r, self.mount + name)
            self.entries[e.path] = e

    def _read_full_entry(self, r, path):
        offset, size, usize = r.i64(), r.i64(), r.i64()
        comp = r.i32()
        if self.version <= 1:
            r.i64()  # timestamp
        sha1 = bytes(r.take(20))
        blocks = []
        if self.version >= 3:
            if comp:
                blocks = [(r.i64(), r.i64()) for _ in range(r.i32())]
            encrypted = bool(r.u8())
            r.u32()  # compression block size
        else:
            encrypted = False
        return PakEntry(path, offset, size, usize, comp, encrypted, blocks, sha1)

    def _read_index_v10plus(self):
        r = Reader(self.index_bytes)
        self.mount = r.fstr()
        r.i32()  # file count
        r.u64()  # path hash seed
        if r.i32():  # has path hash index
            r.i64(); r.i64(); r.take(20)
        if not r.i32():
            raise PakError("pak has no full directory index")
        dir_off, dir_size = r.i64(), r.i64()
        r.take(20)
        encoded = r.take(r.i32())  # bit-packed FPakEntry records, addressed by byte offset
        self.f.seek(dir_off)
        d = Reader(self.f.read(dir_size))
        self.entries = {}
        for _ in range(d.i32()):
            dirname = d.fstr()
            for _ in range(d.i32()):
                fname = d.fstr()
                loc = d.i32()
                path = self.mount + dirname + fname
                if loc < 0:
                    continue  # entries stored in the (unused here) non-encoded list
                self.entries[path] = self._decode_entry(encoded, loc, path)

    @staticmethod
    def _decode_entry(enc, loc, path):
        r = Reader(enc, loc)
        v = r.u32()
        cm = (v >> 23) & 0x3F
        if (v & 0x3F) == 0x3F:
            r.u32()  # compression block size
        off = r.u32() if v & (1 << 31) else r.u64()
        usz = r.u32() if v & (1 << 30) else r.u64()
        sz = (r.u32() if v & (1 << 29) else r.u64()) if cm else usz
        encrypted = bool(v & (1 << 22))
        nb = (v >> 6) & 0xFFFF
        blocks = []
        if nb == 1 and not encrypted:
            blocks = [sz]
        elif nb:
            blocks = [r.u32() for _ in range(nb)]
        return PakEntry(path, off, sz, usz, cm, encrypted, blocks)

    # ------------------------------------------------------------------- data
    def read(self, path_or_entry):
        e = path_or_entry if isinstance(path_or_entry, PakEntry) else self.entries[path_or_entry]
        if e.encrypted:
            raise PakError(f"{e.path} is encrypted")
        self.f.seek(e.data_offset)
        if not e.comp:
            data = self.f.read(e.usize)
            if len(data) != e.usize:
                raise PakError(f"{e.path} is truncated")
            return data
        method = self.compression[e.comp - 1].lower() if e.comp - 1 < len(self.compression) else ""
        if method != "zlib":
            raise PakError(f"{e.path} uses unsupported compression '{method}'")
        out = bytearray()
        for b in e.blocks:
            out += zlib.decompress(self.f.read(b if isinstance(b, int) else b[1] - b[0]))
        return bytes(out)

    def read_entry_header(self, e):
        """Raw serialized FPakEntry stored in front of an uncompressed file's data."""
        self.f.seek(e.offset)
        return self.f.read(ENTRY_HEADER_SIZE_UNCOMPRESSED)

    def index_hash_ok(self):
        return hashlib.sha1(self.index_bytes).digest() == self.index_hash

    def close(self):
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
