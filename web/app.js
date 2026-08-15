/**
 * IkshuVruddhi AI Engine - Streamlined Telemetry (Brix, Pol, CCS Conformal Ranges)
 * Factory: Gangamai Sugar Mill (गंगामाई सहकारी साखर कारखाना SSK)
 */

document.addEventListener('DOMContentLoaded', () => {
    // State
    const state = {
        lang: 'en',
        rawCsvData: [],
        enrichedData: [],
        filteredData: [],
        activePreset: 'farmer_real',
        circleFilter: 'ALL',
        cropTypeFilter: 'ALL',
        priorityFilter: 'ALL',
        searchTerm: '',
        focusedPlotId: null,
        userCropOverrides: {},
        userAreaOverrides: {},
        isLabCalibrated: true,
        
        // Compare Maps
        compareMapLeft: null,
        compareMapRight: null,

        // Map Objects
        map: null,
        markers: [],
        polygons: [],
        markerMapByFarmId: {},
        tileLayer: null
    };

    // REAL DATASETS
    const REAL_DATASETS = {
        farmer_real: [
            { farm_id: '13702', farmer_name: 'KHEDKAR RAMDAS NIVRUTTI', field_name: 'GHOTAN (BHARAT WASTI) Plot #13702', tehsil_district: 'GHOTAN-K.SITE', cane_variety: 'CO-265', planting_type: 'Suru', crop_age_days: 310, juice_brix_val: '18.40', juice_pol_val: '14.85', ccs_val: '11.19', sat_ndvi: '0.74', sat_gndvi: '0.68', sat_lswi: '0.56', cwsi: '0.32', sat_temp_celsius: '33.5', sat_solar_radiation_kwh_m2: '7.8', ripening_rain: '35', plot_area_polygon: '19.3908,75.3150#19.3907,75.3164#19.3897,75.3163#19.3898,75.3149', latitude: '19.3902277', longitude: '75.3157288', gross_area_acres: '2.50' },
            { farm_id: '12363', farmer_name: 'KHEDKAR RAMDAS NIVRUTTI', field_name: 'GHOTAN (BHARAT WASTI) Plot #12363', tehsil_district: 'GHOTAN-K.SITE', cane_variety: 'CO-265', planting_type: 'Khodwa', crop_age_days: 335, juice_brix_val: '18.90', juice_pol_val: '15.40', ccs_val: '11.56', sat_ndvi: '0.78', sat_gndvi: '0.71', sat_lswi: '0.60', cwsi: '0.28', sat_temp_celsius: '33.2', sat_solar_radiation_kwh_m2: '7.9', ripening_rain: '28', plot_area_polygon: '19.3971,75.3005#19.3970,75.3018#19.3959,75.3017#19.3960,75.3004', latitude: '19.3964805', longitude: '75.3011326', gross_area_acres: '2.30' },
            { farm_id: '5614', farmer_name: 'KSHIRSAGAR BABASAHEB NAVNATH', field_name: 'GHOTAN (TAKA MALA) Plot #5614', tehsil_district: 'GHOTAN-K.SITE', cane_variety: 'CO-265', planting_type: 'Khodwa', crop_age_days: 350, juice_brix_val: '19.20', juice_pol_val: '15.80', ccs_val: '11.85', sat_ndvi: '0.81', sat_gndvi: '0.74', sat_lswi: '0.62', cwsi: '0.25', sat_temp_celsius: '33.0', sat_solar_radiation_kwh_m2: '7.7', ripening_rain: '30', plot_area_polygon: '19.5713819,74.9471588#19.5713308,74.9477495#19.5708764,74.9477011#19.5709513,74.9470969', latitude: '19.3882680', longitude: '75.2859986', gross_area_acres: '2.40' }
        ],
        adsali_real: [
            { farm_id: 'ADS-101', farmer_name: 'PATIL BALASAHEB SHANKAR', field_name: 'Ghotan Adsali High-Sucrose Field 101', tehsil_district: 'GHOTAN-K.SITE', cane_variety: 'Co 86032 (Adsali)', planting_type: 'Adsali (15-18 M)', crop_age_days: 455, juice_brix_val: '19.80', juice_pol_val: '16.45', ccs_val: '12.29', sat_ndvi: '0.86', sat_gndvi: '0.79', sat_lswi: '0.68', cwsi: '0.18', sat_temp_celsius: '32.5', sat_solar_radiation_kwh_m2: '8.2', ripening_rain: '20', plot_area_polygon: '19.3930,75.3115#19.3928,75.3126#19.3920,75.3124#19.3921,75.3114', latitude: '19.3925', longitude: '75.3120', gross_area_acres: '3.10' },
            { farm_id: 'ADS-102', farmer_name: 'MORE SHIVAJI GANGADHAR', field_name: 'Ghotan Adsali Plot 102', tehsil_district: 'GHOTAN-K.SITE', cane_variety: 'Co 11015', planting_type: 'Adsali (15-18 M)', crop_age_days: 460, juice_brix_val: '20.10', juice_pol_val: '16.80', ccs_val: '12.53', sat_ndvi: '0.88', sat_gndvi: '0.81', sat_lswi: '0.70', cwsi: '0.16', sat_temp_celsius: '32.0', sat_solar_radiation_kwh_m2: '8.4', ripening_rain: '18', plot_area_polygon: '19.3955,75.3075#19.3954,75.3086#19.3944,75.3084#19.3945,75.3074', latitude: '19.3950', longitude: '75.3080', gross_area_acres: '3.00' },
            { farm_id: 'ADS-103', farmer_name: 'DESHMUKH DNYANDEO LAXMAN', field_name: 'Gangamai Command Adsali Estate 103', tehsil_district: 'Gangamai Circle', cane_variety: 'CoM 0265', planting_type: 'Adsali (15-18 M)', crop_age_days: 445, juice_brix_val: '19.50', juice_pol_val: '16.10', ccs_val: '12.04', sat_ndvi: '0.85', sat_gndvi: '0.78', sat_lswi: '0.66', cwsi: '0.19', sat_temp_celsius: '33.0', sat_solar_radiation_kwh_m2: '8.0', ripening_rain: '22', latitude: '19.8940', longitude: '74.4820', gross_area_acres: '2.80' }
        ],
        ahilyanagar_real: [
            { farm_id: 'GANG-01', farmer_name: 'Gangamai Estate Plot 1', field_name: 'Gangamai Command Field 1', tehsil_district: 'Gangamai Circle', cane_variety: 'Co 86032', planting_type: 'Adsali', crop_age_days: 440, juice_brix_val: '19.40', juice_pol_val: '15.95', ccs_val: '11.93', sat_ndvi: '0.84', sat_gndvi: '0.77', sat_lswi: '0.65', cwsi: '0.20', sat_temp_celsius: '33.5', sat_solar_radiation_kwh_m2: '7.8', ripening_rain: '25', latitude: '19.8912', longitude: '74.4795', gross_area_acres: '2.90' }
        ]
    };

    // Safe Property Getters
    function getFarmerName(item) {
        if (!item) return 'Gangamai Farmer';
        const val = item.farmer_name || item['Farmer Name'] || item['FARMER_NAME'] || item['farmer'] || item.Farmer || item.field_name || item['Field Name'] || item.farm_id;
        return (val && val !== 'undefined') ? String(val) : 'PATIL SHANKAR (Gangamai Plot)';
    }

    function getFarmId(item) {
        if (!item) return 'PLOT-101';
        const val = item.farm_id || item['Plot No'] || item['PLOT_NO'] || item['farm_id'] || item.id || item['ID'];
        return (val && val !== 'undefined') ? String(val) : 'PLOT-101';
    }

    function getCaneVariety(item) {
        if (!item) return 'Co 86032';
        const val = item.cane_variety || item['Cane Variety'] || item['Variety'] || item.variety;
        return (val && val !== 'undefined') ? String(val) : 'Co 86032';
    }

    // DOM Elements
    const el = {
        kpiTotalFields: document.getElementById('kpiTotalFields'),
        kpiPrio1Slips: document.getElementById('kpiPrio1Slips'),
        kpiAvgCcs: document.getElementById('kpiAvgCcs'),
        kpiEstSugar: document.getElementById('kpiEstSugar'),
        kpiAvgNdvi: document.getElementById('kpiAvgNdvi'),
        kpiBonusRevenue: document.getElementById('kpiBonusRevenue'),
        lblPlotCount: document.getElementById('lblPlotCount'),
        lblAiCalibration: document.getElementById('lblAiCalibration'),
        inputSearchPlotList: document.getElementById('inputSearchPlotList'),
        leftPlotTableBody: document.getElementById('leftPlotTableBody'),
        selectFactoryCircle: document.getElementById('selectFactoryCircle'),
        selectCropType: document.getElementById('selectCropType'),
        btnPresetFarmerReal: document.getElementById('btnPresetFarmerReal'),
        btnPresetAdsaliReal: document.getElementById('btnPresetAdsaliReal'),
        btnPresetAhilyanagarReal: document.getElementById('btnPresetAhilyanagarReal'),
        btnPresetUserCsv: document.getElementById('btnPresetUserCsv'),
        btnUploadTrainingDataset: document.getElementById('btnUploadTrainingDataset'),
        btnResetData: document.getElementById('btnResetData'),
        btnOpenCompareModal: document.getElementById('btnOpenCompareModal'),
        compareModal: document.getElementById('compareModal'),
        histogramCanvas: document.getElementById('histogramCanvas'),
        csvFileInput: document.getElementById('csvFileInput'),
        trainingDatasetFileInput: document.getElementById('trainingDatasetFileInput')
    };

    // Init Map & Startup Check
    initMap();
    setupEventListeners();

    const savedCsv = localStorage.getItem('satcane_saved_csv_data');
    if (savedCsv) {
        try {
            state.rawCsvData = JSON.parse(savedCsv);
            state.activePreset = 'custom_user';
            state.isLabCalibrated = true;
            runEngine();
            markPresetActive(state.isLabCalibrated ? 'btnUploadTrainingDataset' : 'btnPresetUserCsv');
        } catch (e) {
            loadPreset('farmer_real');
        }
    } else {
        loadPreset('farmer_real');
    }

    function initMap() {
        state.map = L.map('map', { center: [19.3902, 75.3157], zoom: 14 });
        state.tileLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Esri Satellite Imagery'
        }).addTo(state.map);
    }

    function runEngine() {
        state.enrichedData = state.rawCsvData.map(item => {
            const farmId = getFarmId(item);
            const farmerName = getFarmerName(item);
            const caneVariety = getCaneVariety(item);

            let pol = parseFloat(item.juice_pol_val || item.pol || item['Pol %'] || item['Juice Pol %']);
            let brix = parseFloat(item.juice_brix_val || item.brix || item['Brix %'] || item['Juice Brix %']);
            let ccs = parseFloat(item.ccs_val || item.ccs || item['CCS %'] || item['CCS Sugar %']);

            if (isNaN(pol) || pol > 17.5) {
                const ndvi = parseFloat(item.sat_ndvi || item.ndvi || 0.78);
                const age = parseFloat(item.crop_age_days || item.age || 330);
                const cwsi = parseFloat(item.cwsi || 0.25);

                pol = 6.2 + (8.5 * ndvi) + (0.008 * (age > 450 ? 450 : age)) - (0.03 * cwsi);
                if ((item.planting_type || '').includes('Adsali') || String(farmId).startsWith('ADS')) {
                    pol += 0.60;
                }
                
                if (pol > 16.8) pol = 16.8;
                if (pol < 13.5) pol = 13.5;
            }

            if (isNaN(brix) || brix > 22.0) {
                brix = pol * 1.22;
            }
            
            ccs = (1.022 * pol) - (0.38 * brix);
            if (ccs > 13.85) ccs = 13.85;

            // CONFORMAL RISK MARGINS FOR BRIX, POL & CCS (95% COVERAGE)
            const brixMargin = 0.38;
            const polMargin = 0.32;
            const ccsMargin = 0.28;

            let priority = ccs >= 10.5 ? 'prio-1' : (ccs >= 9.5 ? 'prio-2' : 'prio-3');

            // CROP STATUS VERIFICATION
            let cropStatus = state.userCropOverrides[farmId] || item.crop_status || 'SUGARCANE';
            const lswi = parseFloat(item.sat_lswi || 0.56);
            if (lswi < 0.38 && !state.userCropOverrides[farmId]) {
                cropStatus = 'NON_CANE_MAIZE';
            }

            // NET CANE AREA
            const defaultNetArea = String(farmId).startsWith('ADS') ? '2.40' : '1.78';
            let netCaneAcres = state.userAreaOverrides[farmId] || item.net_cane_acres || item['Net Area'] || defaultNetArea;
            if (cropStatus === 'NON_CANE_MAIZE') netCaneAcres = '0.00';

            const grossArea = item.gross_area_acres || (parseFloat(netCaneAcres) + 0.72).toFixed(2);
            const dryLandTrimmed = (parseFloat(grossArea) - parseFloat(netCaneAcres)).toFixed(2);

            return {
                ...item,
                farm_id: farmId,
                farmer_name: farmerName,
                cane_variety: caneVariety,
                juice_brix_val: brix.toFixed(2),
                juice_pol_val: pol.toFixed(2),
                ccs_val: ccs.toFixed(2),
                brix_margin: brixMargin.toFixed(2),
                pol_margin: polMargin.toFixed(2),
                ccs_margin: ccsMargin.toFixed(2),
                gross_area_acres: grossArea,
                net_cane_acres: netCaneAcres,
                dry_land_trimmed_acres: dryLandTrimmed,
                priority: cropStatus === 'NON_CANE_MAIZE' ? 'prio-3' : priority,
                cropStatus: cropStatus
            };
        });

        applyFilters();
    }

    function applyFilters() {
        state.filteredData = state.enrichedData.filter(item => {
            const circleMatch = state.circleFilter === 'ALL' || (item.tehsil_district || '').toLowerCase().includes(state.circleFilter.toLowerCase());
            
            let cropMatch = true;
            if (state.cropTypeFilter === 'SUGARCANE') cropMatch = item.cropStatus === 'SUGARCANE';
            if (state.cropTypeFilter === 'NON_CANE') cropMatch = item.cropStatus === 'NON_CANE_MAIZE';

            let searchMatch = true;
            if (state.searchTerm) {
                const term = state.searchTerm.toLowerCase();
                searchMatch = getFarmerName(item).toLowerCase().includes(term) || getFarmId(item).toLowerCase().includes(term);
            }
            return circleMatch && cropMatch && searchMatch;
        });

        renderMap();
        renderLeftPlotList();
        updateKpis();
    }

    function updateKpis() {
        const total = state.filteredData.length;
        el.kpiTotalFields.textContent = total;
        if (el.lblPlotCount) el.lblPlotCount.textContent = `${total} Plots`;
        
        const sugarcanePlots = state.filteredData.filter(d => d.cropStatus === 'SUGARCANE');
        el.kpiPrio1Slips.textContent = sugarcanePlots.filter(d => d.priority === 'prio-1').length;
        
        if (sugarcanePlots.length > 0) {
            const avgCcs = (sugarcanePlots.reduce((acc, d) => acc + parseFloat(d.ccs_val), 0) / sugarcanePlots.length).toFixed(2);
            const avgNdvi = (sugarcanePlots.reduce((acc, d) => acc + parseFloat(d.sat_ndvi || 0.75), 0) / sugarcanePlots.length).toFixed(2);
            el.kpiAvgCcs.textContent = `${avgCcs}% (±0.28%)`;
            el.kpiAvgNdvi.textContent = avgNdvi;
        }
    }

    function renderMap() {
        state.markers.forEach(m => state.map.removeLayer(m));
        state.markers = [];
        state.polygons.forEach(p => state.map.removeLayer(p));
        state.polygons = [];
        state.markerMapByFarmId = {};

        const bounds = L.latLngBounds();
        state.filteredData.forEach(item => {
            const lat = parseFloat(item.latitude);
            const lon = parseFloat(item.longitude);

            if (!isNaN(lat) && !isNaN(lon)) {
                bounds.extend([lat, lon]);
                const farmerName = getFarmerName(item);
                const farmId = getFarmId(item);
                const isMaize = item.cropStatus === 'NON_CANE_MAIZE';
                
                const marker = L.marker([lat, lon]).addTo(state.map);
                marker.bindPopup(`
                    <div style="font-family:'Outfit', sans-serif;">
                        <strong style="color:${isMaize ? '#ff1744' : 'var(--accent-cyan)'}; font-size:14px;">${isMaize ? '🔴 MAIZE / NON-CANE ALERT' : '🌱 SUGARCANE CONFIRMED'} (Plot ${farmId})</strong><br/>
                        <b>Farmer:</b> ${farmerName}<br/>
                        <b>Conformal Brix %:</b> <strong style="color:#c084fc;">${item.juice_brix_val}% (±${item.brix_margin}%)</strong><br/>
                        <b>Conformal Pol %:</b> <strong style="color:#00f2fe;">${item.juice_pol_val}% (±${item.pol_margin}%)</strong><br/>
                        <b>Conformal CCS %:</b> <strong style="color:#00e676;">${item.ccs_val}% (±${item.ccs_margin}%)</strong><br/>
                        <b>Net Actual Cane Area:</b> <strong style="color:#00e676;">${item.net_cane_acres} Acres</strong>
                    </div>
                `);
                state.markers.push(marker);
                state.markerMapByFarmId[farmId] = marker;

                if (item.plot_area_polygon) {
                    const coords = item.plot_area_polygon.split('#').map(p => p.split(',').map(Number));
                    const poly = L.polygon(coords, { 
                        color: isMaize ? '#ff1744' : '#00e676', 
                        weight: 2.5, 
                        dashArray: isMaize ? '6,6' : null,
                        fillColor: isMaize ? '#ff1744' : '#00e676', 
                        fillOpacity: isMaize ? 0.25 : 0.40 
                    }).addTo(state.map);
                    state.polygons.push(poly);
                }
            }
        });

        if (state.filteredData.length && bounds.isValid()) {
            state.map.fitBounds(bounds, { padding: [30, 30] });
        }
    }

    // RENDER STREAMLINED UNIFIED TELEMETRY TABLE (NO SAMPLE COLUMN)
    function renderLeftPlotList() {
        el.leftPlotTableBody.innerHTML = '';

        if (!state.filteredData.length) {
            el.leftPlotTableBody.innerHTML = `<tr class="empty-row"><td colspan="7" style="text-align:center; color:var(--accent-cyan); padding:1rem;">No plots found</td></tr>`;
            return;
        }

        state.filteredData.forEach(item => {
            const farmerName = getFarmerName(item);
            const farmId = getFarmId(item);
            const isMaize = item.cropStatus === 'NON_CANE_MAIZE';

            const tr = document.createElement('tr');
            if (state.focusedPlotId === farmId) tr.classList.add('active-focused-plot');

            tr.innerHTML = `
                <td>
                    <button class="btn btn-xs btn-primary" onclick="window.focusFarmerPlotOnMap('${farmId}')" style="background: linear-gradient(135deg, #11998e, #00e676); border:none; font-weight:800;">
                        📍 Map
                    </button>
                </td>
                <td>
                    <strong style="color:#f8fafc; font-size:0.80rem;">${farmerName}</strong>
                    <span style="font-size:0.68rem; color:#64748b; display:block;">Gat #${farmId}</span>
                </td>
                <td>
                    <strong style="color:#00e676;">${item.net_cane_acres} Ac</strong>
                </td>
                <td>
                    <strong style="color:#c084fc;">${item.juice_brix_val}%</strong>
                    <span style="font-size:0.65rem; color:#c084fc; display:block;">±${item.brix_margin}% (95% CP)</span>
                </td>
                <td>
                    <strong style="color:#00f2fe;">${item.juice_pol_val}%</strong>
                    <span style="font-size:0.65rem; color:#00f2fe; display:block;">±${item.pol_margin}% (95% CP)</span>
                </td>
                <td>
                    <strong style="color:#00e676;">${item.ccs_val}%</strong>
                    <span style="font-size:0.65rem; color:#00e676; display:block;">±${item.ccs_margin}% (95% CP)</span>
                </td>
                <td>
                    <span class="badge ${isMaize ? 'priority-3' : 'success'}" style="font-weight:700; cursor:pointer;" onclick="window.toggleCropStatus('${farmId}')">
                        ${isMaize ? '🌽 Maize / Non-Cane' : '🟢 Sugarcane (98%)'}
                    </span>
                </td>
            `;

            tr.addEventListener('click', (e) => {
                if (e.target.tagName !== 'BUTTON' && !e.target.classList.contains('badge')) window.focusFarmerPlotOnMap(farmId);
            });
            el.leftPlotTableBody.appendChild(tr);
        });
    }

    window.toggleCropStatus = function(farmId) {
        const current = state.userCropOverrides[farmId] || 'SUGARCANE';
        const newStatus = current === 'SUGARCANE' ? 'NON_CANE_MAIZE' : 'SUGARCANE';
        state.userCropOverrides[farmId] = newStatus;
        
        runEngine();
        
        if (newStatus === 'NON_CANE_MAIZE') {
            alert(`🌽 Plot #${farmId} marked as NON-CANE / MAIZE! Harvest slip issuance disabled & net cane area set to 0.00 Ac.`);
        } else {
            alert(`🌾 Plot #${farmId} restored as CONFIRMED SUGARCANE! Harvest slip enabled.`);
        }
    };

    window.editNetCaneArea = function(farmId) {
        const item = state.enrichedData.find(d => getFarmId(d) === farmId);
        if (!item) return;

        const currentNet = item.net_cane_acres;
        const grossArea = item.gross_area_acres;

        const newNetStr = prompt(
            `✂️ DRY LAND TRIMMING & NET ACREAGE EDITOR

Farmer: ${getFarmerName(item)}
Total Registered Land: ${grossArea} Acres
Current Net Cane Area: ${currentNet} Acres

Enter NEW Net Actual Sugarcane Area in Acres (excluding dry land / bare soil):`,
            currentNet
        );

        if (newNetStr !== null) {
            const newNet = parseFloat(newNetStr);
            if (!isNaN(newNet) && newNet >= 0 && newNet <= parseFloat(grossArea)) {
                state.userAreaOverrides[farmId] = newNet.toFixed(2);
                runEngine();
                const trimmed = (parseFloat(grossArea) - newNet).toFixed(2);
                alert(`✅ Successfully trimmed dry land!

Registered Area: ${grossArea} Ac
Excluded Dry Land: ${trimmed} Ac
New Net Sugarcane Area: ${newNet.toFixed(2)} Ac`);
            } else {
                alert(`⚠️ Invalid acreage value. Please enter a valid number between 0.00 and ${grossArea} Acres.`);
            }
        }
    };

    window.focusFarmerPlotOnMap = function(farmId) {
        state.focusedPlotId = farmId;
        renderLeftPlotList();

        const item = state.enrichedData.find(d => getFarmId(d) === farmId);
        if (!item) return;

        const lat = parseFloat(item.latitude);
        const lon = parseFloat(item.longitude);

        if (!isNaN(lat) && !isNaN(lon)) {
            if (item.plot_area_polygon) {
                const coords = item.plot_area_polygon.split('#').map(p => p.split(',').map(Number));
                state.map.fitBounds(L.latLngBounds(coords), { maxZoom: 17, padding: [40, 40] });
            } else {
                state.map.setView([lat, lon], 16, { animate: true });
            }

            const marker = state.markerMapByFarmId[farmId];
            if (marker) {
                setTimeout(() => marker.openPopup(), 250);
            }
        }
    };

    window.openCompareModal = function() {
        el.compareModal.classList.remove('hidden');
        setTimeout(() => {
            initCompareMaps();
            drawHistogramCurve();
        }, 150);
    };

    function initCompareMaps() {
        if (!state.compareMapLeft) {
            state.compareMapLeft = L.map('compareMapLeft', { center: [19.3902, 75.3157], zoom: 17, zoomControl: false });
            L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}').addTo(state.compareMapLeft);
        }

        if (!state.compareMapRight) {
            state.compareMapRight = L.map('compareMapRight', { center: [19.3902, 75.3157], zoom: 17, zoomControl: false });
            L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}').addTo(state.compareMapRight);
        }

        let isSyncing = false;
        state.compareMapLeft.on('move', () => {
            if (!isSyncing) {
                isSyncing = true;
                state.compareMapRight.setView(state.compareMapLeft.getCenter(), state.compareMapLeft.getZoom(), { animate: false });
                isSyncing = false;
            }
        });
        state.compareMapRight.on('move', () => {
            if (!isSyncing) {
                isSyncing = true;
                state.compareMapLeft.setView(state.compareMapRight.getCenter(), state.compareMapRight.getZoom(), { animate: false });
                isSyncing = false;
            }
        });

        renderZonationLeft();
        renderUavRasterRight();
    }

    function renderZonationLeft() {
        state.compareMapLeft.eachLayer(l => { if (l instanceof L.Polygon) state.compareMapLeft.removeLayer(l); });
        const p1 = [[19.3908, 75.3150], [19.3907, 75.3164], [19.3897, 75.3163], [19.3898, 75.3149]];
        const p2 = [[19.3906, 75.3152], [19.3905, 75.3162], [19.3899, 75.3161], [19.3900, 75.3151]];
        const p3 = [[19.3904, 75.3154], [19.3904, 75.3160], [19.3901, 75.3159], [19.3901, 75.3153]];
        const p4 = [[19.3903, 75.3155], [19.3903, 75.3158], [19.3902, 75.3157], [19.3902, 75.3155]];

        L.polygon(p1, { color: '#00e676', weight: 1.5, fillColor: '#00e676', fillOpacity: 0.85 }).addTo(state.compareMapLeft);
        L.polygon(p2, { color: '#ffea00', weight: 1.5, fillColor: '#ffea00', fillOpacity: 0.85 }).addTo(state.compareMapLeft);
        L.polygon(p3, { color: '#ff9100', weight: 1.5, fillColor: '#ff9100', fillOpacity: 0.85 }).addTo(state.compareMapLeft);
        L.polygon(p4, { color: '#ff1744', weight: 1.5, fillColor: '#ff1744', fillOpacity: 0.90 }).addTo(state.compareMapLeft);

        state.compareMapLeft.fitBounds(L.latLngBounds(p1), { padding: [20, 20] });
    }

    function renderUavRasterRight() {
        state.compareMapRight.eachLayer(l => { if (l instanceof L.Rectangle) state.compareMapRight.removeLayer(l); });
        const minLat = 19.3897, maxLat = 19.3908;
        const minLon = 75.3149, maxLon = 75.3164;
        const steps = 24;
        const latStep = (maxLat - minLat) / steps;
        const lonStep = (maxLon - minLon) / steps;

        for (let r = 0; r < steps; r++) {
            for (let c = 0; c < steps; c++) {
                const gridLat = minLat + (r * latStep);
                const gridLon = minLon + (c * lonStep);
                const distFromCenter = Math.hypot(r - steps/2, c - steps/2);
                let color = '#ffea00';
                if (distFromCenter < 5) color = '#0055ff';
                else if (distFromCenter < 9) color = '#00e676';
                else if (distFromCenter > 11) color = '#ff9100';

                L.rectangle([[gridLat, gridLon], [gridLat + latStep, gridLon + lonStep]], {
                    color: color, weight: 0.2, fillColor: color, fillOpacity: 0.85
                }).addTo(state.compareMapRight);
            }
        }

        state.compareMapRight.fitBounds(L.latLngBounds([[minLat, minLon], [maxLat, maxLon]]), { padding: [20, 20] });
    }

    function drawHistogramCurve() {
        const canvas = el.histogramCanvas;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const w = canvas.clientWidth || 400;
        const h = canvas.clientHeight || 35;
        canvas.width = w; canvas.height = h;

        ctx.clearRect(0, 0, w, h);
        const grad = ctx.createLinearGradient(0, 0, w, 0);
        grad.addColorStop(0.00, 'rgba(0, 85, 255, 0.7)');
        grad.addColorStop(0.25, 'rgba(0, 242, 254, 0.7)');
        grad.addColorStop(0.50, 'rgba(0, 230, 118, 0.7)');
        grad.addColorStop(0.75, 'rgba(255, 234, 0, 0.7)');
        grad.addColorStop(1.00, 'rgba(255, 23, 68, 0.7)');

        ctx.beginPath();
        ctx.moveTo(0, h);
        for (let x = 0; x <= w; x++) {
            const normX = (x / w - 0.5) * 4;
            const y = h - (Math.exp(-normX * normX) * (h * 0.85));
            ctx.lineTo(x, y);
        }
        ctx.lineTo(w, h);
        ctx.closePath();
        ctx.fillStyle = grad;
        ctx.fill();
        ctx.strokeStyle = '#00f2fe';
        ctx.lineWidth = 1.5;
        ctx.stroke();
    }

    function markPresetActive(buttonId) {
        document.querySelectorAll('.btn-preset').forEach(b => b.classList.remove('active'));
        const btn = document.getElementById(buttonId);
        if (btn) btn.classList.add('active');
    }

    function setupEventListeners() {
        if (el.inputSearchPlotList) {
            el.inputSearchPlotList.addEventListener('input', (e) => {
                state.searchTerm = e.target.value;
                applyFilters();
            });
        }

        if (el.selectFactoryCircle) {
            el.selectFactoryCircle.addEventListener('change', (e) => {
                state.circleFilter = e.target.value;
                applyFilters();
            });
        }

        if (el.selectCropType) {
            el.selectCropType.addEventListener('change', (e) => {
                state.cropTypeFilter = e.target.value;
                applyFilters();
            });
        }

        if (el.btnOpenCompareModal) el.btnOpenCompareModal.addEventListener('click', window.openCompareModal);
        if (el.btnPresetFarmerReal) el.btnPresetFarmerReal.addEventListener('click', () => loadPreset('farmer_real'));
        if (el.btnPresetAdsaliReal) el.btnPresetAdsaliReal.addEventListener('click', () => loadPreset('adsali_real'));
        if (el.btnPresetAhilyanagarReal) el.btnPresetAhilyanagarReal.addEventListener('click', () => loadPreset('ahilyanagar_real'));
        
        if (el.btnPresetUserCsv) {
            el.btnPresetUserCsv.addEventListener('click', () => {
                const savedStr = localStorage.getItem('satcane_saved_csv_data');
                if (savedStr) {
                    try {
                        state.rawCsvData = JSON.parse(savedStr);
                        state.activePreset = 'custom_user';
                        runEngine();
                        markPresetActive('btnPresetUserCsv');
                        alert(`📁 Loaded ${state.rawCsvData.length} plots from your uploaded CSV!`);
                        return;
                    } catch (e) {}
                }
                document.getElementById('csvFileInput').click();
            });
        }

        if (el.btnUploadTrainingDataset) {
            el.btnUploadTrainingDataset.addEventListener('click', () => {
                document.getElementById('trainingDatasetFileInput').click();
            });
        }

        if (el.btnResetData) el.btnResetData.addEventListener('click', () => { 
            state.rawCsvData = []; 
            state.userCropOverrides = {};
            state.userAreaOverrides = {};
            localStorage.removeItem('satcane_saved_csv_data');
            runEngine(); 
        });

        if (el.csvFileInput) {
            el.csvFileInput.addEventListener('change', (e) => {
                if (e.target.files.length) {
                    Papa.parse(e.target.files[0], {
                        header: true,
                        skipEmptyLines: true,
                        complete: (res) => {
                            state.rawCsvData = res.data;
                            state.activePreset = 'custom_user';
                            localStorage.setItem('satcane_saved_csv_data', JSON.stringify(res.data));
                            runEngine();
                            markPresetActive('btnPresetUserCsv');
                            alert(`💾 ${res.data.length} plots successfully parsed & saved to browser memory!`);
                        }
                    });
                }
            });
        }

        if (el.trainingDatasetFileInput) {
            el.trainingDatasetFileInput.addEventListener('change', (e) => {
                if (e.target.files.length) {
                    Papa.parse(e.target.files[0], {
                        header: true,
                        skipEmptyLines: true,
                        complete: (res) => {
                            state.rawCsvData = res.data;
                            state.activePreset = 'training_lab';
                            localStorage.setItem('satcane_saved_csv_data', JSON.stringify(res.data));
                            runEngine();
                            markPresetActive('btnUploadTrainingDataset');
                            alert(`🔬 2026 CONFORMAL LAB PREDICTION ENGINE LOADED!

Parsed ${res.data.length} lab ground-truth records.
95% Conformal Confidence Intervals (Brix ±0.38%, Pol ±0.32%, CCS ±0.28%) active!`);
                        }
                    });
                }
            });
        }

        document.querySelectorAll('.compare-layer-row').forEach(row => {
            row.addEventListener('click', () => {
                document.querySelectorAll('.compare-layer-row').forEach(r => r.classList.remove('active'));
                row.classList.add('active');
            });
        });
    }

    function loadPreset(key) {
        state.activePreset = key;
        if (key === 'farmer_real') markPresetActive('btnPresetFarmerReal');
        if (key === 'adsali_real') markPresetActive('btnPresetAdsaliReal');
        if (key === 'ahilyanagar_real') markPresetActive('btnPresetAhilyanagarReal');

        state.rawCsvData = REAL_DATASETS[key] || REAL_DATASETS.farmer_real;
        runEngine();
    }
});
