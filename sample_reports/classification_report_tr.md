# besFundLens Varlık Dağılımı Sınıflandırma Raporu

## Varlık Dağılımı Sınıfları

| Varlık Sınıfı | Aile | Fon Sayısı | Ort. Güven | Ort. Kararlılık |
|---|---|---:|---:|---:|
| Hisse Senedi Ağırlıklı | Hisse | 141 | 0.60 | 0.99 |
| Sabit Getirili Ağırlıklı | Sabit Getirili | 141 | 0.59 | 0.99 |
| Kira Sertifikası Eğilimli Çoklu Varlık | Sabit Getirili | 68 | 0.56 | 1.00 |
| Kıymetli Maden Ağırlıklı | Kıymetli Maden | 25 | 0.73 | 0.99 |
| Yatırım Fonu Eğilimli Çoklu Varlık | Fon Sepeti | 24 | 0.09 | 0.99 |

## Risk Bantları

| Risk Bandı | Fon Sayısı |
|---|---:|
| Uzmanlaşmış | 123 |
| Muhafazakâr | 116 |
| Dengeli | 88 |
| Atak | 72 |

## Kur Riski Bantları

| Kur Bandı | Fon Sayısı |
|---|---:|
| TRY Ağırlıklı | 303 |
| Karma Kur | 45 |
| FX Ağırlıklı | 29 |
| Altın Ağırlıklı | 22 |

## Katılım / Konvansiyonel Dağılımı

| Katılım | Fon Sayısı |
|---|---:|
| Konvansiyonel | 261 |
| Katılım | 132 |
| Karma | 5 |
| Bilinmiyor | 1 |

## Stil Kayması İzleme Listesi

| Fon | Varlık Sınıfı | Stil Kayması | Kararlılık | Güven |
|---|---|---:|---:|---:|
| AEZ | Hisse Senedi Ağırlıklı | 189.2 | 0.75 | 0.07 |
| TNE | Hisse Senedi Ağırlıklı | 124.5 | 1.00 | 0.41 |
| AUG | Sabit Getirili Ağırlıklı | 89.7 | 1.00 | 0.53 |
| BBD | Hisse Senedi Ağırlıklı | 85.0 | 1.00 | 0.77 |
| AVJ | Kira Sertifikası Eğilimli Çoklu Varlık | 60.0 | 1.00 | 0.29 |
| GGJ | Kıymetli Maden Ağırlıklı | 49.8 | 0.75 | 0.24 |
| ACV | Kira Sertifikası Eğilimli Çoklu Varlık | 49.6 | 1.00 | 0.32 |
| VEY | Kira Sertifikası Eğilimli Çoklu Varlık | 47.7 | 1.00 | 0.10 |
| RZN | Yatırım Fonu Eğilimli Çoklu Varlık | 45.9 | 1.00 | 0.11 |
| IEE | Hisse Senedi Ağırlıklı | 45.3 | 1.00 | 0.63 |

## Sınıflandırma Kalitesi

- Model: **Pencere-ortalamalı dağılım vektörleri üzerinde KMeans**
- Sınıf sayısı (k): **5**
- Silhouette skoru: **0.523**
- Sınıflandırılan fon sayısı: **399**
- Sınıflandırma penceresi: **2026-05-08 - 2026-08-07**
- Düşük güvenli fon sayısı: **53**
- Yoğun look-through fon sayısı: **30**

## Sınıflandırma Notları

- Sınıflar, pencere-ortalamalı dağılım vektörlerinin kümelenmesiyle keşfedilir; sınıf adları her kümenin merkezinden türetilir.
- `Güven`, en yakın ve ikinci en yakın sınıf arasındaki marjdır ve portföyün başka fonlarda tutulan payı oranında düşürülür.
- `Kararlılık`, fonun kendi sınıfında kaldığı alt pencerelerin oranıdır.
- `Stil Kayması`, ilk ve son alt pencere arasındaki dağılım mesafesidir (yüzde puan).
- Sınıflandırma, yayımlanan dağılım verisi üzerinde betimleyici bir analizdir. Yatırım tavsiyesi değildir.