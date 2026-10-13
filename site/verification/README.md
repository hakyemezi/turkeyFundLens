# Ownership files for search engines

Every file in this folder except this one is copied to the top of the built
site as it is. Search engines ask for such a file to prove the site is yours:

- **Google Search Console**: `google<code>.html`, downloaded from the console
  when adding the property `https://hakyemezi.github.io/turkeyFundLens/` with
  the "HTML file" method.
- **Bing Webmaster Tools**: `BingSiteAuth.xml` (or import the site from Google
  Search Console, which needs no file).
- **Yandex Webmaster**: `yandex_<code>.html`.
- **IndexNow**: the `<key>.txt` file already here. It is a public key by
  design, not a secret: `site/indexnow.py` uses it to tell Bing, Yandex and the
  other IndexNow engines which pages changed after each build.

After adding a file, the next build publishes it; then press Verify in the
console and submit `sitemap.xml` there.
