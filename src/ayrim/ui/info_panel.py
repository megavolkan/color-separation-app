"""Belge bilgisi paneli: PDF sürümü, renk profilleri, sayfa kutuları ve yazı tipleri.

Her bölüm bir başlık ve anahtar (sağa yaslı) / değer (sola yaslı) tablosundan oluşur.
"""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocumentFragment
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..docdetails import DocDetails, IccProfile, bleed_mm, box_size_mm, page_ranges
from .plate_list import OVERPRINT_HELP
from .theme import LIGHT, Theme
from .widgets import InfoButton

PADDING = 10
BOX_LABELS = {
    "MediaBox": "Ortam (MediaBox)",
    "CropBox": "Kırpma (CropBox)",
    "BleedBox": "Taşma (BleedBox)",
    "TrimBox": "Kesim (TrimBox)",
    "ArtBox": "Sanat (ArtBox)",
}
RGB_SPACES = {"RGB", "ICC RGB"}
OVERPRINT_KEY = "Üste baskı"
BLEND_KEY = "Karışım uzayı"
BLEND_HELP = (
    "<b>Saydamlık karışım renk uzayı</b><br>"
    "PDF sayfasındaki saydamlık ve üste baskı etkileri, sayfa grubunun renk uzayında hesaplanır. "
    "Bu uzay CMYK ise mürekkepler ayrı ayrı korunur ve üste baskı doğru sonuç verir.<br><br>"
    "RGB ise karışım RGB'de yapılır: üste baskılı spot rengin altındaki CMYK mürekkepleri silinebilir "
    "(boşaltma) ve renkler RGB'ye gidip gelirken değişebilir. Bu sayfalarda önizleme ile baskı farklı olabilir.<br><br>"
    "Çözüm: tasarım programında belge renk biçimini CMYK seçip CMYK çıktıyla (örn. PDF/X-4) dışa aktarın."
)
INFO_KEYS = {
    OVERPRINT_KEY: OVERPRINT_HELP + "<br><br>Kalıp listesinde bu kalıpların yanında <b>OP</b> işareti görünür.",
    BLEND_KEY: BLEND_HELP,
}

Rows = list[tuple[str, str]]  # (anahtar, değer HTML'i)


def _profile(p: IccProfile) -> str:
    return f"{escape(p.name)} ({p.color_space}, ICC {p.version})"


def sections(d: DocDetails, page: int, t: Theme) -> list[tuple[str, Rows | str]]:
    """Panel bölümleri: (başlık, satırlar) ya da (başlık, satır yoksa gösterilecek metin)."""

    def accent(text: str, small: bool = False) -> str:
        size = " font-size:9px;" if small else ""
        return f"<span style='color:{t.accent};{size}'>{text}</span>"

    pdf: Rows = [("Sürüm", escape(d.pdf_version))]
    pdf += [("Uyumluluk", escape(s)) for s in (d.pdfx, d.pdfa) if s]

    color: Rows = []
    if d.output_intents:
        for oi in d.output_intents:
            value = escape(oi.condition) or "(adsız)"
            if oi.profile:
                value += f"<br>{_profile(oi.profile)}"
            color.append(("Çıktı amacı", value))
    else:
        color.append(("Çıktı amacı", "Yok"))
    color.append(("Gömülü profiller", "<br><br>".join(_profile(p) for p in d.icc_profiles) or "Yok"))
    lines = [accent(s) if s in RGB_SPACES else escape(s) for s in d.color_spaces]
    if RGB_SPACES & set(d.color_spaces):
        last = max(i for i, s in enumerate(d.color_spaces) if s in RGB_SPACES)
        lines[last] += " " + accent("RGB nesneler baskıda CMYK’ya dönüştürülür.", small=True)
    color.append(("Renk uzayları", "<br>".join(lines) or "—"))
    color.append((OVERPRINT_KEY, "<br>".join(escape(n) for n in d.overprint) or "Yok"))
    spaces_used = sorted({p.blend_space for p in d.pages if p.blend_space})
    if spaces_used:
        rgb = d.rgb_blend_pages
        if rgb:
            where = "tüm sayfalar" if len(rgb) == len(d.pages) else f"sayfa {page_ranges(rgb)}"
            value = accent(f"RGB ({where})") + " " + accent(
                "Üste baskı ve saydamlık bu sayfalarda CMYK'daki gibi görünmeyebilir.", small=True)
            others = [s for s in spaces_used if s != "RGB"]
            if others:
                rest = [p.number for p in d.pages if p.blend_space and p.blend_space != "RGB"]
                value = f"{'/'.join(others)} (sayfa {page_ranges(rest)})<br>" + value
        else:
            value = ", ".join(spaces_used)
        color.append((BLEND_KEY, value))

    out: list[tuple[str, Rows | str]] = [("PDF", pdf), ("Renk", color)]
    if 1 <= page <= len(d.pages):
        pb = d.pages[page - 1]
        boxes: Rows = []
        for name, label in BOX_LABELS.items():
            if name in pb.boxes:
                w, h = box_size_mm(pb.boxes[name])
                boxes.append((label, f"{w:.1f} × {h:.1f} mm"))
            elif name == "TrimBox":
                boxes.append((label, accent("tanımlı değil")))
        bleed = bleed_mm(pb)
        if bleed is not None:
            boxes.append(("Taşma payı", f"{bleed:.1f} mm" if bleed > 0.05 else accent("yok")))
        if pb.rotate:
            boxes.append(("Döndürme", f"{pb.rotate}°"))
        out.append((f"Sayfa {page} Kutuları", boxes))

    fonts: Rows = []
    for f in d.fonts:
        state = ("gömülü, alt küme" if f.subset else "gömülü") if f.embedded else accent("gömülü değil")
        fonts.append((escape(f.name), f"{escape(f.subtype)} · {state}"))
    out.append(("Yazı Tipleri", fonts or "Yazı tipi yok"))
    return out


