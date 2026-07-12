const reportsRefreshButton = document.querySelector("#reportsRefreshButton");
const reportsMessage = document.querySelector("#reportsMessage");
const reportsBody = document.querySelector("#reportsBody");
const reportsGeneratedAt = document.querySelector("#reportsGeneratedAt");
const reportsScopeText = document.querySelector("#reportsScopeText");
const dailyQueriesValue = document.querySelector("#dailyQueriesValue");
const monthlyQueriesValue = document.querySelector("#monthlyQueriesValue");
const uniqueClientsValue = document.querySelector("#uniqueClientsValue");
const adoptionValue = document.querySelector("#adoptionValue");
const dailyTrendChart = document.querySelector("#dailyTrendChart");
const hourlyUsageChart = document.querySelector("#hourlyUsageChart");
const teamsRanking = document.querySelector("#teamsRanking");
const topClients = document.querySelector("#topClients");
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
  cell.colSpan = 10;
  cell.className = "admin-empty-cell";
  cell.textContent = "Nenhum usuário encontrado.";
  row.appendChild(cell);
  reportsBody.appendChild(row);
}

function renderBars(target, items, valueKey, labelFormatter) {
  target.innerHTML = "";
  const max = Math.max(1, ...items.map((item) => Number(item[valueKey] || 0)));
  items.forEach((item) => {
    const column = document.createElement("div");
    column.className = "bar-column";
    column.title = `${labelFormatter(item)}: ${formatNumber(item[valueKey])} consulta(s)`;
    const value = document.createElement("strong");
    value.textContent = formatNumber(item[valueKey]);
    const bar = document.createElement("span");
    bar.className = "bar-fill";
    bar.style.height = `${Math.max(3, Number(item[valueKey] || 0) * 100 / max)}%`;
    const label = document.createElement("small");
    label.textContent = labelFormatter(item);
    column.append(value, bar, label);
    target.appendChild(column);
  });
}

function renderList(target, items, config) {
  target.innerHTML = "";
  if (!items.length) {
    target.textContent = "Ainda não há dados para exibir.";
    target.classList.add("report-list-empty");
    return;
  }
  target.classList.remove("report-list-empty");
  items.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "report-list-row";
    const position = document.createElement("span");
    position.className = "list-position";
    position.textContent = index + 1;
    const content = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = config.title(item);
    const detail = document.createElement("small");
    detail.textContent = config.detail(item);
    content.append(title, detail);
    const value = document.createElement("b");
    value.textContent = config.value(item);
    row.append(position, content, value);
    target.appendChild(row);
  });
}

function renderReport(data) {
  const summary = data.summary || {};
  const scope = data.scope || {};
  dailyQueriesValue.textContent = formatNumber(summary.consultas_diarias);
  monthlyQueriesValue.textContent = formatNumber(summary.consultas_mensais);
  uniqueClientsValue.textContent = formatNumber(summary.clientes_unicos_mes);
  adoptionValue.textContent = `${Number(summary.adocao_mensal || 0).toLocaleString("pt-BR")}%`;
  reportsGeneratedAt.textContent = `Atualizado em ${formatDate(data.generated_at)}`;
  if (reportsScopeText) {
    reportsScopeText.textContent = scope.type === "team"
      ? `Visão exclusiva da equipe ${scope.team_name || "vinculada ao seu perfil"}.`
      : "Visão consolidada de todos os usuários e equipes.";
  }

  renderBars(dailyTrendChart, data.daily_trend || [], "consultas", (item) => {
    const [, month, day] = item.data.split("-");
    return `${day}/${month}`;
  });
  renderBars(hourlyUsageChart, (data.hourly_usage || []).filter((item) => item.hora >= 7 && item.hora <= 20), "consultas", (item) => `${String(item.hora).padStart(2, "0")}h`);
  renderList(teamsRanking, data.teams || [], {
    title: (item) => item.equipe,
    detail: (item) => `${item.usuarios_ativos_mes} de ${item.usuarios} usuário(s) ativos no mês`,
    value: (item) => `${formatNumber(item.consultas_mes)} consultas`,
  });
  renderList(topClients, data.top_clients || [], {
    title: (item) => item.cliente,
    detail: (item) => `${item.cnpj} · ${item.usuarios} usuário(s)`,
    value: (item) => `${formatNumber(item.consultas)} consultas`,
  });

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
      createTextCell(item.equipe_nome || "Sem equipe"),
      createTextCell(formatNumber(item.consultas_diarias), "report-number-cell"),
      createTextCell(formatNumber(item.consultas_mensais), "report-number-cell"),
      createTextCell(formatNumber(item.clientes_unicos_mes), "report-number-cell"),
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
