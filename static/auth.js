const authMessage = document.querySelector("#authMessage");
const loginForm = document.querySelector("#loginForm");
const registerForm = document.querySelector("#registerForm");
const forgotPasswordForm = document.querySelector("#forgotPasswordForm");
const resetPasswordForm = document.querySelector("#resetPasswordForm");
const pendingMessage = document.querySelector("#pendingMessage");
const resendVerificationButton = document.querySelector("#resendVerificationButton");
const emailVerificationMessage = document.querySelector("#emailVerificationMessage");
const confirmEmailBadge = document.querySelector("#confirmEmailBadge");
const confirmEmailTitle = document.querySelector("#confirmEmailTitle");
const confirmEmailMessage = document.querySelector("#confirmEmailMessage");
const confirmEmailLoginLink = document.querySelector("#confirmEmailLoginLink");
const adminSearchInput = document.querySelector("#adminSearchInput");
const adminStatusFilter = document.querySelector("#adminStatusFilter");
const adminRefreshButton = document.querySelector("#adminRefreshButton");
const adminUsersBody = document.querySelector("#adminUsersBody");
const adminUsersCount = document.querySelector("#adminUsersCount");
const adminMessage = document.querySelector("#adminMessage");
const teamForm = document.querySelector("#teamForm");
const teamNameInput = document.querySelector("#teamNameInput");
const teamMessage = document.querySelector("#teamMessage");
const teamsList = document.querySelector("#teamsList");
const adminTeamsCount = document.querySelector("#adminTeamsCount");
const dataUploadForm = document.querySelector("#dataUploadForm");
const dataUploadButton = document.querySelector("#dataUploadButton");
const dataUploadMessage = document.querySelector("#dataUploadMessage");
const dataUploadSummary = document.querySelector("#dataUploadSummary");
const sidebarToggleAuth = document.querySelector("#sidebarToggle");

function showAuthMessage(message, type = "error", target = authMessage) {
  if (!target) return;
  target.textContent = message;
  target.className = `auth-message ${type}`.trim();
  target.hidden = false;
}

function hideAuthMessage(target = authMessage) {
  if (!target) return;
  target.textContent = "";
  target.hidden = true;
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  return { response, data };
}

async function sessionIsActive() {
  try {
    const response = await fetch("/api/auth/me", { cache: "no-store" });
    return response.ok;
  } catch {
    return false;
  }
}

function setSubmitLoading(form, loading) {
  const button = form?.querySelector("button[type='submit']");
  if (!button) return;
  button.disabled = loading;
  button.classList.toggle("is-loading", loading);
}

function setDataUploadLoading(loading) {
  if (!dataUploadButton) return;
  dataUploadButton.disabled = loading;
  dataUploadButton.classList.toggle("is-loading", loading);
  dataUploadButton.setAttribute("aria-busy", loading ? "true" : "false");
}

function formatBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes)) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let amount = bytes;
  let unitIndex = 0;
  while (amount >= 1024 && unitIndex < units.length - 1) {
    amount /= 1024;
    unitIndex += 1;
  }
  return `${amount.toLocaleString("pt-BR", { maximumFractionDigits: unitIndex ? 1 : 0 })} ${units[unitIndex]}`;
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

function statusClass(status) {
  if (status === "ATIVO") return "success";
  if (status === "BLOQUEADO" || status === "CANCELADO") return "danger";
  return "neutral";
}

function statusLabel(status) {
  return {
    PENDENTE_APROVACAO: "Pendente",
    ATIVO: "Ativo",
    BLOQUEADO: "Bloqueado",
    CANCELADO: "Cancelado",
  }[status] || status || "-";
}

function profileLabel(profile) {
  return {
    ADMIN: "Administrador",
    GESTOR: "Gestor",
    SUPERVISOR: "Supervisor",
    USUARIO: "Usuário",
  }[profile] || profile || "-";
}

function userActions(user) {
  if (user.status === "PENDENTE_APROVACAO") {
    const actions = [["cancelar", "Cancelar"]];
    if (user.email_confirmado) actions.unshift(["aprovar", "Aprovar"]);
    return actions;
  }
  if (user.status === "ATIVO") {
    return [
      ["bloquear", "Bloquear"],
      ["cancelar", "Cancelar"],
    ];
  }
  if (user.status === "BLOQUEADO") {
    return [
      ["reativar", "Reativar"],
      ["cancelar", "Cancelar"],
    ];
  }
  return [];
}

