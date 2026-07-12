const statusBadge = document.querySelector("#statusBadge");
const statusPanel = document.querySelector("#statusPanel");
const searchForm = document.querySelector("#searchForm");
const cnpjInput = document.querySelector("#cnpjInput");
const searchButton = document.querySelector("#searchButton");
const exportPdfButton = document.querySelector("#exportPdfButton");
const refreshDataButton = document.querySelector("#refreshDataButton");
const searchMessage = document.querySelector("#searchMessage");
const companyPanel = document.querySelector("#companyPanel");
const offersPanel = document.querySelector("#offersPanel");
const offersToggle = document.querySelector("#offersToggle");
const offersToggleLabel = document.querySelector("#offersToggleLabel");
const offersContent = document.querySelector("#offersContent");
const offerPosseValue = document.querySelector("#offerPosseValue");
const offerFirstValue = document.querySelector("#offerFirstValue");
const offerDigitalValue = document.querySelector("#offerDigitalValue");
const contactsPanel = document.querySelector("#contactsPanel");
const contactManagerValue = document.querySelector("#contactManagerValue");
const contactEmailValue = document.querySelector("#contactEmailValue");
const contactMobileValue = document.querySelector("#contactMobileValue");
const metricsPanel = document.querySelector("#metricsPanel");
const mobilePanel = document.querySelector("#mobilePanel");
const companyNameValue = document.querySelector("#companyNameValue");
const clientCnpjValue = document.querySelector("#clientCnpjValue");
const clientStatusValue = document.querySelector("#clientStatusValue");
const clientSegmentValue = document.querySelector("#clientSegmentValue");
const deviceCreditValue = document.querySelector("#deviceCreditValue");
const creditProgress = document.querySelector("#creditProgress");
const creditSummaryValue = document.querySelector("#creditSummaryValue");
const broadbandAvailability = document.querySelector("#broadbandAvailability");
const broadbandAvailabilityValue = document.querySelector("#broadbandAvailabilityValue");
const broadbandAvailabilityBadge = document.querySelector("#broadbandAvailabilityBadge");
const broadbandCoverageValue = document.querySelector("#broadbandCoverageValue");
const mobileLinesMetric = document.querySelector("#mobileLinesMetric");
const broadbandLinesMetric = document.querySelector("#broadbandLinesMetric");
const monthlyValueMetric = document.querySelector("#monthlyValueMetric");
const internetTotalMetric = document.querySelector("#internetTotalMetric");
const mobileDetailLink = document.querySelector("#mobileDetailLink");
const broadbandDetailLink = document.querySelector("#broadbandDetailLink");
const invoiceDueValue = document.querySelector("#invoiceDueValue");
const invoiceAmountValue = document.querySelector("#invoiceAmountValue");
const contractedInternetValue = document.querySelector("#contractedInternetValue");
const m0M16Value = document.querySelector("#m0M16Value");
const m17Value = document.querySelector("#m17Value");
const aboveM17Value = document.querySelector("#aboveM17Value");
const m0M16Percent = document.querySelector("#m0M16Percent");
const m17Percent = document.querySelector("#m17Percent");
const aboveM17Percent = document.querySelector("#aboveM17Percent");
const m0M16Bar = document.querySelector("#m0M16Bar");
const m17Bar = document.querySelector("#m17Bar");
const aboveM17Bar = document.querySelector("#aboveM17Bar");
const printReportHeader = document.querySelector("#printReportHeader");
const printReportCnpj = document.querySelector("#printReportCnpj");
const printReportDate = document.querySelector("#printReportDate");
const sidebarToggle = document.querySelector("#sidebarToggle");

let baseReady = false;
let searchLoading = false;
let lastSuccessfulCnpj = "";
let titleBeforePrintExport = "";
const initialParams = new URLSearchParams(window.location.search);
const initialCnpj = initialParams.get("cnpj") || "";

function onlyDigits(value) {
  return value.replace(/\D/g, "");
}

