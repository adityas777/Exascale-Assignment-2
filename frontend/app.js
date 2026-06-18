// --- GLOBAL APPLICATION STATE ---
const state = {
    selectedYear: 2024,
    selectedIntensityMetric: "Tons of Steel Produced",
    emissionFactors: [],
    emissionRecords: [],
    auditLogs: [],
    charts: {
        yoy: null,
        hotspot: null,
        trend: null
    },
    activeOverrideRecord: null
};

// --- DOM ELEMENTS ---
const elements = {
    yearSelector: document.getElementById("year-selector"),
    navLinks: document.querySelectorAll(".nav-link"),
    tabContents: document.querySelectorAll(".tab-content"),
    tabTitleText: document.getElementById("tab-title-text"),
    tabSubtitleText: document.getElementById("tab-subtitle-text"),
    
    // KPI elements
    kpiTotalFootprint: document.getElementById("kpi-total-footprint"),
    kpiFootprintMeta: document.getElementById("kpi-footprint-meta"),
    kpiYoyValue: document.getElementById("kpi-yoy-value"),
    kpiYoyMeta: document.getElementById("kpi-yoy-meta"),
    kpiTrendIcon: document.getElementById("kpi-trend-icon"),
    kpiIntensityValue: document.getElementById("kpi-intensity-value"),
    kpiIntensityMeta: document.getElementById("kpi-intensity-meta"),
    kpiOverridesValue: document.getElementById("kpi-overrides-value"),
    
    // Forms
    recordForm: document.getElementById("record-form"),
    recordActivitySelect: document.getElementById("form-activity-type"),
    recordUnitInput: document.getElementById("form-unit"),
    recordDateInput: document.getElementById("form-date"),
    metricForm: document.getElementById("metric-form"),
    metricNameSelect: document.getElementById("form-metric-name"),
    metricUnitInput: document.getElementById("form-metric-unit"),
    metricDateInput: document.getElementById("form-metric-date"),
    
    // Datagrids
    recordsTableBody: document.getElementById("records-table-body"),
    auditTableBody: document.getElementById("audit-table-body"),
    filterScopeSelect: document.getElementById("filter-scope"),
    
    // Override Modal
    overrideModal: document.getElementById("override-modal"),
    overrideRecordId: document.getElementById("override-record-id"),
    overrideActivity: document.getElementById("override-activity"),
    overrideOriginalVal: document.getElementById("override-original-val"),
    overrideForm: document.getElementById("override-form"),
    overrideEmissionsInput: document.getElementById("override-emissions-input"),
    overrideJustificationInput: document.getElementById("override-justification-input"),
    modalCloseBtn: document.getElementById("modal-close-btn"),
    modalCancelBtn: document.getElementById("modal-cancel-btn"),
    
    toastContainer: document.getElementById("toast-container")
};

// --- HELPER: TOAST NOTIFICATIONS ---
function showToast(message, type = "success") {
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    
    let icon = "🔔";
    if (type === "success") icon = "✅";
    if (type === "error") icon = "❌";
    if (type === "warning") icon = "⚠️";
    
    toast.innerHTML = `<span>${icon}</span> <div>${message}</div>`;
    elements.toastContainer.appendChild(toast);
    
    // Fade out after 4 seconds
    setTimeout(() => {
        toast.classList.add("toast-fade-out");
        toast.addEventListener("animationend", () => {
            toast.remove();
        });
    }, 4000);
}

// --- TAB NAV LOGIC ---
const tabTitles = {
    "dashboard-tab": { title: "GHG Emissions Dashboard", subtitle: "Real-time Scope 1 & 2 sustainability metrics" },
    "input-tab": { title: "Record Entry & Log Submission", subtitle: "Submit activity details and operational metrics" },
    "explorer-tab": { title: "Emissions Record Explorer", subtitle: "Examine, filter, and manually override calculations" },
    "audit-tab": { title: "Compliance Override Audit Trail", subtitle: "Verifiable logs of manual footprint alterations" }
};

