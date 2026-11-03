"""Write a simple, uncompressed version-3 pak (legacy index), which UE 4.27 still loads."""
import hashlib
import os
import struct

from .binio import fstring_bytes
from .pak_reader import PAK_MAGIC

PAK_VERSION = 3
MOUNT_POINT = "../../../"


def _entry_record(offset, data):
    # FPakEntry (v3): offset, size, uncompressed size, compression method, SHA1,
    # [compression blocks - none], bEncrypted, compression block size.
    return (struct.pack("<qqqi", offset, len(data), len(data), 0)
            + hashlib.sha1(data).digest() + b"\0" + struct.pack("<I", 0))


def write_pak(path, files, mount=MOUNT_POINT):
    """Write `files` ([(path relative to mount, bytes)]) to `path`. Returns bytes written."""
    names = [n for n, _ in files]
    if len(set(names)) != len(names):
        raise ValueError("duplicate file names in pak")
    index = bytearray(fstring_bytes(mount) + struct.pack("<i", len(files)))
    pos = 0
    with open(path, "wb") as f:
        for name, data in files:
            header = _entry_record(0, data)  # the in-data copy stores offset 0
            f.write(header)
            f.write(data)
            index += fstring_bytes(name) + _entry_record(pos, data)
            pos += len(header) + len(data)
        footer = struct.pack("<IIqq", PAK_MAGIC, PAK_VERSION, pos, len(index)) + hashlib.sha1(index).digest()
        f.write(index)
        f.write(footer)
        f.flush()
        os.fsync(f.fileno())
    return pos + len(index) + len(footer)
