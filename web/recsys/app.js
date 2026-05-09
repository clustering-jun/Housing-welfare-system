const state = {
  map: null,
  markers: {},
  complexes: [],
  details: {},
  recommendations: {},
  filtered: [],
  selectedId: null,
};

const $ = (id) => document.getElementById(id);

function riskColor(score) {
  if (score >= 0.6) return "#e74c3c";
  if (score >= 0.4) return "#e67e22";
  if (score >= 0.2) return "#f1c40f";
  return "#27ae60";
}

function riskClass(score) {
  if (score >= 0.6) return "high";
  if (score >= 0.4) return "med";
  if (score >= 0.2) return "warn";
  return "low";
}

function fmtScore(value) {
  return value == null ? "-" : Number(value).toFixed(3);
}

function fmtPct(value) {
  return value == null ? "-" : `${(Number(value) * 100).toFixed(1)}%`;
}

function fmtNum(value) {
  return value == null ? "-" : Number(value).toLocaleString("ko-KR");
}

async function loadJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path} 로딩 실패`);
  return response.json();
}

async function boot() {
  const [complexes, details, recommendations, stats] = await Promise.all([
    loadJson("./data/complexes.json"),
    loadJson("./data/details.json"),
    loadJson("./data/recommendations.json"),
    loadJson("./data/stats.json"),
  ]);
  state.complexes = complexes;
  state.details = details;
  state.recommendations = recommendations;
  state.filtered = [...complexes];

  $("statTotal").textContent = fmtNum(stats.total_complexes);
  $("statBlindspot").textContent = fmtNum(stats.blindspot_count);
  $("statRobust").textContent = fmtNum(stats.robust_highrisk_count);

  initMap();
  buildClusterFilter();
  renderList(state.filtered);
  bindEvents();
}

function initMap() {
  state.map = L.map("map", { center: [36.4, 127.8], zoom: 7 });
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap",
    maxZoom: 18,
  }).addTo(state.map);

  state.complexes.forEach((complex) => {
    if (!complex.lat || !complex.lng) return;
    const score = Number(complex.vulnerability_score || 0);
    const size = complex.is_blindspot ? 14 : 10;
    const icon = L.divIcon({
      className: "",
      html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${riskColor(score)};border:2px solid white;box-shadow:0 1px 5px rgba(0,0,0,.35);"></div>`,
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
    });
    const marker = L.marker([complex.lat, complex.lng], { icon }).addTo(state.map);
    marker.bindPopup(`
      <b>${complex.name}</b><br>
      <span style="color:#6f7f8f">${complex.village || ""}</span><br>
      <b style="color:${riskColor(score)}">취약도 ${fmtScore(score)}</b><br>
      ${complex.sido || ""} ${complex.sigungu || ""}<br>
      <button onclick="selectComplex('${complex.id}')" style="margin-top:8px;width:100%;padding:6px;border:0;border-radius:4px;background:#1e6091;color:white;cursor:pointer;">리포트 보기</button>
    `);
    marker.on("click", () => selectComplex(complex.id));
    state.markers[complex.id] = marker;
  });
}

function buildClusterFilter() {
  const select = $("clusterFilter");
  [...new Set(state.complexes.map((c) => c.cluster).filter(Boolean))].sort().forEach((cluster) => {
    const option = document.createElement("option");
    option.value = cluster;
    option.textContent = `클러스터 ${cluster}`;
    select.appendChild(option);
  });
}

function bindEvents() {
  $("searchInput").addEventListener("input", () => applyFilters());
  $("searchBtn").addEventListener("click", () => applyFilters());
  $("riskFilter").addEventListener("change", () => applyFilters());
  $("clusterFilter").addEventListener("change", () => applyFilters());
  $("closeReport").addEventListener("click", () => $("reportPanel").classList.remove("open"));
}

