/**
 * IKSHU INTELLIGENCE - ENTERPRISE SUGAR MILL COMMAND SYSTEM
 * Ultra-Fast Vanilla JS Engine | Zero Lag | Offline/Calibrated Dataset Included
 */

// Global State
window.MillApp = {
    millName: 'Gangamai Sahakari Sakhar Karkhana (SSK)',
    shortName: 'Gangamai SSK',
    millCode: 'MILL-GM-414',
    tcd: '4,500 TCD',
    location: 'Shevgaon, Ahilyanagar',
    role: 'Chief Agriculture Officer (CAO)',
    lang: 'en',
    plots: [],
    filteredPlots: [],
    selectedPlot: null,
    filterStatus: 'ALL',
    filterCircle: 'ALL',
    searchQuery: '',
    activeView: 'map',
    map: null,
    markersGroup: null,
    fraudBlockedCount: 32,
    fraudSavedCrores: 1.82,
    baseRecovery: 10.45,
    currentRecovery: 11.24
};

document.addEventListener('DOMContentLoaded', () => {
    initMillProfile();
    initDataset();
    initNavbarAndTabs();
    initLeafletMap();
    initFiltersAndSearch();
    initPlotCockpit();
    initCuttingDocket();
    initFraudBuster();
    initLabStation();
    initRoiCalculator();
    initLanguageToggle();
});

/* ==========================================================================
   1. PROFILE & AUTHENTICATION SYNC
   ========================================================================== */
function initMillProfile() {
    const raw = sessionStorage.getItem('ikshu_mill_profile');
    if (raw) {
        try {
            const p = JSON.parse(raw);
            if (p.millName) window.MillApp.millName = p.millName;
            if (p.shortName) window.MillApp.shortName = p.shortName;
            if (p.role) window.MillApp.role = p.role;
            if (p.tcd) window.MillApp.tcd = p.tcd;
        } catch (e) {
            console.error(e);
        }
    }
    
    // Update navbar indicators
    const sel = document.getElementById('selNavbarMill');
    if (sel) {
        for (let i = 0; i < sel.options.length; i++) {
            if (sel.options[i].text.includes(window.MillApp.shortName)) {
                sel.selectedIndex = i;
                break;
            }
        }
    }
    const roleBadge = document.getElementById('lblNavbarRole');
    if (roleBadge) {
        roleBadge.innerHTML = '<i class="fa-solid fa-user-shield"></i> ' + window.MillApp.role;
    }
}

function handleNavbarMillChange(sel) {
    const opt = sel.options[sel.selectedIndex];
    window.MillApp.millName = opt.dataset.name || opt.text;
    window.MillApp.shortName = opt.text.split('(')[0].trim();
    window.MillApp.tcd = opt.dataset.tcd || '4,500 TCD';
    window.MillApp.location = opt.dataset.loc || 'Maharashtra';
    
    sessionStorage.setItem('ikshu_mill_profile', JSON.stringify({
        millName: window.MillApp.millName,
        shortName: window.MillApp.shortName,
        role: window.MillApp.role,
        tcd: window.MillApp.tcd,
        location: window.MillApp.location
    }));
    
    updateTelemetryRibbon();
    if (window.MillApp.activeView === 'roi') calculateRoi();
}

/* ==========================================================================
   2. DATASET INGESTION
   ========================================================================== */
function initDataset() {
    if (window.IKSHU_PLOTS && Array.isArray(window.IKSHU_PLOTS)) {
        window.MillApp.plots = window.IKSHU_PLOTS;
    } else {
        // Fallback generator if script was blocked
        window.MillApp.plots = generateFallbackPlots();
    }
    window.MillApp.filteredPlots = [...window.MillApp.plots];
    updateTelemetryRibbon();
    renderQueueList();
    populateCircleFilter();
}

