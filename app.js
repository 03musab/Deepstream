// Deepstream - Operations Dashboard Controller
document.addEventListener("DOMContentLoaded", () => {
    // Initialise Lucide Icons
    lucide.createIcons();

    // ---- Transient feedback toast ---------------------------------------
    let toastTimer = null;
    function showToast(message) {
        const toast = document.getElementById("app-toast");
        if (!toast) return;
        toast.textContent = message;
        toast.classList.add("show");
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => toast.classList.remove("show"), 3200);
    }

    // ---- Offline / empty-state banner -----------------------------------
    // If the compiled dataset is missing the console still renders, but the
    // user gets a clear signal that charts will be empty.
    if (typeof NEPTUNE_DATA_STORE === "undefined") {
        const banner = document.getElementById("offline-banner");
        if (banner) banner.classList.remove("hidden");
        showToast("Offline mode — dataset unavailable. Rebuild data-store.js to enable charts.");
    }

    // ---- Mobile navigation (off-canvas drawer) ---------------------------
    const menuToggleOpen = document.getElementById("menu-toggle-open");
    const menuToggle = document.getElementById("menu-toggle");
    function setNavOpen(open) {
        document.body.classList.toggle("nav-open", open);
        if (menuToggleOpen) menuToggleOpen.setAttribute("aria-expanded", String(open));
        if (menuToggle) menuToggle.setAttribute("aria-expanded", String(!open));
    }
    if (menuToggleOpen) menuToggleOpen.addEventListener("click", () => setNavOpen(true));
    if (menuToggle) menuToggle.addEventListener("click", () => setNavOpen(false));
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") setNavOpen(false);
    });
    // Tap outside the drawer (or the open button) to dismiss it on mobile.
    document.addEventListener("click", (e) => {
        if (!document.body.classList.contains("nav-open")) return;
        if (e.target.closest("#sidebar") || e.target.closest("#menu-toggle-open")) return;
        setNavOpen(false);
    });

    // Application State
    const state = {
        activeTab: "terminal",
        selectedZone: "Alpha",
        selectedCommodity: "copper",
        modeler: {
            auvs: 20,
            starterPrice: 120000,
            proPrice: 500000,
            enterprisePrice: 2000000
        }
    };

    // Configuration Data
    const zoneData = {
        Alpha: {
            name: "ALPHA (ENSO)",
            coords: "0.528° S, 120.449° W",
            variable: "SST Anomaly (°C)",
            commodity: "Copper Futures (HG=F)",
            commodityKey: "copper",
            r: "0.9135",
            lead: "8 Weeks (56 Days)",
            confidence: "94.8%"
        },
        Beta: {
            name: "BETA (GoM)",
            coords: "26.312° N, 88.754° W",
            variable: "Chemical Plume index",
            commodity: "Crude Oil Futures (CL=F)",
            commodityKey: "oil",
            r: "0.6026",
            lead: "2 Weeks (14 Days)",
            confidence: "78.2%"
        },
        Gamma: {
            name: "GAMMA (Atlantic)",
            coords: "58.450° N, 12.180° W",
            variable: "Chlorophyll Index (mg/m³)",
            commodity: "North Sea Tuna Prices",
            commodityKey: "tuna",
            r: "-0.9498",
            lead: "4 Weeks (28 Days)",
            confidence: "96.1%"
        },
        Delta: {
            name: "DELTA (Indian)",
            coords: "12.920° N, 60.110° E",
            variable: "Current Flow (m/s)",
            commodity: "Shipping route risk Index",
            commodityKey: "oil", // Reuses oil or general forecast
            r: "0.7812",
            lead: "3 Weeks (21 Days)",
            confidence: "88.5%"
        },
        Epsilon: {
            name: "EPSILON (Arctic)",
            coords: "78.115° N, 42.902° E",
            variable: "Ice density anomaly (%)",
            commodity: "Ice routing costs",
            commodityKey: "copper", // Reuses copper
            r: "0.8415",
            lead: "6 Weeks (42 Days)",
            confidence: "91.2%"
        }
    };

    // Pearson Correlation Coefficient calculation
    function calculatePearsonCorrelation(x, y) {
        const n = x.length;
        if (n === 0) return 0;
        const meanX = x.reduce((a, b) => a + b, 0) / n;
        const meanY = y.reduce((a, b) => a + b, 0) / n;
        
        let num = 0;
        let denX = 0;
        let denY = 0;
        
        for (let i = 0; i < n; i++) {
            const diffX = x[i] - meanX;
            const diffY = y[i] - meanY;
            num += diffX * diffY;
            denX += diffX * diffX;
            denY += diffY * diffY;
        }
        
        if (denX === 0 || denY === 0) return 0;
        return num / Math.sqrt(denX * denY);
    }

    // Pre-build index maps for faster daily calculations
    const dailyOceanMaps = {};
    const sstMap = {};
    if (typeof NEPTUNE_DATA_STORE !== 'undefined') {
        NEPTUNE_DATA_STORE.sst.forEach(item => {
            sstMap[item.date.substring(0, 7)] = item.val;
        });
    }

    // Aligns commodity and ocean time-series with lag shifting
    function alignAndLagData(oceanKey, commodityKey, lagDays) {
        if (typeof NEPTUNE_DATA_STORE === 'undefined') {
            return { dates: [], ocean: [], commodity: [] };
        }
        
        const oceanData = NEPTUNE_DATA_STORE[oceanKey] || [];
        const commodityData = NEPTUNE_DATA_STORE[commodityKey] || [];
        
        // Create lookup map for commodity data: date -> val
        const commodityMap = {};
        commodityData.forEach(item => {
            commodityMap[item.date] = item.val;
        });
        
        const alignedOcean = [];
        const alignedCommodity = [];
        const alignedDates = [];
        
        // Sort dates to ensure chronological ordering
        const sortedCommodityDates = commodityData.map(item => item.date).sort();
        
        sortedCommodityDates.forEach(dateStr => {
            // targetDateObj = date - lagDays
            const dateParts = dateStr.split('-');
            const dateObj = new Date(parseInt(dateParts[0]), parseInt(dateParts[1]) - 1, parseInt(dateParts[2]));
            dateObj.setDate(dateObj.getDate() - lagDays);
            
            // Format back as YYYY-MM-DD
            const y = dateObj.getFullYear();
            const m = String(dateObj.getMonth() + 1).padStart(2, '0');
            const d = String(dateObj.getDate()).padStart(2, '0');
            const laggedDateStr = `${y}-${m}-${d}`;
            
            let oceanVal = null;
            if (oceanKey === 'sst') {
                const ym = laggedDateStr.substring(0, 7);
                oceanVal = sstMap[ym];
                if (oceanVal === undefined) {
                    const matchingMonths = NEPTUNE_DATA_STORE.sst.filter(item => item.date <= laggedDateStr);
                    if (matchingMonths.length > 0) {
                        oceanVal = matchingMonths[matchingMonths.length - 1].val;
                    } else {
                        oceanVal = NEPTUNE_DATA_STORE.sst[0].val;
                    }
                }
            } else {
                if (!dailyOceanMaps[oceanKey]) {
                    dailyOceanMaps[oceanKey] = {};
                    oceanData.forEach(item => {
                        dailyOceanMaps[oceanKey][item.date] = item.val;
                    });
                }
                oceanVal = dailyOceanMaps[oceanKey][laggedDateStr];
            }
            
            if (oceanVal !== null && oceanVal !== undefined) {
                alignedOcean.push(oceanVal);
                alignedCommodity.push(commodityMap[dateStr]);
                alignedDates.push(dateStr);
            }
        });
        
        return {
            dates: alignedDates,
            ocean: alignedOcean,
            commodity: alignedCommodity
        };
    }

    let forecastChart = null;
    let modelerChart = null;

    // Mapping commodities to ocean signals & labels
    const commodityConfigMap = {
        copper: {
            oceanKey: 'sst',
            label: "Copper Price ($/lb)",
            oceanLabel: "Pacific SST Anomaly (°C)",
            defaultLag: 56
        },
        tuna: {
            oceanKey: 'chlorophyll',
            label: "Tuna Price ($/kg)",
            oceanLabel: "Atlantic Chlorophyll Index (mg/m³)",
            defaultLag: 28
        },
        oil: {
            oceanKey: 'plume',
            label: "Crude Oil Price ($/bbl)",
            oceanLabel: "GoM Plume Concentration Index",
            defaultLag: 14
        }
    };

    // Initialize/Update Forecast Chart
    function initForecastChart(commodity) {
        const ctx = document.getElementById('forecastChart');
        if (!ctx) return;

        // Show a brief loading state so slider scrubbing feels responsive.
        const loading = document.getElementById("chart-loading");
        if (loading) {
            loading.classList.remove("is-loading");
            loading.setAttribute("aria-hidden", "false");
        }
        
        const config = commodityConfigMap[commodity];
        const lagInput = document.getElementById("lag-slider-input");
        const lagDays = lagInput ? parseInt(lagInput.value) : config.defaultLag;
        
        // Dynamic alignment and calculation
        const aligned = alignAndLagData(config.oceanKey, commodity, lagDays);
        
        // Calculate statistical correlation over the entire history
        const r = calculatePearsonCorrelation(aligned.ocean, aligned.commodity);
        
        // Update dashboard metrics
        document.getElementById("corr-val").textContent = r.toFixed(4);
        document.getElementById("lead-val").textContent = `${Math.round(lagDays / 7)} Weeks (${lagDays} Days)`;
        
        const confidence = Math.min(99.9, Math.max(10.0, Math.abs(r) * 105)).toFixed(1) + "%";
        document.getElementById("conf-val").textContent = confidence;
        
        // Sub-sample tail for plotting (last 90 data points)
        const tailLength = 90;
        const chartDates = aligned.dates.slice(-tailLength).map(dateStr => {
            const parts = dateStr.split('-');
            const d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
            return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        });
        const chartPrices = aligned.commodity.slice(-tailLength);
        const chartOcean = aligned.ocean.slice(-tailLength);

        if (forecastChart) {
            forecastChart.destroy();
        }

        forecastChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartDates,
                datasets: [
                    {
                        label: config.label,
                        data: chartPrices,
                        borderColor: '#4facfe',
                        backgroundColor: 'rgba(79, 172, 254, 0.05)',
                        borderWidth: 2,
                        yAxisID: 'yPrice',
                        tension: 0.3,
                        fill: true
                    },
                    {
                        label: config.oceanLabel,
                        data: chartOcean,
                        borderColor: '#00e676',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        yAxisID: 'yOcean',
                        tension: 0.3,
                        fill: false
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            color: '#8a9fc4',
                            font: { family: 'Outfit', size: 11 }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.02)' },
                        ticks: { color: '#536a8d', font: { family: 'Inter', size: 10 } }
                    },
                    yPrice: {
                        type: 'linear',
                        position: 'left',
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#4facfe', font: { family: 'Inter', size: 10 } },
                        title: { display: true, text: 'Commodity Price', color: '#4facfe', font: { family: 'Outfit', size: 12 } }
                    },
                    yOcean: {
                        type: 'linear',
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        ticks: { color: '#00e676', font: { family: 'Inter', size: 10 } },
                        title: { display: true, text: 'Ocean Index (Lagged)', color: '#00e676', font: { family: 'Outfit', size: 12 } }
                    }
                }
            }
        });
    }

    // Handles Map Node Clicks
    const zoneMarkers = document.querySelectorAll(".zone-marker");
    const lagSlider = document.getElementById("lag-slider-input");
    const lagSliderVal = document.getElementById("lag-slider-val");
    
    zoneMarkers.forEach(marker => {
        // Keyboard access: Enter/Space activate a zone like a click.
        marker.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                marker.click();
            }
        });

        marker.addEventListener("click", () => {
            zoneMarkers.forEach(m => m.classList.remove("active-target"));
            marker.classList.add("active-target");
            
            const zoneKey = marker.getAttribute("data-zone");
            state.selectedZone = zoneKey;
            
            const info = zoneData[zoneKey];
            
            // Update Spec Panel Elements
            document.getElementById("spec-zone").textContent = info.name;
            document.getElementById("spec-coords").textContent = info.coords;
            document.getElementById("spec-variable").textContent = info.variable;
            document.getElementById("spec-commodity").textContent = info.commodity;
            
            // Force dropdown change
            const comSelect = document.getElementById("commodity-select");
            comSelect.value = info.commodityKey;
            state.selectedCommodity = info.commodityKey;
            
            // Update slider value to default lag for this zone/commodity
            const config = commodityConfigMap[info.commodityKey];
            if (lagSlider && lagSliderVal) {
                lagSlider.value = config.defaultLag;
                lagSliderVal.textContent = `${config.defaultLag} Days`;
            }
            
            // Re-render chart (which automatically calculates correlation and updates DOM labels)
            initForecastChart(info.commodityKey);
            
            // Log target change
            addLogLine(`[TARGET] Switched telemetry center to ${info.name}. Coordinating downlink...`, "info");
        });
    });

    // Handle Dropdown changes directly
    const comSelect = document.getElementById("commodity-select");
    if (comSelect) {
        comSelect.addEventListener("change", (e) => {
            const comVal = e.target.value;
            state.selectedCommodity = comVal;
            
            // Update slider value to default lag for this commodity
            const config = commodityConfigMap[comVal];
            if (lagSlider && lagSliderVal) {
                lagSlider.value = config.defaultLag;
                lagSliderVal.textContent = `${config.defaultLag} Days`;
            }
            
            initForecastChart(comVal);
            addLogLine(`[SYS] Recalibrating Deepstream-GPT neural weights for commodity index matching: ${comVal.toUpperCase()}`, "system");
        });
    }

    // Handle Lag Slider changes
    if (lagSlider && lagSliderVal) {
        lagSlider.addEventListener("input", (e) => {
            const lagVal = parseInt(e.target.value);
            lagSliderVal.textContent = `${lagVal} Days`;
            initForecastChart(state.selectedCommodity);
        });
    }

    // Log Streamer simulation
    const logBox = document.getElementById("console-log");
    function addLogLine(text, type = "info") {
        if (!logBox) return;
        const line = document.createElement("div");
        line.className = `log-line ${type}`;
        
        const time = new Date().toISOString().slice(11, 19);
        line.innerHTML = `<span class="system">[${time}]</span> ${text}`;
        
        logBox.appendChild(line);
        logBox.scrollTop = logBox.scrollHeight;
        
        // Cap logs at 30 items
        while (logBox.children.length > 30) {
            logBox.removeChild(logBox.firstChild);
        }
    }

    const logMessages = [
        () => `[UPLINK] AUV-0${Math.floor(Math.random()*9+1)}: Depth: ${Math.floor(Math.random()*400+100)}m | Temp anomaly: ${(Math.random()*1.5-0.5).toFixed(2)}°C`,
        () => `[COPERNICUS] Stream hourly current profile aligned for Zone: ${state.selectedZone.toUpperCase()}`,
        () => `[NEPTUNE-GPT] Forward forecast signal generated. Sharpe projection: ${(Math.random()*0.8+0.5).toFixed(2)}`,
        () => `[SATELLITE] Iridium burst complete. Upload size: ${Math.floor(Math.random()*15+5)}KB. Error rate: 0.00%`,
        () => `[UPLINK] AUV-1${Math.floor(Math.random()*9)}: Chlorophyll density matches trend anomaly: -${Math.floor(Math.random()*10+5)}%`,
        () => `[SYS] Calibrating ADCP acoustic sensor arrays in zone ${state.selectedZone.toUpperCase()}`
    ];

    setInterval(() => {
        if (state.activeTab === "terminal") {
            const randomMsg = logMessages[Math.floor(Math.random() * logMessages.length)]();
            const types = ["info", "success", "info", "system"];
            const randomType = types[Math.floor(Math.random() * types.length)];
            addLogLine(randomMsg, randomType);
        }
    }, 4500);

    // Live clock update
    setInterval(() => {
        const clockEl = document.getElementById("live-clock");
        if (clockEl) {
            clockEl.textContent = new Date().toUTCString().slice(17, 25) + " UTC";
        }
    }, 1000);

    // Initial Tab Navigation
    const navItems = document.querySelectorAll(".nav-item");
    const mainContent = document.querySelector(".main-content");

    navItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            navItems.forEach(n => n.classList.remove("active"));
            item.classList.add("active");
            
            // Close the off-canvas drawer on mobile once a section is chosen.
            setNavOpen(false);
            
            const targetTab = item.getAttribute("data-tab");
            state.activeTab = targetTab;
            
            // Clean up main workspace layout
            const consolePanel = document.getElementById("terminal-tab");
            if (targetTab === "terminal") {
                consolePanel.classList.remove("hidden");
                // Remove other tab structures if created
                removeDynamicTabs();
                document.getElementById("page-title").textContent = "Operations Console";
                initForecastChart(state.selectedCommodity);
            } else {
                consolePanel.classList.add("hidden");
                removeDynamicTabs();
                renderDynamicTab(targetTab);
            }
        });
    });

    function removeDynamicTabs() {
        const dyTabs = ["zones-dynamic", "modeler-dynamic"];
        dyTabs.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.remove();
        });
    }

    function renderDynamicTab(tabName) {
        if (tabName === "zones") {
            document.getElementById("page-title").textContent = "AUV Fleet Deployments";
            const grid = document.createElement("div");
            grid.id = "zones-dynamic";
            grid.className = "workspace-grid full-width-panel";
            grid.innerHTML = `
                <div class="panel full-width-panel">
                    <h2 class="panel-title" style="margin-bottom: 20px; color: var(--color-cyan);">Deployment Zones Overview</h2>
                    <div class="table-scroll">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Zone</th>
                                    <th>Coordinates</th>
                                    <th>Primary Ocean Indicator</th>
                                    <th>Target Commodity</th>
                                    <th>Pearson Correlation</th>
                                    <th>Forecast Lead Time</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td style="font-weight:600;">Alpha (Pacific Ring)</td>
                                    <td class="mono">0.528° S, 120.449° W</td>
                                    <td>SST Anomaly (ENSO)</td>
                                    <td>Copper Futures (HG=F)</td>
                                    <td class="text-glow">r = 0.9135</td>
                                    <td>8 Weeks</td>
                                    <td><span class="badge badge-success">ACTIVE</span></td>
                                </tr>
                                <tr>
                                    <td style="font-weight:600;">Beta (Gulf of Mexico)</td>
                                    <td class="mono">26.312° N, 88.754° W</td>
                                    <td>Chemical Plume index</td>
                                    <td>Crude Oil (CL=F)</td>
                                    <td style="color: var(--color-amber);">r = 0.6026</td>
                                    <td>2 Weeks</td>
                                    <td><span class="badge badge-success">ACTIVE</span></td>
                                </tr>
                                <tr>
                                    <td style="font-weight:600;">Gamma (North Atlantic)</td>
                                    <td class="mono">58.450° N, 12.180° W</td>
                                    <td>Chlorophyll density drop</td>
                                    <td>North Sea Tuna Prices</td>
                                    <td class="text-glow">r = -0.9498</td>
                                    <td>4 Weeks</td>
                                    <td><span class="badge badge-success">ACTIVE</span></td>
                                </tr>
                                <tr>
                                    <td style="font-weight:600;">Delta (Indian Ocean)</td>
                                    <td class="mono">12.920° N, 60.110° E</td>
                                    <td>Current flows & Chemistry</td>
                                    <td>Shipping Route Risks</td>
                                    <td style="color: var(--color-cyan);">r = 0.7812</td>
                                    <td>3 Weeks</td>
                                    <td><span class="badge badge-cyan">PENDING P2</span></td>
                                </tr>
                                <tr>
                                    <td style="font-weight:600;">Epsilon (Arctic Passage)</td>
                                    <td class="mono">78.115° N, 42.902° E</td>
                                    <td>Ice density anomaly</td>
                                    <td>Rare Earth / Ice Routing</td>
                                    <td style="color: var(--color-cyan);">r = 0.8415</td>
                                    <td>6 Weeks</td>
                                    <td><span class="badge badge-cyan">PENDING P2</span></td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
            mainContent.appendChild(grid);
            lucide.createIcons();
        } else if (tabName === "modeler") {
            document.getElementById("page-title").textContent = "Financial Projection Modeler";
            const grid = document.createElement("div");
            grid.id = "modeler-dynamic";
            grid.className = "workspace-grid";
            grid.style.gridTemplateColumns = "1.2fr 1.8fr";
            
            grid.innerHTML = `
                <div class="panel modeler-controls">
                    <h2 class="panel-title" style="color:var(--color-cyan);">Variable Modeler</h2>
                    
                    <div class="slider-group">
                        <div class="slider-label-group">
                            <span>Target Client Fleet Size (AUVs)</span>
                            <span id="val-auv" class="text-glow">20</span>
                        </div>
                        <input type="range" class="slider-input" id="slide-auv" min="5" max="300" value="20">
                    </div>
                    
                    <div class="slider-group">
                        <div class="slider-label-group">
                            <span>Starter Subscription Price ($/yr)</span>
                            <span id="val-starter" class="text-glow">$120K</span>
                        </div>
                        <input type="range" class="slider-input" id="slide-starter" min="50000" max="300000" step="10000" value="120000">
                    </div>
                    
                    <div class="slider-group">
                        <div class="slider-label-group">
                            <span>Pro Subscription Price ($/yr)</span>
                            <span id="val-pro" class="text-glow">$500K</span>
                        </div>
                        <input type="range" class="slider-input" id="slide-pro" min="200000" max="1000000" step="50000" value="500000">
                    </div>
                    
                    <div class="slider-group">
                        <div class="slider-label-group">
                            <span>Enterprise Price ($/yr)</span>
                            <span id="val-enterprise" class="text-glow">$2.0M</span>
                        </div>
                        <input type="range" class="slider-input" id="slide-enterprise" min="1000000" max="5000000" step="100000" value="2000000">
                    </div>
                </div>
                
                <div class="panel" style="padding: 24px; display: flex; flex-direction: column;">
                    <h2 class="panel-title" style="margin-bottom: 20px;">Projected Revenue Target (ARR Growth)</h2>
                    <div style="flex-grow: 1; position: relative; height: 300px;">
                        <canvas id="modelerChart"></canvas>
                    </div>
                </div>
            `;
            mainContent.appendChild(grid);
            lucide.createIcons();
            
            // Initialise Modeler Chart
            initModelerChart();
            
            // Add listeners to Sliders
            setupModelerListeners();
        }
    }

    function initModelerChart() {
        const ctx = document.getElementById("modelerChart");
        if (!ctx) return;

        // Calculate projections based on active state variables
        const arrProjections = calculateProjections();

        modelerChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Year 1', 'Year 2', 'Year 3', 'Year 4', 'Year 5'],
                datasets: [{
                    label: 'Projected ARR ($ Millions)',
                    data: arrProjections,
                    backgroundColor: 'rgba(0, 242, 254, 0.45)',
                    borderColor: '#00f2fe',
                    borderWidth: 1.5,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: '#8a9fc4', font: { family: 'Outfit', size: 11 } }
                    },
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { 
                            color: '#8a9fc4', 
                            font: { family: 'Inter', size: 10 },
                            callback: function(value) { return '$' + value + 'M'; }
                        }
                    }
                }
            }
        });
    }

    function calculateProjections() {
        // Base multipliers for clients at Year 1 to 5
        // Y1: 1 client ($15k/trial) -> Y5: 83 clients
        const clientsByYear = {
            y1: { starter: 2, pro: 0, enterprise: 0 },
            y2: { starter: 10, pro: 2, enterprise: 0 },
            y3: { starter: 30, pro: 8, enterprise: 2 },
            y4: { starter: 45, pro: 15, enterprise: 6 },
            y5: { starter: 50, pro: 20, enterprise: 10 }
        };
        
        // Multiplier based on AUV count (increases client capacity & data value)
        const auvMultiplier = 1 + (state.modeler.auvs - 20) / 200;

        const projections = [
            // Year 1
            ((clientsByYear.y1.starter * state.modeler.starterPrice) / 1000000).toFixed(2),
            // Year 2
            (( (clientsByYear.y2.starter * state.modeler.starterPrice) + (clientsByYear.y2.pro * state.modeler.proPrice) ) * auvMultiplier / 1000000).toFixed(2),
            // Year 3
            (( (clientsByYear.y3.starter * state.modeler.starterPrice) + (clientsByYear.y3.pro * state.modeler.proPrice) + (clientsByYear.y3.enterprise * state.modeler.enterprisePrice) ) * auvMultiplier / 1000000).toFixed(2),
            // Year 4
            (( (clientsByYear.y4.starter * state.modeler.starterPrice) + (clientsByYear.y4.pro * state.modeler.proPrice) + (clientsByYear.y4.enterprise * state.modeler.enterprisePrice) ) * auvMultiplier / 1000000).toFixed(2),
            // Year 5
            (( (clientsByYear.y5.starter * state.modeler.starterPrice) + (clientsByYear.y5.pro * state.modeler.proPrice) + (clientsByYear.y5.enterprise * state.modeler.enterprisePrice) ) * auvMultiplier / 1000000).toFixed(2)
        ];

        return projections.map(parseFloat);
    }

    function setupModelerListeners() {
        const slideAuv = document.getElementById("slide-auv");
        const slideStarter = document.getElementById("slide-starter");
        const slidePro = document.getElementById("slide-pro");
        const slideEnterprise = document.getElementById("slide-enterprise");

        if (slideAuv) {
            slideAuv.addEventListener("input", (e) => {
                const val = parseInt(e.target.value);
                state.modeler.auvs = val;
                document.getElementById("val-auv").textContent = val;
                updateModelerChart();
            });
        }
        if (slideStarter) {
            slideStarter.addEventListener("input", (e) => {
                const val = parseInt(e.target.value);
                state.modeler.starterPrice = val;
                document.getElementById("val-starter").textContent = `$${(val/1000).toFixed(0)}K`;
                updateModelerChart();
            });
        }
        if (slidePro) {
            slidePro.addEventListener("input", (e) => {
                const val = parseInt(e.target.value);
                state.modeler.proPrice = val;
                document.getElementById("val-pro").textContent = `$${(val/1000).toFixed(0)}K`;
                updateModelerChart();
            });
        }
        if (slideEnterprise) {
            slideEnterprise.addEventListener("input", (e) => {
                const val = parseInt(e.target.value);
                state.modeler.enterprisePrice = val;
                document.getElementById("val-enterprise").textContent = `$${(val/1000000).toFixed(1)}M`;
                updateModelerChart();
            });
        }
    }

    function updateModelerChart() {
        if (!modelerChart) return;
        modelerChart.data.datasets[0].data = calculateProjections();
        modelerChart.update();
    }

    // Animated Demo Mode Sequencer
    const playDemoBtn = document.getElementById("play-demo-btn");
    const demoCallout = document.getElementById("demo-tour-callout");
    const demoText = document.getElementById("demo-tour-text");
    const demoProgress = document.getElementById("demo-tour-progress");

    if (playDemoBtn && demoCallout && demoText && demoProgress) {
        playDemoBtn.addEventListener("click", () => {
            if (playDemoBtn.disabled) return;
            
            playDemoBtn.disabled = true;
            playDemoBtn.style.opacity = "0.5";
            playDemoBtn.querySelector("span").textContent = "Running Demo...";
            
            demoCallout.classList.add("visible");
            
            updateDemoStep(1, 6, "Welcome to the Deepstream Terminal Demonstration. We begin in Zone Alpha (Pacific ENSO) mapping Sea Surface Temperatures.", () => {
                const alphaMarker = document.getElementById("zone-alpha");
                if (alphaMarker) alphaMarker.dispatchEvent(new Event("click"));
                
                setTimeout(() => {
                    updateDemoStep(2, 6, "Adjusting forecast lead time smoothly to align ocean waves with market prices. Recalculating Pearson correlation (r) dynamically...", () => {
                        animateSlider(lagSlider, 0, 56, 40, () => {
                            setTimeout(() => {
                                updateDemoStep(3, 6, "Transitioning to Zone Gamma (North Atlantic). Fetching daily Chlorophyll anomalies and North Sea Tuna prices...", () => {
                                    const gammaMarker = document.getElementById("zone-gamma");
                                    if (gammaMarker) gammaMarker.dispatchEvent(new Event("click"));
                                    
                                    setTimeout(() => {
                                        updateDemoStep(4, 6, "Switching console workspace view to the Financial Projection Modeler...", () => {
                                            const modelerTabBtn = document.querySelector('[data-tab="modeler"]');
                                            if (modelerTabBtn) modelerTabBtn.dispatchEvent(new Event("click"));
                                            
                                            setTimeout(() => {
                                                updateDemoStep(5, 6, "Scaling fleet deployments from 20 to 180 AUVs. Projected Year 5 ARR dynamically updates to over $50 Million.", () => {
                                                    const auvSlider = document.getElementById("slide-auv");
                                                    animateSlider(auvSlider, 20, 180, 20, () => {
                                                        setTimeout(() => {
                                                            updateDemoStep(6, 6, "Demo Complete. Deepstream is fully validated, offering real-time forecasts and institutional-grade causality.", () => {
                                                                setTimeout(() => {
                                                                    const terminalTabBtn = document.querySelector('[data-tab="terminal"]');
                                                                    if (terminalTabBtn) terminalTabBtn.dispatchEvent(new Event("click"));
                                                                    
                                                                    demoCallout.classList.remove("visible");
                                                                    showToast("Demo complete — Deepstream terminal tour finished.");
                                                                    
                                                                    playDemoBtn.disabled = false;
                                                                    playDemoBtn.style.opacity = "1";
                                                                    playDemoBtn.querySelector("span").textContent = "Play Animated Demo";
                                                                }, 4000);
                                                            });
                                                        }, 1500);
                                                    });
                                                });
                                            }, 2000);
                                        });
                                    }, 3500);
                                });
                            }, 3500);
                        });
                    });
                }, 2000);
            });
        });
    }

    function updateDemoStep(stepNum, totalSteps, text, callback) {
        demoProgress.textContent = `Step ${stepNum} of ${totalSteps}`;
        demoText.innerHTML = "";
        let i = 0;
        function type() {
            if (i < text.length) {
                demoText.innerHTML += text.charAt(i);
                i++;
                setTimeout(type, 15);
            } else {
                if (callback) callback();
            }
        }
        type();
    }

    function animateSlider(sliderEl, start, end, stepDelay = 30, callback) {
        if (!sliderEl) {
            if (callback) callback();
            return;
        }
        
        let current = start;
        const isIncrement = end > start;
        
        const interval = setInterval(() => {
            if (isIncrement) {
                current += 2;
                if (current >= end) {
                    current = end;
                    clearInterval(interval);
                    if (callback) callback();
                }
            } else {
                current -= 2;
                if (current <= end) {
                    current = end;
                    clearInterval(interval);
                    if (callback) callback();
                }
            }
            sliderEl.value = current;
            sliderEl.dispatchEvent(new Event("input"));
        }, stepDelay);
    }

    // Default Initialization
    initForecastChart("copper");
    document.getElementById("zone-alpha")?.classList.add("active-target");

    // Hide the loading overlay shortly after the chart has had a frame to
    // paint (opacity-only transition, so it fades instead of vanishing).
    function hideChartLoading() {
        const loading = document.getElementById("chart-loading");
        if (loading) {
            loading.classList.add("is-loading");
            loading.setAttribute("aria-hidden", "true");
        }
    }
    const loadTimer = setInterval(() => {
        if (forecastChart) {
            clearInterval(loadTimer);
            setTimeout(hideChartLoading, 250);
        }
    }, 100);
});