function applyFilters() {
  const query = $("searchInput").value.trim().toLowerCase();
  const risk = $("riskFilter").value;
  const cluster = $("clusterFilter").value;
  let rows = state.complexes.filter((c) => {
    const text = `${c.name} ${c.village || ""} ${c.sido || ""} ${c.sigungu || ""}`.toLowerCase();
    return !query || text.includes(query);
  });
  if (risk !== "all") {
    rows = rows.filter((c) => {
      const score = Number(c.vulnerability_score || 0);
      if (risk === "blindspot") return Number(c.is_blindspot) === 1;
      if (risk === "high") return score >= 0.6;
      if (risk === "medium") return score >= 0.4 && score < 0.6;
      if (risk === "low") return score < 0.4;
      return true;
    });
  }
  if (cluster !== "all") rows = rows.filter((c) => c.cluster === cluster);

  const visible = new Set(rows.map((c) => c.id));
  Object.entries(state.markers).forEach(([id, marker]) => {
    if (visible.has(id)) {
      if (!state.map.hasLayer(marker)) marker.addTo(state.map);
    } else if (state.map.hasLayer(marker)) {
      marker.remove();
    }
  });
  state.filtered = rows;
  renderList(rows);
}

function renderList(rows) {
  $("listCount").textContent = `${rows.length}개`;
  $("complexList").innerHTML = rows.slice(0, 120).map((c) => {
    const score = Number(c.vulnerability_score || 0);
    return `
      <div class="complex-item ${state.selectedId === c.id ? "active" : ""}" onclick="selectComplex('${c.id}')">
        <span class="risk-dot ${riskClass(score)}"></span>
        <div>
          <div class="complex-name">${c.name}</div>
          <div class="complex-sub">${c.sido || ""} ${c.sigungu || ""} · ${c.supply_type || ""}</div>
          <div class="complex-sub">${c.risk_grade || ""} · ${c.rank ? `${c.rank}위` : ""}</div>
        </div>
        <div class="score" style="color:${riskColor(score)}">${fmtScore(score)}</div>
      </div>
    `;
  }).join("");
}

window.selectComplex = function selectComplex(id) {
  state.selectedId = id;
  const complex = state.complexes.find((c) => c.id === id);
  if (!complex) return;
  $("reportPanel").classList.add("open");
  focusMap(complex);
  state.markers[id]?.openPopup();
  renderList(state.filtered);
  renderReport(id);
};

function focusMap(complex) {
  const zoom = 14;
  const map = state.map;
  const panel = $("reportPanel");
  const size = map.getSize();
  const overlay = panel.classList.contains("open") && panel.offsetWidth < size.x * .85 ? panel.offsetWidth : 0;
  const desiredX = (size.x - overlay) / 2;
  const markerPoint = map.project([complex.lat, complex.lng], zoom);
  const centerPoint = L.point(markerPoint.x + size.x / 2 - desiredX, markerPoint.y);
  map.setView(map.unproject(centerPoint, zoom), zoom, { animate: true });
}

function renderReport(id) {
  const d = state.details[id];
  const rec = state.recommendations[id];
  if (!d || !rec) return;

  $("reportTitle").textContent = d.name;
  $("reportSubtitle").textContent = `${d.sido || ""} ${d.sigungu || ""} · ${d.supply_type || ""} · ${fmtNum(d.total_units)}호`;
  $("reportBadges").innerHTML = `
    <span class="badge" style="background:${riskColor(d.vulnerability_score)}">${d.risk_grade || "등급 없음"}</span>
    <span class="badge">취약도 ${fmtScore(d.vulnerability_score)}</span>
    <span class="badge">전체 ${d.rank || "-"}위</span>
    ${d.is_blindspot ? '<span class="badge" style="background:#c0392b">사각지대</span>' : ""}
    ${d.is_robust_highrisk ? '<span class="badge" style="background:#e67e22">강건 고위험</span>' : ""}
  `;

  $("reportBody").innerHTML = `
    ${basicSection(d)}
    ${vulnerabilitySection(d)}
    ${serviceSection(d)}
    ${recommendationSection(rec)}
  `;
}

function box(label, value) {
  return `<div class="info-box"><span>${label}</span><strong>${value ?? "-"}</strong></div>`;
}

function basicSection(d) {
  return `
    <section class="section">
      <h3>단지 기본 정보</h3>
      <div class="grid">
        ${box("단지명", d.name)}
        ${box("마을명", d.village || "-")}
        ${box("위치", `${d.sido || ""} ${d.sigungu || ""}`)}
        ${box("공급유형", d.supply_type || "-")}
        ${box("건설호수", `${fmtNum(d.total_units)}호`)}
        ${box("총인구", `${fmtNum(d.total_population)}명`)}
        ${box("고령화율", fmtPct(d.elderly_rate))}
        ${box("초고령비율", fmtPct(d.super_elderly_rate))}
        ${box("아동청소년비율", fmtPct(d.child_youth_rate))}
        ${box("클러스터", d.cluster || "-")}
      </div>
    </section>
  `;
}