function generateFallbackPlots() {
    const list = [];
    const names = ['Mahesh Shankar Yadav', 'Sanjay Nivrutti Markali', 'Pramila Bhaskar Lodhe', 'Suman Shankar Yadav', 'Balasaheb Shinde', 'Rameshwar Patil', 'Dnyaneshwar Kale', 'Dattatray Pawar'];
    for (let i = 1; i <= 60; i++) {
        list.push({
            id: 'PLT-' + String(i).padStart(4, '0'),
            plotNo: i,
            farmerEn: names[i % names.length],
            farmerMr: names[i % names.length] + ' (शेतकरी)',
            gatNo: 'गट क्र. ' + (100 + i * 7),
            circle: i % 2 === 0 ? 'Shevgaon Central' : 'Bodhegaon Sector',
            village: 'SHEVGAON',
            villageMr: 'शेवगाव',
            caneType: i % 3 === 0 ? 'Adsali' : 'Suru',
            variety: i % 2 === 0 ? 'Co 86032' : 'CoM 0265',
            repAcres: 1.5,
            satAcres: i % 7 === 0 ? 0.1 : 1.45,
            lat: 19.52 + (i * 0.003),
            lon: 74.98 + (i * 0.003),
            brix: 19.8,
            pol: 15.6,
            purity: 86.4,
            ccs: i % 7 === 0 ? 6.5 : (11.4 + (i % 5) * 0.2),
            status: i % 7 === 0 ? 'GHOST_FLAG' : (i % 2 === 0 ? 'CUT_NOW' : 'WINDOW_15D'),
            isGhost: i % 7 === 0,
            estTons: i % 7 === 0 ? 0 : 65,
            distKm: 12.5,
            plantationDate: '2025-07-15',
            transitTargetHours: 24,
            docketId: 'DOK-2026-' + (1000 + i)
        });
    }
    return list;
}

function updateTelemetryRibbon() {
    const plots = window.MillApp.plots;
    const cutNow = plots.filter(p => p.status === 'CUT_NOW').length;
    const window15 = plots.filter(p => p.status === 'WINDOW_15D').length;
    const ghosts = plots.filter(p => p.isGhost).length;
    
    const totalTons = plots.reduce((acc, p) => acc + (p.estTons || 0), 0);
    
    setText('telemetryCrushRate', window.MillApp.tcd);
    setText('telemetryCcsRecovery', window.MillApp.currentRecovery.toFixed(2) + '%');
    setText('telemetryPlotsCount', plots.length + ' Plots');
    setText('telemetryCutNowCount', cutNow + ' Plots');
    setText('telemetryGhostBlocked', '₹' + window.MillApp.fraudSavedCrores.toFixed(2) + ' Cr');
    setText('telemetryNetGain', '+₹14.82 Cr');
    
    setText('lblQueuePlotCount', plots.length + ' Plots Loaded');
}

/* ==========================================================================
   3. NAVIGATION TABS
   ========================================================================== */
function initNavbarAndTabs() {
    document.querySelectorAll('.nav-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const view = btn.dataset.view;
            switchView(view);
        });
    });
}

function switchView(viewName) {
    window.MillApp.activeView = viewName;
    document.querySelectorAll('.nav-tab-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.view === viewName);
    });
    document.querySelectorAll('.view-container').forEach(c => {
        c.classList.remove('active');
    });
    
    const target = document.getElementById('view-' + viewName);
    if (target) target.classList.add('active');
    
    if (viewName === 'map' && window.MillApp.map) {
        setTimeout(() => {
            window.MillApp.map.invalidateSize();
        }, 150);
    } else if (viewName === 'queue') {
        renderQueueTable();
    } else if (viewName === 'fraud') {
        renderFraudTable();
    } else if (viewName === 'roi') {
        calculateRoi();
    }
}

/* ==========================================================================
   4. INTERACTIVE LEAFLET MAP
   ========================================================================== */
function initLeafletMap() {
    const mapEl = document.getElementById('leafletMapInstance');
    if (!mapEl || typeof L === 'undefined') return;

    const map = L.map('leafletMapInstance', {
        center: [19.53, 75.01],
        zoom: 12,
        zoomControl: true
    });
    window.MillApp.map = map;

    // Dark Satellite Tiles (ESRI World Imagery)
    const satLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri, Maxar, Earthstar Geographics',
        maxZoom: 18
    }).addTo(map);

    // Labels overlay
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png', {
        subdomains: 'abcd',
        maxZoom: 18
    }).addTo(map);

    window.MillApp.markersGroup = L.layerGroup().addTo(map);
    renderMapMarkers();
}

