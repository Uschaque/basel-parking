/* Browser application. No server, key, package or dated occupancy snapshot required. */
(function (root) {
  'use strict';
  const DAY = 86400000;
  function localParts(now, zone = 'Europe/Zurich') {
    const p = Object.fromEntries(new Intl.DateTimeFormat('en-GB', {
      timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
    }).formatToParts(new Date(now)).map(x => [x.type, x.value]));
    return {date: `${p.year}-${p.month}-${p.day}`, hour: Number(p.hour), minute: Number(p.minute)};
  }
  function addDays(date, n) { return new Date(Date.parse(date + 'T12:00:00Z') + n * DAY).toISOString().slice(0, 10); }
  function weekday(date) { return (new Date(date + 'T12:00:00Z').getUTCDay() + 6) % 7; }
  function median(values) { const a = [...values].sort((a, b) => a - b), m = Math.floor(a.length / 2); return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2; }
  function number(v) { return typeof v === 'number' || typeof v === 'string' && v.trim() !== '' ? Number(v) : NaN; }
  function validCounts(x) { const f = number(x.free), t = number(x.total); return Number.isInteger(f) && Number.isInteger(t) && f >= 0 && t > 0 && f <= t; }
  function liveValue(x, now, maxAge) {
    if (!x) return {reason: 'Relevé indisponible'};
    const age = now - Date.parse(x.published);
    if (!Number.isFinite(age) || age < -60000 || age > maxAge) return {reason: 'Relevé trop ancien'};
    const status = String(x.status).toLowerCase();
    if (status !== 'offen') return {reason: status === 'geschlossen' ? 'Fermé actuellement' : 'Statut non confirmé', closed: status === 'geschlossen'};
    const free = number(x.free), total = number(x.total);
    const missingTotal = x.total === null || x.total === undefined || x.total === '';
    if (!Number.isInteger(free) || free < 0 || !missingTotal && !validCounts(x)) return {reason: 'Relevé incohérent', open: true};
    return {free, total: missingTotal ? null : total, published: x.published, open: true};
  }
  function historyURL(config, day, hour, now) {
    const u = new URL(`${config.api_base}/${config.history_dataset}/exports/json`);
    u.search = new URLSearchParams({
      select: 'id2,published,free,total', timezone: config.timezone,
      where: `published >= date'${new Date(now - config.lookback_days * DAY).toISOString()}' and published < date'${new Date(now).toISOString()}' and date_format(published, 'e') = '${day + 1}' and hour(published) = ${hour}`,
      order_by: 'published desc'
    });
    return u;
  }
  function profilesFromRows(rows, catalog, config, day, hour, now) {
    const groups = Object.create(null), seen = new Set();
    for (const row of rows) {
      const stamp = Date.parse(row.published), key = String(row.id2 || '');
      if (!key || !Number.isFinite(stamp) || stamp >= now || stamp < now - config.lookback_days * DAY) continue;
      const p = localParts(stamp, config.timezone);
      if (weekday(p.date) !== day || p.hour !== hour) continue;
      // One hourly observation per local date: repeated winter-time hours get one vote.
      const unique = `${key}:${p.date}`;
      if (seen.has(unique)) continue;
      seen.add(unique);
      const g = groups[key] ||= {rows: [], invalid: 0, all: 0};
      g.all++;
      if (!validCounts(row)) { g.invalid++; continue; }
      g.rows.push({...row, free: Number(row.free), total: Number(row.total), stamp});
    }
    const profiles = {};
    for (const [key, g] of Object.entries(groups)) {
      if (g.invalid / g.all > .01) { profiles[key] = {reason: 'Historique incohérent pour ce créneau'}; continue; }
      g.rows.sort((a, b) => b.stamp - a.stamp);
      const latest = g.rows[0];
      if (!latest || now - latest.stamp > config.max_history_age_days * DAY) { profiles[key] = {reason: 'Historique trop ancien'}; continue; }
      const capacity = number(catalog[key]?.total) > 0 ? number(catalog[key].total) : latest.total;
      const comparable = g.rows.filter(r => r.total === capacity);
      if (comparable.length < config.min_samples) { profiles[key] = {reason: 'Historique comparable insuffisant'}; continue; }
      const newest = Math.max(...comparable.map(r => r.stamp));
      if (now - newest > config.max_history_age_days * DAY) { profiles[key] = {reason: 'Historique comparable trop ancien'}; continue; }
      const values = comparable.map(r => r.free).sort((a, b) => a - b);
      profiles[key] = {free: Math.round(median(values)), total: capacity, n: comparable.length,
        low: values[Math.floor((values.length - 1) * .25)], high: values[Math.ceil((values.length - 1) * .75)], published: new Date(newest).toISOString()};
    }
    return profiles;
  }
  function distance(a, b) {
    if (![a?.lat, a?.lon, b?.lat, b?.lon].every(Number.isFinite)) return Infinity;
    const rad = x => x * Math.PI / 180, x = rad(b.lat - a.lat), y = rad(b.lon - a.lon);
    return 12742000 * Math.asin(Math.sqrt(Math.sin(x / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(y / 2) ** 2));
  }
  function easterDate(year) {
    // Gregorian Easter; Basel-Stadt's movable public holidays are offsets from it.
    const a = year % 19, b = Math.floor(year / 100), c = year % 100;
    const d = Math.floor(b / 4), e = b % 4, f = Math.floor((b + 8) / 25);
    const g = Math.floor((b - f + 1) / 3), h = (19 * a + b - d - g + 15) % 30;
    const i = Math.floor(c / 4), k = c % 4, l = (32 + 2 * e + 2 * i - h - k) % 7;
    const m = Math.floor((a + 11 * h + 22 * l) / 451);
    const x = h + l - 7 * m + 114, month = Math.floor(x / 31), day = x % 31 + 1;
    return new Date(Date.UTC(year, month - 1, day)).toISOString().slice(0, 10);
  }
  function isBaselHoliday(date) {
    if (['01-01', '05-01', '08-01', '12-25', '12-26'].includes(date.slice(5))) return true;
    return [-2, 1, 39, 50].some(offset => addDays(easterDate(Number(date.slice(0, 4))), offset) === date);
  }
  function isSpecialDate(date) {
    const easter = easterDate(Number(date.slice(0, 4)));
    return [-41, -40, -39].some(offset => addDays(easter, offset) === date);
  }
  function anfosException(date) {
    if (date === addDays(easterDate(Number(date.slice(0, 4))), -41)) return true;
    let sunday = addDays(date.slice(0, 4) + '-12-25', -1);
    while (weekday(sunday) !== 6) sunday = addDays(sunday, -1);
    return date === sunday || date === addDays(sunday, -7);
  }
  function openingAt(config, id, date, hour, minute = 0) {
    const rule = config.opening_hours?.[id];
    if (!rule) return {state: 'unknown', hours: null};
    if (id === 'anfos' && anfosException(date)) return {state: 'unknown', special: true};
    if (rule.kind === 'always') return {state: 'open', hours: '24/7'};
    const time = hour * 60 + minute, day = weekday(date);
    if (rule.kind === 'daily') return {state: time >= rule.start && time < rule.end ? 'open' : 'closed', hours: '06:00–23:00'};
    if (rule.kind === 'mon_sat_overnight') {
      // Sunday is conservatively closed even in the 00:00–01:00 overlap.
      // Special openings and public holidays need operator confirmation.
      const holiday = rule.holidays === 'closed' && (isBaselHoliday(date) || time < rule.end_next_day && isBaselHoliday(addDays(date, -1)));
      const open = !holiday && day !== 6 && (time >= rule.start || (day !== 0 && time < rule.end_next_day));
      return {state: open ? 'open' : 'closed', hours: 'Mon–Sat 06:00–01:00; Sun closed'};
    }
    return {state: 'unknown', hours: null};
  }
  const core = {localParts, addDays, weekday, median, validCounts, liveValue, historyURL, profilesFromRows, distance, isBaselHoliday, isSpecialDate, openingAt};
  if (typeof module !== 'undefined' && module.exports) module.exports = core;
  root.ParkingCore = core;
  if (typeof document === 'undefined') return;

  const C = JSON.parse(document.querySelector('#config').textContent);
  const $ = id => document.getElementById(id);
  const escape = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const messages = root.ParkingMessages;
  let preferred = 'en', consent = null;
  try {
    consent = localStorage.getItem('basel-parking-consent');
    if (consent === 'accepted' && Object.hasOwn(messages, localStorage.getItem('basel-parking-language'))) preferred = localStorage.getItem('basel-parking-language');
    if (consent !== 'accepted') { localStorage.removeItem('basel-parking-language'); localStorage.removeItem('basel-parking-v2-history'); }
  } catch {}
  const requestedLanguage = new URLSearchParams(location.search).get('lang');
  if (Object.hasOwn(messages, requestedLanguage)) preferred = requestedLanguage;
  const state = {locale: preferred, catalog: {}, live: {}, liveBusy: false, liveError: '', liveAttempt: 0, liveFetched: 0, history: new Map(), historyError: '', historyBusy: false, request: 0, activeHistory: null, calendar: '', hoursKey: ''};
  const localeCode = () => ({en:'en-GB',de:'de-CH',fr:'fr-CH'})[state.locale];
  const t = (key, vars = {}) => (messages[state.locale][key] ?? messages.en[key] ?? key).replace(/\{(\w+)\}/g, (_, name) => String(vars[name] ?? ''));
  const dateLabel = date => new Intl.DateTimeFormat(localeCode(), {timeZone: C.timezone, weekday: 'short', day: 'numeric', month: 'short'}).format(new Date(date + 'T12:00:00Z'));
  const longDate = date => new Intl.DateTimeFormat(localeCode(), {timeZone: C.timezone, dateStyle:'long'}).format(new Date(date + 'T12:00:00Z'));
  const timeLabel = date => new Intl.DateTimeFormat(localeCode(), {timeZone: C.timezone, hour: '2-digit', minute: '2-digit'}).format(new Date(date));
  const numberLabel = value => Number(value).toLocaleString(localeCode());
  function translatePage() {
    document.documentElement.lang = state.locale;
    document.title = t('title');
    $('privacy-link').href = 'privacy.html?lang=' + state.locale;
    document.querySelector('meta[name="description"]').content = t('description');
    document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
    $('language').value = state.locale;
    $('language').setAttribute('aria-label', t('languageLabel'));
    $('refresh').setAttribute('aria-label', t('refresh'));
    document.querySelector('.search').setAttribute('aria-label', t('arrivalDate'));
    for (const option of $('vehicle').options) {
      if (option.value !== '0') option.textContent = Number(option.value).toLocaleString(localeCode(), {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' m';
    }
    for (const [id, d] of Object.entries(C.destinations)) {
      const existing = Array.from($('destination').options).find(option => option.value === id);
      if (existing) existing.textContent = t('destination_' + id);
      else $('destination').add(new Option(t('destination_' + id), id));
    }
  }

  function syncCalendar(now = Date.now(), relabel = false) {
    const current = localParts(now, C.timezone), before = $('day').value, beforeHour = $('hour').value;
    let changed = false;
    if (state.calendar !== current.date || relabel) {
      const followedToday = !before || before === state.calendar;
      const options = Array.from({length: C.date_window_days}, (_, i) => {
        const date = addDays(current.date, i);
        return new Option(i === 0 ? t('today') : i === 1 ? t('tomorrow') + ' · ' + dateLabel(date) : dateLabel(date), date);
      });
      $('day').replaceChildren(...options);
      $('day').value = followedToday || before < current.date || before > addDays(current.date, C.date_window_days - 1) ? current.date : before;
      if (state.calendar !== current.date) { state.history.clear(); changed = true; }
      state.calendar = current.date;
      if (relabel) state.hoursKey = '';
    }
    const today = $('day').value === current.date, key = `${$('day').value}:${today ? current.hour : 'future'}`;
    if (state.hoursKey !== key) {
      const options = today ? [new Option(t('now'), 'now')] : [];
      for (let h = today ? current.hour + 1 : 0; h < 24; h++) options.push(new Option(`${String(h).padStart(2, '0')}:00`, String(h)));
      $('hour').replaceChildren(...options);
      const exists = options.some(o => o.value === beforeHour);
      $('hour').value = exists ? beforeHour : today ? 'now' : '10';
      state.hoursKey = key;
    }
    return changed || before !== $('day').value || beforeHour !== $('hour').value;
  }
  function selection() { return {day: weekday($('day').value), hour: Number($('hour').value), now: $('hour').value === 'now', date: $('day').value}; }
  function cacheKey(s) { return `${state.calendar}:${s.day}:${s.hour}`; }
  async function fetchJSON(url, timeout = 20000) {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), timeout);
    try { const r = await fetch(String(url), {cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer', signal: controller.signal}); if (!r.ok) throw new Error(`HTTP ${r.status}`); return await r.json(); }
    finally { clearTimeout(timer); }
  }
  function storageRead(key) { if (consent !== 'accepted') return null; try { const x = JSON.parse(localStorage.getItem('basel-parking-v2-history')); return x?.key === key ? x : null; } catch { return null; } }
  function storageWrite(value) { if (consent === 'accepted') try { localStorage.setItem('basel-parking-v2-history', JSON.stringify(value)); } catch {} }
  function recentCache(entry, now) { return entry && Array.isArray(entry.rows) && now >= entry.fetchedAt && now - entry.fetchedAt < C.history_refresh_ms; }

  async function loadHistory(force = false) {
    const s = selection(), token = ++state.request;
    if (s.now) { state.historyBusy = false; state.activeHistory = null; state.historyError = ''; render(); return; }
    const key = cacheKey(s), now = Date.now(), cached = state.history.get(key) || storageRead(key);
    if (!force && recentCache(cached, now)) { state.historyBusy = false; state.activeHistory = cached; state.historyError = ''; render(); return; }
    state.historyBusy = true; state.historyError = ''; state.activeHistory = null; render();
    try {
      const rows = await fetchJSON(historyURL(C, s.day, s.hour, now), 30000);
      if (!Array.isArray(rows)) throw Error('Format historique inattendu');
      const value = {key, fetchedAt: Date.now(), rows};
      state.history.set(key, value); storageWrite(value);
      if (token === state.request) state.activeHistory = value;
    } catch (e) { if (token === state.request) state.historyError = 'historyError'; }
    finally { if (token === state.request) { state.historyBusy = false; render(); } }
  }
  async function loadLive() {
    if (state.liveBusy) return;
    state.liveBusy = true; state.liveAttempt = Date.now(); $('refresh').disabled = true;
    try {
      // Export is unpaginated: newly published garages are discovered automatically.
      const rows = await fetchJSON(`${C.api_base}/${C.live_dataset}/exports/json?select=id2,name,address,status,free,total,published,geo_point_2d`);
      if (!Array.isArray(rows) || !rows.length || !rows.some(x => x.id2 && x.published)) throw Error('Format actuel inattendu');
      const catalog = Object.create(null), live = Object.create(null);
      for (const row of rows) {
        if (!row.id2) continue;
        const key = String(row.id2), old = live[key];
        if (old && Date.parse(old.published) > Date.parse(row.published)) continue;
        live[key] = row;
        const point = row.geo_point_2d || {};
        catalog[key] = {key, name: row.name || row.title || key, address: row.address || '', total: row.total,
          lat: number(point.lat), lon: number(point.lon), height: C.clearance_m[key] ?? null,
          url: `https://www.parkleitsystem-basel.ch/parkhaus/${encodeURIComponent(key)}.html`};
      }
      state.catalog = catalog; state.live = live; state.liveFetched = Date.now(); state.liveError = '';
    } catch (e) { state.live = {}; state.liveError = 'liveError'; }
    finally { state.liveBusy = false; $('refresh').disabled = false; render(); }
  }
  const reasons = {
    'Relevé indisponible':'reasonNoReading', 'Relevé trop ancien':'reasonStale', 'Fermé actuellement':'reasonClosed',
    'Statut non confirmé':'reasonUnknownStatus', 'Relevé incohérent':'reasonInvalid',
    'Historique incohérent pour ce créneau':'reasonBadHistory', 'Historique trop ancien':'reasonOldHistory',
    'Historique comparable insuffisant':'reasonFewHistory', 'Historique comparable trop ancien':'reasonComparableOld'
  };
  let showAll = false;
  function render() {
    const s = selection(), now = Date.now(), dest = C.destinations[$('destination').value], height = Number($('vehicle').value);
    const current = localParts(now, C.timezone), entry = state.activeHistory;
    const usable = !s.now && entry?.key === cacheKey(s) && recentCache(entry, now);
    const profiles = usable ? profilesFromRows(entry.rows, state.catalog, C, s.day, s.hour, now) : {};
    const garages = Object.values(state.catalog).filter(g => !height || g.height !== null && g.height >= height);
    const items = garages.map(g => {
      const hours = openingAt(C, g.key, s.now ? current.date : s.date, s.now ? current.hour : s.hour, s.now ? current.minute : 0);
      const observed = s.now ? liveValue(state.live[g.key], now, C.max_live_age_ms) : null;
      let value = s.now ? observed : profiles[g.key] || {reason: state.historyBusy ? 'loadingEstimate' : 'reasonNoEstimate'};
      // Current source status and regular schedules are independent evidence.
      // A fresh open report is kept, with a visible conflict message if needed.
      if (!s.now) {
        if (hours.state === 'closed') value = {reason: 'reasonScheduledClosed', closed: true};
        else if (hours.state === 'unknown') value = {reason: hours.special ? 'reasonSpecialHours' : 'reasonNoHours'};
        else if (isBaselHoliday(s.date) || isSpecialDate(s.date)) value = {reason: 'reasonSpecialDate'};
        else if (C.capacity_unverified?.includes(g.key)) value = {reason: 'reasonCapacityReview'};
      }
      return {g, value, hours, observed, distance: distance(dest, g)};
    });
    items.sort((a, b) => Number(!(a.value.free > 0)) - Number(!(b.value.free > 0)) || a.distance - b.distance || a.g.name.localeCompare(b.g.name));
    const validLive = Object.values(state.live).filter(x => Number.isFinite(liveValue(x, now, C.max_live_age_ms).free)).length;
    $('connection').className = state.liveError || !validLive ? 'error' : 'ok';
    const connection = state.liveError ? t(state.liveError) : state.liveFetched ? t('connectionLast', {time:timeLabel(state.liveFetched)}) + (!validLive ? t('connectionNone') : '') : t('connectionPending');
    if ($('connection').textContent !== connection) $('connection').textContent = connection;
    $('mode-label').textContent = t(s.now ? 'modeNow' : 'modeFuture');
    $('results-title').textContent = s.now ? t('titleNow') : t('titleFuture', {date:dateLabel(s.date), hour:String(s.hour).padStart(2,'0')});
    $('count').textContent = t('count', {count:items.length});
    $('context').textContent = t('context', {destination:t('destination_' + $('destination').value)});
    const notes = [];
    if (!s.now) notes.push(`<div class="notice info">${escape(t('futureNote'))}</div>`);
    if (!s.now && state.historyError) notes.push(`<div class="notice">${escape(t(state.historyError))}</div>`);
    const noticeHTML = notes.join('');
    if ($('notice').innerHTML !== noticeHTML) $('notice').innerHTML = noticeHTML;
    $('cards').setAttribute('aria-busy', String(!state.liveFetched && state.liveBusy || !s.now && state.historyBusy));
    const visible = showAll ? items : items.slice(0, 4);
    const markup = visible.length ? visible.map(({g, value: v, hours, observed}) => {
      const valid = Number.isFinite(v.free), questionable = C.capacity_unverified?.includes(g.key);
      const occupancy = valid && v.total > 0 && !questionable ? Math.round(100 * (1 - v.free / v.total)) : null;
      let badge = s.now ? observed.closed ? 'badgeClosed' : observed.open ? 'badgeOpen' : 'badgeUnavailable'
        : hours.state === 'closed' ? 'badgeExpectedClosed' : hours.state === 'open' ? 'badgeExpectedOpen' : 'badgeUnknown';
      const color = badge === 'badgeClosed' || badge === 'badgeExpectedClosed' ? 'closed' : badge === 'badgeUnknown' || badge === 'badgeUnavailable' ? 'unverified' : 'open';
      const info = valid ? s.now ? t('lastReport', {time:timeLabel(v.published)}) : t('latestHistory', {n:v.n, date:dateLabel(localParts(Date.parse(v.published), C.timezone).date)}) : t(reasons[v.reason] || v.reason || 'reasonNoEstimate');
      const rule = C.opening_hours[g.key];
      const hoursLabel = t(!rule ? 'hoursUnknown' : rule.kind === 'always' ? 'hoursAlways' : rule.kind === 'daily' ? 'hoursDaily' : 'hoursWeek');
      const maxHeight = g.height !== null ? t('maxHeight', {height:g.height.toLocaleString(localeCode(), {minimumFractionDigits:2, maximumFractionDigits:2})}) : t('heightUnknown');
      const warning = s.now && observed.open && hours.state === 'closed' ? t('hoursConflict') : '';
      const capacityNote = questionable ? t('capacityReview') : valid && occupancy === null ? t('capacityMissing') : '';
      const coordinates = [g.lat,g.lon].every(Number.isFinite) ? `${g.lat},${g.lon}` : `${g.address}, Basel, Switzerland`;
      const route = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(coordinates)}&travelmode=driving`;
      return `<article class="card" data-parking="${escape(g.key)}">
        <div class="card-heading"><h3>${escape(g.name)}</h3><span class="badge ${color}">${escape(t(badge))}</span><p class="address">${escape(g.address)}</p></div>
        <div class="availability"><span class="number${valid ? v.free < 10 ? ' tight' : '' : ' unknown'}">${valid ? escape(numberLabel(v.free)) : escape(t('unknownCount'))}</span><span class="places-label">${escape(t(s.now ? 'freeNow' : 'freeFuture'))}</span></div>
        <div class="reading"><p class="measure">${escape(info)}</p>${warning ? `<p class="data-warning">${escape(warning)}</p>` : ''}${capacityNote ? `<p class="data-warning">${escape(capacityNote)}</p>` : ''}
        ${occupancy !== null ? `<p class="occupancy">${escape(t(s.now ? 'occupied' : 'occupiedFuture'))} <strong>${escape(t('capacity',{pct:occupancy,total:numberLabel(v.total)}))}</strong></p><meter min="0" max="100" value="${occupancy}" aria-label="${escape(t(s.now ? 'occupied' : 'occupiedFuture'))}">${occupancy}%</meter>` : ''}</div>
        <details class="parking-details" data-details="${escape(g.key)}"><summary>${escape(t('details'))}</summary><p>${escape(hoursLabel)}</p><p>${escape(maxHeight)}</p>${!s.now && valid ? `<p>${escape(t('range', {low:numberLabel(v.low),high:numberLabel(v.high)}))}</p>` : ''}<p>${escape(t('checkedOn',{date:longDate(C.opening_hours_checked_on)}))}</p><a href="${g.url}" target="_blank" rel="noopener noreferrer">${escape(t('parkInfo'))}</a></details>
        <a class="directions" href="${route}" aria-label="${escape(t('directionsTo',{name:g.name}))}" target="_blank" rel="noopener noreferrer">${escape(t('directions'))}</a>
      </article>`;
    }).join('') : `<div class="empty">${escape(t(state.liveBusy && !state.liveFetched ? 'loading' : !Object.keys(state.catalog).length ? 'noCatalog' : 'noHeight'))}</div>`;
    // Do not discard keyboard focus or expanded details on each timer tick.
    const normalized = document.createElement('div'); normalized.innerHTML = markup;
    for (const d of $('cards').querySelectorAll('details[open]')) {
      for (const next of normalized.querySelectorAll('details')) if (next.dataset.details === d.dataset.details) next.open = true;
    }
    if ($('cards').innerHTML !== normalized.innerHTML) {
      const focused = document.activeElement, oldCard = focused?.closest('.card');
      const focusKey = oldCard?.dataset.parking, focusPart = focused?.tagName === 'SUMMARY' ? 'summary' : focused?.classList.contains('directions') ? '.directions' : focused?.closest('details') ? 'details a' : null;
      $('cards').replaceChildren(...normalized.childNodes);
      if (focusKey && focusPart) {
        const card = [...$('cards').querySelectorAll('.card')].find(el => el.dataset.parking === focusKey);
        card?.querySelector(focusPart)?.focus({preventScroll:true});
      }
    }
    $('show-more').hidden = items.length <= 4;
    $('show-more').textContent = t(showAll ? 'showLess' : 'showMore', {n:Math.max(0,items.length - 4)});
    $('show-more').setAttribute('aria-expanded', String(showAll));
    $('height-note').textContent = t('heightNote', {date:longDate(C.opening_hours_checked_on)}) + (height ? t('heightFiltered') : '');
  }
  let lastHistoryAttempt = 0;
  function tick() {
    const changed = syncCalendar(), now = Date.now();
    if (changed) loadHistory();
    render();
    if (document.hidden) return;
    if (now - state.liveAttempt >= C.live_refresh_ms || now < state.liveAttempt) loadLive();
    if (!selection().now && !state.historyBusy && now - lastHistoryAttempt >= C.live_refresh_ms) {
      lastHistoryAttempt = now; loadHistory();
    }
  }
  $('day').addEventListener('change', () => { syncCalendar(); loadHistory(); });
  $('hour').addEventListener('change', () => loadHistory());
  $('destination').addEventListener('change', render);
  $('vehicle').addEventListener('change', render);
  $('language').addEventListener('change', () => {
    if (!messages[$('language').value]) return;
    state.locale = $('language').value;
    if (consent === 'accepted') try { localStorage.setItem('basel-parking-language', state.locale); } catch {}
    translatePage(); syncCalendar(Date.now(), true); render();
  });
  $('refresh').addEventListener('click', () => { syncCalendar(); loadLive(); loadHistory(true); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) { tick(); if (Date.now() - state.liveAttempt > 15000) loadLive(); } });
  root.addEventListener('pageshow', tick);
  root.addEventListener('online', () => { syncCalendar(); loadLive(); loadHistory(true); });
  function saveConsent(value) {
    consent = value;
    try {
      localStorage.setItem('basel-parking-consent', value);
      if (value === 'accepted') localStorage.setItem('basel-parking-language', state.locale);
      else { localStorage.removeItem('basel-parking-language'); localStorage.removeItem('basel-parking-v2-history'); }
    } catch {}
    $('privacy-banner').hidden = true;
    $('privacy-status').textContent = t(value === 'accepted' ? 'consentAccepted' : 'consentRejected');
  }
  $('consent-accept').addEventListener('click', () => saveConsent('accepted'));
  $('consent-reject').addEventListener('click', () => saveConsent('rejected'));
  $('privacy-settings').addEventListener('click', () => { $('privacy-banner').hidden = false; $('consent-reject').focus(); });
  $('privacy-banner').hidden = consent === 'accepted' || consent === 'rejected';
  $('show-more').addEventListener('click', () => { showAll = !showAll; render(); });
  $('view-results').addEventListener('click', () => { $('results-title').focus({preventScroll:true}); $('results').scrollIntoView({block:'start'}); });
  translatePage(); syncCalendar(); render(); loadLive();
  setInterval(tick, 15000);
})(typeof window !== 'undefined' ? window : globalThis);
