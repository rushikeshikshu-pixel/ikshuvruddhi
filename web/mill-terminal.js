/**
 * IKSHU INTELLIGENCE - ENTERPRISE SUGAR MILL COMMAND SYSTEM
 * Ultra-Fast Vanilla JS Engine | Zero Lag | Full Factory Action Suite
 * Clean UTF-8 Encodings for Indian Rupee (₹), Polarimetry (°Bx), and Marathi
 */

// Global Sugar Mill State
window.MillApp = {
    millName: 'Gangamai Sahakari Sakhar Karkhana (SSK)',
    shortName: 'Gangamai SSK',
    millCode: 'MILL-GM-414',
    tcd: '4,500 TCD',
    tcdNumber: 4500,
    seasonDays: 150,
    sugarPrice: 3600,
    location: 'Shevgaon, Ahilyanagar',
    role: 'Chief Agriculture Officer (CAO)',
    lang: 'en',
    plots: [],
    customPlots: [],
    harvestGangs: [],
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
    currentRecovery: 11.24,
    pendingBulkPlots: []
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
    initMillActionsAndModals();
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
            if (p.tcd) {
                window.MillApp.tcd = p.tcd;
                window.MillApp.tcdNumber = parseInt(p.tcd.replace(/\D/g, '')) || 4500;
            }
        } catch (e) {
            console.error(e);
        }
    }

    // Load custom mill settings if saved
    const rawSettings = localStorage.getItem('ikshu_mill_settings');
    if (rawSettings) {
        try {
            const s = JSON.parse(rawSettings);
            if (s.tcd) {
                window.MillApp.tcd = s.tcd + ' TCD';
                window.MillApp.tcdNumber = parseInt(s.tcd);
            }
            if (s.seasonDays) window.MillApp.seasonDays = parseInt(s.seasonDays);
            if (s.sugarPrice) window.MillApp.sugarPrice = parseInt(s.sugarPrice);
            if (s.baseRecovery) window.MillApp.baseRecovery = parseFloat(s.baseRecovery);
        } catch (e) {
            console.error(e);
        }
    }

    // Load registered harvest gangs
    const rawGangs = localStorage.getItem('ikshu_harvest_gangs');
    if (rawGangs) {
        try {
            window.MillApp.harvestGangs = JSON.parse(rawGangs);
        } catch (e) {
            console.error(e);
        }
    } else {
        window.MillApp.harvestGangs = [
            { id: 'GANG-01', name: 'Santosh Kale Mukadam', phone: '98221 45120', type: 'Tractor Trolley (12 MT)', regNo: 'MH-16-BX-4122', quotaMt: 45, circle: 'Shevgaon Central' },
            { id: 'GANG-02', name: 'Babanrao Shinde Toli', phone: '94231 87654', type: '10-Tonne Truck (18 MT)', regNo: 'MH-16-T-8940', quotaMt: 55, circle: 'Bodhegaon Sector' },
            { id: 'GANG-03', name: 'Kisanrao Pawar Toli', phone: '98500 23145', type: 'Bullock Cart (2.5 MT)', regNo: 'BC-SHEV-04', quotaMt: 15, circle: 'Erandgaon Circle' }
        ];
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

window.handleNavbarMillChange = function(sel) {
    const opt = sel.options[sel.selectedIndex];
    window.MillApp.millName = opt.dataset.name || opt.text;
    window.MillApp.shortName = opt.text.split('(')[0].trim();
    window.MillApp.tcd = opt.dataset.tcd || '4,500 TCD';
    window.MillApp.tcdNumber = parseInt(window.MillApp.tcd.replace(/\D/g, '')) || 4500;
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
    showToast('Switched operational context to ' + window.MillApp.shortName);
};

/* ==========================================================================
   2. DATASET INGESTION & LOCAL STORAGE MERGE
   ========================================================================== */
function initDataset() {
    let basePlots = [];
    if (window.IKSHU_PLOTS && Array.isArray(window.IKSHU_PLOTS)) {
        basePlots = [...window.IKSHU_PLOTS];
    } else {
        basePlots = generateFallbackPlots();
    }

    // Merge custom plots added by the mill from localStorage
    const rawCustom = localStorage.getItem('ikshu_custom_plots');
    if (rawCustom) {
        try {
            const customList = JSON.parse(rawCustom);
            if (Array.isArray(customList) && customList.length > 0) {
                window.MillApp.customPlots = customList;
                basePlots = [...customList, ...basePlots];
            }
        } catch (e) {
            console.error(e);
        }
    }

    window.MillApp.plots = basePlots;
    window.MillApp.filteredPlots = [...window.MillApp.plots];
    updateTelemetryRibbon();
    renderQueueList();
    populateCircleFilter();
}

function generateFallbackPlots() {
    const list = [];
    const names = ['YADAV MAHESH SHANKAR', 'MARKALI SANJAY NIVRUTTI', 'LODHE PRAMILA BHASKAR', 'PATIL BALASAHEB', 'SHINDE RAMESHWAR', 'KALE DNYANESHWAR', 'PAWAR DATTATRAY'];
    for (let i = 1; i <= 60; i++) {
        list.push({
            id: 'PLT-' + String(i).padStart(4, '0'),
            plotNo: i,
            farmerEn: names[i % names.length],
            farmerMr: names[i % names.length] + ' (शेतकरी)',
            gatNo: 'Gat ' + (100 + i * 7),
            gatNumber: 100 + i * 7,
            circle: i % 2 === 0 ? 'Shevgaon Central' : 'Bodhegaon Sector',
            village: 'SHEVGAON',
            villageMr: 'शेवगाव',
            caneType: i % 3 === 0 ? 'Adsali' : 'Suru',
            variety: i % 2 === 0 ? 'Co 86032' : 'CoM 0265',
            repAcres: 1.8,
            satAcres: i % 7 === 0 ? 0.0 : 1.75,
            lat: 19.5234 + (i * 0.0025),
            lon: 74.9450 + (i * 0.0028),
            ndvi: i % 7 === 0 ? 0.18 : (0.68 + (i % 5) * 0.02),
            brix: i % 7 === 0 ? 12.0 : 21.4,
            pol: i % 7 === 0 ? 7.5 : 17.5,
            purity: i % 7 === 0 ? 62.5 : 81.8,
            ccs: i % 7 === 0 ? 6.2 : (11.8 + (i % 5) * 0.2),
            status: i % 7 === 0 ? 'GHOST_FLAG' : (i % 2 === 0 ? 'CUT_NOW' : 'WINDOW_15D'),
            isGhost: i % 7 === 0,
            estTons: i % 7 === 0 ? 0 : 75,
            distKm: 12.5,
            plantationDate: '2025-07-15',
            transitTargetHours: 18,
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
    
    setText('telemetryCrushRate', window.MillApp.tcd);
    setText('telemetryCcsRecovery', window.MillApp.currentRecovery.toFixed(2) + '%');
    setText('telemetryPlotsCount', plots.length + ' Plots');
    setText('telemetryCutNowCount', cutNow + ' Plots');
    setText('telemetryGhostBlocked', '₹' + window.MillApp.fraudSavedCrores.toFixed(2) + ' Cr');
    
    const seasonTons = window.MillApp.tcdNumber * window.MillApp.seasonDays;
    const boostPct = (window.MillApp.currentRecovery - window.MillApp.baseRecovery) / 100;
    const extraSugarQtl = (seasonTons * boostPct) * 10;
    const extraRevCr = ((extraSugarQtl * window.MillApp.sugarPrice) / 10000000).toFixed(2);
    
    setText('telemetryNetGain', '+₹' + extraRevCr + ' Cr');
    setText('lblQueuePlotCount', plots.length + ' Plots Ingested');
}

/* ==========================================================================
   3. NAVIGATION TABS
   ========================================================================== */
function initNavbarAndTabs() {
    document.querySelectorAll('.nav-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.nav-tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const viewKey = btn.dataset.view;
            switchView(viewKey);
        });
    });
}

function switchView(viewKey) {
    window.MillApp.activeView = viewKey;
    document.querySelectorAll('.view-container').forEach(c => c.classList.remove('active'));
    const target = document.getElementById('view-' + viewKey);
    if (target) target.classList.add('active');

    if (viewKey === 'map' && window.MillApp.map) {
        setTimeout(() => { window.MillApp.map.invalidateSize(); }, 200);
    } else if (viewKey === 'queue') {
        renderQueueTable();
    } else if (viewKey === 'fraud') {
        renderFraudTable();
    } else if (viewKey === 'roi') {
        calculateRoi();
    }
}

/* ==========================================================================
   4. LEAFLET MAP & CLUSTERING
   ========================================================================== */
function initLeafletMap() {
    const el = document.getElementById('leafletMapInstance');
    if (!el || typeof L === 'undefined') return;

    window.MillApp.map = L.map('leafletMapInstance', {
        zoomControl: false,
        attributionControl: false
    }).setView([19.5714, 74.9474], 13);

    L.control.zoom({ position: 'bottomright' }).addTo(window.MillApp.map);

    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 18
    }).addTo(window.MillApp.map);

    window.MillApp.markersGroup = L.layerGroup().addTo(window.MillApp.map);
    renderMapMarkers();

    const btnSat = document.getElementById('btnLayerSat');
    const btnRadar = document.getElementById('btnLayerRadar');
    if (btnSat && btnRadar) {
        btnSat.addEventListener('click', () => {
            btnSat.classList.add('active');
            btnRadar.classList.remove('active');
            showToast('Switched to Copernicus Sentinel-2 True Color (10m)');
        });
        btnRadar.addEventListener('click', () => {
            btnRadar.classList.add('active');
            btnSat.classList.remove('active');
            showToast('Switched to Sentinel-1 SAR C-Band Radar (Cloud Piercing)');
        });
    }
}

