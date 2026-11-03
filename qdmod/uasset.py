"""Minimal parser for cooked UE 4.27 packages (.uasset header + .uexp export data).

Only what the patcher needs: the name/import/export tables, each export's class
and super (parent) reference, and the location of top-level float properties.
"""
from .binio import Reader

PACKAGE_TAG = 0x9E2A83C1


class AssetError(Exception):
    pass


class Export:
    __slots__ = ("name", "class_index", "super_index", "size", "uexp_offset")

    def __init__(self, name, class_index, super_index, size, uexp_offset):
        self.name, self.class_index, self.super_index = name, class_index, super_index
        self.size, self.uexp_offset = size, uexp_offset


class Package:
    """Parse a cooked package. `uexp` may be empty if only the header tables are needed."""

    def __init__(self, uasset, uexp=b""):
        self.uexp = uexp
        r = Reader(uasset)
        if r.u32() != PACKAGE_TAG:
            raise AssetError("not an Unreal package")
        r.i32()  # legacy file version
        r.i32()  # legacy UE3 version
        self.file_version = r.i32()
        r.i32()  # licensee version
        for _ in range(r.i32()):  # custom versions
            r.take(20)
        self.header_size = r.i32()
        r.fstr()  # folder name
        self.flags = r.u32()
        name_count, name_offset = r.i32(), r.i32()
        r.i32(); r.i32()  # gatherable text data
        export_count, export_offset = r.i32(), r.i32()
        import_count, import_offset = r.i32(), r.i32()

        r.p = name_offset
        self.names = []
        for _ in range(name_count):
            self.names.append(r.fstr())
            r.take(4)  # hashes

        r.p = import_offset
        self.imports = []
        for _ in range(import_count):
            r.take(16)  # class package + class name
            r.i32()  # outer index
            self.imports.append(self._fname(r))

        r.p = export_offset
        self.exports = []
        for _ in range(export_count):
            start = r.p
            cls, sup = r.i32(), r.i32()
            r.i32()  # template index
            r.i32()  # outer index
            name = self._fname(r)
            r.u32()  # object flags
            size, offset = r.i64(), r.i64()
            r.p = start + 104  # fixed-size FObjectExport record in UE 4.27
            self.exports.append(Export(name, cls, sup, size, offset - self.header_size))

    def _fname(self, r):
        i, n = r.i32(), r.i32()
        if not 0 <= i < len(self.names):
            raise AssetError(f"bad name index {i}")
        nm = self.names[i]
        return nm if n == 0 else f"{nm}_{n - 1}"

    def ref_name(self, index):
        """('import'|'export'|'null', object name) for an FPackageIndex."""
        if index < 0:
            return "import", self.imports[-index - 1]
        if index > 0:
            return "export", self.exports[index - 1].name
        return "null", ""

    def class_name(self, export):
        return self.ref_name(export.class_index)[1]

    def find_export(self, name):
        for e in self.exports:
            if e.name == name:
                return e
        return None

    def top_floats(self, export):
        """{property name: absolute .uexp offset} for an export's top-level FloatProperty values."""
        if isinstance(export, str):
            export = self.find_export(export)
            if export is None:
                return {}
        off, end = export.uexp_offset, export.uexp_offset + export.size
        if off < 0 or end > len(self.uexp):
            raise AssetError("export data lies outside the .uexp file")
        r, out = Reader(self.uexp, off), {}
        while r.p < end:
            name = self._fname(r)
            if name == "None":
                break
            typ = self._fname(r)
            size = r.i32()
            r.i32()  # array index
            if typ == "StructProperty":
                self._fname(r); r.take(16)
            elif typ == "BoolProperty":
                r.u8()
            elif typ in ("ByteProperty", "EnumProperty", "ArrayProperty", "SetProperty"):
                self._fname(r)
            elif typ == "MapProperty":
                self._fname(r); self._fname(r)
            if r.u8():  # has property guid
                r.take(16)
            if typ == "FloatProperty" and size == 4:
                out[name] = r.p
            r.p += size
        return out
