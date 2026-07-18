(async () => {
  const userName = document.querySelector("#currentUserName");
  const userRole = document.querySelector("#currentUserRole");
  const userInitials = document.querySelector("#currentUserInitials");
  const adminNavItem = document.querySelector("#adminNavItem");
  const adminReportsNavItem = document.querySelector("#adminReportsNavItem");
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
    if (userRole) userRole.textContent = roleLabels[user.perfil] || user.perfil || "Perfil";
    if (userInitials) userInitials.textContent = initials(user.nome_completo);
    if (adminNavItem) adminNavItem.hidden = user.perfil !== "ADMIN";
    if (adminReportsNavItem) adminReportsNavItem.hidden = !["ADMIN", "GESTOR", "SUPERVISOR"].includes(user.perfil);
    window.setInterval(verifyActiveSession, 30_000);
  } catch (error) {
    window.location.href = "/login";
  }
})();
