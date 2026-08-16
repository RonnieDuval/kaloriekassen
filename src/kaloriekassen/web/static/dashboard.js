const state = {
  days: Number(document.body.dataset.defaultDays || 30),
  payload: null,
  selectedDate: null,
};

const numberFormat = new Intl.NumberFormat("da-DK", { maximumFractionDigits: 0 });
const decimalFormat = new Intl.NumberFormat("da-DK", { maximumFractionDigits: 1 });
const dateFormat = new Intl.DateTimeFormat("da-DK", {
  weekday: "short",
  day: "numeric",
  month: "short",
});
const longDateFormat = new Intl.DateTimeFormat("da-DK", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
});

function el(id) { return document.getElementById(id); }
function number(value, suffix = "") {
  return value === null || value === undefined ? "—" : `${numberFormat.format(value)}${suffix}`;
}
function decimal(value, suffix = "") {
  return value === null || value === undefined ? "—" : `${decimalFormat.format(value)}${suffix}`;
}
function civilDate(value) { return new Date(`${value}T12:00:00`); }
function localToday() {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
function formatDate(value, formatter = dateFormat) { return formatter.format(civilDate(value)); }
function formatDateTime(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("da-DK", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  }).format(new Date(value));
}
function escapeText(value) {
  const span = document.createElement("span");
  span.textContent = value ?? "";
  return span.innerHTML;
}