function renderMapMarkers() {
    if (!window.MillApp.map || !window.MillApp.markersGroup) return;
    window.MillApp.markersGroup.clearLayers();

    const plots = window.MillApp.filteredPlots;

    plots.forEach(plot => {
        let color = '#10b981'; // Green CUT_NOW
        if (plot.status === 'WINDOW_15D') color = '#f59e0b'; // Amber
        else if (plot.status === 'VEGETATIVE') color = '#38bdf8'; // Blue
        else if (plot.isGhost || plot.status === 'GHOST_FLAG') color = '#ef4444'; // Red

        const marker = L.circleMarker([plot.lat, plot.lon], {
            radius: plot.status === 'CUT_NOW' ? 7 : 5,
            fillColor: color,
            color: '#ffffff',
            weight: 1.5,
            opacity: 0.9,
            fillOpacity: 0.85
        });

        const tooltipContent = '<div style="font-family:\'Plus Jakarta Sans\',sans-serif; font-size:12px; padding:3px 6px;">' +
            '<strong>' + plot.gatNo + '</strong> &bull; ' + plot.farmerEn + '<br/>' +
            'CCS: <span style="color:' + color + '; font-weight:800;">' + plot.ccs + '%</span> | Variety: ' + plot.variety +
            '</div>';

        marker.bindTooltip(tooltipContent, { direction: 'top', offset: [0, -5] });

        marker.on('click', () => {
            selectPlot(plot.id);
        });

        window.MillApp.markersGroup.addLayer(marker);
    });
}

/* ==========================================================================
   5. FILTERS & SEARCH
   ========================================================================== */
function initFiltersAndSearch() {
    const inputSearch = document.getElementById('inputQueueSearch');
    const selCircle = document.getElementById('selQueueCircle');
    const pills = document.querySelectorAll('.filter-pill');

    if (inputSearch) {
        inputSearch.addEventListener('input', (e) => {
            window.MillApp.searchQuery = e.target.value.toLowerCase().trim();
            applyFilters();
        });
    }

    if (selCircle) {
        selCircle.addEventListener('change', (e) => {
            window.MillApp.filterCircle = e.target.value;
            applyFilters();
        });
    }

    pills.forEach(pill => {
        pill.addEventListener('click', (e) => {
            pills.forEach(p => p.classList.remove('active'));
            e.currentTarget.classList.add('active');
            window.MillApp.filterStatus = e.currentTarget.dataset.filter;
            applyFilters();
        });
    });
}

