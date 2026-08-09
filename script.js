(() => {
  "use strict";

  const root = document.documentElement;
  root.classList.add("js");

  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  function setActivePage() {
    const page = document.querySelector("[data-page]")?.dataset.page;
    if (!page) return;
    document.querySelectorAll("[data-nav]").forEach((link) => {
      if (link.dataset.nav === page) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  }

  function setupHeader() {
    const header = document.querySelector("[data-site-header]");
    const toggle = document.querySelector(".nav-toggle");
    const nav = document.querySelector(".primary-nav");
    const firstLink = nav?.querySelector("a");
    if (!header || !toggle || !nav) return;

    const setScrolled = () => header.classList.toggle("is-scrolled", window.scrollY > 12);
    setScrolled();
    window.addEventListener("scroll", setScrolled, { passive: true });

    const closeMenu = (returnFocus = false) => {
      nav.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
      if (returnFocus) toggle.focus();
    };

    toggle.addEventListener("click", () => {
      const isOpen = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!isOpen));
      nav.classList.toggle("is-open", !isOpen);
      if (!isOpen) firstLink?.focus();
    });

    nav.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => closeMenu()));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") closeMenu(true);
    });
    document.addEventListener("click", (event) => {
      if (toggle.getAttribute("aria-expanded") === "true" && !nav.contains(event.target) && !toggle.contains(event.target)) closeMenu();
    });
    window.addEventListener("resize", () => {
      if (window.innerWidth > 760) closeMenu();
    }, { passive: true });
  }

  function setupReveals() {
    const targets = [...document.querySelectorAll(".site-page > section")];
    if (!targets.length) return;
    targets.forEach((target) => target.classList.add("reveal-ready"));
    if (prefersReducedMotion.matches || !("IntersectionObserver" in window)) {
      targets.forEach((target) => target.classList.add("is-visible"));
      return;
    }
    const observer = new IntersectionObserver((entries, instance) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        instance.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: .08 });
    targets.forEach((target) => observer.observe(target));
  }

  function setupSignalInstrument() {
    const instrument = document.querySelector("[data-signal-instrument]");
    if (!instrument || prefersReducedMotion.matches || !window.matchMedia("(pointer: fine)").matches) return;
    instrument.addEventListener("pointermove", (event) => {
      const bounds = instrument.getBoundingClientRect();
      const x = ((event.clientX - bounds.left) / bounds.width) * 100;
      const y = ((event.clientY - bounds.top) / bounds.height) * 100;
      instrument.style.setProperty("--pointer-x", `${x}%`);
      instrument.style.setProperty("--pointer-y", `${y}%`);
    }, { passive: true });
    instrument.addEventListener("pointerleave", () => {
      instrument.style.removeProperty("--pointer-x");
      instrument.style.removeProperty("--pointer-y");
    }, { passive: true });
  }

  function setupContactForm() {
    const form = document.querySelector("#contact-form");
    if (!form || typeof window.fetch !== "function") return;
    const button = form.querySelector("button[type='submit']");
    const status = form.querySelector("#form-status");
    if (!button || !status) return;

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const originalLabel = button.innerHTML;
      button.disabled = true;
      form.setAttribute("aria-busy", "true");
      status.className = "form-status";
      status.textContent = "Sending…";
      try {
        const response = await fetch(form.action, {
          method: form.method || "POST",
          body: new FormData(form),
          headers: { Accept: "application/json" }
        });
        if (!response.ok) throw new Error("Submission failed");
        form.reset();
        status.classList.add("success");
        status.textContent = "Thanks—your message has been sent. We’ll be in touch.";
      } catch (error) {
        status.classList.add("error");
        status.textContent = "Something went wrong. Please try again or submit the form directly.";
      } finally {
        button.disabled = false;
        button.innerHTML = originalLabel;
        form.removeAttribute("aria-busy");
      }
    });
  }

  function setCurrentYear() {
    const year = String(new Date().getFullYear());
    document.querySelectorAll("[data-current-year]").forEach((element) => { element.textContent = year; });
  }

  setActivePage();
  setupHeader();
  setupReveals();
  setupSignalInstrument();
  setupContactForm();
  setCurrentYear();
})();
