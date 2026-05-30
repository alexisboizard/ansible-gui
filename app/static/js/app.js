'use strict';

// ── Theme ────────────────────────────────────────────────────────────────────

function initTheme() {
  const saved = localStorage.getItem('theme');
  if (saved) {
    applyTheme(saved);
  } else {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    applyTheme(prefersDark ? 'dark' : 'light');
  }
}

function applyTheme(theme) {
  const html = document.documentElement;
  html.classList.remove('dark-theme', 'light-theme');
  html.classList.add(theme === 'light' ? 'light-theme' : 'dark-theme');
  localStorage.setItem('theme', theme);
  updateThemeIcon();
}

function toggleTheme() {
  const isLight = document.documentElement.classList.contains('light-theme');
  applyTheme(isLight ? 'dark' : 'light');
}

function updateThemeIcon() {
  const isLight = document.documentElement.classList.contains('light-theme');
  const btn = document.getElementById('theme-toggle');
  if (!btn) return;
  btn.innerHTML = isLight
    ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`
    : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`;
}

// ── Navigation ────────────────────────────────────────────────────────────────

function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));

  const page = document.getElementById('page-' + name);
  if (page) page.classList.add('active');

  const link = document.querySelector(`.sidebar-link[data-page="${name}"]`);
  if (link) link.classList.add('active');

  document.getElementById('topbar-title').textContent =
    link ? link.querySelector('span')?.textContent || name : name;

  if (name === 'dashboard') loadDashboard();
  if (name === 'inventory') loadHosts();
  if (name === 'variables') loadVariables();
  if (name === 'playbooks') loadPlaybooks();
  if (name === 'roles') loadRoles();
  if (name === 'dynamic-inventory') loadDynamicInventories();
  if (name === 'executions') loadExecutions();
  if (name === 'schedules') loadSchedules();
  if (name === 'settings') loadSettings();
  if (name === 'users') loadUsers();
  if (name === 'audit') loadAudit();
}

// ── Toast ─────────────────────────────────────────────────────────────────────

function toast(msg, type = 'info') {
  const icons = { success: '✓', error: '✗', info: 'ℹ' };
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span class="toast-icon">${icons[type] || icons.info}</span><span class="toast-message">${msg}</span>`;
  document.getElementById('toast-container').appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

// ── API ───────────────────────────────────────────────────────────────────────

async function api(method, url, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(url, opts);
  if (res.status === 401) { location.href = '/login'; throw new Error('Unauthorized'); }
  return res;
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

let chartTrend = null;
let chartRatio = null;
let chartPlaybooks = null;

async function loadDashboard() {
  const res = await api('GET', '/api/dashboard');
  const data = await res.json();
  document.getElementById('stat-hosts').textContent = data.total_hosts;
  document.getElementById('stat-reachable').textContent = data.reachable_hosts;
  document.getElementById('stat-playbooks').textContent = data.total_playbooks;
  document.getElementById('stat-executions').textContent = data.total_executions;

  // Concurrency info
  document.getElementById('stat-running').textContent = data.running_executions ?? '—';
  document.getElementById('stat-max-concurrent').textContent = data.max_concurrent_executions ?? '—';

  const tbody = document.getElementById('recent-executions-tbody');
  tbody.innerHTML = '';
  for (const e of (data.recent_executions || [])) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${e.playbook_name || '-'}</td>
      <td><span class="badge ${statusBadge(e.status)}">${e.status}</span></td>
      <td>${e.triggered_by || '-'}</td>
      <td>${fmtDate(e.started_at)}</td>
    `;
    tbody.appendChild(tr);
  }

  // Load stats for charts
  loadStats();
}

async function loadStats() {
  const res = await api('GET', '/api/stats');
  if (!res.ok) return;
  const stats = await res.json();

  renderTrendChart(stats.executions_per_day);
  renderRatioChart(stats.success_count, stats.failed_count, stats.other_count);
  renderTopPlaybooksChart(stats.top_playbooks);
}

function getChartColors() {
  const isDark = document.documentElement.classList.contains('dark-theme');
  return {
    text: isDark ? '#a0aec0' : '#4a5568',
    grid: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
    success: '#27d96c',
    danger: '#f5365c',
    info: '#11cdef',
    primary: '#6c63ff',
    warning: '#fb8c00',
  };
}

function renderTrendChart(data) {
  const ctx = document.getElementById('chart-executions-trend');
  if (!ctx) return;

  const colors = getChartColors();
  const labels = data.map(d => d.date.slice(5)); // MM-DD format
  const totals = data.map(d => d.total);
  const successes = data.map(d => d.success);
  const failures = data.map(d => d.failed);

  if (chartTrend) chartTrend.destroy();

  chartTrend = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Total',
          data: totals,
          borderColor: colors.primary,
          backgroundColor: colors.primary + '33',
          fill: true,
          tension: 0.3,
        },
        {
          label: 'Success',
          data: successes,
          borderColor: colors.success,
          backgroundColor: 'transparent',
          tension: 0.3,
        },
        {
          label: 'Failed',
          data: failures,
          borderColor: colors.danger,
          backgroundColor: 'transparent',
          tension: 0.3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          labels: { color: colors.text, usePointStyle: true, pointStyle: 'circle' },
        },
      },
      scales: {
        x: {
          ticks: { color: colors.text, maxRotation: 45, minRotation: 45 },
          grid: { color: colors.grid },
        },
        y: {
          beginAtZero: true,
          ticks: { color: colors.text, stepSize: 1 },
          grid: { color: colors.grid },
        },
      },
    },
  });
}

function renderRatioChart(success, failed, other) {
  const ctx = document.getElementById('chart-success-ratio');
  if (!ctx) return;

  const colors = getChartColors();

  if (chartRatio) chartRatio.destroy();

  const total = success + failed + other;
  if (total === 0) {
    // No data - show placeholder
    chartRatio = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['No data'],
        datasets: [{ data: [1], backgroundColor: [colors.grid] }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
      },
    });
    return;
  }

  chartRatio = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Success', 'Failed', 'Other'],
      datasets: [{
        data: [success, failed, other],
        backgroundColor: [colors.success, colors.danger, colors.warning],
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '60%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: colors.text, usePointStyle: true, pointStyle: 'circle' },
        },
      },
    },
  });
}

function renderTopPlaybooksChart(data) {
  const ctx = document.getElementById('chart-top-playbooks');
  if (!ctx) return;

  const colors = getChartColors();

  if (chartPlaybooks) chartPlaybooks.destroy();

  if (!data || data.length === 0) {
    chartPlaybooks = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['No data'],
        datasets: [{ data: [0], backgroundColor: [colors.grid] }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
      },
    });
    return;
  }

  const labels = data.map(d => d.name.length > 20 ? d.name.slice(0, 20) + '...' : d.name);
  const counts = data.map(d => d.count);
  const barColors = [colors.primary, colors.info, colors.success, colors.warning, colors.danger];

  chartPlaybooks = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Executions',
        data: counts,
        backgroundColor: barColors.slice(0, data.length),
        borderRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: {
          beginAtZero: true,
          ticks: { color: colors.text, stepSize: 1 },
          grid: { color: colors.grid },
        },
        y: {
          ticks: { color: colors.text },
          grid: { display: false },
        },
      },
    },
  });
}

// ── Hosts ─────────────────────────────────────────────────────────────────────

let hostsData = [];

async function loadHosts(q = '') {
  const url = q ? `/api/hosts?q=${encodeURIComponent(q)}` : '/api/hosts';
  const res = await api('GET', url);
  hostsData = await res.json();
  renderHosts();
}

