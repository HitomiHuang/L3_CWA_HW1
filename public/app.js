"use strict";

const $ = (id) => document.getElementById(id);
const query = new URLSearchParams(location.search);
const allowedLayers = new Set(["temperature", "humidity", "wind", "forecast", "rain"]);
const state = { data: null, layer: allowedLayers.has(query.get("layer")) ? query.get("layer") : "temperature", basemap: "dark",
  forecastLayer: ["forecast", "rain"].includes(query.get("layer")) ? query.get("layer") : "forecast",
  city: query.get("city"), station: null, detailsOpen: false, period: query.get("period") || "", search: "",
  map: null, streetLayer: null, countyLayer: null, countyGeoJson: null, markerGroup: null,
  typhoonGroup: null, typhoonNodes: [], typhoonVisible: false, favorites: readFavorites() };
const labels = { temperature: "最新測站氣溫", humidity: "測站相對濕度", wind: "測站平均風速", forecast: "縣市預報最高溫", rain: "縣市降雨機率" };
const ids = { forecast: "F-C0032-001", weekly: "F-D0047-091", observations: "O-A0001-001", typhoons: "W-C0034-005" };
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
const num = (value) => value === null || value === undefined || value === "" ? null : (Number.isFinite(Number(value)) ? Number(value) : null);
const fmtNum = (value, unit = "") => num(value) === null ? "—" : Number(num(value).toFixed(1)).toString() + unit;
const rows = (name) => state.data?.[name]?.rows || [];

