const TEAM_BUILD_VERSION = "team-v8-drivers-fix-20250206";
const dataUrl = `./data/team_comparison_features.json?v=${TEAM_BUILD_VERSION}`;
const driversUrl = `./data/team_points_drivers.json?v=${TEAM_BUILD_VERSION}`;

const identityCols = new Set(["year", "team"]);
let metricOptions = [];
let zMetricOptions = [];

const chartMetricOptions = [
  "points",
  "position",
  "composite_team_score",
  "total_score",
  "goals",
  "conceded_goals",
  "xg_diff",
  "possesion_threat",
  "xg",
  "shots_on_target",
  "average_shot_distance",
  "touches_in_penalty_area",
  "positional_attacks_with_shots",
  "counterattacks_with_shots",
  "set_pieces_with_shots",
  "corners_with_shots",
  "crosses_accurate",
  "deep_completed_crosses",
  "deep_completed_passes",
  "penalty_area_entries_runs_crosses",
  "offensive_duels_won",
  "defensive_duels_won",
  "aerial_duels_won",
  "interceptions",
  "clearances",
  "shots_against_on_target",
  "ppda",
  "possession_pct",
  "passes_accurate",
  "progressive_passes_accurate",
  "passes_to_final_third_accurate",
  "average_pass_length",
  "match_tempo"
];

const defaultMetrics = [
  "points",
  "xg_diff",
  "goals",
  "conceded_goals",
  "possession_pct"
];

const TEAM_PRESETS = {
  results: {
    radar: ["points", "position", "xg_diff", "goals", "conceded_goals"],
    bubbleX: "points",
    bubbleY: "xg_diff",
    bubbleComposite: ["points", "xg_diff", "goals", "conceded_goals"]
  },
  attack: {
    radar: ["goals", "xg", "shots_on_target", "touches_in_penalty_area", "positional_attacks_with_shots"],
    bubbleX: "xg",
    bubbleY: "goals",
    bubbleComposite: ["xg", "shots_on_target", "touches_in_penalty_area", "positional_attacks_with_shots"]
  },
  defense: {
    radar: ["conceded_goals", "shots_against_on_target", "interceptions", "ppda", "defensive_duels_won"],
    bubbleX: "shots_against_on_target",
    bubbleY: "ppda",
    bubbleComposite: ["shots_against_on_target", "interceptions", "ppda", "defensive_duels_won"]
  },
  possession: {
    radar: ["possession_pct", "passes_accurate", "progressive_passes_accurate", "passes_to_final_third_accurate", "deep_completed_passes"],
    bubbleX: "possession_pct",
    bubbleY: "progressive_passes_accurate",
    bubbleComposite: ["possession_pct", "passes_accurate", "progressive_passes_accurate", "passes_to_final_third_accurate"]
  }
};

const similarityMetricOptions = [
  "attacking_score_6_z",
  "defensive_score_8_z",
  "ball_progression_6_z",
  "xg_diff_z",
  "possesion_threat_z",
  "xg_z",
  "shots_on_target_z",
  "possession_pct_z",
  "passes_accurate_z"
];

const metricLabels = {
  points: "Points",
  standarised_points_score: "Standardized Points Score",
  position: "Table Position",
  positon_reversed: "Position (Reversed)",
  adjusted_position_z_score: "Adjusted Position Z",
  composite_team_score: "Composite Team Score",
  total_score: "Total Score",
  attacking_score_6: "Attacking Score",
  defensive_score_8: "Defensive Score",
  ball_progression_6: "Ball Progression",
  xg_diff: "xG Diff",
  possesion_threat: "Possession Threat",
  goals: "Goals",
  conceded_goals: "Conceded Goals",
  xg: "xG",
  shots_on_target: "Shots on Target",
  possession_pct: "Possession %",
  passes_accurate: "Passes Accurate",
  touches_in_penalty_area: "Touches In Pen Area",
  offensive_duels_won: "Offensive Duels Won",
  defensive_duels_won: "Defensive Duels Won",
  aerial_duels_won: "Aerial Duels Won",
  interceptions: "Interceptions",
  clearances: "Clearances",
  progressive_passes_accurate: "Progressive Passes Accurate",
  passes_to_final_third_accurate: "Passes to Final Third Accurate",
  crosses_accurate: "Crosses Accurate",
  deep_completed_passes: "Deep Completed Passes",
  deep_completed_crosses: "Deep Completed Crosses",
  penalty_area_entries_runs_crosses: "Penalty Area Entries (Runs/Crosses)",
  positional_attacks_with_shots: "Positional Attacks with Shots",
  counterattacks_with_shots: "Counterattacks with Shots",
  set_pieces_with_shots: "Set Pieces with Shots",
  corners_with_shots: "Corners with Shots",
  shots_against_on_target: "Shots Against On Target",
  average_pass_length: "Average Pass Length",
  average_shot_distance: "Average Shot Distance",
  ppda: "PPDA",
  match_tempo: "Match Tempo"
};

const metricHelp = {
  points: "League points (results).",
  standarised_points_score: "Standardized points score (model-derived).",
  position: "Table position (lower is better).",
  positon_reversed: "Position reversed (higher = better).",
  adjusted_position_z_score: "Adjusted position z-score (model-derived).",
  composite_team_score: "Composite team model score.",
  total_score: "Total score from model components.",
  attacking_score_6: "Attacking score component.",
  defensive_score_8: "Defensive score component.",
  ball_progression_6: "Ball progression score component.",
  xg_diff: "xG for minus xG against.",
  possesion_threat: "Possession threat model output.",
  goals: "Goals scored.",
  conceded_goals: "Goals conceded (lower is better).",
  xg: "Expected goals for.",
  shots_on_target: "Shots on target for.",
  possession_pct: "Possession percentage.",
  passes_accurate: "Accurate passes.",
  touches_in_penalty_area: "Touches in opponent penalty area.",
  offensive_duels_won: "Offensive duels won.",
  defensive_duels_won: "Defensive duels won.",
  aerial_duels_won: "Aerial duels won.",
  interceptions: "Interceptions.",
  clearances: "Clearances.",
  progressive_passes_accurate: "Accurate progressive passes.",
  passes_to_final_third_accurate: "Accurate passes into final third.",
  crosses_accurate: "Accurate crosses.",
  deep_completed_passes: "Passes completed into deep area.",
  deep_completed_crosses: "Crosses completed into deep area.",
  penalty_area_entries_runs_crosses: "Penalty area entries via runs/crosses.",
  positional_attacks_with_shots: "Positional attacks ending in shots.",
  counterattacks_with_shots: "Counterattacks ending in shots.",
  set_pieces_with_shots: "Set-piece attacks ending in shots.",
  corners_with_shots: "Corners ending in shots.",
  shots_against_on_target: "Shots on target conceded (lower is better).",
  average_pass_length: "Average pass length.",
  average_shot_distance: "Average shot distance.",
  ppda: "PPDA (defensive intensity; lower = more aggressive).",
  match_tempo: "Match tempo."
};

const radarLowerBetter = new Set([
  "position",
  "conceded_goals",
  "shots_against_on_target",
  "ppda",
  "yellow_cards",
  "red_cards",
  "fouls"
]);