function renderHosts() {
  const tbody = document.getElementById('hosts-tbody');
  tbody.innerHTML = '';

  if (hostsData.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
      <p>No hosts found. Add your first host to get started.</p></div></td></tr>`;
    return;
  }

  for (const h of hostsData) {
    const groups = (h.groups || '').split(',').filter(Boolean);
    const groupTags = groups.map(g => `<span class="group-tag">${g.trim()}</span>`).join('');
    const pingDot = h.reachable === true
      ? `<span class="ping-dot reachable"></span>`
      : h.reachable === false
        ? `<span class="ping-dot unreachable"></span>`
        : `<span class="ping-dot unknown"></span>`;

    const latency = h.ping_latency ? `<span style="font-size:11px;color:var(--text-muted)">${h.ping_latency}ms</span>` : '';

    const osBadge = h.os_type === 'windows'
      ? `<span class="os-badge windows">⊞ Windows</span>`
      : `<span class="os-badge linux">🐧 Linux</span>`;

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${pingDot} ${latency}</td>
      <td><strong>${h.name}</strong></td>
      <td style="font-family:monospace;font-size:12px">${h.address}</td>
      <td>${osBadge}</td>
      <td><div class="group-tags">${groupTags || '<span style="color:var(--text-muted)">—</span>'}</div></td>
      <td>${h.last_ping ? fmtDate(h.last_ping) : '<span style="color:var(--text-muted)">Never</span>'}</td>
      <td>
        <div style="display:flex;gap:4px">
          ${isAdmin() ? `
          <button class="btn btn-icon btn-sm" title="Edit" onclick="openHostModal(${h.id})">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button class="btn btn-icon btn-sm" title="Delete" onclick="deleteHost(${h.id})" style="color:var(--danger);border-color:rgba(245,54,92,0.3)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
          </button>` : '<span style="color:var(--text-muted);font-size:11px">—</span>'}
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  }
}

function onOsTypeChange() {
  const isWindows = document.getElementById('host-os').value === 'windows';
  document.getElementById('host-port-group').style.display = isWindows ? '' : 'none';
}

function openHostModal(id = null) {
  const host = id ? hostsData.find(h => h.id === id) : null;
  document.getElementById('host-modal-title').textContent = host ? 'Edit Host' : 'Add Host';
  document.getElementById('host-id').value = host ? host.id : '';
  document.getElementById('host-name').value = host ? host.name : '';
  document.getElementById('host-address').value = host ? host.address : '';
  document.getElementById('host-groups').value = host ? (host.groups || '') : '';
  document.getElementById('host-os').value = host ? (host.os_type || 'linux') : 'linux';

  // Extract known fields from variables, leave the rest in the JSON box
  let vars = {};
  if (host) { try { vars = JSON.parse(host.variables || '{}'); } catch(e) {} }

  document.getElementById('host-username').value = vars.ansible_user || '';
  document.getElementById('host-password').value = vars.ansible_password || '';
  document.getElementById('host-port').value = vars.ansible_port || '';

  // Remove fields that now have dedicated inputs before showing in JSON box
  const extra = Object.assign({}, vars);
  delete extra.ansible_user;
  delete extra.ansible_password;
  delete extra.ansible_port;
  // For Windows, keep winrm vars visible in extra if present
  document.getElementById('host-vars').value = Object.keys(extra).length
    ? JSON.stringify(extra, null, 2)
    : '';

  onOsTypeChange();
  showModal('host-modal');
}

async function saveHost() {
  const id = document.getElementById('host-id').value;
  const osType = document.getElementById('host-os').value;

  // Start with extra JSON vars
  let vars = {};
  const extraRaw = document.getElementById('host-vars').value.trim();
  if (extraRaw) {
    try { vars = JSON.parse(extraRaw); } catch(e) {
      toast('Invalid JSON in extra variables', 'error'); return;
    }
  }

  // Inject dedicated fields
  const username = document.getElementById('host-username').value.trim();
  const password = document.getElementById('host-password').value;
  const port = document.getElementById('host-port').value.trim();

  if (username) vars.ansible_user = username;
  if (password) vars.ansible_password = password;
  if (port) vars.ansible_port = parseInt(port);

  // Auto-inject WinRM settings for Windows if not already set
  if (osType === 'windows') {
    if (!vars.ansible_connection) vars.ansible_connection = 'winrm';
    if (!vars.ansible_winrm_transport) vars.ansible_winrm_transport = 'ntlm';
    if (!vars.ansible_shell_type) vars.ansible_shell_type = 'powershell';
    if (!vars.ansible_port) vars.ansible_port = 5985;
  }

  const data = {
    name: document.getElementById('host-name').value.trim(),
    address: document.getElementById('host-address').value.trim(),
    groups: document.getElementById('host-groups').value.trim(),
    os_type: osType,
    variables: vars,
  };

  if (!data.name || !data.address) { toast('Name and address are required', 'error'); return; }

  const res = id
    ? await api('PUT', `/api/hosts/${id}`, data)
    : await api('POST', '/api/hosts', data);

  if (res.ok) {
    toast(id ? 'Host updated' : 'Host created', 'success');
    closeModal('host-modal');
    loadHosts();
  } else {
    toast('Failed to save host', 'error');
  }
}

async function deleteHost(id) {
  if (!confirm('Delete this host?')) return;
  const res = await api('DELETE', `/api/hosts/${id}`);
  if (res.ok) { toast('Host deleted', 'success'); loadHosts(); }
  else { toast('Failed to delete host', 'error'); }
}

async function pingAllHosts() {
  const res = await api('POST', '/api/hosts/ping');
  if (res.ok) {
    toast('Ping started — refreshing in 5 seconds', 'info');
    setTimeout(() => loadHosts(), 5000);
  }
}

async function exportHosts() {
  window.location.href = '/api/hosts/export';
}

function openImportModal() {
  showModal('import-modal');
}

async function importHosts() {
  const fileInput = document.getElementById('import-file');
  if (!fileInput.files[0]) { toast('Select a CSV file first', 'error'); return; }
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  const res = await fetch('/api/hosts/import', { method: 'POST', body: formData });
  if (res.ok) {
    const data = await res.json();
    toast(`Imported ${data.imported} hosts`, 'success');
    closeModal('import-modal');
    loadHosts();
  } else {
    toast('Import failed', 'error');
  }
}

// ── Playbooks ─────────────────────────────────────────────────────────────────

let playbooksData = [];
let foldersData = [];
let activeFolderId = null; // null = All
let cmEditor = null;

const defaultPlaybook = `---
- name: My Playbook
  hosts: all
  gather_facts: true
  tasks:
    - name: Example task
      debug:
        msg: "Hello from Ansible GUI"
`;

async function loadPlaybooks() {
  const [pbRes, folderRes] = await Promise.all([
    api('GET', '/api/playbooks'),
    api('GET', '/api/folders'),
  ]);
  playbooksData = await pbRes.json();
  foldersData = await folderRes.json();
  renderFolders();
  renderPlaybooks();
}

function renderFolders() {
  const list = document.getElementById('folders-list');
  list.innerHTML = '';

  const allBtn = document.createElement('button');
  allBtn.className = `folder-item${activeFolderId === null ? ' active' : ''}`;
  allBtn.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
    <span class="folder-item-name">All Playbooks</span>
    <span style="font-size:11px;color:var(--text-muted);margin-left:auto">${playbooksData.length}</span>
  `;
  allBtn.onclick = () => { activeFolderId = null; renderFolders(); renderPlaybooks(); };
  list.appendChild(allBtn);

  const unfiled = playbooksData.filter(p => !p.folder_id);
  if (unfiled.length > 0) {
    const unfiledBtn = document.createElement('button');
    unfiledBtn.className = `folder-item${activeFolderId === 'unfiled' ? ' active' : ''}`;
    unfiledBtn.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
      <span class="folder-item-name">Unfiled</span>
      <span style="font-size:11px;color:var(--text-muted);margin-left:auto">${unfiled.length}</span>
    `;
    unfiledBtn.onclick = () => { activeFolderId = 'unfiled'; renderFolders(); renderPlaybooks(); };
    list.appendChild(unfiledBtn);
  }

  if (foldersData.length > 0) {
    const sep = document.createElement('div');
    sep.style.cssText = 'height:1px;background:var(--border-color);margin:6px 0';
    list.appendChild(sep);
  }

  for (const f of foldersData) {
    const count = playbooksData.filter(p => p.folder_id === f.id).length;
    const item = document.createElement('button');
    item.className = `folder-item${activeFolderId === f.id ? ' active' : ''}`;
    item.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
      <span class="folder-item-name">${f.name}</span>
      <span style="font-size:11px;color:var(--text-muted)">${count}</span>
      <div class="folder-item-actions">
        <button class="folder-action-btn" title="Rename" onclick="event.stopPropagation();openFolderModal(${f.id})">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
        </button>
        <button class="folder-action-btn" title="Delete" onclick="event.stopPropagation();deleteFolder(${f.id})" style="color:var(--danger)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M9 6V4h6v2"/></svg>
        </button>
      </div>
    `;
    item.onclick = () => { activeFolderId = f.id; renderFolders(); renderPlaybooks(); };
    list.appendChild(item);
  }
}

function renderPlaybooks() {
  const container = document.getElementById('playbooks-grid');
  const titleEl = document.getElementById('playbooks-folder-title');
  container.innerHTML = '';

  let filtered = playbooksData;
  if (activeFolderId === null) {
    titleEl.textContent = 'All Playbooks';
  } else if (activeFolderId === 'unfiled') {
    filtered = playbooksData.filter(p => !p.folder_id);
    titleEl.textContent = 'Unfiled';
  } else {
    const folder = foldersData.find(f => f.id === activeFolderId);
    filtered = playbooksData.filter(p => p.folder_id === activeFolderId);
    titleEl.textContent = folder ? folder.name : 'Folder';
  }

  if (filtered.length === 0) {
    container.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
      <p>No playbooks here. Create one or move existing playbooks to this folder.</p></div>`;
    return;
  }

  for (const p of filtered) {
    const folderBadge = p.folder_name
      ? `<span class="pb-folder-badge"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:10px;height:10px"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>${p.folder_name}</span>`
      : '';

    const card = document.createElement('div');
    card.className = 'card';
    card.style.cssText = 'cursor:default';
    card.innerHTML = `
      <div class="card-body">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:10px">
          <div style="min-width:0">
            <div style="font-weight:600;font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${p.name}</div>
            <div style="font-size:12px;color:var(--text-muted);margin-top:2px">${p.description || 'No description'}</div>
          </div>
          <div style="display:flex;gap:4px;flex-shrink:0">
            ${isAdmin() ? `<button class="btn btn-icon btn-sm" title="Edit" onclick="openPlaybookModal(${p.id})">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>` : ''}
            <button class="btn btn-icon btn-sm" title="History" onclick="openHistoryModal(${p.id})" style="color:var(--info);border-color:rgba(17,205,239,0.3)">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            </button>
            <button class="btn btn-icon btn-sm" title="Export .yml" onclick="exportPlaybook(${p.id})">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            </button>
            ${isAdmin() ? `<button class="btn btn-icon btn-sm" title="Run" onclick="openRunModal(${p.id})" style="color:var(--success);border-color:rgba(39,217,108,0.3)">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            </button>
            <button class="btn btn-icon btn-sm" title="Delete" onclick="deletePlaybook(${p.id})" style="color:var(--danger);border-color:rgba(245,54,92,0.3)">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M9 6V4h6v2"/></svg>
            </button>` : ''}
          </div>
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between">
          <div>${folderBadge}</div>
          <div style="font-size:11px;color:var(--text-muted)">Updated ${fmtDate(p.updated_at)}</div>
        </div>
      </div>
    `;
    container.appendChild(card);
  }
}

// ── Folder CRUD ───────────────────────────────────────────────────────────────

function openFolderModal(id = null) {
  const folder = id ? foldersData.find(f => f.id === id) : null;
  document.getElementById('folder-modal-title').textContent = folder ? 'Rename Folder' : 'New Folder';
  document.getElementById('folder-id').value = folder ? folder.id : '';
  document.getElementById('folder-name').value = folder ? folder.name : '';
  showModal('folder-modal');
  setTimeout(() => document.getElementById('folder-name').focus(), 50);
}

async function saveFolder() {
  const id = document.getElementById('folder-id').value;
  const name = document.getElementById('folder-name').value.trim();
  if (!name) { toast('Folder name is required', 'error'); return; }

  const res = id
    ? await api('PUT', `/api/folders/${id}`, { name })
    : await api('POST', '/api/folders', { name });

  if (res.ok) {
    toast(id ? 'Folder renamed' : 'Folder created', 'success');
    closeModal('folder-modal');
    loadPlaybooks();
  } else {
    const err = await res.json().catch(() => ({}));
    toast(err.error || 'Failed to save folder', 'error');
  }
}

async function deleteFolder(id) {
  const folder = foldersData.find(f => f.id === id);
  if (!confirm(`Delete folder "${folder?.name}"? Playbooks inside will become unfiled.`)) return;
  const res = await api('DELETE', `/api/folders/${id}`);
  if (res.ok) {
    if (activeFolderId === id) activeFolderId = null;
    toast('Folder deleted', 'success');
    loadPlaybooks();
  } else {
    toast('Failed to delete folder', 'error');
  }
}

function openPlaybookModal(id = null) {
  const pb = id ? playbooksData.find(p => p.id === id) : null;
  const newContent = pb ? pb.content : defaultPlaybook;

  document.getElementById('pb-modal-title').textContent = pb ? 'Edit Playbook' : 'New Playbook';
  document.getElementById('pb-id').value = pb ? pb.id : '';
  document.getElementById('pb-name').value = pb ? pb.name : '';
  document.getElementById('pb-description').value = pb ? (pb.description || '') : '';

  // Populate folder dropdown
  const folderSelect = document.getElementById('pb-folder');
  folderSelect.innerHTML = '<option value="">— No folder —</option>';
  for (const f of foldersData) {
    const opt = document.createElement('option');
    opt.value = f.id;
    opt.textContent = f.name;
    if (pb && pb.folder_id === f.id) opt.selected = true;
    // Pre-select current active folder for new playbooks
    if (!pb && activeFolderId && activeFolderId !== 'unfiled' && activeFolderId === f.id) opt.selected = true;
    folderSelect.appendChild(opt);
  }

  // Destroy existing CodeMirror BEFORE showing modal
  if (cmEditor) {
    cmEditor.toTextArea();
    cmEditor = null;
  }

  const textarea = document.getElementById('pb-content');
  textarea.value = newContent;

  showModal('pb-modal');

  // Re-initialize CodeMirror after modal is visible
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      cmEditor = CodeMirror.fromTextArea(textarea, {
        mode: 'yaml',
        theme: 'dracula',
        lineNumbers: true,
        indentUnit: 2,
        tabSize: 2,
        indentWithTabs: false,
        lineWrapping: false,
        autoCloseBrackets: true,
        matchBrackets: true,
        extraKeys: {
          Tab: (cm) => cm.replaceSelection('  '),
          'Ctrl-Space': (cm) => cm.showHint({ hint: ansibleHint }),
        },
        hintOptions: { hint: ansibleHint },
      });
      // Force set the value to ensure correct content
      cmEditor.setValue(newContent);
      cmEditor.refresh();
      cmEditor.clearHistory();

      // Auto-trigger hints after certain characters
      cmEditor.on('inputRead', (cm, change) => {
        if (change.text[0] === ':' || change.text[0] === '-') {
          setTimeout(() => cm.showHint({ hint: ansibleHint, completeSingle: false }), 100);
        }
      });
    });
  });
}

