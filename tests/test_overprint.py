"""Üste baskı ile boyanan kalıpların bulunması."""

from ayrim.docdetails import read_doc_details

from make_fixtures import PAGE, PdfWriter, separation_cs


def overprint_pdf(path, content: str, form: str | None = None) -> None:
    w = PdfWriter()
    pages = w.reserve()
    cs = separation_cs(w, "PANTONE 185 C")
    op = w.add("<< /Type /ExtGState /OP true /OPM 1 >>")
    fill_only = w.add("<< /Type /ExtGState /OP false /op true >>")
    xobj = ""
    if form is not None:
        f = w.add(
            f"<< /Type /XObject /Subtype /Form /BBox [0 0 {PAGE} {PAGE}] /Length {len(form)} >>\n"
            f"stream\n{form}\nendstream".encode("latin-1")
        )
        xobj = f"/XObject << /Fm0 {f} 0 R >>"
    content_obj = w.stream(content)
    page = w.add(
        f"<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 {PAGE} {PAGE}] "
        f"/Resources << /ColorSpace << /CS0 {cs} 0 R >> /ExtGState << /GSop {op} 0 R /GSfill {fill_only} 0 R >> "
        f"{xobj} >> /Contents {content_obj} 0 R >>"
    )
    w.set(pages, f"<< /Type /Pages /Kids [{page} 0 R] /Count 1 >>")
    w.write(path, w.add(f"<< /Type /Catalog /Pages {pages} 0 R >>"))


BACKGROUND = "0 0 0.1 0 k 0 0 300 300 re f\n"  # üste baskının etkisi olsun diye altta mürekkep


def inks(tmp_path, content, form=None, background=BACKGROUND):
    pdf = tmp_path / "op.pdf"
    overprint_pdf(pdf, background + content, form)
    return list(read_doc_details(pdf).pages[0].overprint)


def test_black_text_and_q_restore(tmp_path):
    # siyah dolgu üste baskılı; q/Q sonrası cyan kutu üste baskısız
    content = "q /GSop gs 0 0 0 1 k 10 10 50 50 re f Q 1 0 0 0 k 70 10 50 50 re f"
    assert inks(tmp_path, content) == ["Black"]


def test_spot_stroke_and_cmyk_components(tmp_path):
    content = "/GSop gs /CS0 CS 0.5 SCN 10 10 m 100 100 l S 0 0.4 0.2 0 k 10 10 50 50 re f"
    assert inks(tmp_path, content) == ["Magenta", "Yellow", "PANTONE 185 C"]


def test_fill_only_and_zero_tint(tmp_path):
    # /op yalnız dolgu için; çizgi üste baskısız. %0 tint mürekkep koymaz.
    content = "/GSfill gs 1 0 0 0 K 10 10 m 50 50 l S /CS0 cs 0 scn 10 10 50 50 re f"
    assert inks(tmp_path, content) == []


def test_inside_form_xobject(tmp_path):
    content = "/GSop gs /Fm0 Do"
    form = "0 0 0 0.6 k 10 10 50 50 re f"
    assert inks(tmp_path, content, form) == ["Black"]


def test_ineffective_overprint_ignored(tmp_path):
    # Affinity çıktısı gibi: en alttaki spot zemin üste baskılı ama altında hiçbir şey yok;
    # kesim işaretleri kayıt rengiyle (/All) üste baskılı çiziliyor. İkisi de baskıyı değiştirmez.
    w = PdfWriter()
    pages = w.reserve()
    spot = separation_cs(w, "PANTONE 185 C")
    fn = w.add("<< /FunctionType 2 /Domain [0 1] /C0 [1] /C1 [0] /N 1 >>")
    reg = w.add(f"[/Separation /All /DeviceGray {fn} 0 R]")
    gs0 = w.add("<< /Type /ExtGState /OP false /op true /OPM 1 >>")
    gs5 = w.add("<< /Type /ExtGState /OP true /op false /OPM 1 >>")
    content = w.stream(
        "/GS0 gs /C4 cs 1 scn 0 0 300 300 re f\n"
        "/GS5 gs /C5 CS 1 SCN 5 5 m 20 5 l S\n"
    )
    page = w.add(
        f"<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 {PAGE} {PAGE}] "
        f"/Resources << /ColorSpace << /C4 {spot} 0 R /C5 {reg} 0 R >> "
        f"/ExtGState << /GS0 {gs0} 0 R /GS5 {gs5} 0 R >> >> /Contents {content} 0 R >>"
    )
    w.set(pages, f"<< /Type /Pages /Kids [{page} 0 R] /Count 1 >>")
    pdf = tmp_path / "affinity.pdf"
    w.write(pdf, w.add(f"<< /Type /Catalog /Pages {pages} 0 R >>"))
    assert read_doc_details(pdf).overprint == []


def test_no_overprint(tmp_path, fixtures_dir):
    assert inks(tmp_path, "0 0 0 1 k 10 10 50 50 re f") == []
    assert inks(tmp_path, "/GSop gs 0 0 0 1 k 10 10 50 50 re f", background="") == []
    assert read_doc_details(fixtures_dir / "basic.pdf").overprint == ["PANTONE 185 C"]
