(() => {
  const root = document.documentElement;
  const storedTheme = localStorage.getItem("theme");
  const systemDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  root.dataset.theme = storedTheme || (systemDark ? "dark" : "light");

  function updateThemeButtons() {
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      const dark = root.dataset.theme === "dark";
      button.setAttribute("aria-label", dark ? "Use light mode" : "Use dark mode");
      button.textContent = dark ? "☀" : "☾";
    });
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-theme-toggle]");
    if (!button) return;
    root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
    localStorage.setItem("theme", root.dataset.theme);
    updateThemeButtons();
  });

  function updateClock() {
    document.querySelectorAll("[data-live-clock]").forEach((element) => {
      element.textContent = new Intl.DateTimeFormat("en-GB", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      }).format(new Date());
    });
  }

  function dismissToasts() {
    document.querySelectorAll("[data-auto-dismiss]").forEach((toast) => {
      setTimeout(() => toast.remove(), Number(toast.dataset.autoDismiss || 4500));
    });
  }

  window.appLoading = {
    show(title = "Working…", description = "Please keep this page open.") {
      const overlay = document.getElementById("loadingOverlay");
      if (!overlay) return;
      overlay.querySelector("[data-loading-title]").textContent = title;
      overlay.querySelector("[data-loading-description]").textContent = description;
      overlay.classList.add("show");
      overlay.setAttribute("aria-hidden", "false");
    },
    hide() {
      const overlay = document.getElementById("loadingOverlay");
      if (!overlay) return;
      overlay.classList.remove("show");
      overlay.setAttribute("aria-hidden", "true");
    },
  };

  updateThemeButtons();
  updateClock();
  dismissToasts();
  setInterval(updateClock, 1000);
})();
