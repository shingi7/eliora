const ST_BUILD_VERSION = "st-v6-radar-tooltips-20250206";
const dataUrl = `./data/player_st_comparison_features.json?v=${ST_BUILD_VERSION}`;

const metricOptions = [
  "overall_percentile",
  "goal_threat_percentile",
  "link_play_percentile",
  "touches_in_box_per_90",
  "non_pkxg_p90",
  "non_penalty_goals_p90",
  "shots_per_90",
  "shots_on_target_pct",
  "goal_conversion_pct",
  "shooting_impact",
  "offensive_duels_per_90",
  "offensive_duels_won_pct",
  "offensive_duel_impact",
  "key_passes_per_90",
  "passes_to_penalty_area_per_90",
  "accurate_passes_to_penalty_area_pct",
  "penalty_box_passes_impact",
  "xa_per_90"
];

const zMetricOptions = [
  "non_pkxg_p90_z",
  "non_penalty_goals_p90_z",
  "shots_per_90_z",
  "shots_on_target_pct_z",
  "goal_conversion_pct_z",
  "touches_in_box_per_90_z",
  "offensive_duels_per_90_z",
  "offensive_duels_won_pct_z",
  "key_passes_per_90_z",
  "passes_to_penalty_area_per_90_z",
  "accurate_passes_to_penalty_area_pct_z",
  "xa_per_90_z"
];

const chartZMetricOptions = metricOptions.map(metric => `${metric}_z`);

const defaultMetrics = [
  "overall_percentile",
  "goal_threat_percentile",
  "link_play_percentile",
  "non_pkxg_p90",
  "touches_in_box_per_90"
];

const ST_PRESETS = {
  balanced: {
    radar: [
      "overall_percentile",
      "goal_threat_percentile",
      "link_play_percentile",
      "non_pkxg_p90",
      "touches_in_box_per_90"
    ],
    bubbleX: "non_pkxg_p90",
    bubbleY: "goal_conversion_pct",
    bubbleComposite: [
      "overall_percentile",
      "goal_threat_percentile",
      "link_play_percentile",
      "non_pkxg_p90",
      "touches_in_box_per_90"
    ]
  },
  finisher: {
    radar: [
      "goal_threat_percentile",
      "non_penalty_goals_p90",
      "shots_per_90",
      "shots_on_target_pct",
      "goal_conversion_pct"
    ],
    bubbleX: "shots_per_90",
    bubbleY: "goal_conversion_pct",
    bubbleComposite: [
      "goal_threat_percentile",
      "non_penalty_goals_p90",
      "shots_on_target_pct",
      "goal_conversion_pct"
    ]
  },
  link: {
    radar: [
      "link_play_percentile",
      "key_passes_per_90",
      "passes_to_penalty_area_per_90",
      "accurate_passes_to_penalty_area_pct",
      "xa_per_90"
    ],
    bubbleX: "key_passes_per_90",
    bubbleY: "xa_per_90",
    bubbleComposite: [
      "link_play_percentile",
      "key_passes_per_90",
      "passes_to_penalty_area_per_90",
      "xa_per_90"
    ]
  }
};

