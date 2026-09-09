# besFundLens

**Türkiye emeklilik fonları için İngilizce öncelikli, iki dilli raporlamaya hazır analiz motoru.**

besFundLens, emeklilik fonlarının AUM hareketlerini **piyasa etkisi** ve **tahmini yatırımcı akışı** olarak ayrıştırır; portföy DNA'sını haritalar, fonları varlık dağılımına göre sınıflandırır, piyasa-akış rejimlerini belirler ve iki dilli Markdown raporlar üretir.

> Proje şu anda Türkiye BES / emeklilik fonu verilerine odaklanmaktadır. Fiyat tahmin modeli olmaktan ziyade yeniden kullanılabilir bir analiz motoru olarak tasarlanmıştır.

## Bu proje neden var?

Fon analizlerinin çoğu getiri ve AUM değişimi seviyesinde kalır. besFundLens daha derin bir soru sorar:

> AUM piyasalar hareket ettiği için mi değişti, yoksa yatırımcılar para eklediği/çektiği için mi?

Şu analizleri bir araya getirir:

- Fon DNA'sı / portföy dağılımı analizi
- Piyasa kapsamı ve para birimi risk haritalaması
- AUM değişimi ayrıştırması
- Tahmini net yatırımcı akışı
- Katılımcı değişimi analizi
- Model tabanlı varlık dağılımı sınıflandırması (v2)
- Piyasa-akış quadrant analizi
- İngilizce ve Türkçe anlatı raporlaması

## v0.2.0 ile gelenler

**Varlık dağılımı sınıflandırması.** Fonlar, elle yazılmış bir kural zinciriyle
değil, dağılım vektörleri üzerinde çalışan bir kümeleme modeliyle gruplanır.
Ayrıntılar: [docs/CLASSIFICATION.md](docs/CLASSIFICATION.md).

- Sınıflar, pencere-ortalamalı dağılım vektörleri üzerinde KMeans ile
  **keşfedilir**; `k` silhouette skoruna göre otomatik seçilir. Kural tabanlı
  taksonomi yalnızca her kümenin merkezinden okunabilir bir **ad üretir**.
- Sınıflandırma tek güne değil, **tüm lookback penceresine** dayanır; sınıf
  kararlılığı, stil kayması ve dağılım oynaklığı ayrıca raporlanır.
- Varlık sınıfının yanında dört ayarlanabilir kategorik eksen yer alır:
  **katılım** (faizsiz), **risk bandı**, **kur bandı** ve **look-through bandı**.
- Her sonuç bir **güven skoru** taşır; portföyün başka fonlarda tutulan ve bu
  nedenle görünmeyen payı oranında düşürülür.
- Eğitilen model JSON olarak kaydedilir ve **dönemler arasında yeniden
  kullanılabilir**; böylece sınıf adları raporlar arasında karşılaştırılabilir kalır.

v0.1'deki kural tabanlı `archetype` kolonu aynen korunmuştur.

## Kurulum

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

## SQLite cache ile hızlı başlangıç

SQLite zorunlu değildir; ancak çok yıllı analizler ve tekrar eden iş akışları için önerilir.

```bash
python scripts/fetch_history.py \
  --start 2021-06-15 \
  --end 2026-06-15 \
  --db-path data/besfundlens.sqlite
```

İngilizce rapor üretmek için:

```bash
python scripts/generate_report.py \
  --db-path data/besfundlens.sqlite \
  --lookback 1m \
  --language en \
  --output sample_reports/market_report_en.md
```

Türkçe rapor üretmek için:

```bash
python scripts/generate_report.py \
  --db-path data/besfundlens.sqlite \
  --lookback 1m \
  --language tr \
  --output sample_reports/market_report_tr.md
```

## Python API

```python
from besfundlens.workflows import run_universe_analysis_from_sqlite

result = run_universe_analysis_from_sqlite(
    db_path="data/besfundlens.sqlite",
    lookback="1m",
    language="en",
    top_n=10,
)

print(result["markdown"])
```

Seçili fon karşılaştırması:

```python
from besfundlens.workflows import compare_funds_from_sqlite
from besfundlens.core.engine import selected_funds_report_to_markdown

comparison = compare_funds_from_sqlite(
    db_path="data/besfundlens.sqlite",
    fund_codes=["AAJ", "MHD", "MEA"],
    lookback="1m",
    sort_by="market_effect_pct",
    ascending=False,
)

print(selected_funds_report_to_markdown(comparison, language="en"))
print(selected_funds_report_to_markdown(comparison, language="tr"))
```

## Varlık dağılımı sınıflandırması

Evreni sınıflandırıp modeli eğitmek için:

```bash
python scripts/classify_funds.py \
  --db-path data/besfundlens.sqlite \
  --lookback 3m \
  --fit \
  --model-path models/allocation_classifier.json \
  --output reports/classification.md \
  --language tr
```

Aynı modeli farklı bir pencerede kullanmak için (sınıf adları sabit kalır):

```bash
python scripts/classify_funds.py \
  --db-path data/besfundlens.sqlite \
  --lookback 1m \
  --predict \
  --model-path models/allocation_classifier.json \
  --output reports/classification_1m.csv
```

Python API:

```python
from besfundlens import classify_funds_from_sqlite

result = classify_funds_from_sqlite(
    db_path="data/besfundlens.sqlite",
    lookback="3m",
    save_model_to="models/allocation_classifier.json",
)

df = result["classification_df"]
print(df[[
    "fonKodu", "asset_class_tr", "class_confidence",
    "risk_band_tr", "currency_band_tr", "participation_class_tr", "style_drift",
]].head())
```

