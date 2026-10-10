// Site-wide: cookie consent and consent-gated analytics.
(function () {
  const KEY = "tg-consent";
  const banner = document.getElementById("cookie-banner");
  const code = document.body.dataset.analytics;

  function read() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function write(value) {
    try { localStorage.setItem(KEY, value); } catch (e) { /* private mode: choice lasts this page only */ }
  }
  function loadAnalytics() {
    if (!code || document.getElementById("gc-script")) return;
    const s = document.createElement("script");
    s.id = "gc-script";
    s.async = true;
    s.src = "https://gc.zgo.at/count.js";
    s.dataset.goatcounter = `https://${code}.goatcounter.com/count`;
    document.body.appendChild(s);
  }

  const choice = read();
  if (choice === "all") loadAnalytics();
  if (!choice && banner) banner.hidden = false;

  if (banner) {
    banner.addEventListener("click", (event) => {
      const value = event.target.dataset && event.target.dataset.consent;
      if (!value) return;
      write(value);
      banner.hidden = true;
      if (value === "all") loadAnalytics();
    });
  }
  const settings = document.getElementById("cookie-settings");
  if (settings && banner) settings.addEventListener("click", () => { banner.hidden = false; });
})();
