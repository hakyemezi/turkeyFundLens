# turkeyFundLens

**Türkiye emeklilik ve menkul kıymet yatırım fonları için İngilizce öncelikli, iki dilli raporlamaya hazır analiz motoru.**

> Eski adı **besFundLens**. Başladığı emeklilik (BES) fonlarına menkul kıymet
> yatırım fonları eklendiğinde, Ekim 2026'da yeniden adlandırıldı. Eski repo
> linkleri buraya yönlenir; `import besfundlens` de kullanımdan kaldırma
> uyarısıyla çalışmaya devam eder.

turkeyFundLens, fonların AUM hareketlerini **piyasa etkisi** ve **tahmini yatırımcı akışı** olarak ayrıştırır; portföy DNA'sını haritalar, fonları varlık dağılımına göre sınıflandırır, piyasa-akış rejimlerini belirler ve iki dilli Markdown raporlar üretir.

> Proje iki TEFAS evrenini kapsar: BES / emeklilik fonları (`EMK`) ve menkul kıymet yatırım fonları (`YAT`). Her biri kendi evreni olarak analiz edilir. Fiyat tahmin modeli olmaktan ziyade yeniden kullanılabilir bir analiz motoru olarak tasarlanmıştır.

## Bu proje neden var?

Fon analizlerinin çoğu getiri ve AUM değişimi seviyesinde kalır. turkeyFundLens daha derin bir soru sorar:

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
  --db-path data/turkeyfundlens.sqlite
```

Menkul kıymet yatırım fonları için `--fund-type YAT` ekleyin. `--db-path`
verilmezse her fon türü kendi dosyasını kullanır (`YAT` için
`data/turkeyfundlens_yat.sqlite`); script yazdığı tabloları değiştirdiği için ortak
bir dosyada bir evren diğerinin üzerine yazardı.

İngilizce rapor üretmek için:

```bash
python scripts/generate_report.py \
  --db-path data/turkeyfundlens.sqlite \
  --lookback 1m \
  --language en \
  --output sample_reports/market_report_en.md
```

Türkçe rapor üretmek için:

```bash
python scripts/generate_report.py \
  --db-path data/turkeyfundlens.sqlite \
  --lookback 1m \
  --language tr \
  --output sample_reports/market_report_tr.md
```

## Python API

```python
from turkeyfundlens.workflows import run_universe_analysis_from_sqlite

result = run_universe_analysis_from_sqlite(
    db_path="data/turkeyfundlens.sqlite",
    lookback="1m",
    language="en",
    top_n=10,
)

print(result["markdown"])
```

Seçili fon karşılaştırması:

```python
from turkeyfundlens.workflows import compare_funds_from_sqlite
from turkeyfundlens.core.engine import selected_funds_report_to_markdown

