const authMessage = document.querySelector("#authMessage");
const loginForm = document.querySelector("#loginForm");
const registerForm = document.querySelector("#registerForm");
const forgotPasswordForm = document.querySelector("#forgotPasswordForm");
const resetPasswordForm = document.querySelector("#resetPasswordForm");
const pendingMessage = document.querySelector("#pendingMessage");
const adminSearchInput = document.querySelector("#adminSearchInput");
const adminStatusFilter = document.querySelector("#adminStatusFilter");
const adminRefreshButton = document.querySelector("#adminRefreshButton");
const adminUsersBody = document.querySelector("#adminUsersBody");
const adminUsersCount = document.querySelector("#adminUsersCount");
const adminMessage = document.querySelector("#adminMessage");
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

function userActions(user) {
  if (user.status === "PENDENTE_APROVACAO") {
    return [
      ["aprovar", "Aprovar"],
      ["cancelar", "Cancelar"],
    ];
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
    cell.colSpan = 6;
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
    userCell.append(nameEl, emailEl);

    const profileCell = document.createElement("td");
    profileCell.textContent = user.perfil === "ADMIN" ? "Administrador" : "Usuário";

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

    row.append(userCell, profileCell, statusCell, createdCell, loginCell, actionCell);
    adminUsersBody.appendChild(row);
  });
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

  const hasFile = [...dataUploadForm.querySelectorAll("input[type='file']")].some(
    (input) => input.files.length > 0,
  );
  if (!hasFile) {
    showAuthMessage("Selecione ao menos um arquivo CSV para atualizar.", "error", dataUploadMessage);
    return;
  }

  setDataUploadLoading(true);
  showAuthMessage("Enviando arquivos e reconstruindo a base...", "success", dataUploadMessage);
  try {
    const response = await fetch("/api/admin/data/upload", {
      method: "POST",
      body: new FormData(dataUploadForm),
    });
    if (response.status === 401) {
      window.location.href = "/login";
      return;
    }
    const data = await response.json();
    const ok = response.ok && data.ok;
    showAuthMessage(
      data.message || (ok ? "Base atualizada com sucesso." : "Não foi possível atualizar a base."),
      ok ? "success" : "error",
      dataUploadMessage,
    );
    if (ok) {
      dataUploadForm.reset();
      renderDataUploadSummary(data);
    }
  } catch (error) {
    showAuthMessage("Não foi possível enviar os arquivos. Tente novamente.", "error", dataUploadMessage);
  } finally {
    setDataUploadLoading(false);
  }
});

loginForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideAuthMessage();
  setSubmitLoading(loginForm, true);
  const { response, data } = await postJson("/api/auth/login", {
    email: document.querySelector("#loginEmail").value,
    senha: document.querySelector("#loginPassword").value,
  });
  setSubmitLoading(loginForm, false);
  if (!response.ok) {
    showAuthMessage(data.message || "E-mail ou senha inválidos.");
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
  window.location.href = "/aguardando-aprovacao";
});

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

sidebarToggleAuth?.addEventListener("click", () => {
  document.body.classList.toggle("sidebar-open");
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    document.body.classList.remove("sidebar-open");
  }
});

loadAdminUsers();
