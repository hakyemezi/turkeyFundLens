"""
Interface text for the Streamlit page.

Only strings the page itself needs live here. Anything that also appears in the
generated report — archetype, market effect, AUM change and so on — is read
from the engine's REPORT_LABELS instead, so the page and the report call the
same thing by the same name.

A key missing from a language falls back to English.
"""

LANGUAGES = {
    "en": ("🇬🇧", "English"),
    "tr": ("🇹🇷", "Türkçe"),
}

# strftime("%B") follows the C locale, not the language the page is in, so
# month names are spelled out here rather than left as "09 September 2026"
# inside an otherwise Turkish sentence.
MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"],
    "tr": ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
           "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"],
}

UI = {

    "en": {
        "language": "Language",
        "title": "Did the market move it, or did investors?",

        # sidebar
        "fund_type": "Fund type",
        "fund_type_short_EMK": "BES",
        "fund_type_short_YAT": "YAT",
        "fund_type_help": "BES: pension funds. YAT: securities investment funds "
                          "(Menkul Kıymet Yatırım Fonları), the mutual funds TEFAS "
                          "lists under that tab. Each is analysed as its own universe.",
        "fund_type_EMK": "Pension funds (BES)",
        "fund_type_YAT": "Securities investment funds",
        "data": "Data",
        "source_live": "Live from TEFAS",
        "source_cache": "Local SQLite cache",
        "source_help": "Live fetches the window on demand, so the page always "
                       "reflects the latest published day. The cache is for local "
                       "use, where years of history are already on disk.",
        "cache_path": "Cache path",
        "start_date": "Start date",
        "end_date": "End date",
        "start_help": "Prices on the first published day on or after this date are "
                      "the base, so that day's own move is not included. To count "
                      "it, start on the business day before.",
        "valid_only": "Valid universe records only",
        "valid_only_help": "Drops funds that started the window with {aum} or less, "
                           "or with no participants, and any whose ratios cannot be "
                           "computed. Funds that do not cover the whole window are "
                           "left out either way.",
        "deeper_title": "Want to go deeper than a year?",
        "deeper_body": "Run this project on your own machine. Locally you can build "
                       "a SQLite cache of several years and analyse the whole span, "
                       "without waiting on a fetch each time:",
        "deeper_turkeyfundsdata": "[**turkeyfundsdata**](https://github.com/hakyemezi/turkeyfundsdata) "
                                  "pulls up to five years from the same TEFAS endpoints, and "
                                  "`load_turkeyfundsdata_frame` in `besfundlens.data.loaders` "
                                  "takes its output directly.",

        # loading and errors
        "no_cache": "No SQLite cache at `{path}`. Switch to **{live}**, or build a "
                    "cache with the command in the sidebar.",
        "spinner_live": "Fetching {start} – {end} from TEFAS and analysing",
        "spinner_cache": "Analysing {start} – {end}",
        "empty_response": "TEFAS returned nothing for that window. It answers with an "
                          "empty result rather than an error when it is being called "
                          "too quickly, so waiting a minute and rerunning usually fixes it.",

        # header
        "data_through": "Data through {date}",
        "via_live": "fetched from TEFAS",
        "via_cache": "from the local cache",
        "funds_count": "{n} funds",
        "window": "{intervals} trading intervals from {date}",
        "kpi_end_aum": "End AUM",
        "kpi_flow_share": "Flow as % of start AUM",

        # views
        "view_market": "Market map",
        "view_funds": "Funds",
        "view_report": "Report",

        # market map
        "zoom": "Zoom to the bulk of the universe",
        "zoom_help": "A few small funds post flows of several hundred percent. Left "
                     "in the frame they flatten everyone else onto the zero line.",
        "axis_market": "Market effect (%)",
        "axis_flow": "Estimated investor flow (%)",
        "chart_caption": "Each circle is a fund, sized by AUM. Right of the vertical "
                         "line the market lifted it; above the horizontal line "
                         "investors put money in. The interesting funds are the ones "
                         "off the diagonal — growing on flows while the market fell, "
                         "or losing investors through a rally. Scroll to zoom, drag to pan.",
        "chart_outliers": "{n} funds sit outside this frame and are drawn at its edge; "
                          "untick the box to see them.",
        "by_quadrant": "By quadrant",
        "by_archetype": "By archetype",

        # funds
        "filter_search": "Search code or name",
        "showing": "{shown} of {total} funds",
        "col_code": "Code",
        "col_aum": "AUM",
        "col_participants": "Participants",
        "col_quadrant": "Market-flow quadrant",
        "col_regime": "Flow regime",
        "col_return": "Return %",
        "col_aum_change": "AUM change %",
        "col_market_effect": "Market effect %",
        "col_flow": "Flow %",
        "col_participant_change": "Participant change %",
        "keep_one": "Select at least one column.",
        "download_csv": "Download this view as CSV",
        "missing_days": "{n} business day(s) in this window have no published data: {days}. "
                        "The analysis still runs, but a gap can distort a short window.",
        "too_short": "Not enough data to analyse {start} – {end}: it takes at least "
                     "two published days, and only funds covering the whole range "
                     "count. With a cache, pick dates inside what it holds, or "
                     "extend it.",
        "partial_window": "You asked for {start} – {end}; the data covers {first} – "
                          "{last}, so that is what is analysed.",
        "unpublished": "{n} fund(s) have no valuation on some day in this window — a "
                       "zero price, or a placeholder with no units in circulation — "
                       "which TEFAS shows for a fund that is suspended, liquidating or "
                       "has matured. Largest first: {codes}.",
        "unpublished_choice": "How should these funds be treated?",
        "unpublished_exclude": "Exclude them",
        "unpublished_include": "Include them as zero",
        "unpublished_help": "Excluded: those days count as unpublished, so the funds "
                            "drop out of the window and of the totals. Included as zero: "
                            "the figures are taken as TEFAS published them, so a zero "
                            "price reads as a -100% return split between market effect "
                            "and outflow, and a large fund moves the universe totals "
                            "with it.",
        "unpublished_ask": "Pick one to run the analysis. The choice is kept for "
                           "this session and can be changed here.",
        "dates_order": "The start date has to be before the end date.",
        "live_too_long": "Live mode fetches at most a year at a time. Narrow the "
                         "dates, or use a local cache for a longer span.",
        "view_detail": "Fund detail",
        "pick_fund": "Pick a fund",
        "detail_what_moved": "What moved its AUM",
        "detail_start_aum": "Start AUM",
        "detail_decomp_note": "AUM change is market effect plus estimated investor "
                              "flow. A fund can grow while investors leave, or shrink "
                              "while they arrive — that gap is the point of the split.",
        "detail_dna": "Portfolio DNA",
        "detail_top_asset": "Largest asset group",
        "detail_scope": "Market scope",
        "detail_currency": "Currency exposure",
        "detail_lookthrough": "Held in other funds",
        "detail_lookthrough_help": "The share of the portfolio held through other "
                                   "funds, whose own holdings are not visible here.",
        "detail_position": "Where it sits in the universe",
        "detail_highlighted": "This fund is ringed; the rest of the universe is faded.",
        "detail_participants": "Participants",
        "detail_participant_change": "Participant change",
        "bar_market_effect": "Market effect",
        "bar_flow": "Investor flow",
        "download_report": "Download the report as Markdown",

        # stress signals
        "view_stress": "Stress signals",
        "event_manual": "Set the event date by hand",
        "event_help": "The event date splits each fund's flow into before and after. Left "
                      "alone it is detected from the data on every run, so it follows the "
                      "window rather than any one crisis: the day an unusual share of funds "
                      "fell at least {drop}% and, for a run, an unusual share then lost at "
                      "least {out}% of their money within two days.",
        "event_pick": "Event date",
        "event_outside": "The event date has to fall after the start date and no later than "
                         "the end date. Using the detected one.",
        "event_detected_run": "Event: {date}, detected — a run: prices fell across the "
                              "universe and investors left after",
        "event_detected_shock": "Event: {date}, detected — a market shock: prices fell across "
                                "the universe, but no wave of outflows followed",
        "event_none": "No stress event stands out in this window. Set a date by hand to "
                      "split the flows anyway.",
        "stress_title_manual": "Event: {date}, set by hand",
        "event_at_start": "The event falls on the window's first day, so there is no before "
                          "to compare with. Start the window earlier to see it.",
        "stress_chart_caption": "The share of funds having a bad day. The event is the day "
                                "both lines break away from the weeks before; the price line "
                                "alone makes a market shock. The dashed line marks the event.",
        "series_price_drop": "Price down {pct}% or more",
        "series_outflow": "Outflow of {pct}% or more",
        "axis_fund_share": "Share of funds (%)",
        "kpi_frozen": "Funds that stopped dealing",
        "kpi_frozen_aum": "Their AUM at the start",
        "kpi_turned": "Turned inflow to outflow",
        "kpi_unpublished": "Without a valuation",
        "founders_title": "By founder",
        "founders_none": "No founder shows any of these signals in this window.",
        "founders_caption": "Stressed AUM is what the founder held at the start of the "
                            "window in funds that stopped dealing or went without a "
                            "valuation. Ordered by that amount, since a share would put a "
                            "one-fund founder on top for one bad fund. Only founders with a "
                            "signal are listed.",
        "col_founder": "Founder",
        "col_funds": "Funds",
        "col_stressed_aum": "Stressed AUM",
        "col_stressed_share": "Stressed share",
        "col_frozen": "Stopped",
        "col_unpublished": "No valuation",
        "col_turned": "Turned",
        "col_flow_before": "Flow before event %",
        "col_flow_after": "Flow after event %",
        "col_frozen_since": "Stopped dealing since",
        "col_frozen_days": "Days stopped",
        "col_ongoing": "Still stopped",
        "frozen_title": "Funds that stopped dealing",
        "frozen_none": "No fund stopped dealing in this window.",
        "frozen_caption": "Units in circulation and the number of holders did not move for "
                          "at least {days} published days running while the price kept "
                          "moving, in a fund that dealt on most days before. That is what a "
                          "fund closed to subscriptions and redemptions looks like in the "
                          "data; why it closed has to be checked with KAP.",
        "turned_title": "Funds that turned from inflow to outflow",
        "turned_no_event": "There is no before to compare with: no event in this window, or "
                           "it falls on the first day.",
        "turned_none": "No fund turned from inflow to outflow across the event.",
        "turned_caption": "At least {pct}% in before the event and at least {pct}% out after "
                          "it, each as a share of what the fund held at the time. The event "
                          "day counts as after.",
        "detail_frozen_ongoing": "Units in circulation and the number of holders have not "
                                 "moved since {since} ({n} published days), while the price "
                                 "has. The fund looks closed to dealing; its flow reads as "
                                 "zero because nothing can move, not because nothing is wrong.",
        "detail_frozen_past": "Units in circulation and the number of holders did not move "
                              "from {since} to {until} ({n} published days), while the price "
                              "did. The fund looks to have been closed to dealing in that time.",
        "detail_daily": "Day by day",
        "detail_daily_caption": "Each bar is one day's estimated investor flow, as a share of "
                                "the AUM the day before. The window's total can hide a run: a "
                                "fund that doubled on inflows and then lost a third in a day "
                                "still sums to an inflow. The dashed line marks the event.",
        "axis_daily_flow": "Daily flow (%)",
    },

    "tr": {
        "language": "Dil",
        "title": "Piyasa mı taşıdı, yatırımcılar mı?",

        # kenar çubuğu
        "fund_type": "Fon türü",
        "fund_type_short_EMK": "BES",
        "fund_type_short_YAT": "YAT",
        "fund_type_help": "BES: emeklilik fonları. YAT: TEFAS'ta bu sekmede listelenen "
                          "menkul kıymet yatırım fonları. Her biri kendi evreni olarak "
                          "analiz edilir.",
        "fund_type_EMK": "Emeklilik fonları (BES)",
        "fund_type_YAT": "Menkul kıymet yatırım fonları",
        "data": "Veri",
        "source_live": "TEFAS'tan canlı",
        "source_cache": "Yerel SQLite cache",
        "source_help": "Canlı seçenek pencereyi anlık olarak çeker, böylece sayfa her "
                       "zaman en son yayımlanan günü gösterir. Cache, yılların geçmişi "
                       "zaten diskte olduğu için yerel kullanıma yöneliktir.",
        "cache_path": "Cache yolu",
        "start_date": "Başlangıç tarihi",
        "end_date": "Bitiş tarihi",
        "start_help": "Bu tarihteki ya da sonrasındaki ilk yayımlanmış günün fiyatları "
                      "baz alınır; o günün kendi hareketi dahil edilmez. Dahil etmek "
                      "için bir önceki iş gününden başlatın.",
        "valid_only": "Yalnızca geçerli evren kayıtları",
        "valid_only_help": "Aralığa {aum} veya altında ya da katılımcısız başlayan "
                           "fonları ve oranları hesaplanamayanları eler. Aralığın "
                           "tamamını kapsamayan fonlar her durumda dışarıda kalır.",
        "deeper_title": "Bir yıldan uzun analiz mi istiyorsunuz?",
        "deeper_body": "Projeyi kendi bilgisayarınızda çalıştırın. Yerelde birkaç yıllık "
                       "bir SQLite cache oluşturup tüm dönemi analiz edebilir, her "
                       "seferinde veri çekilmesini beklemezsiniz:",
        "deeper_turkeyfundsdata": "[**turkeyfundsdata**](https://github.com/hakyemezi/turkeyfundsdata) "
                                  "aynı TEFAS uç noktalarından beş yıla kadar veri çeker; "
                                  "`besfundlens.data.loaders` içindeki `load_turkeyfundsdata_frame` "
                                  "onun çıktısını doğrudan kabul eder.",

        # yükleme ve hatalar
        "no_cache": "`{path}` yolunda SQLite cache yok. **{live}** seçeneğine geçin ya da "
                    "kenar çubuğundaki komutla bir cache oluşturun.",
        "spinner_live": "TEFAS'tan {start} – {end} verisi çekiliyor ve analiz ediliyor",
        "spinner_cache": "{start} – {end} analizi çalışıyor",
        "empty_response": "TEFAS bu dönem için boş yanıt verdi. Çok hızlı çağrıldığında hata "
                          "yerine boş sonuç döndürür; bir dakika bekleyip tekrar çalıştırmak "
                          "genelde çözer.",

        # başlık
        "data_through": "Veri {date} tarihine kadar",
        "via_live": "TEFAS'tan çekildi",
        "via_cache": "yerel cache'ten",
        "funds_count": "{n} fon",
        "window": "{date} tarihinden itibaren {intervals} işlem aralığı",
        "kpi_end_aum": "Bitiş AUM",
        "kpi_flow_share": "Başlangıç AUM'a göre akış",

        # görünümler
        "view_market": "Piyasa haritası",
        "view_funds": "Fonlar",
        "view_report": "Rapor",

        # piyasa haritası
        "zoom": "Evrenin ana kütlesine yakınlaş",
        "zoom_help": "Birkaç küçük fon yüzlerce puanlık akış bildiriyor. Kadrajda "
                     "kalırlarsa diğer herkesi sıfır çizgisine yapıştırırlar.",
        "axis_market": "Piyasa etkisi (%)",
        "axis_flow": "Tahmini yatırımcı akışı (%)",
        "chart_caption": "Her daire bir fon, boyutu AUM'a göre. Dikey çizginin sağında "
                         "fonu piyasa yukarı taşımış; yatay çizginin üstünde yatırımcı "
                         "para koymuş. İlginç olanlar köşegenin dışındakiler — piyasa "
                         "düşerken girişle büyüyenler ya da yükseliş boyunca yatırımcı "
                         "kaybedenler. Yakınlaşmak için kaydırın, gezinmek için sürükleyin.",
        "chart_outliers": "{n} fon bu kadrajın dışında kalıyor ve kenarına çizildi; "
                          "görmek için kutunun işaretini kaldırın.",
        "by_quadrant": "Rejime göre",
        "by_archetype": "Fon tipine göre",

        # fonlar
        "filter_search": "Kod veya ad ara",
        "showing": "{total} fondan {shown} tanesi",
        "col_code": "Kod",
        "col_aum": "AUM",
        "col_participants": "Katılımcı",
        "col_quadrant": "Piyasa-akış rejimi",
        "col_regime": "Akış rejimi",
        "col_return": "Getiri %",
        "col_aum_change": "AUM değişimi %",
        "col_market_effect": "Piyasa etkisi %",
        "col_flow": "Akış %",
        "col_participant_change": "Katılımcı değişimi %",
        "keep_one": "En az bir sütun seçin.",
        "download_csv": "Bu görünümü CSV olarak indir",
        "missing_days": "Bu dönemde {n} iş gününe ait veri yayımlanmamış: {days}. "
                        "Analiz yine de çalışır, ancak boşluk kısa aralıkları bozabilir.",
        "too_short": "{start} – {end} aralığını analiz etmek için yeterli veri yok: en "
                     "az iki yayımlanmış gün gerekir ve yalnızca aralığın tamamını "
                     "kapsayan fonlar sayılır. Cache kullanıyorsanız cache'in kapsadığı "
                     "tarihleri seçin ya da cache'i genişletin.",
        "partial_window": "{start} – {end} aralığı istendi; veri {first} – {last} "
                          "aralığını kapsıyor, analiz bu aralık üzerinden yapıldı.",
        "unpublished": "{n} fon bu aralıktaki bazı günlerde değerleme yayımlamadı (sıfır "
                       "fiyat ya da dolaşımda payı olmayan yer tutucu kayıt); TEFAS bunu "
                       "işlemleri durdurulan, tasfiye edilen ya da vadesi dolan fonlar "
                       "için gösterir. Büyükten küçüğe: {codes}.",
        "unpublished_choice": "Bu fonlar nasıl ele alınsın?",
        "unpublished_exclude": "Hariç tut",
        "unpublished_include": "0 olarak dahil et",
        "unpublished_help": "Hariç tut: o günler yayımlanmamış sayılır, fonlar aralıktan "
                            "ve toplamlardan çıkar. 0 olarak dahil et: rakamlar TEFAS'ın "
                            "yayımladığı gibi alınır; sıfır fiyat −%100 getiri olarak "
                            "okunup piyasa etkisi ile çıkış arasında bölünür ve büyük bir "
                            "fon evren toplamlarını da birlikte etkiler.",
        "unpublished_ask": "Analizi çalıştırmak için birini seçin. Seçim bu oturum "
                           "boyunca hatırlanır ve buradan değiştirilebilir.",
        "dates_order": "Başlangıç tarihi bitiş tarihinden önce olmalı.",
        "live_too_long": "Canlı modda tek seferde en fazla bir yıl çekilir. Aralığı "
                         "daraltın ya da daha uzun dönem için yerel cache kullanın.",
        "view_detail": "Fon detayı",
        "pick_fund": "Bir fon seçin",
        "detail_what_moved": "AUM'unu ne hareket ettirdi",
        "detail_start_aum": "Başlangıç AUM",
        "detail_decomp_note": "AUM değişimi, piyasa etkisi ile tahmini yatırımcı "
                              "akışının toplamıdır. Bir fon yatırımcı çıkarken büyüyebilir "
                              "ya da yatırımcı girerken küçülebilir; bu ayrımın amacı tam "
                              "olarak o farkı görmektir.",
        "detail_dna": "Portföy DNA'sı",
        "detail_top_asset": "En büyük varlık grubu",
        "detail_scope": "Piyasa kapsamı",
        "detail_currency": "Döviz maruziyeti",
        "detail_lookthrough": "Diğer fonlarda tutulan",
        "detail_lookthrough_help": "Portföyün başka fonlar aracılığıyla tutulan payı; "
                                   "o fonların kendi varlıkları burada görünmez.",
        "detail_position": "Evrende nerede duruyor",
        "detail_highlighted": "Bu fon halkalı gösterildi, evrenin geri kalanı soluklaştırıldı.",
        "detail_participants": "Katılımcı",
        "detail_participant_change": "Katılımcı değişimi",
        "bar_market_effect": "Piyasa etkisi",
        "bar_flow": "Yatırımcı akışı",
        "download_report": "Raporu Markdown olarak indir",

        # stres sinyalleri
        "view_stress": "Stres sinyalleri",
        "event_manual": "Olay tarihini elle seç",
        "event_help": "Olay tarihi her fonun akışını öncesi ve sonrası diye ikiye böler. Elle "
                      "seçilmezse her çalıştırmada veriden tespit edilir; yani belli bir "
                      "krize değil, seçilen aralığa göre belirlenir: fonların olağandışı bir "
                      "kısmının aynı gün en az %{drop} değer kaybettiği ve, fon krizi için, "
                      "ardından iki gün içinde olağandışı bir kısmının en az %{out} çıkış "
                      "yaşadığı gün.",
        "event_pick": "Olay tarihi",
        "event_outside": "Olay tarihi başlangıç tarihinden sonra olmalı ve bitiş tarihini "
                         "geçmemeli. Tespit edilen tarih kullanılıyor.",
        "event_detected_run": "Olay: {date}, otomatik tespit — fon krizi: fiyatlar evren "
                              "genelinde düştü, ardından yatırımcılar çıktı",
        "event_detected_shock": "Olay: {date}, otomatik tespit — piyasa şoku: fiyatlar evren "
                                "genelinde düştü, ama çıkış dalgası gelmedi",
        "event_none": "Bu aralıkta öne çıkan bir stres olayı yok. Akışları yine de bölmek "
                      "için tarihi elle seçin.",
        "stress_title_manual": "Olay: {date}, elle seçildi",
        "event_at_start": "Olay aralığın ilk gününe denk geliyor, bu yüzden karşılaştırılacak "
                          "bir öncesi yok. Görmek için aralığı daha erken başlatın.",
        "stress_chart_caption": "Kötü gün yaşayan fonların oranı. Olay, iki çizginin de önceki "
                                "haftalardan koptuğu gündür; yalnızca fiyat çizgisinin kopması "
                                "piyasa şoku sayılır. Kesikli çizgi olay tarihini gösterir.",
        "series_price_drop": "Fiyatı en az %{pct} düşen",
        "series_outflow": "En az %{pct} çıkış yaşayan",
        "axis_fund_share": "Fon oranı (%)",
        "kpi_frozen": "Alım-satımı duran fon",
        "kpi_frozen_aum": "Başlangıçtaki AUM'ları",
        "kpi_turned": "Girişten çıkışa dönen",
        "kpi_unpublished": "Değerlemesiz",
        "founders_title": "Kurucuya göre",
        "founders_none": "Bu aralıkta hiçbir kurucuda bu sinyaller görülmüyor.",
        "founders_caption": "Stresli AUM, kurucunun aralık başında alım-satımı duran ya da "
                            "değerleme yayımlamayan fonlarda tuttuğu tutardır. Tutara göre "
                            "sıralanır; orana göre sıralamak tek fonlu bir kurucuyu tek kötü "
                            "fon yüzünden en üste çıkarırdı. Yalnızca sinyali olan kurucular "
                            "listelenir.",
        "col_founder": "Kurucu",
        "col_funds": "Fon",
        "col_stressed_aum": "Stresli AUM",
        "col_stressed_share": "Stresli pay",
        "col_frozen": "Duran",
        "col_unpublished": "Değerlemesiz",
        "col_turned": "Dönen",
        "col_flow_before": "Olay öncesi akış %",
        "col_flow_after": "Olay sonrası akış %",
        "col_frozen_since": "Alım-satım duruşu",
        "col_frozen_days": "Duruş (gün)",
        "col_ongoing": "Sürüyor",
        "frozen_title": "Alım-satımı duran fonlar",
        "frozen_none": "Bu aralıkta alım-satımı duran fon yok.",
        "frozen_caption": "Dolaşımdaki pay ve kişi sayısı en az {days} yayın günü üst üste "
                          "hiç değişmemiş, fiyat ise değişmeye devam etmiş; fon da öncesinde "
                          "günlerin çoğunda işlem görüyormuş. Alım-satıma kapanmış bir fon "
                          "veride böyle görünür; neden kapandığı KAP'tan doğrulanmalı.",
        "turned_title": "Girişten çıkışa dönen fonlar",
        "turned_no_event": "Karşılaştırılacak bir öncesi yok: bu aralıkta olay tespit "
                           "edilmedi ya da olay ilk güne denk geliyor.",
        "turned_none": "Olay çevresinde girişten çıkışa dönen fon yok.",
        "turned_caption": "Olaydan önce en az %{pct} giriş, sonra en az %{pct} çıkış; ikisi "
                          "de fonun o andaki büyüklüğüne oranla. Olay günü sonrasına sayılır.",
        "detail_frozen_ongoing": "Dolaşımdaki pay ve kişi sayısı {since} tarihinden beri ({n} "
                                 "yayın günü) değişmiyor, fiyat ise değişiyor. Fon alım-satıma "
                                 "kapanmış görünüyor; akışın sıfır çıkması bir sorun olmadığı "
                                 "için değil, hiçbir şey hareket edemediği için.",
        "detail_frozen_past": "Dolaşımdaki pay ve kişi sayısı {since} – {until} arasında ({n} "
                              "yayın günü) değişmedi, fiyat ise değişti. Fon o süre boyunca "
                              "alım-satıma kapanmış görünüyor.",
        "detail_daily": "Gün gün",
        "detail_daily_caption": "Her çubuk bir günün tahmini yatırımcı akışıdır; bir önceki "
                                "günün AUM'una oranla. Dönem toplamı bir kaçışı gizleyebilir: "
                                "girişlerle iki katına çıkıp bir günde üçte birini kaybeden fon "
                                "toplamda yine giriş gösterir. Kesikli çizgi olay tarihini "
                                "gösterir.",
        "axis_daily_flow": "Günlük akış (%)",
    },
}

# A pension plan has participants; a securities investment fund has investors.
# TEFAS reports both as the same head count, so only the word changes. These
# replace the keys above while the YAT universe is selected. The engine's own
# labels are reworded by besfundlens.core.localization.investor_wording.
UI_BY_FUND_TYPE = {
    "YAT": {
        "en": {
            "col_participants": "Investors",
            "col_participant_change": "Investor change %",
            "detail_participants": "Investors",
            "detail_participant_change": "Investor change",
            "valid_only_help": "Drops funds that started the window with {aum} or less, "
                               "or with no investors, and any whose ratios cannot be "
                               "computed. Funds that do not cover the whole window are "
                               "left out either way.",
        },
        "tr": {
            "col_participants": "Yatırımcı",
            "col_participant_change": "Yatırımcı değişimi %",
            "detail_participants": "Yatırımcı",
            "detail_participant_change": "Yatırımcı değişimi",
            "valid_only_help": "Aralığa {aum} veya altında ya da yatırımcısız başlayan "
                               "fonları ve oranları hesaplanamayanları eler. Aralığın "
                               "tamamını kapsamayan fonlar her durumda dışarıda kalır.",
        },
    },
}
