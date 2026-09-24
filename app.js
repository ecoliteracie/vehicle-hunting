const DATA_URL = 'data/vehicles.json';
let DATA = null;
const chartInstances = {};
const app = document.getElementById('app');

const fmtUSD = n => (n == null ? '—' : `$${n.toLocaleString('en-US')}`);
const avgMpg = t => (t.mpgCombined ?? (t.mpgCity != null && t.mpgHwy != null ? Math.round((t.mpgCity + t.mpgHwy) / 2) : null));

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function groupVehicles(vehicles) {
  const map = new Map();
  vehicles.forEach(v => {
    if (!map.has(v.modelSlug)) map.set(v.modelSlug, { modelSlug: v.modelSlug, model: v.model, bodyType: v.bodyType, profiles: [] });
    map.get(v.modelSlug).profiles.push(v);
  });
  map.forEach(g => g.profiles.sort((a, b) => a.year - b.year));
  return Array.from(map.values()).sort((a, b) => a.model.localeCompare(b.model));
}

function trimStats(vehicle) {
  const prices = vehicle.trims.map(t => t.msrp).filter(v => v != null);
  const mpgs = vehicle.trims.map(avgMpg).filter(v => v != null);
  const drivetrains = Array.from(new Set(vehicle.trims.map(t => t.drivetrain)));
  return {
    priceMin: prices.length ? Math.min(...prices) : null,
    priceMax: prices.length ? Math.max(...prices) : null,
    mpgMax: mpgs.length ? Math.max(...mpgs) : null,
    gradeCount: vehicle.featureMatrix.grades.length,
    drivetrains,
  };
}

/* ---------- Make selection ---------- */

function getCurrentMake() {
  let stored = 'Toyota';
  try { stored = localStorage.getItem('vh-make') || 'Toyota'; } catch (e) { /* private mode */ }
  const makes = DATA?.makes || ['Toyota'];
  return makes.includes(stored) ? stored : makes[0];
}

function setCurrentMake(make) {
  try { localStorage.setItem('vh-make', make); } catch (e) { /* private mode */ }
}

function vehiclesForCurrentMake() {
  const make = getCurrentMake();
  return DATA.vehicles.filter(v => v.make === make);
}

/* ---------- Router ---------- */