const tableColumns = [
  { key: "season", label: "Season", type: "int" },
  { key: "player", label: "Player", type: "text" },
  { key: "team", label: "Team", type: "text" },
  { key: "minutes_played", label: "Minutes", type: "int" },
  { key: "overall_percentile", label: "Overall %", type: "num" },
  { key: "goal_threat_percentile", label: "Goal Threat %", type: "num" },
  { key: "link_play_percentile", label: "Link Play %", type: "num" },
  { key: "non_pkxg_p90", label: "Non-PK xG P90", type: "num" },
  { key: "non_penalty_goals_p90", label: "Non-PK Goals P90", type: "num" },
  { key: "shots_per_90", label: "Shots P90", type: "num" },
  { key: "shots_on_target_pct", label: "Shots On Target %", type: "num" },
  { key: "goal_conversion_pct", label: "Goal Conversion %", type: "num" },
  { key: "shooting_impact", label: "Shooting Impact", type: "num" },
  { key: "touches_in_box_per_90", label: "Touches In Box P90", type: "num" },
  { key: "offensive_duels_per_90", label: "Offensive Duels P90", type: "num" },
  { key: "offensive_duels_won_pct", label: "Offensive Duels Won %", type: "num" },
  { key: "offensive_duel_impact", label: "Offensive Duel Impact", type: "num" },
  { key: "key_passes_per_90", label: "Key Passes P90", type: "num" },
  { key: "passes_to_penalty_area_per_90", label: "Passes To Pen Area P90", type: "num" },
  { key: "accurate_passes_to_penalty_area_pct", label: "Accurate Passes To Pen Area %", type: "num" },
  { key: "penalty_box_passes_impact", label: "Penalty Box Passes Impact", type: "num" },
  { key: "xa_per_90", label: "xA P90", type: "num" },
  { key: "xg", label: "xG", type: "num" },
  { key: "non_pkxg", label: "Non-PK xG", type: "num" },
  { key: "penalties_taken", label: "Penalties Taken", type: "num" },
  { key: "possession", label: "Possession", type: "num" },
  { key: "total_stdev", label: "Total Stdev", type: "num" },
  { key: "goal_threat_stdev", label: "Goal Threat Stdev", type: "num" },
  { key: "link_play_stdev", label: "Link Play Stdev", type: "num" }
];

const metricLabels = {
  overall_percentile: "Overall %",
  goal_threat_percentile: "Goal Threat %",
  link_play_percentile: "Link Play %",
  total_stdev: "Total Stdev",
  goal_threat_stdev: "Goal Threat Stdev",
  link_play_stdev: "Link Play Stdev",
  non_pkxg_p90: "Non-PK xG P90",
  non_penalty_goals_p90: "Non-PK Goals P90",
  shots_per_90: "Shots P90",
  shots_on_target_pct: "Shots On Target %",
  goal_conversion_pct: "Goal Conversion %",
  shooting_impact: "Shooting Impact",
  offensive_duels_per_90: "Offensive Duels P90",
  offensive_duels_won_pct: "Offensive Duels Won %",
  offensive_duel_impact: "Offensive Duel Impact",
  touches_in_box_per_90: "Touches In Box P90",
  key_passes_per_90: "Key Passes P90",
  passes_to_penalty_area_per_90: "Passes To Pen Area P90",
  accurate_passes_to_penalty_area_pct: "Accurate Passes To Pen Area %",
  penalty_box_passes_impact: "Penalty Box Passes Impact",
  xa_per_90: "xA P90",
  xg: "xG",
  non_pkxg: "Non-PK xG",
  penalties_taken: "Penalties Taken",
  possession: "Possession"
};

const radarLowerBetter = new Set([]);

const metricHelp = {
  overall_percentile: "Overall percentile for ST role; higher is better.",
  goal_threat_percentile: "Goal threat percentile; higher = stronger scoring threat.",
  link_play_percentile: "Link play percentile; higher = better involvement.",
  total_stdev: "Overall variability (stdev) across model dimensions.",
  goal_threat_stdev: "Goal threat variability (stdev).",
  link_play_stdev: "Link play variability (stdev).",
  non_pkxg_p90: "Non-penalty expected goals per 90.",
  non_penalty_goals_p90: "Non-penalty goals per 90.",
  shots_per_90: "Shots per 90 minutes.",
  shots_on_target_pct: "Share of shots on target (accuracy %).",
  goal_conversion_pct: "Goals per shot (%).",
  shooting_impact: "Shooting impact metric (model-derived).",
  offensive_duels_per_90: "Offensive duels per 90.",
  offensive_duels_won_pct: "Offensive duel win rate (%).",
  offensive_duel_impact: "Offensive duel impact metric (model-derived).",
  touches_in_box_per_90: "Touches in the penalty box per 90.",
  key_passes_per_90: "Key passes per 90.",
  passes_to_penalty_area_per_90: "Passes into the penalty area per 90.",
  accurate_passes_to_penalty_area_pct: "Accuracy % of passes into the penalty area.",
  penalty_box_passes_impact: "Penalty box passes impact (model-derived).",
  xa_per_90: "Expected assists per 90.",
  xg: "Expected goals (total).",
  non_pkxg: "Non-penalty expected goals (total).",
  penalties_taken: "Penalties taken.",
  possession: "Team possession context."
};

