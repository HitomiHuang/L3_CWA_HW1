"use strict";

const $ = (id) => document.getElementById(id);
const state = { data: null, layer: "temperature", city: null, station: null, period: "", search: "", map: null, markerGroup: null };
const labels = { temperature: "最新測站氣溫", humidity: "測站相對濕度", wind: "測站平均風速", forecast: "縣市預報最高溫", rain: "縣市降雨機率" };
const ids = { forecast: "F-C0032-001", weekly: "F-D0047-091", observations: "O-A0001-001" };
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
const num = (value) => value === null || value === undefined || value === "" ? null : (Number.isFinite(Number(value)) ? Number(value) : null);
const fmtNum = (value, unit = "") => num(value) === null ? "—" : Number(num(value).toFixed(1)).toString() + unit;
const rows = (name) => state.data?.[name]?.rows || [];

function fmtTime(value, long = false) {
  const date = new Date(value);
  if (!value || Number.isNaN(date.getTime())) return "—";
  const opts = { timeZone: "Asia/Taipei", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false };
  if (long) opts.year = "numeric";
  return new Intl.DateTimeFormat("zh-TW", opts).format(date);
}
function periodLabel(start, end) { return fmtTime(start) + " – " + fmtTime(end); }
function showNotice(message) {
  const el = $("notice"); el.textContent = message; el.hidden = false;
  clearTimeout(showNotice.timer); showNotice.timer = setTimeout(() => { el.hidden = true; }, 5500);
}
function isForecast() { return state.layer === "forecast" || state.layer === "rain"; }
function currentField() { return ({ temperature: "temperature", humidity: "relative_humidity", wind: "wind_speed", forecast: "max_temp", rain: "pop" })[state.layer]; }
function currentUnit() { return ({ temperature: "°", humidity: "%", wind: "m/s", forecast: "°", rain: "%" })[state.layer]; }
function validStation(row) {
  return Number.isFinite(num(row.latitude)) && Number.isFinite(num(row.longitude))
    && num(row.latitude) > 20 && num(row.latitude) < 27 && num(row.longitude) > 117 && num(row.longitude) < 123;
}
function colorFor(value) {
  const n = num(value);
  if (n === null) return "#748a9b";
  if (state.layer === "humidity" || state.layer === "rain") return n >= 80 ? "#2871c0" : n >= 60 ? "#4f9bd0" : n >= 40 ? "#61b8c7" : n >= 20 ? "#92c6ad" : "#c0c9a0";
  if (state.layer === "wind") return n >= 12 ? "#db735c" : n >= 8 ? "#e8a05e" : n >= 4 ? "#e8cd76" : n >= 2 ? "#89c8be" : "#65a9c5";
  return n >= 35 ? "#d86953" : n >= 30 ? "#ec9557" : n >= 25 ? "#e9bb69" : n >= 20 ? "#77b4c1" : "#5590bf";
}
function legendItems() {
  if (state.layer === "humidity" || state.layer === "rain") return [["<20", "#c0c9a0"], ["20–39", "#92c6ad"], ["40–59", "#61b8c7"], ["60–79", "#4f9bd0"], ["≥80", "#2871c0"]];
  if (state.layer === "wind") return [["<2", "#65a9c5"], ["2–3", "#89c8be"], ["4–7", "#e8cd76"], ["8–11", "#e8a05e"], ["≥12", "#db735c"]];
  return [["<20", "#5590bf"], ["20–24", "#77b4c1"], ["25–29", "#e9bb69"], ["30–34", "#ec9557"], ["≥35", "#d86953"]];
}
function renderLegend() {
  $("legend").innerHTML = '<span class="legend-title">' + escapeHtml(currentUnit()) + '</span>' +
    legendItems().map(([text, color]) => '<span class="legend-item"><i class="legend-dot" style="background:' + color + '"></i>' + escapeHtml(text) + '</span>').join("");
}
function initMap() {
  if (!window.L) { showNotice("地圖元件載入失敗，請檢查網路後重新整理。"); return; }
  state.map = L.map("map", { zoomControl: false, minZoom: 6, maxZoom: 12, preferCanvas: true }).setView([23.78, 120.96], 7);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    subdomains: "abc", maxZoom: 12
  }).addTo(state.map);
  L.control.zoom({ position: "bottomleft" }).addTo(state.map);
  state.markerGroup = L.layerGroup().addTo(state.map);
  state.map.on("zoomend", renderMap);
}
function stationRows() { return rows("observations").filter(validStation); }
function counties() {
  const names = new Set([...rows("forecast").map((r) => r.location), ...stationRows().map((r) => r.county)].filter(Boolean));
  return [...names].sort((a, b) => a.localeCompare(b, "zh-Hant"));
}
function countyStats() {
  const field = currentField(), groups = new Map();
  for (const row of stationRows()) {
    if (!row.county || num(row[field]) === null) continue;
    const group = groups.get(row.county) || { name: row.county, count: 0, sum: 0 };
    group.count++; group.sum += num(row[field]); groups.set(row.county, group);
  }
  return [...groups.values()].map((group) => ({ name: group.name, count: group.count, value: group.sum / group.count }));
}
function forecastPeriods() {
  const map = new Map();
  for (const row of rows("forecast")) map.set(row.start_time + "|" + row.end_time, row);
  return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}