async function fetchJson(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

function setHealth(mode, text) {
  const indicator = el("health-indicator");
  indicator.classList.remove("healthy", "error");
  if (mode) indicator.classList.add(mode);
  el("health-text").textContent = text;
}

function showError(message) {
  const banner = el("error-banner");
  banner.textContent = message;
  banner.hidden = false;
  setHealth("error", "Datafejl");
}

function hideError() { el("error-banner").hidden = true; }

function renderMetrics(day, measurement) {
  const isCurrentDay = day?.date === localToday();
  const missingGoogleDaily = day?.estimated_tdee_kcal == null;
  const balance = day?.estimated_energy_balance_kcal;
  const balanceElement = el("metric-balance");
  balanceElement.textContent = number(balance, " kcal");
  balanceElement.classList.toggle("positive", balance > 0);
  balanceElement.classList.toggle("negative", balance < 0);

  el("metric-intake").textContent = number(day?.calories_in, " kcal");
  el("metric-tdee").textContent = number(day?.estimated_tdee_kcal, " kcal");
  el("metric-tdee-note").textContent = missingGoogleDaily
    ? (isCurrentDay ? "Afventer næste 15-minutters synk" : "Google-dagssum mangler")
    : (isCurrentDay ? "Foreløbig Google totalenergi" : "Google totalenergi");
  el("metric-bmr").textContent = number(day?.basal_energy_kcal, " kcal");
  el("metric-steps").textContent = number(day?.steps);
  el("metric-step-energy").textContent = day?.steps == null
    ? (isCurrentDay ? "Afventer næste 15-minutters synk" : "Google-dagssum mangler")
    : `${number(day.step_energy_estimated_kcal, " kcal")} estimeret${isCurrentDay ? " · foreløbig" : ""}`;
  el("metric-balance-note").textContent = balance == null
    ? (isCurrentDay ? "Beregnes ved næste 15-minutters synk" : "Kan ikke beregnes uden TDEE")
    : (isCurrentDay ? "Foreløbig: indtag minus TDEE" : "Indtag minus TDEE");
  el("metric-exercise").textContent = number(day?.exercise_energy_kcal, " kcal");

  const weight = day?.weight_kg ?? measurement?.weight_kg;
  const bodyFat = day?.body_fat_pct ?? measurement?.body_fat_pct;
  el("metric-weight").textContent = decimal(weight, " kg");
  el("metric-body-fat").textContent = bodyFat == null
    ? "Seneste måling"
    : `${decimal(bodyFat, " %")} fedt`;

  if (day?.date) {
    el("selected-date-heading").textContent = formatDate(day.date, longDateFormat);
    const dayState = el("day-state");
    dayState.hidden = false;
    const isComplete = day.data_completeness === "complete" && !isCurrentDay;
    dayState.className = `day-state ${isComplete ? "complete" : "partial"}`;
    dayState.textContent = isCurrentDay
      ? "Foreløbige tal"
      : (isComplete ? "Komplet dag" : "Ufuldstændig dag");
    const completeness = {
      complete: "Kost og energiforbrug er komplette for dagen.",
      missing_intake: "Kalorieindtag mangler for dagen.",
      missing_expenditure: "Energiforbrug mangler for dagen.",
      missing_intake_and_expenditure: "Kost og energiforbrug mangler for dagen.",
    };
    el("completeness-copy").textContent = isCurrentDay
      ? (missingGoogleDaily
        ? "Afventer dagens første Google-snapshot. Derefter opdateres skridt, TDEE og energibalance hvert 15. minut."
        : "Skridt, TDEE og energibalance er foreløbige og opdateres fra Google hvert 15. minut.")
      : (completeness[day.data_completeness]
        || "Samler kost, bevægelse, træning og kropsmålinger.");
  }
}

function svgElement(name, attributes = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
  return node;
}

function renderLineChart(container, points, series, options = {}) {
  container.replaceChildren();
  const available = points.flatMap((point) => series
    .map((item) => point[item.key])
    .filter((value) => Number.isFinite(value)));
  if (!available.length) {
    const empty = document.createElement("div");
    empty.className = "chart-empty";
    empty.textContent = "Ingen målinger i den valgte periode";
    container.append(empty);
    return;
  }

  const width = 900;
  const height = 300;
  const pad = { top: 18, right: 18, bottom: 35, left: 58 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  let minimum = Math.min(...available);
  let maximum = Math.max(...available);
  if (options.includeZero !== false) {
    minimum = Math.min(0, minimum);
    maximum = Math.max(0, maximum);
  }
  const margin = Math.max((maximum - minimum) * 0.08, options.minimumMargin || 1);
  minimum -= margin;
  maximum += margin;
  const spread = maximum - minimum || 1;
  const x = (index) => pad.left + (points.length === 1 ? plotWidth / 2 : index * plotWidth / (points.length - 1));
  const y = (value) => pad.top + (maximum - value) * plotHeight / spread;

  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, role: "img" });
  for (let line = 0; line <= 4; line += 1) {
    const lineY = pad.top + line * plotHeight / 4;
    svg.append(svgElement("line", { x1: pad.left, y1: lineY, x2: width - pad.right, y2: lineY, class: "chart-grid-line" }));
    const label = svgElement("text", { x: pad.left - 10, y: lineY + 4, "text-anchor": "end", class: "chart-label" });
    label.textContent = number(maximum - line * spread / 4);
    svg.append(label);
  }
  if (minimum < 0 && maximum > 0) {
    svg.append(svgElement("line", { x1: pad.left, y1: y(0), x2: width - pad.right, y2: y(0), class: "chart-zero-line" }));
  }

  const labelIndexes = [...new Set([0, Math.floor((points.length - 1) / 2), points.length - 1])];
  labelIndexes.forEach((index) => {
    if (!points[index]) return;
    const label = svgElement("text", { x: x(index), y: height - 8, "text-anchor": index === 0 ? "start" : index === points.length - 1 ? "end" : "middle", class: "chart-label" });
    label.textContent = formatDate(points[index].date || points[index].measured_at.slice(0, 10));
    svg.append(label);
  });

  series.forEach((item) => {
    const valid = points.map((point, index) => ({ value: point[item.key], index }))
      .filter((point) => Number.isFinite(point.value));
    if (!valid.length) return;
    const path = valid.map((point, index) => `${index === 0 ? "M" : "L"}${x(point.index).toFixed(2)},${y(point.value).toFixed(2)}`).join(" ");
    svg.append(svgElement("path", { d: path, fill: "none", stroke: item.color, "stroke-width": item.width || 2.4, "stroke-linecap": "round", "stroke-linejoin": "round", opacity: item.opacity || 1 }));
    valid.forEach((point) => {
      const circle = svgElement("circle", { cx: x(point.index), cy: y(point.value), r: 3.2, fill: item.color, stroke: "#10201d", "stroke-width": 2 });
      const title = svgElement("title");
      title.textContent = `${item.label}: ${decimal(point.value)} · ${points[point.index].date || points[point.index].measured_at.slice(0, 10)}`;
      circle.append(title);
      svg.append(circle);
    });
  });
  container.append(svg);
}

