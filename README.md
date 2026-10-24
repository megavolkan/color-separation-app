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

### Windows

[Ghostscript'in 64 bit Windows sürümünü](https://ghostscript.com/releases/gsdnld.html) ve
`uv`'yi (`winget install --id=astral-sh.uv -e`) kurun. Ardından PowerShell'de:

```powershell
.\packaging\build_windows.ps1
```

`dist\Ayrim\Ayrim.exe` oluşur; klasörün tamamını istediğiniz yere taşıyabilirsiniz.

### Hazır paketler (GitHub Actions)

Depo GitHub'a gönderildiğinde `.github/workflows/build.yml` testleri çalıştırır ve macOS,
Windows ve Linux paketlerini üretir (Actions sekmesinde "Artifacts"). Yeni bir sürüm
yayınlamak için `pyproject.toml` içindeki `version` değerini artırıp (ör. `0.1.1` → `0.1.2`)
gönderin: o sürümün etiketi (`v0.1.2`) henüz yoksa iş akışı etiketi oluşturur ve paketleri
GitHub Releases'ta yayınlar. Sürüm numarası değişmeyen gönderimler yalnızca derlenir.

Paketler imzasızdır. macOS'ta ilk açılışta sağ tık > **Aç**, Windows'ta SmartScreen
uyarısında **Ek bilgi > Yine de çalıştır** gerekir. Ghostscript her sistemde ayrıca kurulmalıdır.

Linux (Arch/CachyOS): `sudo pacman -S ghostscript uv`, sonra aynı komutlar.

## Kullanım

- **Dosya > Aç…** (⌘O) ya da PDF'i pencereye sürükleyin.
- Sağdaki listede kalıpları anahtarlarla açıp kapatın; kalıp adının yanında sayfadaki ortalama
  kapsama oranı yazar. O sayfada üste baskı (overprint) ile basılan kalıpların yanında **OP** işareti çıkar. Satırın sağındaki renk kutusuna tıklayarak kalıbın ekran rengini değiştirebilirsiniz
  (rengi PDF'ten okunamayan spotlar için).
- Tek kalıp seçiliyken **Tek kalıbı gri göster** ile kalıp gri tonlu görünür.
- İmleci sayfada gezdirin: alttaki panel her kalıbın yüzdesini ve toplam mürekkebi (TAC) gösterir.
- Sağ üstteki **− 1 / 3 +** düğmeleriyle (PageUp/PageDown) sayfalar arasında gezinin. Büyüteç düğmeleri,
  trackpad'de kıstırma ya da ⌘ + tekerlek yakınlaştırır; çerçeve düğmesi (⌘0) sayfayı pencereye sığdırır.
- **Çözünürlük: Otomatik** sayfayı ekranın (Retina dahil) gerektirdiği çözünürlükte işler;
  yakınlaştırınca daha yüksek DPI ile yeniden işler. İsterseniz sabit 72/150/300/600 dpi seçin.
- Soldaki **Belge bilgisi** paneli (⌘I ile açılıp kapanır) PDF sürümünü ve PDF/X uyumluluğunu,
  çıktı amacını ve gömülü ICC profillerini, kullanılan renk uzaylarını, o sayfanın kutularını
  (Media/Trim/Bleed…, mm cinsinden) ve taşma payını, yazı tiplerinin gömülü olup olmadığını gösterir.
  RGB nesneler ve gömülmemiş yazı tipleri vurgu rengiyle işaretlenir. **Üste baskı** satırı üste baskı ile
  basılan kalıpları listeler; yanındaki (i) üzerine gelince üste baskının ne olduğu anlatılır.
- **Dosya > Kapat** (⌘W) belgeyi kapatır, uygulama açık kalır.
- Araç çubuğundaki ay / güneş düğmesi (⌘⇧T) açık ve koyu tema arasında geçer;
  seçim hatırlanır. İlk açılışta sistemin teması kullanılır.

İşlenen sayfalar `~/Library/Caches/ayrim` altında saklanır; aynı dosya ve ayarla
yeniden işlenmez.

## Geliştirme

```sh
uv run pytest                                   # testler
uv run python tests/fixtures/make_fixtures.py   # test PDF'lerini yeniden üret
```

Ghostscript ile doğrulanan davranışlar (10.02, `src/ayrim/separations.py`):
- Kalıp pikselinde 0 = %100 mürekkep, 255 = mürekkep yok (`ink_from_pixel`).
- Kalıp dosya adı `p<N>(<ad>).tif` (Ghostscript 10.08'den itibaren `p<N>.tif(<ad>).tif`); adda dosya adına uymayan karakterler `%XX`
  olarak yazılır (`/` → `%2F`, `%` → `%25`, `:` → `%3A`).
- `-dSimulateOverprint` artık desteklenmiyor; `-sOverprint=simulate|disable` kullanılıyor.
- Yalnızca sayfada kullanılan spotlar için dosya üretilir; CMYK her zaman üretilir.