const tableColumns = [
  { key: "year", label: "Season", type: "int" },
  { key: "team", label: "Team", type: "text" },
  { key: "points", label: "Points", type: "num" },
  { key: "position", label: "Table Position", type: "num" },
  { key: "composite_team_score", label: "Composite Team Score", type: "num" },
  { key: "total_score", label: "Total Score", type: "num" },
  { key: "standarised_points_score", label: "Standardized Points Score", type: "num" },
  { key: "adjusted_position_z_score", label: "Adjusted Position Z", type: "num" },
  { key: "attacking_score_6", label: "Attacking Score", type: "num" },
  { key: "defensive_score_8", label: "Defensive Score", type: "num" },
  { key: "ball_progression_6", label: "Ball Progression", type: "num" },
  { key: "xg_diff", label: "xG Diff", type: "num" },
  { key: "possesion_threat", label: "Possession Threat", type: "num" },
  { key: "goals", label: "Goals", type: "num" },
  { key: "conceded_goals", label: "Conceded Goals", type: "num" },
  { key: "xg", label: "xG", type: "num" },
  { key: "shots_on_target", label: "Shots on Target", type: "num" },
  { key: "average_shot_distance", label: "Average Shot Distance", type: "num" },
  { key: "touches_in_penalty_area", label: "Touches In Pen Area", type: "num" },
  { key: "positional_attacks_with_shots", label: "Positional Attacks with Shots", type: "num" },
  { key: "counterattacks_with_shots", label: "Counterattacks with Shots", type: "num" },
  { key: "set_pieces_with_shots", label: "Set Pieces with Shots", type: "num" },
  { key: "corners_with_shots", label: "Corners with Shots", type: "num" },
  { key: "crosses_accurate", label: "Crosses Accurate", type: "num" },
  { key: "deep_completed_passes", label: "Deep Completed Passes", type: "num" },
  { key: "deep_completed_crosses", label: "Deep Completed Crosses", type: "num" },
  { key: "penalty_area_entries_runs_crosses", label: "Penalty Area Entries (Runs/Crosses)", type: "num" },
  { key: "offensive_duels_won", label: "Offensive Duels Won", type: "num" },
  { key: "defensive_duels_won", label: "Defensive Duels Won", type: "num" },
  { key: "aerial_duels_won", label: "Aerial Duels Won", type: "num" },
  { key: "interceptions", label: "Interceptions", type: "num" },
  { key: "clearances", label: "Clearances", type: "num" },
  { key: "shots_against_on_target", label: "Shots Against On Target", type: "num" },
  { key: "possession_pct", label: "Possession %", type: "num" },
  { key: "passes_accurate", label: "Passes Accurate", type: "num" },
  { key: "progressive_passes_accurate", label: "Progressive Passes Accurate", type: "num" },
  { key: "passes_to_final_third_accurate", label: "Passes to Final Third Accurate", type: "num" },
  { key: "average_pass_length", label: "Average Pass Length", type: "num" },
  { key: "ppda", label: "PPDA", type: "num" },
  { key: "match_tempo", label: "Match Tempo", type: "num" }
];

const radarPalette = [
  "#1f77b4",
  "#ff7f0e",
  "#2ca02c",
  "#d62728",
  "#9467bd",
  "#8c564b",
  "#e377c2",
  "#7f7f7f",
  "#bcbd22",
  "#17becf"
];

let rawData = [];
let filteredData = [];
let rowById = new Map();
let tableColumnsAvailable = [];
let activeSimilarityMetrics = [];
let similarityMetricCounts = {};
let similarityMetricMissing = [];
let similarityMinShared = 0;
let allDataKeys = new Set();
let driversData = null;

const REQUIRED_TABLE_KEYS = new Set(["year", "team", "points"]);
const MIN_SHARED_SIM_METRICS = 4;

