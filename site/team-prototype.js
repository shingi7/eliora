const dataUrl = "./data/team_comparison_features.json";

const identityCols = new Set(["year", "team"]);
let metricOptions = [];
let zMetricOptions = [];

const defaultMetrics = [
  "points",
  "composite_team_score",
  "total_score",
  "xg_diff",
  "attacking_score_6"
];

const tableColumns = [
  { key: "year", label: "Season", type: "int" },
  { key: "team", label: "Team", type: "text" },
  { key: "points", label: "Points", type: "num" },
  { key: "standarised_points_score", label: "Std Points Score", type: "num" },
  { key: "position", label: "Position", type: "num" },
  { key: "adjusted_position_z_score", label: "Adj Position Z", type: "num" },
  { key: "composite_team_score", label: "Composite Score", type: "num" },
  { key: "total_score", label: "Total Score", type: "num" },
  { key: "attacking_score_6", label: "Attacking", type: "num" },
  { key: "defensive_score_8", label: "Defensive", type: "num" },
  { key: "ball_progression_6", label: "Ball Progression", type: "num" },
  { key: "xg_diff", label: "xG Diff", type: "num" },
  { key: "possesion_threat", label: "Possession Threat", type: "num" },
  { key: "goals", label: "Goals", type: "num" },
  { key: "conceded_goals", label: "Conceded", type: "num" },
  { key: "xg", label: "xG", type: "num" },
  { key: "shots_on_target", label: "Shots on Target", type: "num" },
  { key: "possession_pct", label: "Possession %", type: "num" },
  { key: "passes_accurate", label: "Passes Accurate", type: "num" }
];

let rawData = [];
let filteredData = [];
let rowById = new Map();
let tableColumnsAvailable = [];