elements.navLinks.forEach(link => {
    link.addEventListener("click", (e) => {
        e.preventDefault();
        const targetTabId = link.getAttribute("data-tab");
        
        // Toggle Link Classes
        elements.navLinks.forEach(l => l.classList.remove("active"));
        link.classList.add("active");
        
        // Toggle Content Classes
        elements.tabContents.forEach(tab => {
            if (tab.id === targetTabId) {
                tab.classList.add("active");
            } else {
                tab.classList.remove("active");
            }
        });
        
        // Update Titles
        if (tabTitles[targetTabId]) {
            elements.tabTitleText.textContent = tabTitles[targetTabId].title;
            elements.tabSubtitleText.textContent = tabTitles[targetTabId].subtitle;
        }
    });
});

// --- YEAR SELECTOR CHANGE ---
elements.yearSelector.addEventListener("change", (e) => {
    state.selectedYear = parseInt(e.target.value);
    refreshDashboardData();
});

// --- DYNAMIC FORM LOGIC ---
// Populate units based on selected activity type
elements.recordActivitySelect.addEventListener("change", (e) => {
    const selectedActivity = e.target.value;
    const factor = state.emissionFactors.find(f => f.activity_type === selectedActivity);
    if (factor) {
        elements.recordUnitInput.value = factor.unit;
    }
});

elements.metricNameSelect.addEventListener("change", (e) => {
    const metric = e.target.value;
    elements.metricUnitInput.value = (metric === "Employees") ? "count" : "tonnes";
});

// --- API COMMUNICATIONS ---
const api = {
    async fetch(url, options = {}) {
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP error ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error(`API Error fetching ${url}:`, error);
            showToast(error.message, "error");
            throw error;
        }
    },
    
    async getEmissionFactors() {
        return this.fetch("/api/emission-factors");
    },
    async getEmissionRecords(scope = "", location = "") {
        let url = "/api/emission-records";
        const params = [];
        if (scope) params.push(`scope=${scope}`);
        if (location) params.push(`location=${location}`);
        if (params.length > 0) url += "?" + params.join("&");
        return this.fetch(url);
    },
    async createEmissionRecord(data) {
        return this.fetch("/api/emission-records", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });
    },
    async overrideEmissionRecord(recordId, data) {
        return this.fetch(`/api/emission-records/${recordId}/override`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });
    },
    async getAuditLogs() {
        return this.fetch("/api/audit-logs");
    },
    async createBusinessMetric(data) {
        return this.fetch("/api/business-metrics", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });
    },
    // Analytics specific
    async getYoYAnalytics(year) {
        return this.fetch(`/api/analytics/yoy?year=${year}`);
    },
    async getIntensityAnalytics(year, metric) {
        return this.fetch(`/api/analytics/intensity?year=${year}&metric_name=${encodeURIComponent(metric)}`);
    },
    async getHotspotAnalytics(year) {
        return this.fetch(`/api/analytics/hotspot?year=${year}`);
    },
    async getTrendAnalytics(year) {
        return this.fetch(`/api/analytics/monthly-trend?year=${year}`);
    }
};

// --- INITIALIZE APPLICATION DATA ---
async function initApp() {
    try {
        // Set default form dates to today
        const todayStr = new Date().toISOString().split("T")[0];
        elements.recordDateInput.value = todayStr;
        elements.metricDateInput.value = todayStr;
        
        // 1. Load emission factors for select dropdown
        const factors = await api.getEmissionFactors();
        state.emissionFactors = factors;
        
        // Group by activity type for unique entries in select
        const seen = new Set();
        elements.recordActivitySelect.innerHTML = '<option value="" disabled selected>Select activity type...</option>';
        factors.forEach(f => {
            if (!seen.has(f.activity_type)) {
                seen.add(f.activity_type);
                const opt = document.createElement("option");
                opt.value = f.activity_type;
                opt.textContent = `${f.activity_type} (${f.unit})`;
                elements.recordActivitySelect.appendChild(opt);
            }
        });
        
        // 2. Load initially displayed lists
        await refreshLists();
        
        // 3. Load analytics
        await refreshDashboardData();
        
        showToast("Emissions registry initialized successfully!");
    } catch (e) {
        console.error("Initialization failed:", e);
    }
}

