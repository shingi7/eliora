(function () {
  "use strict";

  var U = window.EliOraDemo;
  var $ = function (id) { return document.getElementById(id); };
  var presets = {
    base: { demand: 8, price: 3, cost: 4, payroll: 2, collections: 14 },
    dip: { demand: -18, price: 1, cost: 3, payroll: 2, collections: 20 },
    cost: { demand: 7, price: 2, cost: 24, payroll: 8, collections: 18 },
    collections: { demand: 6, price: 2, cost: 5, payroll: 3, collections: 48 }
  };
  var fields = ["demand", "price", "cost", "payroll", "collections"];
  var state = Object.assign({}, presets.base);
  var weeks = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9", "W10", "W11", "W12", "W13"];

  function values() {
    var weekly = [];
    var cash = 118000;
    var collectionDelayWeeks = Math.ceil(state.collections / 7);
    weeks.forEach(function (week, i) {
      var base = 32500 + (i * 850);
      var revenue = base * (1 + (state.demand / 100)) * (1 + (state.price / 100));
      var direct = revenue * (.34 + (state.cost / 1000));
      var payroll = 14500 * (1 + (state.payroll / 100));
      var collectionRate = i < collectionDelayWeeks ? .58 : .92;
      var cashIn = revenue * collectionRate;
      var delayDrag = Math.max(0, state.collections - 14) * (i < collectionDelayWeeks ? 210 : 55);
      cash += cashIn - direct - payroll - delayDrag + 1500;
      weekly.push({
        week: week,
        revenue: revenue,
        direct: direct,
        payroll: payroll,
        ending: cash,
        age: collectionDelayWeeks > 2 && i < collectionDelayWeeks ? "Collections delayed" : "Within plan"
      });
    });
    var totalRevenue = weekly.reduce(function (sum, row) { return sum + row.revenue; }, 0);
    var totalDirect = weekly.reduce(function (sum, row) { return sum + row.direct; }, 0);
    var totalPayroll = weekly.reduce(function (sum, row) { return sum + row.payroll; }, 0);
    var ar = 42000 + (state.collections * 1220);
    return {
      weekly: weekly,
      revenue: totalRevenue,
      margin: ((totalRevenue - totalDirect) / totalRevenue) * 100,
      cash: weekly[12].ending,
      ar: ar,
      buffer: weekly[12].ending - totalPayroll,
      direct: totalDirect,
      payroll: totalPayroll
    };
  }

  function input(field, value) {
    document.querySelectorAll('[data-field="' + field + '"]').forEach(function (node) { node.value = value; });
  }

  function renderChart(rows) {
    var cashValues = rows.map(function (row) { return row.ending; });
    var points = U.svgLine(cashValues, 760, 240, 32);
    var first = points.split(" ")[0];
    var last = points.split(" ").slice(-1)[0];
    $("cash-chart").innerHTML = '<svg viewBox="0 0 760 240" role="img" aria-labelledby="cash-chart-title cash-chart-desc"><title id="cash-chart-title">13-week ending cash, recalculated</title><desc id="cash-chart-desc">The cash path changes with demand, cost, payroll, and collection timing assumptions. Ending cash moves from ' + U.money(cashValues[0]) + ' in week 1 to ' + U.money(cashValues[12]) + ' in week 13.</desc><line class="chart-grid" x1="32" x2="728" y1="50" y2="50"/><line class="chart-grid" x1="32" x2="728" y1="120" y2="120"/><line class="chart-grid" x1="32" x2="728" y1="190" y2="190"/><polyline class="chart-line" points="' + points + '"/><circle cx="' + first.split(",")[0] + '" cy="' + first.split(",")[1] + '" r="5" fill="var(--lab-lime)"/><circle cx="' + last.split(",")[0] + '" cy="' + last.split(",")[1] + '" r="5" fill="var(--lab-lime)"/><text class="chart-axis" x="32" y="225">W1</text><text class="chart-axis" x="372" y="225">W7</text><text class="chart-axis" x="700" y="225">W13</text></svg>';
    $("cash-table").querySelector("tbody").innerHTML = rows.map(function (row) { return '<tr><td><strong>' + row.week + '</strong></td><td>' + U.money(row.revenue) + '</td><td>' + U.money(row.ending) + '</td><td>' + row.age + '</td></tr>'; }).join("");
  }

  function render() {
    var v = values();
    $("forecast-revenue").textContent = U.money(v.revenue);
    $("forecast-margin").textContent = U.percent(v.margin);
    $("forecast-cash").textContent = U.money(v.cash);
    $("forecast-ar").textContent = U.money(v.ar);
    $("forecast-buffer").textContent = U.money(v.buffer);
    $("assumption-note").textContent = "Cash path recalculated: demand " + (state.demand >= 0 ? "+" : "") + state.demand + "%, price " + (state.price >= 0 ? "+" : "") + state.price + "%, direct cost " + (state.cost >= 0 ? "+" : "") + state.cost + "%, payroll " + (state.payroll >= 0 ? "+" : "") + state.payroll + "%, collection delay " + state.collections + " days.";
    renderChart(v.weekly);

    var bridge = [
      { label: "Revenue", value: v.revenue, width: 100, state: "good" },
      { label: "Direct cost", value: -v.direct, width: (v.direct / v.revenue) * 100, state: "warn" },
      { label: "Payroll", value: -v.payroll, width: Math.min(100, (v.payroll / v.revenue) * 240), state: "warn" },
      { label: "Gross profit", value: v.revenue - v.direct, width: v.margin, state: "good" }
    ];
    $("margin-bridge").innerHTML = bridge.map(function (row) { return '<div class="metric-row ' + row.state + '"><span>' + row.label + '</span><span class="metric-bar"><span style="width:' + row.width + '%"></span></span><strong>' + (row.value < 0 ? "−" : "") + U.money(Math.abs(row.value)) + '</strong></div>'; }).join("");

    var aging = [
      { label: "Current", value: Math.max(0, 61000 - state.collections * 400), pct: 48 },
      { label: "1–30 days", value: 33000 + state.collections * 300, pct: 27 },
      { label: "31–60 days", value: 18000 + state.collections * 450, pct: 16 },
      { label: "60+ days", value: 9000 + state.collections * 470, pct: 9 }
    ];
    $("aging-list").innerHTML = aging.map(function (row) { return '<div class="metric-row ' + (row.label === "60+ days" ? "warn" : "") + '"><span>' + row.label + '</span><span class="metric-bar"><span style="width:' + row.pct + '%"></span></span><strong>' + U.money(row.value) + '</strong></div>'; }).join("");

    var invoices = [["INV-1042", "Mid-market", 18600, 12], ["INV-1037", "Enterprise", 24200, 38], ["INV-1029", "SMB", 6800, state.collections + 21]];
    $("invoice-rows").innerHTML = invoices.map(function (row) { return '<tr><td><strong>' + row[0] + '</strong></td><td>' + row[1] + '</td><td>' + U.money(row[2]) + '</td><td>' + row[3] + ' days</td></tr>'; }).join("");

    var alerts = [];
    if (v.margin < 58) alerts.push(["Margin below planning guardrail", "Direct cost assumptions reduce gross margin to " + U.percent(v.margin) + ".", "Review price or delivery mix."]);
    if (state.collections > 30) alerts.push(["Collections delay is material", "AR risk is modeled at " + U.money(v.ar) + ".", "Prioritize the oldest invoices."]);
    if (v.buffer < 100000) alerts.push(["Operating buffer is thin", "Week 13 buffer is " + U.money(v.buffer) + ".", "Revisit timing assumptions."]);
    if (!alerts.length) alerts.push(["No threshold breach", "The selected assumptions remain inside the illustrative guardrails.", "Continue review with an owner."]);
    $("forecast-alerts").innerHTML = alerts.map(function (row, i) { return '<li class="action-row-item"><span class="severity ' + (i ? "medium" : "low") + '">' + (i ? "Watch" : "Note") + '</span><div><strong>' + row[0] + '</strong><small>' + row[1] + '<br><b>Next:</b> ' + row[2] + '</small></div></li>'; }).join("");
  }

  document.querySelectorAll("[data-field]").forEach(function (node) {
    node.addEventListener("input", function (event) {
      var field = event.target.dataset.field;
      state[field] = Number(event.target.value);
      input(field, state[field]);
      render();
    });
  });
  $("forecast-preset").addEventListener("change", function (event) {
    state = Object.assign({}, presets[event.target.value]);
    fields.forEach(function (field) { input(field, state[field]); });
    render();
  });
  $("copy-forecast").addEventListener("click", function () { var v = values(); U.copy("Synthetic forecast brief: projected revenue " + U.money(v.revenue) + ", gross margin " + U.percent(v.margin) + ", ending cash " + U.money(v.cash) + ", AR risk " + U.money(v.ar) + ". Assumptions are local and illustrative.", $("forecast-copy-status")); });
  $("export-csv").addEventListener("click", function () { var v = values(); U.download("eliora-forecast.csv", U.csv([["Week", "Revenue", "Ending cash", "Collection note"]].concat(v.weekly.map(function (row) { return [row.week, row.revenue.toFixed(2), row.ending.toFixed(2), row.age]; }))), "text/csv"); });
  $("export-json").addEventListener("click", function () { U.download("eliora-forecast.json", JSON.stringify({ assumptions: state, forecast: values() }, null, 2), "application/json"); });

  var dialog = $("methodology-dialog");
  $("open-methodology").addEventListener("click", function (event) { U.openDialog(dialog, event.currentTarget); });
  dialog.querySelector("[data-dialog-close]").addEventListener("click", function () { U.closeDialog(dialog); });
  dialog.addEventListener("click", function (event) { if (event.target === dialog) U.closeDialog(dialog); });
  render();
}());
