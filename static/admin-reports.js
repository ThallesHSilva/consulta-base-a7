const reportsRefreshButton = document.querySelector("#reportsRefreshButton");
const reportsMessage = document.querySelector("#reportsMessage");
const reportsBody = document.querySelector("#reportsBody");
const reportsGeneratedAt = document.querySelector("#reportsGeneratedAt");
const dailyQueriesValue = document.querySelector("#dailyQueriesValue");
const monthlyQueriesValue = document.querySelector("#monthlyQueriesValue");
const totalQueriesValue = document.querySelector("#totalQueriesValue");
const usersTrackedValue = document.querySelector("#usersTrackedValue");
const sidebarToggleReports = document.querySelector("#sidebarToggle");

function formatNumber(value) {
  const number = Number(value || 0);
  return number.toLocaleString("pt-BR");
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

function showReportsMessage(message, type = "error") {
  if (!reportsMessage) return;
  reportsMessage.textContent = message;
  reportsMessage.className = `auth-message ${type}`.trim();
  reportsMessage.hidden = false;
}

function hideReportsMessage() {
  if (!reportsMessage) return;
  reportsMessage.textContent = "";
  reportsMessage.hidden = true;
}

function setReportsLoading(loading) {
  if (!reportsRefreshButton) return;
  reportsRefreshButton.disabled = loading;
  reportsRefreshButton.setAttribute("aria-busy", loading ? "true" : "false");
}

function createTextCell(text, className = "") {
  const cell = document.createElement("td");
  cell.textContent = text || "-";
  if (className) cell.className = className;
  return cell;
}

function renderEmptyReports() {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = 8;
  cell.className = "admin-empty-cell";
  cell.textContent = "Nenhum usuário encontrado.";
  row.appendChild(cell);
  reportsBody.appendChild(row);
}

function renderReport(data) {
  const summary = data.summary || {};
  dailyQueriesValue.textContent = formatNumber(summary.consultas_diarias);
  monthlyQueriesValue.textContent = formatNumber(summary.consultas_mensais);
  totalQueriesValue.textContent = formatNumber(summary.consultas_totais);
  usersTrackedValue.textContent = formatNumber(summary.usuarios);
  reportsGeneratedAt.textContent = `Atualizado em ${formatDate(data.generated_at)}`;

  const items = data.items || [];
  reportsBody.innerHTML = "";
  if (!items.length) {
    renderEmptyReports();
    return;
  }

  items.forEach((item) => {
    const row = document.createElement("tr");
    row.appendChild(createTextCell(String(item.posicao || "-"), "ranking-position"));

    const userCell = document.createElement("td");
    const nameEl = document.createElement("strong");
    nameEl.textContent = item.nome_completo || "-";
    const emailEl = document.createElement("span");
    emailEl.textContent = item.email || "-";
    userCell.append(nameEl, emailEl);

    row.append(
      userCell,
      createTextCell(formatNumber(item.consultas_diarias), "report-number-cell"),
      createTextCell(formatNumber(item.consultas_mensais), "report-number-cell"),
      createTextCell(formatNumber(item.consultas_totais), "report-number-cell"),
      createTextCell(item.tempo_desde_ultima_consulta || "Nunca"),
      createTextCell(item.tempo_desde_ultimo_login || "Nunca"),
    );

    const statusCell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = `badge ${statusClass(item.status)}`;
    badge.textContent = statusLabel(item.status);
    statusCell.appendChild(badge);
    row.appendChild(statusCell);

    reportsBody.appendChild(row);
  });
}

async function loadReports() {
  hideReportsMessage();
  setReportsLoading(true);
  try {
    const response = await fetch("/api/admin/reports/usage", { cache: "no-store" });
    if (response.status === 401) {
      window.location.href = "/login";
      return;
    }
    const data = await response.json();
    if (!response.ok || !data.ok) {
      showReportsMessage(data.message || "Não foi possível carregar o relatório.");
      return;
    }
    renderReport(data);
  } catch (error) {
    showReportsMessage("Não foi possível carregar o relatório. Tente novamente.");
  } finally {
    setReportsLoading(false);
  }
}

reportsRefreshButton?.addEventListener("click", loadReports);

sidebarToggleReports?.addEventListener("click", () => {
  document.body.classList.toggle("sidebar-open");
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    document.body.classList.remove("sidebar-open");
  }
});

loadReports();
