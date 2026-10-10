const watchlist = JSON.parse(document.getElementById("watchlist-data").textContent);
const byEmployee = new Map(
  watchlist.map((record) => [String(Math.trunc(record.EmployeeNumber)), record]),
);

const search = document.getElementById("search");
const capacity = document.getElementById("capacity-filter");
const department = document.getElementById("department-filter");
const band = document.getElementById("band-filter");
const rows = [...document.querySelectorAll("#watchlist-table tbody tr")];
const visibleCount = document.getElementById("visible-count");
const emptyState = document.getElementById("empty-state");
const heroCapacity = document.getElementById("hero-capacity");
const statusStorageKey = "talentguard-demo-intervention-status";
const allowedStatuses = [
  "Not reviewed",
  "Reviewed",
  "Intervention planned",
  "Follow-up scheduled",
];

function formatCompactNumber(value) {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

function updateScenario(visibleRows) {
  const employees = visibleRows.length;
  const exits = visibleRows.filter((row) => row.dataset.outcome === "Yes").length;
  const precision = employees ? exits / employees : 0;
  const costExposure = visibleRows.reduce((total, row) => {
    const monthlyIncome = Number(row.dataset.monthlyIncome);
    return total + (Number.isFinite(monthlyIncome) ? monthlyIncome * 6 : 0);
  }, 0);

  document.getElementById("scenario-employees").textContent = String(employees);
  document.getElementById("scenario-exits").textContent = String(exits);
  document.getElementById("scenario-precision").textContent = `${Math.round(precision * 100)}%`;
  document.getElementById("scenario-cost").textContent = `${formatCompactNumber(costExposure)} units`;
  heroCapacity.textContent = String(employees);
}

function applyFilters() {
  const query = search.value.trim().toLowerCase();
  const capacityLimit = Number(capacity.value);
  const visibleRows = [];

  rows.forEach((row) => {
    const matchesSearch = !query || row.dataset.search.toLowerCase().includes(query);
    const matchesCapacity = Number(row.dataset.rank) <= capacityLimit;
    const matchesDepartment = !department.value || row.dataset.department === department.value;
    const matchesBand = !band.value || row.dataset.band === band.value;
    const visible = matchesSearch && matchesCapacity && matchesDepartment && matchesBand;
    row.hidden = !visible;
    if (visible) visibleRows.push(row);
  });

  visibleCount.textContent = String(visibleRows.length);
  emptyState.hidden = visibleRows.length !== 0;
  updateScenario(visibleRows);
}

[search, capacity, department, band].forEach((control) =>
  control.addEventListener("input", applyFilters),
);

const dialog = document.getElementById("employee-dialog");
const dialogTitle = document.getElementById("dialog-title");
const dialogContent = document.getElementById("dialog-content");
let activeEmployeeNumber = null;

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function loadStatuses() {
  try {
    const parsed = JSON.parse(localStorage.getItem(statusStorageKey) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function statusFor(employeeNumber) {
  const saved = loadStatuses()[String(employeeNumber)];
  return allowedStatuses.includes(saved) ? saved : "Not reviewed";
}

function saveStatus(employeeNumber, status) {
  if (!allowedStatuses.includes(status)) return;
  const statuses = loadStatuses();
  if (status === "Not reviewed") {
    delete statuses[String(employeeNumber)];
  } else {
    statuses[String(employeeNumber)] = status;
  }
  try {
    localStorage.setItem(statusStorageKey, JSON.stringify(statuses));
  } catch {
    // The demo still works when browser storage is unavailable.
  }
}

function renderEmployee(record) {
  const employeeNumber = Math.trunc(record.EmployeeNumber);
  const currentStatus = statusFor(employeeNumber);
  dialogTitle.textContent = `Employee ${employeeNumber}`;
  const reasons = [record.RiskReason1, record.RiskReason2, record.RiskReason3];
  const statusButtons = allowedStatuses
    .map(
      (status) =>
        `<button class="status-button" type="button" data-review-status="${escapeHtml(status)}" aria-pressed="${status === currentStatus}">${escapeHtml(status)}</button>`,
    )
    .join("");

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
    <div class="status-panel">
      <div><p class="dialog-label">Demo intervention state</p><span class="status-pill">${escapeHtml(currentStatus)}</span></div>
      <div class="status-actions">${statusButtons}</div>
      <p class="demo-state-note">Saved only in this browser for the hackathon demonstration.</p>
    </div>
    <p class="dialog-disclaimer">Use as discussion support. Confirm the context with the employee and a qualified HR reviewer before taking action.</p>
  `;
}

function openEmployee(employeeNumber) {
  const record = byEmployee.get(String(employeeNumber));
  if (!record) return;
  activeEmployeeNumber = String(employeeNumber);
  renderEmployee(record);
  if (!dialog.open) dialog.showModal();
}

document.querySelectorAll("[data-employee]").forEach((button) => {
  button.addEventListener("click", () => openEmployee(button.dataset.employee));
});

dialogContent.addEventListener("click", (event) => {
  const button = event.target.closest("[data-review-status]");
  if (!button || !activeEmployeeNumber) return;
  saveStatus(activeEmployeeNumber, button.dataset.reviewStatus);
  renderEmployee(byEmployee.get(activeEmployeeNumber));
});

document.getElementById("dialog-close").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", (event) => {
  const bounds = dialog.getBoundingClientRect();
  const outside =
    event.clientX < bounds.left ||
    event.clientX > bounds.right ||
    event.clientY < bounds.top ||
    event.clientY > bounds.bottom;
  if (outside) dialog.close();
});

applyFilters();