const numericMetricKeys = new Set(
  tableColumns
    .filter(col => col.type !== "text")
    .map(col => col.key)
    .concat(metricOptions)
);

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
  return metricLabels[metric] || metric.replace(/_/g, " ");
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
    option.textContent = prettyMetricLabel(metric);
    if (metricHelp[metric]) {
      option.title = metricHelp[metric];
    }
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

  const entries = [];
  const allValues = [];
  selectedPlayers.forEach(id => {
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
    radarStatus.textContent = "No data available for the selected players/metrics.";
    return;
  }

  if (valueShift > 0) {
    radarStatus.textContent = "Values shifted to be non-negative for stacked pizza slices.";
  }

  Plotly.newPlot("radar", traces, {
    polar: {
      radialaxis: { visible: true },
      angularaxis: { tickmode: "array", tickvals: metricAngles, ticktext: selectedMetrics.map(prettyMetricLabel) }
    },
    barmode: "stack",
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
    option.textContent = prettyMetricLabel(metric);
    if (metricHelp[metric]) {
      option.title = metricHelp[metric];
    }
    topMetricSelect.appendChild(option);
  });
  topMetricSelect.value = "overall_percentile";
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
  setSelectedValues(bubbleMetricSelect, defaultMetrics);
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
    if (metricHelp[col.key]) {
      option.title = metricHelp[col.key];
    }
    tableSortSelect.appendChild(option);
  });
  tableSortSelect.value = "overall_percentile";
}

function applyPreset(presetKey, controls) {
  const preset = ST_PRESETS[presetKey];
  if (!preset) {
    return;
  }
  const { metricSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, playerSelect, radarModeSelect, radarStatus, bubbleSeasonSelect, bubbleLabelSelect, minutesInput, bubbleStatus } = controls;
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

  updateRadar(playerSelect, metricSelect, radarModeSelect, radarStatus);
  buildBubbleChart(bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, minutesInput, bubbleStatus);
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
    minMinutes: params.get("min_minutes"),
    players: decodeList(params.get("players")),
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
    tableTeams: decodeList(params.get("table_teams")),
    tableSearch: params.get("table_search"),
    tableMinMinutes: params.get("table_min_minutes"),
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

  setParam("season", state.seasonSelect.value);
  setParam("min_minutes", state.minutesInput.value);
  setListParam("players", normalizeMultiSelection(getSelectedValues(state.playerSelect)));
  setListParam("metrics", normalizeMultiSelection(getSelectedValues(state.metricSelect)));
  setParam("radar_mode", state.radarModeSelect.value);
  setListParam("top_seasons", normalizeMultiSelection(getSelectedValues(state.topSeasonSelect)));
  setParam("top_metric", state.topMetricSelect.value);
  setParam("top_n", state.topNInput.value);
  setListParam("bubble_seasons", normalizeMultiSelection(getSelectedValues(state.bubbleSeasonSelect)));
  setParam("bubble_x", state.bubbleXSelect.value);
  setParam("bubble_y", state.bubbleYSelect.value);
  setListParam("bubble_comp", normalizeMultiSelection(getSelectedValues(state.bubbleCompositeSelect)));
  setParam("bubble_labels", state.bubbleLabelSelect.value);
  setParam("similarity_target", state.targetSelect.value);
  setListParam("table_seasons", normalizeMultiSelection(getSelectedValues(state.tableSeasonSelect)));
  setListParam("table_teams", normalizeMultiSelection(getSelectedValues(state.tableTeamSelect)));
  setParam("table_search", state.tablePlayerSearch.value.trim());
  setParam("table_min_minutes", state.tableMinutesInput.value);
  setParam("table_rows", state.tableRowsSelect.value);
  setParam("table_sort", state.tableSortSelect.value);
  setParam("table_sort_dir", state.tableSortDirSelect.value);

  const query = params.toString();
  const newUrl = query ? `${window.location.pathname}?${query}` : window.location.pathname;
  window.history.replaceState(null, "", newUrl);
}