async function savePlaybook() {
  const id = document.getElementById('pb-id').value;
  const content = cmEditor ? cmEditor.getValue() : document.getElementById('pb-content').value;

  const folderVal = document.getElementById('pb-folder').value;
  const data = {
    name: document.getElementById('pb-name').value.trim(),
    description: document.getElementById('pb-description').value.trim(),
    content,
    folder_id: folderVal ? parseInt(folderVal) : null,
  };

  if (!data.name) { toast('Playbook name is required', 'error'); return; }

  const res = id
    ? await api('PUT', `/api/playbooks/${id}`, data)
    : await api('POST', '/api/playbooks', data);

  if (res.ok) {
    toast(id ? 'Playbook saved' : 'Playbook created', 'success');
    closeModal('pb-modal');
    loadPlaybooks();
  } else {
    const err = await res.json().catch(() => ({}));
    toast(err.error || 'Failed to save playbook', 'error');
  }
}

async function deletePlaybook(id) {
  if (!confirm('Delete this playbook?')) return;
  const res = await api('DELETE', `/api/playbooks/${id}`);
  if (res.ok) { toast('Playbook deleted', 'success'); loadPlaybooks(); }
  else { toast('Failed to delete playbook', 'error'); }
}

function exportPlaybook(id) {
  window.location.href = `/api/playbooks/${id}/export`;
}

function exportAllPlaybooks() {
  window.location.href = '/api/playbooks/export';
}

function openPlaybookImportModal() {
  document.getElementById('pb-import-file').value = '';
  showModal('pb-import-modal');
}

async function importPlaybooks() {
  const fileInput = document.getElementById('pb-import-file');
  if (!fileInput.files[0]) { toast('Select a file first', 'error'); return; }
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  const res = await fetch('/api/playbooks/import', { method: 'POST', body: formData });
  if (res.ok) {
    const data = await res.json();
    const msg = `${data.imported} imported, ${data.updated} updated`;
    toast(msg, 'success');
    closeModal('pb-import-modal');
    loadPlaybooks();
  } else {
    const err = await res.json().catch(() => ({}));
    toast(err.error || 'Import failed', 'error');
  }
}

// ── Playbook History ──────────────────────────────────────────────────────────

let historyPlaybookId = null;
let historyVersions = [];
let historyCurrentContent = '';

async function openHistoryModal(pbId) {
  historyPlaybookId = pbId;
  const pb = playbooksData.find(p => p.id === pbId);
  historyCurrentContent = pb ? pb.content : '';

  document.getElementById('history-playbook-name').textContent = pb ? pb.name : '';
  document.getElementById('history-versions-list').innerHTML = '<div style="padding:16px;color:var(--text-muted)">Loading...</div>';
  document.getElementById('history-diff-container').style.display = 'none';

  showModal('history-modal');

  const res = await api('GET', `/api/playbooks/${pbId}/versions`);
  if (!res.ok) {
    document.getElementById('history-versions-list').innerHTML = '<div style="padding:16px;color:var(--danger)">Failed to load versions</div>';
    return;
  }

  const data = await res.json();
  historyVersions = data.versions || [];
  renderHistoryVersions();
}

function renderHistoryVersions() {
  const container = document.getElementById('history-versions-list');

  if (historyVersions.length === 0) {
    container.innerHTML = '<div style="padding:16px;color:var(--text-muted)">No version history yet</div>';
    return;
  }

  container.innerHTML = '';
  for (const v of historyVersions) {
    const item = document.createElement('div');
    item.className = 'history-version-item';
    item.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div>
          <strong>v${v.version_num}</strong>
          <span style="color:var(--text-muted);font-size:12px;margin-left:8px">${fmtDate(v.created_at)}</span>
        </div>
        <div style="font-size:12px;color:var(--text-secondary)">${v.created_by}</div>
      </div>
    `;
    item.onclick = () => selectHistoryVersion(v.id);
    container.appendChild(item);
  }
}

async function selectHistoryVersion(versionId) {
  const version = historyVersions.find(v => v.id === versionId);
  if (!version) return;

  // Mark selected
  document.querySelectorAll('.history-version-item').forEach(el => el.classList.remove('selected'));
  event.currentTarget.classList.add('selected');

  // Show diff
  const diffContainer = document.getElementById('history-diff-container');
  diffContainer.style.display = '';

  document.getElementById('history-version-num').textContent = `v${version.version_num}`;
  document.getElementById('history-restore-btn').onclick = () => restoreVersion(versionId, version.version_num);

  // Simple diff view — show old content
  const diffContent = document.getElementById('history-diff-content');
  diffContent.textContent = version.content;
}

async function restoreVersion(versionId, versionNum) {
  if (!confirm(`Restore version ${versionNum}? This will create a new version with the old content.`)) return;

  const res = await api('POST', `/api/playbooks/${historyPlaybookId}/versions/${versionId}/restore`);
  if (res.ok) {
    toast(`Restored v${versionNum}`, 'success');
    closeModal('history-modal');
    loadPlaybooks();
  } else {
    toast('Failed to restore version', 'error');
  }
}

// ── Run Modal ─────────────────────────────────────────────────────────────────

let runPlaybookId = null;

function openRunModal(pbId) {
  runPlaybookId = pbId;
  const pb = playbooksData.find(p => p.id === pbId);
  document.getElementById('run-playbook-name').textContent = pb ? pb.name : '';
  document.getElementById('run-extra-vars').value = '';
  document.getElementById('run-tags').value = '';
  document.getElementById('run-skip-tags').value = '';
  document.getElementById('run-check-mode').checked = false;
  showModal('run-modal');
}

async function executePlaybook() {
  if (!runPlaybookId) return;
  const res = await api('POST', '/api/executions', {
    playbook_id: runPlaybookId,
    extra_vars: document.getElementById('run-extra-vars').value.trim(),
    tags: document.getElementById('run-tags').value.trim(),
    skip_tags: document.getElementById('run-skip-tags').value.trim(),
    check_mode: document.getElementById('run-check-mode').checked,
  });

  if (res.ok) {
    const data = await res.json();
    toast('Execution started', 'success');
    closeModal('run-modal');
    showPage('executions');
    setTimeout(() => openOutputModal(data.id), 500);
  } else {
    toast('Failed to start execution', 'error');
  }
}

// ── Executions ────────────────────────────────────────────────────────────────

let outputPollTimer = null;
let outputSocket = null;
let currentExecutionId = null;
let useWebSocket = true;  // Try WebSocket first, fallback to polling if unavailable

function initSocket() {
  // Initialize Socket.IO connection if not already connected
  if (outputSocket && outputSocket.connected) return outputSocket;

  try {
    if (typeof io === 'undefined') {
      console.warn('Socket.IO not loaded, falling back to polling');
      useWebSocket = false;
      return null;
    }

    outputSocket = io({
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 3,
      reconnectionDelay: 1000,
    });

    outputSocket.on('connect', () => {
      console.log('WebSocket connected');
      useWebSocket = true;
    });

    outputSocket.on('connect_error', (error) => {
      console.warn('WebSocket connection error, falling back to polling:', error.message);
      useWebSocket = false;
    });

    outputSocket.on('disconnect', () => {
      console.log('WebSocket disconnected');
    });

    // Handle real-time execution output
    outputSocket.on('execution_output', (data) => {
      if (data.execution_id === currentExecutionId) {
        const out = document.getElementById('output-content');
        if (out) {
          // Append the new line to existing content
          const currentText = out.textContent === 'Loading...' || out.textContent === '(no output)' ? '' : out.textContent;
          out.textContent = currentText + data.line;
          out.scrollTop = out.scrollHeight;
        }
      }
    });

    // Handle execution status changes
    outputSocket.on('execution_status', (data) => {
      if (data.execution_id === currentExecutionId) {
        const statusEl = document.getElementById('output-status');
        if (statusEl) {
          statusEl.innerHTML = `<span class="badge ${statusBadge(data.status)}">${data.status}</span>`;
        }

        // Update output if provided (for initial state or final state)
        if (data.output !== undefined) {
          const out = document.getElementById('output-content');
          if (out && (out.textContent === 'Loading...' || data.status === 'success' || data.status === 'failed')) {
            out.textContent = data.output || '(no output)';
            out.scrollTop = out.scrollHeight;
          }
        }

        // If execution finished, leave the room
        if (data.status !== 'running' && data.status !== 'pending') {
          if (outputSocket && outputSocket.connected) {
            outputSocket.emit('leave_execution', { execution_id: currentExecutionId });
          }
        }
      }
    });

    return outputSocket;
  } catch (e) {
    console.warn('Failed to initialize WebSocket:', e);
    useWebSocket = false;
    return null;
  }
}

async function loadExecutions() {
  const res = await api('GET', '/api/executions');
  const executions = await res.json();
  renderExecutions(executions);
}

function renderExecutions(executions) {
  const tbody = document.getElementById('executions-tbody');
  tbody.innerHTML = '';

  if (executions.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
      <p>No executions yet.</p></div></td></tr>`;
    return;
  }

  for (const e of executions) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>#${e.id}</td>
      <td><strong>${e.playbook_name || '-'}</strong></td>
      <td><code style="font-size:11px">${e.host_pattern}</code></td>
      <td><span class="badge ${statusBadge(e.status)}">${e.status}</span></td>
      <td>${fmtDate(e.started_at)}</td>
      <td>
        <div style="display:flex;gap:4px">
          <button class="btn btn-icon btn-sm" title="View output" onclick="openOutputModal(${e.id})">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
          </button>
          ${isAdmin() && (e.status === 'running' || e.status === 'pending') ? `
          <button class="btn btn-icon btn-sm" title="Cancel" onclick="cancelExecution(${e.id})" style="color:var(--warning)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
          </button>` : ''}
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  }
}

