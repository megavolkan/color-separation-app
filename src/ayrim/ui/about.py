"""Hakkında penceresi: sürüm, lisans (AGPL-3.0 §5d gereği) ve Ghostscript bilgisi."""

from __future__ import annotations

from html import escape

from .. import __version__
from ..gs import Ghostscript

SOURCE_URL = "https://github.com/megavolkan/color-separation-app"
LICENSE_URL = "https://www.gnu.org/licenses/agpl-3.0.html"
GS_SOURCE_URL = "https://github.com/ArtifexSoftware/ghostpdl"


def about_html(gs: Ghostscript | None) -> str:
    if gs is not None:
        gs_line = f"Ghostscript {escape(gs.version)} kullanılıyor: <code>{escape(gs.path)}</code>"
    else:
        gs_line = "Ghostscript bulunamadı."
    return (
        f"<h3>Ayrım {escape(__version__)}</h3>"
        "<p>PDF renk ayrımı önizleyicisi (CMYK ve spot kalıplar).</p>"
        "<p>Telif hakkı © 2026 megavolkan</p>"
        "<p>Bu program özgür yazılımdır: <a href='"
        f"{LICENSE_URL}'>GNU Affero Genel Kamu Lisansı</a> 3. sürümü ya da (tercihinize göre) "
        "daha sonraki bir sürümü kapsamında dağıtabilir ve değiştirebilirsiniz. Program yararlı olacağı "
        "umuduyla, ancak <b>HİÇBİR GARANTİ OLMADAN</b> dağıtılır; SATILABİLİRLİK veya BELİRLİ BİR AMACA "
        "UYGUNLUK garantisi dahil değildir.</p>"
        f"<p>Kaynak kod: <a href='{SOURCE_URL}'>{SOURCE_URL}</a></p>"
        f"<p>{gs_line}<br>Ghostscript, Artifex Software, Inc. tarafından geliştirilen ve AGPL-3.0 ile "
        f"lisanslanan ayrı bir programdır (<a href='{GS_SOURCE_URL}'>kaynak kod</a>). Ayrım, Artifex "
        "ile ilişkili değildir.</p>"
        "<p>Kullanılan diğer açık kaynak bileşenler THIRD_PARTY_LICENSES.md dosyasında listelenir.</p>"
    )
