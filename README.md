# Basel Parking

A multilingual web application for checking parking availability in Basel and exploring historical estimates for a later arrival.

[Live application](https://basel-parkings.netlify.app/)

## What it does

The application requests the latest public parking reports from Basel-Stadt. Users select a destination, arrival date, time and vehicle height. It displays reported free spaces prominently, with occupancy when the source provides a usable capacity. The interface is available in English, German and French.

Future values are historical medians for the same weekday and hour over a rolling 182-day window. They require at least 12 comparable dates. They are estimates, with no reservation or guarantee of a space.

## Architecture

The browser runs plain JavaScript, HTML and CSS. Python packages the application for deployment and creates the icons and sharing image. Atkinson Hyperlegible Next is hosted locally. The application has no user accounts, private database, API keys or application server.

Current reports are requested approximately every minute while the page is visible. Calendar choices follow the current date in Europe/Zurich, including midnight and daylight saving changes. Historical requests use a rolling date range. Optional local storage retains the selected language and a public-history cache; users can refuse or withdraw permission.

Opening hours and height limits are manually maintained. Fresh official opening status and regular entry hours are treated as separate evidence, with conflicts shown to the user.

## Project structure

| Path | Purpose |
| --- | --- |
| `basel_parking/app.js` | API requests, validation, calendar, historical estimates and rendering |
| `basel_parking/i18n.js` | English, German and French interface text |
| `basel_parking/config.json` | Public source settings, destinations, heights and regular hours |
| `basel_parking/styles.css` | Responsive layout and local fonts |
| `basel_parking/build_site.py` | Generates the deployable application and standalone HTML |
| `basel_parking/tests/` | Core and browser tests |
| `basel-parking-netlify/` | Complete generated files for static deployment |
| `docs/verification-fr.md` | Verification results and outstanding items |

`build.py`, `results.json`, `ANALYSE_HISTORIQUE.md` belong to an earlier analysis. Their results do not validate the current application's predictive accuracy. The production application fetches fresh data and does not read a bundled CSV.

## Run locally

Use Python 3.10 or later to serve the generated site:

```sh
python3 -m http.server 8000 --directory basel-parking-netlify
```

Open http://localhost:8000. Internet access is required for public parking data. The Python development server does not apply Netlify's `_headers` file.

## Rebuild after editing

```sh
python3 -m pip install -r requirements.txt
python3 basel_parking/build_site.py
```

The build updates `basel-parking-netlify/` and creates standalone HTML copies. Deploy the complete output directory to include auxiliary pages, assets and security headers. The included Netlify configuration selects that directory; no build command is needed when the generated files are committed.

## Run tests

Install Node.js and Playwright:

```sh
npm install --no-save playwright
npx playwright install chromium
node --test basel_parking/tests/core.test.js
node basel_parking/tests/browser.v4.test.cjs
```

The browser test starts its own local server and applies the prepared security headers. Set `BASEL_SKIP_LIVE=1` to skip real API calls. `BASEL_CHROMIUM_PATH` can specify an existing Chromium executable.

Thirteen core tests passed during the latest verification. Chromium checks covered the three languages at 375 x 667, the 2032 midnight rollover, refreshing data, stale history, connectivity failures, storage choices, CSP and escaping of source-provided names. These tests verify behavior in defined cases. Safari and a physical iPhone have not been tested.

## Known limitations

Current availability can change before a driver arrives. Reports older than fifteen minutes are suppressed, but a shorter warning threshold would improve freshness communication. Distances used for ranking are straight-line distances, not road travel times.

The predictive accuracy of the current version has not been measured on an independent holdout set. Historical ranges describe past observations rather than confidence intervals. Estimates are suppressed for known public holidays and Basel carnival dates. Other exceptional events remain outside the model.

Badischer Bahnhof has conflicting visitor-capacity information across official sources. Its reported current free count is retained with a warning; its occupancy percentage and future estimate are suspended pending clarification.

New exceptional opening hours are not automatically discovered. Publisher contact information and complete legal details still need the owner's real public details. No audience analytics is configured. These limitations are documented rather than filled with invented information.

## Next steps

Evaluate forecast errors with chronological holdouts and report results per parking location. Test the interface with people unfamiliar with the project. Add freshness warnings and investigate the visitor-capacity discrepancy. Verify the complete deployment and test Safari on an actual device.

## Data and attribution

Current reports: https://data.bs.ch/explore/dataset/100088/

Historical reports: https://data.bs.ch/explore/dataset/100014/

Parking details: https://www.parkleitsystem-basel.ch/

The application attributes public data to Basel-Stadt under CC BY 4.0. Preserve attribution when reusing historical data. Atkinson Hyperlegible Next is distributed with its license in `basel_parking/assets/FONT-LICENSE.txt` and the deployment assets.

## Development

The implementation and documentation were prepared with AI assistance. The code, tests and known limitations are available for review. This repository makes no claim of independently validated forecasting performance.

## Download historical data

The 22 MB CSV snapshot is excluded from Git. Download a fresh public export without rebuilding the earlier analysis:

```sh
python3 -c "from basel_parking.build import refresh; refresh()"
```

This writes `basel_parking/data/all_historical.csv`. No download is required to run the live application.
