const dataUrl = "./data/player_st_comparison_features.json";

const metricOptions = [
  "overall_percentile",
  "goal_threat_percentile",
  "link_play_percentile",
  "non_pkxg_p90",
  "non_penalty_goals_p90",
  "shots_per_90",
  "shots_on_target_pct",
  "offensive_duels_won_pct",
  "touches_in_box_per_90",
  "key_passes_per_90",
  "xa_per_90",
  "xg",
  "non_pkxg",
  "goal_conversion_pct",
  "offensive_duels_per_90",
  "passes_to_penalty_area_per_90",
  "accurate_passes_to_penalty_area_pct",
  "penalties_taken",
  "possession",
  "shooting_impact",
  "penalty_box_passes_impact"
];

const zMetricOptions = [
  "overall_percentile_z",
  "goal_threat_percentile_z",
  "link_play_percentile_z",
  "non_pkxg_p90_z",
  "non_penalty_goals_p90_z",
  "shots_per_90_z",
  "shots_on_target_pct_z",
  "offensive_duels_won_pct_z",
  "touches_in_box_per_90_z",
  "key_passes_per_90_z",
  "xa_per_90_z"
];

const defaultMetrics = [
  "overall_percentile",
  "goal_threat_percentile",
  "link_play_percentile",
  "non_pkxg_p90",
  "shots_per_90"
];

const tableColumns = [
  { key: "season", label: "Season", type: "int" },
  { key: "player", label: "Player", type: "text" },
  { key: "team", label: "Team", type: "text" },
  { key: "minutes_played", label: "Minutes", type: "int" },
  { key: "overall_percentile", label: "Overall %", type: "num" },
  { key: "goal_threat_percentile", label: "Goal Threat %", type: "num" },
  { key: "link_play_percentile", label: "Link Play %", type: "num" },
  { key: "non_pkxg_p90", label: "Non PKxG P90", type: "num" },
  { key: "non_penalty_goals_p90", label: "Non-pen goals P90", type: "num" },
  { key: "shots_per_90", label: "Shots P90", type: "num" },
  { key: "shots_on_target_pct", label: "Shots on target %", type: "num" },
  { key: "offensive_duels_won_pct", label: "Offensive duels won %", type: "num" },
  { key: "touches_in_box_per_90", label: "Touches in box P90", type: "num" },
  { key: "key_passes_per_90", label: "Key passes P90", type: "num" },
  { key: "xa_per_90", label: "xA P90", type: "num" }
];

let rawData = [];
let filteredData = [];
let rowById = new Map();

