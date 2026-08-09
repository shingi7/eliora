(function () {
  "use strict";
  var api = {
    money: function (value, digits) { return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: digits == null ? 0 : digits }).format(value); },
    number: function (value) { return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value); },
    percent: function (value, digits) { return Number(value).toFixed(digits == null ? 1 : digits) + "%"; },
    escape: function (value) { return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[char]; }); },
    copy: function (value, statusNode) {
      var done = function () { if (statusNode) statusNode.textContent = "Copied to clipboard."; };
      var fallback = function () { var area = document.createElement("textarea"); area.value = value; area.setAttribute("readonly", ""); area.style.position = "fixed"; area.style.opacity = "0"; document.body.appendChild(area); area.select(); try { document.execCommand("copy"); } catch (error) {} document.body.removeChild(area); done(); };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(value).then(done).catch(fallback); else fallback();
    },
    download: function (filename, content, type) { var blob = new Blob([content], { type: type || "text/plain" }); var link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = filename; document.body.appendChild(link); link.click(); link.remove(); setTimeout(function () { URL.revokeObjectURL(link.href); }, 0); },
    csv: function (rows) { return rows.map(function (row) { return row.map(function (cell) { var text = String(cell == null ? "" : cell).replace(/"/g, '""'); return '"' + text + '"'; }).join(","); }).join("\n"); },
    svgLine: function (points, width, height, padding) { var p = padding || 24; var min = Math.min.apply(null, points); var max = Math.max.apply(null, points); var span = max - min || 1; var step = (width - (p * 2)) / Math.max(1, points.length - 1); return points.map(function (value, index) { return (p + (index * step)).toFixed(1) + "," + (height - p - (((value - min) / span) * (height - (p * 2)))).toFixed(1); }).join(" "); },
    openDialog: function (dialog, opener) { if (window.EliOraLab) window.EliOraLab.openDialog(dialog, opener); },
    closeDialog: function (dialog) { if (window.EliOraLab) window.EliOraLab.closeDialog(dialog); }
  };
  window.EliOraDemo = api;
}());