function renderUsers(users) {
  if (!adminUsersBody) return;
  adminUsersBody.innerHTML = "";
  if (adminUsersCount) {
    adminUsersCount.textContent = `${users.length.toLocaleString("pt-BR")} usuário(s)`;
  }

  if (!users.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 8;
    cell.className = "admin-empty-cell";
    cell.textContent = "Nenhum usuário encontrado.";
    row.appendChild(cell);
    adminUsersBody.appendChild(row);
    return;
  }

  users.forEach((user) => {
    const row = document.createElement("tr");

    const userCell = document.createElement("td");
    const nameEl = document.createElement("strong");
    nameEl.textContent = user.nome_completo;
    const emailEl = document.createElement("span");
    emailEl.textContent = user.email;
    const emailStatusEl = document.createElement("span");
    emailStatusEl.className = user.email_confirmado ? "email-verified" : "email-pending";
    emailStatusEl.textContent = user.email_confirmado ? "E-mail confirmado" : "E-mail não confirmado";
    userCell.append(nameEl, emailEl, emailStatusEl);

    const profileCell = document.createElement("td");
    const profileSelect = document.createElement("select");
    profileSelect.className = "team-select";
    profileSelect.setAttribute("aria-label", `Perfil de ${user.nome_completo}`);
    ["ADMIN", "GESTOR", "SUPERVISOR", "USUARIO"].forEach((profile) => {
      profileSelect.add(new Option(profileLabel(profile), profile));
    });
    profileSelect.value = user.perfil;
    profileSelect.addEventListener("change", () => assignProfile(user.id, profileSelect.value, profileSelect));
    profileCell.appendChild(profileSelect);
    const teamCell = document.createElement("td");
    const teamSelect = document.createElement("select");
    teamSelect.className = "team-select";
    teamSelect.setAttribute("aria-label", `Equipe de ${user.nome_completo}`);
    teamSelect.add(new Option("Sem equipe", ""));
    adminTeams.forEach((team) => teamSelect.add(new Option(team.nome, String(team.id))));
    teamSelect.value = user.equipe_id == null ? "" : String(user.equipe_id);
    teamSelect.addEventListener("change", () => assignTeam(user.id, teamSelect.value, teamSelect));
    teamCell.appendChild(teamSelect);

    const managerCell = document.createElement("td");
    const managerSelect = document.createElement("select");
    managerSelect.className = "team-select";
    managerSelect.setAttribute("aria-label", `Gestor de ${user.nome_completo}`);
    if (user.perfil === "SUPERVISOR") {
      managerSelect.add(new Option("Sem gestor", ""));
      adminManagers.forEach((manager) => {
        managerSelect.add(new Option(manager.nome_completo, String(manager.id)));
      });
      managerSelect.value = user.gestor_id == null ? "" : String(user.gestor_id);
      managerSelect.addEventListener("change", () => {
        assignManager(user.id, managerSelect.value, managerSelect);
      });
    } else {
      managerSelect.add(new Option("Não se aplica", ""));
      managerSelect.disabled = true;
    }
    managerCell.appendChild(managerSelect);

    const statusCell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = `badge ${statusClass(user.status)}`;
    badge.textContent = statusLabel(user.status);
    statusCell.appendChild(badge);

    const createdCell = document.createElement("td");
    createdCell.textContent = formatDate(user.data_criacao);

    const loginCell = document.createElement("td");
    loginCell.textContent = formatDate(user.ultimo_login);

    const actionCell = document.createElement("td");
    actionCell.className = "admin-actions";
    userActions(user).forEach(([action, label]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `admin-action-button ${action}`;
      button.textContent = label;
      button.addEventListener("click", () => runUserAction(user.id, action));
      actionCell.appendChild(button);
    });
    if (!actionCell.children.length) {
      actionCell.textContent = "-";
    }

    row.append(userCell, profileCell, teamCell, managerCell, statusCell, createdCell, loginCell, actionCell);
    adminUsersBody.appendChild(row);
  });
}

let adminTeams = [];
let adminManagers = [];