function metric(label, value) {
  if (value == null) return "";
  const score = Number(value);
  return `
    <div class="bar-row">
      <div class="bar-label"><span>${label}</span><b style="color:${riskColor(score)}">${fmtScore(score)}</b></div>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.round(score * 100)}%;background:${riskColor(score)}"></div></div>
    </div>
  `;
}

function vulnerabilitySection(d) {
  const v = d.vulnerability_detail || {};
  return `
    <section class="section">
      <h3>취약도 분석</h3>
      ${metric("종합 취약도", v.total)}
      ${metric("인구 취약도", v.population)}
      ${metric("시설 취약도", v.facility)}
      ${metric("접근성 취약도", v.accessibility)}
      ${metric("서비스 이용 취약도", v.service)}
      ${metric("거버넌스 취약도", v.governance)}
      ${metric("이상탐지 점수", v.anomaly)}
      <div class="tags">${(d.main_causes || "").split(",").filter(Boolean).map((x) => `<span class="tag">${x.trim()}</span>`).join("")}</div>
    </section>
  `;
}

function serviceSection(d) {
  const f = d.facilities || {};
  const h = d.home_doctor || {};
  const c = d.community || {};
  return `
    <section class="section">
      <h3>시설·서비스 현황</h3>
      <div class="grid">
        ${box("경로당", f.senior_center ? "있음" : "없음")}
        ${box("복지관", f.welfare_center ? "있음" : "없음")}
        ${box("운동시설", f.exercise_facility ? "있음" : "없음")}
        ${box("홈닥터 총지원건수", h.total_supports != null ? `${fmtNum(h.total_supports)}건` : "-")}
        ${box("홈닥터 이용률", fmtPct(h.usage_rate))}
        ${box("커뮤니티 활동", c.total_activities != null ? `${fmtNum(c.total_activities)}회` : "-")}
        ${box("세대당 참여인원", c.participants_per_household != null ? Number(c.participants_per_household).toFixed(3) : "-")}
      </div>
    </section>
  `;
}

function recommendationSection(rec) {
  const core = rec.core_programs || [];
  const comp = rec.complementary_programs || [];
  const programs = [
    ...core.map((p) => ({ ...p, core: true })),
    ...comp.map((p) => ({ ...p, core: false })),
  ];
  return `
    <section class="section">
      <h3>맞춤형 복지 프로그램 추천</h3>
      ${rec.overall_assessment ? `<p>${rec.overall_assessment}</p>` : ""}
      ${programs.map(programCard).join("")}
      ${rec.implementation_roadmap ? `<h3>실행 로드맵</h3><p>${rec.implementation_roadmap}</p>` : ""}
      ${rec.monitoring_indicators?.length ? `<h3>성과 측정 지표</h3><div class="tags">${rec.monitoring_indicators.map((x) => `<span class="tag">${x}</span>`).join("")}</div>` : ""}
    </section>
  `;
}

function programCard(p) {
  return `
    <article class="program-card ${p.core ? "" : "comp"}">
      <div class="program-top">
        <div>
          <div class="program-title">${p.name || "프로그램"} <span style="font-size:11px;color:#789">[${p.catalog_id || ""}]</span></div>
          <div class="tags">
            <span class="tag">${p.core ? "핵심" : "보완"}</span>
            <span class="tag">${p.category || ""}</span>
            <span class="tag">${p.selection_method === "rule_based" ? "규칙 선정" : "AI 선정"}</span>
            ${p.target ? `<span class="tag">${p.target}</span>` : ""}
          </div>
        </div>
      </div>
      <p>${p.description || ""}</p>
      ${p.rationale ? `<p><b>추천 근거:</b> ${p.rationale}</p>` : ""}
      <div class="detail-grid">
        ${p.implementation ? `<div><span>실행 방안</span>${p.implementation}</div>` : ""}
        ${p.expected_effect ? `<div><span>기대 효과</span>${p.expected_effect}</div>` : ""}
        ${p.fit_reasons?.length ? `<div><span>선정 조건</span>${p.fit_reasons.join(" · ")}</div>` : ""}
      </div>
    </article>
  `;
}

boot().catch((error) => {
  document.body.innerHTML = `<pre style="padding:24px;color:#c0392b">${error.message}</pre>`;
});