// --- REFRESH RECORDS & AUDIT LISTS ---
async function refreshLists() {
    // Refresh records
    const scopeFilter = elements.filterScopeSelect.value;
    state.emissionRecords = await api.getEmissionRecords(scopeFilter);
    renderRecordsTable();
    
    // Refresh audit logs
    state.auditLogs = await api.getAuditLogs();
    renderAuditTable();
}

// --- RENDER TABLE GRID DATA ---
function renderRecordsTable() {
    if (state.emissionRecords.length === 0) {
        elements.recordsTableBody.innerHTML = `<tr><td colspan="10" class="empty-state">No matching emission records found in DB.</td></tr>`;
        return;
    }
    
    elements.recordsTableBody.innerHTML = "";
    state.emissionRecords.forEach(rec => {
        const tr = document.createElement("tr");
        if (rec.is_overridden) {
            tr.className = "record-row-overridden";
        }
        
        const finalEmissions = rec.is_overridden ? rec.override_emissions : rec.calculated_emissions;
        
        tr.innerHTML = `
            <td><strong>#${rec.id}</strong></td>
            <td>${rec.date}</td>
            <td><span class="badge badge-scope-${rec.scope}">Scope ${rec.scope}</span></td>
            <td>${rec.activity_type}</td>
            <td>${rec.activity_data.toLocaleString()} ${rec.unit}</td>
            <td>${(rec.calculated_emissions / 1000.0).toFixed(3)} t</td>
            <td>${rec.is_overridden ? (rec.override_emissions / 1000.0).toFixed(3) + ' t' : '-'}</td>
            <td><strong>${(finalEmissions / 1000.0).toFixed(3)} tCO₂e</strong></td>
            <td><span class="badge ${rec.is_overridden ? 'badge-overridden' : 'badge-calculated'}">${rec.is_overridden ? 'Overridden' : 'Calculated'}</span></td>
            <td>
                <button type="button" class="btn btn-muted btn-sm override-btn-trigger" data-id="${rec.id}">
                    ✏️ Override
                </button>
            </td>
        `;
        elements.recordsTableBody.appendChild(tr);
    });
    
    // Attach event listeners to newly generated override buttons
    document.querySelectorAll(".override-btn-trigger").forEach(btn => {
        btn.addEventListener("click", () => {
            const id = parseInt(btn.getAttribute("data-id"));
            openOverrideModal(id);
        });
    });
}

function renderAuditTable() {
    if (state.auditLogs.length === 0) {
        elements.auditTableBody.innerHTML = `<tr><td colspan="7" class="empty-state">No manual overrides have been performed yet.</td></tr>`;
        return;
    }
    
    elements.auditTableBody.innerHTML = "";
    state.auditLogs.forEach(log => {
        const tr = document.createElement("tr");
        const dt = new Date(log.timestamp).toLocaleString();
        
        tr.innerHTML = `
            <td><strong>#${log.id}</strong></td>
            <td>#${log.record_id}</td>
            <td>${log.changed_by}</td>
            <td>${(log.old_value / 1000.0).toFixed(3)} t</td>
            <td><strong>${(log.new_value / 1000.0).toFixed(3)} t</strong></td>
            <td><span class="justification-text" title="${log.justification}">${log.justification}</span></td>
            <td>${dt}</td>
        `;
        elements.auditTableBody.appendChild(tr);
    });
}

// Filter table on scope selector change
elements.filterScopeSelect.addEventListener("change", async () => {
    const scopeFilter = elements.filterScopeSelect.value;
    state.emissionRecords = await api.getEmissionRecords(scopeFilter);
    renderRecordsTable();
});

