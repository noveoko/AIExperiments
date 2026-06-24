/**
 * DevBox Setup Configurator — local-only wizard UI.
 * All API calls go to 127.0.0.1 only.
 */

const state = {
  schema: null,
  currentStep: 0,
  config: {},
  secrets: { ado_pat: "", databricks_token: "" },
  artifacts: {},
  selectedFile: null,
};

const SECRET_KEYS = new Set(["ado_pat", "databricks_token"]);

const DEFAULTS = {
  profile_name: "default",
  git_user_name: "",
  git_user_email: "",
  ado_org: "",
  ado_project: "",
  ado_auth_method: "gcm",
  environment: "corporate_devbox",
  wsl_distro: "Ubuntu-24.04",
  wsl_memory_gb: 8,
  wsl_processors: 4,
  wsl_swap_gb: 4,
  ide: "cursor",
  devbox_setup_path: "C:\\src\\devBoxSetup",
  python_default: "3.12.8",
  python_versions: ["3.12.8", "3.11.11"],
  package_manager_default: "uv",
  install_ruff: true,
  install_pytest: true,
  install_pre_commit: true,
  databricks_host: "",
  databricks_auth: "cli",
  databricks_runtime: "15.4.x-scala2.12",
  databricks_connect_version: "15.4.*",
  uc_catalog_dev: "dev_catalog",
  uc_catalog_prod: "prod_catalog",
  uc_schema: "etl",
  node_type_id: "Standard_DS3_v2",
  num_workers: 2,
  ci_package_manager: "uv",
  ci_python_versions: ["3.12", "3.11"],
  deploy_target: "none",
  service_connection_name: "",
  bundle_name: "etl_project",
  package_name: "etl_project",
};

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

function toast(msg, type = "success") {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = `toast show ${type}`;
  setTimeout(() => el.classList.remove("show"), 3000);
}

function getConfig() {
  const cfg = { ...DEFAULTS, ...state.config };
  cfg.wsl_memory_gb = Number(cfg.wsl_memory_gb);
  cfg.wsl_processors = Number(cfg.wsl_processors);
  cfg.wsl_swap_gb = Number(cfg.wsl_swap_gb);
  cfg.num_workers = Number(cfg.num_workers);
  cfg.install_ruff = Boolean(cfg.install_ruff);
  cfg.install_pytest = Boolean(cfg.install_pytest);
  cfg.install_pre_commit = Boolean(cfg.install_pre_commit);
  if (!Array.isArray(cfg.python_versions)) cfg.python_versions = [cfg.python_versions];
  if (!Array.isArray(cfg.ci_python_versions)) cfg.ci_python_versions = [cfg.ci_python_versions];
  return cfg;
}

function shouldShowField(field) {
  if (!field.showWhen) return true;
  return Object.entries(field.showWhen).every(([k, v]) => state.config[k] === v);
}

function renderField(field) {
  if (!shouldShowField(field)) return "";

  const val = SECRET_KEYS.has(field.key)
    ? state.secrets[field.key] || ""
    : state.config[field.key] ?? DEFAULTS[field.key] ?? "";

  let input = "";
  switch (field.type) {
    case "select":
      input = `<select data-key="${field.key}">${field.options
        .map((o) => `<option value="${o.value}" ${val === o.value ? "selected" : ""}>${o.label}</option>`)
        .join("")}</select>`;
      break;
    case "multiselect": {
      const selected = new Set(Array.isArray(val) ? val : []);
      input = `<div class="multiselect">${field.options
        .map(
          (o) =>
            `<label><input type="checkbox" data-key="${field.key}" data-multi value="${o.value}" ${
              selected.has(o.value) ? "checked" : ""
            }><span>${o.label}</span></label>`
        )
        .join("")}</div>`;
      break;
    }
    case "checkbox":
      input = `<div class="checkbox-group"><label><input type="checkbox" data-key="${field.key}" ${
        val ? "checked" : ""
      }> ${field.label}</label></div>`;
      break;
    case "secret":
      input = `<input type="password" data-key="${field.key}" data-secret value="${val}" autocomplete="off" placeholder="••••••••">`;
      break;
    case "number":
      input = `<input type="number" data-key="${field.key}" value="${val}" min="${field.min ?? ""}" max="${field.max ?? ""}" step="${field.step ?? 1}">`;
      break;
    case "email":
      input = `<input type="email" data-key="${field.key}" value="${val}" placeholder="${field.placeholder || ""}">`;
      break;
    default:
      input = `<input type="text" data-key="${field.key}" value="${val}" placeholder="${field.placeholder || ""}">`;
  }

  if (field.type === "checkbox") {
    return `<div class="field">${input}${field.hint ? `<div class="hint">${field.hint}</div>` : ""}</div>`;
  }

  return `<div class="field">
    <label>${field.label}${field.required ? " *" : ""}</label>
    ${input}
    ${field.hint ? `<div class="hint">${field.hint}</div>` : ""}
  </div>`;
}