function renderDailyTable(daily) {
  const body = el("daily-table-body");
  body.replaceChildren();
  [...daily].reverse().slice(0, 16).forEach((day) => {
    const row = document.createElement("tr");
    row.dataset.date = day.date;
    if (day.date === state.selectedDate) row.classList.add("selected");
    const balanceClass = day.estimated_energy_balance_kcal > 0 ? "balance-positive" : "balance-negative";
    row.innerHTML = `
      <td>${escapeText(formatDate(day.date))}</td>
      <td>${escapeText(number(day.calories_in))}</td>
      <td>${escapeText(number(day.estimated_tdee_kcal))}</td>
      <td class="${balanceClass}">${escapeText(number(day.estimated_energy_balance_kcal))}</td>
      <td>${escapeText(number(day.steps))}</td>
      <td>${escapeText(decimal(day.weight_kg))}</td>`;
    row.addEventListener("click", () => selectDay(day.date));
    body.append(row);
  });
}

function renderActivities(activities) {
  const list = el("activity-list");
  list.replaceChildren();
  if (!activities.length) {
    list.innerHTML = '<div class="empty-state">Ingen aktiviteter</div>';
    return;
  }
  activities.slice(0, 8).forEach((activity) => {
    const item = document.createElement("div");
    item.className = "stack-item";
    const distance = activity.distance_meters == null ? "" : ` · ${decimal(activity.distance_meters / 1000, " km")}`;
    item.innerHTML = `
      <div><strong>${escapeText(activity.activity_type || "Aktivitet")}</strong>
      <small>${escapeText(formatDateTime(activity.started_at))}${escapeText(distance)}</small></div>
      <div class="stack-value">${escapeText(number(activity.calories_out, " kcal"))}</div>`;
    list.append(item);
  });
}

function renderSyncJobs(jobs) {
  const metadata = {
    intervals: ["Hvert 30. minut", "Træning og aktivitetskalorier"],
    myfitnesspal: ["Hver 3. time", "Mad og kalorieindtag"],
    "google-health-read": ["Hver 6. time", "Kopi af Google-træninger"],
    "google-health-daily": ["Hver 6. time", "Skridt, aktiv energi og TDEE for afsluttede dage"],
    "google-health-today": ["Hvert 15. minut", "Foreløbige skridt, aktiv energi og TDEE for i dag"],
    withings: ["Hver 6. time", "Vægt og kropssammensætning"],
    "google-health-export": ["Med Intervals hvert 30. minut", "Nye Intervals-træninger til Google"],
    "google-health-heart-rate-backfill": ["Engangskørsel", "Historisk gennemsnitspuls"],
  };
  const list = el("sync-list");
  list.replaceChildren();
  jobs.forEach((job) => {
    const [cadence, contents] = metadata[job.job] || ["Efter konfiguration", job.source];
    const item = document.createElement("div");
    item.className = "stack-item";
    item.innerHTML = `
      <div><strong>${escapeText(job.job)}</strong>
      <small>${escapeText(cadence)} · ${escapeText(contents)}</small>
      <small>Senest ${escapeText(formatDateTime(job.completed_at))} · ${escapeText(number(job.stored_count))} gemt</small></div>
      <span class="status-pill ${job.status === "success" ? "success" : "failed"}">${job.status === "success" ? "OK" : "Fejl"}</span>`;
    list.append(item);
  });
}

