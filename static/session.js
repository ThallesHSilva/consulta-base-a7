(async () => {
  const userName = document.querySelector("#currentUserName");
  const userRole = document.querySelector("#currentUserRole");
  const userInitials = document.querySelector("#currentUserInitials");
  const adminNavItem = document.querySelector("#adminNavItem");
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
    if (userRole) userRole.textContent = user.perfil === "ADMIN" ? "Administrador" : "Usuário";
    if (userInitials) userInitials.textContent = initials(user.nome_completo);
    if (adminNavItem) adminNavItem.hidden = user.perfil !== "ADMIN";
  } catch (error) {
    window.location.href = "/login";
  }
})();