function populateCircleFilter() {
    const selCircle = document.getElementById('selQueueCircle');
    if (!selCircle) return;

    const circles = [...new Set(window.MillApp.plots.map(p => p.circle))].filter(Boolean);
    selCircle.innerHTML = '<option value="ALL">All Circles (सर्व मंडळे)</option>';
    circles.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c;
        opt.textContent = c;
        selCircle.appendChild(opt);
    });
}

function applyFilters() {
    let list = [...window.MillApp.plots];

    if (window.MillApp.filterStatus !== 'ALL') {
        if (window.MillApp.filterStatus === 'GHOST_FLAG') {
            list = list.filter(p => p.isGhost || p.status === 'GHOST_FLAG');
        } else {
            list = list.filter(p => p.status === window.MillApp.filterStatus);
        }
    }

    if (window.MillApp.filterCircle !== 'ALL') {
        list = list.filter(p => p.circle === window.MillApp.filterCircle);
    }

    if (window.MillApp.searchQuery) {
        const q = window.MillApp.searchQuery;
        list = list.filter(p => 
            p.farmerEn.toLowerCase().includes(q) ||
            p.gatNo.toLowerCase().includes(q) ||
            p.village.toLowerCase().includes(q) ||
            (p.docketId && p.docketId.toLowerCase().includes(q))
        );
    }

    window.MillApp.filteredPlots = list;
    setText('lblQueuePlotCount', list.length + ' Plots Ingested');
    renderQueueList();
    renderMapMarkers();
    if (window.MillApp.activeView === 'queue') renderQueueTable();
}

function renderQueueList() {
    const container = document.getElementById('plotListScrollContainer');
    if (!container) return;

    const plots = window.MillApp.filteredPlots;
    if (plots.length === 0) {
        container.innerHTML = '<div style="padding:30px; text-align:center; color:#94a3b8;"><i class="fa-solid fa-inbox" style="font-size:28px; margin-bottom:8px; display:block;"></i>No sugarcane parcels match this filter.</div>';
        return;
    }

    let html = '';
    plots.slice(0, 80).forEach(p => {
        const isSelected = window.MillApp.selectedPlot && window.MillApp.selectedPlot.id === p.id;
        let badgeClass = 'badge-optimal';
        let badgeText = 'CUT NOW';
        if (p.status === 'WINDOW_15D') { badgeClass = 'badge-warning'; badgeText = '15 DAYS'; }
        else if (p.status === 'VEGETATIVE') { badgeClass = 'badge-subtle'; badgeText = 'ADSALI'; }
        else if (p.isGhost) { badgeClass = 'badge-danger'; badgeText = 'GHOST'; }

        html += '<div class="plot-card-item ' + (isSelected ? 'active' : '') + '" onclick="selectPlot(\'' + p.id + '\')">' +
            '<div class="plot-card-head">' +
                '<div class="plot-gat-pill"><i class="fa-solid fa-seedling"></i> ' + p.gatNo + '</div>' +
                '<span class="badge ' + badgeClass + '">' + badgeText + '</span>' +
            '</div>' +
            '<div class="plot-farmer-name">' + (window.MillApp.lang === 'mr' ? p.farmerMr : p.farmerEn) + '</div>' +
            '<div class="plot-meta-sub">' + p.village + ' &bull; ' + p.circle + ' &bull; ' + p.variety + '</div>' +
            '<div class="plot-metrics-strip">' +
                '<div class="metric-chip"><span>CCS</span><strong style="color:' + (p.ccs >= 11.2 ? '#00e676' : '#f59e0b') + ';">' + p.ccs + '%</strong></div>' +
                '<div class="metric-chip"><span>BRIX</span><strong>' + p.brix + '&deg;Bx</strong></div>' +
                '<div class="metric-chip"><span>ACRES</span><strong>' + p.repAcres + ' Ac</strong></div>' +
                '<div class="metric-chip"><span>EST TONS</span><strong>' + p.estTons + ' MT</strong></div>' +
            '</div>' +
        '</div>';
    });

    if (plots.length > 80) {
        html += '<div style="text-align:center; padding:12px; font-size:11px; color:#94a3b8;">Showing top 80 of ' + plots.length + ' parcels. Use filter or search for specific Gats.</div>';
    }

    container.innerHTML = html;
}

window.selectPlot = function(plotId) {
    const plot = window.MillApp.plots.find(p => p.id === plotId);
    if (!plot) return;

    window.MillApp.selectedPlot = plot;
    renderQueueList();
    openPlotCockpit(plot);

    if (window.MillApp.map) {
        window.MillApp.map.flyTo([plot.lat, plot.lon], 16, { duration: 0.8 });
    }
};

/* ==========================================================================
   6. PLOT COCKPIT SLIDEOVER & CUTTING SLIP DOCKET
   ========================================================================== */
function initPlotCockpit() {
    const closeBtn = document.getElementById('btnCloseCockpit');
    const cockpit = document.getElementById('plotCockpitDrawer');
    if (closeBtn && cockpit) {
        closeBtn.addEventListener('click', () => {
            cockpit.classList.remove('open');
        });
    }
}

