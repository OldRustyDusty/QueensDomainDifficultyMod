"""Independent re-read and check of a written mod pak.

Checks, from the bytes on disk:
  * pak structure: version, mount point, footer position, index SHA1, every entry's
    in-data header and SHA1, contiguous non-overlapping layout;
  * content: every .uasset is byte-identical to the original; every .uexp differs
    from the original only in allowed 4-byte float slots, and each changed float
    equals original x the preset's multiplier (rounded to 32-bit float);
  * completeness: the set of changed floats is exactly the expected set.
"""
import hashlib
import json
import struct

from .binio import f32
from .errors import VerifyError
from .pak_reader import PakError, PakFile
from .pak_writer import MOUNT_POINT, PAK_VERSION, _entry_record
from .patcher import BREAKABLE_PROP, ENEMY_CLASS, ENEMY_PROPS
from .presets import preset_from_manifest
from .uasset import AssetError, Package

MANIFEST_NAME = "QDDifficultyMod/manifest.json"


def read_manifest(pak):
    path = pak.mount + MANIFEST_NAME
    if path not in pak.entries:
        return None
    return json.loads(pak.read(path).decode("utf-8"))


def _expected_change(pkg, export, prop, mult, breakable_classes):
    """(category, multiplier) the preset intends for this float, or (None, None) if untouched."""
    is_enemy = (pkg.ref_name(export.class_index) == ("import", ENEMY_CLASS)
                or export.name == "Default__" + ENEMY_CLASS)
    if is_enemy:
        for p, key in ENEMY_PROPS:
            if prop == p:
                return "enemy", mult[key]
    if (prop == BREAKABLE_PROP and export.name.startswith("Default__")
            and export.name[len("Default__"):] in breakable_classes):
        return "breakable", mult["breakable_hp"]
    return None, None