function router() {
  Object.values(chartInstances).forEach(c => c.destroy());
  Object.keys(chartInstances).forEach(k => delete chartInstances[k]);

  const hash = location.hash.replace(/^#\/?/, '');
  const parts = hash.split('/').filter(Boolean);
  if (parts[0] === 'model' && parts[1]) {
    renderModelPage(parts[1], parts[2] ? Number(parts[2]) : null);
  } else if (parts[0] === 'all-trims') {
    renderAllTrimsPage();
  } else {
    renderHome();
  }
  window.scrollTo({ top: 0 });
}

/* ---------- Home ---------- */

function renderHome() {
  const make = getCurrentMake();
  const groups = groupVehicles(vehiclesForCurrentMake());
  app.innerHTML = `
    <section class="hero">
      <p class="eyebrow">Car / ${make}</p>
      <h1>Every ${make} trim, compared at a glance</h1>
      <p class="hero-sub">Pick a model to see every trim's price, efficiency, and full feature matrix on one page.</p>
    </section>
    <section class="model-grid">
      ${groups.map(modelCard).join('')}
    </section>
    <a class="all-trims-banner" href="#/all-trims">
      <div>
        <h2>See every trim, every model, in one table</h2>
        <p>Price, engine/output, efficiency, and the handful of features tracked consistently across all profiles — sortable and filterable. Not a full apples-to-apples feature comparison (body styles and powertrains differ too much for that) but enough to scan the whole lineup at once.</p>
      </div>
      <span class="all-trims-banner__arrow" aria-hidden="true">→</span>
    </a>
  `;
}

function modelCard(g) {
  const stats = g.profiles.map(trimStats);
  const priceMin = Math.min(...stats.map(s => s.priceMin).filter(v => v != null));
  const priceMax = Math.max(...stats.map(s => s.priceMax).filter(v => v != null));
  const mpgMax = Math.max(...stats.map(s => s.mpgMax).filter(v => v != null));
  const years = g.profiles.map(p => p.year).join(' · ');
  const gradeCount = g.profiles[0].featureMatrix.grades.length;
  return `
  <a class="model-card" href="#/model/${g.modelSlug}">
    <div class="model-card__top">
      <span class="badge badge--body">${g.bodyType}</span>
      <span class="badge">${years}</span>
    </div>
    <h2>${g.model}</h2>
    <dl class="model-card__stats">
      <div><dt>From</dt><dd>${fmtUSD(priceMin)}</dd></div>
      <div><dt>To</dt><dd>${fmtUSD(priceMax)}</dd></div>
      <div><dt>Best MPG</dt><dd>${mpgMax}</dd></div>
      <div><dt>Grades</dt><dd>${gradeCount}</dd></div>
    </dl>
  </a>`;
}

/* ---------- All Trims ---------- */

const FEATURE_LOOKUP = {
  roof: {
    'camry-2026': ['Panoramic roof'],
    'corolla-2026': ['Power tilt/slide moonroof'],
    'corolla-2027': ['Moonroof / glass roof (bundled with Qi charging above this tier)'],
    'corolla-cross-2026': ['Moonroof / glass roof'],
    'rav4-hybrid-2026': ['Panoramic glass roof'],
    'prius-2027': ['Fixed glass roof'],
    'accord-2026': ['One-touch power moonroof'],
    'accord-hybrid-2026': ['One-touch moonroof'],
    'civic-si-2026': ['One-touch moonroof'],
    'civic-hybrid-2026': ['One-touch moonroof'],
    'pilot-2026': ['Panoramic moonroof'],
  },
  heatedSeats: {
    'camry-2026': ['Heated front seats / heated steering wheel'],
    'corolla-2026': ['SofTex-trimmed heated front sport seats', 'SofTex-trimmed heated front seats'],
    'corolla-2027': ['Heated SofTex front seats'],
    'corolla-cross-2026': ['Heated front seats'],
    'rav4-hybrid-2026': ['Heated front seats'],
    'prius-2027': ['Heated front seats'],
    'accord-2026': ['Heated front seats'],
    'accord-hybrid-2026': ['Heated front seats'],
    'civic-hybrid-2026': ['Heated front seats'],
    'civic-si-2026': ['Heated front seats'],
    'passport-2026': ['Heated and ventilated front seats'],
    'pilot-2026': ['Ventilated front / heated 2nd-row seats'],
  },
  audio: {
    'camry-2026': ['JBL 9-speaker premium audio'],
    'corolla-2026': ['JBL premium audio (9 speakers, subwoofer, amplifier)'],
    'corolla-2027': ['JBL Premium Audio'],
    'corolla-cross-2026': ['JBL 9-speaker premium audio'],
    'rav4-hybrid-2026': ['JBL 9-speaker premium audio'],
    'prius-2027': ['JBL 8-speaker premium audio'],
    'accord-2026': ['Eight-speaker, 180-watt audio'],
    'accord-hybrid-2026': ['Bose 12-speaker premium audio'],
    'civic-2026': ['Eight-speaker, 180-watt audio'],
    'civic-hybrid-2026': ['Bose 12-speaker premium audio'],
    'civic-si-2026': ['Bose 12-speaker premium audio'],
    'passport-2026': ['Bose premium audio'],
    'pilot-2026': ['Bose premium audio'],
  },
  hud: {
    'camry-2026': ['10-in head-up display'],
    'corolla-2026': ['Head-up display'],
    'corolla-2027': ['Head-up display'],
    'corolla-cross-2026': ['Head-up display'],
    'rav4-hybrid-2026': ['Head-up display'],
    'prius-2027': ['Head-up display'],
    'accord-hybrid-2026': ['Head-up display'],
    'pilot-2026': ['Head-up display / heated steering wheel'],
  },
};

function lookupFeature(vehicle, grade, key) {
  const featureNames = FEATURE_LOOKUP[key]?.[vehicle.id];
  if (!featureNames) return null;
  const gradeIdx = vehicle.featureMatrix.grades.indexOf(grade);
  if (gradeIdx === -1) return null;
  let fallback = null;
  for (const fname of featureNames) {
    const row = vehicle.featureMatrix.rows.find(r => r.feature === fname);
    if (!row) continue;
    const v = row.values[gradeIdx];
    if (fallback == null) fallback = v;
    if (v && v !== '-') return v;
  }
  return fallback;
}

function allTrimsFlat() {
  const rows = [];
  for (const v of vehiclesForCurrentMake()) {
    for (const t of v.trims) {
      rows.push({
        model: v.model,
        modelSlug: v.modelSlug,
        year: v.year,
        vehicleLabel: `${v.model} '${String(v.year).slice(2)} ${t.name}`,
        bodyType: v.bodyType,
        drivetrain: t.drivetrain,
        engine: t.engine,
        hp: t.hp,
        msrp: t.msrp,
        mpgCombined: avgMpg(t),
        roof: lookupFeature(v, t.grade, 'roof'),
        heatedSeats: lookupFeature(v, t.grade, 'heatedSeats'),
        audio: lookupFeature(v, t.grade, 'audio'),
        hud: lookupFeature(v, t.grade, 'hud'),
      });
    }
  }
  return rows;
}

function renderAllTrimsPage() {
  const make = getCurrentMake();
  const allRows = allTrimsFlat();
  const models = Array.from(new Set(vehiclesForCurrentMake().map(v => v.model)));

  app.innerHTML = `
    <section class="model-page">
      <p class="eyebrow"><a href="#/">Car</a> / <a href="#/">${make}</a> / All Trims</p>
      <div class="model-page__head">
        <div>
          <h1>All ${make} trims at a glance</h1>
          <p class="scope">Every trim across every model, one row each. A full apples-to-apples feature comparison isn't possible across different body styles and powertrains, so this sticks to what's genuinely comparable: price, engine/output, efficiency, and the handful of features tracked consistently across all six profiles. Click a column header to sort, or a model chip to filter. Open a model's own page for its complete feature matrix.</p>
        </div>
      </div>

      <div class="chip-row" id="modelFilter">
        ${models.map(m => `<button type="button" class="chip is-active" data-model="${m}">${m}</button>`).join('')}
      </div>

      <section class="panel">
        <div class="panel__head">
          <h2 id="allTrimsCount">${allRows.length} trims</h2>
          <input type="search" id="allTrimsSearch" placeholder="Search trims…" aria-label="Search trims">
        </div>
        <div class="fcell-legend">
          <span class="fcell-legend__item"><span class="fcell fcell--standard"><span aria-hidden="true"></span></span> Standard</span>
          <span class="fcell-legend__item"><span class="fcell fcell--available"><span aria-hidden="true"></span></span> Available</span>
          <span class="fcell-legend__item"><span class="fcell fcell--none"><span aria-hidden="true">–</span></span> Not offered</span>
          <span class="fcell-legend__item"><span class="fcell fcell--unknown"><span aria-hidden="true">?</span></span> Unconfirmed</span>
        </div>
        <div class="table-scroll table-scroll--matrix">
          <table class="trim-table" id="allTrimsTable">
            <thead>
              <tr>
                <th data-key="vehicleLabel" class="feature-col">Vehicle</th>
                <th data-key="bodyType">Body</th>
                <th data-key="drivetrain">Drive</th>
                <th data-key="engine">Engine</th>
                <th data-key="hp" class="num">HP</th>
                <th data-key="msrp" class="num">MSRP</th>
                <th data-key="mpgCombined" class="num">MPG comb.</th>
                <th>Roof</th>
                <th>Htd seats</th>
                <th>Audio</th>
                <th>HUD</th>
              </tr>
            </thead>
            <tbody>${allTrimsRows(allRows)}</tbody>
          </table>
        </div>
      </section>
    </section>
  `;

  wireAllTrimsTable(allRows);
}

function allTrimsRows(rows) {
  return rows.map(r => `
    <tr>
      <td class="trim-name feature-col"><a href="#/model/${r.modelSlug}/${r.year}">${r.vehicleLabel}</a></td>
      <td>${r.bodyType}</td>
      <td>${r.drivetrain}</td>
      <td>${r.engine}</td>
      <td class="num">${r.hp}</td>
      <td class="num">${fmtUSD(r.msrp)}</td>
      <td class="num">${r.mpgCombined ?? '—'}</td>
      <td>${r.roof ? featureCell(r.roof) : '—'}</td>
      <td>${r.heatedSeats ? featureCell(r.heatedSeats) : '—'}</td>
      <td>${r.audio ? featureCell(r.audio) : '—'}</td>
      <td>${r.hud ? featureCell(r.hud) : '—'}</td>
    </tr>`).join('');
}

function wireAllTrimsTable(allRows) {
  const table = document.getElementById('allTrimsTable');
  const chipRow = document.getElementById('modelFilter');
  const search = document.getElementById('allTrimsSearch');
  const countEl = document.getElementById('allTrimsCount');
  let sortKey = null;
  let sortDir = 1;

  function apply() {
    const active = new Set(Array.from(chipRow.querySelectorAll('.chip.is-active')).map(c => c.dataset.model));
    let rows = allRows.filter(r => active.has(r.model));
    const q = search.value.trim().toLowerCase();
    if (q) rows = rows.filter(r => r.vehicleLabel.toLowerCase().includes(q));
    if (sortKey) {
      rows = [...rows].sort((a, b) => {
        const av = a[sortKey];
        const bv = b[sortKey];
        if (av == null && bv == null) return 0;
        if (av == null) return 1;
        if (bv == null) return -1;
        if (typeof av === 'string') return av.localeCompare(bv) * sortDir;
        return (av - bv) * sortDir;
      });
    }
    table.querySelector('tbody').innerHTML = allTrimsRows(rows);
    countEl.textContent = `${rows.length} trim${rows.length === 1 ? '' : 's'}`;
  }

  chipRow.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      chip.classList.toggle('is-active');
      apply();
    });
  });

  search.addEventListener('input', apply);

  table.querySelectorAll('th[data-key]').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.key;
      sortDir = sortKey === key ? -sortDir : 1;
      sortKey = key;
      table.querySelectorAll('th[data-key]').forEach(h => h.classList.remove('sorted-asc', 'sorted-desc'));
      th.classList.add(sortDir === 1 ? 'sorted-asc' : 'sorted-desc');
      apply();
    });
  });
}

