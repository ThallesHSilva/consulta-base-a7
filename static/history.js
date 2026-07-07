const historyBody = document.querySelector("#historyBody");
const historyCount = document.querySelector("#historyCount");
const historyMessage = document.querySelector("#historyMessage");
const historyRefreshButton = document.querySelector("#historyRefreshButton");
const sidebarToggleHistory = document.querySelector("#sidebarToggle");

function onlyDigits(value) {
  return String(value || "").replace(/\D/g, "");
}

function formatCnpj(value) {
  const raw = String(value || "").trim();
  const digits = onlyDigits(raw);
  if (digits.length !== 14) return raw || "-";
  return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8, 12)}-${digits.slice(12)}`;
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

function showHistoryMessage(message, type = "error") {
  if (!historyMessage) return;
  historyMessage.textContent = message;
  historyMessage.className = `auth-message ${type}`.trim();
  historyMessage.hidden = false;
}

function hideHistoryMessage() {
  if (!historyMessage) return;
  historyMessage.textContent = "";
  historyMessage.hidden = true;
}

function setHistoryLoading(loading) {
  if (!historyRefreshButton) return;
  historyRefreshButton.disabled = loading;
  historyRefreshButton.setAttribute("aria-busy", loading ? "true" : "false");
}

function createTextCell(text) {
  const cell = document.createElement("td");
  cell.textContent = text || "-";
  return cell;
}

function renderEmptyHistory() {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = 5;
  cell.className = "admin-empty-cell";
  cell.textContent = "Nenhuma consulta registrada ainda.";
  row.appendChild(cell);
  historyBody.appendChild(row);
}

function renderHistory(items) {
  if (!historyBody) return;
  historyBody.innerHTML = "";

  if (historyCount) {
    historyCount.textContent = `${items.length.toLocaleString("pt-BR")} consulta(s)`;
  }

  if (!items.length) {
    renderEmptyHistory();
    return;
  }

  items.forEach((item) => {
    const row = document.createElement("tr");
    row.append(
      createTextCell(formatCnpj(item.cnpj)),
      createTextCell(item.company_name || "CNPJ não localizado"),
      createTextCell(formatDate(item.data_consulta)),
    );

    const statusCell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = `badge ${item.found ? "success" : "neutral"}`;
    badge.textContent = item.found ? "Localizado" : "Não localizado";
    statusCell.appendChild(badge);

    const actionCell = document.createElement("td");
    actionCell.className = "history-actions";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "admin-action-button reativar";
    button.textContent = "Consultar novamente";
    button.addEventListener("click", () => {
      window.location.href = `/app?cnpj=${encodeURIComponent(item.cnpj || item.cnpj_key || "")}`;
    });
    actionCell.appendChild(button);

    row.append(statusCell, actionCell);
    historyBody.appendChild(row);
  });
}

async function loadHistory() {
  hideHistoryMessage();
  setHistoryLoading(true);
  try {
    const response = await fetch("/api/history", { cache: "no-store" });
    if (response.status === 401) {
      window.location.href = "/login";
      return;
    }
    const data = await response.json();
    if (!response.ok || !data.ok) {
      showHistoryMessage(data.message || "Não foi possível carregar o histórico.");
      return;
    }
    renderHistory(data.items || []);
  } catch (error) {
    showHistoryMessage("Não foi possível carregar o histórico. Tente novamente.");
  } finally {
    setHistoryLoading(false);
  }
}

historyRefreshButton?.addEventListener("click", loadHistory);

sidebarToggleHistory?.addEventListener("click", () => {
  document.body.classList.toggle("sidebar-open");
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    document.body.classList.remove("sidebar-open");
  }
});

loadHistory();