function toNumber(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function rowId(row) {
  return `${row.season}|${row.player}|${row.team}`;
}

function rowLabel(row) {
  return `${row.player} — ${row.team} — ${row.season}`;
}

function prettyMetricLabel(metric) {
  return metric.replace(/_/g, " ");
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

function buildSeasonOptions(seasonSelect) {
  const seasons = Array.from(new Set(rawData.map(row => row.season))).sort((a, b) => a - b);
  buildMultiSelectOptions(seasonSelect, seasons, "All seasons");
  if (seasons.length > 0) {
    seasonSelect.value = String(seasons[seasons.length - 1]);
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
  setSelectedValues(metricSelect, defaultMetrics);
}

function getRadarValue(row, metric, radarModeSelect) {
  if (radarModeSelect.value === "z") {
    return row[`${metric}_z`];
  }
  return row[metric];
}

function getFilteredData(seasonSelect, minutesInput) {
  const seasonValue = seasonSelect.value;
  const minMinutes = toNumber(minutesInput.value) || 0;
  return rawData.filter(row => {
    const seasonOk = seasonValue === "all" || row.season === Number(seasonValue);
    const minutesOk = row.minutes_played >= minMinutes;
    return seasonOk && minutesOk;
  });
}

function updatePlayerOptions(playerSelect) {
  const previous = getSelectedValues(playerSelect);
  playerSelect.innerHTML = "";

  const sorted = [...filteredData].sort((a, b) => (b.overall_percentile || -Infinity) - (a.overall_percentile || -Infinity));
  sorted.forEach(row => {
    const option = document.createElement("option");
    const id = rowId(row);
    option.value = id;
    option.textContent = rowLabel(row);
    playerSelect.appendChild(option);
  });

  const availableIds = new Set(sorted.map(row => rowId(row)));
  const stillSelected = previous.filter(id => availableIds.has(id));
  if (stillSelected.length > 0) {
    setSelectedValues(playerSelect, stillSelected);
  } else if (sorted.length > 0) {
    setSelectedValues(playerSelect, [rowId(sorted[0]), rowId(sorted[1])].filter(Boolean));
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

function updateRadar(playerSelect, metricSelect, radarModeSelect, radarStatus) {
  const selectedPlayers = getSelectedValues(playerSelect);
  const selectedMetrics = getSelectedValues(metricSelect);
  radarStatus.textContent = "";

  if (selectedPlayers.length === 0 || selectedMetrics.length === 0) {
    Plotly.purge("radar");
    radarStatus.textContent = "Select at least one player and one metric.";
    return;
  }

  const traces = [];
  selectedPlayers.forEach(id => {
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
    radarStatus.textContent = "No data available for the selected players/metrics.";
    return;
  }

  Plotly.newPlot("radar", traces, {
    polar: { radialaxis: { visible: true } },
    showlegend: true,
    margin: { t: 30, b: 30, l: 30, r: 30 }
  }, { displayModeBar: false });
}

function buildTopSeasonOptions(topSeasonSelect) {
  const seasons = Array.from(new Set(rawData.map(row => row.season))).sort((a, b) => a - b);
  buildMultiSelectOptions(topSeasonSelect, seasons, "All seasons", seasons.length > 0 ? [seasons[seasons.length - 1]] : []);
}

function buildTopMetricOptions(topMetricSelect) {
  topMetricSelect.innerHTML = "";
  metricOptions.forEach(metric => {
    const option = document.createElement("option");
    option.value = metric;
    option.textContent = metric;
    topMetricSelect.appendChild(option);
  });
  topMetricSelect.value = "overall_percentile";
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
  setSelectedValues(bubbleMetricSelect, defaultMetrics);
}

function buildBubbleAxisOptions(selectEl, defaultMetric) {
  selectEl.innerHTML = "";
  metricOptions.forEach(metric => {
    const option = document.createElement("option");
    option.value = metric;
    option.textContent = metric;
    selectEl.appendChild(option);
  });
  selectEl.value = defaultMetric;
}

function buildTeamOptions(tableTeamSelect) {
  const teams = Array.from(new Set(rawData.map(row => row.team))).sort((a, b) => a.localeCompare(b));
  buildMultiSelectOptions(tableTeamSelect, teams, "All teams", ["all"]);
}

function buildTableSeasonOptions(tableSeasonSelect) {
  const seasons = Array.from(new Set(rawData.map(row => row.season))).sort((a, b) => a - b);
  buildMultiSelectOptions(tableSeasonSelect, seasons, "All seasons", seasons.length > 0 ? [seasons[seasons.length - 1]] : []);
}

function buildTableSortOptions(tableSortSelect) {
  tableSortSelect.innerHTML = "";
  tableColumns.forEach(col => {
    const option = document.createElement("option");
    option.value = col.key;
    option.textContent = col.label;
    tableSortSelect.appendChild(option);
  });
  tableSortSelect.value = "overall_percentile";
}

function getTopPerformersData(topSeasonSelect, minutesInput) {
  const selected = getSelectedValues(topSeasonSelect);
  const includeAll = selected.includes("all");
  const seasons = includeAll ? null : selected.map(Number);
  const minMinutes = toNumber(minutesInput.value) || 0;
  return rawData.filter(row => {
    const seasonOk = includeAll || (seasons && seasons.includes(row.season));
    const minutesOk = row.minutes_played >= minMinutes;
    return seasonOk && minutesOk;
  });
}

function buildTopPerformers(topSeasonSelect, topMetricSelect, topNInput, topStatus, minutesInput) {
  const selectedMetric = topMetricSelect.value;
  const topN = Math.max(1, Math.min(50, parseInt(topNInput.value || "10", 10)));

  topStatus.textContent = "";
  if (!selectedMetric) {
    Plotly.purge("topPerformersChart");
    topStatus.textContent = "Select a category.";
    return;
  }

  const topFilteredData = getTopPerformersData(topSeasonSelect, minutesInput);
  const players = [...topFilteredData]
    .filter(row => Number.isFinite(row[selectedMetric]))
    .sort((a, b) => b[selectedMetric] - a[selectedMetric])
    .slice(0, topN);

  if (players.length === 0) {
    Plotly.purge("topPerformersChart");
    topStatus.textContent = "No data available for the selected filters.";
    return;
  }

  const yLabels = players.map(row => rowLabel(row));
  const values = players.map(row => row[selectedMetric]);
  const trace = {
    type: "bar",
    orientation: "v",
    name: selectedMetric,
    x: players.map(row => row.player),
    y: values,
    hovertext: yLabels,
    hovertemplate: "%{hovertext}<br>" + selectedMetric + ": %{y:.3f}<extra></extra>"
  };

  Plotly.newPlot("topPerformersChart", [trace], {
    margin: { t: 30, b: 160, l: 50, r: 20 },
    xaxis: { tickangle: -30, automargin: true, tickfont: { size: 10 } },
    yaxis: { title: selectedMetric, automargin: true },
    showlegend: false
  }, { displayModeBar: false });
}

function getTableFilteredData(tableSeasonSelect, tableTeamSelect, tablePlayerSearch, tableMinutesInput) {
  const selectedSeasons = getSelectedValues(tableSeasonSelect);
  const includeAllSeasons = selectedSeasons.length === 0 || selectedSeasons.includes("all");
  const seasons = includeAllSeasons ? null : selectedSeasons.map(Number);

  const selectedTeams = getSelectedValues(tableTeamSelect);
  const includeAllTeams = selectedTeams.length === 0 || selectedTeams.includes("all");
  const teams = includeAllTeams ? null : new Set(selectedTeams);

  const search = tablePlayerSearch.value.trim().toLowerCase();
  const minMinutes = toNumber(tableMinutesInput.value) || 0;

  return rawData.filter(row => {
    const seasonOk = includeAllSeasons || (seasons && seasons.includes(row.season));
    const teamOk = includeAllTeams || (teams && teams.has(row.team));
    const playerOk = search.length === 0 || (row.player || "").toLowerCase().includes(search);
    const minutesOk = row.minutes_played >= minMinutes;
    return seasonOk && teamOk && playerOk && minutesOk;
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

function buildPlayerTable(tableSeasonSelect, tableTeamSelect, tablePlayerSearch, tableMinutesInput, tableRowsSelect, tableSortSelect, tableSortDirSelect, tableStatus) {
  const rows = getTableFilteredData(tableSeasonSelect, tableTeamSelect, tablePlayerSearch, tableMinutesInput);
  const sortKey = tableSortSelect.value;
  const sortDir = tableSortDirSelect.value;
  const sortColumn = tableColumns.find(col => col.key === sortKey) || tableColumns[0];

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

  const tbody = document.querySelector("#playerTable tbody");
  tbody.innerHTML = displayRows.map(row => {
    const cells = tableColumns.map(col => `<td>${formatTableValue(row, col)}</td>`).join("");
    return `<tr>${cells}</tr>`;
  }).join("");

  tableStatus.textContent = `Showing ${displayRows.length} of ${rows.length} rows`;
}

function buildBubbleChart(bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, minutesInput, bubbleStatus) {
  const selectedMetrics = getSelectedValues(bubbleCompositeSelect);
  bubbleStatus.textContent = "";

  if (selectedMetrics.length === 0) {
    Plotly.purge("bubbleChart");
    bubbleStatus.textContent = "Select at least one composite category.";
    return;
  }

  const selectedSeasons = getSelectedValues(bubbleSeasonSelect);
  if (selectedSeasons.length === 0) {
    Plotly.purge("bubbleChart");
    bubbleStatus.textContent = "Select at least one season.";
    return;
  }
  const includeAll = selectedSeasons.includes("all");
  const seasons = includeAll ? null : selectedSeasons.map(Number);
  const minMinutes = toNumber(minutesInput.value) || 0;
  const xMetric = bubbleXSelect.value;
  const yMetric = bubbleYSelect.value;

  if (!xMetric || !yMetric) {
    Plotly.purge("bubbleChart");
    bubbleStatus.textContent = "Select both x-axis and y-axis metrics.";
    return;
  }

  const rows = rawData.filter(row => {
    const seasonOk = includeAll || (seasons && seasons.includes(row.season));
    const minutesOk = row.minutes_played >= minMinutes;
    return seasonOk && minutesOk;
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
    bubbleStatus.textContent = "No rows with complete data for the selected categories.";
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

  const pointsBySeason = new Map();
  points.forEach(point => {
    const seasonKey = String(point.row.season);
    if (!pointsBySeason.has(seasonKey)) {
      pointsBySeason.set(seasonKey, []);
    }
    pointsBySeason.get(seasonKey).push(point);
  });

  const traces = [];
  Array.from(pointsBySeason.keys()).sort().forEach(seasonKey => {
    const seasonPoints = pointsBySeason.get(seasonKey);
    const customdata = seasonPoints.map(point => [
      point.row.player,
      point.row.team,
      point.row.season,
      point.row.minutes_played,
      point.xVal,
      point.yVal,
      point.compositeZ
    ]);
    traces.push({
      type: "scatter",
      mode: "markers",
      name: seasonKey,
      x: seasonPoints.map(point => point.xVal),
      y: seasonPoints.map(point => point.yVal),
      customdata,
      marker: {
        size: seasonPoints.map(point => sizeFor(point.compositeZ)),
        sizemode: "area",
        opacity: 0.7
      },
      hovertemplate:
        "Player: %{customdata[0]}<br>" +
        "Team: %{customdata[1]}<br>" +
        "Season: %{customdata[2]}<br>" +
        "Minutes: %{customdata[3]}<br>" +
        `${prettyMetricLabel(xMetric)}: %{customdata[4]:.3f}<br>` +
        `${prettyMetricLabel(yMetric)}: %{customdata[5]:.3f}<br>` +
        "Composite (avg z): %{customdata[6]:.3f}<extra></extra>"
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
      text: labeledPoints.map(point => point.row.player),
      textposition: "top center",
      textfont: { size: 10 },
      showlegend: false,
      hoverinfo: "skip"
    });
  }

  const showLegend = pointsBySeason.size > 1;

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
    similarityStatus.textContent = "Select a target player.";
    return;
  }

  const targetRow = rowById.get(targetId);
  if (!targetRow) {
    similarityStatus.textContent = "Target player is not available in the filtered dataset.";
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
    similarityStatus.textContent = "No similar players found with complete data.";
    return;
  }

  topFive.forEach(entry => {
    const row = entry.row;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.player}</td>
      <td>${row.season}</td>
      <td>${row.team}</td>
      <td>${row.minutes_played}</td>
      <td>${entry.dist.toFixed(3)}</td>
    `;
    tbody.appendChild(tr);
  });
}

function updateAll(seasonSelect, minutesInput, playerSelect, metricSelect, radarModeSelect, targetSelect, radarStatus, similarityStatus, topSeasonSelect, topMetricSelect, topNInput, topStatus, bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, bubbleStatus) {
  filteredData = getFilteredData(seasonSelect, minutesInput);
  rowById = new Map(filteredData.map(row => [rowId(row), row]));
  updatePlayerOptions(playerSelect);
  updateTargetOptions(targetSelect);
  updateRadar(playerSelect, metricSelect, radarModeSelect, radarStatus);
  updateSimilarity(targetSelect, similarityStatus);

  buildTopPerformers(topSeasonSelect, topMetricSelect, topNInput, topStatus, minutesInput);
  buildBubbleChart(bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, minutesInput, bubbleStatus);
}

function setStatus(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle("error", isError);
}

async function init() {
  const seasonSelect = document.getElementById("seasonSelect");
  const minutesInput = document.getElementById("minutesInput");
  const playerSelect = document.getElementById("playerSelect");
  const metricSelect = document.getElementById("metricSelect");
  const radarModeSelect = document.getElementById("radarModeSelect");
  const targetSelect = document.getElementById("targetSelect");
  const radarStatus = document.getElementById("radarStatus");
  const similarityStatus = document.getElementById("similarityStatus");
  const dataStatus = document.getElementById("dataStatus");
  const dataDebug = document.getElementById("dataDebug");
  const topSeasonSelect = document.getElementById("topSeasonSelect");
  const topMetricSelect = document.getElementById("topMetricSelect");
  const topNInput = document.getElementById("topNInput");
  const topStatus = document.getElementById("topPerformersStatus");
  const bubbleSeasonSelect = document.getElementById("bubbleSeasonSelect");
  const bubbleXSelect = document.getElementById("bubbleXMetricSelect");
  const bubbleYSelect = document.getElementById("bubbleYMetricSelect");
  const bubbleCompositeSelect = document.getElementById("bubbleCompositeSelect");
  const bubbleLabelSelect = document.getElementById("bubbleLabelSelect");
  const bubbleStatus = document.getElementById("bubbleStatus");
  const tableSeasonSelect = document.getElementById("tableSeasonSelect");
  const tableTeamSelect = document.getElementById("tableTeamSelect");
  const tablePlayerSearch = document.getElementById("tablePlayerSearch");
  const tableMinutesInput = document.getElementById("tableMinutesInput");
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
    row.season = toNumber(row.season);
    row.minutes_played = toNumber(row.minutes_played);
    metricOptions.forEach(metric => {
      row[metric] = toNumber(row[metric]);
    });
    zMetricOptions.forEach(metric => {
      row[metric] = toNumber(row[metric]);
    });
  });

  buildSeasonOptions(seasonSelect);
  buildMetricOptions(metricSelect);
  buildTopSeasonOptions(topSeasonSelect);
  buildTopMetricOptions(topMetricSelect);
  buildTopSeasonOptions(bubbleSeasonSelect);
  buildBubbleAxisOptions(bubbleXSelect, "overall_percentile");
  buildBubbleAxisOptions(bubbleYSelect, "goal_threat_percentile");
  buildBubbleMetricOptions(bubbleCompositeSelect);
  bubbleLabelSelect.value = "top10";
  buildTableSeasonOptions(tableSeasonSelect);
  buildTeamOptions(tableTeamSelect);
  buildTableSortOptions(tableSortSelect);

  setStatus(dataStatus, "Data loaded.");
  setTimeout(() => {
    setStatus(dataStatus, "");
  }, 1500);

  seasonSelect.addEventListener("change", () =>
    updateAll(seasonSelect, minutesInput, playerSelect, metricSelect, radarModeSelect, targetSelect, radarStatus, similarityStatus, topSeasonSelect, topMetricSelect, topNInput, topStatus, bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, bubbleStatus)
  );
  minutesInput.addEventListener("change", () =>
    updateAll(seasonSelect, minutesInput, playerSelect, metricSelect, radarModeSelect, targetSelect, radarStatus, similarityStatus, topSeasonSelect, topMetricSelect, topNInput, topStatus, bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, bubbleStatus)
  );
  playerSelect.addEventListener("change", () =>
    updateRadar(playerSelect, metricSelect, radarModeSelect, radarStatus)
  );
  metricSelect.addEventListener("change", () =>
    updateRadar(playerSelect, metricSelect, radarModeSelect, radarStatus)
  );
  radarModeSelect.addEventListener("change", () =>
    updateRadar(playerSelect, metricSelect, radarModeSelect, radarStatus)
  );
  targetSelect.addEventListener("change", () =>
    updateSimilarity(targetSelect, similarityStatus)
  );

  topSeasonSelect.addEventListener("change", () =>
    buildTopPerformers(topSeasonSelect, topMetricSelect, topNInput, topStatus, minutesInput)
  );
  topMetricSelect.addEventListener("change", () =>
    buildTopPerformers(topSeasonSelect, topMetricSelect, topNInput, topStatus, minutesInput)
  );
  topNInput.addEventListener("change", () =>
    buildTopPerformers(topSeasonSelect, topMetricSelect, topNInput, topStatus, minutesInput)
  );

  bubbleSeasonSelect.addEventListener("change", () =>
    buildBubbleChart(bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, minutesInput, bubbleStatus)
  );
  bubbleXSelect.addEventListener("change", () =>
    buildBubbleChart(bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, minutesInput, bubbleStatus)
  );
  bubbleYSelect.addEventListener("change", () =>
    buildBubbleChart(bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, minutesInput, bubbleStatus)
  );
  bubbleCompositeSelect.addEventListener("change", () =>
    buildBubbleChart(bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, minutesInput, bubbleStatus)
  );
  bubbleLabelSelect.addEventListener("change", () =>
    buildBubbleChart(bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, minutesInput, bubbleStatus)
  );

  const updateTable = () =>
    buildPlayerTable(tableSeasonSelect, tableTeamSelect, tablePlayerSearch, tableMinutesInput, tableRowsSelect, tableSortSelect, tableSortDirSelect, tableStatus);

  tableSeasonSelect.addEventListener("change", updateTable);
  tableTeamSelect.addEventListener("change", updateTable);
  tablePlayerSearch.addEventListener("input", updateTable);
  tableMinutesInput.addEventListener("change", updateTable);
  tableRowsSelect.addEventListener("change", updateTable);
  tableSortSelect.addEventListener("change", updateTable);
  tableSortDirSelect.addEventListener("change", updateTable);

  updateAll(seasonSelect, minutesInput, playerSelect, metricSelect, radarModeSelect, targetSelect, radarStatus, similarityStatus, topSeasonSelect, topMetricSelect, topNInput, topStatus, bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, bubbleStatus);
  updateTable();
}

document.addEventListener("DOMContentLoaded", init);