function openPlotCockpit(plot) {
    const cockpit = document.getElementById('plotCockpitDrawer');
    if (!cockpit) return;

    setText('cockpitGatBadge', plot.gatNo);
    setText('cockpitFarmerName', plot.farmerEn);
    setText('cockpitVillageCircle', `${plot.village} • ${plot.circle} (${plot.distKm} km from mill)`);
    
    setText('cockpitValCcs', plot.ccs + '%');
    setText('cockpitValBrix', plot.brix + '°Bx');
    setText('cockpitValPol', plot.pol + '%');
    setText('cockpitValPurity', plot.purity + '%');
    setText('cockpitValNdvi', plot.ndvi);
    setText('cockpitValAcres', `${plot.repAcres} Ac (Sat: ${plot.satAcres} Ac)`);
    setText('cockpitValTons', plot.estTons + ' MT');
    setText('cockpitValVariety', `${plot.variety} (${plot.caneType})`);
    setText('cockpitValPlantDate', plot.plantationDate);
    setText('cockpitValDocketId', plot.docketId);

    cockpit.classList.add('open');
}

function initCuttingDocket() {
    const btnOpenDocket = document.getElementById('btnIssueCuttingSlip');
    const docketModal = document.getElementById('cuttingDocketModalOverlay');
    const btnCloseDocket = document.getElementById('btnCloseDocketModal');
    const btnPrintDocket = document.getElementById('btnPrintDocket');

    if (btnOpenDocket && docketModal) {
        btnOpenDocket.addEventListener('click', () => {
            if (!window.MillApp.selectedPlot) return;
            renderOfficialDocket(window.MillApp.selectedPlot);
            docketModal.classList.add('open');
        });
    }

    if (btnCloseDocket && docketModal) {
        btnCloseDocket.addEventListener('click', () => {
            docketModal.classList.remove('open');
        });
    }

    if (btnPrintDocket) {
        btnPrintDocket.addEventListener('click', () => {
            window.print();
        });
    }
}

function renderOfficialDocket(plot) {
    setText('docketMillHeaderName', window.MillApp.millName);
    setText('docketMillHeaderSub', `Sugar Directorate Factory Code: ${window.MillApp.millCode} • Crushing Capacity: ${window.MillApp.tcd}`);
    setText('docketSlipNo', plot.docketId);
    setText('docketPrintDate', new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }));
    
    setText('docketFarmerName', `${plot.farmerEn} / ${plot.farmerMr}`);
    setText('docketGatNo', plot.gatNo);
    setText('docketVillageCircle', `${plot.village} • Circle: ${plot.circle}`);
    setText('docketAcreage', `${plot.repAcres} Acres (Sentinel Verified: ${plot.satAcres} Ac)`);
    setText('docketVariety', `${plot.variety} • Type: ${plot.caneType}`);
    setText('docketEstTonnage', `${plot.estTons} Metric Tonnes`);

    setText('docketValCcs', plot.ccs + '%');
    setText('docketValBrix', plot.brix + '°Bx');
    setText('docketValPol', plot.pol + '%');
    setText('docketMaxHours', `${plot.transitTargetHours} Hours Cut-to-Crush Max`);

    const selGang = window.MillApp.harvestGangs[0] || { name: 'Santosh Kale Mukadam', phone: '98221 45120', type: 'Tractor Trolley' };
    setText('docketAssignedGang', `${selGang.name} (${selGang.type}) • Ph: ${selGang.phone}`);
}

/* ==========================================================================
   7. VIEW 2: HARVEST QUEUE TABLE
   ========================================================================== */
function renderQueueTable() {
    const tbody = document.getElementById('tableQueueBody');
    if (!tbody) return;

    const plots = window.MillApp.filteredPlots;
    let html = '';

    plots.slice(0, 100).forEach(p => {
        let badgeColor = '#10b981';
        let badgeLabel = 'CUT NOW';
        if (p.status === 'WINDOW_15D') { badgeColor = '#f59e0b'; badgeLabel = '15 DAYS'; }
        else if (p.status === 'VEGETATIVE') { badgeColor = '#38bdf8'; badgeLabel = 'ADSALI'; }
        else if (p.isGhost) { badgeColor = '#ef4444'; badgeLabel = 'GHOST'; }

        html += '<tr>' +
            '<td><strong>' + p.docketId + '</strong></td>' +
            '<td>' + p.gatNo + '</td>' +
            '<td><strong>' + p.farmerEn + '</strong></td>' +
            '<td>' + p.village + '</td>' +
            '<td>' + p.variety + '</td>' +
            '<td>' + p.repAcres + ' Ac</td>' +
            '<td style="color:' + badgeColor + '; font-weight:800;">' + p.ccs + '%</td>' +
            '<td>' + p.brix + '&deg;Bx</td>' +
            '<td>' + p.estTons + ' MT</td>' +
            '<td><span style="display:inline-block; padding:3px 8px; border-radius:999px; font-size:10px; font-weight:800; background:' + badgeColor + '22; color:' + badgeColor + '; border:1px solid ' + badgeColor + '44;">' + badgeLabel + '</span></td>' +
            '<td><button onclick="selectPlot(\'' + p.id + '\')" style="background:rgba(0,242,254,0.12); border:1px solid #00f2fe; color:#00f2fe; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;"><i class="fa-solid fa-eye"></i> Inspect</button></td>' +
        '</tr>';
    });

    tbody.innerHTML = html;
}

/* ==========================================================================
   8. VIEW 3: MAHABHUNAKSHA FRAUD BUSTER TABLE
   ========================================================================== */
function initFraudBuster() {
    // Handled in renderFraudTable
}

function renderFraudTable() {
    const tbody = document.getElementById('tableFraudBody');
    if (!tbody) return;

    const ghostPlots = window.MillApp.plots.filter(p => p.isGhost || p.status === 'GHOST_FLAG');
    let html = '';

    ghostPlots.forEach(p => {
        html += '<tr>' +
            '<td style="color:#ef4444; font-weight:800;"><i class="fa-solid fa-triangle-exclamation"></i> ' + p.gatNo + '</td>' +
            '<td><strong>' + p.farmerEn + '</strong></td>' +
            '<td>' + p.village + ' (' + p.circle + ')</td>' +
            '<td>Declared: ' + p.repAcres + ' Ha</td>' +
            '<td style="color:#ef4444;">0.00 Ha (Zero Canopy)</td>' +
            '<td><span style="color:#ef4444; font-family:monospace; font-weight:800;">' + p.ndvi + ' (Fallow)</span></td>' +
            '<td><span style="background:rgba(239,68,68,0.15); border:1px solid #ef4444; color:#ef4444; padding:3px 8px; border-radius:999px; font-size:10px; font-weight:800;">DOCKET BLOCKED</span></td>' +
            '<td style="color:#10b981; font-weight:700;">₹65,000 Advance Saved</td>' +
        '</tr>';
    });

    tbody.innerHTML = html;
}