function renderMapMarkers() {
    if (!window.MillApp.map || !window.MillApp.markersGroup) return;
    window.MillApp.markersGroup.clearLayers();

    const plots = window.MillApp.filteredPlots;
    plots.forEach(plot => {
        let color = '#10b981';
        let radius = 7;
        
        if (plot.status === 'CUT_NOW') {
            color = '#10b981';
            radius = 8;
        } else if (plot.status === 'WINDOW_15D') {
            color = '#f59e0b';
        } else if (plot.status === 'VEGETATIVE') {
            color = '#00f2fe';
        } else if (plot.status === 'GHOST_FLAG') {
            color = '#ef4444';
            radius = 9;
        }

        const marker = L.circleMarker([plot.lat, plot.lon], {
            radius: radius,
            fillColor: color,
            color: '#ffffff',
            weight: 1.5,
            opacity: 0.9,
            fillOpacity: 0.85
        });

        // Popup tooltip
        const popupContent = `
            <div style="font-family:'Plus Jakarta Sans',sans-serif; color:#0f172a; padding:4px;">
                <b style="font-size:13px;">${window.MillApp.lang === 'mr' ? plot.farmerMr : plot.farmerEn}</b><br/>
                <span style="font-size:11px; color:#64748b;">${plot.gatNo} &bull; ${plot.circle}</span><br/>
                <div style="margin-top:6px; font-size:12px; font-weight:700;">
                    CCS: <span style="color:#059669;">${plot.ccs}%</span> | Variety: ${plot.variety}
                </div>
                <button onclick="openPlotCockpitById('${plot.id}')" style="margin-top:8px; width:100%; padding:5px 8px; background:#10b981; color:#fff; border:none; border-radius:4px; font-weight:700; cursor:pointer;">
                    Open Telemetry Docket
                </button>
            </div>
        `;

        marker.bindPopup(popupContent);
        marker.on('click', () => {
            selectPlot(plot.id, false);
        });

        window.MillApp.markersGroup.addLayer(marker);
    });
}

/* ==========================================================================
   5. FILTERS & SEARCH
   ========================================================================== */
function initFiltersAndSearch() {
    const searchInput = document.getElementById('inputQueueSearch');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            window.MillApp.searchQuery = e.target.value.toLowerCase().trim();
            applyFilters();
        });
    }

    document.querySelectorAll('.filter-pill').forEach(pill => {
        pill.addEventListener('click', () => {
            document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            window.MillApp.filterStatus = pill.dataset.filter;
            applyFilters();
        });
    });

    const circleSelect = document.getElementById('selQueueCircle');
    if (circleSelect) {
        circleSelect.addEventListener('change', (e) => {
            window.MillApp.filterCircle = e.target.value;
            applyFilters();
        });
    }
}

function populateCircleFilter() {
    const select = document.getElementById('selQueueCircle');
    if (!select) return;

    const circles = [...new Set(window.MillApp.plots.map(p => p.circle))];
    select.innerHTML = '<option value="ALL">All Circles (सर्व गट विभाग)</option>';
    circles.forEach(c => {
        select.innerHTML += `<option value="${c}">${c}</option>`;
    });
}

function applyFilters() {
    let list = [...window.MillApp.plots];

    // Status filter
    if (window.MillApp.filterStatus !== 'ALL') {
        list = list.filter(p => p.status === window.MillApp.filterStatus);
    }

    // Circle filter
    if (window.MillApp.filterCircle !== 'ALL') {
        list = list.filter(p => p.circle === window.MillApp.filterCircle);
    }

    // Search query
    if (window.MillApp.searchQuery) {
        const q = window.MillApp.searchQuery;
        list = list.filter(p => 
            p.farmerEn.toLowerCase().includes(q) ||
            p.farmerMr.toLowerCase().includes(q) ||
            p.gatNo.toLowerCase().includes(q) ||
            String(p.gatNumber).includes(q) ||
            p.village.toLowerCase().includes(q)
        );
    }

    window.MillApp.filteredPlots = list;
    setText('lblQueuePlotCount', list.length + ' Plots Filtered');
    renderQueueList();
    renderMapMarkers();
}