def _label(html: str, name: str) -> QLabel:
    lab = QLabel(html)
    lab.setObjectName(name)
    lab.setTextFormat(Qt.TextFormat.RichText)
    lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lab


class InfoPanel(QScrollArea):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.theme = LIGHT
        self.details: DocDetails | None = None
        self.page = 1
        self._message = "Belge açılmadı."
        self._rebuild()

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self._rebuild()

    def show_message(self, text: str) -> None:
        self.details, self._message = None, text
        self._rebuild()

    def set_details(self, details: DocDetails, page: int) -> None:
        self.details, self.page = details, page
        self._rebuild()

    def set_page(self, page: int) -> None:
        self.page = page
        if self.details is not None:
            self._rebuild()

    def text(self) -> str:
        """Paneldeki görünen metin, satır satır (testler için)."""
        return "\n".join(
            QTextDocumentFragment.fromHtml(lab.text()).toPlainText() for lab in self.widget().findChildren(QLabel)
        )

    def _rebuild(self) -> None:
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        if self.details is None:
            box = QWidget()
            bl = QVBoxLayout(box)
            bl.setContentsMargins(PADDING, PADDING, PADDING, PADDING)
            msg = _label(escape(self._message), "muted")
            msg.setWordWrap(True)
            bl.addWidget(msg)
            lay.addWidget(box)
        else:
            for i, (title, rows) in enumerate(sections(self.details, self.page, self.theme)):
                if i:
                    line = QFrame()
                    line.setObjectName("sectionLine")
                    lay.addWidget(line)
                lay.addWidget(self._section(title, rows))
        lay.addStretch(1)
        old = self.takeWidget()
        if old is not None:
            old.deleteLater()
        self.setWidget(inner)

    def _section(self, title: str, rows: Rows | str) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(PADDING, PADDING, PADDING, PADDING)
        lay.setSpacing(PADDING)
        lay.addWidget(_label(escape(title) + ":", "sectionTitle"))
        if isinstance(rows, str):
            lay.addWidget(_label(escape(rows), "muted"))
            return box
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(PADDING)
        grid.setVerticalSpacing(4)
        grid.setColumnStretch(1, 1)
        for r, (key, value) in enumerate(rows):
            key_cell = _label(key + ":", "key")
            if key in INFO_KEYS:
                # Anahtarın soluna, üzerine gelince ne olduğunu anlatan (i) düğmesi.
                key_cell = QWidget()
                kl = QHBoxLayout(key_cell)
                kl.setContentsMargins(0, 0, 0, 0)
                kl.setSpacing(4)
                kl.addWidget(InfoButton(INFO_KEYS[key]))
                kl.addWidget(_label(key + ":", "key"))
            grid.addWidget(key_cell, r, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            v = _label(value, "value")
            v.setWordWrap(True)
            # Uzun değerler panel genişliğinde satıra bölünsün, paneli genişletip taşmasın.
            v.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            v.setMinimumWidth(1)
            grid.addWidget(v, r, 1, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(grid)
        return box