function renderTeams() {
  if (adminTeamsCount) adminTeamsCount.textContent = `${adminTeams.length} equipe(s)`;
  if (!teamsList) return;
  teamsList.innerHTML = "";
  adminTeams.forEach((team) => {
    const item = document.createElement("span");
    item.className = "team-chip";
    item.textContent = `${team.nome} · ${team.total_membros} membro(s)`;
    teamsList.appendChild(item);
  });
}

async function loadTeams() {
  const response = await fetch("/api/admin/teams", { cache: "no-store" });
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || "Não foi possível carregar as equipes.");
  adminTeams = data.teams || [];
  renderTeams();
}

async function assignTeam(userId, teamId, select) {
  select.disabled = true;
  const { response, data } = await postJson("/api/admin/users/team", { user_id: userId, equipe_id: teamId });
  showAuthMessage(data.message, response.ok ? "success" : "error", adminMessage);
  select.disabled = false;
  if (response.ok) await refreshAdminManagement();
  else await loadAdminUsers();
}

async function assignProfile(userId, profile, select) {
  select.disabled = true;
  const { response, data } = await postJson("/api/admin/users/profile", {
    user_id: userId,
    perfil: profile,
  });
  showAuthMessage(data.message, response.ok ? "success" : "error", adminMessage);
  select.disabled = false;
  await loadAdminUsers();
}

async function assignManager(userId, managerId, select) {
  select.disabled = true;
  const { response, data } = await postJson("/api/admin/users/manager", {
    user_id: userId,
    gestor_id: managerId,
  });
  showAuthMessage(data.message, response.ok ? "success" : "error", adminMessage);
  select.disabled = false;
  await loadAdminUsers();
}

async function refreshAdminManagement() {
  await loadTeams();
  await loadAdminUsers();
}

function renderDataUploadSummary(data) {
  if (!dataUploadSummary) return;
  dataUploadSummary.innerHTML = "";

  const uploaded = data.uploaded || [];
  const sources = data.sources || [];
  if (!uploaded.length && !sources.length) {
    dataUploadSummary.hidden = true;
    return;
  }

  if (uploaded.length) {
    const title = document.createElement("strong");
    title.textContent = "Arquivos recebidos";
    const list = document.createElement("ul");
    uploaded.forEach((item) => {
      const row = document.createElement("li");
      row.textContent = `${item.label}: ${formatBytes(item.size)}`;
      list.appendChild(row);
    });
    dataUploadSummary.append(title, list);
  }

  if (sources.length) {
    const title = document.createElement("strong");
    title.textContent = "Base carregada";
    const list = document.createElement("ul");
    sources.forEach((source) => {
      const row = document.createElement("li");
      const rows = Number(source.indexed_count || 0).toLocaleString("pt-BR");
      row.textContent = `${source.label}: ${rows} linhas indexadas`;
      list.appendChild(row);
    });
    dataUploadSummary.append(title, list);
  }

  dataUploadSummary.hidden = false;
}

function uploadErrorMessage(status, fallback = "") {
  if (status === 413) {
    return "O proxy recusou o arquivo por tamanho (HTTP 413). Configure client_max_body_size para pelo menos 100m.";
  }
  if (status === 502) {
    return "O proxy perdeu a conexão com a aplicação durante o upload (HTTP 502). Verifique os logs e a memória do contêiner.";
  }
  if (status === 504) {
    return "O processamento excedeu o tempo do proxy (HTTP 504). Aumente proxy_read_timeout e verifique os logs.";
  }
  return fallback || `O servidor recusou a operação (HTTP ${status}).`;
}

async function readUploadResponse(response) {
  const text = await response.text();
  if (text) {
    try {
      return JSON.parse(text);
    } catch (error) {
      // Respostas HTML do proxy são convertidas em uma mensagem útil abaixo.
    }
  }
  return { ok: false, message: uploadErrorMessage(response.status) };
}

async function loadAdminUsers() {
  if (!adminUsersBody) return;
  hideAuthMessage(adminMessage);
  const params = new URLSearchParams();
  if (adminSearchInput?.value) params.set("search", adminSearchInput.value);
  if (adminStatusFilter?.value) params.set("status", adminStatusFilter.value);

  const response = await fetch(`/api/admin/users?${params.toString()}`, { cache: "no-store" });
  const data = await response.json();
  if (!response.ok) {
    showAuthMessage(data.message || "Não foi possível carregar usuários.", "error", adminMessage);
    return;
  }
  adminManagers = data.managers || [];
  renderUsers(data.users || []);
}

