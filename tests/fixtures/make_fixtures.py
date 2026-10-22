"""Bilinen mürekkep değerleriyle test PDF'leri üretir.

Çalıştırma: uv run python tests/fixtures/make_fixtures.py
Kutu konumları ve beklenen değerler EXPECTED içinde tutulur; testler bunu kullanır.
"""

from pathlib import Path

HERE = Path(__file__).parent
PAGE = 300  # pt, kare sayfa

# Spot renkler: ad -> CMYK alternatif değeri (tint 1.0 için)
SPOTS = {
    "PANTONE 185 C": (0.0, 0.91, 0.76, 0.0),
    "Spot Gold. 871/C": (0.20, 0.30, 0.70, 0.15),
    "Varnish": (0.0, 0.0, 0.0, 0.10),
}

Box = tuple[int, int, int, int]  # (x, y, w, h) pt, sol alt köşe orijin
# EXPECTED[dosya][sayfa] = [(kutu, {kalıp: yüzde})]
EXPECTED: dict[str, dict[int, list[tuple[Box, dict[str, float]]]]] = {}


def pdf_name(name: str) -> str:
    out = []
    for ch in name:
        if ch.isascii() and (ch.isalnum() or ch in "-_."):
            out.append(ch)
        else:
            out.extend(f"#{b:02X}" for b in ch.encode("utf-8"))
    return "/" + "".join(out)