Tüm eşikler ayarlanabilir:

```python
from besfundlens import ClassificationConfig, classify_funds_from_sqlite

config = ClassificationConfig(
    feature_space="detailed",       # broad | detailed | raw
    k_range=(6, 20),                # silhouette ile bu aralıkta seçilir
    risk_band_method="quantile",    # fixed | quantile | kmeans1d
    risk_band_edges=(5.0, 25.0, 55.0),
    currency_band_threshold=50.0,
    lookthrough_penalty=True,
)

result = classify_funds_from_sqlite(db_path="data/besfundlens.sqlite", config=config)
```

Sınıflandırma piyasa anlatı raporuna otomatik olarak eklenir.
Atlamak için `run_universe_analysis()` çağrısına `classify=False` verin.

## Lookback presetleri

| Preset | Anlamı |
|---|---:|
| `1m` | 20 mevcut fon aralığı |
| `3m` | 60 mevcut fon aralığı |
| `6m` | 120 mevcut fon aralığı |
| `1y` | 240 mevcut fon aralığı |

Proje takvim günü yerine **mevcut gözlemler / aralıklar** kullanır. Bu önemlidir; çünkü fon verileri hafta sonları, resmi tatiller veya eksik yayın tarihleri nedeniyle kesintiye uğrayabilir.

## Web arayüzü

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Sayfa **canlı veriyle** açılır: lookback penceresini doğrudan TEFAS'tan çeker,
böylece sayfayı açan kişi bir cache oluşturulduğu andaki veriyi değil, en son
yayımlanan günü görür. Bir aylık pencere yaklaşık 10 saniye, bir yıllık ise
yaklaşık bir dakika sürer; sonrasında altı saat önbelleklenir. Başlıkta verinin
hangi tarihe kadar olduğu her zaman yazar.

Evreni tek bir dağılım grafiğinde gösterir: piyasa etkisine karşı tahmini
yatırımcı akışı. Piyasa düşerken girişle büyüyen fonlar kendi köşesinde durur.
Yanında kuadran ve arketip özetleri, filtrelenebilir fon tablosu, CSV dışa
aktarma ve Markdown rapor bulunur.

Bir yıldan uzun analizler için projeyi kendi bilgisayarınızda çalıştırın ve
`scripts/fetch_history.py` ile oluşturduğunuz SQLite cache'i kullanın. Kenar
çubuğu ikisi arasında geçiş yapar.

## Veri alma stratejisi

besFundLens üç iş akışını destekler:

1. Hızlı denemeler, notebook çalışmaları ve web arayüzü için **doğrudan API modu**.
2. Çok yıllı analizler ve tekrar eden raporlamalar için **SQLite cache modu**.
3. `load_turkeyfundsdata_frame` ile **turkeyfundsdata çerçeveleri**.

[turkeyfundsdata](https://github.com/hakyemezi/turkeyfundsdata) aynı TEFAS uç
noktalarını okur ve tek çağrıda beş yıla kadar veri çekebilir; ancak fiyat ile
dağılımı tek bir çerçevede birleştirip kolon adlarını büyük harfe çevirir.
Yükleyici bunu motorun beklediği iki çerçeveye geri ayırır:

```python
from tefas import get_fund_data_for_years
from besfundlens.data.loaders import load_turkeyfundsdata_frame

df_general, df_allocation = load_turkeyfundsdata_frame(
    get_fund_data_for_years(5, "EMK")
)
```

Cache güncelleyici, dönem değiştirme yaklaşımı kullanır: güncelleme başlangıç tarihinden itibaren kayıtları siler ve yeni çekilen veriyi ekler. Bu bilinçli bir tercihtir; çünkü finansal fon verilerinde geriye dönük düzeltmeler gelebilir.

## Repo yapısı

```text
streamlit_app.py     # web arayüzü
besfundlens/
  core/            # analiz motoru, varlık metadata'sı, ortak yardımcılar
  classification/  # v2 varlık dağılımı sınıflandırma katmanı
  data/            # API istemcisi ve veri yükleyiciler
  storage/         # SQLite cache yardımcıları
  reports/         # markdown rapor yardımcıları
scripts/           # CLI tarzı scriptler
examples/          # küçük demolar
docs/              # metodoloji notları
sample_reports/
tests/
```

## Sorumlu veri kullanımı

Bu proje, orijinal araştırma scriptlerinde kullanılan herkese açık fon veri endpoint'lerine dayanır. Lütfen veri çekme yardımcılarını sorumlu şekilde kullanın, aşırı API isteğinden kaçının ve tekrar eden analizlerde SQLite cache kullanımını tercih edin.

## Teşekkür / Not

Bu proje **İlyas Hakyemez** tarafından geliştirilmiş; kodlama, refactoring ve dokümantasyon aşamalarında ChatGPT'den yapay zekâ destekli geliştirme yardımı alınmıştır.

Proje fikri, finansal analiz mantığı, veri doğrulama süreci, testler, yorumlama çerçevesi ve ürün yönü proje sahibi tarafından belirlenmiş ve gözden geçirilmiştir. Yapay zekâ desteği; kod yapısının düzenlenmesi, modülerleştirme, iki dilli raporlama ve GitHub repo hazırlığı süreçlerinde yardımcı geliştirme aracı olarak kullanılmıştır.

## Uyarı

Bu proje araştırma, eğitim ve analitik prototipleme amaçlıdır. Yatırım tavsiyesi değildir.
