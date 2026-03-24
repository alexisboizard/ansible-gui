// ──────────────────────────────────────────────
// State & Helpers
// ──────────────────────────────────────────────
let cmEditor = null;
let settingsSchema = {};
let settingsValues = {};
let allHosts = [];

// ──────────────────────────────────────────────
// Theme Management
// ──────────────────────────────────────────────
function initTheme() {
    const saved = localStorage.getItem("theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const theme = saved || (prefersDark ? "dark" : "light");
    applyTheme(theme);
}

function applyTheme(theme) {
    const html = document.documentElement;
    const body = document.body;
    const icon = document.getElementById("theme-icon");

    // Apply to both html and body for compatibility
    html.classList.remove("dark-theme", "light-theme");
    html.classList.add(theme + "-theme");
    if (body) {
        body.classList.remove("dark-theme", "light-theme");
        body.classList.add(theme + "-theme");
    }

    if (icon) {
        icon.className = theme === "dark" ? "bi bi-sun-fill" : "bi bi-moon-fill";
    }

    localStorage.setItem("theme", theme);
}

function toggleTheme() {
    const html = document.documentElement;
    const isLight = html.classList.contains("light-theme");
    applyTheme(isLight ? "dark" : "light");
}

// Initialize theme immediately to avoid flash
initTheme();

function api(method, url, data) {
    const opts = {
        method,
        headers: { "Content-Type": "application/json" },
    };
    if (data) opts.body = JSON.stringify(data);
    return fetch(url, opts).then(async (r) => {
        if (r.status === 401) {
            window.location.href = "/login";
            throw new Error("Session expirée");
        }
        const json = await r.json();
        if (!r.ok) throw new Error(json.error || "Erreur serveur");
        return json;
    });
}

function showToast(message, type = "success") {
    const toast = document.getElementById("toast");
    const body = document.getElementById("toast-body");
    toast.className = `toast align-items-center text-white border-0 bg-${type}`;
    body.textContent = message;
    new bootstrap.Toast(toast, { delay: 3000 }).show();
}

function formatDate(iso) {
    if (!iso) return "-";
    const d = new Date(iso);
    return d.toLocaleString("fr-FR");
}

function statusBadge(status) {
    const map = {
        pending: "secondary",
        running: "primary",
        success: "success",
        failed: "danger",
    };
    return `<span class="badge bg-${map[status] || "secondary"} status-badge">${status}</span>`;
}

// ──────────────────────────────────────────────
// Navigation
// ──────────────────────────────────────────────
document.querySelectorAll("[data-tab]").forEach((link) => {
    link.addEventListener("click", (e) => {
        e.preventDefault();
        document.querySelectorAll("[data-tab]").forEach((l) => l.classList.remove("active"));
        link.classList.add("active");
        document.querySelectorAll(".tab-content-section").forEach((s) => s.classList.add("d-none"));
        document.getElementById("tab-" + link.dataset.tab).classList.remove("d-none");

        const tab = link.dataset.tab;
        if (tab === "dashboard") loadDashboard();
        else if (tab === "inventory") loadHosts();
        else if (tab === "playbooks") loadPlaybooks();
        else if (tab === "executions") loadExecutions();
        else if (tab === "schedules") loadSchedules();
        else if (tab === "settings") loadSettings();
    });
});

// ──────────────────────────────────────────────
// DASHBOARD
// ──────────────────────────────────────────────
function loadDashboard() {
    // Load stats
    api("GET", "/api/hosts").then((hosts) => {
        document.getElementById("stat-hosts").textContent = hosts.length;
        const up = hosts.filter(h => h.reachable === true).length;
        const down = hosts.filter(h => h.reachable === false).length;
        document.getElementById("stat-hosts-up").textContent = up;
        document.getElementById("stat-hosts-down").textContent = down;
    });

    api("GET", "/api/playbooks").then((playbooks) => {
        document.getElementById("stat-playbooks").textContent = playbooks.length;
    });

    // Recent executions
    api("GET", "/api/executions").then((executions) => {
        const tbody = document.getElementById("dashboard-recent-executions");
        const recent = executions.slice(0, 5);
        if (recent.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Aucune execution</td></tr>';
            return;
        }
        tbody.innerHTML = recent.map(e => `
            <tr>
                <td>${esc(e.playbook_name || "?")}</td>
                <td>${statusBadge(e.status)}</td>
                <td><small class="text-muted">${formatDate(e.started_at)}</small></td>
            </tr>
        `).join("");
    });

    // Upcoming schedules
    api("GET", "/api/schedules").then((schedules) => {
        const tbody = document.getElementById("dashboard-upcoming-schedules");
        const upcoming = schedules.filter(s => s.enabled && s.next_run_at).slice(0, 5);
        if (upcoming.length === 0) {
            tbody.innerHTML = '<tr><td colspan="2" class="text-center text-muted">Aucune planification</td></tr>';
            return;
        }
        tbody.innerHTML = upcoming.map(s => `
            <tr>
                <td>${esc(s.playbook_name || "?")}</td>
                <td><small class="text-muted">${formatDate(s.next_run_at)}</small></td>
            </tr>
        `).join("");
    });
}

// ──────────────────────────────────────────────
// HOSTS
// ──────────────────────────────────────────────
function loadHosts() {
    api("GET", "/api/hosts").then((hosts) => {
        allHosts = hosts;
        renderHosts(hosts);
    });
}

function hostStatusDot(host) {
    if (host.reachable === null || host.reachable === undefined) {
        return '<span class="host-status-dot status-unknown" title="Inconnu"></span>';
    }
    if (host.reachable) {
        const latency = host.ping_latency != null ? ` (${host.ping_latency.toFixed(1)} ms)` : "";
        const lastPing = host.last_ping ? `\nDernier ping : ${formatDate(host.last_ping)}` : "";
        return `<span class="host-status-dot status-up" title="Joignable${latency}${lastPing}"></span>`;
    }
    const lastPing = host.last_ping ? `\nDernier ping : ${formatDate(host.last_ping)}` : "";
    return `<span class="host-status-dot status-down" title="Injoignable${lastPing}"></span>`;
}

function renderHosts(hosts) {
    const tbody = document.getElementById("hosts-table");
    const empty = document.getElementById("hosts-empty");
    if (hosts.length === 0) {
        tbody.innerHTML = "";
        empty.classList.remove("d-none");
        return;
    }
    empty.classList.add("d-none");
    tbody.innerHTML = hosts
        .map(
            (h) => `
        <tr>
            <td class="text-center">${hostStatusDot(h)}</td>
            <td><strong>${esc(h.hostname)}</strong></td>
            <td><code>${esc(h.ip_address)}</code></td>
            <td>${h.port}</td>
            <td>${esc(h.username)}</td>
            <td>${(h.group_name || "all").split(",").map(g => `<span class="badge bg-info me-1">${esc(g.trim())}</span>`).join("")}</td>
            <td>${esc(h.description)}</td>
            <td>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-primary" onclick="editHost(${h.id})" title="Modifier">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-outline-danger" onclick="deleteHost(${h.id})" title="Supprimer">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </td>
        </tr>`
        )
        .join("");
}

function triggerPing() {
    api("POST", "/api/hosts/ping")
        .then((r) => {
            showToast(r.message);
            // Reload hosts after a delay to let ping finish
            setTimeout(loadHosts, 5000);
        })
        .catch((e) => showToast(e.message, "danger"));
}

function showImportModal() {
    document.getElementById("import-file").value = "";
    document.getElementById("import-result").innerHTML = "";
    new bootstrap.Modal(document.getElementById("importModal")).show();
}

function importHosts() {
    const fileInput = document.getElementById("import-file");
    const resultDiv = document.getElementById("import-result");

    if (!fileInput.files || !fileInput.files[0]) {
        resultDiv.innerHTML = '<div class="alert alert-warning">Selectionnez un fichier CSV</div>';
        return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    resultDiv.innerHTML = '<div class="text-muted"><i class="bi bi-hourglass-split"></i> Import en cours...</div>';

    fetch("/api/hosts/import", {
        method: "POST",
        body: formData,
    })
        .then(async (r) => {
            const json = await r.json();
            if (!r.ok) throw new Error(json.error || "Erreur serveur");
            return json;
        })
        .then((r) => {
            let html = `<div class="alert alert-success"><i class="bi bi-check-circle"></i> ${esc(r.message)}</div>`;
            if (r.errors && r.errors.length > 0) {
                html += '<div class="alert alert-warning mt-2"><strong>Avertissements :</strong><ul class="mb-0 mt-2">';
                r.errors.forEach((e) => {
                    html += `<li>${esc(e)}</li>`;
                });
                html += "</ul></div>";
            }
            resultDiv.innerHTML = html;
            loadHosts();
        })
        .catch((e) => {
            resultDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-x-circle"></i> ${esc(e.message)}</div>`;
        });
}

function filterHosts() {
    const q = document.getElementById("hosts-search").value.toLowerCase().trim();
    if (!q) {
        renderHosts(allHosts);
        return;
    }
    const filtered = allHosts.filter((h) =>
        (h.hostname || "").toLowerCase().includes(q) ||
        (h.ip_address || "").toLowerCase().includes(q) ||
        (h.group_name || "").toLowerCase().includes(q) ||
        (h.username || "").toLowerCase().includes(q) ||
        (h.description || "").toLowerCase().includes(q)
    );
    renderHosts(filtered);
}

function showHostModal(host = null) {
    document.getElementById("hostModalTitle").textContent = host ? "Modifier l'hôte" : "Ajouter un hôte";
    document.getElementById("host-id").value = host ? host.id : "";
    document.getElementById("host-hostname").value = host ? host.hostname : "";
    document.getElementById("host-ip").value = host ? host.ip_address : "";
    document.getElementById("host-port").value = host ? host.port : 22;
    document.getElementById("host-username").value = host ? host.username : "ansible";
    document.getElementById("host-group").value = host ? host.group_name : "all";
    document.getElementById("host-variables").value = host ? host.variables : "{}";
    document.getElementById("host-description").value = host ? host.description : "";
    new bootstrap.Modal(document.getElementById("hostModal")).show();
}

function editHost(id) {
    api("GET", `/api/hosts/${id}`).then((host) => showHostModal(host));
}

function saveHost() {
    const id = document.getElementById("host-id").value;
    const data = {
        hostname: document.getElementById("host-hostname").value.trim(),
        ip_address: document.getElementById("host-ip").value.trim(),
        port: parseInt(document.getElementById("host-port").value) || 22,
        username: document.getElementById("host-username").value.trim() || "ansible",
        group_name: document.getElementById("host-group").value.trim() || "all",
        variables: document.getElementById("host-variables").value.trim() || "{}",
        description: document.getElementById("host-description").value.trim(),
    };

    if (!data.hostname || !data.ip_address) {
        showToast("Hostname et adresse IP sont requis", "danger");
        return;
    }

    const method = id ? "PUT" : "POST";
    const url = id ? `/api/hosts/${id}` : "/api/hosts";

    api(method, url, data)
        .then(() => {
            bootstrap.Modal.getInstance(document.getElementById("hostModal")).hide();
            showToast(id ? "Hôte mis à jour" : "Hôte ajouté");
            loadHosts();
        })
        .catch((e) => showToast(e.message, "danger"));
}

function deleteHost(id) {
    if (!confirm("Supprimer cet hôte ?")) return;
    api("DELETE", `/api/hosts/${id}`)
        .then(() => {
            showToast("Hôte supprimé");
            loadHosts();
        })
        .catch((e) => showToast(e.message, "danger"));
}

// ──────────────────────────────────────────────
// PLAYBOOKS
// ──────────────────────────────────────────────
function loadPlaybooks() {
    api("GET", "/api/playbooks").then((playbooks) => {
        const container = document.getElementById("playbooks-list");
        const empty = document.getElementById("playbooks-empty");
        if (playbooks.length === 0) {
            container.innerHTML = "";
            empty.classList.remove("d-none");
            return;
        }
        empty.classList.add("d-none");
        container.innerHTML = playbooks
            .map(
                (p) => `
            <div class="col-md-4 mb-3">
                <div class="card playbook-card h-100">
                    <div class="card-body">
                        <h5 class="card-title"><i class="bi bi-file-earmark-code"></i> ${esc(p.name)}</h5>
                        <p class="card-text text-muted">${esc(p.description) || "<em>Pas de description</em>"}</p>
                        <small class="text-muted">Modifié : ${formatDate(p.updated_at)}</small>
                    </div>
                    <div class="card-footer d-flex gap-2">
                        <button class="btn btn-sm btn-outline-primary" onclick="editPlaybook(${p.id})">
                            <i class="bi bi-pencil"></i> Modifier
                        </button>
                        <button class="btn btn-sm btn-success" onclick="showRunModal(${p.id}, '${esc(p.name)}')">
                            <i class="bi bi-play-fill"></i> Exécuter
                        </button>
                        <button class="btn btn-sm btn-outline-danger ms-auto" onclick="deletePlaybook(${p.id})">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>
            </div>`
            )
            .join("");
    });
}

function showPlaybookModal(playbook = null) {
    document.getElementById("playbookModalTitle").textContent = playbook
        ? "Modifier le playbook"
        : "Nouveau playbook";
    document.getElementById("playbook-id").value = playbook ? playbook.id : "";
    document.getElementById("playbook-name").value = playbook ? playbook.name : "";
    document.getElementById("playbook-description").value = playbook ? playbook.description : "";

    const defaultContent = `---
- name: Mon playbook
  hosts: all
  become: true
  tasks:
    - name: Ping
      ansible.builtin.ping:
`;

    const modal = new bootstrap.Modal(document.getElementById("playbookModal"));
    modal.show();

    document.getElementById("playbookModal").addEventListener(
        "shown.bs.modal",
        function initCM() {
            const textarea = document.getElementById("playbook-content");
            textarea.value = playbook ? playbook.content : defaultContent;

            if (cmEditor) {
                cmEditor.toTextArea();
                cmEditor = null;
            }

            cmEditor = CodeMirror.fromTextArea(textarea, {
                mode: "yaml",
                theme: "dracula",
                lineNumbers: true,
                indentUnit: 2,
                tabSize: 2,
                indentWithTabs: false,
                lineWrapping: true,
                extraKeys: {
                    Tab: function (cm) {
                        cm.replaceSelection("  ", "end");
                    },
                },
            });
            cmEditor.refresh();

            document.getElementById("playbookModal").removeEventListener("shown.bs.modal", initCM);
        },
        { once: true }
    );
}

function editPlaybook(id) {
    api("GET", `/api/playbooks/${id}`).then((p) => showPlaybookModal(p));
}

function savePlaybook() {
    const id = document.getElementById("playbook-id").value;
    const content = cmEditor ? cmEditor.getValue() : document.getElementById("playbook-content").value;
    const data = {
        name: document.getElementById("playbook-name").value.trim(),
        description: document.getElementById("playbook-description").value.trim(),
        content: content,
    };

    if (!data.name || !data.content) {
        showToast("Le nom et le contenu sont requis", "danger");
        return;
    }

    const method = id ? "PUT" : "POST";
    const url = id ? `/api/playbooks/${id}` : "/api/playbooks";

    api(method, url, data)
        .then(() => {
            bootstrap.Modal.getInstance(document.getElementById("playbookModal")).hide();
            if (cmEditor) {
                cmEditor.toTextArea();
                cmEditor = null;
            }
            showToast(id ? "Playbook mis à jour" : "Playbook créé");
            loadPlaybooks();
        })
        .catch((e) => showToast(e.message, "danger"));
}

function deletePlaybook(id) {
    if (!confirm("Supprimer ce playbook ?")) return;
    api("DELETE", `/api/playbooks/${id}`)
        .then(() => {
            showToast("Playbook supprimé");
            loadPlaybooks();
        })
        .catch((e) => showToast(e.message, "danger"));
}

// ──────────────────────────────────────────────
// EXECUTIONS
// ──────────────────────────────────────────────
function showRunModal(playbookId, playbookName) {
    document.getElementById("run-playbook-id").value = playbookId;
    document.getElementById("run-playbook-name").textContent = playbookName;
    document.getElementById("run-hosts").value = "all";
    document.getElementById("run-notify").checked = false;
    new bootstrap.Modal(document.getElementById("runModal")).show();
}

function executePlaybook() {
    const data = {
        playbook_id: parseInt(document.getElementById("run-playbook-id").value),
        hosts_pattern: document.getElementById("run-hosts").value.trim() || "all",
        notify: document.getElementById("run-notify").checked,
    };

    api("POST", "/api/executions", data)
        .then(() => {
            bootstrap.Modal.getInstance(document.getElementById("runModal")).hide();
            showToast("Playbook lancé en arrière-plan");
            document.querySelector('[data-tab="executions"]').click();
        })
        .catch((e) => showToast(e.message, "danger"));
}

function loadExecutions() {
    api("GET", "/api/executions").then((executions) => {
        const tbody = document.getElementById("executions-table");
        tbody.innerHTML = executions
            .map(
                (e) => `
            <tr>
                <td>${e.id}</td>
                <td>${esc(e.playbook_name || "?")}</td>
                <td>${esc(e.hosts_pattern)}</td>
                <td>${statusBadge(e.status)}</td>
                <td>${formatDate(e.started_at)}</td>
                <td>${formatDate(e.finished_at)}</td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-secondary" onclick="viewOutput(${e.id})">
                            <i class="bi bi-terminal"></i> Sortie
                        </button>
                        ${e.status === "running" || e.status === "pending" ? `<button class="btn btn-outline-danger" onclick="cancelExecution(${e.id})" title="Annuler"><i class="bi bi-x-circle"></i></button>` : ""}
                    </div>
                </td>
            </tr>`
            )
            .join("");
    });
}

function viewOutput(executionId) {
    api("GET", `/api/executions/${executionId}`).then((e) => {
        document.getElementById("execution-output").textContent = e.output || "(en attente...)";
        new bootstrap.Modal(document.getElementById("outputModal")).show();
    });
}

function purgeExecutions(mode) {
    const labels = {
        completed: "toutes les exécutions terminées",
        "7days": "les exécutions de plus de 7 jours",
        "30days": "les exécutions de plus de 30 jours",
        all: "TOUTES les exécutions",
    };
    if (!confirm(`Supprimer ${labels[mode] || mode} ?`)) return;

    api("POST", "/api/executions/purge", { mode })
        .then((r) => {
            showToast(r.message);
            loadExecutions();
        })
        .catch((e) => showToast(e.message, "danger"));
}

function cancelExecution(id) {
    if (!confirm("Annuler cette exécution ?")) return;
    api("POST", `/api/executions/${id}/cancel`)
        .then((r) => {
            showToast(r.message);
            loadExecutions();
        })
        .catch((e) => showToast(e.message, "danger"));
}

// ──────────────────────────────────────────────
// SCHEDULES
// ──────────────────────────────────────────────
function scheduleLastRunBadge(s) {
    if (!s.last_run_at) return '<span class="text-muted">-</span>';
    const statusMap = { success: "success", failed: "danger" };
    const cls = statusMap[s.last_run_status] || "secondary";
    return `<span class="badge bg-${cls}">${s.last_run_status}</span> <small class="text-muted">${formatDate(s.last_run_at)}</small>`;
}

function loadSchedules() {
    api("GET", "/api/schedules").then((schedules) => {
        const tbody = document.getElementById("schedules-table");
        tbody.innerHTML = schedules
            .map(
                (s) => `
            <tr>
                <td>${esc(s.playbook_name || "?")}</td>
                <td><code>${esc(s.cron_expression)}</code></td>
                <td>${esc(s.hosts_pattern)}</td>
                <td>${scheduleLastRunBadge(s)}</td>
                <td>${s.next_run_at ? formatDate(s.next_run_at) : '<span class="text-muted">-</span>'}</td>
                <td>${esc(s.notify_email) || "-"}</td>
                <td>
                    <div class="form-check form-switch">
                        <input class="form-check-input" type="checkbox" ${s.enabled ? "checked" : ""}
                               onchange="toggleSchedule(${s.id}, this.checked)">
                    </div>
                </td>
                <td>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteSchedule(${s.id})">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>`
            )
            .join("");
    });
}

function showScheduleModal() {
    document.getElementById("schedule-id").value = "";
    document.getElementById("schedule-cron").value = "";
    document.getElementById("schedule-hosts").value = "all";
    document.getElementById("schedule-email").value = "";
    document.getElementById("schedule-description").value = "";
    document.getElementById("schedule-enabled").checked = true;

    api("GET", "/api/playbooks").then((playbooks) => {
        const select = document.getElementById("schedule-playbook");
        select.innerHTML = playbooks
            .map((p) => `<option value="${p.id}">${esc(p.name)}</option>`)
            .join("");
        new bootstrap.Modal(document.getElementById("scheduleModal")).show();
    });
}

function saveSchedule() {
    const id = document.getElementById("schedule-id").value;
    const data = {
        playbook_id: parseInt(document.getElementById("schedule-playbook").value),
        cron_expression: document.getElementById("schedule-cron").value.trim(),
        hosts_pattern: document.getElementById("schedule-hosts").value.trim() || "all",
        notify_email: document.getElementById("schedule-email").value.trim(),
        description: document.getElementById("schedule-description").value.trim(),
        enabled: document.getElementById("schedule-enabled").checked,
    };

    if (!data.cron_expression) {
        showToast("L'expression cron est requise", "danger");
        return;
    }

    const method = id ? "PUT" : "POST";
    const url = id ? `/api/schedules/${id}` : "/api/schedules";

    api(method, url, data)
        .then(() => {
            bootstrap.Modal.getInstance(document.getElementById("scheduleModal")).hide();
            showToast(id ? "Planification mise à jour" : "Planification créée");
            loadSchedules();
        })
        .catch((e) => showToast(e.message, "danger"));
}

function toggleSchedule(id, enabled) {
    api("PUT", `/api/schedules/${id}`, { enabled })
        .then(() => showToast(enabled ? "Planification activée" : "Planification désactivée"))
        .catch((e) => showToast(e.message, "danger"));
}

function deleteSchedule(id) {
    if (!confirm("Supprimer cette planification ?")) return;
    api("DELETE", `/api/schedules/${id}`)
        .then(() => {
            showToast("Planification supprimée");
            loadSchedules();
        })
        .catch((e) => showToast(e.message, "danger"));
}

// ──────────────────────────────────────────────
// SETTINGS
// ──────────────────────────────────────────────
function loadSettings() {
    Promise.all([api("GET", "/api/settings/schema"), api("GET", "/api/settings")]).then(
        ([schema, values]) => {
            settingsSchema = schema;
            settingsValues = values;
            renderSettingsCategory("ssh");
            renderSettingsCategory("ldap");
            renderSettingsCategory("smtp");
            renderSettingsCategory("general");
        }
    );
}

function renderSettingsCategory(category) {
    const container = document.getElementById(`settings-${category}-fields`);
    if (!container || !settingsSchema[category]) return;

    container.innerHTML = settingsSchema[category]
        .map((field) => {
            const val = settingsValues[field.key] || "";

            if (field.type === "checkbox") {
                const checked = val === "true" ? "checked" : "";
                return `
                <div class="form-check form-switch mb-3">
                    <input class="form-check-input" type="checkbox" id="setting-${field.key}" ${checked}
                           data-setting-key="${field.key}">
                    <label class="form-check-label" for="setting-${field.key}">${esc(field.label)}</label>
                </div>`;
            }

            if (field.type === "textarea") {
                return `
                <div class="mb-3">
                    <label class="form-label" for="setting-${field.key}">${esc(field.label)}</label>
                    <textarea class="form-control" id="setting-${field.key}" rows="5"
                              placeholder="${esc(field.placeholder)}"
                              data-setting-key="${field.key}">${esc(val)}</textarea>
                    <div class="form-text">Collez votre cle privee SSH ici</div>
                </div>`;
            }

            const inputType = field.type === "password" ? "password" : field.type === "number" ? "number" : "text";
            return `
            <div class="mb-3">
                <label class="form-label" for="setting-${field.key}">${esc(field.label)}</label>
                <input type="${inputType}" class="form-control" id="setting-${field.key}"
                       placeholder="${esc(field.placeholder)}" value="${esc(val)}"
                       data-setting-key="${field.key}">
            </div>`;
        })
        .join("");
}

function collectSettingsCategory(category) {
    const data = {};
    if (!settingsSchema[category]) return data;

    settingsSchema[category].forEach((field) => {
        const el = document.getElementById(`setting-${field.key}`);
        if (!el) return;

        if (field.type === "checkbox") {
            data[field.key] = el.checked ? "true" : "false";
        } else {
            data[field.key] = el.value;
        }
    });
    return data;
}

function saveSettings(category) {
    const data = collectSettingsCategory(category);
    api("PUT", "/api/settings", data)
        .then(() => showToast("Paramètres enregistrés"))
        .catch((e) => showToast(e.message, "danger"));
}

function testLdap() {
    const resultEl = document.getElementById("ldap-test-result");
    resultEl.innerHTML = '<span class="text-muted">Test en cours...</span>';

    // Save first, then test
    const data = collectSettingsCategory("ldap");
    api("PUT", "/api/settings", data)
        .then(() => api("POST", "/api/settings/test-ldap"))
        .then((r) => {
            if (r.success) {
                resultEl.innerHTML = `<span class="text-success"><i class="bi bi-check-circle"></i> ${esc(r.message)}</span>`;
            } else {
                resultEl.innerHTML = `<span class="text-danger"><i class="bi bi-x-circle"></i> ${esc(r.message)}</span>`;
            }
        })
        .catch((e) => {
            resultEl.innerHTML = `<span class="text-danger"><i class="bi bi-x-circle"></i> ${esc(e.message)}</span>`;
        });
}

function testSmtp() {
    const resultEl = document.getElementById("smtp-test-result");
    resultEl.innerHTML = '<span class="text-muted">Test en cours...</span>';

    const data = collectSettingsCategory("smtp");
    api("PUT", "/api/settings", data)
        .then(() => api("POST", "/api/settings/test-smtp"))
        .then((r) => {
            if (r.success) {
                resultEl.innerHTML = `<span class="text-success"><i class="bi bi-check-circle"></i> ${esc(r.message)}</span>`;
            } else {
                resultEl.innerHTML = `<span class="text-danger"><i class="bi bi-x-circle"></i> ${esc(r.message)}</span>`;
            }
        })
        .catch((e) => {
            resultEl.innerHTML = `<span class="text-danger"><i class="bi bi-x-circle"></i> ${esc(e.message)}</span>`;
        });
}

// ──────────────────────────────────────────────
// ADMIN PASSWORD
// ──────────────────────────────────────────────
function changeAdminPassword() {
    const resultEl = document.getElementById("admin-password-result");
    const current = document.getElementById("admin-current-password").value;
    const newPw = document.getElementById("admin-new-password").value;
    const confirm = document.getElementById("admin-confirm-password").value;

    if (!current || !newPw || !confirm) {
        resultEl.innerHTML = '<span class="text-danger">Tous les champs sont requis.</span>';
        return;
    }
    if (newPw !== confirm) {
        resultEl.innerHTML = '<span class="text-danger">Les mots de passe ne correspondent pas.</span>';
        return;
    }

    resultEl.innerHTML = "";

    api("POST", "/api/auth/change-password", {
        current_password: current,
        new_password: newPw,
        confirm_password: confirm,
    })
        .then((r) => {
            resultEl.innerHTML = `<span class="text-success"><i class="bi bi-check-circle"></i> ${esc(r.message)}</span>`;
            document.getElementById("admin-current-password").value = "";
            document.getElementById("admin-new-password").value = "";
            document.getElementById("admin-confirm-password").value = "";
        })
        .catch((e) => {
            resultEl.innerHTML = `<span class="text-danger"><i class="bi bi-x-circle"></i> ${esc(e.message)}</span>`;
        });
}

// ──────────────────────────────────────────────
// Utils
// ──────────────────────────────────────────────
function esc(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// ──────────────────────────────────────────────
// Init
// ──────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    loadDashboard();
});
