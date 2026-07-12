const detailTitle = document.querySelector("#detailTitle");
const detailCompanyName = document.querySelector("#detailCompanyName");
const detailCnpj = document.querySelector("#detailCnpj");
const detailContent = document.querySelector("#detailContent");
const backLink = document.querySelector("#backLink");
const sidebarToggle = document.querySelector("#sidebarToggle");

const params = new URLSearchParams(window.location.search);
const detailType = params.get("type") || "";
const cnpj = params.get("cnpj") || "";
backLink.href = cnpj ? `/app?cnpj=${encodeURIComponent(cnpj)}` : "/app";

function formatCurrency(value) {
  if (!Number.isFinite(value)) return "-";
  return value.toLocaleString("pt-BR", {
    currency: "BRL",
    style: "currency",
  });
}

function setPageTitle() {
  if (detailType === "mobile") {
    detailTitle.textContent = "Detalhamento móvel";
    return;
  }

  if (detailType === "broadband") {
    detailTitle.textContent = "Detalhamento BL";
    return;
  }

  detailTitle.textContent = "Detalhamento";
}

function renderEmpty(message) {
  detailContent.innerHTML = "";
  const empty = document.createElement("div");
  empty.className = "empty-state";
  empty.textContent = message;
  detailContent.appendChild(empty);
}

function createMobileOfferTable(offers) {
  const table = document.createElement("table");
  table.className = "detail-table mobile-offer-table";
  table.innerHTML = `
    <thead>
      <tr>
        <th>OFERTA</th>
        <th>PLANO</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;

  const tbody = table.querySelector("tbody");
  offers.forEach((offer) => {
    const row = document.createElement("tr");
    [offer.offer || "-", offer.plan || "-"].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.appendChild(cell);
    });
    tbody.appendChild(row);
  });
  return table;
}

function renderMobile(items) {
  detailContent.innerHTML = "";
  if (!items.length) {
    renderEmpty("Nenhuma linha móvel encontrada para este CNPJ.");
    return;
  }

  const table = document.createElement("table");
  table.className = "detail-table";
  table.innerHTML = `
    <thead>
      <tr>
        <th>Linha</th>
        <th>Plano</th>
        <th>M</th>
        <th>Média de Faturamento</th>
        <th>Ofertas</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;

  const tbody = table.querySelector("tbody");
  const expandableRows = [];
  let expandAllButton = null;

  function updateExpandAllLabel() {
    if (!expandAllButton) return;
    const allExpanded = expandableRows.every((entry) => !entry.offerRow.hidden);
    expandAllButton.textContent = allExpanded
      ? "Recolher todas as ofertas"
      : "Expandir todas as ofertas";
    expandAllButton.setAttribute("aria-expanded", allExpanded ? "true" : "false");
  }

  function setLineExpanded(entry, expanded) {
    entry.offerRow.hidden = !expanded;
    entry.button.setAttribute("aria-expanded", expanded ? "true" : "false");
    entry.button.classList.toggle("is-expanded", expanded);
    entry.button.querySelector("span").textContent = expanded ? "Recolher" : "Ver ofertas";
    updateExpandAllLabel();
  }

  items.forEach((item, index) => {
    const row = document.createElement("tr");
    row.className = "mobile-line-row";
    [item.line || "-", item.plan || "-", item.m || "-", formatCurrency(item.average_billing)].forEach(
      (value) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.appendChild(cell);
      },
    );

    const offers = item.offers || [];
    const actionCell = document.createElement("td");
    if (!offers.length) {
      actionCell.textContent = "-";
      row.appendChild(actionCell);
      tbody.appendChild(row);
      return;
    }

    const button = document.createElement("button");
    button.type = "button";
    button.className = "mobile-line-offers-toggle";
    button.setAttribute("aria-expanded", "false");
    button.setAttribute("aria-controls", `mobileLineOffers${index}`);
    button.innerHTML = `
      <span>Ver ofertas</span>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
    `;
    actionCell.appendChild(button);
    row.appendChild(actionCell);

    const offerRow = document.createElement("tr");
    offerRow.id = `mobileLineOffers${index}`;
    offerRow.className = "mobile-offer-row";
    offerRow.hidden = true;
    const offerCell = document.createElement("td");
    offerCell.colSpan = 5;
    const panel = document.createElement("section");
    panel.className = "mobile-line-offers-panel";
    const heading = document.createElement("div");
    heading.className = "mobile-line-offers-heading";
    const label = document.createElement("span");
    label.textContent = "Ofertas para a linha";
    const line = document.createElement("strong");
    line.textContent = item.line || "-";
    heading.append(label, line);
    panel.append(heading, createMobileOfferTable(offers));
    offerCell.appendChild(panel);
    offerRow.appendChild(offerCell);

    const entry = { button, offerRow };
    expandableRows.push(entry);
    button.addEventListener("click", () => setLineExpanded(entry, offerRow.hidden));
    tbody.append(row, offerRow);
  });

  if (!expandableRows.length) {
    detailContent.appendChild(table);
    return;
  }

  const toolbar = document.createElement("div");
  toolbar.className = "mobile-detail-toolbar";
  const summary = document.createElement("span");
  summary.textContent = `${expandableRows.length} ${expandableRows.length === 1 ? "linha com oferta" : "linhas com ofertas"}`;
  expandAllButton = document.createElement("button");
  expandAllButton.type = "button";
  expandAllButton.className = "mobile-offers-all-toggle";
  expandAllButton.textContent = "Expandir todas as ofertas";
  expandAllButton.setAttribute("aria-expanded", "false");
  expandAllButton.addEventListener("click", () => {
    const shouldExpand = expandableRows.some((entry) => entry.offerRow.hidden);
    expandableRows.forEach((entry) => setLineExpanded(entry, shouldExpand));
  });
  toolbar.append(summary, expandAllButton);
  detailContent.append(toolbar, table);
}

