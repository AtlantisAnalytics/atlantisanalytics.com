# atlantisanalytics.com

The one-page hub for Atlantis Analytics, LLC. It is a static page with no scripts and no trackers, served by GitHub Pages.

`build.py` reads `site.toml` for the fixed text and adds live parts from public sources:
- this week's bakeoff.si picks, from its API;
- the watchmaker crate's version, from crates.io;
- the latest merged pull requests in our public repositories, from GitHub's API.

The `pages` workflow rebuilds and deploys the page every 6 hours, on every push to `main`, and on demand. If any source fails, the build fails and the last good page stays live.

```sh
python3 -m unittest discover -s tests   # tests (standard library only)
python3 build.py                        # builds _site/
```

To change the wording, edit `site.toml`. To change the look, edit `assets/style.css`.

## Going live (one time)

1. Make this repository public. GitHub Pages on a private organization repository needs a paid org plan.
2. In **Settings → Pages**:
   - set **Source** to **GitHub Actions**;
   - set **Custom domain** to `atlantisanalytics.com`;
   - tick **Enforce HTTPS** once the certificate is issued.
3. At the domain's DNS host, change **only** the web records, and leave MX, SPF, DKIM and DMARC (Google Workspace email) untouched:
   - `@` A records: `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`. Replace the existing web `A` record.
   - `www` CNAME: `atlantisanalytics.github.io`.
4. Remove the custom-domain mapping from the old Google Sites page.
5. Run the `pages` workflow once (**Actions → pages → Run workflow**), then load https://atlantisanalytics.com.
