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
  "xa_per_90"
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

function getSelectedValues(selectEl) {
  return Array.from(selectEl.selectedOptions).map(option => option.value);
}

function setSelectedValues(selectEl, values) {
  Array.from(selectEl.options).forEach(option => {
    option.selected = values.includes(option.value);
  });
}

function buildSeasonOptions(seasonSelect) {
  const seasons = Array.from(new Set(rawData.map(row => row.season))).sort((a, b) => a - b);
  seasonSelect.innerHTML = "";
  const allOption = document.createElement("option");
  allOption.value = "all";
  allOption.textContent = "All seasons";
  seasonSelect.appendChild(allOption);
  seasons.forEach(season => {
    const option = document.createElement("option");
    option.value = String(season);
    option.textContent = String(season);
    seasonSelect.appendChild(option);
  });
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
  const defaultMetrics = [
    "overall_percentile",
    "goal_threat_percentile",
    "link_play_percentile",
    "non_pkxg_p90",
    "shots_per_90"
  ];
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

  const sorted = [...filteredData].sort((a, b) => b.overall_percentile - a.overall_percentile);
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

function distance(aRow, bRow) {
  let sum = 0;
  for (const col of zMetricOptions) {
    const a = aRow[col];
    const b = bRow[col];
    if (a === null || b === null || a === undefined || b === undefined) {
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

function updateAll(seasonSelect, minutesInput, playerSelect, metricSelect, radarModeSelect, targetSelect, radarStatus, similarityStatus) {
  filteredData = getFilteredData(seasonSelect, minutesInput);
  rowById = new Map(filteredData.map(row => [rowId(row), row]));
  updatePlayerOptions(playerSelect);
  updateTargetOptions(targetSelect);
  updateRadar(playerSelect, metricSelect, radarModeSelect, radarStatus);
  updateSimilarity(targetSelect, similarityStatus);
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

  dataDebug.textContent = `Data URL: ${dataUrl}`;
  dataStatus.textContent = "Loading data...";

  try {
    const response = await fetch(dataUrl);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} ${response.statusText}`);
    }
    rawData = await response.json();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    dataStatus.textContent = `Error loading data (${message}). Check that the JSON file is available.`;
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

  dataStatus.textContent = "Data loaded.";
  setTimeout(() => {
    dataStatus.textContent = "";
  }, 1500);

  seasonSelect.addEventListener("change", () =>
    updateAll(seasonSelect, minutesInput, playerSelect, metricSelect, radarModeSelect, targetSelect, radarStatus, similarityStatus)
  );
  minutesInput.addEventListener("change", () =>
    updateAll(seasonSelect, minutesInput, playerSelect, metricSelect, radarModeSelect, targetSelect, radarStatus, similarityStatus)
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

  updateAll(seasonSelect, minutesInput, playerSelect, metricSelect, radarModeSelect, targetSelect, radarStatus, similarityStatus);
}

document.addEventListener("DOMContentLoaded", init);