function readFavorites() {
  try {
    const value = JSON.parse(localStorage.getItem("weather-favorite-counties") || "[]");
    return Array.isArray(value) ? value.filter((name) => typeof name === "string").slice(0, 8) : [];
  } catch { return []; }
}
function updateUrl() {
  const url = new URL(location.href);
  if (state.city) url.searchParams.set("city", state.city); else url.searchParams.delete("city");
  if (state.layer !== "temperature") url.searchParams.set("layer", state.layer); else url.searchParams.delete("layer");
  if (isForecast() && state.period) url.searchParams.set("period", state.period); else url.searchParams.delete("period");
  history.replaceState(null, "", url);
}
function renderFavorites() {
  state.favorites = state.favorites.filter((city) => counties().includes(city));
  $("favorite-wrap").hidden = !state.favorites.length;
  $("favorite-list").innerHTML = state.favorites.map((city) =>
    '<button type="button" data-favorite="' + escapeHtml(city) + '">' + escapeHtml(city) + '</button>').join("");
  $("favorite-list").querySelectorAll("[data-favorite]").forEach((button) =>
    button.addEventListener("click", () => selectCity(button.dataset.favorite)));
}
function setCityBrowserOpen(open) {
  $("city-browser").classList.toggle("open", open);
  $("city-browser-content").hidden = !open;
  $("city-toggle").setAttribute("aria-expanded", String(open));
}
function toggleFavorite() {
  if (!state.city) return;
  state.favorites = state.favorites.includes(state.city) ? state.favorites.filter((city) => city !== state.city) :
    [...state.favorites, state.city].slice(-8);
  try { localStorage.setItem("weather-favorite-counties", JSON.stringify(state.favorites)); } catch { /* Private mode may block storage. */ }
  renderFavorites(); renderOverview();
}

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
  if (state.typhoonVisible) {
    $("legend").innerHTML = '<span class="legend-item"><i class="legend-route observed"></i>分析路徑</span>' +
      '<span class="legend-item"><i class="legend-route predicted"></i>預報路徑</span>' +
      '<span class="legend-item">圖示大小＝最大風速，非暴風圈範圍</span>';
    return;
  }
  $("legend").innerHTML = '<span class="legend-title">' + escapeHtml(currentUnit()) + '</span>' +
    legendItems().map(([text, color]) => '<span class="legend-item"><i class="legend-dot" style="background:' + color + '"></i>' + escapeHtml(text) + '</span>').join("");
}
function initMap() {
  if (!window.L) { showNotice("地圖元件載入失敗，請檢查網路後重新整理。"); return; }
  state.map = L.map("map", { zoomControl: false, minZoom: 4, maxZoom: 12, preferCanvas: true }).setView([23.78, 120.96], 8);
  state.streetLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    subdomains: "abc", maxZoom: 12
  });
  L.control.zoom({ position: "topright" }).addTo(state.map);
  state.markerGroup = L.layerGroup().addTo(state.map);
  state.typhoonGroup = L.layerGroup().addTo(state.map);
  state.map.on("zoomend", renderMap);
  state.map.on("moveend zoomend", layoutTyphoonLabels);
  loadCountyGeometry();
}
function normalizeCounty(name) { return String(name || "").replaceAll("臺", "台"); }
function countyValues() {
  const values = isForecast() ? activeForecastRows().map((row) => ({ name: row.location, value: row[currentField()] })) : countyStats();
  return new Map(values.map((row) => [normalizeCounty(row.name), row.value]));
}
function renderCountyAreas() {
  if (!state.map || !state.countyGeoJson) return;
  if (state.countyLayer) state.map.removeLayer(state.countyLayer);
  const values = state.data ? countyValues() : new Map();
  const names = new Map(state.data ? counties().map((name) => [normalizeCounty(name), name]) : []);
  state.countyLayer = L.geoJSON(state.countyGeoJson, {
    attribution: '縣市界線：<a href="https://github.com/dkaoster/taiwan-atlas">taiwan-atlas</a>／內政部國土測繪中心',
    style: (feature) => {
      const county = normalizeCounty(feature.properties.COUNTYNAME);
      if (state.typhoonVisible) return { color: "#7996a5", weight: 1, fillColor: "#527387", fillOpacity: .18, opacity: .55 };
      const value = values.get(county);
      return { color: county === normalizeCounty(state.city) ? "#eff8fb" : "#9bb9c9", weight: county === normalizeCounty(state.city) ? 2 : 1,
        fillColor: value === undefined ? "#527387" : colorFor(value), fillOpacity: value === undefined ? .52 : .66, opacity: .65 };
    },
    onEachFeature: (feature, layer) => {
      const name = names.get(normalizeCounty(feature.properties.COUNTYNAME));
      if (name) {
        layer.bindTooltip(() => {
          const value = values.get(normalizeCounty(name));
          return '<strong>' + escapeHtml(name) + '</strong>' +
            (state.typhoonVisible ? '' : '<span>' + escapeHtml(fmtNum(value, currentUnit())) + '</span>');
        }, { className: "county-tooltip", direction: "top", sticky: true });
        layer.on("click", () => selectCity(name));
      }
    }
  });
  if (state.basemap === "dark") state.countyLayer.addTo(state.map);
}
async function loadCountyGeometry() {
  try {
    if (!window.topojson) throw new Error("地圖邊界元件未載入");
    const response = await fetch("/data/counties-10t.json");
    if (!response.ok) throw new Error("縣市界線讀取失敗");
    const topology = await response.json();
    state.countyGeoJson = topojson.feature(topology, topology.objects.counties);
    renderCountyAreas();
  } catch (error) {
    setBasemap("street");
    showNotice(error.message + "；已切換至街道圖。");
  }
}
function setBasemap(basemap) {
  state.basemap = basemap;
  document.body.classList.toggle("dark-basemap", basemap === "dark");
  document.querySelectorAll(".basemap-button").forEach((button) => {
    const active = button.dataset.basemap === basemap;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  if (!state.map) return;
  if (basemap === "street") {
    if (state.countyLayer) state.map.removeLayer(state.countyLayer);
    state.streetLayer.addTo(state.map);
  } else {
    state.map.removeLayer(state.streetLayer);
    if (state.countyLayer) state.countyLayer.addTo(state.map);
  }
  renderMap();
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
function renderOverview() {
  const city = state.city;
  $("overview").hidden = !city || !state.data || state.detailsOpen || state.typhoonVisible;
  if (!city || !state.data) return;
  const stations = stationRows().filter((row) => row.county === city);
  const temps = stations.map((row) => num(row.temperature)).filter((value) => value !== null);
  const average = temps.length ? temps.reduce((sum, value) => sum + value, 0) / temps.length : null;
  const observedAt = stations.map((row) => row.observed_at).filter(Boolean).sort().at(-1);
  const forecast = activeForecastRows().find((row) => row.location === city);
  $("overview-city").textContent = city;
  const favored = state.favorites.includes(city);
  $("favorite-toggle").textContent = favored ? "★" : "☆";
  $("favorite-toggle").setAttribute("aria-pressed", String(favored));
  $("favorite-toggle").setAttribute("aria-label", favored ? "取消收藏" + city : "收藏" + city);
  $("overview-content").innerHTML =
    '<div class="overview-primary"><div><small>測站平均氣溫</small><strong>' + escapeHtml(fmtNum(average, "°C")) + '</strong></div>' +
    '<span>' + escapeHtml(stations.length + " 站 · 觀測 " + fmtTime(observedAt)) + '</span></div>' +
    '<div class="overview-forecast"><span>' + escapeHtml(forecast?.wx || "暫無時段預報") + '</span><strong>' +
    escapeHtml(fmtNum(forecast?.min_temp, "°")) + ' / ' + escapeHtml(fmtNum(forecast?.max_temp, "°")) + '</strong></div>' +
    '<div class="overview-meta"><span>降雨機率 ' + escapeHtml(fmtNum(forecast?.pop, "%")) + '</span><span>' +
    escapeHtml(forecast ? periodLabel(forecast.start_time, forecast.end_time) : "—") + '</span></div>' +
    '<div class="overview-source">預報抓取 ' + escapeHtml(fmtTime(state.data.forecast.fetched_at, true)) +
    ' · 網站發布 ' + escapeHtml(fmtTime(state.data.exported_at, true)) + '</div>';
}
function activeTyphoons() {
  const data = state.data?.typhoons;
  if (!data || !data.fetched_at || Date.now() - new Date(data.fetched_at).getTime() > 18 * 3600000) return [];
  return rows("typhoons").filter((row) => row.latest_at &&
    Date.now() - new Date(row.latest_at).getTime() < 24 * 3600000 &&
    Array.isArray(row.observed) && row.observed.length && typhoonTrack(row).length);
}
function typhoonTrack(cyclone) {
  const valid = (point) => point && Number.isFinite(num(point.latitude)) && Number.isFinite(num(point.longitude)) &&
    Number.isFinite(new Date(point.time).getTime());
  return [...cyclone.observed.filter(valid).map((point) => ({ ...point, forecast: false })),
    ...(Array.isArray(cyclone.forecast) ? cyclone.forecast : []).filter(valid)
      .map((point) => ({ ...point, forecast: true }))]
    .sort((a, b) => new Date(a.time) - new Date(b.time));
}
function typhoonIcon(point, position) {
  const wind = num(point.wind_speed);
  const size = wind === null ? 23 : Math.max(18, Math.min(34, Math.round(12 + wind * .55)));
  const html = '<div class="typhoon-node ' + position + (point.forecast ? ' is-forecast' : '') + '" style="--typhoon-size:' + size + 'px">' +
    '<svg viewBox="0 0 64 64" aria-hidden="true"><circle class="typhoon-halo" cx="32" cy="32" r="28"/>' +
    '<path class="typhoon-band" d="M31 8 C44 8 54 18 54 31 C48 24 41 22 35 26 C32 28 30 31 29 34 C24 28 22 19 26 12 C27 10 29 8 31 8 Z"/>' +
    '<path class="typhoon-band" d="M33 56 C20 56 10 46 10 33 C16 40 23 42 29 38 C32 36 34 33 35 30 C40 36 42 45 38 52 C37 54 35 56 33 56 Z"/>' +
    '<circle class="typhoon-eye" cx="32" cy="32" r="4"/></svg>' +
    '<span class="typhoon-node-leader" aria-hidden="true"></span>' +
    '<span class="typhoon-node-time">' + escapeHtml(fmtTime(point.time)) + '</span></div>';
  return L.divIcon({ className: "typhoon-map-icon", html, iconSize: [size, size], iconAnchor: [size / 2, size / 2], popupAnchor: [0, -size / 2] });
}
function typhoonPopup(cyclone, point) {
  return '<strong>' + escapeHtml(cyclone.name) + '</strong><br>' +
    escapeHtml((point.forecast ? '預報位置 · ' : '分析位置 · ') + fmtTime(point.time, true)) +
    '<br>最大風速：' + escapeHtml(fmtNum(point.wind_speed, ' m/s'));
}
function layoutTyphoonLabels() {
  if (!state.typhoonVisible || !state.map || !state.typhoonNodes.length) return;
  const width = state.map.getSize().x;
  const height = state.map.getSize().y;
  const sidebar = document.querySelector('.sidebar').getBoundingClientRect();
  const dock = document.querySelector('.bottom-hud').getBoundingClientRect();
  const map = state.map.getContainer().getBoundingClientRect();
  const leftLimit = matchMedia('(max-width: 900px)').matches ? 12 : Math.max(12, sidebar.right - map.left + 12);
  const bottomLimit = dock.top - map.top - 10;
  const nodes = state.typhoonNodes.map(({ marker, point }) => {
    const element = marker.getElement();
    if (!element) return null;
    const label = element.querySelector('.typhoon-node-time');
    const center = state.map.latLngToContainerPoint(marker.getLatLng());
    return { point, element, label, leader: element.querySelector('.typhoon-node-leader'), center,
      size: element.offsetWidth, width: label.offsetWidth, height: label.offsetHeight };
  }).filter(Boolean);
  const icons = nodes.map(({ center, size }) => ({ x: center.x - size / 2 - 2, y: center.y - size / 2 - 2,
    width: size + 4, height: size + 4 }));
  const placed = [];
  const overlap = (a, b) => a.x < b.x + b.width + 2 && a.x + a.width + 2 > b.x &&
    a.y < b.y + b.height + 2 && a.y + a.height + 2 > b.y;
  for (const node of nodes) {
    const { center, size, width: labelWidth, height: labelHeight } = node;
    const sides = node.point.forecast ? ['left', 'right'] : ['right', 'left'];
    let best = null;
    for (const offset of [0, -20, 20, -40, 40, -60, 60, -80, 80, -100, 100, -120, 120, -140, 140]) {
      for (const side of sides) {
        const box = { x: side === 'right' ? center.x + size / 2 + 6 : center.x - size / 2 - 6 - labelWidth,
          y: center.y - labelHeight / 2 + offset, width: labelWidth, height: labelHeight };
        const outside = Math.max(0, leftLimit - box.x) + Math.max(0, box.x + box.width - width + 10) +
          Math.max(0, 12 - box.y) + Math.max(0, box.y + box.height - bottomLimit);
        const collisions = placed.filter((other) => overlap(box, other)).length +
          icons.filter((icon) => overlap(box, icon)).length;
        const score = outside * 1000 + collisions * 10000 + Math.abs(offset) +
          (side === sides[0] ? 0 : 4);
        if (!best || score < best.score) best = { box, score };
      }
    }
    const box = best.box;
    const anchorX = center.x - size / 2;
    const anchorY = center.y - size / 2;
    Object.assign(node.label.style, { left: (box.x - anchorX) + 'px', top: (box.y - anchorY) + 'px',
      right: 'auto', bottom: 'auto', transform: 'none' });
    const endX = Math.max(box.x, Math.min(center.x, box.x + box.width));
    const endY = Math.max(box.y, Math.min(center.y, box.y + box.height));
    const dx = endX - center.x;
    const dy = endY - center.y;
    Object.assign(node.leader.style, { left: size / 2 + 'px', top: size / 2 + 'px',
      width: Math.hypot(dx, dy) + 'px', transform: 'rotate(' + Math.atan2(dy, dx) + 'rad)',
      display: Math.hypot(dx, dy) > size / 2 + 8 ? 'block' : 'none' });
    placed.push(box);
  }
}
function renderTyphoons() {
  const active = activeTyphoons();
  $("typhoon-card").hidden = !active.length;
  if (state.typhoonGroup) state.typhoonGroup.clearLayers();
  state.typhoonNodes = [];
  if (!active.length) { state.typhoonVisible = false; return; }
  $("typhoon-card").innerHTML = '<span class="eyebrow">颱風資訊</span><strong>' +
    escapeHtml(active.map((row) => row.name).join("、")) + ' · 颱風路徑</strong><small>' +
    escapeHtml(fmtTime(active[0].latest_at)) + ' 分析，含預報位置</small>' +
    '<button id="typhoon-toggle" type="button">' + (state.typhoonVisible ? "隱藏路徑" : "查看路徑") + '</button>';
  $("typhoon-toggle").addEventListener("click", () => {
    const opening = !state.typhoonVisible;
    state.typhoonVisible = opening;
    renderControls();
    if (state.typhoonVisible && state.map) {
      closeDetails();
      const points = active.flatMap((row) => typhoonTrack(row)
        .map((point) => [point.latitude, point.longitude]));
      const narrow = matchMedia('(max-width: 900px)').matches;
      const overlayHeight = document.querySelector('.bottom-hud').getBoundingClientRect().height;
      state.map.fitBounds(L.latLngBounds([...points, [23.8, 120.96]]).pad(.08), {
        maxZoom: 7,
        paddingTopLeft: narrow ? [24, 70] : [310, 70],
        paddingBottomRight: [30, Math.ceil(overlayHeight + 30)]
      });
      closeMenu();
    } else {
      state.map?.flyTo([23.78, 120.96], 8);
    }
  });
  if (!state.typhoonVisible || !state.typhoonGroup) return;
  for (const cyclone of active) {
    const track = typhoonTrack(cyclone);
    if (!track.length) continue;
    const observed = track.filter((point) => !point.forecast).map((point) => [point.latitude, point.longitude]);
    const predicted = track.filter((point) => point.forecast).map((point) => [point.latitude, point.longitude]);
    if (observed.length > 1) L.polyline(observed, { color: "#f0b975", weight: 2.5 }).addTo(state.typhoonGroup);
    if (predicted.length) L.polyline(observed.length ? [observed.at(-1), ...predicted] : predicted,
      { color: "#97d9e8", weight: 2.5, dashArray: "7 7" }).addTo(state.typhoonGroup);
    track.forEach((point, index) => {
      const position = ['label-right', 'label-above', 'label-left', 'label-below'][index % 4];
      const marker = L.marker([point.latitude, point.longitude], {
        icon: typhoonIcon(point, position),
        title: cyclone.name + ' · ' + fmtTime(point.time) + (point.forecast ? ' · 預報' : ' · 分析'),
        zIndexOffset: Math.round(num(point.wind_speed) || 0)
      }).bindPopup(typhoonPopup(cyclone, point)).addTo(state.typhoonGroup);
      state.typhoonNodes.push({ marker, point });
    });
  }
  requestAnimationFrame(layoutTyphoonLabels);
}
function distanceKm(lat1, lon1, lat2, lon2) {
  const radians = (degrees) => degrees * Math.PI / 180;
  const a = Math.sin(radians(lat2 - lat1) / 2) ** 2 + Math.cos(radians(lat1)) * Math.cos(radians(lat2)) *
    Math.sin(radians(lon2 - lon1) / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}
function locateNearestStation() {
  if (!navigator.geolocation) { showNotice("此瀏覽器不支援定位功能。"); return; }
  $("locate").disabled = true;
  navigator.geolocation.getCurrentPosition((position) => {
    $("locate").disabled = false;
    const candidates = stationRows().filter((row) => num(row.temperature) !== null);
    const nearest = candidates.map((row) => ({ row, km: distanceKm(position.coords.latitude, position.coords.longitude,
      row.latitude, row.longitude) })).sort((a, b) => a.km - b.km)[0];
    if (!nearest || nearest.km > 150) { showNotice("目前位置距臺灣測站較遠，請用搜尋選擇縣市。"); return; }
    selectStation(nearest.row.station_id);
    state.map?.flyTo([nearest.row.latitude, nearest.row.longitude], 10);
    showNotice("已選取最近測站：" + nearest.row.station_name + "（約 " + Math.round(nearest.km) + " 公里）");
  }, () => { $("locate").disabled = false; showNotice("無法取得位置，請允許定位權限或用搜尋選擇縣市。"); },
  { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 });
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
  if (state.typhoonVisible) {
    $("map-title").textContent = "颱風分析與預測路徑";
    $("map-subtitle").textContent = "每個圖示代表一筆日期資料 · 大小依最大風速 · 實線分析、虛線預報";
    return;
  }
  $("map-title").textContent = labels[state.layer];
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
    state.map.getZoom() >= 9 ? "實際測站座標 · 點選圓點查看觀測" : "縣市測站平均 · 點選圓點查看概況";
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
  if (!counties().includes(city)) return;
  state.city = city; state.station = null; state.detailsOpen = false; state.search = ""; $("search").value = "";
  renderCities(); renderOverview(); renderDetails(); renderMap(); updateUrl(); if (state.basemap === "dark") renderCountyAreas();
  closeMenu();
}
function selectStation(id) {
  const row = stationRows().find((item) => item.station_id === id);
  if (!row) return;
  state.station = id; state.city = row.county; state.detailsOpen = true; state.search = ""; $("search").value = "";
  renderCities(); renderOverview(); renderDetails(); renderMap(); updateUrl(); if (state.basemap === "dark") renderCountyAreas();
  state.map?.flyTo([row.latitude, row.longitude], 10);
  closeMenu();
}
function renderDetails() {
  if (!state.detailsOpen || (!state.city && !state.station)) {
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
  state.detailsOpen = false;
  $("details").classList.remove("open");
  $("details-content").innerHTML = '<div class="detail-empty">選取地圖上的測站或左側縣市，查看詳細天氣與預報。</div>';
  if (state.data) { renderCities(); renderOverview(); }
  if (state.basemap === "dark") renderCountyAreas();
}
function renderDataDialog() {
  $("published-time").textContent = "網站快照發布：" + fmtTime(state.data.exported_at, true);
  $("source-summary").innerHTML = Object.entries(ids).map(([name, id]) => {
    const title = ({ forecast: "36 小時預報", weekly: "一週預報", observations: "測站觀測", typhoons: "颱風動態" })[name];
    const data = state.data[name] || { count: 0, fetched_at: null };
    return '<div class="source-row"><span>' + escapeHtml(title + " · " + id) + '</span><strong>' + escapeHtml(data.count + " 筆 · " + fmtTime(data.fetched_at)) + '</strong></div>';
  }).join("");
  $("crawl-log").innerHTML = (state.data.crawl_runs || []).map((run) =>
    '<div class="crawl-row ' + escapeHtml(run.status) + '"><span>' + escapeHtml(run.dataset_id + " · " + fmtTime(run.finished_at)) +
    '</span><strong>' + escapeHtml(run.status === "success" ? "成功 · " + run.record_count + " 筆" : "失敗 · " + (run.error_message || "未知錯誤")) + '</strong></div>').join("") || '<p>尚無爬蟲紀錄。</p>';
}
function renderControls() {
  if (state.typhoonVisible && !activeTyphoons().length) state.typhoonVisible = false;
  document.body.classList.toggle("typhoon-mode", state.typhoonVisible);
  if (isForecast()) state.forecastLayer = state.layer;
  document.querySelectorAll(".layer-button").forEach((button) => {
    const active = button.dataset.layer === state.layer;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  $("map-title").textContent = labels[state.layer];
  const times = forecastPeriods();
  if (!times.some(([key]) => key === state.period)) {
    state.period = times.find(([, row]) => new Date(row.end_time).getTime() > Date.now())?.[0] || times.at(-1)?.[0] || "";
  }
  $("period-control").hidden = !isForecast() || state.typhoonVisible;
  $("timeline-control").hidden = state.typhoonVisible;
  $("download").hidden = state.typhoonVisible;
  $("period-select").innerHTML = times.map(([key, row]) =>
    '<option value="' + escapeHtml(key) + '">' + escapeHtml(periodLabel(row.start_time, row.end_time)) + '</option>').join("");
  $("period-select").value = state.period;
  const periodIndex = Math.max(times.findIndex(([key]) => key === state.period), 0);
  $("period-range").max = String(Math.max(times.length - 1, 0));
  $("period-range").value = String(periodIndex);
  $("period-range").disabled = times.length < 2;
  $("timeline-label").textContent = state.period ? periodLabel(...state.period.split("|")) : "目前沒有預報時段";
  $("period-range").setAttribute("aria-valuetext", $("timeline-label").textContent);
  $("timeline-start").textContent = times.length ? fmtTime(times[0][1].start_time) : "—";
  $("timeline-end").textContent = times.length ? fmtTime(times.at(-1)[1].end_time) : "—";
  $("dock-title").textContent = state.typhoonVisible ? "颱風路徑" : isForecast() ? "預報有效時段" : "最新測站觀測";
  $("dock-time").textContent = state.typhoonVisible ? fmtTime(state.data.typhoons.source_updated, true) + " 發布" :
    isForecast() ? fmtTime(state.data.forecast.fetched_at, true) + " 抓取" :
    fmtTime(state.data.observations.fetched_at, true) + " 抓取";
  const source = state.typhoonVisible ? state.data.typhoons : isForecast() ? state.data.forecast : state.data.observations;
  const age = source.fetched_at ? Date.now() - new Date(source.fetched_at).getTime() : Infinity;
  $("freshness").textContent = (state.typhoonVisible ? "颱風抓取 " : isForecast() ? "預報抓取 " : "觀測抓取 ") + fmtTime(source.fetched_at) +
    (age > 12 * 3600000 ? " · 資料較舊" : "");
  document.querySelector(".status-dot").classList.toggle("stale", age > 12 * 3600000);
  renderLegend(); renderFavorites(); renderCities(); renderOverview(); renderMap(); renderDetails();
  renderDataDialog(); renderCountyAreas(); renderTyphoons(); updateUrl();
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
    if (!counties().includes(state.city)) state.city = null;
    renderControls();
    if (!data.observations.count) showNotice("尚無測站資料。請先在本機執行 python scripts/fetch_once.py --all。");
  } catch (error) { showNotice(error.message + "；請先執行爬蟲並匯出 JSON。"); }
  finally { $("refresh").disabled = false; }
}
document.querySelectorAll(".layer-button").forEach((button) => button.addEventListener("click", () => {
  state.layer = button.dataset.layer; state.station = null; state.typhoonVisible = false;
  if (state.data) renderControls(); closeMenu();
}));
document.querySelectorAll(".basemap-button").forEach((button) => button.addEventListener("click", () => setBasemap(button.dataset.basemap)));
$("city-toggle").addEventListener("click", () => setCityBrowserOpen(!$("city-browser").classList.contains("open")));
$("search").addEventListener("input", (event) => { state.search = event.target.value.trim(); if (state.search) setCityBrowserOpen(true); if (state.data) { renderCities(); renderMap(); } });
$("period-select").addEventListener("change", (event) => { state.period = event.target.value; renderControls(); });
$("period-range").addEventListener("input", (event) => {
  if (state.typhoonVisible) return;
  const period = forecastPeriods()[Number(event.target.value)]?.[0];
  if (!period || (period === state.period && isForecast())) return;
  state.period = period;
  if (!isForecast()) {
    state.layer = state.forecastLayer;
    state.station = null;
  }
  renderControls();
});
$("favorite-toggle").addEventListener("click", toggleFavorite);
$("overview-details").addEventListener("click", () => { if (state.city) { state.detailsOpen = true; renderOverview(); renderDetails(); } });
$("overview-close").addEventListener("click", () => { state.city = null; state.station = null; state.detailsOpen = false; renderCities(); renderOverview(); renderDetails(); updateUrl(); if (state.basemap === "dark") renderCountyAreas(); });
$("share-view").addEventListener("click", async () => {
  updateUrl();
  try { await navigator.clipboard.writeText(location.href); showNotice("目前縣市與圖層連結已複製。"); }
  catch { window.prompt("複製目前畫面連結", location.href); }
});
$("locate").addEventListener("click", locateNearestStation);
$("zoom-home").addEventListener("click", () => state.map?.flyTo([23.78, 120.96], 8));
$("download").addEventListener("click", downloadCsv);
$("refresh").addEventListener("click", loadData);
$("data-button").addEventListener("click", () => $("data-dialog").showModal());
$("detail-close").addEventListener("click", closeDetails);
$("menu-toggle").addEventListener("click", () => { closeDetails(); $("sidebar").classList.add("open"); document.body.classList.add("menu-open"); });
$("menu-close").addEventListener("click", closeMenu);
initMap();
setBasemap("dark");
loadData();
