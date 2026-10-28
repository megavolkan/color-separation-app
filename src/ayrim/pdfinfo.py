"""PDF meta verisi: sayfa bilgisi ve spot renklerin ekran rengi.

Spot rengin ekran rengi, Separation/DeviceN renk uzayının alternatif uzayında
tint transform fonksiyonu %100 tint için hesaplanarak bulunur.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import pikepdf

from .composite import RGB
from .separations import PROCESS_NAMES

_IGNORED_COLORANTS = {"None", "All", *PROCESS_NAMES}


@dataclass(frozen=True)
class PageInfo:
    number: int  # 1'den başlar
    width_pt: float
    height_pt: float


@dataclass
class DocInfo:
    pages: list[PageInfo]
    spot_colors: dict[str, RGB | None] = field(default_factory=dict)
    # Alternatif uzayı CMYK olan spotların %100 tint CMYK değerleri (profille ekran rengi için).
    spot_cmyk: dict[str, tuple[float, float, float, float]] = field(default_factory=dict)
    cmyk_profile: bytes | None = None  # çıktı amacı ya da gömülü CMYK ICC profili

    @property
    def page_count(self) -> int:
        return len(self.pages)


def name_str(obj: pikepdf.Object) -> str:
    return str(obj)[1:] if str(obj).startswith("/") else str(obj)


# ---------------------------------------------------------------- PDF fonksiyonları


def _floats(arr) -> list[float]:
    return [float(v) for v in arr]


def _clip(vals: list[float], rng: list[float] | None) -> list[float]:
    if not rng:
        return vals
    return [min(max(v, rng[2 * i]), rng[2 * i + 1]) for i, v in enumerate(vals)]


def eval_function(fn, inputs: list[float]) -> list[float]:
    """PDF fonksiyonunu (tip 0, 2, 3, 4 veya fonksiyon dizisi) değerlendirir."""
    if isinstance(fn, pikepdf.Array):
        return [eval_function(f, inputs)[0] for f in fn]
    ftype = int(fn.FunctionType)
    domain = _floats(fn.Domain)
    x = _clip(list(inputs), domain)
    rng = _floats(fn.Range) if "/Range" in fn else None
    if ftype == 2:
        c0 = _floats(fn.C0) if "/C0" in fn else [0.0]
        c1 = _floats(fn.C1) if "/C1" in fn else [1.0]
        n = float(fn.N)
        t = x[0] ** n
        return _clip([a + t * (b - a) for a, b in zip(c0, c1)], rng)
    if ftype == 3:
        bounds = _floats(fn.Bounds)
        encode = _floats(fn.Encode)
        edges = [domain[0], *bounds, domain[1]]
        k = 0
        while k < len(bounds) and x[0] >= bounds[k]:
            k += 1
        lo, hi = edges[k], edges[k + 1]
        e0, e1 = encode[2 * k], encode[2 * k + 1]
        v = e0 if hi == lo else e0 + (x[0] - lo) * (e1 - e0) / (hi - lo)
        return _clip(eval_function(fn.Functions[k], [v]), rng)
    if ftype == 0:
        return _clip(_eval_sampled(fn, x, domain), rng)
    if ftype == 4:
        return _clip(_eval_postscript(bytes(fn.read_bytes()), x), rng)
    raise ValueError(f"Desteklenmeyen fonksiyon tipi {ftype}")


def _eval_sampled(fn, x: list[float], domain: list[float]) -> list[float]:
    """Tip 0 örneklenmiş fonksiyon; her girişte en yakın örnek ile (birim vektörler için tam)."""
    size = [int(s) for s in fn.Size]
    bps = int(fn.BitsPerSample)
    rng = _floats(fn.Range)
    n_out = len(rng) // 2
    encode = _floats(fn.Encode) if "/Encode" in fn else [v for s in size for v in (0, s - 1)]
    decode = _floats(fn.Decode) if "/Decode" in fn else rng
    data = fn.read_bytes()
    idx = 0
    stride = 1
    for i, xi in enumerate(x):
        d0, d1 = domain[2 * i], domain[2 * i + 1]
        e = encode[2 * i] + (xi - d0) * (encode[2 * i + 1] - encode[2 * i]) / ((d1 - d0) or 1)
        e = min(max(round(e), 0), size[i] - 1)
        idx += e * stride
        stride *= size[i]
    out = []
    maxv = (1 << bps) - 1
    for j in range(n_out):
        bit = (idx * n_out + j) * bps
        val = 0
        for b in range(bps):
            byte = data[(bit + b) // 8]
            val = (val << 1) | ((byte >> (7 - (bit + b) % 8)) & 1)
        out.append(decode[2 * j] + val * (decode[2 * j + 1] - decode[2 * j]) / maxv)
    return out


def _ps_tokens(src: str) -> list:
    src = src.replace("{", " { ").replace("}", " } ")
    tokens: list = []
    stack = [tokens]
    for tok in src.split():
        if tok == "{":
            new: list = []
            stack[-1].append(new)
            stack.append(new)
        elif tok == "}":
            stack.pop()
        else:
            try:
                stack[-1].append(float(tok) if any(c in tok for c in ".eE") else int(tok))
            except ValueError:
                stack[-1].append(tok)
    return tokens[0] if len(tokens) == 1 and isinstance(tokens[0], list) else tokens


def _eval_postscript(code: bytes, x: list[float]) -> list[float]:
    """Tip 4 (PostScript hesap makinesi) fonksiyonu için küçük bir yorumlayıcı."""
    prog = _ps_tokens(code.decode("latin-1"))
    st: list = list(x)

    def run(ops: list) -> None:
        i = 0
        while i < len(ops):
            op = ops[i]
            if isinstance(op, list):
                nxt = ops[i + 1] if i + 1 < len(ops) else None
                nxt2 = ops[i + 2] if i + 2 < len(ops) else None
                if nxt == "if":
                    if st.pop():
                        run(op)
                    i += 2
                    continue
                if isinstance(nxt, list) and nxt2 == "ifelse":
                    run(op if st.pop() else nxt)
                    i += 3
                    continue
                raise ValueError("Beklenmeyen PostScript yapısı")
            if isinstance(op, (int, float)):
                st.append(op)
            else:
                _ps_op(op, st)
            i += 1

    run(prog)
    return [float(v) for v in st]


def _ps_op(op: str, st: list) -> None:
    b = {
        "add": lambda a, c: a + c, "sub": lambda a, c: a - c, "mul": lambda a, c: a * c,
        "div": lambda a, c: a / c, "idiv": lambda a, c: int(a) // int(c), "mod": lambda a, c: int(a) % int(c),
        "exp": lambda a, c: a ** c, "atan": lambda a, c: math.degrees(math.atan2(a, c)) % 360,
        "eq": lambda a, c: a == c, "ne": lambda a, c: a != c, "gt": lambda a, c: a > c,
        "ge": lambda a, c: a >= c, "lt": lambda a, c: a < c, "le": lambda a, c: a <= c,
        "and": lambda a, c: a & c if isinstance(a, int) and not isinstance(a, bool) else a and c,
        "or": lambda a, c: a | c if isinstance(a, int) and not isinstance(a, bool) else a or c,
        "xor": lambda a, c: a ^ c, "bitshift": lambda a, c: a << c if c >= 0 else a >> -c,
    }
    u = {
        "abs": abs, "neg": lambda a: -a, "ceiling": math.ceil, "floor": math.floor,
        "round": lambda a: math.floor(a + 0.5), "truncate": math.trunc, "sqrt": math.sqrt,
        "sin": lambda a: math.sin(math.radians(a)), "cos": lambda a: math.cos(math.radians(a)),
        "ln": math.log, "log": math.log10, "cvi": int, "cvr": float,
        "not": lambda a: (not a) if isinstance(a, bool) else ~a,
    }
    if op in b:
        c = st.pop()
        a = st.pop()
        st.append(b[op](a, c))
    elif op in u:
        st.append(u[op](st.pop()))
    elif op == "true":
        st.append(True)
    elif op == "false":
        st.append(False)
    elif op == "dup":
        st.append(st[-1])
    elif op == "pop":
        st.pop()
    elif op == "exch":
        st[-1], st[-2] = st[-2], st[-1]
    elif op == "copy":
        n = int(st.pop())
        if n:
            st.extend(st[-n:])
    elif op == "index":
        n = int(st.pop())
        st.append(st[-1 - n])
    elif op == "roll":
        j = int(st.pop())
        n = int(st.pop())
        if n:
            seg = st[-n:]
            j %= n
            st[-n:] = seg[-j:] + seg[:-j] if j else seg
    else:
        raise ValueError(f"Desteklenmeyen PostScript operatörü: {op}")


# ---------------------------------------------------------------- renk dönüşümleri


def _srgb_gamma(v: float) -> float:
    v = min(max(v, 0.0), 1.0)
    return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def lab_to_srgb(L: float, a: float, b: float, white: tuple[float, float, float] = (0.9642, 1.0, 0.8249)) -> RGB:
    """CIE Lab → sRGB (Bradford ile D65'e uyarlama)."""
    fy = (L + 16) / 116
    fx = fy + a / 500
    fz = fy - b / 200

    def finv(t: float) -> float:
        return t**3 if t > 6 / 29 else 3 * (6 / 29) ** 2 * (t - 4 / 29)

    X, Y, Z = white[0] * finv(fx), white[1] * finv(fy), white[2] * finv(fz)
    # Bradford: kaynak beyaz → D65
    M = ((0.8951, 0.2664, -0.1614), (-0.7502, 1.7135, 0.0367), (0.0389, -0.0685, 1.0296))
    Minv = ((0.9869929, -0.1470543, 0.1599627), (0.4323053, 0.5183603, 0.0492912), (-0.0085287, 0.0400428, 0.9684867))

    def mul(m, v):
        return tuple(sum(m[i][j] * v[j] for j in range(3)) for i in range(3))

    src = mul(M, white)
    dst = mul(M, (0.95047, 1.0, 1.08883))
    lms = mul(M, (X, Y, Z))
    lms = tuple(lms[i] * dst[i] / src[i] for i in range(3))
    X, Y, Z = mul(Minv, lms)
    r = 3.2404542 * X - 1.5371385 * Y - 0.4985314 * Z
    g = -0.9692660 * X + 1.8760108 * Y + 0.0415560 * Z
    bb = 0.0556434 * X - 0.2040259 * Y + 1.0572252 * Z
    return (_srgb_gamma(r), _srgb_gamma(g), _srgb_gamma(bb))


def cmyk_to_srgb(c: float, m: float, y: float, k: float) -> RGB:
    """Basit (profilsiz) CMYK → sRGB; yalnızca ekran rengi için."""
    return ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))


