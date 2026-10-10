const watchlist = JSON.parse(document.getElementById("watchlist-data").textContent);
const byEmployee = new Map(watchlist.map((record) => [String(Math.trunc(record.EmployeeNumber)), record]));

const search = document.getElementById("search");
const department = document.getElementById("department-filter");
const band = document.getElementById("band-filter");
const rows = [...document.querySelectorAll("#watchlist-table tbody tr")];
const visibleCount = document.getElementById("visible-count");
const emptyState = document.getElementById("empty-state");

function applyFilters() {
  const query = search.value.trim().toLowerCase();
  let count = 0;
  rows.forEach((row) => {
    const matchesSearch = !query || row.dataset.search.toLowerCase().includes(query);
    const matchesDepartment = !department.value || row.dataset.department === department.value;
    const matchesBand = !band.value || row.dataset.band === band.value;
    const visible = matchesSearch && matchesDepartment && matchesBand;
    row.hidden = !visible;
    if (visible) count += 1;
  });
  visibleCount.textContent = String(count);
  emptyState.hidden = count !== 0;
}

[search, department, band].forEach((control) => control.addEventListener("input", applyFilters));

const dialog = document.getElementById("employee-dialog");
const dialogTitle = document.getElementById("dialog-title");
const dialogContent = document.getElementById("dialog-content");

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function openEmployee(employeeNumber) {
  const record = byEmployee.get(String(employeeNumber));
  if (!record) return;
  dialogTitle.textContent = `Employee ${Math.trunc(record.EmployeeNumber)}`;
  const reasons = [record.RiskReason1, record.RiskReason2, record.RiskReason3];
  dialogContent.innerHTML = `
    <div class="dialog-summary">
      <div><span>Rank</span><strong>#${String(Math.trunc(record.Rank)).padStart(2, "0")}</strong></div>
      <div><span>Risk score</span><strong>${Math.round(record.RiskScore * 100)}%</strong></div>
      <div><span>Historical outcome</span><strong>${escapeHtml(record.HistoricalOutcome)}</strong></div>
    </div>
    <div class="dialog-role">
      <span>${escapeHtml(record.Department)}</span>
      <h3>${escapeHtml(record.JobRole)}</h3>
      <p>${Math.trunc(record.YearsAtCompany)} years at company · ${Math.trunc(record.YearsInCurrentRole)} years in role · Overtime: ${escapeHtml(record.OverTime)}</p>
    </div>
    <div class="dialog-section">
      <p class="dialog-label">Leading risk drivers</p>
      <ol class="reason-list">${reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}</ol>
    </div>
    <div class="dialog-section action-plan">
      <p class="dialog-label">Recommended intervention</p>
      <strong>${escapeHtml(record.PrimaryAction)}</strong>
      <p>${escapeHtml(record.Recommendation)}</p>
    </div>
    <p class="dialog-disclaimer">Use as discussion support. Confirm the context with the employee and a qualified HR reviewer before taking action.</p>
  `;
  dialog.showModal();
}

document.querySelectorAll("[data-employee]").forEach((button) => {
  button.addEventListener("click", () => openEmployee(button.dataset.employee));
});

document.getElementById("dialog-close").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", (event) => {
  const bounds = dialog.getBoundingClientRect();
  const outside = event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom;
  if (outside) dialog.close();
});