function bindFormEvents(container) {
  container.querySelectorAll("[data-key]").forEach((el) => {
    const key = el.dataset.key;
    const handler = () => {
      if (el.dataset.secret || SECRET_KEYS.has(key)) {
        state.secrets[key] = el.value;
        return;
      }
      if (el.dataset.multi !== undefined) {
        const checked = [...container.querySelectorAll(`[data-key="${key}"][data-multi]:checked`)].map(
          (c) => c.value
        );
        state.config[key] = checked;
        return;
      }
      if (el.type === "checkbox") {
        state.config[key] = el.checked;
        return;
      }
      state.config[key] = el.type === "number" ? Number(el.value) : el.value;
    };
    el.addEventListener("change", handler);
    el.addEventListener("input", handler);
  });
}

function renderStepNav() {
  const nav = document.getElementById("step-nav");
  nav.innerHTML = state.schema.steps
    .map(
      (s, i) => `<li class="${i === state.currentStep ? "active" : ""} ${i < state.currentStep ? "done" : ""}">
      <span class="num">${i < state.currentStep ? "✓" : i + 1}</span>${s.title}
    </li>`
    )
    .join("");
}

function renderReviewStep() {
  const files = Object.keys(state.artifacts);
  const selected = state.selectedFile || files[0];
  return `
    <div class="step-header">
      <h2>Review & Generate</h2>
      <p>Preview generated artifacts, write to disk, or run bootstrap scripts.</p>
    </div>
    <div class="actions" style="border: none; padding-top: 0; margin-bottom: 1rem;">
      <button class="btn btn-primary" id="btn-preview">Preview artifacts</button>
      <button class="btn btn-success" id="btn-write">Write to ~/.config/devbox-setup/generated/</button>
      <button class="btn btn-secondary" id="btn-doctor">Run doctor</button>
      <button class="btn btn-secondary" id="btn-bootstrap">Run bootstrap</button>
    </div>
    <div class="review-panel ${files.length ? "" : "hidden"}" id="review-panel">
      <div class="file-list" id="file-list">
        ${files.map((f) => `<button data-file="${f}" class="${f === selected ? "active" : ""}">${f}</button>`).join("")}
      </div>
      <div class="preview"><pre id="file-preview">${escapeHtml(state.artifacts[selected] || "")}</pre></div>
    </div>
    <div class="output-panel hidden" id="output-panel">
      <pre id="run-output"></pre>
    </div>
  `;
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderStep() {
  renderStepNav();
  const step = state.schema.steps[state.currentStep];
  const container = document.getElementById("step-container");

  if (step.id === "review") {
    container.innerHTML = renderReviewStep();
    bindReviewEvents();
  } else {
    container.innerHTML = `
      <div class="step-header">
        <h2>${step.title}</h2>
        <p>${step.description}</p>
      </div>
      <div class="form-grid">${step.fields.map(renderField).join("")}</div>
    `;
    bindFormEvents(container);
  }

  document.getElementById("btn-back").disabled = state.currentStep === 0;
  document.getElementById("btn-next").textContent =
    state.currentStep === state.schema.steps.length - 1 ? "Finish" : "Next";
  document.getElementById("btn-next").classList.toggle(
    "hidden",
    state.currentStep === state.schema.steps.length - 1
  );
}

function bindReviewEvents() {
  document.getElementById("btn-preview")?.addEventListener("click", async () => {
    try {
      const res = await api("/api/generate", {
        method: "POST",
        body: JSON.stringify({ config: getConfig(), secrets: state.secrets }),
      });
      state.artifacts = res.artifacts;
      state.selectedFile = Object.keys(state.artifacts)[0];
      renderStep();
      toast("Artifacts generated");
    } catch (e) {
      toast(e.message, "error");
    }
  });

  document.getElementById("btn-write")?.addEventListener("click", async () => {
    try {
      const res = await api("/api/generate/write", {
        method: "POST",
        body: JSON.stringify({ config: getConfig(), secrets: state.secrets }),
      });
      toast(`Written to ${res.written_to}`);
    } catch (e) {
      toast(e.message, "error");
    }
  });

  document.getElementById("btn-doctor")?.addEventListener("click", () => runScript("doctor"));
  document.getElementById("btn-bootstrap")?.addEventListener("click", () => {
    if (confirm("Run full WSL bootstrap? This installs system packages and tools.")) {
      runScript("bootstrap");
    }
  });

  document.querySelectorAll("#file-list button").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.selectedFile = btn.dataset.file;
      document.querySelectorAll("#file-list button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("file-preview").textContent = state.artifacts[state.selectedFile] || "";
    });
  });
}