def to_srgb(space, values: list[float]) -> RGB | None:
    """Alternatif renk uzayındaki değeri sRGB'ye çevirir; bilinmiyorsa None."""
    if isinstance(space, pikepdf.Array):
        kind = name_str(space[0])
        if kind == "Lab":
            d = space[1]
            white = tuple(_floats(d.WhitePoint)) if "/WhitePoint" in d else (0.9642, 1.0, 0.8249)
            return lab_to_srgb(*values[:3], white=white)
        if kind == "ICCBased":
            stream = space[1]
            if "/Alternate" in stream:
                return to_srgb(stream.Alternate, values)
            n = int(stream.N)
            space = {1: "DeviceGray", 3: "DeviceRGB", 4: "DeviceCMYK"}.get(n)
        elif kind in ("CalRGB", "CalGray"):
            space = "DeviceRGB" if kind == "CalRGB" else "DeviceGray"
        else:
            return None
    else:
        space = name_str(space)
    v = [min(max(x, 0.0), 1.0) for x in values]
    if space in ("DeviceCMYK", "CMYK") and len(v) >= 4:
        return cmyk_to_srgb(*v[:4])
    if space in ("DeviceRGB", "RGB") and len(v) >= 3:
        return (v[0], v[1], v[2])
    if space in ("DeviceGray", "G") and v:
        return (v[0], v[0], v[0])
    return None