/* ---------- Model page ---------- */

function renderModelPage(modelSlug, year) {
  const profiles = DATA.vehicles.filter(v => v.modelSlug === modelSlug).sort((a, b) => a.year - b.year);
  if (!profiles.length) {
    app.innerHTML = `<p class="error">Model not found. <a href="#/">Back to models</a></p>`;
    return;
  }
  const vehicle = profiles.find(p => p.year === year) || profiles[0];

  app.innerHTML = `
    <section class="model-page">
      <p class="eyebrow"><a href="#/">Car</a> / <a href="#/">${vehicle.make}</a> / ${vehicle.model}</p>
      <div class="model-page__head">
        <div>
          <h1>${vehicle.title}</h1>
          <p class="scope">${vehicle.scope}</p>
        </div>
        ${profiles.length > 1 ? yearTabs(profiles, vehicle) : ''}
      </div>

      ${statStrip(vehicle)}

      <section class="charts-row">
        <div class="chart-card">
          <h3>MSRP by grade</h3>
          <div class="chart-wrap"><canvas id="chartPrice"></canvas></div>
        </div>
        <div class="chart-card">
          <h3>Fuel economy by grade (combined MPG)</h3>
          <div class="chart-wrap"><canvas id="chartMpg"></canvas></div>
        </div>
      </section>

      ${trimTable(vehicle)}
      ${featureMatrixSection(vehicle)}
      ${powertrainSection(vehicle)}
      ${standardEquipmentSection(vehicle)}
      ${highlightsSection(vehicle)}
      ${notesSection(vehicle)}
      ${sourcesSection(vehicle)}
    </section>
  `;

  wireYearTabs(profiles);
  wireTrimTableSort(vehicle);
  wireFeatureSearch();
  buildCharts(vehicle);
}