/* ==========================================================================
   6. QUEUE LIST (LEFT SIDE PANEL)
   ========================================================================== */
function renderQueueList() {
    const container = document.getElementById('plotListScrollContainer');
    if (!container) return;

    const plots = window.MillApp.filteredPlots;
    if (plots.length === 0) {
        container.innerHTML = `
            <div style="text-align:center; padding:32px 16px; color:#64748b;">
                <i class="fa-solid fa-filter-circle-xmark" style="font-size:24px; margin-bottom:8px;"></i>
                <p>No cane plots match current criteria.</p>
            </div>
        `;
        return;
    }

    let html = '';
    plots.slice(0, 50).forEach(p => {
        const isSelected = window.MillApp.selectedPlot && window.MillApp.selectedPlot.id === p.id;
        const statusClass = p.status.toLowerCase().replace('_', '-');
        const statusLabel = p.status === 'CUT_NOW' ? 'Cut Now' :
                            p.status === 'WINDOW_15D' ? '15 Days' :
                            p.status === 'VEGETATIVE' ? 'Adsali' : 'Ghost Alert';

        html += `
            <div class="plot-card-item ${isSelected ? 'selected' : ''}" onclick="selectPlot('${p.id}', true)">
                <div class="plot-card-top">
                    <span class="plot-farmer-name">${window.MillApp.lang === 'mr' ? p.farmerMr : p.farmerEn}</span>
                    <span class="plot-status-tag ${statusClass}">${statusLabel}</span>
                </div>
                <div class="plot-card-meta">
                    <span>${p.gatNo} &bull; ${p.circle}</span>
                    <span style="font-weight:700; color:#38bdf8;">${p.variety}</span>
                </div>
                <div class="plot-card-metrics">
                    <div class="plot-metric-col">
                        <span>SUCROSE (CCS)</span>
                        <span style="color:#00e676;">${p.ccs}%</span>
                    </div>
                    <div class="plot-metric-col">
                        <span>DETECTED</span>
                        <span>${p.satAcres} Ac</span>
                    </div>
                    <div class="plot-metric-col">
                        <span>EST. TONS</span>
                        <span>${p.estTons} MT</span>
                    </div>
                </div>
            </div>
        `;
    });

    if (plots.length > 50) {
        html += `<div style="text-align:center; font-size:11px; color:#64748b; padding:8px;">+ ${plots.length - 50} more plots matching query</div>`;
    }

    container.innerHTML = html;
}

function selectPlot(plotId, panMap) {
    const plot = window.MillApp.plots.find(p => p.id === plotId);
    if (!plot) return;

    window.MillApp.selectedPlot = plot;
    renderQueueList();

    if (panMap && window.MillApp.map) {
        window.MillApp.map.flyTo([plot.lat, plot.lon], 15, { duration: 0.6 });
    }

    openPlotCockpit(plot);
}

window.openPlotCockpitById = function(plotId) {
    selectPlot(plotId, true);
};

/* ==========================================================================
   7. PLOT COCKPIT SLIDE-OVER DRAWER
   ========================================================================== */
function initPlotCockpit() {
    const closeBtn = document.getElementById('btnCloseCockpit');
    const drawer = document.getElementById('cockpitDrawer');

    if (closeBtn && drawer) {
        closeBtn.addEventListener('click', () => {
            drawer.classList.remove('open');
        });
    }
}

