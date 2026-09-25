const assert = require('node:assert/strict');
const {test} = require('node:test');
const C = require('../config.json');
const core = require('../app.js');
const DAY = 86400000;
const now = Date.parse('2032-09-25T12:00:00Z');

test('Calendar works in 2032 and uses Basel midnight, leap years and DST', () => {
  assert.equal(core.localParts(Date.parse('2032-09-25T22:01:00Z')).date, '2032-09-26');
  assert.equal(core.addDays('2032-02-28', 1), '2032-02-29');
  assert.equal(core.addDays('2032-02-29', 1), '2032-03-01');
  assert.equal(core.addDays('2032-12-31', 1), '2033-01-01');
  assert.equal(core.localParts(Date.parse('2026-03-29T00:59:00Z')).hour, 1);
  assert.equal(core.localParts(Date.parse('2026-03-29T01:00:00Z')).hour, 3);
  assert.equal(core.localParts(Date.parse('2026-10-25T00:30:00Z')).hour, 2);
  assert.equal(core.localParts(Date.parse('2026-10-25T01:30:00Z')).hour, 2);
});
test('History query uses the actual rolling year and local weekday/hour', () => {
  const url = core.historyURL(C, 5, 16, now);
  assert.match(url.searchParams.get('where'), /2032/);
  assert.doesNotMatch(url.searchParams.get('where'), /2026/);
  assert.match(url.searchParams.get('where'), /'6'.*16/);
  assert.equal(url.searchParams.get('timezone'), 'Europe/Zurich');
});
const live = {status: 'offen', free: 30, total: 100, published: new Date(now - 60000).toISOString()};
test('Live counts reject stale, future, closed and impossible observations', () => {
  assert.equal(core.liveValue(live, now, C.max_live_age_ms).free, 30);
  for (const patch of [{free: 101}, {free: null}, {total: 0}, {status: 'geschlossen'}, {published: '2026-09-25T12:00:00Z'}, {published: new Date(now + DAY).toISOString()}]) {
    assert.equal(core.liveValue({...live, ...patch}, now, C.max_live_age_ms).free, undefined);
  }
  assert.equal(core.liveValue({...live, free: 0}, now, C.max_live_age_ms).free, 0);
});
function sample() {
  return Array.from({length: 20}, (_, i) => ({id2: 'test', free: 10 + i * 2, total: 100, published: new Date(now - (i + 1) * 7 * DAY).toISOString()}));
}
const day = core.weekday(core.localParts(now).date), hour = core.localParts(now).hour;
test('Recent matching observations produce a median, with duplicate dates removed', () => {
  const rows = sample(), p = core.profilesFromRows([...rows, rows[0]], {test:{total:100}}, C, day, hour, now).test;
  assert.equal(p.n, 20);
  assert.equal(p.free, 29);
  assert.equal(p.total, 100);
});
test('Old samples and new capacity do not produce a stale forecast', () => {
  assert.equal(core.profilesFromRows(sample(), {test:{total:200}}, C, day, hour, now).test.free, undefined);
  assert.deepEqual(core.profilesFromRows(sample(), {}, C, day, hour, now + 6 * 365 * DAY), {});
  assert.equal(core.profilesFromRows(sample().slice(4), {}, C, day, hour, now).test.free, undefined);
});
test('Bad source values suppress the affected forecast, instead of being hidden', () => {
  const rows = sample(); rows[0].free = 999;
  assert.equal(core.profilesFromRows(rows, {}, C, day, hour, now).test.free, undefined);
});
test('Published regular entry hours close Bahnhof Süd at 23:00, but keep 24-hour garages open', () => {
  assert.equal(core.openingAt(C, 'bahnhofsued', '2032-09-25', 5, 59).state, 'closed');
  assert.equal(core.openingAt(C, 'bahnhofsued', '2032-09-25', 6).state, 'open');
  assert.equal(core.openingAt(C, 'bahnhofsued', '2032-09-25', 22, 59).state, 'open');
  assert.equal(core.openingAt(C, 'bahnhofsued', '2032-09-25', 23).state, 'closed');
  assert.equal(core.openingAt(C, 'city', '2032-09-25', 23).state, 'open');
});
test('Sunday closure and weekday overnight hours do not interpret tariff hours as opening hours', () => {
  assert.equal(core.weekday('2032-09-26'), 6);
  for (const id of ['anfos', 'clarahuus']) {
    assert.equal(core.openingAt(C, id, '2032-09-26', 16).state, 'closed');
    assert.equal(core.openingAt(C, id, '2032-09-27', 0).state, 'closed');
    assert.equal(core.openingAt(C, id, '2032-09-27', 6).state, 'open');
    assert.equal(core.openingAt(C, id, '2032-09-28', 0).state, 'open');
    assert.equal(core.openingAt(C, id, '2032-09-28', 1).state, 'closed');
  }
  assert.equal(core.openingAt(C, 'new_parking', '2032-09-26', 16).state, 'unknown');
});
test('Basel-Stadt holidays recur across years and close Anfos, not all garages', () => {
  for (const date of ['2026-04-03','2026-04-06','2026-05-14','2026-05-25','2027-03-26','2027-05-06','2027-05-17','2030-04-19','2030-05-30','2030-06-10','2032-05-01','2032-12-25']) {
    assert.equal(core.isBaselHoliday(date), true, date);
    assert.equal(core.openingAt(C, 'anfos', date, 16).state, 'closed', date);
    assert.equal(core.openingAt(C, 'city', date, 16).state, 'open', date);
  }
  assert.equal(core.isBaselHoliday('2032-05-02'), false);
});

test('Missing total keeps a valid live free count but no percentage', () => {
  for (const total of [null, undefined, '']) {
    const result = core.liveValue({...live, free:77,total}, now, C.max_live_age_ms);
    assert.equal(result.free,77);assert.equal(result.total,null);assert.equal(result.open,true);
  }
  for (const free of [true, false, ' ', -1, 2.5]) assert.equal(core.liveValue({...live,free,total:null},now,C.max_live_age_ms).free,undefined);
});
test('Open status stays separate from missing or inconsistent counts', () => {
  const x=core.liveValue({...live, free:null},now,C.max_live_age_ms);
  assert.equal(x.open,true);assert.equal(x.free,undefined);
  assert.equal(core.liveValue({...live,status:'geschlossen',total:null},now,C.max_live_age_ms).closed,true);
});
test('Anfos special opening dates require confirmation instead of false closure', () => {
  for (const date of ['2026-12-13','2026-12-20','2027-02-15']) assert.equal(core.openingAt(C,'anfos',date,16).state,'unknown',date);
  assert.equal(core.isSpecialDate('2027-02-15'),true);assert.equal(core.isSpecialDate('2027-02-17'),true);assert.equal(core.isSpecialDate('2027-02-18'),false);
});
test('Historical range contains median and uses observed values', () => {
  const p=core.profilesFromRows(sample(),{test:{total:100}},C,day,hour,now).test;
  assert(p.low <= p.free && p.free <= p.high);assert.equal(p.low,18);assert.equal(p.high,40);
});