// --- REFRESH ANALYTICS & DASHBOARD METRICS ---
async function refreshDashboardData() {
    const year = state.selectedYear;
    
    // 1. Fetch data in parallel
    const [yoyData, intensityData, hotspotData, trendData] = await Promise.all([
        api.getYoYAnalytics(year),
        api.getIntensityAnalytics(year, state.selectedIntensityMetric),
        api.getHotspotAnalytics(year),
        api.getTrendAnalytics(year)
    ]);
    
    // 2. Set KPI Cards
    // Footprint is sum of Scope 1 & 2 for selected year
    const s1 = yoyData.scopes.find(s => s.scope === 1)?.current_emissions || 0;
    const s2 = yoyData.scopes.find(s => s.scope === 2)?.current_emissions || 0;
    const totalFootprintKg = s1 + s2;
    const totalFootprintTons = totalFootprintKg / 1000.0;
    elements.kpiTotalFootprint.textContent = `${totalFootprintTons.toLocaleString(undefined, {maximumFractionDigits: 2})} tCO₂e`;
    
    // YoY Trend combined
    const s1_prev = yoyData.scopes.find(s => s.scope === 1)?.previous_emissions || 0;
    const s2_prev = yoyData.scopes.find(s => s.scope === 2)?.previous_emissions || 0;
    const totalPrevKg = s1_prev + s2_prev;
    
    let yoyPct = 0;
    if (totalPrevKg > 0) {
        yoyPct = ((totalFootprintKg - totalPrevKg) / totalPrevKg) * 100;
    }
    
    const formattedYoy = yoyPct.toFixed(2);
    if (yoyPct > 0) {
        elements.kpiYoyValue.textContent = `+${formattedYoy}%`;
        elements.kpiYoyValue.style.color = "var(--danger)";
        elements.kpiTrendIcon.textContent = "📈";
    } else if (yoyPct < 0) {
        elements.kpiYoyValue.textContent = `${formattedYoy}%`;
        elements.kpiYoyValue.style.color = "var(--success)";
        elements.kpiTrendIcon.textContent = "📉";
    } else {
        elements.kpiYoyValue.textContent = `0.00%`;
        elements.kpiYoyValue.style.color = "var(--text-secondary)";
        elements.kpiTrendIcon.textContent = "➖";
    }
    elements.kpiYoyMeta.textContent = `vs. previous year (${(totalPrevKg / 1000.0).toFixed(0)} t)`;
    
    // Intensity Card
    const intVal = intensityData.annual_summary.intensity_kgCO2e_per_unit;
    elements.kpiIntensityValue.textContent = `${intVal.toFixed(3)}`;
    elements.kpiIntensityMeta.textContent = `kgCO₂e / ${intensityData.unit === "tonnes" ? "Ton Produced" : "Employee"}`;
    
    // Set total manual overrides
    const overridesCount = state.emissionRecords.filter(r => r.is_overridden).length;
    elements.kpiOverridesValue.textContent = overridesCount;
    
    // 3. Render/Update Charts
    renderYoYChart(yoyData);
    renderHotspotChart(hotspotData);
    renderTrendChart(trendData);
}

// --- CHART RENDERING ---
function renderYoYChart(yoyData) {
    const ctx = document.getElementById("yoyChart").getContext("2d");
    
    const s1 = yoyData.scopes.find(s => s.scope === 1);
    const s2 = yoyData.scopes.find(s => s.scope === 2);
    
    const currentYear = yoyData.current_year;
    const prevYear = yoyData.previous_year;
    
    const data = {
        labels: [prevYear.toString(), currentYear.toString()],
        datasets: [
            {
                label: 'Scope 1 (Direct)',
                // Divide by 1000 to show in tonnes
                data: [s1.previous_emissions / 1000.0, s1.current_emissions / 1000.0],
                backgroundColor: '#10b981',
                borderRadius: 4
            },
            {
                label: 'Scope 2 (Indirect)',
                data: [s2.previous_emissions / 1000.0, s2.current_emissions / 1000.0],
                backgroundColor: '#3b82f6',
                borderRadius: 4
            }
        ]
    };
    
    if (state.charts.yoy) {
        state.charts.yoy.data = data;
        state.charts.yoy.update();
    } else {
        state.charts.yoy = new Chart(ctx, {
            type: 'bar',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: '#d1d5db', font: { family: 'Plus Jakarta Sans' } }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return ` ${context.dataset.label}: ${context.raw.toFixed(2)} tCO2e`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        stacked: true,
                        grid: { color: '#374151' },
                        ticks: { color: '#9ca3af' }
                    },
                    y: {
                        stacked: true,
                        grid: { color: '#374151' },
                        ticks: { color: '#9ca3af' },
                        title: {
                            display: true,
                            text: 'Emissions (tonnes CO₂e)',
                            color: '#9ca3af'
                        }
                    }
                }
            }
        });
    }
}

