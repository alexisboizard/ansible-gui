// ──────────────────────────────────────────────
// State & Helpers
// ──────────────────────────────────────────────
let cmEditor = null;

function api(method, url, data) {
    const opts = {
        method,
        headers: { "Content-Type": "application/json" },
    };
    if (data) opts.body = JSON.stringify(data);
    return fetch(url, opts).then(async (r) => {
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

        // Load data for the active tab
        const tab = link.dataset.tab;
        if (tab === "inventory") loadHosts();
        else if (tab === "playbooks") loadPlaybooks();
        else if (tab === "executions") loadExecutions();
        else if (tab === "schedules") loadSchedules();
    });
});

// ──────────────────────────────────────────────
// HOSTS
// ──────────────────────────────────────────────
function loadHosts() {
    api("GET", "/api/hosts").then((hosts) => {
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
                <td><strong>${esc(h.hostname)}</strong></td>
                <td><code>${esc(h.ip_address)}</code></td>
                <td>${h.port}</td>
                <td>${esc(h.username)}</td>
                <td><span class="badge bg-info">${esc(h.group_name)}</span></td>
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
    });
}

function showHostModal(host = null) {
    document.getElementById("hostModalTitle").textContent = host ? "Modifier l'hôte" : "Ajouter un hôte";
    document.getElementById("host-id").value = host ? host.id : "";
    document.getElementById("host-hostname").value = host ? host.hostname : "";
    document.getElementById("host-ip").value = host ? host.ip_address : "";
    document.getElementById("host-port").value = host ? host.port : 22;
    document.getElementById("host-username").value = host ? host.username : "root";
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
        username: document.getElementById("host-username").value.trim() || "root",
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

    // Initialize CodeMirror after modal is shown
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
            // Switch to executions tab
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
                    <button class="btn btn-sm btn-outline-secondary" onclick="viewOutput(${e.id})">
                        <i class="bi bi-terminal"></i> Sortie
                    </button>
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

// ──────────────────────────────────────────────
// SCHEDULES
// ──────────────────────────────────────────────
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

    // Load playbooks into select
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
    loadHosts();
});
