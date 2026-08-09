(function () {
  "use strict";

  var header = document.querySelector("[data-lab-header]");
  var toggle = document.querySelector("[data-lab-menu-toggle]");
  var nav = document.querySelector(".lab-nav");
  var lastFocus = null;

  document.documentElement.classList.add("js");

  function closeMenu() {
    if (!header || !toggle) return;
    header.classList.remove("menu-open");
    toggle.setAttribute("aria-expanded", "false");
    if (lastFocus) lastFocus.focus();
  }

  if (header) {
    var updateHeader = function () { header.classList.toggle("is-scrolled", window.scrollY > 12); };
    updateHeader();
    window.addEventListener("scroll", updateHeader, { passive: true });
  }
  if (toggle) {
    toggle.addEventListener("click", function () {
      lastFocus = document.activeElement;
      var open = header.classList.toggle("menu-open");
      toggle.setAttribute("aria-expanded", String(open));
      if (open && nav) {
        var first = nav.querySelector("a");
        if (first) first.focus();
      }
    });
  }
  document.addEventListener("click", function (event) {
    if (header && header.classList.contains("menu-open") && !header.contains(event.target)) closeMenu();
    if (header && header.classList.contains("menu-open") && event.target.closest(".lab-nav a, .lab-cta")) closeMenu();
  });
  document.addEventListener("keydown", function (event) { if (event.key === "Escape" && header && header.classList.contains("menu-open")) closeMenu(); });

  document.querySelectorAll("[data-current-year]").forEach(function (node) { node.textContent = String(new Date().getFullYear()); });

  window.EliOraLab = {
    announce: function (node, message) { if (node) node.textContent = message; },
    openDialog: function (dialog, opener) {
      if (!dialog) return;
      dialog.__opener = opener || document.activeElement;
      if (typeof dialog.showModal === "function") dialog.showModal(); else dialog.removeAttribute("hidden");
      var focusTarget = dialog.querySelector("[data-dialog-close], button, input, select");
      if (focusTarget) focusTarget.focus();
    },
    closeDialog: function (dialog) {
      if (!dialog) return;
      if (typeof dialog.close === "function" && dialog.open) dialog.close(); else dialog.setAttribute("hidden", "");
      if (dialog.__opener && typeof dialog.__opener.focus === "function") dialog.__opener.focus();
    }
  };
}());
