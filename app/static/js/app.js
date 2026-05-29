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
  if (name === 'playbooks') loadPlaybooks();
  if (name === 'executions') loadExecutions();
  if (name === 'schedules') loadSchedules();
  if (name === 'settings') loadSettings();
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

async function loadDashboard() {
  const res = await api('GET', '/api/dashboard');
  const data = await res.json();
  document.getElementById('stat-hosts').textContent = data.total_hosts;
  document.getElementById('stat-reachable').textContent = data.reachable_hosts;
  document.getElementById('stat-playbooks').textContent = data.total_playbooks;
  document.getElementById('stat-executions').textContent = data.total_executions;

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
          <button class="btn btn-icon btn-sm" title="Edit" onclick="openHostModal(${h.id})">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button class="btn btn-icon btn-sm" title="Delete" onclick="deleteHost(${h.id})" style="color:var(--danger);border-color:rgba(245,54,92,0.3)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
          </button>
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
            <button class="btn btn-icon btn-sm" title="Edit" onclick="openPlaybookModal(${p.id})">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
            <button class="btn btn-icon btn-sm" title="Export .yml" onclick="exportPlaybook(${p.id})">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            </button>
            <button class="btn btn-icon btn-sm" title="Run" onclick="openRunModal(${p.id})" style="color:var(--success);border-color:rgba(39,217,108,0.3)">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            </button>
            <button class="btn btn-icon btn-sm" title="Delete" onclick="deletePlaybook(${p.id})" style="color:var(--danger);border-color:rgba(245,54,92,0.3)">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M9 6V4h6v2"/></svg>
            </button>
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
        extraKeys: { Tab: (cm) => cm.replaceSelection('  ') },
      });
      // Force set the value to ensure correct content
      cmEditor.setValue(newContent);
      cmEditor.refresh();
      cmEditor.clearHistory();
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

// ── Run Modal ─────────────────────────────────────────────────────────────────

let runPlaybookId = null;

function openRunModal(pbId) {
  runPlaybookId = pbId;
  const pb = playbooksData.find(p => p.id === pbId);
  document.getElementById('run-playbook-name').textContent = pb ? pb.name : '';
  document.getElementById('run-host-pattern').value = 'all';
  showModal('run-modal');
}

async function executePlaybook() {
  if (!runPlaybookId) return;
  const hostPattern = document.getElementById('run-host-pattern').value.trim() || 'all';

  const res = await api('POST', '/api/executions', {
    playbook_id: runPlaybookId,
    host_pattern: hostPattern,
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
          ${(e.status === 'running' || e.status === 'pending') ? `
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

  if (outputPollTimer) clearInterval(outputPollTimer);

  const poll = async () => {
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
          <button class="btn btn-icon btn-sm" onclick="openScheduleModal(${s.id})">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button class="btn btn-icon btn-sm" onclick="deleteSchedule(${s.id})" style="color:var(--danger);border-color:rgba(245,54,92,0.3)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M9 6V4h6v2"/></svg>
          </button>
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

// ── Modal helpers ─────────────────────────────────────────────────────────────

function showModal(id) {
  document.getElementById(id).classList.add('show');
}

function closeModal(id) {
  document.getElementById(id).classList.remove('show');
  if (id === 'output-modal' && outputPollTimer) {
    clearInterval(outputPollTimer);
    outputPollTimer = null;
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

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  showPage('dashboard');
});