/* ==========================================================================
   9. VIEW 4: POLARIMETER LAB CALIBRATION
   ========================================================================== */
function initLabStation() {
    const brixIn = document.getElementById('labInputBrix');
    const polIn = document.getElementById('labInputPol');
    const purityOut = document.getElementById('labCalcPurity');
    const ccsOut = document.getElementById('labCalcCcs');

    function recalcLab() {
        if (!brixIn || !polIn) return;
        const brix = parseFloat(brixIn.value) || 0;
        const pol = parseFloat(polIn.value) || 0;

        if (brix > 0) {
            const purity = ((pol / brix) * 100).toFixed(1);
            const ccs = (pol * 1.022 - (brix - pol) * 0.292).toFixed(2);
            if (purityOut) purityOut.textContent = purity + '%';
            if (ccsOut) ccsOut.textContent = ccs + '%';
        }
    }

    if (brixIn) brixIn.addEventListener('input', recalcLab);
    if (polIn) polIn.addEventListener('input', recalcLab);
}

/* ==========================================================================
   10. VIEW 5: FACTORY ROI CALCULATOR
   ========================================================================== */
function initRoiCalculator() {
    const tcdIn = document.getElementById('roiInputTcd');
    const seasonIn = document.getElementById('roiInputSeasonDays');
    const recoveryIn = document.getElementById('roiInputRecoveryBoost');
    const priceIn = document.getElementById('roiInputSugarPrice');

    if (tcdIn) tcdIn.addEventListener('input', calculateRoi);
    if (seasonIn) seasonIn.addEventListener('input', calculateRoi);
    if (recoveryIn) recoveryIn.addEventListener('input', calculateRoi);
    if (priceIn) priceIn.addEventListener('input', calculateRoi);
}

function calculateRoi() {
    const tcd = parseInt(document.getElementById('roiInputTcd')?.value || window.MillApp.tcdNumber);
    const days = parseInt(document.getElementById('roiInputSeasonDays')?.value || window.MillApp.seasonDays);
    const boost = parseFloat(document.getElementById('roiInputRecoveryBoost')?.value || 0.45);
    const price = parseInt(document.getElementById('roiInputSugarPrice')?.value || window.MillApp.sugarPrice);

    const totalCane = tcd * days; // MT
    const extraSugarMt = totalCane * (boost / 100);
    const extraSugarQtl = extraSugarMt * 10;
    const extraSugarBags = Math.round(extraSugarQtl * 2);
    const extraRevInr = extraSugarQtl * price;
    const extraRevCr = (extraRevInr / 10000000).toFixed(2);
    const freightSaveCr = ((totalCane * 25) / 10000000).toFixed(2);
    const totalImpactCr = (parseFloat(extraRevCr) + parseFloat(freightSaveCr)).toFixed(2);

    setText('roiBigNumberCr', '₹' + totalImpactCr + ' Cr');
    setText('roiTotalCaneCrushed', (totalCane / 100000).toFixed(2) + ' Lakh MT');
    setText('roiExtraBagsProduced', '+' + extraSugarBags.toLocaleString() + ' Bags');
    setText('roiSugarRevCrores', '₹' + extraRevCr + ' Cr');
    setText('roiDieselSavedCrores', '₹' + freightSaveCr + ' Cr');
}

/* ==========================================================================
   11. BILINGUAL LANGUAGE TOGGLE
   ========================================================================== */
function initLanguageToggle() {
    const btn = document.getElementById('btnLangToggle');
    if (!btn) return;

    btn.addEventListener('click', () => {
        window.MillApp.lang = (window.MillApp.lang === 'en') ? 'mr' : 'en';
        btn.innerHTML = (window.MillApp.lang === 'en') ? '<i class="fa-solid fa-globe"></i> EN | मराठी' : '<i class="fa-solid fa-globe"></i> मराठी | EN';
        renderQueueList();
        showToast(window.MillApp.lang === 'mr' ? 'भाषा मराठी मध्ये बदलली' : 'Language set to English');
    });
}

/* ==========================================================================
   12. SUGAR MILL DASHBOARD ACTION SUITE & ADD MODALS
   ========================================================================== */
function initMillActionsAndModals() {
    const formAddPlot = document.getElementById('formAddSinglePlot');
    if (formAddPlot) formAddPlot.addEventListener('submit', handleAddNewPlot);

    const formAddGang = document.getElementById('formAddHarvestGang');
    if (formAddGang) formAddGang.addEventListener('submit', handleAddNewGang);

    const formSettings = document.getElementById('formMillParameters');
    if (formSettings) formSettings.addEventListener('submit', handleSaveMillSettings);

    const formLab = document.getElementById('formLogLabTestModal');
    if (formLab) formLab.addEventListener('submit', handleSaveLabModal);

    const bulkFileInput = document.getElementById('inputBulkFile');
    if (bulkFileInput) {
        bulkFileInput.addEventListener('change', handleBulkFileSelection);
    }

    const dropzone = document.getElementById('bulkUploadDropzone');
    if (dropzone && bulkFileInput) {
        dropzone.addEventListener('click', () => bulkFileInput.click());
        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });
        dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                bulkFileInput.files = e.dataTransfer.files;
                handleBulkFileSelection({ target: bulkFileInput });
            }
        });
    }
}

// Modal Open/Close Utilities
window.openAddPlotModal = function() { document.getElementById('modalAddPlot')?.classList.add('open'); };
window.closeAddPlotModal = function() { document.getElementById('modalAddPlot')?.classList.remove('open'); };