async function openOutputModal(execId) {
  document.getElementById('output-exec-id').textContent = `#${execId}`;
  document.getElementById('output-content').textContent = 'Loading...';
  showModal('output-modal');

  // Clean up any previous state
  if (outputPollTimer) {
    clearInterval(outputPollTimer);
    outputPollTimer = null;
  }

  // Leave previous room if any
  if (currentExecutionId && outputSocket && outputSocket.connected) {
    outputSocket.emit('leave_execution', { execution_id: currentExecutionId });
  }

  currentExecutionId = execId;

  // Initialize WebSocket and join room for this execution
  const socket = initSocket();

  if (socket && socket.connected && useWebSocket) {
    // Use WebSocket for real-time updates
    socket.emit('join_execution', { execution_id: execId });
    // The server will send current state when we join
  } else {
    // Fallback to polling if WebSocket not available
    startPolling(execId);
  }
}

// Polling fallback for when WebSocket is unavailable
async function startPolling(execId) {
  const poll = async () => {
    if (currentExecutionId !== execId) return;  // Stale poll

    const res = await api('GET', `/api/executions/${execId}`);
    if (!res.ok) return;
    const e = await res.json();
    const out = document.getElementById('output-content');
    out.textContent = e.output || '(no output)';
    out.scrollTop = out.scrollHeight;
    document.getElementById('output-status').innerHTML =
      `<span class="badge ${statusBadge(e.status)}">${e.status}</span>`;

    if (e.status !== 'running' && e.status !== 'pending') {
      clearInterval(outputPollTimer);
      outputPollTimer = null;
    }
  };

  await poll();
  outputPollTimer = setInterval(poll, 800);
}

async function cancelExecution(id) {
  const res = await api('POST', `/api/executions/${id}/cancel`);
  if (res.ok) { toast('Execution cancelled', 'success'); loadExecutions(); }
}

async function purgeExecutions() {
  if (!confirm('Delete ALL execution history?')) return;
  const res = await api('POST', '/api/executions/purge');
  if (res.ok) { toast('Executions purged', 'success'); loadExecutions(); }
}

// ── Schedules ─────────────────────────────────────────────────────────────────

let schedulesData = [];

async function loadSchedules() {
  const [schedRes, pbRes] = await Promise.all([
    api('GET', '/api/schedules'),
    api('GET', '/api/playbooks'),
  ]);
  schedulesData = await schedRes.json();
  playbooksData = await pbRes.json();
  renderSchedules();
}

