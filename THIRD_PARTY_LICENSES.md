# Üçüncü taraf lisansları

Ayrım, aşağıdaki açık kaynak bileşenleri kullanır. Ayrım'ın kendisi
[GNU Affero Genel Kamu Lisansı 3.0 veya sonrası](LICENSE) ile lisanslanmıştır.
Bu dosyadaki lisansların tamamı AGPL-3.0 ile uyumludur. Ayrım: telif hakkı © 2026 megavolkan.

## Hazır paketlerin içinde dağıtılanlar

Hazır paketler (Ayrim.app, Windows ve Linux paketleri) PyInstaller ile üretilir ve
aşağıdakileri içerir. Her bileşenin tam lisans metni, belirtilen proje sayfasında ve
paket içindeki `*.dist-info` klasörlerinde bulunur.

| Bileşen | Lisans | Kaynak |
|---|---|---|
| Qt 6 ve PySide6 / Shiboken6 | LGPL-3.0 (GPL-2.0 / GPL-3.0 seçenekli) | https://www.qt.io/ · https://pyside.org |
| pikepdf | MPL-2.0 | https://github.com/pikepdf/pikepdf |
| qpdf (pikepdf içinde) | Apache-2.0 | https://github.com/qpdf/qpdf |
| NumPy | BSD-3-Clause (ve içindeki bileşenler için 0BSD, MIT, Zlib, CC0-1.0) | https://numpy.org |
| Pillow | MIT-CMU (HPND) | https://python-pillow.github.io |
| Pillow içindeki görüntü kitaplıkları (libjpeg-turbo, libpng, libtiff, zlib, FreeType…) | Kendi lisansları (BSD/IJG/zlib türü) | https://github.com/python-pillow/Pillow |
| lxml | BSD-3-Clause | https://lxml.de |
| packaging | Apache-2.0 veya BSD-2-Clause | https://github.com/pypa/packaging |
| Python | PSF-2.0 | https://www.python.org |
| PyInstaller önyükleyicisi | GPL-2.0, önyükleyici istisnasıyla | https://pyinstaller.org |

**Qt / PySide6 (LGPL-3.0):** Qt kitaplıkları pakette ayrı dosyalar olarak durur
(macOS'ta `Ayrim.app/Contents/Frameworks`, Windows ve Linux'ta `_internal`). Kullanıcı
bunları uyumlu başka bir Qt sürümüyle değiştirebilir. Qt'nin kaynak kodu
https://download.qt.io/ adresindedir.

## Ayrı program olarak kullanılan: Ghostscript

Renk ayrımları [GPL Ghostscript](https://ghostscript.com) ile üretilir. Ghostscript,
Artifex Software, Inc. tarafından geliştirilen ve **AGPL-3.0** ile lisanslanan ayrı bir
programdır. Ayrım ona bağlanmaz (link edilmez); bilgisayarda kurulu `gs` / `gswin64c`
programını komut satırından çalıştırır.

- Lisans: https://www.ghostscript.com/licensing/
- Kaynak kod: https://github.com/ArtifexSoftware/ghostpdl ve
  https://ghostscript.com/releases/gsdnld.html

Ghostscript, Artifex Software, Inc.'in ticari markasıdır. Ayrım, Artifex ile ilişkili
değildir.
