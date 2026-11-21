"use strict";
const byId = (id) => document.getElementById(id);
const rate = value => value == null ? 'N/A' : `${(value * 100).toFixed(1)}%`;
const number = (v) => Number(v ?? 0).toLocaleString("en-US");
const safe = (v) => String(v ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const api = async (path, options) => { const res = await fetch(path, options); if (!res.ok) { let message = `${res.status} ${res.statusText}`; try { const detail = await res.json(); message = detail.detail ?? message; } catch {} throw new Error(message); } return res.json(); };
let map, layer, lastGeojson, selectionRequest = 0, qualityRequest = 0, qualityOffset = 0;
let participants = [], trajectoryFlags = [];
const qualityPageSize = 10;
const trajectoryColor = '#5be1c3';

function initializeMap() {
  if (typeof L === "undefined") { byId('map').textContent = 'Map rendering unavailable. You can still view and download the data.'; return; }
  byId('map').replaceChildren();
  map = L.map('map', { zoomControl:false }).setView([34.05, -118.25], 11);
  L.control.zoom({position:'topright'}).addTo(map);
  if (new URLSearchParams(location.search).get('basemap') !== 'none') L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OpenStreetMap © CARTO', subdomains:'abcd', maxZoom:18
  }).addTo(map);
  layer = L.featureGroup().addTo(map);
}
function selectParticipantOptions() {
  const select = byId('participant');
  select.innerHTML = participants.map(p => `<option value="${safe(p.participant_id)}">${safe(p.participant_id)} · ${number(p.observations)} points</option>`).join('');
  if (!participants.length) select.innerHTML = '<option value="">No data yet — import a CSV</option>';
}
function updateDays() {
  const p = participants.find(p => p.participant_id === byId('participant').value);
  const days = (p?.dates ?? []).slice();
  byId('day').innerHTML = '<option value="">All available dates</option>' + days.map(d => `<option value="${safe(d)}">${safe(d)}</option>`).join('');
}
function renderGeojson(data, fit = true) {
  lastGeojson = data;
  if (!map) return;
  layer.clearLayers();
  if (!data.features.length) { map.setView([34.05,-118.25],11); return; }
  const enabled = new Set(Array.from(document.querySelectorAll('#layer-options input:checked'), input => input.value));
  const styled = L.geoJSON(data, {
    filter: feature => enabled.has(['start', 'end'].includes(feature.properties.kind) ? 'markers' : feature.properties.kind),
    style: feature => {
      const kind = feature.properties.kind;
      if (kind === 'activity_area') {
        return {className:'activity-area',color:'#59beac',weight:1.2,fillColor:'#1c9e84',fillOpacity:.14,dashArray:'5 4'};
      }
      if (kind === 'route') return {className:'gps-route',color:trajectoryColor,weight:3,opacity:.92};
      return {};
    },
    pointToLayer: (feature, position) => {
      const kind = feature.properties.kind;
      const fill = {stay:'#ffb870', start:'#5be1c3', end:'#9fb8ff'}[kind];
      const radius = {stay:5, start:8, end:11}[kind];
      return L.circleMarker(position, {className:`${kind}-marker`, radius,
        color:fill,fillColor:fill,fillOpacity:kind === 'stay' ? 1 : 0,weight:2});
    },
    onEachFeature: (f,l) => {
      const p=f.properties;
      if(p.kind === 'stay') l.bindPopup(`<b>Dwell cluster</b><p>${p.duration_minutes} min · ${p.samples} readings</p><small>${safe(p.start_utc)}</small>`);
      else if(p.kind === 'activity_area') l.bindPopup(`<b>Activity area</b><p>${p.area_km2} km² · projected convex hull</p>`);
      else if(p.kind === 'start' || p.kind === 'end') l.bindPopup(`<b>${p.kind === 'start' ? 'Start' : 'End'} observation</b><p>${safe(p.timestamp_utc)}</p>`);
    }
  });
  layer.addLayer(styled);
  styled.eachLayer(item => {
    if (['start', 'end'].includes(item.feature.properties.kind)) item.bringToFront();
  });
  const bounds = styled.getBounds();
  if(fit && bounds.isValid()) map.fitBounds(bounds.pad(.18), {maxZoom:14});
}
function renderTrajectoryFlags() {
  const selected = byId('trajectory-reason').value;
  const flags = trajectoryFlags.filter(row => !selected || row.quality_flags.includes(selected));
  byId('trajectory-status').textContent = flags.length ?
    `${number(flags.length)} flagged observations in the first 250 samples` :
    'No matching flags in the first 250 samples.';
  byId('trajectory-flags').innerHTML = flags.map(row =>
    `<li>${safe(row.timestamp_utc)} · ${safe(row.quality_flags.join(', ').replaceAll('_', ' '))}
      ${row.incoming_segment_excluded ? ' (incoming segment excluded)' : ''}</li>`).join('');
}