function renderHotspotChart(hotspotData) {
    const ctx = document.getElementById("hotspotChart").getContext("2d");
    
    // Focus on Scope 1 & 2 for hotspots, or show top sources.
    // Excel Scope 1 has a lot of materials. We'll show top 5 and group other as "Other Sources".
    const rawHotspots = hotspotData.hotspots;
    let dataSources = [];
    let dataValues = [];
    
    if (rawHotspots.length > 5) {
        const top5 = rawHotspots.slice(0, 5);
        const otherVal = rawHotspots.slice(5).reduce((sum, h) => sum + h.emissions_kgCO2e, 0);
        
        dataSources = top5.map(h => h.source);
        dataValues = top5.map(h => h.emissions_kgCO2e / 1000.0); // in tonnes
        
        if (otherVal > 0) {
            dataSources.push("Other Sources");
            dataValues.push(otherVal / 1000.0);
        }
    } else {
        dataSources = rawHotspots.map(h => h.source);
        dataValues = rawHotspots.map(h => h.emissions_kgCO2e / 1000.0);
    }
    
    const colorPalette = ['#10b981', '#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#6b7280'];
    
    const data = {
        labels: dataSources,
        datasets: [{
            data: dataValues,
            backgroundColor: colorPalette.slice(0, dataSources.length),
            borderWidth: 1,
            borderColor: '#1f2937'
        }]
    };
    
    if (state.charts.hotspot) {
        state.charts.hotspot.data = data;
        state.charts.hotspot.update();
    } else {
        state.charts.hotspot = new Chart(ctx, {
            type: 'doughnut',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: { 
                            color: '#d1d5db', 
                            boxWidth: 12,
                            font: { family: 'Plus Jakarta Sans', size: 10 }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const val = context.raw.toFixed(2);
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const pct = ((context.raw / total) * 100).toFixed(1);
                                return ` ${context.label}: ${val} t (${pct}%)`;
                            }
                        }
                    }
                },
                cutout: '60%'
            }
        });
    }
}

function renderTrendChart(trendData) {
    const ctx = document.getElementById("trendChart").getContext("2d");
    
    const months = trendData.map(d => {
        // Parse "2024-03" -> "Mar"
        const mNum = parseInt(d.month.split("-")[1]);
        const names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        return names[mNum - 1];
    });
    
    const s1Vals = trendData.map(d => d.scope1 / 1000.0);
    const s2Vals = trendData.map(d => d.scope2 / 1000.0);
    const s3Vals = trendData.map(d => d.scope3 / 1000.0);
    
    const data = {
        labels: months,
        datasets: [
            {
                label: 'Scope 1 (Direct)',
                data: s1Vals,
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                borderWidth: 2,
                fill: false,
                tension: 0.2
            },
            {
                label: 'Scope 2 (Indirect)',
                data: s2Vals,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                borderWidth: 2,
                fill: false,
                tension: 0.2
            },
            {
                label: 'Scope 3 (Value Chain)',
                data: s3Vals,
                borderColor: '#8b5cf6',
                backgroundColor: 'rgba(139, 92, 246, 0.1)',
                borderWidth: 2,
                fill: false,
                tension: 0.2
            }
        ]
    };
    
    if (state.charts.trend) {
        state.charts.trend.data = data;
        state.charts.trend.update();
    } else {
        state.charts.trend = new Chart(ctx, {
            type: 'line',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: '#d1d5db', font: { family: 'Plus Jakarta Sans' } }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return ` ${context.dataset.label}: ${context.raw.toFixed(2)} tCO2e`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: '#374151' },
                        ticks: { color: '#9ca3af' }
                    },
                    y: {
                        grid: { color: '#374151' },
                        ticks: { color: '#9ca3af' },
                        title: {
                            display: true,
                            text: 'Monthly Emissions (tonnes CO₂e)',
                            color: '#9ca3af'
                        }
                    }
                }
            }
        });
    }
}