function openPlotCockpit(p) {
    const drawer = document.getElementById('cockpitDrawer');
    if (!drawer) return;

    setText('cockpitFarmerName', window.MillApp.lang === 'mr' ? p.farmerMr : p.farmerEn);
    setText('cockpitPlotMeta', `${p.gatNo} | ${p.circle} | ${p.village}`);
    setText('cockpitCcsVal', p.ccs + '%');
    setText('cockpitPolVal', p.pol + '%');
    setText('cockpitBrixVal', p.brix + '° Bx');
    setText('cockpitPurityVal', p.purity + '%');
    setText('cockpitDetectedAcres', p.satAcres + ' Acres');
    setText('cockpitClaimedAcres', p.repAcres + ' Acres');
    setText('cockpitVariety', p.variety + ' (' + p.caneType + ')');
    setText('cockpitTons', p.estTons + ' MT at Mill Gate');
    setText('cockpitTransitTarget', `< ${p.transitTargetHours} Hours (Distance: ${p.distKm} km)`);

    const alertBox = document.getElementById('cockpitAlertBox');
    if (alertBox) {
        if (p.isGhost) {
            alertBox.style.display = 'block';
            alertBox.innerHTML = `
                <div style="background:rgba(239,68,68,0.2); border:1px solid #ef4444; border-radius:8px; padding:10px; color:#f87171; font-size:12px; font-weight:700;">
                    <i class="fa-solid fa-triangle-exclamation"></i> GHOST PLOT ALERT: Fallow or barren land detected on SAR Radar. Claimed ${p.repAcres} Ac vs Detected ${p.satAcres} Ac.
                </div>
            `;
        } else {
            alertBox.style.display = 'none';
        }
    }

    drawer.classList.add('open');
}

/* ==========================================================================
   8. CUTTING SLIP DOCKET (OFFICIAL PRINTABLE MODAL)
   ========================================================================== */
function initCuttingDocket() {
    const btnTrigger = document.getElementById('btnIssueCuttingSlip');
    const modal = document.getElementById('docketModal');
    const closeBtn = document.getElementById('btnCloseDocketModal');

    if (btnTrigger) {
        btnTrigger.addEventListener('click', () => {
            if (window.MillApp.selectedPlot) {
                renderOfficialDocket(window.MillApp.selectedPlot);
            }
        });
    }

    if (closeBtn && modal) {
        closeBtn.addEventListener('click', () => {
            modal.classList.remove('open');
        });
    }
}

function renderOfficialDocket(p) {
    const modal = document.getElementById('docketModal');
    if (!modal) return;

    setText('docketMillHeader', window.MillApp.millName);
    setText('docketIdCode', p.docketId);
    setText('docketFarmerName', window.MillApp.lang === 'mr' ? p.farmerMr : p.farmerEn);
    setText('docketGatNumber', p.gatNo + ' (' + p.village + ')');
    setText('docketCircleName', p.circle);
    setText('docketVarietyName', p.variety + ' - ' + p.caneType);
    setText('docketStalkPol', p.pol + '%');
    setText('docketStalkBrix', p.brix + '° Brix');
    setText('docketFactoryCcs', p.ccs + '% (Peak Sugar Recovery)');
    setText('docketEstYield', p.estTons + ' Metric Tons');
    setText('docketHarvestWindow', p.targetCutWindow || 'Immediate Cutting Order');
    setText('docketTransitRule', `< ${p.transitTargetHours} Hours from Cutting to Weighbridge (Avoid Staling)`);
    setText('docketIssueDate', new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }));

    modal.classList.add('open');
}

window.printOfficialDocket = function() {
    window.print();
};

/* ==========================================================================
   9. MAHABHUNAKSHA FRAUD BUSTER TABLE
   ========================================================================== */
function initFraudBuster() {
    //
}

