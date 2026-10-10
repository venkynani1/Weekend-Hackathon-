// Live scoring page: load a profile, validate it, score it on the server, render the result.
(function () {
  const form = document.getElementById("score-form");
  if (!form) return;
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const roles = JSON.parse(document.getElementById("roles-data").textContent);
  const select = document.getElementById("employee-select");
  const idInput = document.getElementById("employee-id");
  const idError = document.getElementById("employee-id-error");
  const loadedLabel = document.getElementById("loaded-label");
  const formError = document.getElementById("form-error");
  const button = document.getElementById("score-button");
  const result = document.getElementById("result");
  const empty = document.getElementById("result-empty");
  const skeleton = document.getElementById("result-skeleton");
  const body = document.getElementById("result-body");

  const pct = (v) => `${Math.round(v * 100)}%`;
  const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
  const esc = (v) => String(v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c]));
  const fields = [...form.querySelectorAll(".field input, .field select")];

  function syncRoles(keepRole) {
    const dept = form.Department.value;
    const current = keepRole ?? form.JobRole.value;
    form.JobRole.innerHTML = roles[dept].map((r) => `<option value="${esc(r)}">${esc(r)}</option>`).join("");
    form.JobRole.value = roles[dept].includes(current) ? current : roles[dept][0];
  }
  form.Department.addEventListener("change", () => syncRoles());

  function setFieldError(name, message) {
    const el = document.getElementById(`e-${name}`);
    const input = form.elements[name];
    if (el) el.textContent = message || "";
    if (input) input.setAttribute("aria-invalid", message ? "true" : "false");
  }
  function clearErrors() {
    fields.forEach((f) => setFieldError(f.name, ""));
    formError.textContent = "";
  }

  function validate() {
    clearErrors();
    let ok = true;
    fields.forEach((f) => {
      if (!f.checkValidity()) {
        ok = false;
        if (f.validity.valueMissing) setFieldError(f.name, "Required.");
        else if (f.validity.rangeUnderflow || f.validity.rangeOverflow) setFieldError(f.name, `Must be between ${Number(f.min).toLocaleString()} and ${Number(f.max).toLocaleString()}.`);
        else setFieldError(f.name, "Enter a whole number.");
      }
    });
    if (!ok) return false;
    const n = (name) => Number(form.elements[name].value);
    for (const name of ["YearsInCurrentRole", "YearsSinceLastPromotion", "YearsWithCurrManager"]) {
      if (n(name) > n("YearsAtCompany")) { setFieldError(name, "Cannot be more than years at company."); ok = false; }
    }
    if (n("YearsAtCompany") > n("TotalWorkingYears")) { setFieldError("TotalWorkingYears", "Cannot be less than years at company."); ok = false; }
    return ok;
  }

  async function loadEmployee(id) {
    idError.textContent = "";
    const res = await fetch(`/api/profile/${encodeURIComponent(id)}`);
    if (!res.ok) { idError.textContent = "No employee with that number."; return false; }
    const profile = await res.json();
    form.Department.value = profile.Department;
    syncRoles(profile.JobRole);
    Object.entries(profile).forEach(([k, v]) => {
      if (k !== "Department" && k !== "JobRole" && form.elements[k]) form.elements[k].value = v;
    });
    form.employee_number.value = id;
    loadedLabel.textContent = `Employee #${id}`;
    clearErrors();
    return true;
  }

  select.addEventListener("change", () => { loadEmployee(select.value).then(() => form.requestSubmit()); });
  document.getElementById("load-employee").addEventListener("click", () => {
    const id = idInput.value.trim();
    if (!/^\d{1,5}$/.test(id)) { idError.textContent = "Enter an employee number."; return; }
    loadEmployee(id).then((ok) => ok && form.requestSubmit());
  });

  function setLoading(loading) {
    result.setAttribute("aria-busy", String(loading));
    button.disabled = loading;
    button.textContent = loading ? "Scoring..." : "Score this employee";
    skeleton.hidden = !loading;
    if (loading) { empty.hidden = true; body.hidden = true; }
  }

  function render(r) {
    const band = r.would_make_top_50 ? "In this cycle's top 50" : r.percentile >= 0.8 ? "Higher than most staff" : "Below watch-list level";
    const scenarios = r.scenarios.length
      ? r.scenarios.map((s) => `
        <tr>
          <th scope="row">${esc(s.label)}<small>${esc(s.cost_note)}</small></th>
          <td class="${s.risk_change_points < -0.5 ? "good" : ""}">${s.risk_change_points > 0 ? "+" : ""}${s.risk_change_points.toFixed(1)} pts</td>
          <td>${money.format(s.cost)}</td>
          <td class="${s.net_value >= 0 ? "good" : "bad"}">${money.format(s.net_value)}</td>
        </tr>`).join("")
      : `<tr><td colspan="4">No standard interventions apply to this profile.</td></tr>`;
    body.innerHTML = `
      <p class="eyebrow">Result</p>
      <div class="result-score">
        <strong>${pct(r.leave_probability)}</strong>
        <span>estimated chance of leaving<br><em>${esc(band)}</em> &middot; riskier than ${(Math.floor(r.percentile * 1000) / 10).toFixed(1)}% of staff</span>
      </div>
      <dl class="result-facts">
        <div><dt>Replacement cost</dt><dd>${money.format(r.replacement_cost)}</dd></div>
        <div><dt>Expected loss</dt><dd>${money.format(r.expected_loss)}</dd></div>
      </dl>
      <p class="dialog-label">Top 3 reasons</p>
      <ol class="reason-list">${r.reasons.map((x) => `<li>${esc(x)}</li>`).join("")}</ol>
      <div class="action-plan">
        <p class="dialog-label">Recommended action</p>
        <strong>${esc(r.primary_action)}</strong>
        <p>${esc(r.recommendation)}</p>
      </div>
      <p class="dialog-label">What-if interventions, best net value first</p>
      <div class="table-shell"><table class="plain-table numeric compact">
        <thead><tr><th scope="col">Intervention</th><th scope="col">Risk change</th><th scope="col">Cost</th><th scope="col">Net value</th></tr></thead>
        <tbody>${scenarios}</tbody>
      </table></div>
      <p class="small-print">Net value = drop in leave probability x replacement cost, minus the intervention cost. This is model sensitivity, not proof of cause.</p>`;
    body.hidden = false;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!validate()) { formError.textContent = "Some fields need attention."; return; }
    const profile = {};
    fields.forEach((f) => { profile[f.name] = f.type === "number" ? Number(f.value) : f.value; });
    setLoading(true);
    try {
      const res = await fetch("/api/score", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ profile, employee_number: form.employee_number.value, website: form.website.value }),
      });
      const data = await res.json();
      if (!res.ok) {
        Object.entries(data.fields || {}).forEach(([k, v]) => setFieldError(k, v));
        formError.textContent = data.error || "Scoring failed.";
        empty.hidden = false;
        return;
      }
      render(data);
    } catch (e) {
      formError.textContent = "Network problem. Check your connection and try again.";
      empty.hidden = false;
    } finally {
      setLoading(false);
    }
  });
})();