// --- FORM SUBMISSIONS ---
elements.recordForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    
    const activity_type = elements.recordActivitySelect.value;
    const quantity = parseFloat(elements.recordForm.querySelector("#form-quantity").value);
    const date = elements.recordDateInput.value;
    const unit = elements.recordUnitInput.value;
    const location = elements.recordForm.querySelector("#form-location").value;
    const section = elements.recordForm.querySelector("#form-section").value;
    
    if (!activity_type || isNaN(quantity) || !date || !location || !section) {
        showToast("Please fill in all required fields.", "warning");
        return;
    }
    
    const payload = {
        activity_type,
        activity_data: quantity,
        unit,
        date,
        location,
        section
    };
    
    try {
        const result = await api.createEmissionRecord(payload);
        showToast(`Record #${result.id} successfully calculated & saved!`);
        elements.recordForm.reset();
        
        // Default the date and unit fields again
        elements.recordDateInput.value = new Date().toISOString().split("T")[0];
        elements.recordUnitInput.value = "";
        
        // Refresh tables and charts
        await refreshLists();
        await refreshDashboardData();
    } catch (err) {
        console.error("Submission failed:", err);
    }
});

elements.metricForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    
    const metric_name = elements.metricNameSelect.value;
    const value = parseFloat(elements.metricForm.querySelector("#form-metric-value").value);
    const date = elements.metricDateInput.value;
    const unit = elements.metricUnitInput.value;
    
    if (!metric_name || isNaN(value) || !date) {
        showToast("Please fill in all metric fields.", "warning");
        return;
    }
    
    const payload = {
        date,
        metric_name,
        value,
        unit
    };
    
    try {
        const result = await api.createBusinessMetric(payload);
        showToast(`Business metric recorded! ID #${result.id}`);
        elements.metricForm.reset();
        elements.metricDateInput.value = new Date().toISOString().split("T")[0];
        elements.metricUnitInput.value = "tonnes"; // Reset to default unit
        
        // Update charts with new intensity calculations
        await refreshDashboardData();
    } catch (err) {
        console.error("Metric submission failed:", err);
    }
});

// --- MANUAL OVERRIDES MODAL & SUBMIT ---
function openOverrideModal(recordId) {
    const record = state.emissionRecords.find(r => r.id === recordId);
    if (!record) return;
    
    state.activeOverrideRecord = record;
    
    elements.overrideRecordId.textContent = record.id;
    elements.overrideActivity.textContent = `${record.activity_type} (${record.activity_data} ${record.unit})`;
    elements.overrideOriginalVal.textContent = record.calculated_emissions.toLocaleString();
    
    // Pre-fill input with existing override or calculated value
    elements.overrideEmissionsInput.value = record.is_overridden ? record.override_emissions : record.calculated_emissions;
    elements.overrideJustificationInput.value = record.is_overridden ? record.override_justification : "";
    
    elements.overrideModal.classList.add("open");
}

function closeOverrideModal() {
    elements.overrideModal.classList.remove("open");
    state.activeOverrideRecord = null;
    elements.overrideForm.reset();
}

// Close events
elements.modalCloseBtn.addEventListener("click", closeOverrideModal);
elements.modalCancelBtn.addEventListener("click", closeOverrideModal);
window.addEventListener("click", (e) => {
    if (e.target === elements.overrideModal) {
        closeOverrideModal();
    }
});

elements.overrideForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    
    if (!state.activeOverrideRecord) return;
    
    const val = parseFloat(elements.overrideEmissionsInput.value);
    const justification = elements.overrideJustificationInput.value.trim();
    
    if (isNaN(val) || justification.length < 5) {
        showToast("Override emissions and justification (min 5 chars) are required.", "warning");
        return;
    }
    
    const payload = {
        override_emissions: val,
        justification: justification
    };
    
    try {
        const result = await api.overrideEmissionRecord(state.activeOverrideRecord.id, payload);
        showToast(`Emission Record #${result.id} successfully overridden!`);
        closeOverrideModal();
        
        // Refresh everything
        await refreshLists();
        await refreshDashboardData();
    } catch (err) {
        console.error("Override submission failed:", err);
    }
});

// --- APP LAUNCH ---
document.addEventListener("DOMContentLoaded", initApp);