function yearTabs(profiles, active) {
  return `<div class="year-tabs" role="tablist">${profiles.map(p => `
    <button class="year-tab ${p.year === active.year ? 'is-active' : ''}" data-year="${p.year}" role="tab" aria-selected="${p.year === active.year}">${p.year}</button>`).join('')}</div>`;
}
function wireYearTabs(profiles) {
  document.querySelectorAll('.year-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      location.hash = `#/model/${profiles[0].modelSlug}/${btn.dataset.year}`;
    });
  });
}

function statStrip(vehicle) {
  const s = trimStats(vehicle);
  const dt = s.drivetrains.length > 1 ? 'FWD & AWD' : s.drivetrains[0];
  return `
  <section class="stat-strip">
    <div class="stat-tile"><span class="stat-label">Starting MSRP</span><span class="stat-value">${fmtUSD(s.priceMin)}</span></div>
    <div class="stat-tile"><span class="stat-label">Top trim MSRP</span><span class="stat-value">${fmtUSD(s.priceMax)}</span></div>
    <div class="stat-tile"><span class="stat-label">Best combined MPG</span><span class="stat-value">${s.mpgMax ?? '—'}</span></div>
    <div class="stat-tile"><span class="stat-label">Grades</span><span class="stat-value">${s.gradeCount}</span></div>
    <div class="stat-tile"><span class="stat-label">Drivetrain</span><span class="stat-value">${dt}</span></div>
  </section>`;
}

