const organizationForm = document.querySelector("#organizationForm");
const organizationsList = document.querySelector("#organizationsList");
const organizationsCount = document.querySelector("#organizationsCount");
const organizationMessage = document.querySelector("#organizationMessage");

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  let data = {};
  try { data = await response.json(); } catch (error) { data = {}; }
  return { response, data };
}

function showMessage(message, type = "error") {
  organizationMessage.textContent = message;
  organizationMessage.className = `auth-message ${type}`;
  organizationMessage.hidden = false;
}

function organizationCard(item) {
  const card = document.createElement("article");
  card.className = "organization-card";

  const info = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = item.nome;
  const details = document.createElement("p");
  details.textContent = `${item.slug} · ${item.usuarios_ativos}/${item.total_usuarios} usuário(s) ativo(s)`;
  const link = document.createElement("a");
  link.href = item.registration_url;
  link.textContent = `Link de cadastro: ${window.location.origin}${item.registration_url}`;
  const loginLink = document.createElement("a");
  loginLink.href = item.login_url;
  loginLink.textContent = `Acesso personalizado: ${window.location.origin}${item.login_url}`;
  info.append(title, details, loginLink, link);

  const action = document.createElement("button");
  action.className = "ghost-button";
  action.type = "button";
  action.textContent = item.status === "ATIVA" ? "Bloquear" : "Ativar";
  action.addEventListener("click", async () => {
    const nextStatus = item.status === "ATIVA" ? "BLOQUEADA" : "ATIVA";
    const { response, data } = await postJson("/api/platform/organizations/status", {
      organization_id: item.id,
      status: nextStatus,
    });
    if (!response.ok) {
      showMessage(data.message || "Não foi possível alterar a empresa.");
      return;
    }
    showMessage(data.message, "success");
    await loadOrganizations();
  });

  card.append(info, action);
  return card;
}

async function loadOrganizations() {
  const response = await fetch("/api/platform/organizations", { cache: "no-store" });
  if (!response.ok) return;
  const data = await response.json();
  const organizations = data.organizations || [];
  organizationsCount.textContent = `${organizations.length} empresa(s)`;
  organizationsList.innerHTML = "";
  organizations.forEach((item) => organizationsList.appendChild(organizationCard(item)));
}

organizationForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = organizationForm.querySelector("button[type=submit]");
  button.disabled = true;
  const { response, data } = await postJson("/api/platform/organizations", {
    nome: document.querySelector("#organizationName").value,
    slug: document.querySelector("#organizationSlug").value,
    admin_nome: document.querySelector("#organizationAdminName").value,
    admin_email: document.querySelector("#organizationAdminEmail").value,
    admin_senha: document.querySelector("#organizationAdminPassword").value,
  });
  button.disabled = false;
  if (!response.ok) {
    showMessage(data.message || "Não foi possível criar a empresa.");
    return;
  }
  showMessage(`${data.message} Cadastro: ${window.location.origin}${data.organization.registration_url}`, "success");
  organizationForm.reset();
  await loadOrganizations();
});

loadOrganizations();
