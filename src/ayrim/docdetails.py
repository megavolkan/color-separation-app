"""Belge bilgisi paneli için PDF'in teknik ayrıntıları.

PDF sürümü ve PDF/X durumu, çıktı amacı ve gömülü ICC profilleri, kullanılan renk
uzayları, sayfa kutuları ve yazı tipleri (gömülü mü, alt küme mi) okunur.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field, replace
from pathlib import Path

import pikepdf

from .overprint import ink_order, overprinted_inks
from .pdfinfo import name_str
from .separations import PROCESS_NAMES

MM_PER_PT = 25.4 / 72.0
BOX_NAMES = ("MediaBox", "CropBox", "BleedBox", "TrimBox", "ArtBox")
# Görünen sıra; burada olmayan türler en sona eklenir.
COLOR_SPACE_ORDER = ("CMYK", "ICC CMYK", "Spot", "Gri", "ICC Gri", "RGB", "ICC RGB", "Lab")
_ICC_SPACES = {b"CMYK": "CMYK", b"RGB ": "RGB", b"GRAY": "Gri", b"Lab ": "Lab"}
_SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")


@dataclass(frozen=True)
class IccProfile:
    name: str
    color_space: str  # CMYK, RGB, Gri, Lab
    version: str  # örn. "4.2"


@dataclass(frozen=True)
class OutputIntent:
    subtype: str  # GTS_PDFX, GTS_PDFA1…
    condition: str  # OutputConditionIdentifier / Info
    profile: IccProfile | None


@dataclass(frozen=True)
class FontInfo:
    name: str  # alt küme öneki atılmış
    subtype: str  # Type1, TrueType, Type0, Type3…
    embedded: bool
    subset: bool


@dataclass(frozen=True)
class PageBoxes:
    number: int
    boxes: dict[str, tuple[float, float, float, float]]  # yalnızca PDF'te tanımlı olanlar, pt
    rotate: int = 0
    overprint: tuple[str, ...] = ()  # üste baskı ile boyanan kalıplar


@dataclass
class DocDetails:
    pdf_version: str
    pdfx: str | None = None
    pdfa: str | None = None
    output_intents: list[OutputIntent] = field(default_factory=list)
    color_spaces: list[str] = field(default_factory=list)
    icc_profiles: list[IccProfile] = field(default_factory=list)
    fonts: list[FontInfo] = field(default_factory=list)
    pages: list[PageBoxes] = field(default_factory=list)

    @property
    def overprint(self) -> list[str]:
        """Belgenin herhangi bir sayfasında üste baskı ile boyanan kalıplar."""
        return ink_order({n for p in self.pages for n in p.overprint})


# ---------------------------------------------------------------- ICC


def read_icc(data: bytes) -> IccProfile | None:
    """ICC profilinin adını (desc etiketi), renk uzayını ve sürümünü okur."""
    if len(data) < 132 or data[36:40] != b"acsp":
        return None
    space = _ICC_SPACES.get(data[16:20], data[16:20].decode("latin-1").strip())
    version = f"{data[8]}.{data[9] >> 4}"
    return IccProfile(_icc_description(data) or "(adsız profil)", space, version)


def _icc_description(data: bytes) -> str | None:
    try:
        (count,) = struct.unpack_from(">I", data, 128)
        for i in range(min(count, 200)):
            sig, off, size = struct.unpack_from(">4sII", data, 132 + 12 * i)
            if sig != b"desc":
                continue
            tag = data[off : off + size]
            if tag[:4] == b"desc":  # ICC v2: ASCII
                (n,) = struct.unpack_from(">I", tag, 8)
                return tag[12 : 12 + n].split(b"\0")[0].decode("latin-1").strip() or None
            if tag[:4] == b"mluc":  # ICC v4: UTF-16BE, ilk kayıt (çoğunlukla enUS)
                n_rec, rec_size = struct.unpack_from(">II", tag, 8)
                if n_rec:
                    length, offset = struct.unpack_from(">II", tag, 16 + 4)
                    return tag[offset : offset + length].decode("utf-16-be").strip("\0 ") or None
    except (struct.error, UnicodeDecodeError):
        pass
    return None


# ---------------------------------------------------------------- renk uzayları ve yazı tipleri


class _Collector:
    def __init__(self) -> None:
        self.spaces: set[str] = set()
        self.icc: dict[tuple, IccProfile] = {}
        self.fonts: dict[tuple, FontInfo] = {}
        self._seen: set = set()

    def _first_visit(self, obj) -> bool:
        if not obj.is_indirect:
            return True
        if obj.objgen in self._seen:
            return False
        self._seen.add(obj.objgen)
        return True

    # --- renk uzayı nesneleri

    def color_space(self, cs, depth: int = 0) -> None:
        if depth > 10 or cs is None:
            return
        if isinstance(cs, pikepdf.Name):
            label = {"/DeviceCMYK": "CMYK", "/DeviceRGB": "RGB", "/DeviceGray": "Gri"}.get(str(cs))
            if label:
                self.spaces.add(label)
            return
        if not isinstance(cs, pikepdf.Array) or len(cs) == 0:
            return
        kind = name_str(cs[0])
        if kind == "ICCBased":
            self._icc_space(cs[1])
        elif kind == "Lab":
            self.spaces.add("Lab")
        elif kind == "CalRGB":
            self.spaces.add("RGB")
        elif kind == "CalGray":
            self.spaces.add("Gri")
        elif kind == "Indexed" and len(cs) > 1:
            self.color_space(cs[1], depth + 1)
        elif kind == "Pattern" and len(cs) > 1:
            self.color_space(cs[1], depth + 1)
        elif kind == "Separation" and len(cs) > 1:
            self._colorant(name_str(cs[1]))
        elif kind == "DeviceN" and len(cs) > 1:
            for n in cs[1]:
                self._colorant(name_str(n))

    def _colorant(self, name: str) -> None:
        if name in ("None", "All"):
            return
        self.spaces.add("CMYK" if name in PROCESS_NAMES else "Spot")

    def _icc_space(self, stream) -> None:
        n = int(stream.get("/N", 0))
        self.spaces.add({1: "ICC Gri", 3: "ICC RGB", 4: "ICC CMYK"}.get(n, "ICC"))
        key = stream.objgen if stream.is_indirect else id(stream)
        if key not in self.icc:
            try:
                prof = read_icc(bytes(stream.read_bytes()))
            except Exception:
                prof = None
            if prof:
                self.icc[key] = prof

    # --- kaynak sözlükleri

    def resources(self, res, depth: int = 0) -> None:
        if not isinstance(res, pikepdf.Dictionary) or depth > 20:
            return
        for cs in _values(res.get("/ColorSpace")):
            self.color_space(cs)
        for sh in _values(res.get("/Shading")):
            if isinstance(sh, (pikepdf.Dictionary, pikepdf.Stream)):
                self.color_space(sh.get("/ColorSpace"))
        for pat in _values(res.get("/Pattern")):
            if not isinstance(pat, (pikepdf.Dictionary, pikepdf.Stream)) or not self._first_visit(pat):
                continue
            sh = pat.get("/Shading")
            if isinstance(sh, (pikepdf.Dictionary, pikepdf.Stream)):
                self.color_space(sh.get("/ColorSpace"))
            if isinstance(pat, pikepdf.Stream):  # döşeme deseni
                self.content(pat, pat.get("/Resources"), depth + 1)
        for font in _values(res.get("/Font")):
            self.font(font, depth)
        for xo in _values(res.get("/XObject")):
            if not isinstance(xo, pikepdf.Stream) or not self._first_visit(xo):
                continue
            sub = str(xo.get("/Subtype", ""))
            if sub == "/Image":
                if not xo.get("/ImageMask", False):
                    self.color_space(xo.get("/ColorSpace"))
            elif sub == "/Form":
                self.content(xo, xo.get("/Resources"), depth + 1)
        for gs in _values(res.get("/ExtGState")):
            smask = gs.get("/SMask") if isinstance(gs, pikepdf.Dictionary) else None
            group = smask.get("/G") if isinstance(smask, pikepdf.Dictionary) else None
            if isinstance(group, pikepdf.Stream) and self._first_visit(group):
                self.content(group, group.get("/Resources"), depth + 1)

    def content(self, stream_or_page, res, depth: int = 0) -> None:
        """İçerik akışındaki doğrudan renk komutları (k, rg, g…) ve kaynakları."""
        try:
            for _operands, op in pikepdf.parse_content_stream(stream_or_page, "k K rg RG g G"):
                self.spaces.add({"k": "CMYK", "rg": "RGB", "g": "Gri"}[str(op).lower()])
        except Exception:
            pass  # bozuk içerik akışı: kaynaklardan okunan bilgi yine gösterilir
        self.resources(res, depth)

    def font(self, font, depth: int) -> None:
        if not isinstance(font, pikepdf.Dictionary) or not self._first_visit(font):
            return
        subtype = name_str(font.get("/Subtype", pikepdf.Name("/Unknown")))
        base = name_str(font.get("/BaseFont", pikepdf.Name("/" + name_str(font.get("/Name", "Type3")))))
        desc = font.get("/FontDescriptor")
        if subtype == "Type0":
            kids = font.get("/DescendantFonts")
            kid = kids[0] if isinstance(kids, pikepdf.Array) and len(kids) else None
            desc = kid.get("/FontDescriptor") if isinstance(kid, pikepdf.Dictionary) else None
            if isinstance(kid, pikepdf.Dictionary):
                subtype = f"Type0 / {name_str(kid.get('/Subtype', ''))}"
        if subtype == "Type3":
            embedded = True  # karakterler PDF içinde çizim olarak tanımlı
            self.resources(font.get("/Resources"), depth + 1)
        else:
            embedded = isinstance(desc, pikepdf.Dictionary) and any(
                k in desc for k in ("/FontFile", "/FontFile2", "/FontFile3")
            )
        subset = bool(_SUBSET_PREFIX.match(base))
        info = FontInfo(_SUBSET_PREFIX.sub("", base), subtype, embedded, subset)
        self.fonts.setdefault((info.name, info.subtype, info.embedded), info)


def _values(d):
    if isinstance(d, pikepdf.Dictionary):
        return [d[k] for k in d.keys()]
    return []


# ---------------------------------------------------------------- belge


def _box(obj, name: str) -> tuple[float, float, float, float] | None:
    arr = obj.get("/" + name)
    if not isinstance(arr, pikepdf.Array) or len(arr) != 4:
        return None
    x0, y0, x1, y1 = (float(v) for v in arr)
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _page_boxes(number: int, page: pikepdf.Page) -> PageBoxes:
    boxes = {}
    media = [float(v) for v in page.mediabox]  # kalıtımla gelen MediaBox dahil
    boxes["MediaBox"] = (min(media[0], media[2]), min(media[1], media[3]), max(media[0], media[2]), max(media[1], media[3]))
    for name in BOX_NAMES[1:]:
        b = _box(page.obj, name)
        if b:
            boxes[name] = b
    return PageBoxes(number, boxes, int(page.obj.get("/Rotate", 0)) % 360)


def _conformance(pdf: pikepdf.Pdf) -> tuple[str | None, str | None]:
    pdfx = pdfa = None
    try:
        info = pdf.docinfo
        if "/GTS_PDFXVersion" in info:
            pdfx = str(info["/GTS_PDFXVersion"])
    except Exception:
        pass
    try:
        meta = pdf.open_metadata()
        pdfx = pdfx or meta.get("pdfxid:GTS_PDFXVersion")
        part, conf = meta.get("pdfaid:part"), meta.get("pdfaid:conformance")
        if part:
            pdfa = f"PDF/A-{part}{(conf or '').lower()}"
    except Exception:
        pass
    return pdfx or None, pdfa


def _output_intents(pdf: pikepdf.Pdf) -> list[OutputIntent]:
    out = []
    intents = pdf.Root.get("/OutputIntents")
    if not isinstance(intents, pikepdf.Array):
        return out
    for oi in intents:
        if not isinstance(oi, pikepdf.Dictionary):
            continue
        prof = None
        dest = oi.get("/DestOutputProfile")
        if isinstance(dest, pikepdf.Stream):
            try:
                prof = read_icc(bytes(dest.read_bytes()))
            except Exception:
                prof = None
        cond = str(oi.get("/OutputConditionIdentifier", "") or "") or str(oi.get("/Info", "") or "")
        out.append(OutputIntent(name_str(oi.get("/S", "")), cond, prof))
    return out


def read_doc_details(path: Path | str) -> DocDetails:
    with pikepdf.open(path) as pdf:
        pdfx, pdfa = _conformance(pdf)
        details = DocDetails(str(pdf.pdf_version), pdfx, pdfa, _output_intents(pdf))
        col = _Collector()
        for i, page in enumerate(pdf.pages, start=1):
            pb = _page_boxes(i, page)
            try:
                pb = replace(pb, overprint=tuple(ink_order(overprinted_inks(page))))
            except Exception:
                pass  # okunamayan içerik: üste baskı bilgisi gösterilmez
            details.pages.append(pb)
            col.content(page, page.resources)
        rank = {s: i for i, s in enumerate(COLOR_SPACE_ORDER)}
        details.color_spaces = sorted(col.spaces, key=lambda s: (rank.get(s, len(rank)), s))
        intent_profiles = {oi.profile for oi in details.output_intents}
        details.icc_profiles = [p for p in dict.fromkeys(col.icc.values()) if p not in intent_profiles]
        details.fonts = sorted(col.fonts.values(), key=lambda f: f.name.casefold())
        return details


# ---------------------------------------------------------------- gösterim yardımcıları


def box_size_mm(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((box[2] - box[0]) * MM_PER_PT, (box[3] - box[1]) * MM_PER_PT)


def bleed_mm(page: PageBoxes) -> float | None:
    """TrimBox ile BleedBox arasındaki en küçük kenar payı (mm); ikisi de yoksa None."""
    trim, bleed = page.boxes.get("TrimBox"), page.boxes.get("BleedBox")
    if not trim or not bleed:
        return None
    margins = (trim[0] - bleed[0], trim[1] - bleed[1], bleed[2] - trim[2], bleed[3] - trim[3])
    return max(min(margins), 0.0) * MM_PER_PT