/* ---------- Trim table ---------- */

function trimTable(vehicle) {
  return `
  <section class="panel">
    <h2>Trim overview</h2>
    <div class="table-scroll">
      <table class="trim-table" id="trimTable">
        <thead>
          <tr>
            <th data-key="name">Trim</th>
            <th data-key="drivetrain">Drivetrain</th>
            <th data-key="msrp" class="num">MSRP</th>
            <th data-key="mpgCity" class="num">MPG city</th>
            <th data-key="mpgHwy" class="num">MPG hwy</th>
            <th data-key="mpgCombined" class="num">MPG comb.</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>${trimRows(vehicle.trims)}</tbody>
      </table>
    </div>
  </section>`;
}

function trimRows(trims) {
  return trims.map(t => `
    <tr>
      <td class="trim-name">${t.name}</td>
      <td>${t.drivetrain}</td>
      <td class="num">${fmtUSD(t.msrp)}</td>
      <td class="num">${t.mpgCity ?? '—'}</td>
      <td class="num">${t.mpgHwy ?? '—'}</td>
      <td class="num">${t.mpgCombined ?? '—'}</td>
      <td class="trim-note">${[t.blurb, t.awdNote].filter(Boolean).join(' · ')}</td>
    </tr>`).join('');
}

function wireTrimTableSort(vehicle) {
  const table = document.getElementById('trimTable');
  if (!table) return;
  let sortKey = null;
  let sortDir = 1;
  table.querySelectorAll('th[data-key]').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.key;
      sortDir = sortKey === key ? -sortDir : 1;
      sortKey = key;
      const sorted = [...vehicle.trims].sort((a, b) => {
        const av = a[key];
        const bv = b[key];
        if (av == null && bv == null) return 0;
        if (av == null) return 1;
        if (bv == null) return -1;
        if (typeof av === 'string') return av.localeCompare(bv) * sortDir;
        return (av - bv) * sortDir;
      });
      table.querySelector('tbody').innerHTML = trimRows(sorted);
      table.querySelectorAll('th[data-key]').forEach(h => h.classList.remove('sorted-asc', 'sorted-desc'));
      th.classList.add(sortDir === 1 ? 'sorted-asc' : 'sorted-desc');
    });
  });
}