comparison = compare_funds_from_sqlite(
    db_path="data/turkeyfundlens.sqlite",
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
  --db-path data/turkeyfundlens.sqlite \
  --lookback 3m \
  --fit \
  --model-path models/allocation_classifier.json \
  --output reports/classification.md \
  --language tr
```

Aynı modeli farklı bir pencerede kullanmak için (sınıf adları sabit kalır):

```bash
python scripts/classify_funds.py \
  --db-path data/turkeyfundlens.sqlite \
  --lookback 1m \
  --predict \
  --model-path models/allocation_classifier.json \
  --output reports/classification_1m.csv
```

Python API:

```python
from turkeyfundlens import classify_funds_from_sqlite

result = classify_funds_from_sqlite(
    db_path="data/turkeyfundlens.sqlite",
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
from turkeyfundlens import ClassificationConfig, classify_funds_from_sqlite

config = ClassificationConfig(
    feature_space="detailed",       # broad | detailed | raw
    k_range=(6, 20),                # silhouette ile bu aralıkta seçilir
    risk_band_method="quantile",    # fixed | quantile | kmeans1d
    risk_band_edges=(5.0, 25.0, 55.0),
    currency_band_threshold=50.0,
    lookthrough_penalty=True,
)

result = classify_funds_from_sqlite(db_path="data/turkeyfundlens.sqlite", config=config)
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

Bunun yerine iki tarih arasını ölçmek için — örneğin bir olaydan bugüne —
`run_universe_analysis_from_sqlite` ya da `run_universe_analysis_from_dataframes`
fonksiyonlarına `start_date` / `end_date`, `scripts/generate_report.py`'a
`--start` / `--end` verin. Veri önce pencereye kesilir: başlangıç tarihindeki ya
da sonrasındaki ilk yayımlanmış gün baz, bitiş tarihindeki ya da öncesindeki son
gün bitiş olur ve yalnızca pencerenin tamamını kapsayan fonlar sayılır.

TEFAS'ın bir fonu değerleme olmadan listelediği günler — sıfır fiyat ya da
vadesi dolmuş fon için dolaşımda payı olmayan yer tutucu kayıt — varsayılan
olarak neredeyse tamamen kayıp değil, yayımlanmamış gün sayılır; fon, kapsamadığı
pencereden çıkar. Sıfırları yayımlandığı gibi almak için `include_unpublished=True`
(ya da `--include-unpublished`) verin. Bunlar menkul kıymet yatırım fonlarında
görülür, BES verisinde şimdiye kadar görülmedi; web sayfası etkilenen fonları
listeler ve analizi çalıştırmadan önce hangisinin uygulanacağını sorar.

## Web arayüzü

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Sayfa **canlı veriyle** açılır: seçilen tarih aralığını doğrudan TEFAS'tan
çeker, böylece sayfayı açan kişi bir cache oluşturulduğu andaki veriyi değil, en
son yayımlanan günü görür; sonuç altı saat önbelleklenir. Kenar çubuğunda evren
(BES ya da YAT) ile başlangıç ve bitiş tarihi seçilir; varsayılan, bugüne kadarki
son bir aydır. Canlı çekim en fazla bir yılla sınırlıdır. Başlıkta verinin hangi
tarihe kadar olduğu her zaman yazar. Aralık içinde değerleme yayımlamayan fon
varsa sayfa bunları adıyla listeler ve analizi çalıştırmadan önce hariç mi
tutulacaklarını, 0 olarak mı dahil edileceklerini sorar.

Arayüzün kendisi de çift dillidir: kenar çubuğundaki seçici tüm sayfayı değiştirir ve tablodaki ile grafikteki fon tipi, rejim ve akış rejimi etiketleri de raporla birlikte çevrilir.

Evreni tek bir dağılım grafiğinde gösterir: piyasa etkisine karşı tahmini
yatırımcı akışı. Piyasa düşerken girişle büyüyen fonlar kendi köşesinde durur.
Yanında kuadran ve arketip özetleri, filtrelenebilir fon tablosu, CSV dışa
aktarma ve Markdown rapor bulunur.

Fon detay görünümü aynı soruyu tek fona indirger: AUM değişimi neyden oluştu, portföy DNA'sı nedir, akışı gün gün nasıl seyretti ve evrenin geri kalanına göre nerede duruyor.

Stres görünümü, dönem toplamlarının gösteremediği yolu okur: girişlerle iki
katına çıkıp bir günde üçte birini kaybeden ve sonra alım-satıma kapanan bir fon
toplamda sağlıklı bir giriş gösterebilir; alım-satıma kapanmış bir fonun ise
akışı hiç olmaz. `turkeyfundlens.core.stress` şunları bulur:

- **olay tarihi**: sabitlenmez, her çalıştırmada veriden tespit edilir. Fonların
  olağandışı bir kısmının fiyatının aynı gün düştüğü gündür; ardından iki gün
  içinde sert çıkışlar geldiyse *fon krizi*, gelmediyse *piyasa şoku* sayılır
  (çıkışları kısıtlı olan BES şok gösterir). Kullanıcı tarihi elle de seçebilir;
- her fon için **olay öncesi ve sonrası akış**, ve olay çevresinde güçlü
  girişten güçlü çıkışa dönen fonlar;
- **alım-satımı duran fonlar**: öncesinde her gün işlem gören bir fonda pay ve
  kişi sayısı beş yayın günü üst üste değişmezken fiyatın değişmeye devam etmesi;
- **aynısı kurucuya göre**, çünkü stres birkaç şirkette yoğunlaşma eğilimindedir.

Canlı çekim, bu ölçümlerin karşılaştırıldığı taban için başlangıç tarihinden bir
ay öncesine de uzanır; analizin kendisi yine yalnızca seçilen aralığı kapsar.

Bir yıldan uzun analizler için projeyi kendi bilgisayarınızda çalıştırın ve
`scripts/fetch_history.py` ile oluşturduğunuz SQLite cache'i kullanın. Kenar
çubuğu ikisi arasında geçiş yapar.

## Veri alma stratejisi

turkeyFundLens üç iş akışını destekler:

1. Hızlı denemeler, notebook çalışmaları ve web arayüzü için **doğrudan API modu**.
2. Çok yıllı analizler ve tekrar eden raporlamalar için **SQLite cache modu**.
3. `load_turkeyfundsdata_frame` ile **turkeyfundsdata çerçeveleri**.

[turkeyfundsdata](https://github.com/hakyemezi/turkeyfundsdata) aynı TEFAS uç
noktalarını okur ve tek çağrıda beş yıla kadar veri çekebilir; ancak fiyat ile
dağılımı tek bir çerçevede birleştirip kolon adlarını büyük harfe çevirir.
Yükleyici bunu motorun beklediği iki çerçeveye geri ayırır:

```python
from tefas import get_fund_data_for_years
from turkeyfundlens.data.loaders import load_turkeyfundsdata_frame

df_general, df_allocation = load_turkeyfundsdata_frame(
    get_fund_data_for_years(5, "EMK")
)
```

Cache güncelleyici, dönem değiştirme yaklaşımı kullanır: güncelleme başlangıç tarihinden itibaren kayıtları siler ve yeni çekilen veriyi ekler. Bu bilinçli bir tercihtir; çünkü finansal fon verilerinde geriye dönük düzeltmeler gelebilir.

## Repo yapısı

```text
streamlit_app.py     # web arayüzü
turkeyfundlens/
  core/            # analiz motoru, varlık metadata'sı, ortak yardımcılar, metinler
  classification/  # v2 varlık dağılımı sınıflandırma katmanı
  data/            # API istemcisi ve veri yükleyiciler
  storage/         # SQLite cache yardımcıları
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