# ---------------------------------------------------------------- spot keşfi


def _is_cmyk_space(space) -> bool:
    if isinstance(space, pikepdf.Array) and len(space) > 1 and name_str(space[0]) == "ICCBased":
        return int(space[1].get("/N", 0)) == 4
    return name_str(space) in ("DeviceCMYK", "CMYK")


def _spot_colors_from_cs(cs, found: dict[str, RGB | None], cmyk: dict | None = None) -> None:
    cmyk = {} if cmyk is None else cmyk
    kind = name_str(cs[0])
    if kind == "Separation":
        name = name_str(cs[1])
        if name in _IGNORED_COLORANTS:
            return
        try:
            values = eval_function(cs[3], [1.0])
            color = to_srgb(cs[2], values)
        except Exception:
            values, color = None, None
        if found.get(name) is None:
            found[name] = color
            if color is not None and _is_cmyk_space(cs[2]) and len(values) >= 4:
                cmyk[name] = tuple(min(max(v, 0.0), 1.0) for v in values[:4])
    elif kind == "DeviceN":
        names = [name_str(n) for n in cs[1]]
        attrs = cs[4] if len(cs) > 4 else None
        colorants = attrs.get("/Colorants") if attrs is not None else None
        for i, name in enumerate(names):
            if name in _IGNORED_COLORANTS:
                continue
            if colorants is not None and pikepdf.Name("/" + name) in colorants:
                _spot_colors_from_cs(colorants[pikepdf.Name("/" + name)], found, cmyk)
                continue
            try:
                vec = [1.0 if j == i else 0.0 for j in range(len(names))]
                values = eval_function(cs[3], vec)
                color = to_srgb(cs[2], values)
            except Exception:
                values, color = None, None
            if found.get(name) is None:
                found[name] = color
                if color is not None and _is_cmyk_space(cs[2]) and len(values) >= 4:
                    cmyk[name] = tuple(min(max(v, 0.0), 1.0) for v in values[:4])