/* ---------- Feature matrix ---------- */

function featureCell(v) {
  if (v === 'S') return `<span class="fcell fcell--standard" title="Standard"><span aria-hidden="true"></span><span class="sr-only">Standard</span></span>`;
  if (v === 'A') return `<span class="fcell fcell--available" title="Available"><span aria-hidden="true"></span><span class="sr-only">Available</span></span>`;
  if (v === '-') return `<span class="fcell fcell--none" title="Not offered"><span aria-hidden="true">–</span><span class="sr-only">Not offered</span></span>`;
  if (v === '?') return `<span class="fcell fcell--unknown" title="Unconfirmed — not documented in sources checked"><span aria-hidden="true">?</span><span class="sr-only">Unconfirmed</span></span>`;
  const m = v.match(/^(S|A)\s*\((.+)\)$/);
  if (m) {
    const isStandard = m[1] === 'S';
    return `<span class="fcell ${isStandard ? 'fcell--standard' : 'fcell--available'}" title="${isStandard ? 'Standard' : 'Available'}: ${m[2]}">
      <span aria-hidden="true"></span><span class="fcell__note">${m[2]}</span></span>`;
  }
  return `<span class="fcell">${v}</span>`;
}

function featureMatrixSection(vehicle) {
  const grades = vehicle.featureMatrix.grades;
  return `
  <section class="panel">
    <div class="panel__head">
      <h2>Full feature matrix</h2>
      <input type="search" id="featureSearch" placeholder="Search features…" aria-label="Search features">
    </div>
    <div class="fcell-legend">
      <span class="fcell-legend__item"><span class="fcell fcell--standard"><span aria-hidden="true"></span></span> Standard</span>
      <span class="fcell-legend__item"><span class="fcell fcell--available"><span aria-hidden="true"></span></span> Available</span>
      <span class="fcell-legend__item"><span class="fcell fcell--none"><span aria-hidden="true">–</span></span> Not offered</span>
      <span class="fcell-legend__item"><span class="fcell fcell--unknown"><span aria-hidden="true">?</span></span> Unconfirmed</span>
    </div>
    <div class="table-scroll table-scroll--matrix">
      <table class="feature-table" id="featureTable">
        <thead>
          <tr><th class="feature-col">Feature</th>${grades.map(g => `<th>${g}</th>`).join('')}</tr>
        </thead>
        <tbody>
          ${vehicle.featureMatrix.rows.map(r => `
            <tr data-feature="${r.feature.toLowerCase()}">
              <td class="feature-col">${r.feature}</td>
              ${r.values.map(v => `<td>${featureCell(v)}</td>`).join('')}
            </tr>`).join('')}
        </tbody>
      </table>
    </div>
  </section>`;
}

function wireFeatureSearch() {
  const input = document.getElementById('featureSearch');
  if (!input) return;
  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();
    document.querySelectorAll('#featureTable tbody tr').forEach(tr => {
      tr.style.display = !q || tr.dataset.feature.includes(q) ? '' : 'none';
    });
  });
}

/* ---------- Powertrain / equipment / highlights / notes / sources ---------- */

function powertrainSection(vehicle) {
  const hasTrims = vehicle.powertrains.some(p => p.trims);
  return `
  <section class="panel">
    <h2>Powertrain &amp; performance</h2>
    <div class="table-scroll">
      <table class="plain-table">
        <thead><tr><th>System</th>${hasTrims ? '<th>Trims</th>' : ''}<th>Engine / transmission</th><th>Output</th><th>Drivetrain availability</th></tr></thead>
        <tbody>
          ${vehicle.powertrains.map(p => `<tr><td>${p.system}</td>${hasTrims ? `<td>${p.trims || '—'}</td>` : ''}<td>${p.engine}</td><td>${p.output}</td><td>${p.availability}</td></tr>`).join('')}
        </tbody>
      </table>
    </div>
    ${vehicle.powertrainNotes?.length ? `<ul class="note-list" style="margin-top: var(--space-4)">${vehicle.powertrainNotes.map(n => `<li>${n}</li>`).join('')}</ul>` : ''}
  </section>`;
}

