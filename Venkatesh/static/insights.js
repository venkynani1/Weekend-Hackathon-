// Business-case calculator on the Insights page. Pure arithmetic, no network.
(function () {
  const root = document.getElementById("calculator");
  if (!root) return;
  const form = root.querySelector("form");
  const d = root.dataset;
  const leavers = Number(d.leavers);
  const costReachedAtBase = Number(d.costReached); // replacement cost of real leavers on the list, at base months
  const baseMonths = Number(d.baseMonths);
  const medianIncome = Number(d.medianIncome);
  const randomLeavers = Number(d.randomLeavers);
  const avgLeaverCostAtBase = Number(d.avgLeaverCost);
  const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
  const out = (key) => root.querySelector(`[data-out="${key}"]`);

  function update() {
    const save = Number(form.save.value) / 100;
    const months = Number(form.months.value);
    const talk = Number(form.talk.value);
    const cycles = Number(form.cycles.value);

    form.save.nextElementSibling.textContent = `${Math.round(save * 100)}%`;
    form.months.nextElementSibling.textContent = months.toFixed(1);
    form.talk.nextElementSibling.textContent = talk.toFixed(2);
    form.cycles.nextElementSibling.textContent = String(cycles);

    const scale = months / baseMonths;
    const gross = costReachedAtBase * scale * save;
    const programme = 50 * medianIncome * talk;
    const net = gross - programme;
    const randomNet = randomLeavers * avgLeaverCostAtBase * scale * save - programme;

    out("saves").textContent = (leavers * save).toFixed(1);
    out("net").textContent = money.format(net);
    out("year").textContent = money.format(net * cycles);
    out("roi").textContent = programme > 0 ? `${(net / programme).toFixed(1)}x` : "n/a";
    out("random").textContent = money.format(randomNet);
    out("net").classList.toggle("negative", net < 0);
    out("random").classList.toggle("negative", randomNet < 0);
  }

  form.addEventListener("input", update);
  update();
})();
