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
      </tr>
    </thead>
    <tbody></tbody>
  `;

  const tbody = table.querySelector("tbody");
  items.forEach((item) => {
    const row = document.createElement("tr");
    [item.line || "-", item.plan || "-", item.m || "-", formatCurrency(item.average_billing)].forEach(
      (value) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.appendChild(cell);
      },
    );
    tbody.appendChild(row);
  });

  detailContent.appendChild(table);
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

function renderBroadband(items) {
  detailContent.innerHTML = "";
  if (!items.length) {
    renderEmpty("Nenhuma BL encontrada para este CNPJ.");
    return;
  }

  items.forEach((account) => {
    const block = document.createElement("article");
    block.className = "account-block";

    const header = document.createElement("div");
    header.className = "account-header";
    [
      ["Conta", account.account || "Sem conta"],
      ["Total", formatCurrency(account.total_billing)],
    ].forEach(([label, value]) => {
      const item = document.createElement("div");
      const labelEl = document.createElement("span");
      labelEl.textContent = label;
      const valueEl = document.createElement("strong");
      valueEl.textContent = value;
      item.append(labelEl, valueEl);
      header.appendChild(item);
    });

    block.append(header, createProductTable(account.products || []));
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