function renderSchedules() {
  const tbody = document.getElementById('schedules-tbody');
  tbody.innerHTML = '';

  if (schedulesData.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
      <p>No schedules configured.</p></div></td></tr>`;
    return;
  }

  for (const s of schedulesData) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${s.name}</strong></td>
      <td>${s.playbook_name || '-'}</td>
      <td><code style="font-size:11px">${s.cron_expr}</code></td>
      <td><code style="font-size:11px">${s.host_pattern}</code></td>
      <td>
        ${s.last_run_at ? `${fmtDate(s.last_run_at)} <span class="badge ${statusBadge(s.last_run_status)}">${s.last_run_status}</span>` : '<span style="color:var(--text-muted)">Never</span>'}
      </td>
      <td>${s.next_run_at ? fmtDate(s.next_run_at) : '<span style="color:var(--text-muted)">—</span>'}</td>
      <td>
        <div style="display:flex;gap:4px">
          ${isAdmin() ? `
          <button class="btn btn-icon btn-sm" onclick="openScheduleModal(${s.id})">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button class="btn btn-icon btn-sm" onclick="deleteSchedule(${s.id})" style="color:var(--danger);border-color:rgba(245,54,92,0.3)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M9 6V4h6v2"/></svg>
          </button>` : '<span style="color:var(--text-muted);font-size:11px">—</span>'}
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  }
}

function openScheduleModal(id = null) {
  const s = id ? schedulesData.find(x => x.id === id) : null;

  document.getElementById('sched-modal-title').textContent = s ? 'Edit Schedule' : 'New Schedule';
  document.getElementById('sched-id').value = s ? s.id : '';
  document.getElementById('sched-name').value = s ? s.name : '';
  document.getElementById('sched-cron').value = s ? s.cron_expr : '0 * * * *';
  document.getElementById('sched-host-pattern').value = s ? s.host_pattern : 'all';
  document.getElementById('sched-enabled').value = s ? (s.enabled ? 'true' : 'false') : 'true';

  const pbSelect = document.getElementById('sched-playbook');
  pbSelect.innerHTML = '';
  for (const p of playbooksData) {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = p.name;
    if (s && s.playbook_id === p.id) opt.selected = true;
    pbSelect.appendChild(opt);
  }

  showModal('sched-modal');
}

async function saveSchedule() {
  const id = document.getElementById('sched-id').value;
  const data = {
    name: document.getElementById('sched-name').value.trim(),
    playbook_id: parseInt(document.getElementById('sched-playbook').value),
    cron_expr: document.getElementById('sched-cron').value.trim(),
    host_pattern: document.getElementById('sched-host-pattern').value.trim() || 'all',
    enabled: document.getElementById('sched-enabled').value === 'true',
  };

  if (!data.name || !data.cron_expr) { toast('Name and cron expression are required', 'error'); return; }

  const res = id
    ? await api('PUT', `/api/schedules/${id}`, data)
    : await api('POST', '/api/schedules', data);

  if (res.ok) {
    toast(id ? 'Schedule updated' : 'Schedule created', 'success');
    closeModal('sched-modal');
    loadSchedules();
  } else {
    toast('Failed to save schedule', 'error');
  }
}

async function deleteSchedule(id) {
  if (!confirm('Delete this schedule?')) return;
  const res = await api('DELETE', `/api/schedules/${id}`);
  if (res.ok) { toast('Schedule deleted', 'success'); loadSchedules(); }
}

function setCronPreset(expr) {
  document.getElementById('sched-cron').value = expr;
}

// ── Settings ──────────────────────────────────────────────────────────────────

let settingsData = {};
let settingsSchema = [];

async function loadSettings() {
  const [dataRes, schemaRes] = await Promise.all([
    api('GET', '/api/settings'),
    api('GET', '/api/settings/schema'),
  ]);
  settingsData = await dataRes.json();
  settingsSchema = await schemaRes.json();
  renderSettings();
}

function renderSettings() {
  const nav = document.getElementById('settings-nav');
  const content = document.getElementById('settings-content');
  nav.innerHTML = '';
  content.innerHTML = '';

  settingsSchema.forEach((section, idx) => {
    const navItem = document.createElement('button');
    navItem.className = `settings-nav-item${idx === 0 ? ' active' : ''}`;
    navItem.textContent = section.label;
    navItem.onclick = () => {
      document.querySelectorAll('.settings-nav-item').forEach(n => n.classList.remove('active'));
      document.querySelectorAll('.settings-section').forEach(s => s.classList.remove('active'));
      navItem.classList.add('active');
      document.getElementById(`settings-${section.category}`).classList.add('active');
    };
    nav.appendChild(navItem);

    const div = document.createElement('div');
    div.id = `settings-${section.category}`;
    div.className = `settings-section${idx === 0 ? ' active' : ''}`;

    const testBtn = section.category === 'auth'
      ? `<button class="btn btn-secondary btn-sm" onclick="openLdapTestModal()" style="margin-left:auto">
           <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
           Test LDAP
         </button>`
      : '';
    let html = `<div style="display:flex;align-items:center;margin-bottom:16px">
      <h3 style="font-size:15px;font-weight:600;margin:0">${section.label}</h3>${testBtn}
    </div>`;
    for (const field of section.fields) {
      const val = settingsData[field.key] || '';
      const hint = field.hint ? `<div style="font-size:11px;color:var(--text-muted);margin-top:4px">${field.hint}</div>` : '';
      html += `<div class="form-group">
        <label class="form-label">${field.label}</label>`;

      if (field.type === 'select') {
        html += `<select class="form-control" id="setting-${field.key}">`;
        for (const [v, l] of field.options) {
          html += `<option value="${v}"${val === v ? ' selected' : ''}>${l}</option>`;
        }
        html += '</select>';
      } else if (field.type === 'textarea') {
        html += `<textarea class="form-control" id="setting-${field.key}" rows="8" placeholder="${field.label}">${val}</textarea>`;
      } else {
        const inputType = field.type === 'password' ? 'password' : 'text';
        html += `<input type="${inputType}" class="form-control" id="setting-${field.key}" value="${val}" placeholder="${field.label}">`;
      }
      html += hint + '</div>';
    }
    div.innerHTML = html;
    content.appendChild(div);
  });
}

async function saveSettings() {
  const data = {};
  for (const section of settingsSchema) {
    for (const field of section.fields) {
      const el = document.getElementById(`setting-${field.key}`);
      if (el) data[field.key] = el.value;
    }
  }
  const res = await api('POST', '/api/settings', data);
  if (res.ok) toast('Settings saved', 'success');
  else toast('Failed to save settings', 'error');
}

// ── LDAP Test ─────────────────────────────────────────────────────────────────

function openLdapTestModal() {
  document.getElementById('ldap-test-user').value = '';
  document.getElementById('ldap-test-pass').value = '';
  document.getElementById('ldap-test-results').style.display = 'none';
  document.getElementById('ldap-test-steps').innerHTML = '';
  showModal('ldap-test-modal');
}

async function runLdapTest() {
  const btn = document.getElementById('ldap-test-btn');
  btn.disabled = true;
  btn.textContent = 'Testing…';

  const resultsEl = document.getElementById('ldap-test-results');
  const stepsEl = document.getElementById('ldap-test-steps');
  resultsEl.style.display = 'none';
  stepsEl.innerHTML = '';

  const res = await api('POST', '/api/settings/test-ldap', {
    test_username: document.getElementById('ldap-test-user').value.trim(),
    test_password: document.getElementById('ldap-test-pass').value,
  });

  btn.disabled = false;
  btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Run Test`;

  const data = await res.json();
  resultsEl.style.display = '';

  for (const s of (data.steps || [])) {
    const row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:flex-start;gap:8px;padding:5px 0;font-size:13px;border-bottom:1px solid var(--border-color)';
    const icon = s.ok
      ? `<span style="color:var(--success);flex-shrink:0">✓</span>`
      : `<span style="color:var(--danger);flex-shrink:0">✗</span>`;
    row.innerHTML = `${icon}<span style="color:${s.ok ? 'var(--text-primary)' : 'var(--danger)'}">${s.msg}</span>`;
    stepsEl.appendChild(row);
  }

  if (data.ok) {
    toast('LDAP test passed', 'success');
  } else {
    toast('LDAP test failed — check steps above', 'error');
  }
}

// ── Users ─────────────────────────────────────────────────────────────────────

let usersData = [];

async function loadUsers() {
  const res = await api('GET', '/api/users');
  usersData = await res.json();
  renderUsers();
}

function renderUsers() {
  const tbody = document.getElementById('users-tbody');
  tbody.innerHTML = '';

  if (usersData.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
      <p>No users found.</p></div></td></tr>`;
    return;
  }

  for (const u of usersData) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${u.id}</td>
      <td>
        <strong>${u.username}</strong>
        ${u.is_ldap ? '<span style="font-size:10px;padding:1px 5px;border-radius:3px;background:rgba(108,99,255,0.15);color:#6c63ff;margin-left:6px">LDAP</span>' : ''}
      </td>
      <td><span class="badge ${u.role === 'admin' ? 'badge-info' : 'badge-muted'}">${u.role || 'admin'}</span></td>
      <td>${fmtDate(u.created_at)}</td>
      <td>
        <div style="display:flex;gap:4px">
          <button class="btn btn-icon btn-sm" title="Edit" onclick="openUserModal(${u.id})">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button class="btn btn-icon btn-sm" title="Delete" onclick="deleteUser(${u.id})" style="color:var(--danger);border-color:rgba(245,54,92,0.3)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M9 6V4h6v2"/></svg>
          </button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  }
}

function openUserModal(id = null) {
  const user = id ? usersData.find(u => u.id === id) : null;
  const isLdap = user && user.is_ldap;
  document.getElementById('user-modal-title').textContent = user ? 'Edit User' : 'New User';
  document.getElementById('user-id').value = user ? user.id : '';
  document.getElementById('user-username').value = user ? user.username : '';
  document.getElementById('user-username').disabled = !!user;
  document.getElementById('user-username-group').style.display = user ? 'none' : '';
  document.getElementById('user-role').value = user ? (user.role || 'admin') : 'admin';
  document.getElementById('user-password').value = '';
  document.getElementById('user-password-confirm').value = '';
  // Hide password fields for LDAP users
  const pwGroup = document.getElementById('user-password-group');
  const pwConfGroup = document.getElementById('user-password-confirm-group');
  if (pwGroup) pwGroup.style.display = isLdap ? 'none' : '';
  if (pwConfGroup) pwConfGroup.style.display = isLdap ? 'none' : '';
  showModal('user-modal');
}

async function saveUser() {
  const id = document.getElementById('user-id').value;
  const password = document.getElementById('user-password').value;
  const confirm = document.getElementById('user-password-confirm').value;
  const role = document.getElementById('user-role').value;

  if (password && password !== confirm) { toast('Passwords do not match', 'error'); return; }

  let res;
  if (id) {
    const payload = { role };
    if (password) payload.password = password;
    res = await api('PUT', `/api/users/${id}`, payload);
  } else {
    if (!password) { toast('Password is required', 'error'); return; }
    const username = document.getElementById('user-username').value.trim();
    if (!username) { toast('Username is required', 'error'); return; }
    res = await api('POST', '/api/users', { username, password, role });
  }

  if (res.ok) {
    toast(id ? 'Password updated' : 'User created', 'success');
    closeModal('user-modal');
    loadUsers();
  } else {
    const err = await res.json().catch(() => ({}));
    toast(err.error || 'Failed to save user', 'error');
  }
}

async function deleteUser(id) {
  if (!confirm('Delete this user?')) return;
  const res = await api('DELETE', `/api/users/${id}`);
  if (res.ok) { toast('User deleted', 'success'); loadUsers(); }
  else {
    const err = await res.json().catch(() => ({}));
    toast(err.error || 'Failed to delete user', 'error');
  }
}

// ── Audit Log ─────────────────────────────────────────────────────────────────

let auditPage = 1;
let auditTotal = 0;
let auditDebounce = null;

async function loadAudit(page = 1) {
  if (auditDebounce) clearTimeout(auditDebounce);
  auditDebounce = setTimeout(() => _loadAudit(page), 200);
}

async function _loadAudit(page = 1) {
  auditPage = page;
  const action = document.getElementById('audit-filter-action')?.value || '';
  const user = document.getElementById('audit-filter-user')?.value || '';
  const url = `/api/audit?page=${page}&action=${encodeURIComponent(action)}&user=${encodeURIComponent(user)}`;
  const res = await api('GET', url);
  if (!res.ok) return;
  const data = await res.json();
  auditTotal = data.total;
  renderAudit(data.logs, data.total, data.page, data.per_page);
}

function renderAudit(logs, total, page, perPage) {
  const tbody = document.getElementById('audit-tbody');
  tbody.innerHTML = '';

  if (logs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
      <p>No audit logs found.</p></div></td></tr>`;
  } else {
    for (const l of logs) {
      const actionBadge = getActionBadge(l.action);
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-size:12px">${fmtDate(l.created_at)}</td>
        <td><strong>${l.user}</strong></td>
        <td><span class="badge ${actionBadge.class}">${actionBadge.label}</span></td>
        <td>
          ${l.target_type ? `<span style="color:var(--text-muted);font-size:11px">${l.target_type}</span> ` : ''}
          ${l.target_name || ''}
          ${l.details && l.details !== '{}' ? `<span style="color:var(--text-muted);font-size:11px;margin-left:4px">${formatDetails(l.details)}</span>` : ''}
        </td>
        <td style="font-size:11px;color:var(--text-muted)">${l.ip_address || '—'}</td>
      `;
      tbody.appendChild(tr);
    }
  }

  const totalPages = Math.ceil(total / perPage);
  document.getElementById('audit-info').textContent = `Page ${page} of ${totalPages} (${total} entries)`;
  document.getElementById('audit-prev').disabled = page <= 1;
  document.getElementById('audit-next').disabled = page >= totalPages;
}

function getActionBadge(action) {
  const map = {
    login: { label: 'Login', class: 'badge-success' },
    login_failed: { label: 'Login Failed', class: 'badge-danger' },
    host_create: { label: 'Create', class: 'badge-info' },
    host_update: { label: 'Update', class: 'badge-warning' },
    host_delete: { label: 'Delete', class: 'badge-danger' },
    hosts_import: { label: 'Import', class: 'badge-info' },
    folder_create: { label: 'Create', class: 'badge-info' },
    folder_update: { label: 'Update', class: 'badge-warning' },
    folder_delete: { label: 'Delete', class: 'badge-danger' },
    playbook_create: { label: 'Create', class: 'badge-info' },
    playbook_update: { label: 'Update', class: 'badge-warning' },
    playbook_delete: { label: 'Delete', class: 'badge-danger' },
    playbook_restore: { label: 'Restore', class: 'badge-info' },
    playbooks_import: { label: 'Import', class: 'badge-info' },
    execution_start: { label: 'Execute', class: 'badge-success' },
    execution_cancel: { label: 'Cancel', class: 'badge-warning' },
    executions_purge: { label: 'Purge', class: 'badge-danger' },
    schedule_create: { label: 'Create', class: 'badge-info' },
    schedule_update: { label: 'Update', class: 'badge-warning' },
    schedule_delete: { label: 'Delete', class: 'badge-danger' },
    settings_update: { label: 'Settings', class: 'badge-warning' },
    user_create: { label: 'Create', class: 'badge-info' },
    user_update: { label: 'Update', class: 'badge-warning' },
    user_delete: { label: 'Delete', class: 'badge-danger' },
    group_var_create: { label: 'Create', class: 'badge-info' },
    group_var_update: { label: 'Update', class: 'badge-warning' },
    group_var_delete: { label: 'Delete', class: 'badge-danger' },
    host_var_create: { label: 'Create', class: 'badge-info' },
    host_var_update: { label: 'Update', class: 'badge-warning' },
    host_var_delete: { label: 'Delete', class: 'badge-danger' },
  };
  return map[action] || { label: action, class: 'badge-muted' };
}

function formatDetails(details) {
  try {
    const obj = JSON.parse(details);
    return Object.entries(obj).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ');
  } catch (e) {
    return '';
  }
}

// ── Modal helpers ─────────────────────────────────────────────────────────────

function showModal(id) {
  document.getElementById(id).classList.add('show');
}

function closeModal(id) {
  document.getElementById(id).classList.remove('show');
  if (id === 'output-modal') {
    // Clean up polling timer
    if (outputPollTimer) {
      clearInterval(outputPollTimer);
      outputPollTimer = null;
    }
    // Leave WebSocket room
    if (currentExecutionId && outputSocket && outputSocket.connected) {
      outputSocket.emit('leave_execution', { execution_id: currentExecutionId });
    }
    currentExecutionId = null;
  }
  if (id === 'pb-modal' && cmEditor) {
    cmEditor.toTextArea();
    cmEditor = null;
  }
}

// Click outside to close
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal-overlay')) {
    const id = e.target.id;
    if (id) closeModal(id);
  }
});

// ── Helpers ───────────────────────────────────────────────────────────────────

function statusBadge(status) {
  const map = {
    success: 'badge-success',
    failed: 'badge-danger',
    running: 'badge-info',
    pending: 'badge-warning',
    cancelled: 'badge-muted',
  };
  return map[status] || 'badge-muted';
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
}

// ── RBAC ──────────────────────────────────────────────────────────────────────

let currentRole = 'admin';

async function initMe() {
  try {
    const res = await api('GET', '/api/me');
    if (res.ok) {
      const data = await res.json();
      currentRole = data.role || 'admin';
      if (currentRole !== 'admin') {
        document.body.classList.add('role-readonly');
      }
    }
  } catch (e) { /* ignore */ }
}

function isAdmin() { return currentRole === 'admin'; }

// ── Variables (Group Vars & Host Vars) ───────────────────────────────────────

let groupVarsData = [];
let hostVarsData = [];

async function loadVariables() {
  const [gvRes, hvRes] = await Promise.all([
    api('GET', '/api/group-vars'),
    api('GET', '/api/host-vars'),
  ]);
  groupVarsData = await gvRes.json();
  hostVarsData = await hvRes.json();
  renderGroupVars();
  renderHostVars();
}

function renderGroupVars() {
  const tbody = document.getElementById('group-vars-tbody');
  tbody.innerHTML = '';

  if (groupVarsData.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 7V4h16v3"/><path d="M9 20h6"/><path d="M12 4v16"/></svg>
      <p>No group variables defined.</p></div></td></tr>`;
    return;
  }

  for (const gv of groupVarsData) {
    const tr = document.createElement('tr');
    const truncValue = gv.var_value.length > 50 ? gv.var_value.substring(0, 50) + '...' : gv.var_value;
    tr.innerHTML = `
      <td><span class="group-tag">${gv.group_name}</span></td>
      <td><code style="font-size:12px">${gv.var_name}</code></td>
      <td><code style="font-size:11px;color:var(--text-secondary)">${truncValue}</code></td>
      <td>
        <div style="display:flex;gap:4px">
          ${isAdmin() ? `
          <button class="btn btn-icon btn-sm" title="Edit" onclick="openGroupVarModal(${gv.id})">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button class="btn btn-icon btn-sm" title="Delete" onclick="deleteGroupVar(${gv.id})" style="color:var(--danger);border-color:rgba(245,54,92,0.3)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M9 6V4h6v2"/></svg>
          </button>` : ''}
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  }
}

function renderHostVars() {
  const tbody = document.getElementById('host-vars-tbody');
  tbody.innerHTML = '';

  if (hostVarsData.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 7V4h16v3"/><path d="M9 20h6"/><path d="M12 4v16"/></svg>
      <p>No host variables defined.</p></div></td></tr>`;
    return;
  }

  for (const hv of hostVarsData) {
    const tr = document.createElement('tr');
    const truncValue = hv.var_value.length > 50 ? hv.var_value.substring(0, 50) + '...' : hv.var_value;
    tr.innerHTML = `
      <td><strong>${hv.host_name}</strong></td>
      <td><code style="font-size:12px">${hv.var_name}</code></td>
      <td><code style="font-size:11px;color:var(--text-secondary)">${truncValue}</code></td>
      <td>
        <div style="display:flex;gap:4px">
          ${isAdmin() ? `
          <button class="btn btn-icon btn-sm" title="Edit" onclick="openHostVarModal(${hv.id})">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button class="btn btn-icon btn-sm" title="Delete" onclick="deleteHostVar(${hv.id})" style="color:var(--danger);border-color:rgba(245,54,92,0.3)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M9 6V4h6v2"/></svg>
          </button>` : ''}
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  }
}

function openGroupVarModal(id = null) {
  const gv = id ? groupVarsData.find(v => v.id === id) : null;
  document.getElementById('group-var-modal-title').textContent = gv ? 'Edit Group Variable' : 'Add Group Variable';
  document.getElementById('group-var-id').value = gv ? gv.id : '';
  document.getElementById('group-var-group').value = gv ? gv.group_name : '';
  document.getElementById('group-var-name').value = gv ? gv.var_name : '';
  document.getElementById('group-var-value').value = gv ? gv.var_value : '';
  showModal('group-var-modal');
}

async function saveGroupVar() {
  const id = document.getElementById('group-var-id').value;
  const data = {
    group_name: document.getElementById('group-var-group').value.trim(),
    var_name: document.getElementById('group-var-name').value.trim(),
    var_value: document.getElementById('group-var-value').value,
  };

  if (!data.group_name) { toast('Group name is required', 'error'); return; }
  if (!data.var_name) { toast('Variable name is required', 'error'); return; }

  const res = id
    ? await api('PUT', `/api/group-vars/${id}`, data)
    : await api('POST', '/api/group-vars', data);

  if (res.ok) {
    toast(id ? 'Variable updated' : 'Variable created', 'success');
    closeModal('group-var-modal');
    loadVariables();
  } else {
    const err = await res.json().catch(() => ({}));
    toast(err.error || 'Failed to save variable', 'error');
  }
}

async function deleteGroupVar(id) {
  if (!confirm('Delete this group variable?')) return;
  const res = await api('DELETE', `/api/group-vars/${id}`);
  if (res.ok) { toast('Variable deleted', 'success'); loadVariables(); }
  else { toast('Failed to delete variable', 'error'); }
}

function openHostVarModal(id = null) {
  const hv = id ? hostVarsData.find(v => v.id === id) : null;
  document.getElementById('host-var-modal-title').textContent = hv ? 'Edit Host Variable' : 'Add Host Variable';
  document.getElementById('host-var-id').value = hv ? hv.id : '';
  document.getElementById('host-var-host').value = hv ? hv.host_name : '';
  document.getElementById('host-var-name').value = hv ? hv.var_name : '';
  document.getElementById('host-var-value').value = hv ? hv.var_value : '';
  showModal('host-var-modal');
}

async function saveHostVar() {
  const id = document.getElementById('host-var-id').value;
  const data = {
    host_name: document.getElementById('host-var-host').value.trim(),
    var_name: document.getElementById('host-var-name').value.trim(),
    var_value: document.getElementById('host-var-value').value,
  };

  if (!data.host_name) { toast('Host name is required', 'error'); return; }
  if (!data.var_name) { toast('Variable name is required', 'error'); return; }

  const res = id
    ? await api('PUT', `/api/host-vars/${id}`, data)
    : await api('POST', '/api/host-vars', data);

  if (res.ok) {
    toast(id ? 'Variable updated' : 'Variable created', 'success');
    closeModal('host-var-modal');
    loadVariables();
  } else {
    const err = await res.json().catch(() => ({}));
    toast(err.error || 'Failed to save variable', 'error');
  }
}

async function deleteHostVar(id) {
  if (!confirm('Delete this host variable?')) return;
  const res = await api('DELETE', `/api/host-vars/${id}`);
  if (res.ok) { toast('Variable deleted', 'success'); loadVariables(); }
  else { toast('Failed to delete variable', 'error'); }
}

// ── Roles ─────────────────────────────────────────────────────────────────────

let rolesData = [];

async function loadRoles() {
  const res = await api('GET', '/api/roles');
  rolesData = await res.json();
  renderRoles();
}

function renderRoles() {
  const tbody = document.getElementById('roles-tbody');
  tbody.innerHTML = '';

  if (rolesData.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4z"/></svg>
      <p>No roles installed. Install roles from Ansible Galaxy or Git.</p></div></td></tr>`;
    return;
  }

  for (const r of rolesData) {
    const fullName = r.namespace ? `${r.namespace}.${r.name}` : r.name;
    const sourceBadge = r.source === 'galaxy'
      ? '<span class="badge badge-info">Galaxy</span>'
      : '<span class="badge badge-warning">Git</span>';

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${r.name}</strong></td>
      <td>${r.namespace || '—'}</td>
      <td>${sourceBadge}</td>
      <td><code style="font-size:12px">${r.version || 'latest'}</code></td>
      <td>${fmtDate(r.installed_at)}</td>
      <td>
        ${isAdmin() ? `
        <button class="btn btn-icon btn-sm" title="Uninstall" onclick="deleteRole(${r.id})" style="color:var(--danger);border-color:rgba(245,54,92,0.3)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M9 6V4h6v2"/></svg>
        </button>` : ''}
      </td>
    `;
    tbody.appendChild(tr);
  }
}

function openInstallRoleModal() {
  document.getElementById('role-source').value = 'galaxy';
  document.getElementById('role-name').value = '';
  document.getElementById('role-version').value = '';
  showModal('role-install-modal');
}

async function installRole() {
  const source = document.getElementById('role-source').value;
  const name = document.getElementById('role-name').value.trim();
  const version = document.getElementById('role-version').value.trim();

  if (!name) { toast('Role name is required', 'error'); return; }

  toast('Installing role...', 'info');
  const res = await api('POST', '/api/roles/install', { source, name, version });

  if (res.ok) {
    toast('Role installed successfully', 'success');
    closeModal('role-install-modal');
    loadRoles();
  } else {
    const err = await res.json().catch(() => ({}));
    toast(err.error || 'Failed to install role', 'error');
  }
}

async function deleteRole(id) {
  if (!confirm('Uninstall this role?')) return;
  const res = await api('DELETE', `/api/roles/${id}`);
  if (res.ok) { toast('Role uninstalled', 'success'); loadRoles(); }
  else { toast('Failed to uninstall role', 'error'); }
}

function openGalaxySearchModal() {
  document.getElementById('galaxy-search-query').value = '';
  document.getElementById('galaxy-search-results').innerHTML = '<div style="color:var(--text-muted);padding:16px;text-align:center">Enter a search query above</div>';
  showModal('galaxy-search-modal');
}

async function searchGalaxy() {
  const query = document.getElementById('galaxy-search-query').value.trim();
  if (!query) { toast('Enter a search query', 'error'); return; }

  const resultsEl = document.getElementById('galaxy-search-results');
  resultsEl.innerHTML = '<div style="color:var(--text-muted);padding:16px;text-align:center">Searching...</div>';

  const res = await api('POST', '/api/roles/search', { query });
  if (!res.ok) {
    resultsEl.innerHTML = '<div style="color:var(--danger);padding:16px">Search failed</div>';
    return;
  }

  const results = await res.json();
  if (results.length === 0) {
    resultsEl.innerHTML = '<div style="color:var(--text-muted);padding:16px;text-align:center">No results found</div>';
    return;
  }

  resultsEl.innerHTML = '';
  for (const r of results) {
    const fullName = r.namespace ? `${r.namespace}.${r.name}` : r.name;
    const item = document.createElement('div');
    item.style.cssText = 'padding:12px;border-bottom:1px solid var(--border-color);display:flex;justify-content:space-between;align-items:center';
    item.innerHTML = `
      <div style="min-width:0">
        <strong>${fullName}</strong>
        <div style="font-size:12px;color:var(--text-secondary);margin-top:2px">${r.description || 'No description'}</div>
        <div style="font-size:11px;color:var(--text-muted);margin-top:4px">Downloads: ${r.download_count?.toLocaleString() || 0}</div>
      </div>
      <button class="btn btn-primary btn-sm" onclick="installFromGalaxy('${fullName}')">Install</button>
    `;
    resultsEl.appendChild(item);
  }
}

async function installFromGalaxy(name) {
  closeModal('galaxy-search-modal');
  toast('Installing role...', 'info');
  const res = await api('POST', '/api/roles/install', { source: 'galaxy', name, version: '' });

  if (res.ok) {
    toast('Role installed successfully', 'success');
    loadRoles();
  } else {
    const err = await res.json().catch(() => ({}));
    toast(err.error || 'Failed to install role', 'error');
  }
}

// ── Dynamic Inventory ─────────────────────────────────────────────────────────

let dynamicInvData = [];
let dynamicInvTemplates = [];
let cmDynamicInv = null;

async function loadDynamicInventories() {
  const res = await api('GET', '/api/dynamic-inventories');
  dynamicInvData = await res.json();
  renderDynamicInventories();
}

function renderDynamicInventories() {
  const tbody = document.getElementById('dynamic-inv-tbody');
  tbody.innerHTML = '';

  if (dynamicInvData.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
      <p>No dynamic inventories configured.</p></div></td></tr>`;
    return;
  }

  for (const inv of dynamicInvData) {
    const typeBadge = inv.inv_type === 'script'
      ? '<span class="badge badge-warning">Script</span>'
      : '<span class="badge badge-info">Plugin</span>';
    const statusBadge = inv.enabled
      ? '<span class="badge badge-success">Enabled</span>'
      : '<span class="badge badge-muted">Disabled</span>';

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${inv.name}</strong></td>
      <td>${typeBadge}</td>
      <td>${statusBadge}</td>
      <td>${fmtDate(inv.updated_at)}</td>
      <td>
        <div style="display:flex;gap:4px">
          <button class="btn btn-icon btn-sm" title="Test" onclick="testDynamicInvById(${inv.id})" style="color:var(--info)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          </button>
          ${isAdmin() ? `
          <button class="btn btn-icon btn-sm" title="Edit" onclick="openDynamicInvModal(${inv.id})">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button class="btn btn-icon btn-sm" title="Delete" onclick="deleteDynamicInv(${inv.id})" style="color:var(--danger);border-color:rgba(245,54,92,0.3)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M9 6V4h6v2"/></svg>
          </button>` : ''}
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  }
}

async function openDynamicInvModal(id = null) {
  const inv = id ? dynamicInvData.find(i => i.id === id) : null;
  const defaultContent = inv ? inv.content : '#!/usr/bin/env python3\nimport json\nimport sys\n\n# Dynamic inventory script\nif len(sys.argv) > 1 and sys.argv[1] == "--list":\n    print(json.dumps({"_meta": {"hostvars": {}}}))\n';

  document.getElementById('dynamic-inv-modal-title').textContent = inv ? 'Edit Dynamic Inventory' : 'New Dynamic Inventory';
  document.getElementById('dynamic-inv-id').value = inv ? inv.id : '';
  document.getElementById('dynamic-inv-name').value = inv ? inv.name : '';
  document.getElementById('dynamic-inv-type').value = inv ? inv.inv_type : 'script';

  // Load templates
  if (dynamicInvTemplates.length === 0) {
    try {
      const res = await api('GET', '/api/dynamic-inventories/templates');
      dynamicInvTemplates = await res.json();
    } catch (e) { }
  }

  const templateSelect = document.getElementById('dynamic-inv-template');
  templateSelect.innerHTML = '<option value="">— Select template —</option>';
  for (const t of dynamicInvTemplates) {
    const opt = document.createElement('option');
    opt.value = t.name;
    opt.textContent = t.name;
    templateSelect.appendChild(opt);
  }

  // Destroy existing editor
  if (cmDynamicInv) {
    cmDynamicInv.toTextArea();
    cmDynamicInv = null;
  }

  const textarea = document.getElementById('dynamic-inv-content');
  textarea.value = defaultContent;

  showModal('dynamic-inv-modal');

  // Initialize CodeMirror
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      const mode = (inv ? inv.inv_type : 'script') === 'script' ? 'python' : 'yaml';
      cmDynamicInv = CodeMirror.fromTextArea(textarea, {
        mode: mode,
        theme: 'dracula',
        lineNumbers: true,
        indentUnit: 2,
        tabSize: 2,
        indentWithTabs: false,
        lineWrapping: false,
      });
      cmDynamicInv.setValue(defaultContent);
      cmDynamicInv.refresh();
    });
  });
}

