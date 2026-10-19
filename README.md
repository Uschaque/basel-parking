# Basel Parking

A multilingual web application for checking parking availability in Basel and exploring historical estimates for a later arrival.

[Live application](https://basel-parkings.netlify.app/)

## What it does

The application requests the latest public parking reports from Basel-Stadt. Users select a destination, arrival date, time and vehicle height. It displays reported free spaces prominently, with occupancy when the source provides a usable capacity. The interface is available in English, German and French.

Future values are historical medians for the same weekday and hour over a rolling 182-day window. They require at least 12 comparable dates. They are estimates, with no reservation or guarantee of a space. A separate [chronological data study](analysis/report.html) evaluates this rule against simple alternatives on unseen dates.

## Architecture

The browser runs plain JavaScript, HTML and CSS. Python packages the application for deployment and creates the icons and sharing image. Atkinson Hyperlegible Next is hosted locally. The application has no user accounts, private database, API keys or application server.

Current reports are requested approximately every minute while the page is visible. Calendar choices follow the current date in Europe/Zurich, including midnight and daylight saving changes. Historical requests use a rolling date range. Optional local storage retains the selected language and a public-history cache; users can refuse or withdraw permission.

Opening hours and height limits are manually maintained. Fresh official opening status and regular entry hours are treated as separate evidence, with conflicts shown to the user.

## How the data reaches the screen

The browser requests JSON directly from the Basel-Stadt public API at `https://data.bs.ch/api/explore/v2.1/catalog/datasets`. Netlify serves the static files. Python runs during the build, not when a visitor requests parking information.

| Information | Source and handling |
| --- | --- |
| Current free spaces and opening status | Dataset `100088`, requested through `/exports/json`; the newest `published` record for each `id2` is retained. |
| Historical observations | Dataset `100014`, filtered by the selected weekday, hour and a rolling 182-day window. |
| Capacity, address and coordinates | Public parking records; missing capacity suppresses the occupancy percentage without discarding a valid free-space count. |
| Regular entry hours and vehicle clearance | Manually maintained in `basel_parking/config.json`; the current verification date is 25 September 2026. |
| Available arrival dates | Calculated in the browser from the current date in `Europe/Zurich`. |

The application discovers parking IDs from the current feed. A newly added parking location can have unknown height or opening hours until the configuration is reviewed. Selecting a vehicle height excludes locations whose clearance is unknown.

### Refresh timing and freshness

| Setting | Current behavior |
| --- | --- |
| `live_refresh_ms = 60000` | A new current-data request is due after 60 seconds while the page is visible; a 15-second timer checks whether it is due. Browser scheduling and network latency can delay it. |
| `max_live_age_ms = 900000` | A reading older than 15 minutes is suppressed according to its source publication time. A successful download alone does not establish freshness. |
| `date_window_days = 14` | Today and the next 13 days are offered. The calendar rolls forward at local midnight, and elapsed hours are removed from today's choices. |
| `history_refresh_ms = 21600000` | Historical query results can be reused for less than six hours. A new local date clears the in-memory history cache. |

The refresh button requests both current data and the selected historical data again. Returning to a visible tab checks for due refreshes; restoring connectivity also triggers new requests. Routine current-data polling pauses while the tab is hidden. Browsers can suspend background pages entirely.

A sudden occupancy increase appears after the provider publishes it and a subsequent request retrieves it. There is no push connection to individual parking spaces and no guaranteed end-to-end update delay. Compare the source report time on each card with the last successful download time shown by the interface.

If the current request fails, the application clears the current readings and shows an error. Previously discovered parking names may remain visible without a free-space count. Requests time out after 20 seconds for current data and 30 seconds for historical data.

### How a future estimate is calculated

For a selected arrival weekday and hour, `historyURL()` requests matching observations. `profilesFromRows()` then processes each parking location:

1. Validate timestamps and counts, and retain one observation per local date for the selected hour. The repeated hour at the autumn clock change receives one vote.
2. Suppress a profile if more than 1% of the examined daily observations have invalid counts.
3. Keep observations with the same capacity as the current catalog, or the latest historical capacity when the catalog has no usable capacity.
4. Require at least 12 comparable dates and a newest comparable observation no more than 14 days old.
5. Display the rounded median free-space count. The expandable range uses observed values around the 25th and 75th percentiles.

The displayed occupancy is `round(100 × (1 - free / total))` when capacity is usable. The historical range describes variation in past observations. On the fixed 56-day holdout ending 19 October 2026, the historical median reached 16.72 free spaces MAE across 12,051 observations from nine quality-approved garages, compared with 21.44 for the previous-week baseline. The paired day-level improvement was 4.72 spaces, with a 95% bootstrap interval from 3.07 to 6.26. These figures measure agreement with later public reports, not physical ground truth or a guarantee for an individual trip.

Future estimates are hidden when regular hours indicate closure, hours are unknown, the selected date is a recognized public holiday or Basel carnival date, or capacity is flagged for review. Events outside those programmed rules are not accounted for.

### Opening hours and exceptional dates

In **Now** mode, a fresh provider status determines whether a location is reported open or closed. An open report outside the configured regular hours is displayed with a conflict warning. Invalid or old data produces an unavailable state rather than an assumed opening status.

For a future arrival, `openingAt()` evaluates the configured schedule. Holiday and carnival dates are calculated for the selected year. Anfos includes specific exceptions that require confirmation, including carnival Monday and the two Sundays preceding Christmas. These rules do not fetch newly announced exceptional opening hours from operators.

Dates continue advancing automatically in later years. Continued correctness also depends on the availability and schema of the public APIs, hosting, and maintenance of opening hours and height limits.

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

`build.py`, `results.json` and `ANALYSE_HISTORIQUE.md` belong to the first analytical implementation. The current reproducible evaluation lives in `analysis/`; the production application still fetches fresh data and does not read a bundled CSV.

## Reproducible data study

The analytical pipeline uses Python, pandas, NumPy and SQLite. It validates and de-duplicates the Basel-Stadt export, stores clean observations in a queryable database, and creates a fixed 182-day training period followed by a 56-day holdout. It compares three methods before accepting a result:

| Model | Holdout MAE | Coverage | Interpretation |
| --- | ---: | ---: | --- |
| Historical median | 16.72 | 100% | Best overall result |
| Previous week | 21.44 | 100% | Simple operational baseline |
| Ridge calendar model | 39.88 | 100% | More complex model rejected because it performed worse |

The headline comparison uses a paired bootstrap over local calendar days. Per-garage metrics, data-quality decisions, row-level predictions and ridge validation results are generated by `analysis/run_analysis.py`. The negative ridge result is retained rather than hidden.

```sh
python3 basel_parking/build.py --refresh
python3 analysis/run_analysis.py
python3 -m unittest discover -s analysis/tests -v
```

Open `analysis/report.html` for the full methods and results. The generated SQLite database is excluded from Git; its schema and review queries remain in `analysis/sql/`.

## Run locally

Use Python 3.10 or later to serve the generated site:

```sh
git clone https://github.com/Uschaque/basel-parking.git
cd basel-parking
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

The 13 core tests passed on 27 September 2026. The earlier browser verification is recorded in `docs/verification-fr.md`. Those Chromium checks covered the three languages at 375 x 667, the 2032 midnight rollover, refreshing data, stale history, connectivity failures, storage choices, CSP and escaping of source-provided names. These tests verify behavior in defined cases. Safari and a physical iPhone have not been tested.

### Check a deployment manually

Open the deployed site and the browser's Network panel. Filter requests for `100088`, confirm that the response contains `published`, `free` and `status`, and compare a card with that location's response. Keep the page visible to observe subsequent requests. Select a future hour and inspect the `100014` request: its date bounds should reflect a recent rolling window.

To check failure handling, block requests to `data.bs.ch` in developer tools and refresh the data. The interface should show unavailable readings or an error. Restore access and use refresh to recover. Selecting an expired source record or simulating a future date is covered by the automated tests; changing a date selector alone does not simulate the passage of calendar time.

These checks establish that the application fetches and handles responses as implemented. They do not establish that an operator's reported count matches the physical parking lot.

## Maintenance and deployment

Edit the source files in `basel_parking/`, then rebuild and include the regenerated `basel-parking-netlify/` output in the deployment. The root `netlify.toml` publishes that directory without a build command. Editing a source file alone will not update the generated site assets. A manual Netlify deployment requires uploading the rebuilt directory; automatic Git deployments depend on the site's Netlify configuration.

Review `opening_hours`, `clearance_m` and their verification dates against operator information whenever those details change. Unknown exceptions should remain explicit. Resolve the Badischer Bahnhof capacity discrepancy before removing its `capacity_unverified` entry. Publisher details must contain real, approved public contact information before a complete legal page can be generated.

The standalone HTML includes application code, configuration and fonts, but still needs internet access for parking data. Use the complete generated directory for a deployment with auxiliary pages and assets. Netlify security headers come from `_headers` and must be checked on the published host.

## Known limitations

Current availability can change before a driver arrives. Reports older than fifteen minutes are suppressed, but a shorter warning threshold would improve freshness communication. Distances used for ranking are straight-line distances, not road travel times.

The holdout validates the historical median against later public reports over one 56-day period. It does not establish performance in another season, during major events or after structural changes. Historical ranges describe past observations rather than confidence intervals. Estimates are suppressed for known public holidays and Basel carnival dates. Other exceptional events remain outside the model.

Badischer Bahnhof has conflicting visitor-capacity information across official sources. Its reported current free count is retained with a warning; its occupancy percentage and future estimate are suspended pending clarification.

New exceptional opening hours are not automatically discovered. Publisher contact information and complete legal details still need the owner's real public details. No audience analytics is configured. These limitations are documented rather than filled with invented information.

## Next steps

Repeat the fixed holdout after a new season has accumulated, add event variables known before the trip, and test whether any candidate model beats the historical median without reducing coverage. Test the interface with people unfamiliar with the project, investigate the visitor-capacity discrepancy, and test Safari on an actual device.

## Data and attribution

Current reports: https://data.bs.ch/explore/dataset/100088/

Historical reports: https://data.bs.ch/explore/dataset/100014/

Parking details: https://www.parkleitsystem-basel.ch/

The application attributes public data to Basel-Stadt under CC BY 4.0. Preserve attribution when reusing historical data. Atkinson Hyperlegible Next is distributed with its license in `basel_parking/assets/FONT-LICENSE.txt` and the deployment assets.

## Development

AI tools assisted parts of the implementation and documentation. The data source, cleaning rules, time boundaries, baselines, model-selection results, tests and limitations are available for review. The project claims only the results produced by the reproducible chronological evaluation above.

## Download historical data

The 22 MB CSV snapshot is excluded from Git. Download a fresh public export without rebuilding the earlier analysis:

```sh
python3 -c "from basel_parking.build import refresh; refresh()"
```

This writes `basel_parking/data/all_historical.csv`. No download is required to run the live application.