def verify_mod_pak(mod_path, main_pak, expected_edits=None, progress=lambda f, m: None):
    """Verify the mod pak at `mod_path` against the opened main PakFile.

    `expected_edits`: optional set of (uexp path, offset) that must be exactly the changed floats.
    Returns a summary dict; raises VerifyError on any problem.
    """
    problems = []

    def fail(msg):
        problems.append(msg)
        if len(problems) >= 20:
            raise VerifyError("Verification failed:\n" + "\n".join(problems))

    try:
        pak = PakFile(mod_path)
    except (PakError, OSError) as e:
        raise VerifyError(f"Verification failed: the written pak can't be read back ({e})")
    try:
        # ---- structure -------------------------------------------------------
        if pak.version != PAK_VERSION:
            fail(f"pak version is {pak.version}, expected {PAK_VERSION}")
        if pak.mount != MOUNT_POINT:
            fail(f"mount point is {pak.mount!r}, expected {MOUNT_POINT!r}")
        if pak.footer_size != 44 or pak.index_offset + pak.index_size + 44 != pak.file_size:
            fail("pak footer/index are not where they should be")
        if not pak.index_hash_ok():
            fail("pak index SHA1 does not match the footer")
        pos = 0
        datas = {}
        for e in sorted(pak.entries.values(), key=lambda e: e.offset):
            if e.offset != pos:
                fail(f"{e.path}: unexpected offset {e.offset} (expected {pos})")
            if e.comp or e.encrypted or e.size != e.usize:
                fail(f"{e.path}: entry should be stored uncompressed and unencrypted")
            data = pak.read(e)
            if hashlib.sha1(data).digest() != e.sha1:
                fail(f"{e.path}: SHA1 mismatch")
            if pak.read_entry_header(e) != _entry_record(0, data):
                fail(f"{e.path}: in-data entry header does not match")
            datas[e.path] = data
            pos = e.data_offset + e.usize
        if pos != pak.index_offset:
            fail("pak data does not end where the index starts")

        # ---- manifest --------------------------------------------------------
        manifest_path = pak.mount + MANIFEST_NAME
        if manifest_path not in datas:
            raise VerifyError("Verification failed: the mod pak has no manifest")
        manifest = json.loads(datas.pop(manifest_path).decode("utf-8"))
        preset = preset_from_manifest(manifest)
        if preset is None or preset.is_vanilla:
            raise VerifyError(f"Verification failed: unknown preset {manifest.get('preset')!r} in manifest")
        mult = preset.multipliers()
        if manifest.get("multipliers") != mult:
            fail("manifest multipliers do not match the preset definition")
        breakable_classes = set(manifest.get("breakable_classes", []))

        # ---- content ---------------------------------------------------------
        uassets = sorted(p for p in datas if p.endswith(".uasset"))
        if len(uassets) * 2 != len(datas) or any(p[:-7] + ".uexp" not in datas for p in uassets):
            fail("pak should contain only .uasset/.uexp pairs plus the manifest")
        changed = set()
        counts = {"enemy": 0, "breakable": 0}
        samples = {}
        for i, ua_path in enumerate(uassets):
            if i % 50 == 0:
                progress(i / max(1, len(uassets)), f"Verifying ({i} of {len(uassets)} assets)")
            ux_path = ua_path[:-7] + ".uexp"
            if ua_path not in main_pak.entries or ux_path not in main_pak.entries:
                fail(f"{ua_path}: not present in the game's main pak")
                continue
            orig_ua = main_pak.read(ua_path)
            orig_ux = main_pak.read(ux_path)
            new_ux = datas[ux_path]
            if datas[ua_path] != orig_ua:
                fail(f"{ua_path}: .uasset differs from the original")
            if len(new_ux) != len(orig_ux):
                fail(f"{ux_path}: size differs from the original")
                continue
            pkg = Package(orig_ua, orig_ux)
            slots = {}  # offset -> (export, prop, category, multiplier)
            for x in pkg.exports:
                for prop, off in pkg.top_floats(x).items():
                    slots[off] = (x, prop) + _expected_change(pkg, x, prop, mult, breakable_classes)
            for b in _diff_positions(orig_ux, new_ux):
                if not any(o <= b < o + 4 for o in slots):
                    fail(f"{ux_path}: byte {b} changed outside any float property")
            for off, (x, prop, cat, m) in slots.items():
                if m == 1.0:  # e.g. Custom at 100%: this value must stay exactly as it was
                    cat, m = None, None
                old = struct.unpack_from("<f", orig_ux, off)[0]
                want = orig_ux[off:off + 4] if m is None else f32(old * m)
                got = new_ux[off:off + 4]
                if got != want:
                    fail(f"{ux_path}: {x.name}.{prop} is {struct.unpack('<f', got)[0]:g}, "
                         f"expected {struct.unpack('<f', want)[0]:g}")
                elif m is not None:
                    changed.add((ux_path, off))
                    counts[cat] += 1
                    short = ua_path.split("/Content/", 1)[-1][:-len(".uasset")]
                    samples.setdefault(short, {})[f"{x.name}.{prop}"] = (old, struct.unpack("<f", got)[0])
        if expected_edits is not None and changed != set(expected_edits):
            missing = len(set(expected_edits) - changed)
            extra = len(changed - set(expected_edits))
            fail(f"changed floats don't match the plan ({missing} missing, {extra} unexpected)")
        # Custom can leave one side untouched, so only require changes where a multiplier isn't 1.
        enemy_expected = mult["enemy_hp"] != 1.0 or mult["enemy_damage"] != 1.0
        breakable_expected = mult["breakable_hp"] != 1.0
        if (enemy_expected and counts["enemy"] == 0) or (breakable_expected and counts["breakable"] == 0):
            fail(f"too few changes found (enemy {counts['enemy']}, breakable {counts['breakable']})")
        if (not enemy_expected and counts["enemy"]) or (not breakable_expected and counts["breakable"]):
            fail(f"unexpected changes found (enemy {counts['enemy']}, breakable {counts['breakable']})")
        if problems:
            raise VerifyError("Verification failed:\n" + "\n".join(problems))
        progress(1.0, "Verified")
        return {"preset": preset.key, "files": len(pak.entries), "assets": len(uassets),
                "enemy_floats": counts["enemy"], "breakable_floats": counts["breakable"],
                "manifest": manifest, "samples": samples}
    except VerifyError:
        raise
    except (AssetError, PakError, ValueError, KeyError, IndexError, struct.error) as e:
        raise VerifyError("Verification failed:\n" + "\n".join(problems + [f"unreadable data ({e})"]))
    finally:
        pak.close()


def _diff_positions(a, b):
    """Byte positions where a and b differ (fast path: compare in 4 KiB chunks first)."""
    out = set()
    for start in range(0, len(a), 4096):
        ca, cb = a[start:start + 4096], b[start:start + 4096]
        if ca != cb:
            out.update(start + i for i in range(len(ca)) if ca[i] != cb[i])
    return out