async function runScript(script) {
  const panel = document.getElementById("output-panel");
  const output = document.getElementById("run-output");
  panel.classList.remove("hidden");
  output.textContent = `Running ${script}...\n`;

  try {
    const res = await api("/api/run", {
      method: "POST",
      body: JSON.stringify({ script, config: getConfig() }),
    });
    output.textContent = res.output || "(no output)";
    toast(`${script}: ${res.status}`, res.status === "completed" ? "success" : "error");
  } catch (e) {
    output.textContent = e.message;
    toast(e.message, "error");
  }
}

async function saveProfile() {
  const name = state.config.profile_name || "default";
  try {
    await api(`/api/profiles/${encodeURIComponent(name)}`, {
      method: "POST",
      body: JSON.stringify({ config: getConfig(), secrets: state.secrets }),
    });
    await loadProfileList();
    document.getElementById("profile-select").value = name;
    toast(`Profile "${name}" saved locally`);
  } catch (e) {
    toast(e.message, "error");
  }
}

async function loadProfile(name) {
  if (!name) {
    state.config = { ...DEFAULTS };
    state.secrets = { ado_pat: "", databricks_token: "" };
    renderStep();
    return;
  }
  try {
    const res = await api(`/api/profiles/${encodeURIComponent(name)}`);
    state.config = { ...DEFAULTS, ...res.config };
    state.secrets = { ado_pat: "", databricks_token: "" };
    renderStep();
    const msg = res.has_secrets
      ? `Loaded "${name}" (secrets saved locally, not displayed)`
      : `Loaded profile "${name}"`;
    toast(msg);
  } catch (e) {
    toast(e.message, "error");
  }
}

async function loadProfileList() {
  const profiles = await api("/api/profiles");
  const sel = document.getElementById("profile-select");
  const current = sel.value;
  sel.innerHTML =
    '<option value="">— New profile —</option>' +
    profiles.map((p) => `<option value="${p}">${p}</option>`).join("");
  if (current) sel.value = current;
}

async function init() {
  state.schema = await api("/api/schema");
  state.config = { ...DEFAULTS };
  await loadProfileList();

  document.getElementById("btn-back").addEventListener("click", () => {
    if (state.currentStep > 0) {
      state.currentStep--;
      renderStep();
    }
  });

  document.getElementById("btn-next").addEventListener("click", () => {
    if (state.currentStep < state.schema.steps.length - 1) {
      state.currentStep++;
      renderStep();
    }
  });

  document.getElementById("btn-save").addEventListener("click", saveProfile);

  document.getElementById("profile-select").addEventListener("change", (e) => {
    loadProfile(e.target.value);
  });

  renderStep();
}

init().catch((e) => {
  document.getElementById("step-container").innerHTML = `<p style="color: var(--danger)">Failed to load: ${e.message}</p>`;
});