function toNumber(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function rowId(row) {
  return `${row.year}|${row.team}`;
}

function rowLabel(row) {
  return `${row.team} — ${row.year}`;
}

function prettyMetricLabel(metric) {
  return metric.replace(/_/g, " ");
}

function initializeMetricOptions() {
  if (rawData.length === 0) {
    metricOptions = [];
    zMetricOptions = [];
    return;
  }
  const sampleKeys = Object.keys(rawData[0]);
  metricOptions = sampleKeys.filter(
    key => !key.endsWith("_z") && !identityCols.has(key)
  );
  metricOptions = metricOptions.filter(key =>
    rawData.some(row => Number.isFinite(row[key]))
  );
  metricOptions.sort();
  zMetricOptions = metricOptions
    .map(metric => `${metric}_z`)
    .filter(metric => sampleKeys.includes(metric));
}

function getDefaultMetricSelection() {
  const selected = defaultMetrics.filter(metric => metricOptions.includes(metric));
  if (selected.length > 0) {
    return selected;
  }
  return metricOptions.slice(0, Math.min(5, metricOptions.length));
}

function getSelectedValues(selectEl) {
  return Array.from(selectEl.selectedOptions).map(option => option.value);
}

function setSelectedValues(selectEl, values) {
  Array.from(selectEl.options).forEach(option => {
    option.selected = values.includes(option.value);
  });
}

function buildMultiSelectOptions(selectEl, values, includeAllLabel, defaultSelected) {
  selectEl.innerHTML = "";
  if (includeAllLabel) {
    const allOption = document.createElement("option");
    allOption.value = "all";
    allOption.textContent = includeAllLabel;
    selectEl.appendChild(allOption);
  }
  values.forEach(value => {
    const option = document.createElement("option");
    option.value = String(value);
    option.textContent = String(value);
    selectEl.appendChild(option);
  });
  if (defaultSelected && defaultSelected.length > 0) {
    setSelectedValues(selectEl, defaultSelected.map(String));
  }
}

function buildYearOptions(yearSelect) {
  const years = Array.from(new Set(rawData.map(row => row.year))).sort((a, b) => a - b);
  buildMultiSelectOptions(yearSelect, years, "All seasons");
  if (years.length > 0) {
    yearSelect.value = String(years[years.length - 1]);
  }
}

function buildMetricOptions(metricSelect) {
  metricSelect.innerHTML = "";
  metricOptions.forEach(metric => {
    const option = document.createElement("option");
    option.value = metric;
    option.textContent = metric;
    metricSelect.appendChild(option);
  });
  setSelectedValues(metricSelect, getDefaultMetricSelection());
}

function getFilteredData(yearSelect, pointsInput) {
  const yearValue = yearSelect.value;
  const minPoints = toNumber(pointsInput.value) || 0;
  return rawData.filter(row => {
    const yearOk = yearValue === "all" || row.year === Number(yearValue);
    const pointsOk = row.points >= minPoints;
    return yearOk && pointsOk;
  });
}

function updateTeamOptions(teamSelect) {
  const previous = getSelectedValues(teamSelect);
  teamSelect.innerHTML = "";

  const sorted = [...filteredData].sort((a, b) => (b.points || -Infinity) - (a.points || -Infinity));
  sorted.forEach(row => {
    const option = document.createElement("option");
    const id = rowId(row);
    option.value = id;
    option.textContent = rowLabel(row);
    teamSelect.appendChild(option);
  });

  const availableIds = new Set(sorted.map(row => rowId(row)));
  const stillSelected = previous.filter(id => availableIds.has(id));
  if (stillSelected.length > 0) {
    setSelectedValues(teamSelect, stillSelected);
  } else if (sorted.length > 0) {
    setSelectedValues(teamSelect, [rowId(sorted[0]), rowId(sorted[1])].filter(Boolean));
  }
}

function updateTargetOptions(targetSelect) {
  const previous = targetSelect.value;
  targetSelect.innerHTML = "";
  filteredData.forEach(row => {
    const option = document.createElement("option");
    const id = rowId(row);
    option.value = id;
    option.textContent = rowLabel(row);
    targetSelect.appendChild(option);
  });
  const available = Array.from(targetSelect.options).map(option => option.value);
  if (available.includes(previous)) {
    targetSelect.value = previous;
  } else if (available.length > 0) {
    targetSelect.value = available[0];
  }
}

function getRadarValue(row, metric, radarModeSelect) {
  if (radarModeSelect.value === "z") {
    return row[`${metric}_z`];
  }
  return row[metric];
}

function updateRadar(teamSelect, metricSelect, radarModeSelect, radarStatus) {
  const selectedTeams = getSelectedValues(teamSelect);
  const selectedMetrics = getSelectedValues(metricSelect);
  radarStatus.textContent = "";

  if (selectedTeams.length === 0 || selectedMetrics.length === 0) {
    Plotly.purge("radar");
    radarStatus.textContent = "Select at least one team and one metric.";
    return;
  }

  const traces = [];
  selectedTeams.forEach(id => {
    const row = rowById.get(id);
    if (!row) return;
    const values = selectedMetrics.map(metric => getRadarValue(row, metric, radarModeSelect));
    if (values.some(value => value === null || value === undefined)) {
      return;
    }
    traces.push({
      type: "scatterpolar",
      r: values,
      theta: selectedMetrics,
      name: rowLabel(row),
      fill: "toself"
    });
  });

  if (traces.length === 0) {
    Plotly.purge("radar");
    radarStatus.textContent = "No data available for the selected teams/metrics.";
    return;
  }

  Plotly.newPlot("radar", traces, {
    polar: { radialaxis: { visible: true } },
    showlegend: true,
    margin: { t: 30, b: 30, l: 30, r: 30 }
  }, { displayModeBar: false });
}

function buildTopYearOptions(topYearSelect) {
  const years = Array.from(new Set(rawData.map(row => row.year))).sort((a, b) => a - b);
  buildMultiSelectOptions(topYearSelect, years, "All seasons", years.length > 0 ? [years[years.length - 1]] : []);
}

function buildTopMetricOptions(topMetricSelect) {
  topMetricSelect.innerHTML = "";
  metricOptions.forEach(metric => {
    const option = document.createElement("option");
    option.value = metric;
    option.textContent = metric;
    topMetricSelect.appendChild(option);
  });
  topMetricSelect.value = metricOptions.includes("points")
    ? "points"
    : metricOptions[0] || "";
}

function buildBubbleAxisOptions(selectEl, defaultMetric) {
  selectEl.innerHTML = "";
  metricOptions.forEach(metric => {
    const option = document.createElement("option");
    option.value = metric;
    option.textContent = metric;
    selectEl.appendChild(option);
  });
  selectEl.value = metricOptions.includes(defaultMetric)
    ? defaultMetric
    : metricOptions[0] || "";
}

function buildBubbleMetricOptions(bubbleMetricSelect) {
  bubbleMetricSelect.innerHTML = "";
  metricOptions.forEach(metric => {
    const option = document.createElement("option");
    option.value = metric;
    option.textContent = metric;
    bubbleMetricSelect.appendChild(option);
  });
  bubbleMetricSelect.multiple = true;
  bubbleMetricSelect.size = 6;
  setSelectedValues(bubbleMetricSelect, getDefaultMetricSelection());
}

function getTopTeamsData(topYearSelect, pointsInput) {
  const selected = getSelectedValues(topYearSelect);
  const includeAll = selected.includes("all");
  const years = includeAll ? null : selected.map(Number);
  const minPoints = toNumber(pointsInput.value) || 0;
  return rawData.filter(row => {
    const yearOk = includeAll || (years && years.includes(row.year));
    const pointsOk = row.points >= minPoints;
    return yearOk && pointsOk;
  });
}

function buildTopTeams(topYearSelect, topMetricSelect, topNInput, topStatus, pointsInput) {
  const selectedMetric = topMetricSelect.value;
  const topN = Math.max(1, Math.min(50, parseInt(topNInput.value || "10", 10)));

  topStatus.textContent = "";
  if (!selectedMetric) {
    Plotly.purge("topTeamsChart");
    topStatus.textContent = "Select a metric.";
    return;
  }

  const topFilteredData = getTopTeamsData(topYearSelect, pointsInput);
  const teams = [...topFilteredData]
    .filter(row => Number.isFinite(row[selectedMetric]))
    .sort((a, b) => b[selectedMetric] - a[selectedMetric])
    .slice(0, topN);

  if (teams.length === 0) {
    Plotly.purge("topTeamsChart");
    topStatus.textContent = "No data available for the selected filters.";
    return;
  }

  const labels = teams.map(row => rowLabel(row));
  const values = teams.map(row => row[selectedMetric]);
  const trace = {
    type: "bar",
    orientation: "v",
    name: selectedMetric,
    x: teams.map(row => row.team),
    y: values,
    hovertext: labels,
    hovertemplate: "%{hovertext}<br>" + selectedMetric + ": %{y:.3f}<extra></extra>"
  };

  Plotly.newPlot("topTeamsChart", [trace], {
    margin: { t: 30, b: 160, l: 50, r: 20 },
    xaxis: { tickangle: -30, automargin: true, tickfont: { size: 10 } },
    yaxis: { title: selectedMetric, automargin: true },
    showlegend: false
  }, { displayModeBar: false });
}

function buildBubbleChart(bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, pointsInput, bubbleStatus) {
  const selectedMetrics = getSelectedValues(bubbleCompositeSelect);
  bubbleStatus.textContent = "";

  if (selectedMetrics.length === 0) {
    Plotly.purge("bubbleChart");
    bubbleStatus.textContent = "Select at least one composite metric.";
    return;
  }

  const selectedYears = getSelectedValues(bubbleYearSelect);
  if (selectedYears.length === 0) {
    Plotly.purge("bubbleChart");
    bubbleStatus.textContent = "Select at least one season.";
    return;
  }
  const includeAll = selectedYears.includes("all");
  const years = includeAll ? null : selectedYears.map(Number);
  const minPoints = toNumber(pointsInput.value) || 0;
  const xMetric = bubbleXSelect.value;
  const yMetric = bubbleYSelect.value;

  if (!xMetric || !yMetric) {
    Plotly.purge("bubbleChart");
    bubbleStatus.textContent = "Select both x-axis and y-axis metrics.";
    return;
  }

  const rows = rawData.filter(row => {
    const yearOk = includeAll || (years && years.includes(row.year));
    const pointsOk = row.points >= minPoints;
    return yearOk && pointsOk;
  });

  if (rows.length === 0) {
    Plotly.purge("bubbleChart");
    bubbleStatus.textContent = "No data available for the selected filters.";
    return;
  }

  const points = [];
  rows.forEach(row => {
    const zVals = [];
    for (const metric of selectedMetrics) {
      const zVal = row[`${metric}_z`];
      if (!Number.isFinite(zVal)) {
        return;
      }
      zVals.push(zVal);
    }
    const xVal = row[xMetric];
    const yVal = row[yMetric];
    if (!Number.isFinite(xVal) || !Number.isFinite(yVal)) {
      return;
    }
    const compositeZ = zVals.reduce((sum, value) => sum + value, 0) / zVals.length;
    points.push({
      row,
      compositeZ,
      xVal,
      yVal
    });
  });

  if (points.length === 0) {
    Plotly.purge("bubbleChart");
    bubbleStatus.textContent = "No rows with complete data for the selected metrics.";
    return;
  }

  const compositeValues = points.map(point => point.compositeZ);
  const compositeMin = Math.min(...compositeValues);
  const compositeMax = Math.max(...compositeValues);
  const sizeFor = value => {
    if (compositeMax === compositeMin) {
      return 14;
    }
    const ratio = (value - compositeMin) / (compositeMax - compositeMin);
    return 8 + ratio * 18;
  };

  const labelMode = bubbleLabelSelect.value;
  const labelSet = new Set();
  if (labelMode === "top10") {
    points
      .slice()
      .sort((a, b) => b.compositeZ - a.compositeZ)
      .slice(0, 10)
      .forEach(point => labelSet.add(rowId(point.row)));
  }

  const pointsByYear = new Map();
  points.forEach(point => {
    const yearKey = String(point.row.year);
    if (!pointsByYear.has(yearKey)) {
      pointsByYear.set(yearKey, []);
    }
    pointsByYear.get(yearKey).push(point);
  });

  const traces = [];
  Array.from(pointsByYear.keys()).sort().forEach(yearKey => {
    const yearPoints = pointsByYear.get(yearKey);
    const customdata = yearPoints.map(point => [
      point.row.team,
      point.row.year,
      point.row.points,
      point.xVal,
      point.yVal,
      point.compositeZ
    ]);
    traces.push({
      type: "scatter",
      mode: "markers",
      name: yearKey,
      x: yearPoints.map(point => point.xVal),
      y: yearPoints.map(point => point.yVal),
      customdata,
      marker: {
        size: yearPoints.map(point => sizeFor(point.compositeZ)),
        sizemode: "area",
        opacity: 0.7
      },
      hovertemplate:
        "Team: %{customdata[0]}<br>" +
        "Season: %{customdata[1]}<br>" +
        "Points: %{customdata[2]}<br>" +
        `${prettyMetricLabel(xMetric)}: %{customdata[3]:.3f}<br>` +
        `${prettyMetricLabel(yMetric)}: %{customdata[4]:.3f}<br>` +
        "Composite (avg z): %{customdata[5]:.3f}<extra></extra>"
    });
  });

  const labeledPoints = points.filter(point => labelSet.has(rowId(point.row)));
  if (labeledPoints.length > 0) {
    traces.push({
      type: "scatter",
      mode: "text",
      name: "Top 10",
      x: labeledPoints.map(point => point.xVal),
      y: labeledPoints.map(point => point.yVal),
      text: labeledPoints.map(point => point.row.team),
      textposition: "top center",
      textfont: { size: 10 },
      showlegend: false,
      hoverinfo: "skip"
    });
  }

  const showLegend = pointsByYear.size > 1;

  Plotly.newPlot("bubbleChart", traces, {
    margin: { t: 30, b: 60, l: 60, r: 20 },
    xaxis: { title: prettyMetricLabel(xMetric) },
    yaxis: { title: prettyMetricLabel(yMetric) },
    showlegend: showLegend,
    legend: { orientation: "h" }
  }, { displayModeBar: false });
}

function distance(aRow, bRow) {
  let sum = 0;
  for (const col of zMetricOptions) {
    const a = aRow[col];
    const b = bRow[col];
    if (!Number.isFinite(a) || !Number.isFinite(b)) {
      return null;
    }
    sum += (a - b) * (a - b);
  }
  return Math.sqrt(sum);
}

function updateSimilarity(targetSelect, similarityStatus) {
  const targetId = targetSelect.value;
  const tbody = document.querySelector("#similarityTable tbody");
  tbody.innerHTML = "";
  similarityStatus.textContent = "";

  if (!targetId) {
    similarityStatus.textContent = "Select a target team.";
    return;
  }

  const targetRow = rowById.get(targetId);
  if (!targetRow) {
    similarityStatus.textContent = "Target team is not available in the filtered dataset.";
    return;
  }

  const candidates = [];
  filteredData.forEach(row => {
    if (rowId(row) === targetId) return;
    const dist = distance(row, targetRow);
    if (dist === null) return;
    candidates.push({ row, dist });
  });

  candidates.sort((a, b) => a.dist - b.dist);
  const topFive = candidates.slice(0, 5);

  if (topFive.length === 0) {
    similarityStatus.textContent = "No similar teams found with complete data.";
    return;
  }

  topFive.forEach(entry => {
    const row = entry.row;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.team}</td>
      <td>${row.year}</td>
      <td>${Number.isFinite(row.points) ? row.points.toFixed(0) : ""}</td>
      <td>${entry.dist.toFixed(3)}</td>
    `;
    tbody.appendChild(tr);
  });
}

function formatTableValue(row, column) {
  const value = row[column.key];
  if (value === null || value === undefined || value === "") {
    return "";
  }
  if (column.type === "text") {
    return String(value);
  }
  if (column.type === "int") {
    return Number.isFinite(value) ? String(Math.round(value)) : "";
  }
  return Number.isFinite(value) ? value.toFixed(3) : "";
}

function buildTableSortOptions(tableSortSelect) {
  tableSortSelect.innerHTML = "";
  const columns = tableColumnsAvailable.length > 0 ? tableColumnsAvailable : tableColumns;
  columns.forEach(col => {
    const option = document.createElement("option");
    option.value = col.key;
    option.textContent = col.label;
    tableSortSelect.appendChild(option);
  });
  if (columns.some(col => col.key === "points")) {
    tableSortSelect.value = "points";
  } else {
    tableSortSelect.value = columns[0]?.key || "";
  }
}

function getTableFilteredData(tableYearSelect, tableTeamSearch, tablePointsInput) {
  const selectedYears = getSelectedValues(tableYearSelect);
  const includeAllYears = selectedYears.length === 0 || selectedYears.includes("all");
  const years = includeAllYears ? null : selectedYears.map(Number);

  const search = tableTeamSearch.value.trim().toLowerCase();
  const minPoints = toNumber(tablePointsInput.value) || 0;

  return rawData.filter(row => {
    const yearOk = includeAllYears || (years && years.includes(row.year));
    const teamOk = search.length === 0 || (row.team || "").toLowerCase().includes(search);
    const pointsOk = row.points >= minPoints;
    return yearOk && teamOk && pointsOk;
  });
}

function buildTeamTable(tableYearSelect, tableTeamSearch, tablePointsInput, tableRowsSelect, tableSortSelect, tableSortDirSelect, tableStatus) {
  const rows = getTableFilteredData(tableYearSelect, tableTeamSearch, tablePointsInput);
  const sortKey = tableSortSelect.value;
  const sortDir = tableSortDirSelect.value;
  const columns = tableColumnsAvailable.length > 0 ? tableColumnsAvailable : tableColumns;
  const sortColumn = columns.find(col => col.key === sortKey) || columns[0];

  rows.sort((a, b) => {
    const aVal = a[sortKey];
    const bVal = b[sortKey];
    if (sortColumn.type === "text") {
      const aStr = (aVal || "").toString();
      const bStr = (bVal || "").toString();
      return sortDir === "asc" ? aStr.localeCompare(bStr) : bStr.localeCompare(aStr);
    }
    const aNum = Number.isFinite(aVal) ? aVal : -Infinity;
    const bNum = Number.isFinite(bVal) ? bVal : -Infinity;
    return sortDir === "asc" ? aNum - bNum : bNum - aNum;
  });

  const limitValue = tableRowsSelect.value;
  const limit = limitValue === "all" ? rows.length : Math.max(1, parseInt(limitValue, 10));
  const displayRows = rows.slice(0, limit);

  const tbody = document.querySelector("#teamTable tbody");
  tbody.innerHTML = displayRows.map(row => {
    const cells = columns.map(col => `<td>${formatTableValue(row, col)}</td>`).join("");
    return `<tr>${cells}</tr>`;
  }).join("");

  tableStatus.textContent = `Showing ${displayRows.length} of ${rows.length} rows`;
}

function updateAll(yearSelect, pointsInput, teamSelect, metricSelect, radarModeSelect, targetSelect, radarStatus, similarityStatus, topYearSelect, topMetricSelect, topNInput, topStatus, bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, bubbleStatus) {
  filteredData = getFilteredData(yearSelect, pointsInput);
  rowById = new Map(filteredData.map(row => [rowId(row), row]));
  updateTeamOptions(teamSelect);
  updateTargetOptions(targetSelect);
  updateRadar(teamSelect, metricSelect, radarModeSelect, radarStatus);
  updateSimilarity(targetSelect, similarityStatus);

  buildTopTeams(topYearSelect, topMetricSelect, topNInput, topStatus, pointsInput);
  buildBubbleChart(bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, pointsInput, bubbleStatus);
}

function setStatus(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle("error", isError);
}

async function init() {
  const yearSelect = document.getElementById("yearSelect");
  const pointsInput = document.getElementById("pointsInput");
  const teamSelect = document.getElementById("teamSelect");
  const metricSelect = document.getElementById("metricSelect");
  const radarModeSelect = document.getElementById("radarModeSelect");
  const targetSelect = document.getElementById("targetSelect");
  const radarStatus = document.getElementById("radarStatus");
  const similarityStatus = document.getElementById("similarityStatus");
  const dataStatus = document.getElementById("dataStatus");
  const dataDebug = document.getElementById("dataDebug");
  const topYearSelect = document.getElementById("topYearSelect");
  const topMetricSelect = document.getElementById("topMetricSelect");
  const topNInput = document.getElementById("topNInput");
  const topStatus = document.getElementById("topTeamsStatus");
  const bubbleYearSelect = document.getElementById("bubbleYearSelect");
  const bubbleXSelect = document.getElementById("bubbleXMetricSelect");
  const bubbleYSelect = document.getElementById("bubbleYMetricSelect");
  const bubbleCompositeSelect = document.getElementById("bubbleCompositeSelect");
  const bubbleLabelSelect = document.getElementById("bubbleLabelSelect");
  const bubbleStatus = document.getElementById("bubbleStatus");
  const tableYearSelect = document.getElementById("tableYearSelect");
  const tableTeamSearch = document.getElementById("tableTeamSearch");
  const tablePointsInput = document.getElementById("tablePointsInput");
  const tableRowsSelect = document.getElementById("tableRowsSelect");
  const tableSortSelect = document.getElementById("tableSortSelect");
  const tableSortDirSelect = document.getElementById("tableSortDirSelect");
  const tableStatus = document.getElementById("tableStatus");

  const pageUrl = window.location.href;
  const pageOrigin = window.location.origin;
  const pagePathname = window.location.pathname;
  dataDebug.innerHTML = [
    `Page URL: ${pageUrl}`,
    `Origin: ${pageOrigin}`,
    `Pathname: ${pagePathname}`,
    `Data URL: ${dataUrl}`
  ].join("<br>");
  setStatus(dataStatus, "Loading data...");

  if (window.location.protocol === "file:") {
    setStatus(dataStatus, "This page appears to be opened from local disk (file://). Fetch will fail there. Use GitHub Pages or a local HTTP server.", true);
  }

  try {
    const response = await fetch(dataUrl);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} ${response.statusText}`);
    }
    rawData = await response.json();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (window.location.protocol === "file:") {
      setStatus(dataStatus, "This page appears to be opened from local disk (file://). Fetch will fail there. Use GitHub Pages or a local HTTP server.", true);
    } else {
      setStatus(dataStatus, `Error loading data (${message}). Check that the JSON file is available.`, true);
    }
    return;
  }

  rawData.forEach(row => {
    row.year = toNumber(row.year);
  });

  initializeMetricOptions();
  tableColumnsAvailable = tableColumns.filter(col => Object.prototype.hasOwnProperty.call(rawData[0] || {}, col.key));

  rawData.forEach(row => {
    metricOptions.forEach(metric => {
      row[metric] = toNumber(row[metric]);
    });
    zMetricOptions.forEach(metric => {
      row[metric] = toNumber(row[metric]);
    });
  });

  buildYearOptions(yearSelect);
  buildMetricOptions(metricSelect);
  buildTopYearOptions(topYearSelect);
  buildTopMetricOptions(topMetricSelect);
  buildTopYearOptions(bubbleYearSelect);
  buildBubbleAxisOptions(bubbleXSelect, "points");
  buildBubbleAxisOptions(bubbleYSelect, "composite_team_score");
  buildBubbleMetricOptions(bubbleCompositeSelect);
  bubbleLabelSelect.value = "top10";
  buildMultiSelectOptions(tableYearSelect, Array.from(new Set(rawData.map(row => row.year))).sort((a, b) => a - b), "All seasons", [Math.max(...rawData.map(row => row.year))]);
  buildTableSortOptions(tableSortSelect);

  setStatus(dataStatus, "Data loaded.");
  setTimeout(() => {
    setStatus(dataStatus, "");
  }, 1500);

  yearSelect.addEventListener("change", () =>
    updateAll(yearSelect, pointsInput, teamSelect, metricSelect, radarModeSelect, targetSelect, radarStatus, similarityStatus, topYearSelect, topMetricSelect, topNInput, topStatus, bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, bubbleStatus)
  );
  pointsInput.addEventListener("change", () =>
    updateAll(yearSelect, pointsInput, teamSelect, metricSelect, radarModeSelect, targetSelect, radarStatus, similarityStatus, topYearSelect, topMetricSelect, topNInput, topStatus, bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, bubbleStatus)
  );
  teamSelect.addEventListener("change", () =>
    updateRadar(teamSelect, metricSelect, radarModeSelect, radarStatus)
  );
  metricSelect.addEventListener("change", () =>
    updateRadar(teamSelect, metricSelect, radarModeSelect, radarStatus)
  );
  radarModeSelect.addEventListener("change", () =>
    updateRadar(teamSelect, metricSelect, radarModeSelect, radarStatus)
  );
  targetSelect.addEventListener("change", () =>
    updateSimilarity(targetSelect, similarityStatus)
  );

  topYearSelect.addEventListener("change", () =>
    buildTopTeams(topYearSelect, topMetricSelect, topNInput, topStatus, pointsInput)
  );
  topMetricSelect.addEventListener("change", () =>
    buildTopTeams(topYearSelect, topMetricSelect, topNInput, topStatus, pointsInput)
  );
  topNInput.addEventListener("change", () =>
    buildTopTeams(topYearSelect, topMetricSelect, topNInput, topStatus, pointsInput)
  );

  bubbleYearSelect.addEventListener("change", () =>
    buildBubbleChart(bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, pointsInput, bubbleStatus)
  );
  bubbleXSelect.addEventListener("change", () =>
    buildBubbleChart(bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, pointsInput, bubbleStatus)
  );
  bubbleYSelect.addEventListener("change", () =>
    buildBubbleChart(bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, pointsInput, bubbleStatus)
  );
  bubbleCompositeSelect.addEventListener("change", () =>
    buildBubbleChart(bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, pointsInput, bubbleStatus)
  );
  bubbleLabelSelect.addEventListener("change", () =>
    buildBubbleChart(bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, pointsInput, bubbleStatus)
  );

  const updateTable = () =>
    buildTeamTable(tableYearSelect, tableTeamSearch, tablePointsInput, tableRowsSelect, tableSortSelect, tableSortDirSelect, tableStatus);

  tableYearSelect.addEventListener("change", updateTable);
  tableTeamSearch.addEventListener("input", updateTable);
  tablePointsInput.addEventListener("change", updateTable);
  tableRowsSelect.addEventListener("change", updateTable);
  tableSortSelect.addEventListener("change", updateTable);
  tableSortDirSelect.addEventListener("change", updateTable);

  updateAll(yearSelect, pointsInput, teamSelect, metricSelect, radarModeSelect, targetSelect, radarStatus, similarityStatus, topYearSelect, topMetricSelect, topNInput, topStatus, bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, bubbleStatus);
  updateTable();
}

document.addEventListener("DOMContentLoaded", init);
