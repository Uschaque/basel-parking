/* Local translations for privacy and 404 pages. */
(function () {
  'use strict';
  const messages = window.ParkingMessages;
  const select = document.getElementById('language');
  let locale = new URLSearchParams(location.search).get('lang');
  if (!Object.hasOwn(messages, locale)) {
    locale = 'en';
    try { if (localStorage.getItem('basel-parking-consent') === 'accepted') locale = localStorage.getItem('basel-parking-language') || 'en'; } catch {}
  }
  if (!Object.hasOwn(messages, locale)) locale = 'en';
  function translate() {
    const m = messages[locale], is404 = document.body.dataset.page === '404';
    document.documentElement.lang = locale;
    document.title = m[is404 ? 'notFoundTitle' : 'privacyPageTitle'];
    document.querySelector('meta[name="description"]').content = m[is404 ? 'notFoundDescription' : 'privacyDescription'];
    document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = m[el.dataset.i18n] || el.textContent; });
    select.value = locale;
    select.setAttribute('aria-label', m.languageLabel);
    document.querySelectorAll('[data-home]').forEach(el => { el.href = '/?lang=' + locale; });
  }
  select.addEventListener('change', () => {
    if (!Object.hasOwn(messages, select.value)) return;
    locale = select.value;
    try { if (localStorage.getItem('basel-parking-consent') === 'accepted') localStorage.setItem('basel-parking-language', locale); } catch {}
    translate();
  });
  translate();
})();