window.openBulkUploadModal = function() { 
    document.getElementById('modalBulkUpload')?.classList.add('open'); 
    const prev = document.getElementById('bulkPreviewContainer');
    if (prev) prev.style.display = 'none';
};
window.closeBulkUploadModal = function() { document.getElementById('modalBulkUpload')?.classList.remove('open'); };

window.openAddGangModal = function() { 
    document.getElementById('modalAddGang')?.classList.add('open'); 
    renderGangsList();
};
window.closeAddGangModal = function() { document.getElementById('modalAddGang')?.classList.remove('open'); };

window.openMillSettingsModal = function() { 
    const modal = document.getElementById('modalMillSettings');
    if (!modal) return;
    const tcdIn = document.getElementById('settingInputTcd');
    const daysIn = document.getElementById('settingInputDays');
    const priceIn = document.getElementById('settingInputPrice');
    const baseRecIn = document.getElementById('settingInputBaseRec');
    if (tcdIn) tcdIn.value = window.MillApp.tcdNumber;
    if (daysIn) daysIn.value = window.MillApp.seasonDays;
    if (priceIn) priceIn.value = window.MillApp.sugarPrice;
    if (baseRecIn) baseRecIn.value = window.MillApp.baseRecovery;
    modal.classList.add('open'); 
};
window.closeMillSettingsModal = function() { document.getElementById('modalMillSettings')?.classList.remove('open'); };

window.openAddLabModal = function() {
    const modal = document.getElementById('modalAddLab');
    if (!modal) return;
    populateLabPlotSelector();
    modal.classList.add('open');
};
window.closeAddLabModal = function() { document.getElementById('modalAddLab')?.classList.remove('open'); };

// Action 1: Add Single Plot
function handleAddNewPlot(e) {
    e.preventDefault();

    const farmerEn = document.getElementById('addFarmerEn').value.trim();
    const farmerMr = document.getElementById('addFarmerMr').value.trim() || (farmerEn + ' (शेतकरी)');
    const gatNumber = parseInt(document.getElementById('addGatNo').value.trim()) || 101;
    const circle = document.getElementById('addCircle').value;
    const village = document.getElementById('addVillage').value.trim().toUpperCase() || 'SHEVGAON';
    const caneType = document.getElementById('addCaneType').value;
    const variety = document.getElementById('addVariety').value;
    const plantDate = document.getElementById('addPlantDate').value || '2025-07-15';
    const acres = parseFloat(document.getElementById('addAcres').value) || 2.0;
    
    let lat = parseFloat(document.getElementById('addLat').value);
    let lon = parseFloat(document.getElementById('addLon').value);
    if (isNaN(lat)) lat = 19.5714 + (Math.random() * 0.04 - 0.02);
    if (isNaN(lon)) lon = 74.9474 + (Math.random() * 0.04 - 0.02);

    const pDate = new Date(plantDate);
    const today = new Date();
    const ageDays = Math.max(180, Math.min(520, Math.round((today - pDate) / (1000 * 60 * 60 * 24))));

    let ndvi = 0.74;
    let brix = 21.6;
    let pol = 17.8;
    let ccs = 12.8;
    let status = 'CUT_NOW';

    if (ageDays < 330) {
        status = 'VEGETATIVE';
        ndvi = 0.52;
        brix = 18.2;
        pol = 13.5;
        ccs = 10.1;
    } else if (ageDays < 370) {
        status = 'WINDOW_15D';
        ndvi = 0.64;
        brix = 20.1;
        pol = 15.8;
        ccs = 11.4;
    } else {
        status = 'CUT_NOW';
        ndvi = 0.78;
        brix = 22.0;
        pol = 18.2;
        ccs = 12.95;
    }

    const estTons = Math.round(acres * (caneType === 'Adsali' ? 50 : 40));
    const newPlotId = 'PLT-' + String(window.MillApp.plots.length + 1).padStart(4, '0');
    const docketId = 'DOK-2026-' + (1200 + window.MillApp.plots.length);

    const newPlot = {
        id: newPlotId,
        plotNo: window.MillApp.plots.length + 1,
        farmerEn: farmerEn,
        farmerMr: farmerMr,
        gatNo: 'Gat ' + gatNumber,
        gatNumber: gatNumber,
        circle: circle,
        village: village,
        villageMr: village,
        caneType: caneType,
        variety: variety,
        repAcres: acres,
        satAcres: parseFloat((acres * 0.98).toFixed(2)),
        lat: parseFloat(lat.toFixed(6)),
        lon: parseFloat(lon.toFixed(6)),
        ndvi: ndvi,
        brix: brix,
        pol: pol,
        purity: parseFloat(((pol / brix) * 100).toFixed(1)),
        ccs: ccs,
        status: status,
        isGhost: false,
        estTons: estTons,
        distKm: 14.2,
        plantationDate: plantDate,
        transitTargetHours: status === 'CUT_NOW' ? 16 : 24,
        docketId: docketId
    };

    window.MillApp.plots.unshift(newPlot);
    window.MillApp.customPlots.unshift(newPlot);
    localStorage.setItem('ikshu_custom_plots', JSON.stringify(window.MillApp.customPlots));

    applyFilters();
    updateTelemetryRibbon();
    closeAddPlotModal();
    e.target.reset();

    selectPlot(newPlot.id);
    showToast(`Registered Gat ${gatNumber} (${farmerEn})! Satellite CCS: ${ccs}% (${status})`);
}

// Action 2: Bulk CSV/Excel Upload
function handleBulkFileSelection(e) {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(evt) {
        const text = evt.target.result;
        parseBulkHarvestRegister(text, file.name);
    };
    reader.readAsText(file);
}