function loadDynamicInvTemplate() {
  const templateName = document.getElementById('dynamic-inv-template').value;
  if (!templateName) return;

  const template = dynamicInvTemplates.find(t => t.name === templateName);
  if (template && cmDynamicInv) {
    document.getElementById('dynamic-inv-type').value = template.inv_type;
    cmDynamicInv.setOption('mode', template.inv_type === 'script' ? 'python' : 'yaml');
    cmDynamicInv.setValue(template.content);
  }
}

async function saveDynamicInv() {
  const id = document.getElementById('dynamic-inv-id').value;
  const content = cmDynamicInv ? cmDynamicInv.getValue() : document.getElementById('dynamic-inv-content').value;

  const data = {
    name: document.getElementById('dynamic-inv-name').value.trim(),
    inv_type: document.getElementById('dynamic-inv-type').value,
    content,
    enabled: true,
  };

  if (!data.name) { toast('Name is required', 'error'); return; }

  const res = id
    ? await api('PUT', `/api/dynamic-inventories/${id}`, data)
    : await api('POST', '/api/dynamic-inventories', data);

  if (res.ok) {
    toast(id ? 'Inventory updated' : 'Inventory created', 'success');
    closeModal('dynamic-inv-modal');
    loadDynamicInventories();
  } else {
    const err = await res.json().catch(() => ({}));
    toast(err.error || 'Failed to save inventory', 'error');
  }
}