function formatCnpj(value) {
  const digits = onlyDigits(value).slice(0, 14);
  if (digits.length <= 2) return digits;
  if (digits.length <= 5) return `${digits.slice(0, 2)}.${digits.slice(2)}`;
  if (digits.length <= 8) {
    return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5)}`;
  }
  if (digits.length <= 12) {
    return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8)}`;
  }
  return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8, 12)}-${digits.slice(12)}`;
}

function numberOrZero(value) {
  return Number.isFinite(value) ? value : 0;
}

function setBadge(text, type) {
  statusBadge.textContent = text;
  statusBadge.className = `status-badge ${type || ""}`.trim();
}

function setSearchLoading(loading) {
  searchLoading = loading;
  searchButton.disabled = loading || !baseReady;
  searchButton.classList.toggle("is-loading", loading);
  searchButton.setAttribute("aria-busy", loading ? "true" : "false");
}

function setActionLoading(button, loading) {
  if (!button) return;
  button.disabled = loading;
  button.setAttribute("aria-busy", loading ? "true" : "false");
}

function redirectIfUnauthorized(response) {
  if (response.status === 401) {
    window.location.href = "/login";
    return true;
  }
  return false;
}

function renderStatus(status) {
  baseReady = Boolean(status.ready);
  setSearchLoading(false);

  if (!baseReady) {
    statusBadge.hidden = false;
    setBadge("Arquivos ausentes", "error");
    statusPanel.className = "status-panel error";
    statusPanel.innerHTML = "";

    const strong = document.createElement("strong");
    strong.textContent = "Arquivo ausente";
    statusPanel.append(strong, document.createTextNode(":"));

    const list = document.createElement("ul");
    list.className = "missing-list";
    status.missing_files.forEach((file) => {
      const item = document.createElement("li");
      item.textContent = file;
      list.appendChild(item);
    });
    statusPanel.appendChild(list);
    return;
  }

  statusBadge.hidden = true;
  statusPanel.className = "status-panel";
  statusPanel.innerHTML = "";
}

function setMetricValue(element, value) {
  if (!element) return;
  if (Number.isFinite(value)) {
    element.textContent = value.toLocaleString("pt-BR");
    return;
  }
  element.textContent = "-";
}

function formatCurrency(value) {
  if (!Number.isFinite(value)) return "-";
  return value.toLocaleString("pt-BR", {
    currency: "BRL",
    style: "currency",
  });
}

function parseCurrencyText(value) {
  if (!value || /sem crédito/i.test(value)) return 0;
  const normalized = value
    .replace(/[^\d,.-]/g, "")
    .replace(/\./g, "")
    .replace(",", ".");
  const parsed = Number.parseFloat(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatGb(value) {
  if (!Number.isFinite(value)) return "-";
  return `${value.toLocaleString("pt-BR")} GB`;
}

function setPanelsVisible(visible) {
  companyPanel.hidden = !visible;
  offersPanel.hidden = !visible;
  contactsPanel.hidden = !visible;
  metricsPanel.hidden = !visible;
  mobilePanel.hidden = !visible;
  if (!visible) setOffersExpanded(false);
}

function showMessage(message, type = "") {
  searchMessage.textContent = message;
  searchMessage.className = `message-panel ${type}`.trim();
  searchMessage.hidden = false;
}

function hideMessage() {
  searchMessage.textContent = "";
  searchMessage.hidden = true;
}

function setDetailLink(link, type, cnpj) {
  if (!cnpj) {
    link.href = "#";
    link.classList.add("disabled");
    link.setAttribute("aria-disabled", "true");
    return;
  }

  link.href = `/detail.html?type=${encodeURIComponent(type)}&cnpj=${encodeURIComponent(cnpj)}`;
  link.classList.remove("disabled");
  link.setAttribute("aria-disabled", "false");
}

function renderDetailLinks(cnpj) {
  setDetailLink(mobileDetailLink, "mobile", cnpj);
  setDetailLink(broadbandDetailLink, "broadband", cnpj);
}

function renderCompanyName(companyName) {
  companyNameValue.textContent = companyName || "-";
}

function renderClientContext(data) {
  const cnpj = data?.query || data?.normalized || cnpjInput.value || "";
  clientCnpjValue.textContent = cnpj ? formatCnpj(cnpj) : "-";
  clientStatusValue.textContent = data?.client_status || "-";
  clientSegmentValue.textContent = data?.client_portfolio || "-";
}

function setOffersExpanded(expanded) {
  offersToggle.setAttribute("aria-expanded", expanded ? "true" : "false");
  offersContent.hidden = !expanded;
  offersPanel.classList.toggle("is-expanded", expanded);
  offersToggleLabel.textContent = expanded ? "Recolher" : "Expandir";
}

function renderOffers(offers) {
  offerPosseValue.textContent = offers?.posse || "-";
  offerFirstValue.textContent = offers?.primeira_oferta || "-";
  offerDigitalValue.textContent = offers?.digital || "-";
}

function renderContacts(contacts) {
  contactManagerValue.textContent = contacts?.manager || "-";
  contactEmailValue.textContent = contacts?.email || "-";
  contactMobileValue.textContent = contacts?.mobile || "-";
}

function renderDeviceCredit(deviceCredit) {
  const text = deviceCredit || "-";
  const creditValue = parseCurrencyText(text);
  const creditPercent = Math.min(100, Math.round((creditValue / 50000) * 100));

  deviceCreditValue.textContent = text;
  creditProgress.style.width = `${creditPercent}%`;
  creditSummaryValue.textContent = creditValue > 0 ? "Valor disponível para renovação" : "Sem crédito liberado";
}

function isUnavailableText(value) {
  return !value || /sem|não|nao|informação|informacao/i.test(value);
}

function renderBroadbandAvailability(metrics, availability) {
  if (!metrics) {
    broadbandAvailability.hidden = true;
    broadbandAvailabilityValue.textContent = "-";
    broadbandAvailabilityBadge.textContent = "Sem disponibilidade";
    broadbandAvailabilityBadge.className = "badge neutral";
    broadbandCoverageValue.textContent = "Disponibilidade consultada no Mapa Parque";
    return;
  }

  const broadbandLines = numberOrZero(metrics.broadband_lines);
  broadbandAvailability.hidden = false;

  if (broadbandLines > 0) {
    broadbandAvailabilityValue.textContent = "BL contratada";
    broadbandAvailabilityBadge.textContent = "Ativa";
    broadbandAvailabilityBadge.className = "badge info";
    broadbandCoverageValue.textContent = "Cliente possui banda larga na base";
    return;
  }

  const text = availability || "Sem disponibilidade";
  const unavailable = isUnavailableText(text);
  broadbandAvailabilityValue.textContent = unavailable ? "Sem disponibilidade" : text;
  broadbandAvailabilityBadge.textContent = unavailable ? "Sem disponibilidade" : "Disponível para abordagem";
  broadbandAvailabilityBadge.className = unavailable ? "badge neutral" : "badge success";
  broadbandCoverageValue.textContent = unavailable ? text : "Disponibilidade consultada no Mapa Parque";
}

function renderMetrics(metrics, mobileInfo) {
  setMetricValue(mobileLinesMetric, metrics?.mobile_lines);
  setMetricValue(broadbandLinesMetric, metrics?.broadband_lines);
  monthlyValueMetric.textContent = formatCurrency(mobileInfo?.invoice_amount);
  internetTotalMetric.textContent = formatGb(mobileInfo?.contracted_internet_gb);
}

function setRangeVisual(valueElement, percentElement, barElement, value, total) {
  const count = numberOrZero(value);
  const percent = total > 0 ? Math.round((count / total) * 100) : 0;
  setMetricValue(valueElement, count);
  percentElement.textContent = `${percent}%`;
  barElement.style.width = count > 0 ? `${Math.max(percent, 4)}%` : "0%";
}

function renderMobileInfo(info) {
  invoiceDueValue.textContent = info?.invoice_due || "-";
  invoiceAmountValue.textContent = formatCurrency(info?.invoice_amount);
  contractedInternetValue.textContent = formatGb(info?.contracted_internet_gb);

  const ranges = Object.fromEntries((info?.m_ranges || []).map((item) => [item.label, item.count]));
  const m0M16 = numberOrZero(ranges["M0 A M16"]);
  const m17 = numberOrZero(ranges.M17);
  const aboveM17 = numberOrZero(ranges["ACIMA DE M17"]);
  const total = m0M16 + m17 + aboveM17;

  setRangeVisual(m0M16Value, m0M16Percent, m0M16Bar, m0M16, total);
  setRangeVisual(m17Value, m17Percent, m17Bar, m17, total);
  setRangeVisual(aboveM17Value, aboveM17Percent, aboveM17Bar, aboveM17, total);
}

function resetPanelValues() {
  renderCompanyName();
  renderClientContext();
  renderOffers();
  renderContacts();
  renderDeviceCredit();
  renderBroadbandAvailability();
  renderMetrics();
  renderMobileInfo();
  renderDetailLinks();
}

function renderResults(data) {
  if (!data.total) {
    lastSuccessfulCnpj = "";
    setPanelsVisible(false);
    resetPanelValues();
    showMessage(data.message || "CNPJ não localizado.", "warning");
    return;
  }

  hideMessage();
  lastSuccessfulCnpj = data.query || data.normalized || cnpjInput.value;
  setPanelsVisible(true);
  renderCompanyName(data.company_name);
  renderClientContext(data);
  renderOffers(data.offers);
  renderContacts(data.contacts);
  renderDeviceCredit(data.device_credit);
  renderMetrics(data.metrics, data.mobile_info);
  renderBroadbandAvailability(data.metrics, data.broadband_availability);
  renderMobileInfo(data.mobile_info);
  renderDetailLinks(data.query || data.normalized);
}

async function loadStatus() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    const status = await response.json();
    renderStatus(status);
    if (baseReady && initialCnpj) {
      cnpjInput.value = formatCnpj(initialCnpj);
      await search(initialCnpj);
    }
  } catch (error) {
    baseReady = false;
    setSearchLoading(false);
    statusBadge.hidden = false;
    setBadge("Erro", "error");
    statusPanel.className = "status-panel error";
    statusPanel.textContent = "Não foi possível consultar o status da base.";
  }
}

async function search(cnpj) {
  setPanelsVisible(false);
  resetPanelValues();
  showMessage("Consultando...", "loading");
  setSearchLoading(true);

  try {
    const response = await fetch(`/api/search?cnpj=${encodeURIComponent(cnpj)}`, {
      cache: "no-store",
    });
    const data = await response.json();
    renderResults(data);
  } catch (error) {
    setPanelsVisible(false);
    showMessage("Não foi possível concluir a consulta. Tente novamente.", "warning");
  } finally {
    setSearchLoading(false);
  }
}

function updatePrintReportHeader() {
  if (!printReportHeader) return;
  printReportHeader.hidden = false;
  printReportCnpj.textContent = lastSuccessfulCnpj ? formatCnpj(lastSuccessfulCnpj) : "-";
  printReportDate.textContent = new Date().toLocaleString("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

function exportPdf() {
  if (!lastSuccessfulCnpj) {
    showMessage("Faça uma consulta antes de exportar o PDF.", "warning");
    return;
  }

  setActionLoading(exportPdfButton, true);
  updatePrintReportHeader();
  titleBeforePrintExport = document.title;
  document.title = `consulta-cnpj-${onlyDigits(lastSuccessfulCnpj) || "cliente"}`;
  document.body.classList.add("pdf-export-mode");
  showMessage("Na janela de impressão, escolha Salvar como PDF.", "success");

  window.setTimeout(() => {
    window.print();
    window.setTimeout(cleanupPrintExport, 1000);
  }, 150);
}

function cleanupPrintExport() {
  if (titleBeforePrintExport) {
    document.title = titleBeforePrintExport;
    titleBeforePrintExport = "";
  }
  document.body.classList.remove("pdf-export-mode");
  setActionLoading(exportPdfButton, false);
}

async function refreshData() {
  setActionLoading(refreshDataButton, true);
  showMessage("Atualizando dados da base...", "loading");
  const cnpjToReload = lastSuccessfulCnpj;

  try {
    const response = await fetch("/api/data/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (redirectIfUnauthorized(response)) return;
    const data = await response.json();
    renderStatus(data);

    if (!response.ok || !data.ok) {
      setPanelsVisible(false);
      resetPanelValues();
      showMessage(data.message || "Não foi possível atualizar os dados.", "warning");
      return;
    }

    if (cnpjToReload) {
      await search(cnpjToReload);
      showMessage("Dados atualizados com sucesso.", "success");
      return;
    }

    showMessage("Dados atualizados com sucesso.", "success");
  } catch (error) {
    showMessage("Não foi possível atualizar os dados. Tente novamente.", "warning");
  } finally {
    setActionLoading(refreshDataButton, false);
  }
}

cnpjInput.addEventListener("input", () => {
  cnpjInput.value = formatCnpj(cnpjInput.value);
  lastSuccessfulCnpj = "";
  setPanelsVisible(false);
  resetPanelValues();
  hideMessage();
});

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!baseReady || searchLoading) return;
  const cnpj = cnpjInput.value;
  const params = new URLSearchParams(window.location.search);
  params.set("cnpj", cnpj);
  window.history.replaceState({}, "", `/app?${params.toString()}`);
  search(cnpj);
});

sidebarToggle?.addEventListener("click", () => {
  document.body.classList.toggle("sidebar-open");
});

offersToggle?.addEventListener("click", () => {
  setOffersExpanded(offersToggle.getAttribute("aria-expanded") !== "true");
});

exportPdfButton?.addEventListener("click", exportPdf);
refreshDataButton?.addEventListener("click", refreshData);
window.addEventListener("afterprint", cleanupPrintExport);

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    document.body.classList.remove("sidebar-open");
  }
});

renderDetailLinks();
loadStatus();