function parseBulkHarvestRegister(csvText, fileName) {
    const lines = csvText.split('\n').filter(l => l.trim().length > 0);
    if (lines.length < 2) {
        alert('File is empty or contains no plot rows.');
        return;
    }

    const parsedPlots = [];
    for (let i = 1; i < lines.length; i++) {
        const cols = lines[i].split(',').map(c => c.trim().replace(/^"|"$/g, ''));
        if (cols.length < 4) continue;

        const plotNo = cols[0] || (window.MillApp.plots.length + i);
        const farmer = cols[1] || `Farmer ${plotNo}`;
        const gut = cols[2] || `Gat ${100 + i}`;
        const village = (cols[3] || 'SHEVGAON').toUpperCase();
        const circle = cols[4] || 'Shevgaon Central';
        const caneType = cols[5] || 'Adsali';
        const variety = cols[6] || 'Co 86032';
        const plantDate = cols[7] || '2025-07-15';
        const acres = parseFloat(cols[8]) || 2.0;
        let lat = parseFloat(cols[9]) || (19.5714 + (i * 0.002));
        let lon = parseFloat(cols[10]) || (74.9474 + (i * 0.002));

        const ndvi = 0.65 + ((i % 10) * 0.015);
        const brix = 21.2 + ((i % 8) * 0.15);
        const pol = parseFloat((brix * 0.80).toFixed(2));
        const ccs = parseFloat((pol * 1.022 - (brix - pol) * 0.292).toFixed(2));
        const estTons = Math.round(acres * 45);

        parsedPlots.push({
            id: 'PLT-' + String(window.MillApp.plots.length + i).padStart(4, '0'),
            plotNo: plotNo,
            farmerEn: farmer,
            farmerMr: farmer + ' (शेतकरी)',
            gatNo: gut.startsWith('Gat') ? gut : 'Gat ' + gut,
            gatNumber: parseInt(gut.replace(/\D/g, '')) || (100 + i),
            circle: circle,
            village: village,
            villageMr: village,
            caneType: caneType,
            variety: variety,
            repAcres: acres,
            satAcres: parseFloat((acres * 0.95).toFixed(2)),
            lat: lat,
            lon: lon,
            ndvi: ndvi,
            brix: parseFloat(brix.toFixed(1)),
            pol: pol,
            purity: parseFloat(((pol / brix) * 100).toFixed(1)),
            ccs: ccs,
            status: ccs >= 11.2 ? 'CUT_NOW' : 'WINDOW_15D',
            isGhost: false,
            estTons: estTons,
            distKm: 12.0,
            plantationDate: plantDate,
            transitTargetHours: 18,
            docketId: 'DOK-2026-' + (1300 + i)
        });
    }

    window.MillApp.pendingBulkPlots = parsedPlots;

    const previewContainer = document.getElementById('bulkPreviewContainer');
    const previewCount = document.getElementById('bulkPreviewCount');
    const previewBody = document.getElementById('bulkPreviewTableBody');

    if (previewContainer && previewBody) {
        previewCount.textContent = `Detected ${parsedPlots.length} valid parcels from "${fileName}"`;
        let html = '';
        parsedPlots.slice(0, 5).forEach(p => {
            html += `<tr><td>${p.gatNo}</td><td>${p.farmerEn}</td><td>${p.village}</td><td>${p.variety}</td><td>${p.repAcres} Ac</td><td style="color:#00e676; font-weight:800;">${p.ccs}%</td></tr>`;
        });
        previewBody.innerHTML = html;
        previewContainer.style.display = 'block';
    }
}

window.handleConfirmBulkImport = function() {
    const list = window.MillApp.pendingBulkPlots;
    if (!list || list.length === 0) return;

    window.MillApp.plots = [...list, ...window.MillApp.plots];
    window.MillApp.customPlots = [...list, ...window.MillApp.customPlots];
    localStorage.setItem('ikshu_custom_plots', JSON.stringify(window.MillApp.customPlots));

    applyFilters();
    updateTelemetryRibbon();
    closeBulkUploadModal();
    showToast(`Successfully ingested ${list.length} parcels into live cutting queue!`);
    window.MillApp.pendingBulkPlots = [];
};

window.downloadStandardRegisterTemplate = function() {
    const csvContent = "Plot No,Farmer,Gut,Village,Circle,Cane Type,Variety Name,Plantation Date,Area_Acres,centroid_lat,centroid_lon\n" +
        "101,SURESH TUKARAM SHINDE,Gat 142,SAINATHNAGAR,Shevgaon Central,Adsali,Co 86032,2025-07-10,2.5,19.5714,74.9474\n" +
        "102,BABASAHEB ANANDRAO PATIL,Gat 148,BODHEGAON,Bodhegaon Sector,Suru,CoM 0265,2025-08-15,1.8,19.5620,74.9520\n" +
        "103,VISHNU SHIVAJI GAIKWAD,Gat 204,NEWASA PHATA,Newasa Phata Circle,Adsali,Co 0118,2025-07-20,3.2,19.5840,74.9310\n";

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'Sugar_Mill_Harvest_Register_Template.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast('Downloaded Sugar Mill Harvest Register Template (.csv)');
};

// Action 3: Harvester Gangs Management
function renderGangsList() {
    const container = document.getElementById('gangsListContainer');
    if (!container) return;

    const gangs = window.MillApp.harvestGangs;
    let html = '';
    gangs.forEach(g => {
        html += '<div style="background:rgba(14,25,45,0.7); border:1px solid var(--border-subtle); border-radius:var(--radius-sm); padding:10px 14px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">' +
            '<div>' +
                '<strong style="color:#ffffff;">' + g.name + '</strong> (' + g.type + ')<br/>' +
                '<span style="font-size:11px; color:#94a3b8;">Phone: ' + g.phone + ' &bull; Circle: ' + g.circle + ' &bull; Reg: ' + g.regNo + '</span>' +
            '</div>' +
            '<div style="text-align:right;">' +
                '<span style="color:#00e676; font-weight:800;">' + g.quotaMt + ' MT/Day</span>' +
            '</div>' +
        '</div>';
    });
    container.innerHTML = html;
}

