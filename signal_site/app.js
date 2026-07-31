/* Deepstream landing site — fetches machine-readable endpoints and renders
   the live signal table, terminal, charts, and track record. */

const $ = (id) => document.getElementById(id);

// Escape server-provided strings before they are placed into innerHTML.
const esc = (value) => String(value ?? "")
  .replace(/&/g, "&amp;")
  .replace(/</g, "&lt;")
  .replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;")
  .replace(/'/g, "&#39;");

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const fmtDate = (iso) => {
  const d = new Date(iso);
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
};

const gradeClass = (c) =>
  c === "HIGH" ? "grade-high" : c === "MEDIUM" ? "grade-medium" : "grade-low";
const gradeLabel = (c) => c.charAt(0) + c.slice(1).toLowerCase();
const posClass = (d) => (d === "LONG" ? "pos-long" : d === "SHORT" ? "pos-short" : "pos-none");

async function fetchJSON(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return res.json();
}

/* ------------------------------------------------------------------ */
/* Terminal + signal table                                             */
/* ------------------------------------------------------------------ */
function renderTerminal(signals, generatedAt) {
  const tradeable = signals.filter((s) => s.status === "ACTIVE");
  $("status-text").textContent = `Last updated — ${fmtDate(generatedAt)}`;
  $("terminal-body").innerHTML = tradeable.length
    ? tradeable.map((s, i) => `
        <div class="terminal-line">
          <span class="ts">[${String(i + 1).padStart(2, "0")}:00]</span>
          <span class="val">${esc(s.pair)}</span>
        </div>
        <div class="terminal-line">
          <span class="ts"></span>
          <span class="${posClass(s.direction)}">${esc(s.direction)}</span>
          <span class="val">${esc(s.entry)}</span>
          <span class="accent">r=${Number(s.pearson_r).toFixed(3)}</span>
        </div>`).join("")
    : `
        <div class="terminal-line"><span class="ts">[00:00]</span><span class="val">No tradeable signal this week.</span></div>
        <div class="terminal-line"><span class="ts">[00:00]</span><span class="val">Standing aside is a position.</span></div>`;
}

function renderSignals(signals, generatedAt) {
  const rows = $("signal-rows");
  $("signal-date").textContent = `Last updated — ${fmtDate(generatedAt)}`;

  if (!signals.length) {
    rows.innerHTML = `<tr><td colspan="9" class="table-empty">No data yet. Check back after the next weekly publication.</td></tr>`;
    return;
  }

  rows.innerHTML = signals.map((s) => {
    if (s.status !== "ACTIVE") {
      return `
        <tr>
          <td>${esc(s.pair)}</td>
          <td><span class="pos-none">no trade</span></td>
          <td class="num">—</td><td class="num">—</td><td class="num">—</td>
          <td class="num">—</td>
          <td class="num">${Number(s.pearson_r).toFixed(3)}</td>
          <td><span class="grade ${gradeClass(s.confidence)}">${esc(gradeLabel(s.confidence))}</span></td>
          <td class="num">${esc(s.lag_days)}d</td>
        </tr>`;
    }
    const rr = s.entry && s.stop_loss
      ? (Math.abs(s.take_profit - s.entry) / Math.abs(s.entry - s.stop_loss)).toFixed(1)
      : "—";
    return `
      <tr>
        <td>${esc(s.pair)}</td>
        <td><span class="${posClass(s.direction)}">${esc(s.direction)}</span></td>
        <td class="num">${esc(s.entry)}</td>
        <td class="num">${esc(s.stop_loss)}</td>
        <td class="num">${esc(s.take_profit)}</td>
        <td class="num">${rr}</td>
        <td class="num">${Number(s.pearson_r).toFixed(3)}</td>
        <td><span class="grade ${gradeClass(s.confidence)}">${esc(gradeLabel(s.confidence))}</span></td>
        <td class="num">${esc(s.lag_days)}d</td>
      </tr>`;
  }).join("");
}

/* ------------------------------------------------------------------ */
/* Charts                                                              */
/* ------------------------------------------------------------------ */
let pairChart = null;
let equityChart = null;
let chartSeries = [];

function chartTheme() {
  const cs = getComputedStyle(document.documentElement);
  return {
    text: cs.getPropertyValue("--text-dim").trim() || "#93a1b0",
    faint: cs.getPropertyValue("--text-faint").trim() || "#5f6f7f",
    grid: "rgba(34, 48, 64, 0.4)",
    accent: cs.getPropertyValue("--accent").trim() || "#4da3ff",
    positive: cs.getPropertyValue("--positive").trim() || "#3dd68c",
  };
}

function renderPairChart(pairId) {
  const t = chartTheme();
  const series = chartSeries.find((s) => String(s.pair_id) === String(pairId));
  if (!series) return;

  const titleEl = $("chart-title");
  if (titleEl) titleEl.textContent = series.pair;
  const lagEl = $("chart-lag");
  if (lagEl) lagEl.textContent = `signal lead — ${series.lag_days}d`;

  if (pairChart) pairChart.destroy();
  pairChart = new Chart($("pairChart"), {
    type: "line",
    data: {
      labels: series.dates,
      datasets: [
        {
          label: series.ocean_col,
          data: series.ocean,
          yAxisID: "y",
          borderColor: t.accent,
          backgroundColor: "rgba(77, 163, 255, 0.08)",
          borderWidth: 1.6,
          pointRadius: 0,
          tension: 0.25,
          fill: true,
        },
        {
          label: series.price_col,
          data: series.price,
          yAxisID: "y1",
          borderColor: t.positive,
          borderWidth: 1.8,
          pointRadius: 0,
          tension: 0.25,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          labels: { color: t.text, font: { family: "JetBrains Mono", size: 11 } },
        },
        tooltip: {
          backgroundColor: "#121922",
          borderColor: "#223040",
          borderWidth: 1,
          titleColor: "#e9eef3",
          bodyColor: "#93a1b0",
          callbacks: {
            title: (items) => items[0]?.label || "",
          },
        },
      },
      scales: {
        x: {
          grid: { color: t.grid },
          ticks: {
            color: t.faint,
            font: { family: "JetBrains Mono", size: 10 },
            maxTicksLimit: 8,
            autoSkip: true,
          },
        },
        y: {
          position: "left",
          grid: { color: t.grid },
          ticks: { color: t.accent, font: { family: "JetBrains Mono", size: 10 } },
        },
        y1: {
          position: "right",
          grid: { drawOnChartArea: false },
          ticks: { color: t.positive, font: { family: "JetBrains Mono", size: 10 } },
        },
      },
    },
  });
}

function renderEquityChart(equity) {
  if (!equity || !equity.length) return;
  const t = chartTheme();
  const total = equity[equity.length - 1];
  const totalEl = $("equity-total");
  if (totalEl) {
    totalEl.textContent = (total >= 0 ? "+" : "") + total.toFixed(1) + "%";
    totalEl.style.color = total >= 0 ? t.positive : t.text;
  }

  if (equityChart) equityChart.destroy();
  equityChart = new Chart($("equityChart"), {
    type: "line",
    data: {
      labels: equity.map((_, i) => `#${i + 1}`),
      datasets: [{
        label: "Cumulative return",
        data: equity,
        borderColor: t.accent,
        backgroundColor: (ctx) => {
          const { chart } = ctx;
          const { ctx: c, chartArea } = chart;
          if (!chartArea) return "transparent";
          const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
          g.addColorStop(0, "rgba(77, 163, 255, 0.22)");
          g.addColorStop(1, "rgba(77, 163, 255, 0)");
          return g;
        },
        borderWidth: 1.8,
        pointRadius: 0,
        tension: 0.2,
        fill: true,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#121922",
          borderColor: "#223040",
          borderWidth: 1,
          titleColor: "#e9eef3",
          bodyColor: "#93a1b0",
          callbacks: {
            label: (item) => {
              const v = item.parsed.y;
              return `Return ${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { color: "transparent" },
          ticks: { display: false },
        },
        y: {
          grid: { color: "rgba(34, 48, 64, 0.4)" },
          ticks: {
            color: t.faint,
            font: { family: "JetBrains Mono", size: 10 },
            callback: (v) => `${v >= 0 ? "+" : ""}${v}%`,
          },
        },
      },
    },
  });
}

function initCharts() {
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      renderPairChart(chip.dataset.pair);
    });
  });
}

/* ------------------------------------------------------------------ */
/* Track record                                                        */
/* ------------------------------------------------------------------ */
function renderTrackRecord(record) {
  if (!record || !record.statistics) return;
  const st = record.statistics;
  $("kpi-total").textContent = st.total_trades ?? "—";
  $("kpi-winrate").textContent = (st.win_rate_pct != null ? st.win_rate_pct.toFixed(1) : "—") + "%";
  $("kpi-avg").textContent = (st.avg_return_pct != null ? st.avg_return_pct.toFixed(2) : "—") + "%";
  $("kpi-wl").textContent = (st.avg_win_pct != null && st.avg_loss_pct != null)
    ? `+${st.avg_win_pct.toFixed(1)} / ${st.avg_loss_pct.toFixed(1)}`
    : "—";

  const rows = $("track-rows");
  const byPair = st.by_pair || {};
  const markets = Object.entries(byPair);
  rows.innerHTML = markets.length
    ? markets.map(([name, m]) => `
        <tr>
          <td>${esc(name)}</td>
          <td class="num">${esc(m.trades)}</td>
          <td class="num">${esc(m.wins)}</td>
          <td class="num">${esc(m.losses)}</td>
          <td class="num">${Number(m.win_rate_pct).toFixed(1)}%</td>
          <td class="num">${Number(m.avg_return_pct).toFixed(2)}%</td>
        </tr>`).join("")
    : `<tr><td colspan="6" class="table-empty">Track record not yet generated.</td></tr>`;

  // Recent outcomes
  const recent = (record.trades || []).slice(-9).reverse();
  $("recent-trades").innerHTML = recent.length
    ? recent.map((t) => {
        const cls = t.outcome === "WIN" ? "ret-win" : t.outcome === "LOSS" ? "ret-loss" : "ret-open";
        const sign = t.return_pct >= 0 ? "+" : "";
        return `
          <div class="recent-card">
            <span class="rc-pair">${esc(t.signal_date)} · ${esc(t.pair)}</span>
            <div class="rc-row">
              <span class="rc-dir ${posClass(t.direction)}">${esc(t.direction)}</span>
              <span class="rc-ret ${cls}">${sign}${Number(t.return_pct).toFixed(1)}%</span>
            </div>
            <div class="rc-row" style="font-family:var(--font-mono);font-size:.72rem;color:var(--text-faint)">
              <span>entry ${esc(t.entry)}</span><span>${esc(t.outcome)}</span>
            </div>
          </div>`;
      }).join("")
    : `<p class="table-empty">No recorded trades yet.</p>`;
}

/* ------------------------------------------------------------------ */
/* Boot                                                                */
/* ------------------------------------------------------------------ */
async function init() {
  try {
    const data = await fetchJSON("/latest_signal.json");
    renderTerminal(data.signals || [], data.generated_at);
    renderSignals(data.signals || [], data.generated_at);
  } catch (e) { console.error("Failed to load signals:", e); }

  try {
    const record = await fetchJSON("/track_record.json");
    renderTrackRecord(record);
  } catch (e) { console.error("Failed to load track record:", e); }

  try {
    const chart = await fetchJSON("/chart_data.json");
    chartSeries = chart.series || [];
    const first = chartSeries[0];
    if (first) renderPairChart(first.pair_id);
    renderEquityChart(chart.equity || []);
    initCharts();
  } catch (e) { console.error("Failed to load chart data:", e); }
}

/* ------------------------------------------------------------------ */
/* Checkout (Cashfree)                                                 */
/* ------------------------------------------------------------------ */

let cashfreeMode = "sandbox";
let cashfreeSdkPromise = null;

function loadCashfreeSdk() {
  if (window.Cashfree) return Promise.resolve(window.Cashfree);
  if (!cashfreeSdkPromise) {
    cashfreeSdkPromise = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://sdk.cashfree.com/js/v3/cashfree.js";
      s.onload = () => resolve(window.Cashfree);
      s.onerror = () => reject(new Error("Cashfree SDK failed to load"));
      document.head.appendChild(s);
    });
  }
  return cashfreeSdkPromise;
}

function setCheckoutStatus(msg, isError = false) {
  const el = $("co-status");
  if (el) {
    el.textContent = msg;
    el.classList.toggle("checkout-error", isError);
  }
}

async function startCheckout() {
  const email = ($("co-email").value || "").trim();
  const phone = ($("co-phone").value || "").trim();
  const submit = $("co-submit");
  if (!/^\S+@\S+\.\S+$/.test(email)) {
    setCheckoutStatus("Please enter a valid email.", true);
    return;
  }
  submit.disabled = true;
  setCheckoutStatus("Creating your order…");
  try {
    const res = await fetch("/api/create-order", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ customer_email: email, customer_phone: phone }),
    });
    const order = await res.json();
    if (!res.ok || !order.payment_session_id) throw new Error("order creation failed");
    // Remember the order id so success.html can poll even if the redirect
    // drops the query parameter.
    sessionStorage.setItem("deepstream_order_id", order.order_id);

    const Cashfree = await loadCashfreeSdk();
    const cashfree = Cashfree({ mode: cashfreeMode });
    const result = await cashfree.checkout({
      paymentSessionId: order.payment_session_id,
      redirectTarget: "_self",
      // Pass order_id explicitly so success.html can poll even if Cashfree
      // omits it from the redirect query (sessionStorage is a backup).
      returnUrl: `${location.origin}/success.html?order_id=${encodeURIComponent(order.order_id)}`,
    });
    if (result && result.error) {
      setCheckoutStatus("Payment could not be completed. Please try again.", true);
      submit.disabled = false;
    }
  } catch (e) {
    console.error("Checkout failed:", e);
    setCheckoutStatus("Could not start checkout. Please try again.", true);
    submit.disabled = false;
  }
}

async function openCheckoutModal() {
  const modal = $("checkout-modal");
  if (!modal) return;
  setCheckoutStatus("");
  // Open the modal first so the status line is visible even when the
  // config fetch fails below. Keep submit disabled until the config loads so
  // the SDK mode (sandbox vs production) is always correct.
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  $("co-submit").disabled = true;
  try {
    const cfg = await fetchJSON("/api/payments_config");
    if (!cfg.configured) {
      setCheckoutStatus("Checkout is temporarily unavailable.", true);
      return;
    }
    cashfreeMode = cfg.mode;
    const amount = `${cfg.currency === "USD" ? "$" : ""}${cfg.amount}${cfg.currency !== "USD" ? " " + cfg.currency : ""}`;
    if ($("co-amount")) $("co-amount").textContent = amount;
    if ($("co-submit")) {
      $("co-submit").textContent = `Pay ${amount} — Subscribe`;
      $("co-submit").disabled = false;
    }
    if ($("co-email")) $("co-email").focus();
  } catch (e) {
    console.error("Failed to load payments config:", e);
    setCheckoutStatus("Checkout is temporarily unavailable.", true);
  }
}

function closeCheckoutModal() {
  const modal = $("checkout-modal");
  if (modal) {
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
  }
}

const buyBtn = $("buy-btn");
if (buyBtn) {
  buyBtn.addEventListener("click", (e) => {
    e.preventDefault();
    openCheckoutModal();
  });
}

const coSubmit = $("co-submit");
if (coSubmit) coSubmit.addEventListener("click", startCheckout);

document.querySelectorAll("[data-close-checkout]").forEach((el) => {
  el.addEventListener("click", closeCheckoutModal);
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeCheckoutModal();
});

init();
