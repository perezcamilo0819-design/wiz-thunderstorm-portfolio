const settingControls = {
  rain: { key: "rain_intensity", output: "rain-out" },
  wind: { key: "wind_intensity", output: "wind-out" },
  thunder: { key: "thunder_volume", output: "thunder-out", scale: 100 },
  lightning: { key: "lightning_brightness", output: "lightning-out", display: value => `${Math.round((value / 255) * 100)}%` },
  close: { key: "close_weight", output: "close-out" },
  medium: { key: "medium_weight", output: "medium-out" },
  far: { key: "far_weight", output: "far-out" },
};

let settingsTimer;
let isRunning = false;
const presetLabels = { relaxing: "Quiet evening", summer: "Summer storm", severe: "Heavy weather", custom: "Custom mix" };

async function request(path, data) {
  const response = await fetch(path, {
    method: data ? "POST" : "GET",
    headers: data ? { "Content-Type": "application/json" } : {},
    body: data ? JSON.stringify(data) : undefined,
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "The local app could not complete that action.");
  return result;
}

function updateRangeFill(input) {
  const percent = ((Number(input.value) - Number(input.min)) / (Number(input.max) - Number(input.min))) * 100;
  input.style.setProperty("--fill", `${percent}%`);
}

function showSetting(id, value) {
  const config = settingControls[id];
  const control = document.getElementById(id);
  const output = document.getElementById(config.output);
  const shown = config.display ? config.display(value) : `${Math.round(value)}%`;
  control.value = value;
  output.value = shown;
  output.textContent = shown;
  updateRangeFill(control);
}

function readSettings() {
  const values = {};
  for (const [id, config] of Object.entries(settingControls)) {
    const control = document.getElementById(id);
    const value = Number(control.value);
    values[config.key] = config.scale ? value / config.scale : value;
  }
  values.min_interval = Number(document.getElementById("min-interval").value);
  values.max_interval = Number(document.getElementById("max-interval").value);
  values.audio_only = document.getElementById("audio-only").checked;
  return values;
}

function updateStrikeMix(settings) {
  const total = settings.close_weight + settings.medium_weight + settings.far_weight || 1;
  for (const [name, weight] of [["close", settings.close_weight], ["medium", settings.medium_weight], ["far", settings.far_weight]]) {
    const percent = (weight / total) * 100;
    document.getElementById(`${name}-bar`).style.width = `${percent}%`;
    const shown = `${Math.round(percent)}%`;
    document.getElementById(`${name}-out`).value = shown;
    document.getElementById(`${name}-out`).textContent = shown;
  }
}

function renderState(state) {
  const connected = state.ready;
  const engineDot = document.getElementById("engine-dot");
  engineDot.className = `connection-dot ${connected ? "ready" : ""}`;
  document.getElementById("engine-status").textContent = connected ? "Storm engine ready" : "Loading local audio";
  const active = state.storm === "Running";
  isRunning = active;
  document.getElementById("storm-state").textContent = active ? "In progress" : state.storm;
  document.getElementById("live-indicator").classList.toggle("active", active);
  document.getElementById("start-label").textContent = active ? "Storm is running" : "Start storm";
  document.getElementById("start-button").disabled = !connected || active;
  document.getElementById("stop-button").disabled = !active;
  document.getElementById("next-strike").textContent = state.next || "--";
  document.getElementById("timer-value").textContent = state.timer || "--";
  document.getElementById("strike-state").textContent = state.strike || "Idle";
  document.getElementById("event-status").textContent = state.event || "Ready when you are";
  document.getElementById("bulb-status").textContent = state.bulbs || "Not connected";
  document.querySelector(".hero-footnote").classList.toggle("active", active);
  document.getElementById("selected-preset").textContent = (presetLabels[state.preset] || "Custom mix").toUpperCase();
  document.querySelectorAll(".preset-card").forEach(card => {
    card.classList.toggle("selected", card.dataset.preset === state.preset);
  });
  for (const [id, config] of Object.entries(settingControls)) {
    if (document.activeElement === document.getElementById(id)) continue;
    let value = state.settings[config.key];
    if (config.scale) value *= config.scale;
    showSetting(id, value);
  }
  if (document.activeElement !== document.getElementById("min-interval")) document.getElementById("min-interval").value = state.settings.min_interval;
  if (document.activeElement !== document.getElementById("max-interval")) document.getElementById("max-interval").value = state.settings.max_interval;
  if (document.activeElement !== document.getElementById("audio-only")) document.getElementById("audio-only").checked = Boolean(state.settings.audio_only);
  updateStrikeMix(state.settings);
}

async function refresh() {
  try {
    renderState(await request("/api/state"));
  } catch (error) {
    document.getElementById("engine-status").textContent = "Local engine unavailable";
    document.getElementById("engine-dot").className = "connection-dot error";
  }
}

function queueSettingsUpdate() {
  updateStrikeMix(readSettings());
  window.clearTimeout(settingsTimer);
  settingsTimer = window.setTimeout(async () => {
    try {
      const result = await request("/api/settings", readSettings());
      document.getElementById("selected-preset").textContent = "CUSTOM MIX";
      document.querySelectorAll(".preset-card").forEach(card => card.classList.remove("selected"));
    } catch (error) {
      setEvent(error.message);
    }
  }, 130);
}

function setEvent(message) {
  document.getElementById("event-status").textContent = message;
}

async function doAction(action, extra = {}) {
  try {
    await request("/api/action", { action, ...extra });
    await refresh();
  } catch (error) {
    setEvent(error.message);
  }
}

document.querySelectorAll("input[type=range]").forEach(input => {
  updateRangeFill(input);
  input.addEventListener("input", () => {
    const config = settingControls[input.id];
    const value = Number(input.value);
    const shown = config.display ? config.display(value) : `${Math.round(value)}%`;
    const output = document.getElementById(config.output);
    output.value = shown;
    output.textContent = shown;
    updateRangeFill(input);
    queueSettingsUpdate();
  });
});

document.querySelectorAll("#min-interval, #max-interval").forEach(input => input.addEventListener("change", queueSettingsUpdate));
document.getElementById("audio-only").addEventListener("change", queueSettingsUpdate);
document.getElementById("start-button").addEventListener("click", () => {
  const selected = document.getElementById("duration").value;
  doAction("start", { duration_minutes: selected === "unlimited" ? null : Number(selected) });
});
document.getElementById("stop-button").addEventListener("click", () => doAction("stop"));
document.getElementById("test-lightning").addEventListener("click", () => doAction("test_lightning", { strike_type: document.getElementById("test-type").value }));
document.getElementById("test-thunder").addEventListener("click", () => doAction("test_thunder", { strike_type: document.getElementById("test-type").value }));
document.querySelectorAll(".preset-card").forEach(card => card.addEventListener("click", async () => {
  try {
    await request("/api/preset", { preset: card.dataset.preset });
    await refresh();
  } catch (error) {
    setEvent(error.message);
  }
}));

refresh();
window.setInterval(refresh, 750);
