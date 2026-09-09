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
        "data": "Data",
        "source_live": "Live from TEFAS",
        "source_cache": "Local SQLite cache",
        "source_help": "Live fetches the window on demand, so the page always "
                       "reflects the latest published day. The cache is for local "
                       "use, where years of history are already on disk.",
        "cache_path": "Cache path",
        "lookback": "Lookback",
        "fetch_estimate": "Fetching {months} takes roughly {seconds} seconds on a "
                          "cold start, then it is cached.",
        "months_one": "1 month",
        "months_many": "{n} months",
        "valid_only": "Valid universe records only",
        "valid_only_help": "Drops funds whose history does not cover the whole "
                           "lookback window.",
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
        "spinner_live": "Fetching {months} from TEFAS and analysing — about {seconds} seconds",
        "spinner_cache": "Running the {lookback} analysis",
        "empty_response": "TEFAS returned nothing for that window. It answers with an "
                          "empty result rather than an error when it is being called "
                          "too quickly, so waiting a minute and rerunning usually fixes it.",

        # header
        "data_through": "Data through {date}",
        "via_live": "fetched from TEFAS",
        "via_cache": "from the local cache",
        "funds_count": "{n} funds",
        "window": "{lookback} lookback, {intervals} trading intervals, from {date}",
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
    },

    "tr": {
        "language": "Dil",
        "title": "Piyasa mı taşıdı, yatırımcılar mı?",

        # kenar çubuğu
        "data": "Veri",
        "source_live": "TEFAS'tan canlı",
        "source_cache": "Yerel SQLite cache",
        "source_help": "Canlı seçenek pencereyi anlık olarak çeker, böylece sayfa her "
                       "zaman en son yayımlanan günü gösterir. Cache, yılların geçmişi "
                       "zaten diskte olduğu için yerel kullanıma yöneliktir.",
        "cache_path": "Cache yolu",
        "lookback": "Dönem",
        "fetch_estimate": "{months} çekmek ilk açılışta yaklaşık {seconds} saniye sürer, "
                          "sonrasında önbelleğe alınır.",
        "months_one": "1 ay",
        "months_many": "{n} ay",
        "valid_only": "Yalnızca geçerli evren kayıtları",
        "valid_only_help": "Geçmişi dönemin tamamını kapsamayan fonları eler.",
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
        "spinner_live": "TEFAS'tan {months} veri çekiliyor ve analiz ediliyor — yaklaşık {seconds} saniye",
        "spinner_cache": "{lookback} analizi çalışıyor",
        "empty_response": "TEFAS bu dönem için boş yanıt verdi. Çok hızlı çağrıldığında hata "
                          "yerine boş sonuç döndürür; bir dakika bekleyip tekrar çalıştırmak "
                          "genelde çözer.",

        # başlık
        "data_through": "Veri {date} tarihine kadar",
        "via_live": "TEFAS'tan çekildi",
        "via_cache": "yerel cache'ten",
        "funds_count": "{n} fon",
        "window": "{lookback} dönem, {intervals} işlem aralığı, {date} tarihinden itibaren",
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
    },
}