function renderDayDetail(payload) {
  const container = el("day-detail");
  el("day-panel-title").textContent = formatDate(payload.date, longDateFormat);
  container.className = "day-detail";
  container.replaceChildren();

  const groups = new Map();
  payload.nutrition_entries.forEach((entry) => {
    const key = entry.source_meal_name || entry.meal_type;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(entry);
  });
  if (!groups.size) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "Ingen måltider registreret";
    container.append(empty);
  } else {
    groups.forEach((entries, name) => {
      const group = document.createElement("section");
      group.className = "meal-group";
      const calories = entries.reduce((total, entry) => total + (entry.calories || 0), 0);
      group.innerHTML = `<div class="meal-title"><strong>${escapeText(name)}</strong><span>${escapeText(number(calories, " kcal"))}</span></div>`;
      entries.forEach((entry) => {
        const row = document.createElement("div");
        row.className = "food-row";
        row.innerHTML = `<span>${escapeText(entry.food_name)}</span><span>${escapeText(number(entry.calories, " kcal"))}</span>`;
        group.append(row);
      });
      container.append(group);
    });
  }

  payload.activities.forEach((activity) => {
    const card = document.createElement("div");
    card.className = "day-activity";
    card.innerHTML = `<strong>${escapeText(activity.activity_type || "Aktivitet")}</strong><br><span class="muted">${escapeText(number(activity.calories_out, " kcal"))} · ${escapeText(decimal((activity.elapsed_time_seconds || 0) / 60, " min"))}</span>`;
    container.append(card);
  });
}

async function selectDay(day) {
  state.selectedDate = day;
  renderDailyTable(state.payload.daily);
  const summary = state.payload.daily.find((item) => item.date === day);
  renderMetrics(summary, state.payload.measurements.at(-1));
  el("day-detail").className = "day-detail empty-state";
  el("day-detail").textContent = "Henter dagens detaljer …";
  try {
    renderDayDetail(await fetchJson(`/api/days/${day}`));
  } catch (error) {
    el("day-detail").textContent = error.message;
  }
}

function renderDashboard(payload) {
  state.payload = payload;
  const latest = payload.daily.at(-1);
  state.selectedDate = latest?.date || null;
  renderMetrics(latest, payload.measurements.at(-1));
  renderLineChart(el("energy-chart"), payload.daily, [
    { key: "calories_in", label: "Indtag", color: "#55e6a5" },
    { key: "estimated_tdee_kcal", label: "TDEE", color: "#5dc9dd" },
    { key: "estimated_energy_balance_kcal", label: "Balance", color: "#f2b76d", width: 2, opacity: 0.86 },
  ]);
  renderLineChart(el("weight-chart"), payload.measurements, [
    { key: "weight_kg", label: "Vægt", color: "#55e6a5" },
  ], { includeZero: false, minimumMargin: 0.5 });
  renderDailyTable(payload.daily);
  renderActivities(payload.activities);
  renderSyncJobs(payload.sync_jobs);
  el("updated-at").textContent = `Opdateret ${formatDateTime(payload.generated_at)}`;
  setHealth("healthy", "Synkronisering OK");
  if (latest?.date) selectDay(latest.date);
}

async function loadDashboard(days) {
  hideError();
  setHealth("", "Henter data");
  try {
    renderDashboard(await fetchJson(`/api/dashboard?days=${days}`));
  } catch (error) {
    showError(`Dashboardet kunne ikke hente data: ${error.message}`);
  }
}

document.querySelectorAll("[data-days]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-days]").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.days = Number(button.dataset.days);
    loadDashboard(state.days);
  });
});

loadDashboard(state.days);
