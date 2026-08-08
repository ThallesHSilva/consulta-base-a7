(async () => {
  const userName = document.querySelector("#currentUserName");
  const userRole = document.querySelector("#currentUserRole");
  const userInitials = document.querySelector("#currentUserInitials");
  const adminNavItem = document.querySelector("#adminNavItem");
  const adminReportsNavItem = document.querySelector("#adminReportsNavItem");
  const sidebarNav = document.querySelector(".sidebar-nav");
  const logoutButton = document.querySelector("#logoutButton");

  function initials(name) {
    const parts = String(name || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2);
    return parts.map((part) => part[0]).join("").toUpperCase() || "--";
  }

  async function logout() {
    await fetch("/api/auth/logout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    window.location.href = "/login";
  }

  async function verifyActiveSession() {
    try {
      const response = await fetch("/api/auth/me", { cache: "no-store" });
      if (response.status === 401) {
        window.location.replace("/login");
      }
    } catch (error) {
      // Falhas momentâneas de rede não encerram a sessão local.
    }
  }

  logoutButton?.addEventListener("click", logout);

  try {
    const response = await fetch("/api/auth/me", { cache: "no-store" });
    if (!response.ok) {
      window.location.href = "/login";
      return;
    }
    const data = await response.json();
    const user = data.user;
    if (!user) {
      window.location.href = "/login";
      return;
    }

    if (userName) userName.textContent = user.nome_completo || "Usuário";
    const roleLabels = {
      ADMIN: "Administrador",
      GESTOR: "Gestor",
      SUPERVISOR: "Supervisor",
      USUARIO: "Usuário",
    };
    if (userRole) {
      const role = roleLabels[user.perfil] || user.perfil || "Perfil";
      userRole.textContent = user.organization_name ? `${role} · ${user.organization_name}` : role;
    }
    if (userInitials) userInitials.textContent = initials(user.nome_completo);
    document.querySelectorAll(".brand-logo").forEach((logo) => {
      logo.src = `/api/branding/logo?v=${Date.now()}`;
      logo.alt = user.organization_name ? `Logo ${user.organization_name}` : "Logo da empresa";
    });
    if (adminNavItem) adminNavItem.hidden = user.perfil !== "ADMIN";
    if (adminReportsNavItem) adminReportsNavItem.hidden = !["ADMIN", "GESTOR", "SUPERVISOR"].includes(user.perfil);
    if (sidebarNav && user.is_platform_admin && !document.querySelector("#platformOrganizationsNavItem")) {
      const link = document.createElement("a");
      link.id = "platformOrganizationsNavItem";
      link.className = "nav-item";
      link.href = "/admin/empresas";
      link.title = "Empresas";
      link.innerHTML = "<span aria-hidden=\"true\">▦</span><span>Empresas</span>";
      sidebarNav.appendChild(link);
    }
    window.setInterval(verifyActiveSession, 30_000);
  } catch (error) {
    window.location.href = "/login";
  }
})();