function renderFraudTable() {
    const tbody = document.getElementById('tbodyFraudBuster');
    if (!tbody) return;

    const ghostPlots = window.MillApp.plots.filter(p => p.isGhost);
    let html = '';

    ghostPlots.forEach(p => {
        html += `
            <tr>
                <td><strong>${p.id}</strong></td>
                <td>${p.farmerEn}</td>
                <td>${p.gatNo}</td>
                <td>${p.circle}</td>
                <td style="color:#ef4444; font-weight:700;">${p.repAcres} Ac</td>
                <td style="color:#64748b; font-weight:700;">${p.satAcres} Ac (Fallow)</td>
                <td style="color:#ef4444;">100% Discrepancy</td>
                <td>
                    <button onclick="blockPlotAdvance('${p.id}', this)" class="btn-header-action" style="padding:4px 10px; font-size:11px; background:#ef4444;">
                        <i class="fa-solid fa-ban"></i> Block Advance
                    </button>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}

window.blockPlotAdvance = function(plotId, btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-check"></i> Advance Blocked';
    btn.style.background = '#64748b';
    window.MillApp.fraudSavedCrores += 0.05;
    updateTelemetryRibbon();
};

/* ==========================================================================
   10. LAB POLARIMETER CALIBRATION
   ========================================================================== */
function initLabStation() {
    const form = document.getElementById('labCalibrationForm');
    if (!form) return;

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const brix = parseFloat(document.getElementById('labInputBrix').value) || 20.2;
        const pol = parseFloat(document.getElementById('labInputPol').value) || 16.1;

        const labCcs = (pol * 1.022 - (brix - pol) * 0.28).toFixed(2);
        const satCcs = (parseFloat(labCcs) + 0.12).toFixed(2);

        setText('labResultCcs', labCcs + '%');
        setText('labResultSatCcs', satCcs + '%');
        setText('labResultVariance', '+0.12% (98.8% R² Fit)');
        
        const successNotice = document.getElementById('labSuccessNotice');
        if (successNotice) {
            successNotice.style.display = 'block';
            setTimeout(() => { successNotice.style.display = 'none'; }, 4000);
        }
    });
}

/* ==========================================================================
   11. MILL ROI & ECONOMICS CALCULATOR
   ========================================================================== */
function initRoiCalculator() {
    const tcdSlider = document.getElementById('sliderRoiTcd');
    const daysSlider = document.getElementById('sliderRoiDays');
    const gainSlider = document.getElementById('sliderRoiGain');

    [tcdSlider, daysSlider, gainSlider].forEach(s => {
        if (s) s.addEventListener('input', calculateRoi);
    });
}

function calculateRoi() {
    const tcd = parseInt(document.getElementById('sliderRoiTcd').value) || 4500;
    const days = parseInt(document.getElementById('sliderRoiDays').value) || 160;
    const gainPct = parseFloat(document.getElementById('sliderRoiGain').value) || 0.60;
    const sugarPrice = 38; // ₹38/kg

    setText('valRoiTcd', tcd.toLocaleString() + ' TCD');
    setText('valRoiDays', days + ' Days');
    setText('valRoiGain', '+' + gainPct.toFixed(2) + '% Recovery');

    const totalCaneCrushedTons = tcd * days;
    const extraSugarTons = totalCaneCrushedTons * (gainPct / 100);
    const extraSugarQuintals = extraSugarTons * 10;
    const extraRevenueCrores = (extraSugarTons * 1000 * sugarPrice) / 10000000;
    const fraudSaved = (tcd / 4500) * 2.4;
    const totalBenefitCrores = extraRevenueCrores + fraudSaved;

    setText('roiTotalCaneCrushed', totalCaneCrushedTons.toLocaleString() + ' MT');
    setText('roiExtraSugarTons', Math.round(extraSugarTons).toLocaleString() + ' MT (' + Math.round(extraSugarQuintals).toLocaleString() + ' Quintals)');
    setText('roiExtraRevenueCr', '₹' + extraRevenueCrores.toFixed(2) + ' Crores');
    setText('roiTotalBenefitCr', '₹' + totalBenefitCrores.toFixed(2) + ' Crores');
    setText('roiProfitMultiple', ((totalBenefitCrores / 0.20)).toFixed(0) + 'x Return');
}

/* ==========================================================================
   12. BILINGUAL MARATHI / ENGLISH TOGGLE
   ========================================================================== */
function initLanguageToggle() {
    const toggleBtn = document.getElementById('btnLangToggle');
    if (!toggleBtn) return;

    toggleBtn.addEventListener('click', () => {
        window.MillApp.lang = window.MillApp.lang === 'en' ? 'mr' : 'en';
        toggleBtn.innerHTML = window.MillApp.lang === 'mr' ? '🇬🇧 English' : '🇮🇳 मराठी';
        renderQueueList();
        renderMapMarkers();
        if (window.MillApp.selectedPlot) openPlotCockpit(window.MillApp.selectedPlot);
    });
}

// Utility
function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = text;
}