async function deleteDynamicInv(id) {
  if (!confirm('Delete this dynamic inventory?')) return;
  const res = await api('DELETE', `/api/dynamic-inventories/${id}`);
  if (res.ok) { toast('Inventory deleted', 'success'); loadDynamicInventories(); }
  else { toast('Failed to delete inventory', 'error'); }
}

async function testDynamicInv() {
  const id = document.getElementById('dynamic-inv-id').value;
  if (!id) {
    toast('Save the inventory first before testing', 'error');
    return;
  }
  await testDynamicInvById(parseInt(id));
}

async function testDynamicInvById(id) {
  document.getElementById('dynamic-inv-test-output').textContent = 'Running test...';
  showModal('dynamic-inv-test-modal');

  const res = await api('POST', `/api/dynamic-inventories/${id}/test`);
  const data = await res.json();

  const outputEl = document.getElementById('dynamic-inv-test-output');
  if (data.ok) {
    outputEl.textContent = data.output || '(empty output)';
  } else {
    outputEl.textContent = `ERROR:\n${data.error || 'Unknown error'}\n\nOutput:\n${data.output || ''}`;
  }
}

// ── Ansible Autocompletion ────────────────────────────────────────────────────

let ansibleModules = [];

async function loadAnsibleModules() {
  try {
    const res = await api('GET', '/api/ansible/modules');
    ansibleModules = await res.json();
  } catch (e) { }
}

