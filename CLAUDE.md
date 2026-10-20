# Ayrım — PDF Renk Ayrımı Önizleyicisi

Baskıya hazır PDF dosyalarının (CMYK + spot renkler) renk ayrımlarını gösteren,
Acrobat Pro "Output Preview / Separations" benzeri bir masaüstü uygulaması.
Kişisel kullanım için; macOS (Apple Silicon) ve Linux'ta çalışmalı.

## Teknoloji

- Python 3.12+, `uv` ile proje ve bağımlılık yönetimi
- Arayüz: PySide6 (Qt)
- Ayrım motoru: Ghostscript (`gs`), `tiffsep` cihazı, subprocess ile çağrılır
- Görüntü işleme: numpy, tifffile (veya Pillow)
- PDF meta verisi (sayfa sayısı, sayfa boyutu, spot renklerin alternatif
  renk değerleri): PyMuPDF veya pikepdf
- Testler: pytest

Ghostscript kurulumu: macOS `brew install ghostscript`, Arch/CachyOS
`pacman -S ghostscript`. Uygulama açılışta `gs` yolunu ve sürümünü kontrol
etmeli; bulunamazsa anlaşılır bir hata göstermeli.

## Temel çalışma prensibi

Her sayfa için Ghostscript şu şekilde çağrılır:

```
gs -dSAFER -dBATCH -dNOPAUSE -sDEVICE=tiffsep -r<DPI> \
   -dFirstPage=N -dLastPage=N -dSimulateOverprint=true \
   -o <cache>/p<N>.tif <dosya.pdf>
```

Çıktı: kompozit `p<N>.tif` + her kalıp için `p<N>(Cyan).tif`,
`p<N>(PANTONE 185 C).tif` vb. gri tonlu dosyalar.

Önemli:
- Kalıp adları dosya adlarından okunur; spot renk adlarında boşluk, nokta,
  özel karakter olabilir, dosya adı ayrıştırması buna dayanıklı olmalı.
- Piksel değeri ile mürekkep yüzdesi arasındaki ilişki (0 = tam mürekkep mi,
  255 mi?) VARSAYILMAMALI; test PDF'leriyle doğrulanmalı ve tek bir yerde
  (`ink_from_pixel`) tanımlanmalı.
- Sayfalar ihtiyaç oldukça (lazy) işlenir; sonuçlar dosya hash'i + sayfa +
  DPI + overprint ayarına göre geçici bir önbellekte tutulur.
- Ghostscript çalışırken arayüz donmamalı (QThread / QThreadPool).

## Özellikler

### Faz 1 — MVP
1. PDF açma (menü + sürükle-bırak)
2. Sayfa için kalıp listesi: her kalıp için onay kutusu, renk örneği, ad
3. Seçili kalıpları birleştirerek önizleme
4. Tek kalıp seçiliyken gri tonlu görüntüleme seçeneği
5. İmleç altındaki noktada her kalıbın mürekkep yüzdesi ve toplam (TAC)
   alt panelde gösterilir
6. Sayfalar arası gezinme

### Faz 2
7. Yakınlaştırma/kaydırma (QGraphicsView); yakınlaşınca daha yüksek DPI ile
   yeniden işleme seçeneği
8. TAC uyarısı: eşik (varsayılan %300, ayarlanabilir) üstündeki alanları
   renkli vurgulama
9. Overprint simülasyonu açık/kapalı
10. DPI seçimi (örn. 72 / 150 / 300)

### Faz 3
11. Belge geneli kalıp özeti: hangi spot renk hangi sayfalarda kullanılıyor,
    yaklaşık kapsama oranı
12. Seçili kalıbı PNG olarak dışa aktarma
13. Basit rapor (sayfa başına kalıplar, maksimum TAC)

## Önizleme renklendirme

Ekranda kalıplar subtractive yaklaşık birleştirmeyle gösterilir:
her kalıbın sRGB karşılığı `c` ve mürekkep oranı `t` (0..1) için piksel
rengi, beyazdan başlayarak `rgb *= 1 - t * (1 - c)` ile çarpılarak bulunur.
- CMYK kalıpları için sabit sRGB değerleri kullanılır.
- Spot renklerin rengi PDF'teki Separation/DeviceN renk uzayının alternatif
  değerinden hesaplanır; okunamazsa kullanıcı rengi elle seçebilir.
Bu bir ekran önizlemesidir, renk doğruluğu iddiası yoktur; amaç ayrımın
yapısını ve mürekkep miktarlarını göstermektir.

## Doğrulama (test PDF'leri)

`tests/fixtures/` altında bilinen değerlerle hazırlanmış PDF'ler olmalı:
- C100, M50, Y25, K100 kutuları
- %100 ve %50 tonda bir spot renk kutusu
- Spot rengin CMYK üzerine overprint edildiği alan
- Spot renk içeren şeffaflık / gradyan
- Birden çok sayfa, farklı sayfalarda farklı spotlar
Testler, bu kutuların merkezindeki ölçülen mürekkep yüzdesinin beklenen
değere ±%2 içinde olduğunu doğrular.

## Kod düzeni

```
src/ayrim/
  gs.py          # Ghostscript bulma, çağırma, önbellek
  separations.py # tiff'leri okuma, kalıp listesi, ink_from_pixel
  pdfinfo.py     # sayfa bilgisi, spot renk alternatif değerleri
  composite.py   # önizleme birleştirme, TAC hesabı
  ui/            # PySide6 pencere ve paneller
tests/
```

Çekirdek mantık (gs.py, separations.py, composite.py) arayüzden bağımsız ve
test edilebilir olmalı.

## Çalışma kuralları

- Her fazı küçük adımlarla ilerlet; her adımın sonunda testler geçmeli.
- Ghostscript davranışı hakkında emin olunmayan her şeyi (çıktı adları,
  piksel yönü, spot sınırı) gerçek bir çalıştırmayla doğrula.
- Kullanıcının asıl dosyaları Affinity'den export edilmiş PDF/X dosyalarıdır.