async function loadSelected() {
  const request = ++selectionRequest;
  const pid = byId('participant').value;
  if (!pid) {
    byId('analytics-context').textContent = 'Import a synthetic CSV to view daily metrics.';
    byId('daily-metrics').replaceChildren();
    byId('daily-chart').replaceChildren();
    byId('map-status').textContent = 'No trajectories available.';
    trajectoryFlags = [];
    renderTrajectoryFlags();
    renderGeojson({features: []});
    return;
  }
  byId('map-status').textContent = 'Loading trajectory…';
  byId('trajectory-status').textContent = 'Loading flags…';
  byId('trajectory-flags').replaceChildren();
  const d = byId('day').value;
  const qs = d ? `?date=${encodeURIComponent(d)}` : '';
  const qualityQuery = new URLSearchParams({include_quality: 'true'});
  if (d) qualityQuery.set('date', d);
  try {
    const [daily, geo, stays, observations] = await Promise.all([
      api(`/api/participants/${encodeURIComponent(pid)}/daily`),
      api(`/api/participants/${encodeURIComponent(pid)}/geojson${qs}`),
      api(`/api/participants/${encodeURIComponent(pid)}/stays${qs}`),
      api(`/api/participants/${encodeURIComponent(pid)}/observations?${qualityQuery}`)
    ]);
    if (request !== selectionRequest) return;
    trajectoryFlags = observations.filter(row => row.quality_flags.length);
    renderTrajectoryFlags();
    const selected = d ? daily.filter(r => r.date === d) : daily;
    const sum = (key) => selected.reduce((v,r) => v+(r[key]||0), 0);
    byId('selected-samples').textContent = number(sum('samples'));
    byId('selected-distance').textContent = `${sum('distance_km').toFixed(2)} km`;
    byId('selected-steps').textContent = number(sum('steps'));
    byId('selected-stays').textContent = number(stays.length);
    byId('selected-anomalies').textContent = number(sum('speed_outliers'));
    byId('analytics-context').textContent = `${pid} · ${d || 'All study dates'}`;
    const maximum = selected.reduce((previous, row) => Math.max(previous, row.distance_km), 0);
    byId('daily-chart').innerHTML = selected.length && selected.length <= 31 ?
      '<p>Daily distance (km)</p>' + selected.map(row =>
        `<div class="chart-row"><span>${safe(row.date)}</span>
          <meter min="0" max="${maximum || 1}" value="${row.distance_km}" aria-label="Distance for ${safe(row.date)}"></meter>
          <span>${row.distance_km.toFixed(3)}</span></div>`).join('') : '';
    byId('daily-metrics').innerHTML = selected.map(row => `<tr>
      <th scope="row">${safe(row.date)}</th><td>${number(row.samples)}</td><td>${number(row.steps)}</td>
      <td>${row.distance_km.toFixed(3)}</td><td>${row.avg_heart_rate_bpm ?? '—'}</td>
      <td>${rate(row.observed_validity_rate)}</td><td>${rate(row.expected_sampling_coverage)}</td><td>${number(row.speed_outliers)}</td>
      <td>${number(row.sampling_gaps)}</td><td>${number(row.repeated_coordinates)}</td></tr>`).join('');
    byId('map-status').textContent = geo.warnings?.join(' ') || (geo.features.length ? '' : 'No map features for this selection.');
    byId('method-version').textContent = `Algorithms v${geo.metadata.algorithm_version} · study time zone ${geo.metadata.study_timezone}`;
    renderGeojson(geo);
  } catch(err) {
    if (request === selectionRequest) {
      byId('map-status').textContent = `Could not load trajectory: ${err.message}`;
      byId('analytics-context').textContent = 'Daily metrics unavailable.';
      trajectoryFlags = [];
      byId('trajectory-status').textContent = 'Trajectory flags unavailable.';
      byId('daily-metrics').replaceChildren();
      byId('daily-chart').replaceChildren();
      renderGeojson({features: []});
    }
  }
}
async function loadImports() {
  const list = await api('/api/imports');
  byId('imports-list').innerHTML = list.length ? list.slice(0,5).map(item => `<div class="import-row"><div><b>${safe(item.filename)}</b><small>${safe(item.created_at.slice(0,16).replace('T',' '))} UTC · ${item.rejected} rejected / ${item.duplicates} duplicate</small></div><span>+${number(item.accepted)}</span></div>`).join('') : '<p>No imports yet</p>';
  byId('quality-batch').innerHTML = list.map(item =>
    `<option value="${item.id}">#${item.id} · ${safe(item.filename)} (${item.rejected} rejected)</option>`).join('');
  await loadQuality('batch');
}
async function loadQuality(reset = false) {
  const request = ++qualityRequest;
  if (reset) qualityOffset = 0;
  const batch = byId('quality-batch').value;
  const reason = reset === 'batch' ? '' : byId('quality-reason').value;
  const status = byId('quality-status');
  byId('quality-records').replaceChildren();
  byId('quality-prev').hidden = byId('quality-next').hidden = true;
  if (!batch) { status.textContent = 'No import batches.'; return; }
  const params = new URLSearchParams({batch_id: batch, limit: qualityPageSize, offset: qualityOffset, reason});
  status.textContent = 'Loading diagnostics…';
  try {
    const result = await api(`/api/imports?${params}`);
    if (request !== qualityRequest) return;
    byId('quality-reason').innerHTML = '<option value="">All reasons</option>' +
      result.categories.map(item => `<option value="${safe(item.reason)}">${safe(item.reason)} (${item.count})</option>`).join('');
    byId('quality-reason').value = reason;
    byId('quality-records').innerHTML = result.records.map(record => `<li>Row ${record.row} · ${safe(record.reason)}</li>`).join('');
    status.textContent = result.total ? `${qualityOffset + 1}–${qualityOffset + result.records.length} of ${result.total} rejected rows` : 'No recorded diagnostics in this selection.';
    byId('quality-prev').hidden = qualityOffset === 0;
    byId('quality-next').hidden = qualityOffset + result.records.length >= result.total;
  } catch (error) {
    if (request === qualityRequest) status.textContent = error.message;
  }
}
async function refreshAll() {
  const [stats,people] = await Promise.all([api('/api/summary'),api('/api/participants')]);
  byId('metric-participants').textContent=number(stats.participants);
  byId('metric-observations').textContent=number(stats.observations);
  byId('metric-distance').textContent=stats.distance_km.toFixed(2);
  byId('metric-days').textContent=number(stats.participant_days);
  byId('quality-outliers').textContent=number(stats.speed_outliers);
  byId('study-dates').textContent = stats.first_study_date ?
    `Study dates ${stats.first_study_date} to ${stats.last_study_date} · ${number(stats.rejected_rows)} rejected upload rows` :
    'No study observations yet.';
  const saved = byId('participant').value;
  participants = people;
  selectParticipantOptions();
  if (people.some(p=>p.participant_id === saved)) byId('participant').value=saved;
  const savedDate = byId('day').value;
  updateDays();
  if (Array.from(byId('day').options).some(option => option.value === savedDate)) byId('day').value = savedDate;
  await Promise.all([loadSelected(),loadImports()]);
}
async function boot() {
  initializeMap();
  try {const state=await api('/api/health');byId('health').textContent=`API ONLINE · ${state.version}`; byId('restore-demo').hidden = !state.demo_restore_enabled; byId('upload-form').hidden = state.read_only; if (state.read_only) { byId('import-result').textContent = 'CSV upload is disabled in this hosted demo.'; } byId('day-label').textContent = `Study date (${state.study_timezone})`; await refreshAll();}
  catch(err){byId('health').textContent=`API OFFLINE · ${err.message}`; byId('health').style.color='#ff9a9a';}
}
byId('participant').addEventListener('change',()=>{updateDays();loadSelected();});
byId('day').addEventListener('change',loadSelected);
byId('layer-options').addEventListener('change', () => { if (lastGeojson) renderGeojson(lastGeojson, false); });
byId('trajectory-reason').addEventListener('change', renderTrajectoryFlags);
byId('quality-batch').addEventListener('change', () => loadQuality('batch'));
byId('quality-reason').addEventListener('change', () => loadQuality(true));
byId('quality-prev').addEventListener('click', () => { qualityOffset -= qualityPageSize; loadQuality(); });
byId('quality-next').addEventListener('click', () => { qualityOffset += qualityPageSize; loadQuality(); });
byId('export-btn').addEventListener('click', () => {
  const pid = byId('participant').value;
  if (!pid) return;
  const params = new URLSearchParams();
  const day = byId('day').value;
  if (day) params.set('date', day);
  const format = byId('export-format').value;
  let path = 'geojson';
  if (format === 'observations' || format === 'daily') {
    path = 'export.csv';
    params.set('dataset', format);
  } else if (format === 'metadata') {
    params.set('metadata_only', 'true');
  } else {
    params.set('download', 'true');
    if (format !== 'geojson') params.set('layer', format);
  }
  location.href = `/api/participants/${encodeURIComponent(pid)}/${path}?${params}`;
});
const input = byId('csv-file');
async function previewFile() {
  const file = input.files[0];
  const preview = byId('import-preview');
  preview.hidden = true;
  if (!file) return;
  try {
    const snippet = await file.slice(0, 4096).text();
    if (input.files[0] !== file) return;
    preview.textContent = 'File preview (first lines)\n' + snippet.split(/\r?\n/).slice(0, 5).join('\n');
    preview.hidden = false;
  } catch {
    preview.textContent = 'Preview unavailable.';
    preview.hidden = false;
  }
}
input.addEventListener('change', previewFile);
const uploadZone = document.querySelector('.upload-zone');
uploadZone.addEventListener('dragover', event => { event.preventDefault(); uploadZone.classList.add('dragging'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragging'));
uploadZone.addEventListener('drop', event => {
  event.preventDefault();
  uploadZone.classList.remove('dragging');
  if (!event.dataTransfer.files.length) return;
  const selection = new DataTransfer();
  selection.items.add(event.dataTransfer.files[0]);
  input.files = selection.files;
  previewFile();
});
byId('upload-form').addEventListener('submit',async(e)=>{
  e.preventDefault();const file=byId('csv-file').files[0];if(!file)return;
  const result=byId('import-result');result.classList.remove('error');result.textContent='Checking records…';
  const button=e.target.querySelector('button');button.disabled=true;
  try{const form=new FormData();form.append('file',file);const report=await api('/api/import',{method:'POST',body:form});
      result.textContent=`Accepted: ${report.accepted} · duplicates: ${report.duplicates} · rejected: ${report.rejected}`+(report.errors.length?'\nFirst rejected rows: '+report.errors.map(x=>`${x.row} (${x.reason})`).join('; '):'');
      await refreshAll();
  }catch(err){result.classList.add('error');result.textContent=err.message;}
  finally{button.disabled=false;}
});
byId('restore-demo').addEventListener('click', async event => {
  if (!window.confirm('Replace this marked demo database with the canonical 366 synthetic observations? Imported demo records and import history will be removed.')) return;
  const result = byId('import-result');
  const button = event.currentTarget;
  button.disabled = true;
  result.classList.remove('error');
  result.textContent = 'Restoring demo…';
  try {
    const report = await api('/api/demo/restore', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({confirmation:'RESTORE SYNTHETIC DEMO'})});
    result.textContent = `Restored ${report.accepted} synthetic observations.`;
    await refreshAll();
  } catch (error) {
    result.classList.add('error');
    result.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

boot();