function standardEquipmentSection(vehicle) {
  return `
  <section class="panel">
    <h2>Standard on every trim</h2>
    <ul class="equipment-list">${vehicle.standardEquipment.map(e => `<li>${e}</li>`).join('')}</ul>
  </section>`;
}

function highlightsSection(vehicle) {
  let body = '';
  if (vehicle.highlights?.length) {
    body += `<div class="highlight-grid">${vehicle.highlights.map(h => `
      <div class="highlight-card"><h3>${h.grade}</h3><p>${h.text}</p></div>`).join('')}</div>`;
  }
  if (vehicle.progression?.length) {
    body += `<ul class="progression-list" style="${vehicle.highlights?.length ? 'margin-top: var(--space-4)' : ''}">${vehicle.progression.map(p => `<li>${p}</li>`).join('')}</ul>`;
  }
  if (vehicle.specialEditions?.length) {
    body += `<div style="display:flex; flex-direction:column; gap: var(--space-3); margin-top: ${(vehicle.highlights?.length || vehicle.progression?.length) ? 'var(--space-4)' : '0'}">
      ${vehicle.specialEditions.map(se => `<div class="callout callout--accent"><h3>${se.name}</h3><p>${se.text}</p></div>`).join('')}
    </div>`;
  }
  if (!body) return '';
  return `<section class="panel"><h2>Buying guide</h2>${body}</section>`;
}

function notesSection(vehicle) {
  if (!vehicle.notes?.length) return '';
  return `
  <section class="panel">
    <h2>Good to know</h2>
    <ul class="note-list note-list--callout">${vehicle.notes.map(n => `<li>${n}</li>`).join('')}</ul>
  </section>`;
}

function sourcesSection(vehicle) {
  return `
  <section class="panel panel--footer">
    <h2>Sources</h2>
    <ul class="source-list">${vehicle.sources.map(s => `<li><a href="${s.url}" target="_blank" rel="noopener">${s.label}</a></li>`).join('')}</ul>
    <p class="researched">Researched ${vehicle.researched}. <a href="${vehicle.sourceFile}" target="_blank">View source notes (.md)</a></p>
  </section>`;
}

/* ---------- Charts ---------- */

function gradeDrivetrainSeries(vehicle, valueFn) {
  const grades = vehicle.featureMatrix.grades;
  const fwd = grades.map(g => {
    const t = vehicle.trims.find(t => t.grade === g && t.drivetrain === 'FWD');
    return t ? valueFn(t) : null;
  });
  const awd = grades.map(g => {
    const t = vehicle.trims.find(t => t.grade === g && t.drivetrain === 'AWD');
    return t ? valueFn(t) : null;
  });
  return { grades, fwd, awd, hasFwd: fwd.some(v => v != null), hasAwd: awd.some(v => v != null) };
}

function barDataset(label, data, color) {
  return {
    label,
    data,
    backgroundColor: color,
    borderRadius: { topLeft: 4, topRight: 4, bottomLeft: 0, bottomRight: 0 },
    borderSkipped: false,
    maxBarThickness: 24,
    categoryPercentage: 0.7,
    barPercentage: 0.85,
  };
}