async function runUserAction(userId, action) {
  hideAuthMessage(adminMessage);
  const { response, data } = await postJson("/api/admin/users/action", {
    user_id: userId,
    action,
  });
  showAuthMessage(data.message || "Ação concluída.", response.ok ? "success" : "error", adminMessage);
  if (response.ok) {
    await loadAdminUsers();
  }
}

dataUploadForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideAuthMessage(dataUploadMessage);
  if (dataUploadSummary) dataUploadSummary.hidden = true;

  const selectedInputs = [...dataUploadForm.querySelectorAll("input[type='file']")]
    .filter((input) => input.files.length > 0);
  if (!selectedInputs.length) {
    showAuthMessage("Selecione ao menos um arquivo CSV para atualizar.", "error", dataUploadMessage);
    return;
  }

  setDataUploadLoading(true);
  const uploaded = [];
  try {
    for (let index = 0; index < selectedInputs.length; index += 1) {
      const input = selectedInputs[index];
      const file = input.files[0];
      showAuthMessage(
        `Enviando ${index + 1} de ${selectedInputs.length}: ${file.name} (${formatBytes(file.size)})...`,
        "success",
        dataUploadMessage,
      );

      const formData = new FormData();
      formData.append(input.name, file, file.name);
      const response = await fetch("/api/admin/data/upload?refresh=0", {
        method: "POST",
        body: formData,
      });
      if (response.status === 401) {
        window.location.href = "/login";
        return;
      }
      const data = await readUploadResponse(response);
      if (!response.ok || !data.ok) {
        throw new Error(data.message || uploadErrorMessage(response.status));
      }
      uploaded.push(...(data.uploaded || []));
    }

    showAuthMessage("Arquivos recebidos. Reconstruindo a base...", "success", dataUploadMessage);
    const refreshResponse = await fetch("/api/data/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ force: true }),
    });
    if (refreshResponse.status === 401) {
      window.location.href = "/login";
      return;
    }
    const data = await readUploadResponse(refreshResponse);
    if (!refreshResponse.ok && refreshResponse.status !== 503) {
      throw new Error(data.message || uploadErrorMessage(refreshResponse.status));
    }

    const ready = refreshResponse.ok && data.ok;
    showAuthMessage(
      ready
        ? (data.message || "Base atualizada com sucesso.")
        : `Arquivos salvos. ${data.message || "Ainda faltam bases obrigatórias."}`,
      ready ? "success" : "warning",
      dataUploadMessage,
    );
    dataUploadForm.reset();
    renderDataUploadSummary({ ...data, uploaded });
  } catch (error) {
    const savedMessage = uploaded.length
      ? `${uploaded.length} arquivo(s) já foram salvos. `
      : "";
    showAuthMessage(
      `${savedMessage}${error.message || "Não foi possível enviar os arquivos."}`,
      "error",
      dataUploadMessage,
    );
  } finally {
    setDataUploadLoading(false);
  }
});

loginForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideAuthMessage();
  if (resendVerificationButton) resendVerificationButton.hidden = true;
  setSubmitLoading(loginForm, true);
  const { response, data } = await postJson("/api/auth/login", {
    email: document.querySelector("#loginEmail").value,
    senha: document.querySelector("#loginPassword").value,
  });
  setSubmitLoading(loginForm, false);
  if (!response.ok) {
    showAuthMessage(data.message || "E-mail ou senha inválidos.");
    if (data.code === "EMAIL_NAO_CONFIRMADO" && resendVerificationButton) {
      sessionStorage.setItem("verificationEmail", document.querySelector("#loginEmail").value);
      resendVerificationButton.hidden = false;
    }
    return;
  }
  if (!(await sessionIsActive())) {
    showAuthMessage(
      "Login validado, mas a sessao nao foi mantida. Verifique o acesso HTTPS ou a configuracao SESSION_COOKIE_SECURE."
    );
    return;
  }
  window.location.href = data.redirect || "/app";
});

registerForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideAuthMessage();
  setSubmitLoading(registerForm, true);
  const { response, data } = await postJson("/api/auth/register", {
    nome_completo: document.querySelector("#registerName").value,
    email: document.querySelector("#registerEmail").value,
    senha: document.querySelector("#registerPassword").value,
    senha_confirmacao: document.querySelector("#registerPasswordConfirm").value,
  });
  setSubmitLoading(registerForm, false);
  if (!response.ok) {
    showAuthMessage(data.message || "Não foi possível criar a conta.");
    return;
  }
  sessionStorage.setItem("pendingMessage", data.message);
  sessionStorage.setItem("verificationEmail", document.querySelector("#registerEmail").value);
  window.location.href = "/verifique-email";
});

resendVerificationButton?.addEventListener("click", async () => {
  const email = sessionStorage.getItem("verificationEmail")
    || document.querySelector("#loginEmail")?.value
    || "";
  const target = emailVerificationMessage || authMessage;
  if (!email) {
    showAuthMessage("Informe o e-mail usado no cadastro.", "error", target);
    return;
  }
  resendVerificationButton.disabled = true;
  const { data } = await postJson("/api/auth/email/resend", { email });
  resendVerificationButton.disabled = false;
  showAuthMessage(data.message, "success", target);
});

async function validateEmailLink() {
  if (!confirmEmailMessage) return;
  const params = new URLSearchParams(window.location.search);
  const { response, data } = await postJson("/api/auth/email/confirm", {
    token: params.get("token") || "",
  });
  confirmEmailMessage.textContent = data.message || "Não foi possível validar o e-mail.";
  if (response.ok && data.ok) {
    confirmEmailBadge.textContent = "E-MAIL CONFIRMADO";
    confirmEmailBadge.className = "badge success";
    confirmEmailTitle.textContent = "E-mail confirmado";
    sessionStorage.removeItem("verificationEmail");
  } else {
    confirmEmailBadge.textContent = "LINK INVÁLIDO";
    confirmEmailBadge.className = "badge danger";
    confirmEmailTitle.textContent = "Não foi possível confirmar";
  }
  confirmEmailLoginLink.hidden = false;
}

forgotPasswordForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideAuthMessage();
  setSubmitLoading(forgotPasswordForm, true);
  const { data } = await postJson("/api/auth/password/forgot", {
    email: document.querySelector("#forgotEmail").value,
  });
  setSubmitLoading(forgotPasswordForm, false);
  showAuthMessage(data.message, "success");
});

resetPasswordForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideAuthMessage();
  setSubmitLoading(resetPasswordForm, true);
  const params = new URLSearchParams(window.location.search);
  const { response, data } = await postJson("/api/auth/password/reset", {
    token: params.get("token") || "",
    senha: document.querySelector("#resetPassword").value,
    senha_confirmacao: document.querySelector("#resetPasswordConfirm").value,
  });
  setSubmitLoading(resetPasswordForm, false);
  showAuthMessage(data.message || "Não foi possível redefinir a senha.", response.ok ? "success" : "error");
  if (response.ok) {
    resetPasswordForm.reset();
  }
});

if (pendingMessage) {
  const storedMessage = sessionStorage.getItem("pendingMessage");
  if (storedMessage) {
    pendingMessage.textContent = storedMessage;
    sessionStorage.removeItem("pendingMessage");
  }
}

let adminSearchTimer = 0;
adminSearchInput?.addEventListener("input", () => {
  window.clearTimeout(adminSearchTimer);
  adminSearchTimer = window.setTimeout(loadAdminUsers, 250);
});
adminStatusFilter?.addEventListener("change", loadAdminUsers);
adminRefreshButton?.addEventListener("click", loadAdminUsers);

teamForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideAuthMessage(teamMessage);
  setSubmitLoading(teamForm, true);
  const { response, data } = await postJson("/api/admin/teams", { nome: teamNameInput.value });
  setSubmitLoading(teamForm, false);
  showAuthMessage(data.message, response.ok ? "success" : "error", teamMessage);
  if (response.ok) {
    teamForm.reset();
    await refreshAdminManagement();
  }
});

sidebarToggleAuth?.addEventListener("click", () => {
  document.body.classList.toggle("sidebar-open");
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    document.body.classList.remove("sidebar-open");
  }
});

if (adminUsersBody) {
  refreshAdminManagement().catch((error) => showAuthMessage(error.message, "error", adminMessage));
}

validateEmailLink();