function toNumber(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function getAllKeys(rows) {
  const keys = new Set();
  rows.forEach(row => {
    Object.keys(row || {}).forEach(key => keys.add(key));
  });
  return keys;
}

function rowId(row) {
  return `${row.year}|${row.team}`;
}

function rowLabel(row) {
  return `${row.team} — ${row.year}`;
}

function prettyMetricLabel(metric) {
  return metricLabels[metric] || metric.replace(/_/g, " ");
}

function resizePlot(containerId) {
  if (!window.Plotly) return;
  const el = document.getElementById(containerId);
  if (el && el.data) {
    Plotly.Plots.resize(el);
  }
}

function resizePlotsForTab(tabId) {
  const map = {
    "tab-overview": ["radar"],
    "tab-top": ["topTeamsChart"],
    "tab-bubble": ["bubbleChart"],
    "tab-drivers": ["driversCorrChart", "driversRfChart"]
  };
  const ids = map[tabId] || [];
  ids.forEach(id => resizePlot(id));
}

function setupTabs() {
  const buttons = Array.from(document.querySelectorAll("[data-tab-target]"));
  const sections = Array.from(document.querySelectorAll(".tab-section"));
  if (buttons.length === 0 || sections.length === 0) {
    return;
  }

  const activate = (targetId) => {
    sections.forEach(section => {
      section.classList.toggle("active", section.id === targetId);
    });
    buttons.forEach(button => {
      button.classList.toggle("active", button.getAttribute("data-tab-target") === targetId);
    });
    if (targetId) {
      const newUrl = `${window.location.pathname}${window.location.search}#${targetId}`;
      window.history.replaceState(null, "", newUrl);
    }
    resizePlotsForTab(targetId);
  };

  const initialHash = window.location.hash ? window.location.hash.slice(1) : "";
  const initialTarget = sections.some(section => section.id === initialHash)
    ? initialHash
    : buttons[0].getAttribute("data-tab-target");
  activate(initialTarget);

  buttons.forEach(button => {
    button.addEventListener("click", () => {
      activate(button.getAttribute("data-tab-target"));
    });
  });

  window.addEventListener("resize", () => {
    const active = buttons.find(button => button.classList.contains("active"));
    if (active) {
      resizePlotsForTab(active.getAttribute("data-tab-target"));
    }
  });
}

function buildTableHeader(columnsOverride) {
  const headerRow = document.getElementById("teamTableHeader");
  if (!headerRow) return;
  const columns = columnsOverride || (tableColumnsAvailable.length > 0 ? tableColumnsAvailable : tableColumns);
  if (columns.length === 0) {
    headerRow.innerHTML = "<th>No columns available</th>";
    return;
  }
  headerRow.innerHTML = columns.map(col => `<th>${col.label}</th>`).join("");
}

function countNonNull(rows, key) {
  let count = 0;
  rows.forEach(row => {
    const value = toNumber(row[key]);
    if (Number.isFinite(value)) {
      count += 1;
    }
  });
  return count;
}

function initializeMetricOptions() {
  if (rawData.length === 0) {
    metricOptions = [];
    zMetricOptions = [];
    return;
  }
  const sampleKeys = allDataKeys.size > 0 ? Array.from(allDataKeys) : Object.keys(rawData[0]);
  metricOptions = chartMetricOptions.filter(key =>
    sampleKeys.includes(key) && rawData.some(row => Number.isFinite(row[key]))
  );
  zMetricOptions = metricOptions
    .map(metric => `${metric}_z`)
    .filter(metric => sampleKeys.includes(metric));
}

function computeSimilarityAvailability(rows) {
  const keys = rows && rows.length > 0 ? getAllKeys(rows) : new Set();
  similarityMetricCounts = {};
  similarityMetricMissing = [];
  activeSimilarityMetrics = [];

  similarityMetricOptions.forEach(metric => {
    if (!keys.has(metric)) {
      similarityMetricCounts[metric] = 0;
      similarityMetricMissing.push(metric);
      return;
    }
    const count = countNonNull(rows, metric);
    similarityMetricCounts[metric] = count;
    if (count > 0) {
      activeSimilarityMetrics.push(metric);
    }
  });

  similarityMinShared = Math.min(MIN_SHARED_SIM_METRICS, activeSimilarityMetrics.length);
}

function updateDataWarning() {
  const dataWarning = document.getElementById("dataWarning");
  if (!dataWarning) return;
  const keyFields = [
    "standarised_points_score",
    "adjusted_position_z_score",
    "composite_team_score",
    "total_score",
    "attacking_score_6",
    "defensive_score_8",
    "ball_progression_6",
    "xg_diff",
    "possesion_threat",
  ];
  const missing = keyFields.filter(field => countNonNull(rawData, field) === 0);
  if (missing.length > 0) {
    dataWarning.textContent =
      "Some model-derived team fields are unavailable in this export. Similarity and some table columns may be limited until the workbook is recalculated and re-exported.";
    dataWarning.classList.add("error");
  } else {
    dataWarning.textContent = "";
    dataWarning.classList.remove("error");
  }
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
    option.textContent = prettyMetricLabel(metric);
    if (metricHelp[metric]) {
      option.title = metricHelp[metric];
    }
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

function formatRadarValue(value, mode) {
  if (!Number.isFinite(value)) {
    return "—";
  }
  const decimals = mode === "z" ? 2 : 3;
  return value.toFixed(decimals);
}

function computeMetricRanks(rows, metric, radarModeSelect, lowerBetter) {
  const metricKey = radarModeSelect.value === "z" ? `${metric}_z` : metric;
  const values = rows
    .map(row => ({ id: rowId(row), value: row[metricKey] }))
    .filter(item => Number.isFinite(item.value));

  const n = values.length;
  if (n === 0) {
    return { n: 0, map: new Map() };
  }

  values.sort((a, b) => {
    if (lowerBetter) {
      return a.value - b.value;
    }
    return b.value - a.value;
  });

  const rankMap = new Map();
  values.forEach((item, idx) => {
    const rank = idx + 1;
    const percentile = n === 1 ? 100 : ((n - rank) / (n - 1)) * 100;
    rankMap.set(item.id, { rank, percentile, n });
  });

  return { n, map: rankMap };
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

  const entries = [];
  const allValues = [];
  selectedTeams.forEach(id => {
    const row = rowById.get(id);
    if (!row) return;
    const values = selectedMetrics.map(metric => getRadarValue(row, metric, radarModeSelect));
    if (values.some(value => value === null || value === undefined || Number.isNaN(value))) {
      return;
    }
    values.forEach(value => allValues.push(value));
    entries.push({ row, values });
  });

  const metricCount = selectedMetrics.length;
  const metricAngles = selectedMetrics.map((_, idx) => (360 / metricCount) * idx);
  const wedgeWidth = (360 / metricCount) * 0.9;
  const rankMaps = new Map();
  selectedMetrics.forEach(metric => {
    const lowerBetter = radarLowerBetter.has(metric);
    rankMaps.set(metric, computeMetricRanks(filteredData, metric, radarModeSelect, lowerBetter));
  });

  const colorById = new Map();
  entries.forEach((entry, idx) => {
    colorById.set(rowId(entry.row), radarPalette[idx % radarPalette.length]);
  });

  const traces = [];
  const legendShown = new Set();
  let valueShift = 0;
  if (allValues.length > 0) {
    const minVal = Math.min(...allValues);
    valueShift = minVal < 0 ? -minVal : 0;
  }

  for (let metricIndex = 0; metricIndex < metricCount; metricIndex += 1) {
    const angle = metricAngles[metricIndex];
    const metricValues = entries
      .map(entry => ({ entry, value: entry.values[metricIndex] }))
      .sort((a, b) => a.value - b.value);

    metricValues.forEach(item => {
      const entryId = rowId(item.entry.row);
      const showLegend = !legendShown.has(entryId);
      if (showLegend) {
        legendShown.add(entryId);
      }
      const metricKey = selectedMetrics[metricIndex];
      const rawVal = item.entry.row[metricKey];
      const zVal = item.entry.row[`${metricKey}_z`];
      const mode = radarModeSelect.value;
      const rankInfo = rankMaps.get(metricKey);
      const rankEntry = rankInfo ? rankInfo.map.get(entryId) : null;
      const rankText = rankEntry ? `${rankEntry.rank}/${rankEntry.n}` : "—";
      const pctText = rankEntry ? `${rankEntry.percentile.toFixed(0)}%` : "—";
      const hoverTemplate = mode === "z"
        ? "<b>%{customdata.label}</b><br>%{customdata.metric}: %{customdata.zText} (Z)<br>Raw: %{customdata.rawText}<br>Rank: %{customdata.rankText}<br>Percentile: %{customdata.pctText}<extra></extra>"
        : "<b>%{customdata.label}</b><br>%{customdata.metric}: %{customdata.rawText} (Raw)<br>Z: %{customdata.zText}<br>Rank: %{customdata.rankText}<br>Percentile: %{customdata.pctText}<extra></extra>";
      traces.push({
        type: "barpolar",
        r: [item.value + valueShift],
        theta: [angle],
        width: wedgeWidth,
        name: rowLabel(item.entry.row),
        legendgroup: entryId,
        showlegend: showLegend,
        marker: {
          color: colorById.get(entryId),
          opacity: entries.length > 1 ? 0.65 : 0.85,
          line: { width: 1, color: "rgba(0,0,0,0.25)" }
        },
        customdata: [{
          label: rowLabel(item.entry.row),
          metric: prettyMetricLabel(metricKey),
          rawText: formatRadarValue(rawVal, "raw"),
          zText: formatRadarValue(zVal, "z"),
          rankText,
          pctText
        }],
        hovertemplate: hoverTemplate
      });
    });
  }

  if (traces.length === 0) {
    Plotly.purge("radar");
    radarStatus.textContent = "No data available for the selected teams/metrics.";
    return;
  }

  if (valueShift > 0) {
    radarStatus.textContent = "Values shifted to be non-negative for stacked pizza slices.";
  }

  Plotly.newPlot("radar", traces, {
    polar: {
      radialaxis: { visible: true, showticklabels: false },
      angularaxis: { tickmode: "array", tickvals: metricAngles, ticktext: selectedMetrics.map(prettyMetricLabel) }
    },
    barmode: "stack",
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
    option.textContent = prettyMetricLabel(metric);
    if (metricHelp[metric]) {
      option.title = metricHelp[metric];
    }
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
    option.textContent = prettyMetricLabel(metric);
    if (metricHelp[metric]) {
      option.title = metricHelp[metric];
    }
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
    option.textContent = prettyMetricLabel(metric);
    if (metricHelp[metric]) {
      option.title = metricHelp[metric];
    }
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
    name: prettyMetricLabel(selectedMetric),
    x: teams.map(row => row.team),
    y: values,
    hovertext: labels,
    hovertemplate: "%{hovertext}<br>" + prettyMetricLabel(selectedMetric) + ": %{y:.3f}<extra></extra>"
  };

  Plotly.newPlot("topTeamsChart", [trace], {
    margin: { t: 30, b: 160, l: 50, r: 20 },
    xaxis: { tickangle: -30, automargin: true, tickfont: { size: 10 } },
    yaxis: { title: prettyMetricLabel(selectedMetric), automargin: true },
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

  const sizeFor = value => {
    const clamped = Math.max(-2, Math.min(2, value));
    const ratio = (clamped + 2) / 4;
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
  let shared = 0;
  for (const col of activeSimilarityMetrics) {
    const a = aRow[col];
    const b = bRow[col];
    if (!Number.isFinite(a) || !Number.isFinite(b)) {
      continue;
    }
    sum += (a - b) * (a - b);
    shared += 1;
  }
  if (shared < similarityMinShared) {
    return null;
  }
  return { dist: Math.sqrt(sum / shared), shared };
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

  if (activeSimilarityMetrics.length === 0) {
    similarityStatus.textContent =
      "Similarity unavailable: none of the curated similarity metrics exist in the current export. Recalculate the workbook and re-export.";
    return;
  }

  const targetSharedCount = activeSimilarityMetrics.filter(col => Number.isFinite(targetRow[col])).length;
  if (targetSharedCount < similarityMinShared) {
    const missingNote = similarityMetricMissing.length > 0
      ? ` Missing metrics in export: ${similarityMetricMissing.map(prettyMetricLabel).join(", ")}.`
      : "";
    similarityStatus.textContent =
      `Similarity unavailable: target has ${targetSharedCount}/${activeSimilarityMetrics.length} valid similarity metrics (min required ${similarityMinShared}).${missingNote}`;
    return;
  }

  const candidates = [];
  filteredData.forEach(row => {
    if (rowId(row) === targetId) return;
    const result = distance(row, targetRow);
    if (!result) return;
    candidates.push({ row, dist: result.dist, shared: result.shared });
  });

  candidates.sort((a, b) => a.dist - b.dist);
  const maxDist = candidates.length > 0 ? Math.max(...candidates.map(entry => entry.dist)) : 0;
  const topFive = candidates.slice(0, 5);

  if (topFive.length === 0) {
    const missingNote = similarityMetricMissing.length > 0
      ? ` Missing metrics in export: ${similarityMetricMissing.map(prettyMetricLabel).join(", ")}.`
      : "";
    similarityStatus.textContent =
      `Similarity unavailable: no candidates with at least ${similarityMinShared} shared similarity metrics. Target valid: ${targetSharedCount}/${activeSimilarityMetrics.length}.${missingNote}`;
    return;
  }

  const missingNote = similarityMetricMissing.length > 0
    ? ` Missing metrics in export: ${similarityMetricMissing.map(prettyMetricLabel).join(", ")}.`
    : "";
  similarityStatus.textContent =
    `Using ${activeSimilarityMetrics.length} similarity metrics (min shared ${similarityMinShared}).${missingNote}`;

  topFive.forEach(entry => {
    const row = entry.row;
    const similarityPct = maxDist === 0 ? 100 : (1 - entry.dist / maxDist) * 100;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.team}</td>
      <td>${row.year}</td>
      <td>${Number.isFinite(row.points) ? row.points.toFixed(0) : ""}</td>
      <td>${similarityPct.toFixed(1)}%</td>
    `;
    tbody.appendChild(tr);
  });
}

function formatTableValue(row, column) {
  const value = row[column.key];
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (column.type === "text") {
    return String(value);
  }
  if (column.type === "int") {
    return Number.isFinite(value) ? String(Math.round(value)) : "—";
  }
  return Number.isFinite(value) ? value.toFixed(3) : "—";
}

function buildTableSortOptions(tableSortSelect) {
  tableSortSelect.innerHTML = "";
  const columns = tableColumnsAvailable.length > 0 ? tableColumnsAvailable : tableColumns;
  if (columns.length === 0) {
    return;
  }
  columns.forEach(col => {
    const option = document.createElement("option");
    option.value = col.key;
    option.textContent = col.label;
    if (metricHelp[col.key]) {
      option.title = metricHelp[col.key];
    }
    tableSortSelect.appendChild(option);
  });
  if (columns.some(col => col.key === "points")) {
    tableSortSelect.value = "points";
  } else {
    tableSortSelect.value = columns[0]?.key || "";
  }
}

function applyPreset(presetKey, controls) {
  const preset = TEAM_PRESETS[presetKey];
  if (!preset) {
    return;
  }
  const { metricSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, teamSelect, radarModeSelect, radarStatus, bubbleYearSelect, bubbleLabelSelect, pointsInput, bubbleStatus } = controls;
  const validRadar = preset.radar.filter(metric => metricOptions.includes(metric));
  const validComposite = preset.bubbleComposite.filter(metric => metricOptions.includes(metric));

  if (validRadar.length > 0) {
    setSelectedValues(metricSelect, validRadar);
  }
  if (metricOptions.includes(preset.bubbleX)) {
    bubbleXSelect.value = preset.bubbleX;
  }
  if (metricOptions.includes(preset.bubbleY)) {
    bubbleYSelect.value = preset.bubbleY;
  }
  if (validComposite.length > 0) {
    setSelectedValues(bubbleCompositeSelect, validComposite);
  }

  updateRadar(teamSelect, metricSelect, radarModeSelect, radarStatus);
  buildBubbleChart(bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, pointsInput, bubbleStatus);
}

function decodeList(value) {
  if (!value) {
    return [];
  }
  return value.split(",").map(item => decodeURIComponent(item));
}

function encodeList(values) {
  return values.map(item => encodeURIComponent(item)).join(",");
}

function readUrlState() {
  const params = new URLSearchParams(window.location.search);
  return {
    season: params.get("season"),
    minPoints: params.get("min_points"),
    teams: decodeList(params.get("teams")),
    metrics: decodeList(params.get("metrics")),
    radarMode: params.get("radar_mode"),
    topSeasons: decodeList(params.get("top_seasons")),
    topMetric: params.get("top_metric"),
    topN: params.get("top_n"),
    bubbleSeasons: decodeList(params.get("bubble_seasons")),
    bubbleX: params.get("bubble_x"),
    bubbleY: params.get("bubble_y"),
    bubbleComposite: decodeList(params.get("bubble_comp")),
    bubbleLabels: params.get("bubble_labels"),
    similarityTarget: params.get("similarity_target"),
    tableSeasons: decodeList(params.get("table_seasons")),
    tableSearch: params.get("table_search"),
    tableMinPoints: params.get("table_min_points"),
    tableRows: params.get("table_rows"),
    tableSort: params.get("table_sort"),
    tableSortDir: params.get("table_sort_dir")
  };
}

function applySingleSelect(selectEl, value) {
  if (!selectEl || !value) {
    return;
  }
  const exists = Array.from(selectEl.options).some(option => option.value === value);
  if (exists) {
    selectEl.value = value;
  }
}

function applyMultiSelect(selectEl, values) {
  if (!selectEl || !values || values.length === 0) {
    return;
  }
  const available = new Set(Array.from(selectEl.options).map(option => option.value));
  const valid = values.filter(value => available.has(value));
  if (valid.length > 0) {
    setSelectedValues(selectEl, valid);
  }
}

function applyNumberInput(inputEl, value) {
  if (!inputEl || value === null || value === undefined) {
    return;
  }
  const num = Number(value);
  if (Number.isFinite(num)) {
    inputEl.value = String(num);
  }
}

function applyTextInput(inputEl, value) {
  if (!inputEl || value === null || value === undefined) {
    return;
  }
  inputEl.value = String(value);
}

function normalizeMultiSelection(values) {
  if (values.includes("all")) {
    return ["all"];
  }
  return values;
}

function syncUrlFromControls(state) {
  const params = new URLSearchParams();
  const setParam = (key, value) => {
    if (value === null || value === undefined || value === "") {
      return;
    }
    params.set(key, String(value));
  };
  const setListParam = (key, values) => {
    if (!values || values.length === 0) {
      return;
    }
    params.set(key, encodeList(values));
  };

  setParam("season", state.yearSelect.value);
  setParam("min_points", state.pointsInput.value);
  setListParam("teams", normalizeMultiSelection(getSelectedValues(state.teamSelect)));
  setListParam("metrics", normalizeMultiSelection(getSelectedValues(state.metricSelect)));
  setParam("radar_mode", state.radarModeSelect.value);
  setListParam("top_seasons", normalizeMultiSelection(getSelectedValues(state.topYearSelect)));
  setParam("top_metric", state.topMetricSelect.value);
  setParam("top_n", state.topNInput.value);
  setListParam("bubble_seasons", normalizeMultiSelection(getSelectedValues(state.bubbleYearSelect)));
  setParam("bubble_x", state.bubbleXSelect.value);
  setParam("bubble_y", state.bubbleYSelect.value);
  setListParam("bubble_comp", normalizeMultiSelection(getSelectedValues(state.bubbleCompositeSelect)));
  setParam("bubble_labels", state.bubbleLabelSelect.value);
  setParam("similarity_target", state.targetSelect.value);
  setListParam("table_seasons", normalizeMultiSelection(getSelectedValues(state.tableYearSelect)));
  setParam("table_search", state.tableTeamSearch.value.trim());
  setParam("table_min_points", state.tablePointsInput.value);
  setParam("table_rows", state.tableRowsSelect.value);
  setParam("table_sort", state.tableSortSelect.value);
  setParam("table_sort_dir", state.tableSortDirSelect.value);

  const query = params.toString();
  const newUrl = query ? `${window.location.pathname}?${query}` : window.location.pathname;
  window.history.replaceState(null, "", newUrl);
}

function getTableDisplayRows(tableYearSelect, tableTeamSearch, tablePointsInput, tableRowsSelect, tableSortSelect, tableSortDirSelect) {
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

  return { rows: displayRows, total: rows.length, columns };
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
  const { rows: displayRows, total, columns } = getTableDisplayRows(tableYearSelect, tableTeamSearch, tablePointsInput, tableRowsSelect, tableSortSelect, tableSortDirSelect);
  buildTableHeader(columns);
  if (columns.length === 0) {
    tableStatus.textContent = "No table columns available in the current export.";
    return;
  }

  const tbody = document.querySelector("#teamTable tbody");
  tbody.innerHTML = displayRows.map(row => {
    const cells = columns.map(col => `<td>${formatTableValue(row, col)}</td>`).join("");
    return `<tr>${cells}</tr>`;
  }).join("");

  tableStatus.textContent = `Showing ${displayRows.length} of ${total} rows`;
}

function escapeCsvValue(value) {
  if (value === null || value === undefined) {
    return "";
  }
  const str = String(value);
  if (/[",\n]/.test(str)) {
    return `"${str.replace(/"/g, "\"\"")}"`;
  }
  return str;
}

function formatCsvValue(row, column) {
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

function downloadCsv(filename, rows, columns) {
  const header = columns.map(col => escapeCsvValue(col.label)).join(",");
  const body = rows.map(row => columns.map(col => escapeCsvValue(formatCsvValue(row, col))).join(",")).join("\n");
  const csv = [header, body].filter(Boolean).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function formatDateStamp() {
  const now = new Date();
  const yyyy = now.getFullYear();
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  const dd = String(now.getDate()).padStart(2, "0");
  return `${yyyy}${mm}${dd}`;
}

function describeSelection(selectEl, useLabels = true, labelFn = null) {
  const selected = Array.from(selectEl.selectedOptions);
  if (selected.length === 0) {
    return "None";
  }
  if (selected.some(option => option.value === "all")) {
    return "All";
  }
  return selected
    .map(option => {
      if (labelFn) {
        return labelFn(option.value);
      }
      return useLabels ? option.textContent : option.value;
    })
    .join(", ");
}

async function copyToClipboard(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    await navigator.clipboard.writeText(text);
    return true;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  const success = document.execCommand("copy");
  document.body.removeChild(textarea);
  return success;
}

function buildSummaryText(state) {
  const {
    yearSelect,
    pointsInput,
    teamSelect,
    metricSelect,
    radarModeSelect,
    topYearSelect,
    topMetricSelect,
    topNInput,
    bubbleYearSelect,
    bubbleXSelect,
    bubbleYSelect,
    bubbleCompositeSelect,
    targetSelect
  } = state;

  return [
    "Team Prototype Summary",
    `Season filter: ${describeSelection(yearSelect, true)}`,
    `Min points: ${pointsInput.value || 0}`,
    `Radar teams: ${describeSelection(teamSelect, true)}`,
    `Radar metrics: ${describeSelection(metricSelect, false, prettyMetricLabel)}`,
    `Radar mode: ${radarModeSelect.value === "z" ? "Z-scores" : "Raw values"}`,
    `Top teams: ${prettyMetricLabel(topMetricSelect.value)} (Top ${topNInput.value})`,
    `Top seasons: ${describeSelection(topYearSelect, true)}`,
    `Bubble seasons: ${describeSelection(bubbleYearSelect, true)}`,
    `Bubble X: ${prettyMetricLabel(bubbleXSelect.value)}`,
    `Bubble Y: ${prettyMetricLabel(bubbleYSelect.value)}`,
    `Bubble composite: ${describeSelection(bubbleCompositeSelect, false, prettyMetricLabel)}`,
    `Similarity target: ${targetSelect.selectedOptions[0]?.textContent || "None"}`
  ].join("\n");
}

function formatReportValue(metric, value) {
  if (!Number.isFinite(value)) {
    return "n/a";
  }
  if (metric === "points" || metric === "position" || metric === "year") {
    return String(Math.round(value));
  }
  if (metric.endsWith("_pct")) {
    return value.toFixed(1);
  }
  return value.toFixed(3);
}

function getTopRowByMetric(rows, metric) {
  let topRow = null;
  let topVal = -Infinity;
  rows.forEach(row => {
    const value = row[metric];
    if (!Number.isFinite(value)) {
      return;
    }
    if (value > topVal) {
      topVal = value;
      topRow = row;
    }
  });
  if (!topRow) {
    return null;
  }
  return { row: topRow, value: topVal };
}

function buildTeamTakeaways(selectedRows, targetRow) {
  const bullets = [];
  if (selectedRows.length >= 2) {
    const metricPriority = [
      { key: "points", label: metricLabels.points || "Points" },
      { key: "xg_diff", label: metricLabels.xg_diff || "xG Diff" },
      { key: "composite_team_score", label: metricLabels.composite_team_score || "Composite Team Score" }
    ];
    metricPriority.forEach(metric => {
      const top = getTopRowByMetric(selectedRows, metric.key);
      if (!top) {
        return;
      }
      bullets.push(`Top ${metric.label}: ${rowLabel(top.row)} (${formatReportValue(metric.key, top.value)})`);
    });
  } else if (selectedRows.length === 1) {
    bullets.push("Select at least two teams to generate takeaways.");
  } else {
    bullets.push("Select teams to generate takeaways.");
  }

  if (targetRow) {
    bullets.push(`Similarity target: ${rowLabel(targetRow)}`);
  }

  if (bullets.length > 3) {
    if (targetRow) {
      const similarityBullet = bullets[bullets.length - 1];
      const metricBullets = bullets.slice(0, -1).slice(0, 2);
      return [...metricBullets, similarityBullet];
    }
    return bullets.slice(0, 3);
  }
  return bullets;
}

function buildReportSnapshot(state) {
  const seasonText = describeSelection(state.yearSelect, true);
  const pointsText = state.pointsInput.value || "0";
  const teamsText = describeSelection(state.teamSelect, true);
  const metricsText = describeSelection(state.metricSelect, false, prettyMetricLabel);
  const radarModeText = state.radarModeSelect.value === "z" ? "Z-scores" : "Raw values";
  const topText = `${prettyMetricLabel(state.topMetricSelect.value)} (Top ${state.topNInput.value}) | Seasons: ${describeSelection(state.topYearSelect, true)}`;
  const bubbleText = `Seasons: ${describeSelection(state.bubbleYearSelect, true)} | X: ${prettyMetricLabel(state.bubbleXSelect.value)} | Y: ${prettyMetricLabel(state.bubbleYSelect.value)} | Composite: ${describeSelection(state.bubbleCompositeSelect, false, prettyMetricLabel)}`;
  const similarityText = state.targetSelect.selectedOptions[0]?.textContent || "None";
  const selectedRows = getSelectedValues(state.teamSelect).map(id => rowById.get(id)).filter(Boolean);
  const targetRow = rowById.get(state.targetSelect.value);
  const takeaways = buildTeamTakeaways(selectedRows, targetRow);

  return {
    seasonText,
    pointsText,
    teamsText,
    metricsText,
    radarModeText,
    topText,
    bubbleText,
    similarityText,
    takeaways
  };
}

function updateReport(state, elements) {
  if (!elements || !elements.reportSeason) {
    return;
  }
  const snapshot = buildReportSnapshot(state);
  elements.reportSeason.textContent = snapshot.seasonText;
  elements.reportPoints.textContent = snapshot.pointsText;
  elements.reportTeams.textContent = snapshot.teamsText;
  elements.reportMetrics.textContent = snapshot.metricsText;
  elements.reportRadarMode.textContent = snapshot.radarModeText;
  elements.reportTop.textContent = snapshot.topText;
  elements.reportBubble.textContent = snapshot.bubbleText;
  elements.reportSimilarity.textContent = snapshot.similarityText;
  if (elements.reportTakeaways) {
    elements.reportTakeaways.innerHTML = snapshot.takeaways.map(item => `<li>${item}</li>`).join("");
  }
}

function buildReportText(state) {
  const snapshot = buildReportSnapshot(state);
  const lines = [
    "Team Current View Report",
    `Season filter: ${snapshot.seasonText}`,
    `Min points: ${snapshot.pointsText}`,
    `Radar teams: ${snapshot.teamsText}`,
    `Radar metrics: ${snapshot.metricsText}`,
    `Radar mode: ${snapshot.radarModeText}`,
    `Top teams: ${snapshot.topText}`,
    `Bubble: ${snapshot.bubbleText}`,
    `Similarity target: ${snapshot.similarityText}`
  ];
  if (snapshot.takeaways.length > 0) {
    lines.push("", "Key Takeaways:");
    snapshot.takeaways.forEach(item => lines.push(`- ${item}`));
  }
  return lines.join("\n");
}

function handleTableExport(tableYearSelect, tableTeamSearch, tablePointsInput, tableRowsSelect, tableSortSelect, tableSortDirSelect, exportStatus) {
  const { rows: displayRows, columns } = getTableDisplayRows(tableYearSelect, tableTeamSearch, tablePointsInput, tableRowsSelect, tableSortSelect, tableSortDirSelect);
  if (displayRows.length === 0) {
    exportStatus.textContent = "No rows to export.";
    return;
  }
  const seasonTag = describeSelection(tableYearSelect, true).replace(/\s+/g, "-").replace(/[,/]/g, "_") || "all";
  const filename = `team_table_export_${seasonTag}_${formatDateStamp()}.csv`;
  downloadCsv(filename, displayRows, columns);
  exportStatus.textContent = `Exported ${displayRows.length} rows.`;
  setTimeout(() => {
    exportStatus.textContent = "";
  }, 2000);
}

function updateAll(yearSelect, pointsInput, teamSelect, metricSelect, radarModeSelect, targetSelect, radarStatus, similarityStatus, topYearSelect, topMetricSelect, topNInput, topStatus, bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, bubbleStatus) {
  filteredData = getFilteredData(yearSelect, pointsInput);
  rowById = new Map(filteredData.map(row => [rowId(row), row]));
  computeSimilarityAvailability(filteredData);
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

function buildDriversChart(containerId, rows, valueKey, title, color) {
  const container = document.getElementById(containerId);
  if (!container) return;
  if (!rows || rows.length === 0) {
    container.innerHTML = "<div class=\"muted\">No data available.</div>";
    return;
  }
  const sorted = [...rows].sort((a, b) => (b[valueKey] || 0) - (a[valueKey] || 0)).slice(0, 10);
  const labels = sorted.map(row => prettyMetricLabel(row.feature)).reverse();
  const values = sorted
    .map(row => {
      const raw = row[valueKey] || 0;
      return valueKey === "abs_spearman" ? Math.abs(raw) : raw;
    })
    .reverse();

  const trace = {
    type: "bar",
    x: values,
    y: labels,
    orientation: "h",
    marker: { color: color || "#1f77b4" }
  };
  const layout = {
    title: title || "",
    margin: { l: 180, r: 20, t: 20, b: 40 },
    xaxis: { title: valueKey === "abs_spearman" ? "|Spearman|" : "Model reliance (higher = stronger)" },
    yaxis: { automargin: true }
  };
  Plotly.newPlot(container, [trace], layout, { displayModeBar: false, responsive: true });
}

function buildDriversReport(driversData) {
  const reportEl = document.getElementById("driversReport");
  if (!reportEl) return;
  const corr = (driversData && driversData.correlations_process) || [];
  const rf = (driversData && driversData.rf_importance_process) || [];

  const topCorr = corr.slice(0, 3).map(row => prettyMetricLabel(row.feature));
  const topRf = rf.slice(0, 3).map(row => prettyMetricLabel(row.feature));

  const extraProcess = [];
  ["possesion_threat", "ball_progression_6", "touches_in_penalty_area", "penalty_area_entries_runs_crosses"].forEach(key => {
    if (corr.some(row => row.feature === key) || rf.some(row => row.feature === key)) {
      extraProcess.push(prettyMetricLabel(key));
    }
  });

  const whatMatters = [
    topRf.length > 0 ? `Model‑strong signals: ${topRf.join(", ")}.` : "Model‑strong signals: unavailable.",
    topCorr.length > 0 ? `Consistent one‑metric patterns: ${topCorr.join(", ")}.` : "Consistent one‑metric patterns: unavailable.",
    extraProcess.length > 0 ? `Useful process indicators: ${extraProcess.join(", ")}.` : "Useful process indicators: see chart selections."
  ];

  const lessDirect = [
    "Discipline/context signals (cards, fouls, tempo) show up, but are less direct than core performance traits.",
    "Set‑piece volume can matter, but is usually a secondary lever compared to open‑play threat."
  ];

  const careful = [
    "These are associations, not causes — treat them as guidance.",
    "Results‑adjacent signals (goals, conceded) can dominate in descriptive models."
  ];

  const interpretation = [
    "Focus on building threat (chance creation) and defensive control; those patterns align most consistently with points.",
    "Use this as a quick diagnostic, then drill into match context."
  ];

  reportEl.innerHTML = `
    <div class="section-note">
      <strong>What matters most</strong>
      <ul>${whatMatters.map(item => `<li>${item}</li>`).join("")}</ul>
    </div>
    <div class="section-note">
      <strong>What likely matters but is less direct</strong>
      <ul>${lessDirect.map(item => `<li>${item}</li>`).join("")}</ul>
    </div>
    <div class="section-note">
      <strong>What to be careful with</strong>
      <ul>${careful.map(item => `<li>${item}</li>`).join("")}</ul>
    </div>
    <div class="section-note">
      <strong>Coach interpretation</strong>
      <ul>${interpretation.map(item => `<li>${item}</li>`).join("")}</ul>
    </div>
  `;
}

function buildDriversReportText(driversData) {
  const corr = (driversData && driversData.correlations_process) || [];
  const rf = (driversData && driversData.rf_importance_process) || [];
  const topCorr = corr.slice(0, 3).map(row => prettyMetricLabel(row.feature));
  const topRf = rf.slice(0, 3).map(row => prettyMetricLabel(row.feature));

  return [
    "Points Drivers (process model)",
    "",
    `What matters most: ${topRf.length > 0 ? topRf.join(", ") : "Unavailable"}`,
    `Consistent single-metric patterns: ${topCorr.length > 0 ? topCorr.join(", ") : "Unavailable"}`,
    "Be careful with: correlations are associations, not causes.",
    "Coach interpretation: build threat + defensive control; use this as guidance."
  ].join("\\n");
}

async function initDriversSection() {
  const driversStatus = document.getElementById("driversStatus");
  const processImg = document.getElementById("driversTreeProcessImg");
  const descImg = document.getElementById("driversTreeDescImg");
  const copyBtn = document.getElementById("driversCopyBtn");
  const copyStatus = document.getElementById("driversCopyStatus");

  if (processImg) {
    processImg.src = `../outputs/team_tree_process_top8_depth3.png?v=${TEAM_BUILD_VERSION}`;
  }
  if (descImg) {
    descImg.src = `../outputs/team_tree_descriptive_top8_depth3.png?v=${TEAM_BUILD_VERSION}`;
  }

  try {
    const response = await fetch(driversUrl);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} ${response.statusText}`);
    }
    driversData = await response.json();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (driversStatus) {
      setStatus(driversStatus, `Points drivers section unavailable (${message}).`, true);
    }
    return;
  }

  if (driversStatus) {
    setStatus(driversStatus, "Process model insights based on historical team data.");
    setTimeout(() => setStatus(driversStatus, ""), 3000);
  }

  buildDriversChart(
    "driversCorrChart",
    driversData.correlations_process || [],
    "abs_spearman",
    "",
    "#1f77b4"
  );
  buildDriversChart(
    "driversRfChart",
    driversData.rf_importance_process || [],
    "importance_mean",
    "",
    "#ff7f0e"
  );
  buildDriversReport(driversData);
  resizePlotsForTab("tab-drivers");

  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      const text = buildDriversReportText(driversData);
      try {
        await navigator.clipboard.writeText(text);
        if (copyStatus) copyStatus.textContent = "Copied!";
      } catch (err) {
        if (copyStatus) copyStatus.textContent = "Copy failed.";
      }
      setTimeout(() => {
        if (copyStatus) copyStatus.textContent = "";
      }, 2000);
    });
  }
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
  const buildVersion = document.getElementById("buildVersion");
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
  const copySummaryBtn = document.getElementById("copySummaryBtn");
  const copySummaryStatus = document.getElementById("copySummaryStatus");
  const exportTableBtn = document.getElementById("exportTableBtn");
  const exportTableStatus = document.getElementById("exportTableStatus");
  const reportSeason = document.getElementById("reportSeason");
  const reportPoints = document.getElementById("reportPoints");
  const reportTeams = document.getElementById("reportTeams");
  const reportMetrics = document.getElementById("reportMetrics");
  const reportRadarMode = document.getElementById("reportRadarMode");
  const reportTop = document.getElementById("reportTop");
  const reportBubble = document.getElementById("reportBubble");
  const reportSimilarity = document.getElementById("reportSimilarity");
  const reportTakeaways = document.getElementById("reportTakeaways");
  const copyReportBtn = document.getElementById("copyReportBtn");
  const copyReportStatus = document.getElementById("copyReportStatus");
  const presetButtons = Array.from(document.querySelectorAll("[data-preset]"));

  const urlState = readUrlState();

  if (buildVersion) {
    buildVersion.textContent = `Build version: ${TEAM_BUILD_VERSION}`;
  }

  const pageUrl = window.location.href;
  const pageOrigin = window.location.origin;
  const pagePathname = window.location.pathname;
  dataDebug.innerHTML = [
    `Page URL: ${pageUrl}`,
    `Origin: ${pageOrigin}`,
    `Pathname: ${pagePathname}`,
    `Data URL: ${dataUrl}`,
    `Drivers URL: ${driversUrl}`
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

  allDataKeys = getAllKeys(rawData);
  initializeMetricOptions();

  rawData.forEach(row => {
    metricOptions.forEach(metric => {
      row[metric] = toNumber(row[metric]);
    });
    zMetricOptions.forEach(metric => {
      row[metric] = toNumber(row[metric]);
    });
    similarityMetricOptions.forEach(metric => {
      if (Object.prototype.hasOwnProperty.call(row, metric)) {
        row[metric] = toNumber(row[metric]);
      }
    });
  });

  allDataKeys = getAllKeys(rawData);
  tableColumnsAvailable = tableColumns.filter(col => allDataKeys.has(col.key));
  if (tableColumnsAvailable.length > 0) {
    tableColumnsAvailable = tableColumnsAvailable.filter(col => {
      if (REQUIRED_TABLE_KEYS.has(col.key)) {
        return true;
      }
      return countNonNull(rawData, col.key) > 0;
    });
  }

  computeSimilarityAvailability(rawData);
  updateDataWarning();
  buildTableHeader();

  buildYearOptions(yearSelect);
  buildMetricOptions(metricSelect);
  buildTopYearOptions(topYearSelect);
  buildTopMetricOptions(topMetricSelect);
  buildTopYearOptions(bubbleYearSelect);
  buildBubbleAxisOptions(bubbleXSelect, "points");
  buildBubbleAxisOptions(bubbleYSelect, "xg_diff");
  buildBubbleMetricOptions(bubbleCompositeSelect);
  bubbleLabelSelect.value = "top10";
  buildMultiSelectOptions(tableYearSelect, Array.from(new Set(rawData.map(row => row.year))).sort((a, b) => a - b), "All seasons", [Math.max(...rawData.map(row => row.year))]);
  buildTableSortOptions(tableSortSelect);

  applySingleSelect(yearSelect, urlState.season);
  applyNumberInput(pointsInput, urlState.minPoints);
  applyMultiSelect(metricSelect, urlState.metrics);
  applySingleSelect(radarModeSelect, urlState.radarMode);
  applyMultiSelect(topYearSelect, urlState.topSeasons);
  applySingleSelect(topMetricSelect, urlState.topMetric);
  applyNumberInput(topNInput, urlState.topN);
  applyMultiSelect(bubbleYearSelect, urlState.bubbleSeasons);
  applySingleSelect(bubbleXSelect, urlState.bubbleX);
  applySingleSelect(bubbleYSelect, urlState.bubbleY);
  applyMultiSelect(bubbleCompositeSelect, urlState.bubbleComposite);
  applySingleSelect(bubbleLabelSelect, urlState.bubbleLabels);
  applyMultiSelect(tableYearSelect, urlState.tableSeasons);
  applyTextInput(tableTeamSearch, urlState.tableSearch);
  applyNumberInput(tablePointsInput, urlState.tableMinPoints);
  applySingleSelect(tableRowsSelect, urlState.tableRows);
  applySingleSelect(tableSortSelect, urlState.tableSort);
  applySingleSelect(tableSortDirSelect, urlState.tableSortDir);

  setStatus(dataStatus, "Data loaded.");
  setTimeout(() => {
    setStatus(dataStatus, "");
  }, 1500);

  initDriversSection();

  const stateRefs = {
    yearSelect,
    pointsInput,
    teamSelect,
    metricSelect,
    radarModeSelect,
    targetSelect,
    topYearSelect,
    topMetricSelect,
    topNInput,
    bubbleYearSelect,
    bubbleXSelect,
    bubbleYSelect,
    bubbleCompositeSelect,
    bubbleLabelSelect,
    tableYearSelect,
    tableTeamSearch,
    tablePointsInput,
    tableRowsSelect,
    tableSortSelect,
    tableSortDirSelect
  };

  const reportElements = {
    reportSeason,
    reportPoints,
    reportTeams,
    reportMetrics,
    reportRadarMode,
    reportTop,
    reportBubble,
    reportSimilarity,
    reportTakeaways
  };

  const updateReportNow = () => updateReport(stateRefs, reportElements);

  const presetControls = {
    metricSelect,
    bubbleXSelect,
    bubbleYSelect,
    bubbleCompositeSelect,
    teamSelect,
    radarModeSelect,
    radarStatus,
    bubbleYearSelect,
    bubbleLabelSelect,
    pointsInput,
    bubbleStatus
  };

  yearSelect.addEventListener("change", () => {
    updateAll(yearSelect, pointsInput, teamSelect, metricSelect, radarModeSelect, targetSelect, radarStatus, similarityStatus, topYearSelect, topMetricSelect, topNInput, topStatus, bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, bubbleStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  pointsInput.addEventListener("change", () => {
    updateAll(yearSelect, pointsInput, teamSelect, metricSelect, radarModeSelect, targetSelect, radarStatus, similarityStatus, topYearSelect, topMetricSelect, topNInput, topStatus, bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, bubbleStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  teamSelect.addEventListener("change", () => {
    updateRadar(teamSelect, metricSelect, radarModeSelect, radarStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  metricSelect.addEventListener("change", () => {
    updateRadar(teamSelect, metricSelect, radarModeSelect, radarStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  radarModeSelect.addEventListener("change", () => {
    updateRadar(teamSelect, metricSelect, radarModeSelect, radarStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  targetSelect.addEventListener("change", () => {
    updateSimilarity(targetSelect, similarityStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });

  topYearSelect.addEventListener("change", () => {
    buildTopTeams(topYearSelect, topMetricSelect, topNInput, topStatus, pointsInput);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  topMetricSelect.addEventListener("change", () => {
    buildTopTeams(topYearSelect, topMetricSelect, topNInput, topStatus, pointsInput);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  topNInput.addEventListener("change", () => {
    buildTopTeams(topYearSelect, topMetricSelect, topNInput, topStatus, pointsInput);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });

  bubbleYearSelect.addEventListener("change", () => {
    buildBubbleChart(bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, pointsInput, bubbleStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  bubbleXSelect.addEventListener("change", () => {
    buildBubbleChart(bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, pointsInput, bubbleStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  bubbleYSelect.addEventListener("change", () => {
    buildBubbleChart(bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, pointsInput, bubbleStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  bubbleCompositeSelect.addEventListener("change", () => {
    buildBubbleChart(bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, pointsInput, bubbleStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  bubbleLabelSelect.addEventListener("change", () => {
    buildBubbleChart(bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, pointsInput, bubbleStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });

  const updateTable = () =>
    buildTeamTable(tableYearSelect, tableTeamSearch, tablePointsInput, tableRowsSelect, tableSortSelect, tableSortDirSelect, tableStatus);

  tableYearSelect.addEventListener("change", () => {
    updateTable();
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  tableTeamSearch.addEventListener("input", () => {
    updateTable();
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  tablePointsInput.addEventListener("change", () => {
    updateTable();
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  tableRowsSelect.addEventListener("change", () => {
    updateTable();
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  tableSortSelect.addEventListener("change", () => {
    updateTable();
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  tableSortDirSelect.addEventListener("change", () => {
    updateTable();
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });

  if (copySummaryBtn) {
    copySummaryBtn.addEventListener("click", async () => {
      const summary = buildSummaryText({
        yearSelect,
        pointsInput,
        teamSelect,
        metricSelect,
        radarModeSelect,
        topYearSelect,
        topMetricSelect,
        topNInput,
        bubbleYearSelect,
        bubbleXSelect,
        bubbleYSelect,
        bubbleCompositeSelect,
        targetSelect
      });
      try {
        await copyToClipboard(summary);
        if (copySummaryStatus) {
          copySummaryStatus.textContent = "Copied.";
          setTimeout(() => {
            copySummaryStatus.textContent = "";
          }, 1500);
        }
      } catch (error) {
        if (copySummaryStatus) {
          copySummaryStatus.textContent = "Copy failed.";
        }
      }
    });
  }

  if (copyReportBtn) {
    copyReportBtn.addEventListener("click", async () => {
      const reportText = buildReportText(stateRefs);
      try {
        await copyToClipboard(reportText);
        if (copyReportStatus) {
          copyReportStatus.textContent = "Copied.";
          setTimeout(() => {
            copyReportStatus.textContent = "";
          }, 1500);
        }
      } catch (error) {
        if (copyReportStatus) {
          copyReportStatus.textContent = "Copy failed.";
        }
      }
    });
  }

  if (exportTableBtn) {
    exportTableBtn.addEventListener("click", () =>
      handleTableExport(tableYearSelect, tableTeamSearch, tablePointsInput, tableRowsSelect, tableSortSelect, tableSortDirSelect, exportTableStatus)
    );
  }

  presetButtons.forEach(button => {
    button.addEventListener("click", () => {
      const presetKey = button.getAttribute("data-preset");
      applyPreset(presetKey, presetControls);
      updateReportNow();
      syncUrlFromControls(stateRefs);
    });
  });

  updateAll(yearSelect, pointsInput, teamSelect, metricSelect, radarModeSelect, targetSelect, radarStatus, similarityStatus, topYearSelect, topMetricSelect, topNInput, topStatus, bubbleYearSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, bubbleStatus);
  applyMultiSelect(teamSelect, urlState.teams);
  applySingleSelect(targetSelect, urlState.similarityTarget);
  updateRadar(teamSelect, metricSelect, radarModeSelect, radarStatus);
  updateSimilarity(targetSelect, similarityStatus);
  updateTable();
  updateReportNow();
  syncUrlFromControls(stateRefs);
}

document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  init();
});