function makeBarChart(canvasId, series, fmt) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;

  const seriesFwd = cssVar('--series-fwd');
  const seriesAwd = cssVar('--series-awd');
  const textSecondary = cssVar('--text-secondary');
  const muted = cssVar('--text-muted');
  const gridline = cssVar('--gridline');
  const baseline = cssVar('--baseline');
  const surface = cssVar('--surface-2');
  const textPrimary = cssVar('--text-primary');
  const border = cssVar('--border');

  const datasets = [];
  if (series.hasFwd) datasets.push(barDataset('FWD', series.fwd, seriesFwd));
  if (series.hasAwd) datasets.push(barDataset('AWD', series.awd, seriesAwd));
  if (!datasets.length) datasets.push(barDataset('MSRP', series.fwd, seriesFwd));

  const font = { family: 'Inter, system-ui, sans-serif', size: 12 };

  return new Chart(ctx, {
    type: 'bar',
    data: { labels: series.grades, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          display: datasets.length > 1,
          position: 'top',
          align: 'end',
          labels: { color: textSecondary, usePointStyle: true, pointStyle: 'circle', boxWidth: 8, boxHeight: 8, font },
        },
        tooltip: {
          backgroundColor: surface,
          titleColor: textPrimary,
          bodyColor: textSecondary,
          borderColor: border,
          borderWidth: 1,
          padding: 10,
          cornerRadius: 8,
          displayColors: datasets.length > 1,
          callbacks: {
            label: (c) => (c.raw == null ? undefined : `${c.dataset.label}: ${fmt.valueFormatter(c.raw)}`),
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          border: { color: baseline },
          ticks: { color: muted, font },
        },
        y: {
          beginAtZero: true,
          grid: { color: gridline },
          border: { display: false },
          ticks: { color: muted, font: { ...font, size: 11 }, callback: (v) => fmt.axisFormatter(v) },
        },
      },
    },
  });
}

function buildCharts(vehicle) {
  const priceSeries = gradeDrivetrainSeries(vehicle, t => t.msrp);
  const mpgSeries = gradeDrivetrainSeries(vehicle, avgMpg);

  chartInstances.price = makeBarChart('chartPrice', priceSeries, {
    valueFormatter: v => fmtUSD(v),
    axisFormatter: v => `$${v / 1000}k`,
  });
  chartInstances.mpg = makeBarChart('chartMpg', mpgSeries, {
    valueFormatter: v => `${v} MPG`,
    axisFormatter: v => `${v}`,
  });
}

/* ---------- Theme ---------- */

const THEME_ICONS = {
  system: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/></svg>',
  light: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
  dark: '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M20.7 14.9A9 9 0 1 1 9.1 3.3a7 7 0 0 0 11.6 11.6Z"/></svg>',
};

function applyTheme(mode) {
  if (mode === 'system') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', mode);
  localStorage.setItem('vh-theme', mode);
}

function updateThemeIcon(mode) {
  const btn = document.getElementById('themeToggle');
  btn.innerHTML = THEME_ICONS[mode];
  btn.title = `Theme: ${mode}`;
}

function setupHeaderControls() {
  let stored = 'system';
  try { stored = localStorage.getItem('vh-theme') || 'system'; } catch (e) { /* private mode */ }
  applyTheme(stored);
  updateThemeIcon(stored);

  document.getElementById('themeToggle').addEventListener('click', () => {
    const order = ['system', 'light', 'dark'];
    let current = 'system';
    try { current = localStorage.getItem('vh-theme') || 'system'; } catch (e) { /* private mode */ }
    const next = order[(order.indexOf(current) + 1) % order.length];
    applyTheme(next);
    updateThemeIcon(next);
    router();
  });

  const makeSelect = document.getElementById('makeSelect');
  makeSelect.value = getCurrentMake();
  makeSelect.addEventListener('change', () => {
    setCurrentMake(makeSelect.value);
    location.hash = '#/';
    router();
  });
}

/* ---------- Init ---------- */

async function init() {
  setupHeaderControls();
  try {
    const res = await fetch(DATA_URL);
    DATA = await res.json();
  } catch (e) {
    app.innerHTML = `<p class="error">Could not load vehicle data. If you're viewing this file directly from disk, run a local server instead (e.g. <code>python -m http.server</code>) rather than opening index.html directly.</p>`;
    return;
  }
  router();
}

window.addEventListener('hashchange', router);
document.addEventListener('DOMContentLoaded', init);
