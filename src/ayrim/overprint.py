"""Üste baskı (overprint) ile boyanan mürekkepleri bulur.

Sayfanın içerik akışı grafik durumu izlenerek okunur: ExtGState'teki /OP (çizgi) ve /op
(dolgu) açıkken boyanan her nesnenin rengi, hangi kalıplara mürekkep koyduğuna çevrilir.
Sonuç kalıp adlarıdır (Cyan, Magenta, Yellow, Black ve spot adları), Ghostscript'in
kalıp adlarıyla aynıdır.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import pikepdf

from .pdfinfo import name_str
from .separations import PROCESS_NAMES

_FILL_OPS = {"f", "F", "f*"}
_STROKE_OPS = {"S", "s"}
_BOTH_OPS = {"B", "B*", "b", "b*"}
_TEXT_OPS = {"Tj", "TJ", "'", '"'}


@dataclass
class _Color:
    space: object = pikepdf.Name("/DeviceGray")  # renk uzayı nesnesi
    values: tuple[float, ...] = (0.0,)


@dataclass
class _State:
    fill: _Color = field(default_factory=_Color)
    stroke: _Color = field(default_factory=_Color)
    op_fill: bool = False
    op_stroke: bool = False
    text_mode: int = 0

    def copy(self) -> _State:
        return replace(self, fill=replace(self.fill), stroke=replace(self.stroke))


def _initial_values(space) -> tuple[float, ...]:
    """Renk uzayı seçilince (cs/CS) geçerli olan başlangıç rengi."""
    if isinstance(space, pikepdf.Name):
        return {"/DeviceCMYK": (0.0, 0.0, 0.0, 1.0), "/DeviceRGB": (0.0, 0.0, 0.0)}.get(str(space), (0.0,))
    if isinstance(space, pikepdf.Array) and len(space):
        kind = name_str(space[0])
        if kind in ("Separation",):
            return (1.0,)
        if kind == "DeviceN":
            return tuple(1.0 for _ in space[1])
        if kind == "ICCBased":
            n = int(space[1].get("/N", 1))
            return (0.0, 0.0, 0.0, 1.0) if n == 4 else (0.0,) * n
    return (0.0,)


def inks_of(space, values: tuple[float, ...]) -> set[str]:
    """Bu renk hangi kalıplara mürekkep koyar?"""
    v = list(values)
    if isinstance(space, pikepdf.Name):
        s = str(space)
        if s == "/DeviceCMYK" and len(v) >= 4:
            return {n for n, x in zip(PROCESS_NAMES, v) if x > 0}
        if s == "/DeviceGray" and v:
            return {"Black"} if v[0] < 1 else set()
        return set()  # RGB'de üste baskının kalıplara etkisi yok
    if not isinstance(space, pikepdf.Array) or not len(space):
        return set()
    kind = name_str(space[0])
    if kind == "Separation":
        name = name_str(space[1])
        if name == "None" or not v or v[0] <= 0:
            return set()
        if name == "All":
            return set(PROCESS_NAMES)
        return {name}
    if kind == "DeviceN":
        return {name_str(n) for n, x in zip(space[1], v) if x > 0 and name_str(n) != "None"}
    if kind == "ICCBased":
        n = int(space[1].get("/N", 0))
        if n == 4:
            return inks_of(pikepdf.Name("/DeviceCMYK"), values)
        if n == 1:
            return inks_of(pikepdf.Name("/DeviceGray"), values)
    return set()


class _Scanner:
    def __init__(self) -> None:
        self.inks: set[str] = set()
        self._depth = 0

    def run(self, stream, resources, state: _State) -> None:
        if self._depth > 12:
            return
        self._depth += 1
        try:
            instructions = pikepdf.parse_content_stream(stream)
        except Exception:
            instructions = []
        stack: list[_State] = []
        st = state
        for operands, op in instructions:
            op = str(op)
            try:
                st = self._step(op, operands, st, stack, resources)
            except Exception:
                continue  # beklenmeyen biçim: o komutu atla
        self._depth -= 1

    def _space(self, operand, resources):
        name = str(operand)
        if name in ("/DeviceCMYK", "/DeviceRGB", "/DeviceGray"):
            return pikepdf.Name(name)
        cs = resources.get("/ColorSpace") if isinstance(resources, pikepdf.Dictionary) else None
        if isinstance(cs, pikepdf.Dictionary) and name in cs:
            return cs[name]
        return pikepdf.Name(name)

    def _paint(self, color: _Color, active: bool) -> None:
        if active:
            self.inks |= inks_of(color.space, color.values)

    def _step(self, op, operands, st: _State, stack: list[_State], resources) -> _State:
        if op == "q":
            stack.append(st.copy())
        elif op == "Q":
            if stack:
                st = stack.pop()
        elif op == "gs":
            eg = resources.get("/ExtGState", {}).get(str(operands[0]))
            if isinstance(eg, pikepdf.Dictionary):
                if "/OP" in eg:
                    st.op_stroke = bool(eg["/OP"])
                    if "/op" not in eg:
                        st.op_fill = st.op_stroke
                if "/op" in eg:
                    st.op_fill = bool(eg["/op"])
        elif op in ("k", "K", "g", "G", "rg", "RG"):
            space = {"k": "/DeviceCMYK", "g": "/DeviceGray", "rg": "/DeviceRGB"}[op.lower()]
            color = _Color(pikepdf.Name(space), tuple(float(x) for x in operands))
            if op.islower():
                st.fill = color
            else:
                st.stroke = color
        elif op in ("cs", "CS"):
            space = self._space(operands[0], resources)
            color = _Color(space, _initial_values(space))
            if op == "cs":
                st.fill = color
            else:
                st.stroke = color
        elif op in ("sc", "scn", "SC", "SCN"):
            nums = tuple(float(x) for x in operands if isinstance(x, (int, float)) or hasattr(x, "__float__"))
            target = st.fill if op.islower() else st.stroke
            if not isinstance(operands[-1], pikepdf.Name):  # desen değilse
                target.values = nums
        elif op == "Tr":
            st.text_mode = int(operands[0])
        elif op in _FILL_OPS:
            self._paint(st.fill, st.op_fill)
        elif op in _STROKE_OPS:
            self._paint(st.stroke, st.op_stroke)
        elif op in _BOTH_OPS:
            self._paint(st.fill, st.op_fill)
            self._paint(st.stroke, st.op_stroke)
        elif op in _TEXT_OPS:
            mode = st.text_mode % 4
            if mode in (0, 2):
                self._paint(st.fill, st.op_fill)
            if mode in (1, 2):
                self._paint(st.stroke, st.op_stroke)
        elif op == "sh" and st.op_fill:
            sh = resources.get("/Shading", {}).get(str(operands[0]))
            if isinstance(sh, (pikepdf.Dictionary, pikepdf.Stream)):
                space = sh.get("/ColorSpace")
                n = len(space[1]) if isinstance(space, pikepdf.Array) and name_str(space[0]) == "DeviceN" else 4
                self.inks |= inks_of(space, (1.0,) * n)
        elif op == "Do":
            xo = resources.get("/XObject", {}).get(str(operands[0]))
            if isinstance(xo, pikepdf.Stream):
                sub = str(xo.get("/Subtype", ""))
                if sub == "/Form":
                    self.run(xo, xo.get("/Resources", resources), st.copy())
                elif sub == "/Image" and xo.get("/ImageMask", False):
                    self._paint(st.fill, st.op_fill)
        return st


def overprinted_inks(page: pikepdf.Page) -> set[str]:
    """Sayfada üste baskı ile boyanan nesnelerin kalıp adları."""
    scanner = _Scanner()
    scanner.run(page, page.resources, _State())
    return scanner.inks


def ink_order(names: set[str]) -> list[str]:
    """Önce CMYK (sırasıyla), sonra spotlar alfabetik."""
    return [n for n in PROCESS_NAMES if n in names] + sorted(names - set(PROCESS_NAMES), key=str.casefold)