function getTableDisplayRows(tableSeasonSelect, tableTeamSelect, tablePlayerSearch, tableMinutesInput, tableRowsSelect, tableSortSelect, tableSortDirSelect) {
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

  return { rows: displayRows, total: rows.length, columns: tableColumns };
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
    topStatus.textContent = "Select a metric.";
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
    name: prettyMetricLabel(selectedMetric),
    x: players.map(row => row.player),
    y: values,
    hovertext: yLabels,
    hovertemplate: "%{hovertext}<br>" + prettyMetricLabel(selectedMetric) + ": %{y:.3f}<extra></extra>"
  };

  Plotly.newPlot("topPerformersChart", [trace], {
    margin: { t: 30, b: 160, l: 50, r: 20 },
    xaxis: { tickangle: -30, automargin: true, tickfont: { size: 10 } },
    yaxis: { title: prettyMetricLabel(selectedMetric), automargin: true },
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
  const { rows: displayRows, total } = getTableDisplayRows(tableSeasonSelect, tableTeamSelect, tablePlayerSearch, tableMinutesInput, tableRowsSelect, tableSortSelect, tableSortDirSelect);

  const tbody = document.querySelector("#playerTable tbody");
  tbody.innerHTML = displayRows.map(row => {
    const cells = tableColumns.map(col => `<td>${formatTableValue(row, col)}</td>`).join("");
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
    seasonSelect,
    minutesInput,
    playerSelect,
    metricSelect,
    radarModeSelect,
    topSeasonSelect,
    topMetricSelect,
    topNInput,
    bubbleSeasonSelect,
    bubbleXSelect,
    bubbleYSelect,
    bubbleCompositeSelect,
    targetSelect
  } = state;

  return [
    "ST Prototype Summary",
    `Season filter: ${describeSelection(seasonSelect, true)}`,
    `Min minutes: ${minutesInput.value || 0}`,
    `Radar players: ${describeSelection(playerSelect, true)}`,
    `Radar metrics: ${describeSelection(metricSelect, false, prettyMetricLabel)}`,
    `Radar mode: ${radarModeSelect.value === "z" ? "Z-scores" : "Raw values"}`,
    `Top performers: ${prettyMetricLabel(topMetricSelect.value)} (Top ${topNInput.value})`,
    `Top seasons: ${describeSelection(topSeasonSelect, true)}`,
    `Bubble seasons: ${describeSelection(bubbleSeasonSelect, true)}`,
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
  if (metric === "minutes_played") {
    return String(Math.round(value));
  }
  if (metric.endsWith("_pct") || metric.includes("percentile")) {
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

function buildPlayerTakeaways(selectedRows, selectedMetrics, targetRow) {
  const bullets = [];
  if (selectedRows.length >= 2) {
    const metricPriority = [
      { key: "overall_percentile", label: metricLabels.overall_percentile || "Overall %" },
      { key: "non_pkxg_p90", label: metricLabels.non_pkxg_p90 || "Non-PK xG P90" },
      { key: "goal_conversion_pct", label: metricLabels.goal_conversion_pct || "Goal Conversion %" }
    ];
    metricPriority.forEach(metric => {
      const hasMetric = selectedMetrics.includes(metric.key) || metricOptions.includes(metric.key);
      if (!hasMetric) {
        return;
      }
      const top = getTopRowByMetric(selectedRows, metric.key);
      if (!top) {
        return;
      }
      bullets.push(`Top ${metric.label}: ${rowLabel(top.row)} (${formatReportValue(metric.key, top.value)})`);
    });
  } else if (selectedRows.length === 1) {
    bullets.push("Select at least two players to generate takeaways.");
  } else {
    bullets.push("Select players to generate takeaways.");
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
  const seasonText = describeSelection(state.seasonSelect, true);
  const minutesText = state.minutesInput.value || "0";
  const playersText = describeSelection(state.playerSelect, true);
  const metricsText = describeSelection(state.metricSelect, false, prettyMetricLabel);
  const radarModeText = state.radarModeSelect.value === "z" ? "Z-scores" : "Raw values";
  const topText = `${prettyMetricLabel(state.topMetricSelect.value)} (Top ${state.topNInput.value}) | Seasons: ${describeSelection(state.topSeasonSelect, true)}`;
  const bubbleText = `Seasons: ${describeSelection(state.bubbleSeasonSelect, true)} | X: ${prettyMetricLabel(state.bubbleXSelect.value)} | Y: ${prettyMetricLabel(state.bubbleYSelect.value)} | Composite: ${describeSelection(state.bubbleCompositeSelect, false, prettyMetricLabel)}`;
  const similarityText = state.targetSelect.selectedOptions[0]?.textContent || "None";
  const selectedRows = getSelectedValues(state.playerSelect).map(id => rowById.get(id)).filter(Boolean);
  const targetRow = rowById.get(state.targetSelect.value);
  const takeaways = buildPlayerTakeaways(selectedRows, getSelectedValues(state.metricSelect), targetRow);

  return {
    seasonText,
    minutesText,
    playersText,
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
  elements.reportMinutes.textContent = snapshot.minutesText;
  elements.reportPlayers.textContent = snapshot.playersText;
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
    "ST Current View Report",
    `Season filter: ${snapshot.seasonText}`,
    `Min minutes: ${snapshot.minutesText}`,
    `Radar players: ${snapshot.playersText}`,
    `Radar metrics: ${snapshot.metricsText}`,
    `Radar mode: ${snapshot.radarModeText}`,
    `Top performers: ${snapshot.topText}`,
    `Bubble: ${snapshot.bubbleText}`,
    `Similarity target: ${snapshot.similarityText}`
  ];
  if (snapshot.takeaways.length > 0) {
    lines.push("", "Key Takeaways:");
    snapshot.takeaways.forEach(item => lines.push(`- ${item}`));
  }
  return lines.join("\n");
}

function handleTableExport(tableSeasonSelect, tableTeamSelect, tablePlayerSearch, tableMinutesInput, tableRowsSelect, tableSortSelect, tableSortDirSelect, exportStatus) {
  const { rows: displayRows, columns } = getTableDisplayRows(tableSeasonSelect, tableTeamSelect, tablePlayerSearch, tableMinutesInput, tableRowsSelect, tableSortSelect, tableSortDirSelect);
  if (displayRows.length === 0) {
    exportStatus.textContent = "No rows to export.";
    return;
  }
  const seasonTag = describeSelection(tableSeasonSelect, true).replace(/\s+/g, "-").replace(/[,/]/g, "_") || "all";
  const filename = `st_table_export_${seasonTag}_${formatDateStamp()}.csv`;
  downloadCsv(filename, displayRows, columns);
  exportStatus.textContent = `Exported ${displayRows.length} rows.`;
  setTimeout(() => {
    exportStatus.textContent = "";
  }, 2000);
}

function buildBubbleChart(bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, minutesInput, bubbleStatus) {
  const selectedMetrics = getSelectedValues(bubbleCompositeSelect);
  bubbleStatus.textContent = "";

  if (selectedMetrics.length === 0) {
    Plotly.purge("bubbleChart");
    bubbleStatus.textContent = "Select at least one composite metric.";
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
  const maxDist = candidates.length > 0 ? Math.max(...candidates.map(entry => entry.dist)) : 0;
  const topFive = candidates.slice(0, 5);

  if (topFive.length === 0) {
    similarityStatus.textContent = "No similar players found with complete data.";
    return;
  }

  topFive.forEach(entry => {
    const row = entry.row;
    const similarityPct = maxDist === 0 ? 100 : (1 - entry.dist / maxDist) * 100;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.player}</td>
      <td>${row.season}</td>
      <td>${row.team}</td>
      <td>${row.minutes_played}</td>
      <td>${similarityPct.toFixed(1)}%</td>
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
  const copySummaryBtn = document.getElementById("copySummaryBtn");
  const copySummaryStatus = document.getElementById("copySummaryStatus");
  const exportTableBtn = document.getElementById("exportTableBtn");
  const exportTableStatus = document.getElementById("exportTableStatus");
  const reportSeason = document.getElementById("reportSeason");
  const reportMinutes = document.getElementById("reportMinutes");
  const reportPlayers = document.getElementById("reportPlayers");
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
    numericMetricKeys.forEach(metric => {
      row[metric] = toNumber(row[metric]);
    });
    chartZMetricOptions.forEach(metric => {
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
  buildBubbleAxisOptions(bubbleXSelect, "non_pkxg_p90");
  buildBubbleAxisOptions(bubbleYSelect, "goal_conversion_pct");
  buildBubbleMetricOptions(bubbleCompositeSelect);
  bubbleLabelSelect.value = "top10";
  buildTableSeasonOptions(tableSeasonSelect);
  buildTeamOptions(tableTeamSelect);
  buildTableSortOptions(tableSortSelect);

  applySingleSelect(seasonSelect, urlState.season);
  applyNumberInput(minutesInput, urlState.minMinutes);
  applyMultiSelect(metricSelect, urlState.metrics);
  applySingleSelect(radarModeSelect, urlState.radarMode);
  applyMultiSelect(topSeasonSelect, urlState.topSeasons);
  applySingleSelect(topMetricSelect, urlState.topMetric);
  applyNumberInput(topNInput, urlState.topN);
  applyMultiSelect(bubbleSeasonSelect, urlState.bubbleSeasons);
  applySingleSelect(bubbleXSelect, urlState.bubbleX);
  applySingleSelect(bubbleYSelect, urlState.bubbleY);
  applyMultiSelect(bubbleCompositeSelect, urlState.bubbleComposite);
  applySingleSelect(bubbleLabelSelect, urlState.bubbleLabels);
  applyMultiSelect(tableSeasonSelect, urlState.tableSeasons);
  applyMultiSelect(tableTeamSelect, urlState.tableTeams);
  applyTextInput(tablePlayerSearch, urlState.tableSearch);
  applyNumberInput(tableMinutesInput, urlState.tableMinMinutes);
  applySingleSelect(tableRowsSelect, urlState.tableRows);
  applySingleSelect(tableSortSelect, urlState.tableSort);
  applySingleSelect(tableSortDirSelect, urlState.tableSortDir);

  setStatus(dataStatus, "Data loaded.");
  setTimeout(() => {
    setStatus(dataStatus, "");
  }, 1500);

  const stateRefs = {
    seasonSelect,
    minutesInput,
    playerSelect,
    metricSelect,
    radarModeSelect,
    targetSelect,
    topSeasonSelect,
    topMetricSelect,
    topNInput,
    bubbleSeasonSelect,
    bubbleXSelect,
    bubbleYSelect,
    bubbleCompositeSelect,
    bubbleLabelSelect,
    tableSeasonSelect,
    tableTeamSelect,
    tablePlayerSearch,
    tableMinutesInput,
    tableRowsSelect,
    tableSortSelect,
    tableSortDirSelect
  };

  const reportElements = {
    reportSeason,
    reportMinutes,
    reportPlayers,
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
    playerSelect,
    radarModeSelect,
    radarStatus,
    bubbleSeasonSelect,
    bubbleLabelSelect,
    minutesInput,
    bubbleStatus
  };

  seasonSelect.addEventListener("change", () => {
    updateAll(seasonSelect, minutesInput, playerSelect, metricSelect, radarModeSelect, targetSelect, radarStatus, similarityStatus, topSeasonSelect, topMetricSelect, topNInput, topStatus, bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, bubbleStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  minutesInput.addEventListener("change", () => {
    updateAll(seasonSelect, minutesInput, playerSelect, metricSelect, radarModeSelect, targetSelect, radarStatus, similarityStatus, topSeasonSelect, topMetricSelect, topNInput, topStatus, bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, bubbleStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  playerSelect.addEventListener("change", () => {
    updateRadar(playerSelect, metricSelect, radarModeSelect, radarStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  metricSelect.addEventListener("change", () => {
    updateRadar(playerSelect, metricSelect, radarModeSelect, radarStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  radarModeSelect.addEventListener("change", () => {
    updateRadar(playerSelect, metricSelect, radarModeSelect, radarStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  targetSelect.addEventListener("change", () => {
    updateSimilarity(targetSelect, similarityStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });

  topSeasonSelect.addEventListener("change", () => {
    buildTopPerformers(topSeasonSelect, topMetricSelect, topNInput, topStatus, minutesInput);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  topMetricSelect.addEventListener("change", () => {
    buildTopPerformers(topSeasonSelect, topMetricSelect, topNInput, topStatus, minutesInput);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  topNInput.addEventListener("change", () => {
    buildTopPerformers(topSeasonSelect, topMetricSelect, topNInput, topStatus, minutesInput);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });

  bubbleSeasonSelect.addEventListener("change", () => {
    buildBubbleChart(bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, minutesInput, bubbleStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  bubbleXSelect.addEventListener("change", () => {
    buildBubbleChart(bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, minutesInput, bubbleStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  bubbleYSelect.addEventListener("change", () => {
    buildBubbleChart(bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, minutesInput, bubbleStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  bubbleCompositeSelect.addEventListener("change", () => {
    buildBubbleChart(bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, minutesInput, bubbleStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  bubbleLabelSelect.addEventListener("change", () => {
    buildBubbleChart(bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, minutesInput, bubbleStatus);
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });

  const updateTable = () =>
    buildPlayerTable(tableSeasonSelect, tableTeamSelect, tablePlayerSearch, tableMinutesInput, tableRowsSelect, tableSortSelect, tableSortDirSelect, tableStatus);

  tableSeasonSelect.addEventListener("change", () => {
    updateTable();
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  tableTeamSelect.addEventListener("change", () => {
    updateTable();
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  tablePlayerSearch.addEventListener("input", () => {
    updateTable();
    updateReportNow();
    syncUrlFromControls(stateRefs);
  });
  tableMinutesInput.addEventListener("change", () => {
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
        seasonSelect,
        minutesInput,
        playerSelect,
        metricSelect,
        radarModeSelect,
        topSeasonSelect,
        topMetricSelect,
        topNInput,
        bubbleSeasonSelect,
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
      handleTableExport(tableSeasonSelect, tableTeamSelect, tablePlayerSearch, tableMinutesInput, tableRowsSelect, tableSortSelect, tableSortDirSelect, exportTableStatus)
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

  updateAll(seasonSelect, minutesInput, playerSelect, metricSelect, radarModeSelect, targetSelect, radarStatus, similarityStatus, topSeasonSelect, topMetricSelect, topNInput, topStatus, bubbleSeasonSelect, bubbleXSelect, bubbleYSelect, bubbleCompositeSelect, bubbleLabelSelect, bubbleStatus);
  applyMultiSelect(playerSelect, urlState.players);
  applySingleSelect(targetSelect, urlState.similarityTarget);
  updateRadar(playerSelect, metricSelect, radarModeSelect, radarStatus);
  updateSimilarity(targetSelect, similarityStatus);
  updateTable();
  updateReportNow();
  syncUrlFromControls(stateRefs);
}

document.addEventListener("DOMContentLoaded", init);