class PdfWriter:
    def __init__(self) -> None:
        self.objects: list[bytes] = []

    def add(self, body: bytes | str) -> int:
        if isinstance(body, str):
            body = body.encode("latin-1")
        self.objects.append(body)
        return len(self.objects)

    def reserve(self) -> int:
        return self.add(b"")

    def set(self, num: int, body: str) -> None:
        self.objects[num - 1] = body.encode("latin-1")

    def stream(self, data: str) -> int:
        raw = data.encode("latin-1")
        return self.add(f"<< /Length {len(raw)} >>\nstream\n".encode() + raw + b"\nendstream")

    def write(self, path: Path, root: int) -> None:
        out = bytearray(b"%PDF-1.6\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, body in enumerate(self.objects, start=1):
            offsets.append(len(out))
            out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(self.objects) + 1}\n0000000000 65535 f \n".encode()
        for off in offsets:
            out += f"{off:010d} 00000 n \n".encode()
        out += (
            f"trailer\n<< /Size {len(self.objects) + 1} /Root {root} 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode()
        path.write_bytes(bytes(out))


def separation_cs(w: PdfWriter, name: str) -> int:
    c1 = " ".join(f"{v:g}" for v in SPOTS[name])
    fn = w.add(f"<< /FunctionType 2 /Domain [0 1] /C0 [0 0 0 0] /C1 [{c1}] /N 1 >>")
    return w.add(f"[/Separation {pdf_name(name)} /DeviceCMYK {fn} 0 R]")


def build(path: Path, pages: list[dict]) -> None:
    w = PdfWriter()
    pages_obj = w.reserve()
    kids = []
    for p in pages:
        cs = " ".join(f"/CS{i} {separation_cs(w, s)} 0 R" for i, s in enumerate(p.get("spots", [])))
        sh = " ".join(f"/{k} {make(w)} 0 R" for k, make in p.get("shadings", {}).items())
        gs = " ".join(f"/{k} {w.add(v)} 0 R" for k, v in p.get("extgstate", {}).items())
        content = w.stream(p["content"])
        res = f"<< /ColorSpace << {cs} >> /Shading << {sh} >> /ExtGState << {gs} >> >>"
        kids.append(
            w.add(
                f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 {PAGE} {PAGE}] "
                f"/Resources {res} /Contents {content} 0 R >>"
            )
        )
    w.set(pages_obj, f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>")
    root = w.add(f"<< /Type /Catalog /Pages {pages_obj} 0 R >>")
    w.write(path, root)


def rect(x: int, y: int, w: int = 50, h: int = 50) -> str:
    return f"{x} {y} {w} {h} re f\n"


def basic_pdf() -> None:
    """Tek sayfa: CMYK kutuları, %100/%50 spot, overprint ve knockout."""
    name = "basic.pdf"
    exp: list = []
    c = ""
    process = [
        ((20, 230), (1, 0, 0, 0), {"Cyan": 100}),
        ((90, 230), (0, 0.5, 0, 0), {"Magenta": 50}),
        ((160, 230), (0, 0, 0.25, 0), {"Yellow": 25}),
        ((230, 230), (0, 0, 0, 1), {"Black": 100}),
    ]
    for (x, y), cmyk, inks in process:
        c += f"{' '.join(f'{v:g}' for v in cmyk)} k\n" + rect(x, y)
        exp.append(((x, y, 50, 50), inks))
    c += "/CS0 cs 1 scn\n" + rect(20, 160)
    exp.append(((20, 160, 50, 50), {"PANTONE 185 C": 100}))
    c += "/CS0 cs 0.5 scn\n" + rect(90, 160)
    exp.append(((90, 160, 50, 50), {"PANTONE 185 C": 50}))
    # zengin siyah: C60 M40 Y40 K100 → TAC %240
    c += "0.6 0.4 0.4 1 k\n" + rect(160, 160)
    exp.append(((160, 160, 50, 50), {"Cyan": 60, "Magenta": 40, "Yellow": 40, "Black": 100}))
    # Overprint: C50 zemin, ortasında overprint'li spot %100
    c += "0.5 0 0 0 k\n" + rect(20, 20, 120, 120)
    c += "q /GSop gs /CS0 cs 1 scn\n" + rect(50, 50, 60, 60) + "Q\n"
    exp.append(((50, 50, 60, 60), {"Cyan": 50, "PANTONE 185 C": 100}))
    exp.append(((20, 20, 25, 120), {"Cyan": 50, "PANTONE 185 C": 0}))
    # Knockout: C50 zemin, ortasında overprint'siz spot → ortada cyan 0
    c += "0.5 0 0 0 k\n" + rect(160, 20, 120, 120)
    c += "/CS0 cs 1 scn\n" + rect(190, 50, 60, 60)
    exp.append(((190, 50, 60, 60), {"Cyan": 0, "PANTONE 185 C": 100}))
    build(
        HERE / name,
        [
            {
                "content": c,
                "spots": ["PANTONE 185 C"],
                "extgstate": {"GSop": "<< /Type /ExtGState /OP true /op true /OPM 1 >>"},
            }
        ],
    )
    EXPECTED[name] = {1: exp}


def multipage_pdf() -> None:
    """3 sayfa: farklı sayfalarda farklı spotlar, şeffaflık ve gradyan."""
    name = "multipage.pdf"
    exp: dict = {}
    c1 = "1 0 0 0 k\n" + rect(20, 20) + "/CS0 cs 1 scn\n" + rect(100, 20)
    exp[1] = [((20, 20, 50, 50), {"Cyan": 100}), ((100, 20, 50, 50), {"PANTONE 185 C": 100})]

    def axial(w: PdfWriter) -> int:
        cs = separation_cs(w, "Spot Gold. 871/C")
        fn = w.add("<< /FunctionType 2 /Domain [0 1] /C0 [0] /C1 [1] /N 1 >>")
        return w.add(
            f"<< /ShadingType 2 /ColorSpace {cs} 0 R /Coords [20 0 280 0] "
            f"/Function {fn} 0 R /Extend [false false] >>"
        )

    c2 = "q /GSa gs /CS0 cs 1 scn\n" + rect(20, 200, 80, 80) + "Q\n"
    c2 += "q 20 40 260 80 re W n /Sh0 sh Q\n"
    exp[2] = [
        ((20, 200, 80, 80), {"Spot Gold. 871/C": 50}),
        # gradyan x=20..280 arası doğrusal: x=150 → %50, x=85 → %25
        ((148, 60, 4, 40), {"Spot Gold. 871/C": 50}),
        ((83, 60, 4, 40), {"Spot Gold. 871/C": 25}),
    ]
    c3 = "/CS0 cs 1 scn\n" + rect(20, 20, 260, 100) + "0 0 0 0.75 k\n" + rect(20, 180)
    exp[3] = [((40, 40, 50, 50), {"Varnish": 100}), ((20, 180, 50, 50), {"Black": 75})]
    build(
        HERE / name,
        [
            {"content": c1, "spots": ["PANTONE 185 C"]},
            {
                "content": c2,
                "spots": ["Spot Gold. 871/C"],
                "shadings": {"Sh0": axial},
                "extgstate": {"GSa": "<< /Type /ExtGState /ca 0.5 /CA 0.5 >>"},
            },
            {"content": c3, "spots": ["Varnish"]},
        ],
    )
    EXPECTED[name] = exp


basic_pdf()
multipage_pdf()

if __name__ == "__main__":
    for n in EXPECTED:
        print("yazıldı:", HERE / n)


def icc_cmyk_pdf(path: Path, profile: bytes) -> list[tuple[Box, dict[str, float]]]:
    """ICCBased CMYK renk uzayıyla boyanmış kutular (Affinity PDF/X dışa aktarımı gibi).

    Profil depoya konmaz; testler Ghostscript'in kendi CMYK profilini kullanır.
    """
    w = PdfWriter()
    pages = w.reserve()
    icc = w.add(f"<< /N 4 /Length {len(profile)} >>\nstream\n".encode() + profile + b"\nendstream")
    cs = w.add(f"[/ICCBased {icc} 0 R]")
    boxes = [
        ((20, 20, 100, 100), (0, 1, 1, 0)),
        ((150, 20, 100, 100), (0.5, 0.2, 0, 0.1)),
        ((20, 150, 100, 100), (0.6, 0.4, 0.4, 1)),
    ]
    c = "".join(f"/CS0 cs {' '.join(f'{v:g}' for v in cmyk)} scn\n" + rect(*b) for b, cmyk in boxes)
    content = w.stream(c)
    page = w.add(
        f"<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 {PAGE} {PAGE}] "
        f"/Resources << /ColorSpace << /CS0 {cs} 0 R >> >> /Contents {content} 0 R >>"
    )
    w.set(pages, f"<< /Type /Pages /Kids [{page} 0 R] /Count 1 >>")
    w.write(path, w.add(f"<< /Type /Catalog /Pages {pages} 0 R >>"))
    names = ("Cyan", "Magenta", "Yellow", "Black")
    return [(b, {n: v * 100 for n, v in zip(names, cmyk)}) for b, cmyk in boxes]


# Windows dosya adlarında geçersiz karakterler içeren spot adları.
SPECIAL_SPOTS = ['Lak: "Parlak" <A>', "Sarı|Altın*?", "PANTONE 871 C/2"]


def special_names_pdf(path: Path) -> None:
    for name in SPECIAL_SPOTS:
        SPOTS.setdefault(name, (0.1, 0.2, 0.3, 0.0))
    c = "".join(f"/CS{i} cs 1 scn\n" + rect(20 + 90 * i, 20) for i in range(len(SPECIAL_SPOTS)))
    build(path, [{"content": c, "spots": SPECIAL_SPOTS}])