function createProductTable(products) {
  const table = document.createElement("table");
  table.className = "detail-table";
  table.innerHTML = `
    <thead>
      <tr>
        <th>DESIGNADOR</th>
        <th>DS_PRODUTO</th>
        <th>Média de Faturamento</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;

  const tbody = table.querySelector("tbody");
  products.forEach((product) => {
    const row = document.createElement("tr");
    [
      product.designator || "-",
      product.product || "-",
      formatCurrency(product.billing),
    ].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.appendChild(cell);
    });
    tbody.appendChild(row);
  });

  return table;
}

function createOfferTable(offers) {
  const table = document.createElement("table");
  table.className = "detail-table offer-table";
  table.innerHTML = `
    <thead>
      <tr>
        <th>OFERTA</th>
        <th>PLANO</th>
        <th>RECOMENDAÇÃO</th>
        <th>VALOR</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;

  const tbody = table.querySelector("tbody");
  offers.forEach((offer) => {
    const row = document.createElement("tr");
    [
      offer.offer || "-",
      offer.plan || "-",
      offer.recommendation_label || "-",
      formatCurrency(offer.value),
    ].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.appendChild(cell);
    });
    tbody.appendChild(row);
  });

  return table;
}

function createOffersPanel(offers, index) {
  const panel = document.createElement("section");
  panel.id = `accountOffers${index}`;
  panel.className = "account-offers-panel";
  panel.hidden = true;

  const heading = document.createElement("div");
  heading.className = "account-offers-heading";
  const eyebrow = document.createElement("span");
  eyebrow.textContent = "Recomendações disponíveis";
  const title = document.createElement("strong");
  title.textContent = `${offers.length} ${offers.length === 1 ? "oferta" : "ofertas"}`;
  heading.append(eyebrow, title);

  panel.append(heading, createOfferTable(offers));
  return panel;
}

function createOffersToggle(offers, panel) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "account-offers-toggle";
  button.setAttribute("aria-expanded", "false");
  button.setAttribute("aria-controls", panel.id);
  button.innerHTML = `
    <span>Ver ofertas (${offers.length})</span>
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
  `;

  button.addEventListener("click", () => {
    const expanded = button.getAttribute("aria-expanded") === "true";
    button.setAttribute("aria-expanded", expanded ? "false" : "true");
    button.classList.toggle("is-expanded", !expanded);
    button.querySelector("span").textContent = expanded
      ? `Ver ofertas (${offers.length})`
      : "Recolher ofertas";
    panel.hidden = expanded;
  });

  return button;
}

function renderBroadband(items) {
  detailContent.innerHTML = "";
  if (!items.length) {
    renderEmpty("Nenhuma BL encontrada para este CNPJ.");
    return;
  }

  items.forEach((account, index) => {
    const block = document.createElement("article");
    block.className = "account-block";

    const header = document.createElement("div");
    header.className = "account-header";
    [
      ["Conta", account.account || "Sem conta", account.address || "Endereço não informado"],
      ["M", account.m || "-"],
      ["Total", formatCurrency(account.total_billing)],
    ].forEach(([label, value, supportingText]) => {
      const item = document.createElement("div");
      const labelEl = document.createElement("span");
      labelEl.textContent = label;
      const valueEl = document.createElement("strong");
      valueEl.textContent = value;
      item.append(labelEl, valueEl);
      if (supportingText) {
        const supportingEl = document.createElement("small");
        supportingEl.className = "account-address";
        supportingEl.textContent = supportingText;
        item.appendChild(supportingEl);
      }
      header.appendChild(item);
    });

    const offers = account.offers || [];
    const productsTable = createProductTable(account.products || []);
    if (offers.length) {
      const offersPanel = createOffersPanel(offers, index);
      const action = document.createElement("div");
      action.className = "account-offers-action";
      action.appendChild(createOffersToggle(offers, offersPanel));
      header.classList.add("has-offers");
      header.appendChild(action);
      block.append(header, productsTable, offersPanel);
    } else {
      block.append(header, productsTable);
    }
    detailContent.appendChild(block);
  });
}

async function loadDetail() {
  setPageTitle();
  detailCnpj.textContent = cnpj || "-";

  if (!cnpj || !detailType) {
    renderEmpty("Abra o detalhamento a partir de um card consultado.");
    return;
  }

  renderEmpty("Carregando detalhamento...");
  const response = await fetch(
    `/api/detail?type=${encodeURIComponent(detailType)}&cnpj=${encodeURIComponent(cnpj)}`,
    { cache: "no-store" },
  );
  const data = await response.json();

  detailCompanyName.textContent = data.company_name || "-";
  if (data.message) {
    renderEmpty(data.message);
    return;
  }

  if (detailType === "mobile") {
    renderMobile(data.items || []);
    return;
  }

  if (detailType === "broadband") {
    renderBroadband(data.items || []);
    return;
  }

  renderEmpty("Tipo de detalhamento inválido.");
}

loadDetail();

sidebarToggle?.addEventListener("click", () => {
  document.body.classList.toggle("sidebar-open");
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    document.body.classList.remove("sidebar-open");
  }
});
