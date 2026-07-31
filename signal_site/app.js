/* Deepstream landing site — fetches and renders the machine-readable
   signal and track-record endpoints served by deepstream/server.py. */

const $ = (id) => document.getElementById(id);

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const fmtDate = (iso) => {
  const d = new Date(iso);
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
};

const gradeClass = (c) =>
  c === "HIGH" ? "grade-high" : c === "MEDIUM" ? "grade-medium" : "grade-low";
const gradeLabel = (c) => c.charAt(0) + c.slice(1).toLowerCase();

const posClass = (d) =>
  d === "LONG" ? "pos-long" : d === "SHORT" ? "pos-short" : "pos-none";

async function fetchJSON(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return res.json();
}

function renderTerminal(signals, generatedAt) {
  const body = $("terminal-body");
  const tradeable = signals.filter((s) => s.status === "ACTIVE");
  $("status-text").textContent = `Last updated — ${fmtDate(generatedAt)}`;

  if (!tradeable.length) {
    body.innerHTML = `
      <div class="terminal-line"><span class="ts">[00:00]</span><span class="val">No tradeable signal this week.</span></div>
      <div class="terminal-line"><span class="ts">[00:00]</span><span class="val">Standing aside is a position.</span></div>`;
    return;
  }

  body.innerHTML = tradeable.map((s, i) => `
    <div class="terminal-line">
      <span class="ts">[${String(i + 1).padStart(2, "0")}:00]</span>
      <span class="val">${s.pair}</span>
    </div>
    <div class="terminal-line">
      <span class="ts"></span>
      <span class="${posClass(s.direction)}">${s.direction}</span>
      <span class="val">${s.entry}</span>
      <span class="accent">r=${Number(s.pearson_r).toFixed(3)}</span>
    </div>`).join("");
}

function renderSignals(signals, generatedAt) {
  const rows = $("signal-rows");
  $("signal-date").textContent = `Last updated — ${fmtDate(generatedAt)}`;

  if (!signals.length) {
    rows.innerHTML = `<tr><td colspan="8" class="table-empty">No data yet. Check back after the next weekly publication.</td></tr>`;
    return;
  }

  rows.innerHTML = signals.map((s) => {
    if (s.status !== "ACTIVE") {
      return `
        <tr>
          <td>${s.pair}</td>
          <td><span class="pos-none">no trade</span></td>
          <td class="num">—</td><td class="num">—</td><td class="num">—</td>
          <td class="num">${Number(s.pearson_r).toFixed(3)}</td>
          <td><span class="grade ${gradeClass(s.confidence)}">${gradeLabel(s.confidence)}</span></td>
          <td class="num">${s.lag_days}d</td>
        </tr>`;
    }
    return `
      <tr>
        <td>${s.pair}</td>
        <td><span class="${posClass(s.direction)}">${s.direction}</span></td>
        <td class="num">${s.entry}</td>
        <td class="num">${s.stop_loss}</td>
        <td class="num">${s.take_profit}</td>
        <td class="num">${Number(s.pearson_r).toFixed(3)}</td>
        <td><span class="grade ${gradeClass(s.confidence)}">${gradeLabel(s.confidence)}</span></td>
        <td class="num">${s.lag_days}d</td>
      </tr>`;
  }).join("");
}

function renderTrackRecord(record) {
  if (!record || !record.statistics) return;
  const st = record.statistics;
  $("kpi-total").textContent = st.total_trades ?? "—";
  $("kpi-winrate").textContent = (st.win_rate_pct != null ? st.win_rate_pct.toFixed(1) : "—") + "%";
  $("kpi-avg").textContent = (st.avg_return_pct != null ? st.avg_return_pct.toFixed(2) : "—") + "%";

  const rows = $("track-rows");
  const byPair = st.by_pair || {};
  const markets = Object.entries(byPair);
  if (!markets.length) {
    rows.innerHTML = `<tr><td colspan="6" class="table-empty">Track record not yet generated.</td></tr>`;
    return;
  }
  rows.innerHTML = markets.map(([name, m]) => `
    <tr>
      <td>${name}</td>
      <td class="num">${m.trades}</td>
      <td class="num">${m.wins}</td>
      <td class="num">${m.losses}</td>
      <td class="num">${Number(m.win_rate_pct).toFixed(1)}%</td>
      <td class="num">${Number(m.avg_return_pct).toFixed(2)}%</td>
    </tr>`).join("");
}

async function init() {
  try {
    const data = await fetchJSON("/latest_signal.json");
    renderTerminal(data.signals || [], data.generated_at);
    renderSignals(data.signals || [], data.generated_at);
  } catch (e) {
    console.error("Failed to load signals:", e);
  }
  try {
    const record = await fetchJSON("/track_record.json");
    renderTrackRecord(record);
  } catch (e) {
    console.error("Failed to load track record:", e);
  }
}

$("buy-btn").addEventListener("click", (e) => {
  e.preventDefault();
  window.location.href = "https://example.com/subscribe";
});

init();