function ansibleHint(cm) {
  const cur = cm.getCursor();
  const token = cm.getTokenAt(cur);
  const line = cm.getLine(cur.line);
  const start = token.start;
  const end = cur.ch;
  const word = token.string.slice(0, end - start).toLowerCase();

  const topLevelKeys = [
    'hosts', 'tasks', 'vars', 'handlers', 'roles', 'become', 'become_user',
    'gather_facts', 'pre_tasks', 'post_tasks', 'environment', 'collections',
    'name', 'when', 'loop', 'with_items', 'register', 'notify', 'tags',
    'block', 'rescue', 'always', 'ignore_errors', 'changed_when', 'failed_when',
    'delegate_to', 'run_once', 'serial', 'strategy', 'any_errors_fatal',
  ];

  const ansibleVars = [
    'ansible_host', 'ansible_user', 'ansible_password', 'ansible_port',
    'ansible_connection', 'ansible_become', 'ansible_become_user',
    'inventory_hostname', 'inventory_hostname_short', 'groups', 'group_names',
    'hostvars', 'ansible_facts', 'ansible_distribution', 'ansible_os_family',
  ];

  let list = [];

  // Check context
  const trimmed = line.trim();
  const indent = line.length - line.trimStart().length;

  // Module suggestions (after "- " at task level)
  if (trimmed.startsWith('- ') && indent >= 4) {
    list = ansibleModules.map(m => ({
      text: m.name + ':',
      displayText: m.name + ' — ' + m.desc,
    }));
  }
  // Top-level or task keys
  else if (indent <= 4 || trimmed.startsWith('-')) {
    list = topLevelKeys.filter(k => k.startsWith(word)).map(k => k + ':');
  }
  // Variable suggestions inside {{ }}
  else if (line.includes('{{')) {
    list = ansibleVars.filter(v => v.startsWith(word));
  }
  // Module names
  else {
    const moduleNames = ansibleModules.map(m => m.name);
    list = moduleNames.filter(m => m.startsWith(word)).map(m => m + ':');
  }

  if (word.length > 0) {
    list = list.filter(item => {
      const text = typeof item === 'string' ? item : item.text;
      return text.toLowerCase().startsWith(word);
    });
  }

  return {
    list: list.slice(0, 15),
    from: CodeMirror.Pos(cur.line, start),
    to: CodeMirror.Pos(cur.line, end),
  };
}

// ── Global Search (Ctrl+K) ────────────────────────────────────────────────────

let searchDebounceTimer = null;
let searchSelectedIndex = -1;
let searchResults = [];
const RECENT_SEARCHES_KEY = 'ansible_gui_recent_searches';

function openSearchModal() {
  const modal = document.getElementById('search-modal');
  const input = document.getElementById('global-search-input');
  modal.classList.add('show');
  input.value = '';
  input.focus();
  searchSelectedIndex = -1;
  searchResults = [];
  document.getElementById('search-results').innerHTML = `
    <div class="search-empty" id="search-empty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <p>Type to search across all items</p>
    </div>
  `;
  renderRecentSearches();
}

function closeSearchModal() {
  document.getElementById('search-modal').classList.remove('show');
  searchSelectedIndex = -1;
  searchResults = [];
}

function getRecentSearches() {
  try {
    const stored = localStorage.getItem(RECENT_SEARCHES_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch (e) {
    return [];
  }
}

function addRecentSearch(item) {
  let recent = getRecentSearches();
  // Remove duplicates
  recent = recent.filter(r => !(r.type === item.type && r.id === item.id));
  // Add to beginning
  recent.unshift(item);
  // Keep only last 5
  recent = recent.slice(0, 5);
  localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(recent));
}

function renderRecentSearches() {
  const container = document.getElementById('search-recent-container');
  const list = document.getElementById('search-recent-list');
  const recent = getRecentSearches();

  if (recent.length === 0) {
    container.style.display = 'none';
    return;
  }

  container.style.display = '';
  list.innerHTML = '';

  recent.forEach((item, idx) => {
    const el = document.createElement('div');
    el.className = 'search-result-item';
    el.setAttribute('data-index', `recent-${idx}`);
    el.innerHTML = `
      ${getSearchResultIcon(item.type)}
      <div class="search-result-content">
        <div class="search-result-name">${escapeHtml(item.name)}</div>
        <div class="search-result-subtitle">${escapeHtml(item.subtitle || '')}</div>
      </div>
      <span class="search-result-type">${item.type}</span>
    `;
    el.onclick = () => navigateToSearchResult(item);
    list.appendChild(el);
  });
}

function getSearchResultIcon(type) {
  const icons = {
    host: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>',
    playbook: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
    execution: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    schedule: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
  };
  return `<div class="search-result-icon ${type}">${icons[type] || icons.host}</div>`;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

async function performSearch(query) {
  if (!query.trim()) {
    document.getElementById('search-results').innerHTML = `
      <div class="search-empty" id="search-empty">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <p>Type to search across all items</p>
      </div>
    `;
    searchResults = [];
    searchSelectedIndex = -1;
    document.getElementById('search-recent-container').style.display = '';
    renderRecentSearches();
    return;
  }

  document.getElementById('search-recent-container').style.display = 'none';

  try {
    const res = await api('GET', `/api/search?q=${encodeURIComponent(query)}`);
    const data = await res.json();
    renderSearchResults(data);
  } catch (e) {
    document.getElementById('search-results').innerHTML = `
      <div class="search-empty">
        <p>Search failed. Please try again.</p>
      </div>
    `;
  }
}

function renderSearchResults(data) {
  const container = document.getElementById('search-results');
  searchResults = [];
  let html = '';
  let globalIndex = 0;

  const categories = [
    { key: 'hosts', label: 'Hosts', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>' },
    { key: 'playbooks', label: 'Playbooks', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>' },
    { key: 'executions', label: 'Executions', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>' },
    { key: 'schedules', label: 'Schedules', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>' },
  ];

  for (const cat of categories) {
    const items = data[cat.key] || [];
    if (items.length === 0) continue;

    html += `<div class="search-category-header">${cat.icon} ${cat.label}</div>`;

    for (const item of items) {
      searchResults.push(item);
      html += `
        <div class="search-result-item" data-index="${globalIndex}" onclick="selectSearchResult(${globalIndex})">
          ${getSearchResultIcon(item.type)}
          <div class="search-result-content">
            <div class="search-result-name">${escapeHtml(item.name)}</div>
            <div class="search-result-subtitle">${escapeHtml(item.subtitle || '')}</div>
          </div>
          <span class="search-result-type">${item.type}</span>
        </div>
      `;
      globalIndex++;
    }
  }

  if (searchResults.length === 0) {
    html = `
      <div class="search-empty">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <p>No results found</p>
      </div>
    `;
  }

  container.innerHTML = html;
  searchSelectedIndex = -1;
}

function selectSearchResult(index) {
  if (index >= 0 && index < searchResults.length) {
    navigateToSearchResult(searchResults[index]);
  }
}

function navigateToSearchResult(item) {
  addRecentSearch(item);
  closeSearchModal();

  switch (item.type) {
    case 'host':
      showPage('inventory');
      // Highlight/scroll to host after page loads
      setTimeout(() => {
        const rows = document.querySelectorAll('#hosts-tbody tr');
        rows.forEach(row => {
          if (row.textContent.includes(item.name)) {
            row.style.background = 'var(--accent-glow)';
            row.scrollIntoView({ behavior: 'smooth', block: 'center' });
            setTimeout(() => { row.style.background = ''; }, 2000);
          }
        });
      }, 200);
      break;

    case 'playbook':
      showPage('playbooks');
      // Open playbook modal for editing
      setTimeout(() => {
        const pb = playbooksData.find(p => p.id === item.id);
        if (pb && isAdmin()) {
          openPlaybookModal(item.id);
        }
      }, 300);
      break;

    case 'execution':
      showPage('executions');
      // Open output modal
      setTimeout(() => {
        openOutputModal(item.id);
      }, 300);
      break;

    case 'schedule':
      showPage('schedules');
      // Highlight schedule row
      setTimeout(() => {
        const rows = document.querySelectorAll('#schedules-tbody tr');
        rows.forEach(row => {
          if (row.textContent.includes(item.name)) {
            row.style.background = 'var(--accent-glow)';
            row.scrollIntoView({ behavior: 'smooth', block: 'center' });
            setTimeout(() => { row.style.background = ''; }, 2000);
          }
        });
      }, 200);
      break;
  }
}

function updateSearchSelection(direction) {
  const items = document.querySelectorAll('.search-result-item');
  if (items.length === 0) return;

  // Remove current selection
  items.forEach(item => item.classList.remove('selected'));

  // Update index
  if (direction === 'down') {
    searchSelectedIndex = (searchSelectedIndex + 1) % items.length;
  } else if (direction === 'up') {
    searchSelectedIndex = searchSelectedIndex <= 0 ? items.length - 1 : searchSelectedIndex - 1;
  }

  // Apply selection
  const selected = items[searchSelectedIndex];
  if (selected) {
    selected.classList.add('selected');
    selected.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

function handleSearchKeydown(e) {
  if (e.key === 'Escape') {
    closeSearchModal();
    e.preventDefault();
  } else if (e.key === 'ArrowDown') {
    updateSearchSelection('down');
    e.preventDefault();
  } else if (e.key === 'ArrowUp') {
    updateSearchSelection('up');
    e.preventDefault();
  } else if (e.key === 'Enter') {
    if (searchSelectedIndex >= 0 && searchSelectedIndex < searchResults.length) {
      navigateToSearchResult(searchResults[searchSelectedIndex]);
    } else {
      // Check if we're in recent searches
      const recentItems = document.querySelectorAll('#search-recent-list .search-result-item.selected');
      if (recentItems.length > 0) {
        recentItems[0].click();
      }
    }
    e.preventDefault();
  }
}

// Initialize global search
document.addEventListener('keydown', (e) => {
  // Ctrl+K or Cmd+K
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    openSearchModal();
  }
});

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  await initMe();
  loadAnsibleModules();
  showPage('dashboard');

  // Setup search modal events
  const searchInput = document.getElementById('global-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(() => {
        performSearch(e.target.value);
      }, 300);
    });

    searchInput.addEventListener('keydown', handleSearchKeydown);
  }

  // Close search modal on overlay click
  const searchModal = document.getElementById('search-modal');
  if (searchModal) {
    searchModal.addEventListener('click', (e) => {
      if (e.target === searchModal) {
        closeSearchModal();
      }
    });
  }
});