function handleAddNewGang(e) {
    e.preventDefault();
    const name = document.getElementById('gangName').value.trim();
    const phone = document.getElementById('gangPhone').value.trim();
    const type = document.getElementById('gangType').value;
    const regNo = document.getElementById('gangRegNo').value.trim();
    const quotaMt = parseInt(document.getElementById('gangQuota').value) || 40;
    const circle = document.getElementById('gangCircle').value;

    const newGang = {
        id: 'GANG-' + String(window.MillApp.harvestGangs.length + 1).padStart(2, '0'),
        name: name,
        phone: phone,
        type: type,
        regNo: regNo,
        quotaMt: quotaMt,
        circle: circle
    };

    window.MillApp.harvestGangs.push(newGang);
    localStorage.setItem('ikshu_harvest_gangs', JSON.stringify(window.MillApp.harvestGangs));

    renderGangsList();
    e.target.reset();
    showToast(`Harvesting Gang "${name}" registered (${quotaMt} MT/Day capacity)!`);
}

// Action 4: Mill Operational Parameters
function handleSaveMillSettings(e) {
    e.preventDefault();
    const tcd = parseInt(document.getElementById('settingInputTcd').value) || 4500;
    const days = parseInt(document.getElementById('settingInputDays').value) || 150;
    const price = parseInt(document.getElementById('settingInputPrice').value) || 3600;
    const baseRec = parseFloat(document.getElementById('settingInputBaseRec').value) || 10.45;

    window.MillApp.tcdNumber = tcd;
    window.MillApp.tcd = tcd.toLocaleString() + ' TCD';
    window.MillApp.seasonDays = days;
    window.MillApp.sugarPrice = price;
    window.MillApp.baseRecovery = baseRec;

    localStorage.setItem('ikshu_mill_settings', JSON.stringify({
        tcd: tcd,
        seasonDays: days,
        sugarPrice: price,
        baseRecovery: baseRec
    }));

    updateTelemetryRibbon();
    if (window.MillApp.activeView === 'roi') calculateRoi();
    closeMillSettingsModal();
    showToast(`Factory crushing parameters saved! Capacity set to ${window.MillApp.tcd}.`);
}

// Action 5: Log Polarimeter Lab Test Modal
function populateLabPlotSelector() {
    const sel = document.getElementById('labModalSelPlot');
    if (!sel) return;

    sel.innerHTML = '';
    window.MillApp.plots.slice(0, 50).forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = `${p.gatNo} - ${p.farmerEn} (${p.variety})`;
        sel.appendChild(opt);
    });
}

function handleSaveLabModal(e) {
    e.preventDefault();
    const plotId = document.getElementById('labModalSelPlot').value;
    const brix = parseFloat(document.getElementById('labModalBrix').value) || 21.0;
    const pol = parseFloat(document.getElementById('labModalPol').value) || 17.0;

    const purity = parseFloat(((pol / brix) * 100).toFixed(1));
    const ccs = parseFloat((pol * 1.022 - (brix - pol) * 0.292).toFixed(2));

    const plot = window.MillApp.plots.find(p => p.id === plotId);
    if (plot) {
        plot.brix = brix;
        plot.pol = pol;
        plot.purity = purity;
        plot.ccs = ccs;
        plot.status = ccs >= 11.2 ? 'CUT_NOW' : 'WINDOW_15D';
    }

    applyFilters();
    updateTelemetryRibbon();
    closeAddLabModal();
    showToast(`Lab polarimeter test committed for ${plot ? plot.gatNo : 'Plot'}! CCS: ${ccs}%`);
}

// Action 6: Export Daily Cutting Program
window.exportDailyCuttingProgram = function() {
    const cutNowPlots = window.MillApp.plots.filter(p => p.status === 'CUT_NOW');
    if (cutNowPlots.length === 0) {
        showToast('No plots currently in CUT_NOW status.');
        return;
    }

    let csv = "Docket ID,Gat No,Farmer Name,Village,Circle,Variety,Cane Type,Area (Ac),Est Tonnage (MT),CCS Recovery (%),Max Transit Hours,Status\n";
    cutNowPlots.forEach(p => {
        csv += `${p.docketId},${p.gatNo},"${p.farmerEn}",${p.village},${p.circle},${p.variety},${p.caneType},${p.repAcres},${p.estTons},${p.ccs}%,${p.transitTargetHours},READY_FOR_CRUSH\n`;
    });

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `Daily_Cutting_Program_${window.MillApp.shortName.replace(/\s+/g, '_')}_${new Date().toISOString().slice(0,10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast(`Exported ${cutNowPlots.length} cutting dockets for weighbridge ERP dispatch!`);
};

/* ==========================================================================
   13. TOAST NOTIFICATION UTILITY
   ========================================================================== */
function showToast(message, type = 'success') {
    let toast = document.getElementById('terminalToastBox');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'terminalToastBox';
        toast.className = 'terminal-toast';
        document.body.appendChild(toast);
    }

    toast.innerHTML = '<i class="fa-solid fa-circle-check" style="color:#00e676; font-size:1.1rem;"></i> <span>' + message + '</span>';
    toast.classList.add('show');

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3800);
}

// Text Helper
function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

// Terminal Lock / Unlock
window.handleAuthSubmit = function(e) {
    e.preventDefault();
    const key = document.getElementById('accessKeyInput').value.trim();
    if (key.toLowerCase() === 'ikshu2026' || key.length >= 4) {
        document.getElementById('enterpriseAuthOverlay').classList.add('unlocked');
        showToast('Terminal unlocked. Active factory: ' + window.MillApp.shortName);
    } else {
        document.getElementById('authErrorMsg').style.display = 'block';
    }
};

window.unlockWithSandbox = function(millName, role, tcd) {
    window.MillApp.millName = millName;
    window.MillApp.shortName = millName.split(' ')[0] + ' SSK';
    window.MillApp.role = role;
    window.MillApp.tcd = tcd;
    initMillProfile();
    updateTelemetryRibbon();
    document.getElementById('enterpriseAuthOverlay').classList.add('unlocked');
    showToast('Demo Evaluator Session Activated');
};

window.lockTerminal = function() {
    document.getElementById('enterpriseAuthOverlay').classList.remove('unlocked');
};
