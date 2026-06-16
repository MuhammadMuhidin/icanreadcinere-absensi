(() => {
  const root = document.documentElement;
  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const storedTheme = localStorage.getItem("theme");
  const systemDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  const prefetched = new Set();

  root.dataset.theme = storedTheme || (systemDark ? "dark" : "light");

  function matchesAndDescendants(scope, selector) {
    const matches = [];
    if (scope instanceof Element && scope.matches(selector)) matches.push(scope);
    if (scope?.querySelectorAll) matches.push(...scope.querySelectorAll(selector));
    return matches;
  }

  function updateThemeButtons() {
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      const dark = root.dataset.theme === "dark";
      button.setAttribute("aria-label", dark ? "Use light mode" : "Use dark mode");
      button.setAttribute("title", dark ? "Use light mode" : "Use dark mode");
      button.textContent = dark ? "☀" : "☾";
    });
  }

  function switchTheme(button) {
    root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
    localStorage.setItem("theme", root.dataset.theme);
    document.querySelector('meta[name="theme-color"]')?.setAttribute(
      "content",
      root.dataset.theme === "dark" ? "#09111f" : "#193773"
    );
    button?.classList.add("theme-switching");
    setTimeout(() => button?.classList.remove("theme-switching"), 380);
    updateThemeButtons();
  }

  function updateClock() {
    const value = new Intl.DateTimeFormat("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(new Date());
    document.querySelectorAll("[data-live-clock]").forEach((element) => {
      element.textContent = value;
    });
  }

  function removeToast(toast) {
    if (!toast?.isConnected) return;
    toast.classList.add("is-leaving");
    setTimeout(() => toast.remove(), reducedMotion ? 0 : 230);
  }

  function initialiseToasts(scope = document) {
    matchesAndDescendants(scope, "[data-auto-dismiss]:not([data-toast-ready])").forEach((toast) => {
      toast.dataset.toastReady = "true";
      const duration = Number(toast.dataset.autoDismiss || 5000);
      toast.style.setProperty("--toast-duration", `${duration}ms`);
      const timer = setTimeout(() => removeToast(toast), duration);
      toast.addEventListener("click", () => {
        clearTimeout(timer);
        removeToast(toast);
      });
      if (toast.classList.contains("toast-success")) createSuccessBurst(toast);
    });
  }

  function createSuccessBurst(anchor) {
    if (reducedMotion) return;
    const rect = anchor.getBoundingClientRect();
    const x = rect.right - 20;
    const y = rect.top + rect.height / 2;
    for (let index = 0; index < 7; index += 1) {
      const particle = document.createElement("span");
      const angle = (Math.PI * 2 * index) / 7;
      const distance = 18 + Math.random() * 18;
      particle.className = "success-burst";
      particle.style.left = `${x}px`;
      particle.style.top = `${y}px`;
      particle.style.setProperty("--burst-x", `${Math.cos(angle) * distance}px`);
      particle.style.setProperty("--burst-y", `${Math.sin(angle) * distance}px`);
      document.body.appendChild(particle);
      setTimeout(() => particle.remove(), 700);
    }
  }

  function addRipple(event, element) {
    if (reducedMotion || element.disabled) return;
    const rect = element.getBoundingClientRect();
    const ripple = document.createElement("span");
    ripple.className = "ripple";
    ripple.style.left = `${event.clientX ? event.clientX - rect.left : rect.width / 2}px`;
    ripple.style.top = `${event.clientY ? event.clientY - rect.top : rect.height / 2}px`;
    element.appendChild(ripple);
    setTimeout(() => ripple.remove(), 580);
  }

  function animateNumber(element) {
    if (element.dataset.countReady === "true") return;
    const raw = element.textContent.trim();
    if (!/^\d+$/.test(raw)) return;
    element.dataset.countReady = "true";
    if (reducedMotion) return;
    const target = Number(raw);
    if (target === 0) return;
    const duration = Math.min(650, 280 + target * 12);
    const start = performance.now();
    element.classList.add("counting");
    const frame = (time) => {
      const progress = Math.min(1, (time - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      element.textContent = String(Math.round(target * eased));
      if (progress < 1) requestAnimationFrame(frame);
      else {
        element.textContent = String(target);
        setTimeout(() => element.classList.remove("counting"), 180);
      }
    };
    requestAnimationFrame(frame);
  }

  function revealElements(scope = document) {
    const selector = ".page-content > section:not([data-reveal-ready]), .page-content > .grid:not([data-reveal-ready]), .list-card:not([data-reveal-ready])";
    matchesAndDescendants(scope, selector).forEach((element, index) => {
      element.dataset.revealReady = "true";
      element.classList.add("reveal-item");
      element.style.setProperty("--reveal-delay", `${Math.min(index * 38, 190)}ms`);
      requestAnimationFrame(() => requestAnimationFrame(() => element.classList.add("is-visible")));
    });
    matchesAndDescendants(scope, ".metric-value").forEach(animateNumber);
  }

  function isPrefetchable(anchor) {
    if (!anchor || anchor.target || anchor.hasAttribute("download") || anchor.dataset.noPrefetch !== undefined) return false;
    if (anchor.getAttribute("href")?.startsWith("#")) return false;
    const url = new URL(anchor.href, location.href);
    if (url.origin !== location.origin || url.pathname === "/logout") return false;
    if (!["http:", "https:"].includes(url.protocol)) return false;
    return true;
  }

  function prefetch(anchor) {
    if (!isPrefetchable(anchor)) return;
    const url = new URL(anchor.href, location.href);
    url.hash = "";
    const key = url.href;
    if (key === location.href.split("#")[0] || prefetched.has(key)) return;
    prefetched.add(key);

    const link = document.createElement("link");
    link.rel = "prefetch";
    link.href = key;
    link.as = "document";
    document.head.appendChild(link);

    fetch(key, {
      method: "GET",
      credentials: "same-origin",
      cache: "force-cache",
      priority: "low",
      headers: { "X-Purpose": "prefetch" },
    }).catch(() => {});
  }

  function predictivePrefetch() {
    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (connection?.saveData || /(^|-)2g$/.test(connection?.effectiveType || "")) return;

    const preferredPaths = location.pathname === "/absence"
      ? ["/history", "/paid_leave"]
      : ["/absence"];
    const links = preferredPaths
      .map((path) => document.querySelector(`a[href="${path}"]`))
      .filter(Boolean);

    const work = () => links.forEach((link, index) => {
      setTimeout(() => prefetch(link), index * 420);
    });
    if ("requestIdleCallback" in window) requestIdleCallback(work, { timeout: 2200 });
    else setTimeout(work, 900);
  }

  function beginNavigation(anchor) {
    if (!isPrefetchable(anchor)) return;
    const destination = new URL(anchor.href, location.href);
    if (destination.href === location.href) return;
    root.classList.remove("navigation-complete");
    root.classList.add("is-navigating");
  }

  function completeNavigation() {
    root.classList.remove("is-navigating");
    root.classList.add("navigation-complete");
    setTimeout(() => root.classList.remove("navigation-complete"), 420);
  }

  function enhanceActiveNavigation() {
    document.querySelectorAll(".nav-item").forEach((item) => {
      if (item.classList.contains("active")) item.setAttribute("aria-current", "page");
      else item.removeAttribute("aria-current");
    });
  }

  document.addEventListener("click", (event) => {
    const themeButton = event.target.closest("[data-theme-toggle]");
    if (themeButton) {
      switchTheme(themeButton);
      return;
    }

    const interactive = event.target.closest(".btn, .icon-button, .nav-item, .tab");
    if (interactive) addRipple(event, interactive);

    const anchor = event.target.closest("a[href]");
    if (anchor && !event.defaultPrevented && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
      beginNavigation(anchor);
    }
  });

  document.addEventListener("pointerdown", (event) => {
    const target = event.target.closest(".btn, .icon-button, .nav-item, .tab");
    target?.classList.add("is-pressing");
  });
  ["pointerup", "pointercancel", "pointerleave"].forEach((type) => {
    document.addEventListener(type, (event) => event.target.closest?.(".is-pressing")?.classList.remove("is-pressing"), true);
  });

  ["pointerenter", "focusin", "touchstart"].forEach((type) => {
    document.addEventListener(type, (event) => prefetch(event.target.closest?.("a[href]")), true);
  });

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => mutation.addedNodes.forEach((node) => {
      if (!(node instanceof Element)) return;
      initialiseToasts(node);
      revealElements(node);
    }));
  });
  observer.observe(document.body, { childList: true, subtree: true });

  window.appLoading = {
    show(title = "Working…", description = "Please keep this page open.") {
      const overlay = document.getElementById("loadingOverlay");
      if (!overlay) return;
      overlay.querySelector("[data-loading-title]").textContent = title;
      overlay.querySelector("[data-loading-description]").textContent = description;
      overlay.classList.add("show");
      overlay.setAttribute("aria-hidden", "false");
      document.body.setAttribute("aria-busy", "true");
    },
    hide() {
      const overlay = document.getElementById("loadingOverlay");
      if (!overlay) return;
      overlay.classList.remove("show");
      overlay.setAttribute("aria-hidden", "true");
      document.body.removeAttribute("aria-busy");
    },
  };

  updateThemeButtons();
  updateClock();
  initialiseToasts();
  revealElements();
  enhanceActiveNavigation();
  predictivePrefetch();
  completeNavigation();
  setInterval(updateClock, 1000);
  window.addEventListener("pageshow", completeNavigation);
  window.addEventListener("pagehide", () => root.classList.add("is-navigating"));
})();
