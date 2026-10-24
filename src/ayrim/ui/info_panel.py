"""Belge bilgisi paneli: PDF sürümü, renk profilleri, sayfa kutuları ve yazı tipleri."""

from __future__ import annotations

from html import escape

from PySide6.QtWidgets import QTextBrowser

from ..docdetails import DocDetails, IccProfile, bleed_mm, box_size_mm

WARN = "#d08000"
BOX_LABELS = {
    "MediaBox": "Ortam (MediaBox)",
    "CropBox": "Kırpma (CropBox)",
    "BleedBox": "Taşma (BleedBox)",
    "TrimBox": "Kesim (TrimBox)",
    "ArtBox": "Sanat (ArtBox)",
}
RGB_SPACES = {"RGB", "ICC RGB"}


def _warn(text: str) -> str:
    return f"<span style='color:{WARN}'>{text}</span>"


def _profile(p: IccProfile) -> str:
    return f"{escape(p.name)} <small>({p.color_space}, ICC {p.version})</small>"


def details_html(d: DocDetails, page: int) -> str:
    out = ["<h3>PDF</h3>", f"Sürüm: <b>{escape(d.pdf_version)}</b>"]
    for std in (d.pdfx, d.pdfa):
        if std:
            out.append(f"<br>Uyumluluk: <b>{escape(std)}</b>")

    out.append("<h3>Renk</h3>")
    if d.output_intents:
        for oi in d.output_intents:
            label = escape(oi.condition) or "(adsız)"
            prof = f"<br>&nbsp;&nbsp;{_profile(oi.profile)}" if oi.profile else ""
            out.append(f"Çıktı amacı: <b>{label}</b> <small>{escape(oi.subtype)}</small>{prof}<br>")
    else:
        out.append("Çıktı amacı: yok<br>")
    if d.icc_profiles:
        out.append("Gömülü profiller:<ul style='margin:0'>")
        out += [f"<li>{_profile(p)}</li>" for p in d.icc_profiles]
        out.append("</ul>")
    elif not d.output_intents:
        out.append("Gömülü ICC profili yok<br>")
    spaces = [_warn(s) if s in RGB_SPACES else s for s in d.color_spaces]
    out.append(f"Renk uzayları: {', '.join(spaces) or '—'}")
    if RGB_SPACES & set(d.color_spaces):
        out.append(f"<br>{_warn('<small>RGB nesneler baskıda CMYK’ya dönüştürülür.</small>')}")

    if 1 <= page <= len(d.pages):
        pb = d.pages[page - 1]
        out.append(f"<h3>Sayfa {page} kutuları</h3>")
        for name, label in BOX_LABELS.items():
            if name in pb.boxes:
                w, h = box_size_mm(pb.boxes[name])
                out.append(f"{label}: <b>{w:.1f} × {h:.1f} mm</b><br>")
        if "TrimBox" not in pb.boxes:
            out.append("Kesim kutusu (TrimBox) tanımlı değil<br>")
        bleed = bleed_mm(pb)
        if bleed is not None:
            text = f"Taşma payı: <b>{bleed:.1f} mm</b>"
            out.append((text if bleed > 0.05 else _warn("Taşma payı yok")) + "<br>")
        if pb.rotate:
            out.append(f"Döndürme: {pb.rotate}°<br>")

    out.append(f"<h3>Yazı tipleri ({len(d.fonts)})</h3>")
    if not d.fonts:
        out.append("Yazı tipi yok")
    for f in d.fonts:
        state = ("gömülü, alt küme" if f.subset else "gömülü") if f.embedded else _warn("gömülü değil")
        out.append(f"{escape(f.name)} <small>{escape(f.subtype)}</small> — {state}<br>")
    return "".join(out)


class InfoPanel(QTextBrowser):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setOpenLinks(False)
        self.details: DocDetails | None = None
        self.show_message("Belge açılmadı.")

    def show_message(self, text: str) -> None:
        self.details = None
        self.setHtml(f"<i>{escape(text)}</i>")

    def set_details(self, details: DocDetails, page: int) -> None:
        self.details = details
        self.set_page(page)

    def set_page(self, page: int) -> None:
        if self.details is not None:
            self.setHtml(details_html(self.details, page))
