# Ayrım

Baskıya hazır PDF dosyalarının (CMYK + spot renkler) renk ayrımlarını gösteren
masaüstü uygulaması. Ayrımı Ghostscript'in `tiffsep` cihazı yapar.

## Kurulum (Apple Silicon Mac)

```sh
brew install ghostscript uv
cd color-separation-app
uv sync
uv run ayrim            # veya: uv run ayrim dosya.pdf
```

### Normal uygulama olarak (Ayrim.app)

Terminali yalnızca bir kez, paketi üretmek için kullanırsınız:

```sh
./packaging/build_mac.sh
```

Betik `Ayrim.app`'i üretip Uygulamalar klasörüne kopyalar. Sonra Ayrım'ı
Launchpad'den, Spotlight'tan ya da Dock'tan açabilir, PDF'leri Dock simgesine
bırakabilir veya Finder'da sağ tık > **Birlikte Aç > Ayrım** ile açabilirsiniz.
Ghostscript uygulamaya gömülü değildir, Homebrew'daki `gs` kullanılır. Kod
değiştiğinde betiği yeniden çalıştırmak yeterlidir.

Linux (Arch/CachyOS): `sudo pacman -S ghostscript uv`, sonra aynı komutlar.

## Kullanım

- **Dosya > Aç…** (⌘O) ya da PDF'i pencereye sürükleyin.
- Sağdaki listede kalıpları açıp kapatın; kalıp adının yanında sayfadaki ortalama
  kapsama oranı yazar. Rengi PDF'ten okunamayan bir spotun rengini çift tıklayıp seçin.
- Tek kalıp seçiliyken **Tek kalıbı gri göster** ile kalıp gri tonlu görünür.
- İmleci sayfada gezdirin: alttaki panel her kalıbın yüzdesini ve toplam mürekkebi (TAC) gösterir.
- ◀ ▶ (PageUp/PageDown) ile sayfalar arasında gezinin. ⌘ + tekerlek yakınlaştırır, **Sığdır** (⌘0) geri alır.

İşlenen sayfalar `~/Library/Caches/ayrim` altında saklanır; aynı dosya ve ayarla
yeniden işlenmez.

## Geliştirme

```sh
uv run pytest                                   # testler
uv run python tests/fixtures/make_fixtures.py   # test PDF'lerini yeniden üret
```

Ghostscript ile doğrulanan davranışlar (10.02, `src/ayrim/separations.py`):
- Kalıp pikselinde 0 = %100 mürekkep, 255 = mürekkep yok (`ink_from_pixel`).
- Kalıp dosya adı `p<N>(<ad>).tif`; adda dosya adına uymayan karakterler `%XX`
  olarak yazılır (`/` → `%2F`, `%` → `%25`, `:` → `%3A`).
- `-dSimulateOverprint` artık desteklenmiyor; `-sOverprint=simulate|disable` kullanılıyor.
- Yalnızca sayfada kullanılan spotlar için dosya üretilir; CMYK her zaman üretilir.