def _walk(obj, found: dict[str, RGB | None], seen: set, depth: int = 0, cmyk: dict | None = None) -> None:
    if depth > 40:
        return
    if obj.is_indirect:
        key = obj.objgen
        if key in seen:
            return
        seen.add(key)
    if isinstance(obj, pikepdf.Array):
        if len(obj) >= 4 and isinstance(obj[0], pikepdf.Name) and name_str(obj[0]) in ("Separation", "DeviceN"):
            _spot_colors_from_cs(obj, found, cmyk)
        for item in obj:
            if isinstance(item, (pikepdf.Array, pikepdf.Dictionary, pikepdf.Stream)):
                _walk(item, found, seen, depth + 1, cmyk)
    elif isinstance(obj, (pikepdf.Dictionary, pikepdf.Stream)):
        for k in obj.keys():
            if k in ("/Parent", "/P"):
                continue
            item = obj[k]
            if isinstance(item, (pikepdf.Array, pikepdf.Dictionary, pikepdf.Stream)):
                _walk(item, found, seen, depth + 1, cmyk)


def _icc_bytes(stream) -> bytes | None:
    try:
        data = stream.read_bytes()
    except Exception:
        return None
    return data if len(data) >= 132 and data[36:40] == b"acsp" and data[16:20] == b"CMYK" else None


def find_cmyk_profile(pdf: pikepdf.Pdf) -> bytes | None:
    """Önizleme için CMYK profili: önce CMYK çıktı amacı, sonra belgede gömülü ilk CMYK ICC profili."""
    for oi in pdf.Root.get("/OutputIntents", []):
        dest = oi.get("/DestOutputProfile") if isinstance(oi, pikepdf.Dictionary) else None
        if isinstance(dest, pikepdf.Stream) and (data := _icc_bytes(dest)):
            return data
    for obj in pdf.objects:
        if isinstance(obj, pikepdf.Stream) and "/Subtype" not in obj and obj.get("/N") == 4:
            if data := _icc_bytes(obj):
                return data
    return None


def read_pdf_info(path: Path | str) -> DocInfo:
    with pikepdf.open(path) as pdf:
        pages = []
        found: dict[str, RGB | None] = {}
        cmyk: dict[str, tuple[float, float, float, float]] = {}
        seen: set = set()
        for i, page in enumerate(pdf.pages, start=1):
            box = [float(v) for v in page.mediabox]
            rot = int(page.obj.get("/Rotate", 0)) % 180
            w, h = abs(box[2] - box[0]), abs(box[3] - box[1])
            if rot:
                w, h = h, w
            pages.append(PageInfo(i, w, h))
            _walk(page.resources, found, seen, cmyk=cmyk)
        return DocInfo(pages, found, cmyk, find_cmyk_profile(pdf))