function activeForecastRows() {
  const [start, end] = state.period.split("|");
  return rows("forecast").filter((row) => row.start_time === start && row.end_time === end);
}
function marker(latlng, value, title, kind, onClick) {
  const text = num(value) === null ? "–" : Number(num(value).toFixed(kind === "station" ? 0 : 1)).toString();
  const html = '<div class="weather-marker ' + kind + '" style="background:' + colorFor(value) + '">' + escapeHtml(text) + '</div>';
  const size = kind === "station" ? 27 : 38;
  const icon = L.divIcon({ className: "", html, iconSize: [size, size], iconAnchor: [size / 2, size / 2] });
  const item = L.marker(latlng, { icon, title });
  item.on("click", onClick);
  item.addTo(state.markerGroup);
}
function renderMap() {
  if (!state.map || !state.data) return;
  state.markerGroup.clearLayers();
  const query = state.search.toLocaleLowerCase();
  if (isForecast()) {
    for (const row of activeForecastRows()) {
      if (query && !row.location.toLocaleLowerCase().includes(query)) continue;
      const coord = state.data.coordinates[row.location];
      if (!coord) continue;
      marker(coord, row[currentField()], row.location + " · 縣市預報", "county", () => selectCity(row.location));
    }
  } else if (state.map.getZoom() >= 9 || query) {
    for (const row of stationRows()) {
      if (num(row[currentField()]) === null) continue;
      if (query && !(row.station_name + " " + row.county + " " + row.town).toLocaleLowerCase().includes(query)) continue;
      marker([row.latitude, row.longitude], row[currentField()], row.station_name + " · 測站觀測", "station", () => selectStation(row.station_id));
    }
  } else {
    for (const group of countyStats()) {
      const coord = state.data.coordinates[group.name];
      if (!coord) continue;
      marker(coord, group.value, group.name + " · " + group.count + " 站平均", "county", () => selectCity(group.name));
    }
  }
  $("map-subtitle").textContent = isForecast() ? "縣市代表點 · " + periodLabel(...state.period.split("|")) :
    state.map.getZoom() >= 9 ? "實際測站座標 · 點選圓點查看觀測" : "縣市測站平均 · 放大查看各測站";
}
function renderCities() {
  const field = currentField(), query = state.search.toLocaleLowerCase();
  const stats = new Map(countyStats().map((group) => [group.name, group]));
  const forecast = new Map(activeForecastRows().map((row) => [row.location, row]));
  const list = counties().filter((city) => !query || city.toLocaleLowerCase().includes(query) ||
    stationRows().some((row) => row.county === city && row.station_name.toLocaleLowerCase().includes(query)));
  $("city-count").textContent = list.length + " 縣市";
  $("city-list").innerHTML = list.length ? list.map((city) => {
    const value = isForecast() ? forecast.get(city)?.[field] : stats.get(city)?.value;
    const count = stats.get(city)?.count;
    return '<button class="city-item ' + (state.city === city ? "active" : "") + '" data-city="' + escapeHtml(city) + '" type="button"><span>' +
      escapeHtml(city) + (!isForecast() && count ? '<small>' + count + ' 站</small>' : "") + '</span><strong>' + escapeHtml(fmtNum(value, currentUnit())) + '</strong></button>';
  }).join("") : '<p class="detail-empty">找不到符合的縣市或測站。</p>';
  $("city-list").querySelectorAll("[data-city]").forEach((button) => button.addEventListener("click", () => selectCity(button.dataset.city)));
}
function lineChart(cityRows, field, color) {
  const data = cityRows.slice(0, 12).map((row) => ({ value: num(row[field]), label: fmtTime(row.start_time) }));
  const valid = data.filter((point) => point.value !== null);
  if (!valid.length) return '<p class="detail-sub">目前沒有可繪製的預報數值。</p>';
  const min = field === "pop" ? 0 : Math.floor(Math.min(...valid.map((point) => point.value)) - 3);
  const max = field === "pop" ? 100 : Math.ceil(Math.max(...valid.map((point) => point.value)) + 3);
  const x = (index) => 24 + index * 254 / Math.max(data.length - 1, 1);
  const y = (value) => 95 - (value - min) * 72 / Math.max(max - min, 1);
  let paths = "", segment = [];
  data.forEach((point, index) => {
    if (point.value === null) { if (segment.length) paths += '<polyline points="' + segment.join(" ") + '" fill="none" stroke="' + color + '" stroke-width="2.6"/>'; segment = []; }
    else segment.push(x(index) + "," + y(point.value));
  });
  if (segment.length) paths += '<polyline points="' + segment.join(" ") + '" fill="none" stroke="' + color + '" stroke-width="2.6"/>';
  return '<svg class="chart" viewBox="0 0 300 130" role="img" aria-label="預報趨勢圖"><line x1="24" y1="95" x2="278" y2="95"/><line x1="24" y1="59" x2="278" y2="59"/><line x1="24" y1="23" x2="278" y2="23"/>' +
    paths + '<text x="24" y="119">' + escapeHtml(data[0]?.label || "") + '</text><text x="278" y="119" text-anchor="end">' + escapeHtml(data[data.length - 1]?.label || "") + '</text></svg>';
}
function forecastDetails(city) {
  const current = activeForecastRows().find((row) => row.location === city);
  const cityRows = rows("forecast").filter((row) => row.location === city).sort((a, b) => a.start_time.localeCompare(b.start_time));
  const weekRows = rows("weekly").filter((row) => row.location === city).sort((a, b) => a.start_time.localeCompare(b.start_time));
  let html = '<div class="detail-section-title">今明 36 小時預報</div>';
  if (!current) return html + '<p class="detail-sub">目前沒有這個時段的縣市預報。</p>';
  html += '<div class="detail-row"><span>有效時間</span><strong>' + escapeHtml(periodLabel(current.start_time, current.end_time)) + '</strong></div>' +
    '<div class="detail-row"><span>天氣現象</span><strong>' + escapeHtml(current.wx || "—") + '</strong></div>' +
    '<div class="metric-grid"><div class="mini-metric"><span>預報最低溫</span><strong>' + escapeHtml(fmtNum(current.min_temp, " °C")) + '</strong></div>' +
    '<div class="mini-metric"><span>預報最高溫</span><strong>' + escapeHtml(fmtNum(current.max_temp, " °C")) + '</strong></div>' +
    '<div class="mini-metric"><span>降雨機率</span><strong>' + escapeHtml(fmtNum(current.pop, "%")) + '</strong></div>' +
    '<div class="mini-metric"><span>舒適度</span><strong>' + escapeHtml(current.comfort || "—") + '</strong></div></div>' +
    '<div class="detail-section-title">最高溫趨勢</div>' + lineChart(cityRows, "max_temp", "#db8d57") +
    '<div class="detail-section-title">降雨機率趨勢</div>' + lineChart(cityRows, "pop", "#5298bf");
  if (weekRows.length) {
    html += '<div class="detail-section-title">未來一週 · 前 4 時段</div>' + weekRows.slice(0, 4).map((row) =>
      '<div class="detail-row"><span>' + escapeHtml(fmtTime(row.start_time)) + '</span><strong>' +
      escapeHtml(fmtNum(row.min_temp, "°")) + ' / ' + escapeHtml(fmtNum(row.max_temp, "°")) + ' · 雨 ' + escapeHtml(fmtNum(row.pop, "%")) + '</strong></div>').join("");
  }
  return html;
}
function selectCity(city) {
  state.city = city; state.station = null;
  if (window.innerWidth > 860 && state.map && state.data.coordinates[city]) {
    state.map.flyTo(state.data.coordinates[city], isForecast() ? 8 : 9, { duration: .6 });
  }
  renderCities(); renderDetails();
  closeMenu();
}
function selectStation(id) {
  const row = stationRows().find((item) => item.station_id === id);
  if (!row) return;
  state.station = id; state.city = row.county;
  renderCities(); renderDetails();
  closeMenu();
}
function renderDetails() {
  if (!state.city && !state.station) {
    $("details").classList.remove("open");
    return;
  }
  const city = state.city || "未知縣市";
  const all = stationRows().filter((row) => row.county === city).sort((a, b) => String(b.observed_at).localeCompare(String(a.observed_at)));
  const station = state.station ? all.find((row) => row.station_id === state.station) : null;
  const valid = all.filter((row) => num(row.temperature) !== null);
  $("detail-kicker").textContent = station ? "STATION OBSERVATION" : "COUNTY OVERVIEW";
  let html = '<div class="detail-place">' + escapeHtml(station ? city + " · " + (station.town || "") : "台灣 · 縣市速覽") + '</div>' +
    '<h2 class="detail-heading">' + escapeHtml(station ? station.station_name : city) + '</h2>';
  if (station) {
    html += '<p class="detail-sub">中央氣象署實際測站 · ' + escapeHtml(station.station_id) + '</p>' +
      '<div class="hero-value">' + escapeHtml(fmtNum(station.temperature)) + '<small>°C</small></div><p class="hero-caption">氣溫 · 觀測 ' + escapeHtml(fmtTime(station.observed_at, true)) + '</p>' +
      '<div class="metric-grid"><div class="mini-metric"><span>相對濕度</span><strong>' + escapeHtml(fmtNum(station.relative_humidity, "%")) + '</strong></div>' +
      '<div class="mini-metric"><span>平均風速</span><strong>' + escapeHtml(fmtNum(station.wind_speed, " m/s")) + '</strong></div></div>' +
      '<div class="detail-row"><span>天氣現象</span><strong>' + escapeHtml(station.weather || "—") + '</strong></div>' +
      '<div class="detail-row"><span>觀測時間</span><strong>' + escapeHtml(fmtTime(station.observed_at, true)) + '</strong></div>';
  } else {
    const avg = valid.length ? valid.reduce((sum, row) => sum + num(row.temperature), 0) / valid.length : null;
    html += '<p class="detail-sub">' + all.length + ' 個測站 · ' + valid.length + ' 站有有效氣溫</p>' +
      '<div class="hero-value">' + escapeHtml(fmtNum(avg)) + '<small>°C</small></div><p class="hero-caption">有效測站的算術平均 · 非縣市官方氣溫</p>';
    if (valid.length) {
      const max = [...valid].sort((a, b) => num(b.temperature) - num(a.temperature))[0];
      const min = [...valid].sort((a, b) => num(a.temperature) - num(b.temperature))[0];
      html += '<div class="metric-grid"><div class="mini-metric"><span>最高測站</span><strong>' + escapeHtml(fmtNum(max.temperature, " °C")) + '</strong></div>' +
        '<div class="mini-metric"><span>最低測站</span><strong>' + escapeHtml(fmtNum(min.temperature, " °C")) + '</strong></div></div>';
    }
    html += '<div class="detail-section-title">測站列表</div><div class="station-list">' +
      all.slice(0, 20).map((row) => '<button class="station-button" data-station="' + escapeHtml(row.station_id) + '" type="button"><span>' +
      escapeHtml(row.station_name) + '</span><strong>' + escapeHtml(fmtNum(row.temperature, " °C")) + '</strong></button>').join("") +
      (all.length ? "" : '<p class="detail-sub">此縣市目前沒有測站觀測。</p>') + '</div>';
  }
  html += forecastDetails(city) +
    '<p class="detail-foot">測站觀測抓取：' + escapeHtml(fmtTime(state.data.observations.fetched_at, true)) +
    '<br>36 小時預報抓取：' + escapeHtml(fmtTime(state.data.forecast.fetched_at, true)) + '</p>';
  $("details-content").innerHTML = html;
  $("details").classList.add("open");
  $("details-content").querySelectorAll("[data-station]").forEach((button) => button.addEventListener("click", () => selectStation(button.dataset.station)));
}
function closeMenu() {
  $("sidebar").classList.remove("open");
  document.body.classList.remove("menu-open");
}
function closeDetails() {
  state.station = null;
  state.city = null;
  $("details").classList.remove("open");
  $("details-content").innerHTML = '<div class="detail-empty">選取地圖上的測站或左側縣市，查看詳細天氣與預報。</div>';
  if (state.data) renderCities();
}
function renderDataDialog() {
  $("source-summary").innerHTML = Object.entries(ids).map(([name, id]) => {
    const title = ({ forecast: "36 小時預報", weekly: "一週預報", observations: "測站觀測" })[name];
    const data = state.data[name];
    return '<div class="source-row"><span>' + escapeHtml(title + " · " + id) + '</span><strong>' + escapeHtml(data.count + " 筆 · " + fmtTime(data.fetched_at)) + '</strong></div>';
  }).join("");
  $("crawl-log").innerHTML = (state.data.crawl_runs || []).map((run) =>
    '<div class="crawl-row ' + escapeHtml(run.status) + '"><span>' + escapeHtml(run.dataset_id + " · " + fmtTime(run.finished_at)) +
    '</span><strong>' + escapeHtml(run.status === "success" ? "成功 · " + run.record_count + " 筆" : "失敗 · " + (run.error_message || "未知錯誤")) + '</strong></div>').join("") || '<p>尚無爬蟲紀錄。</p>';
}
function renderControls() {
  document.querySelectorAll(".layer-button").forEach((button) => button.classList.toggle("active", button.dataset.layer === state.layer));
  $("map-title").textContent = labels[state.layer];
  const times = forecastPeriods();
  if (!times.some(([key]) => key === state.period)) state.period = times[0]?.[0] || "";
  $("period-control").hidden = !isForecast();
  $("period-select").innerHTML = times.map(([key, row]) =>
    '<option value="' + escapeHtml(key) + '">' + escapeHtml(periodLabel(row.start_time, row.end_time)) + '</option>').join("");
  $("period-select").value = state.period;
  $("dock-title").textContent = isForecast() ? "預報有效時段" : "最新測站觀測";
  $("dock-time").textContent = isForecast() ? fmtTime(state.data.forecast.fetched_at, true) + " 抓取" :
    fmtTime(state.data.observations.fetched_at, true) + " 抓取";
  const source = isForecast() ? state.data.forecast : state.data.observations;
  const age = source.fetched_at ? Date.now() - new Date(source.fetched_at).getTime() : Infinity;
  $("freshness").textContent = age < 2 * 3600000 ? "資料抓取 " + fmtTime(source.fetched_at) :
    "快照時間 " + fmtTime(source.fetched_at) + (age > 12 * 3600000 ? " · 資料較舊" : "");
  document.querySelector(".status-dot").classList.toggle("stale", age > 12 * 3600000);
  renderLegend(); renderCities(); renderMap(); renderDetails(); renderDataDialog();
}
function csvValue(value) { return '"' + String(value ?? "").replace(/"/g, '""') + '"'; }
function downloadCsv() {
  const data = isForecast() ? activeForecastRows() : stationRows();
  const fields = isForecast() ? ["location", "start_time", "end_time", "wx", "min_temp", "max_temp", "pop"] :
    ["station_id", "station_name", "county", "town", "observed_at", "temperature", "relative_humidity", "wind_speed"];
  const content = "\uFEFF" + fields.join(",") + "\r\n" + data.map((row) => fields.map((field) => csvValue(row[field])).join(",")).join("\r\n");
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
  link.download = "taiwan-weather-" + (isForecast() ? "forecast" : "observations") + ".csv";
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}
async function loadData() {
  $("refresh").disabled = true;
  try {
    const response = await fetch("/data/snapshot.json?ts=" + Date.now(), { cache: "no-store" });
    if (!response.ok) throw new Error("找不到資料快照（HTTP " + response.status + "）");
    const data = await response.json();
    if (!data || data.schema_version !== 1 || !data.observations || !Array.isArray(data.observations.rows)) throw new Error("資料快照格式錯誤");
    state.data = data;
    renderControls();
    if (!data.observations.count) showNotice("尚無測站資料。請先在本機執行 python scripts/fetch_once.py --all。");
  } catch (error) { showNotice(error.message + "；請先執行爬蟲並匯出 JSON。"); }
  finally { $("refresh").disabled = false; }
}
document.querySelectorAll(".layer-button").forEach((button) => button.addEventListener("click", () => {
  state.layer = button.dataset.layer; state.station = null; if (state.data) renderControls(); closeMenu();
}));
$("search").addEventListener("input", (event) => { state.search = event.target.value.trim(); if (state.data) { renderCities(); renderMap(); } });
$("period-select").addEventListener("change", (event) => { state.period = event.target.value; renderControls(); });
$("zoom-home").addEventListener("click", () => state.map?.flyTo([23.78, 120.96], 7));
$("download").addEventListener("click", downloadCsv);
$("refresh").addEventListener("click", loadData);
$("data-button").addEventListener("click", () => $("data-dialog").showModal());
$("detail-close").addEventListener("click", closeDetails);
$("menu-toggle").addEventListener("click", () => { closeDetails(); $("sidebar").classList.add("open"); document.body.classList.add("menu-open"); });
$("menu-close").addEventListener("click", closeMenu);
initMap();
loadData();
