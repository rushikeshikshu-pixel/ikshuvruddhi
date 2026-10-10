/**
 * IKSHU INTELLIGENCE - FLAGSHIP AEROSPACE & AGRI-TECH PLATFORM ENGINE
 * Domain: ikshuintelligence.com | SatCane AI & IkshuVruddhi Engine
 * UTF-8 Clean Encodings for Marathi, Indian Currency (₹), and Polarimetry (°Bx)
 */

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initMultiSpectralHud();
    initRipeningSimulator();
    initRoiCalculator();
    initCadastralAuditShowcase();
    initLanguageToggle();
    initMillAuthModal();
    initContactForm();
});

/* ==========================================================================
   1. NAVIGATION & SCROLL
   ========================================================================== */
function initNavigation() {
    const nav = document.querySelector('.spacex-navbar');
    const mobileBtn = document.querySelector('.mobile-menu-btn');
    const navLinks = document.querySelector('.nav-links-list');

    window.addEventListener('scroll', () => {
        if (window.scrollY > 40) {
            nav.classList.add('scrolled');
        } else {
            nav.classList.remove('scrolled');
        }
    });

    if (mobileBtn && navLinks) {
        mobileBtn.addEventListener('click', () => {
            const isVisible = navLinks.style.display === 'flex';
            navLinks.style.display = isVisible ? 'none' : 'flex';
            if (!isVisible) {
                navLinks.style.flexDirection = 'column';
                navLinks.style.position = 'absolute';
                navLinks.style.top = '68px';
                navLinks.style.left = '0';
                navLinks.style.width = '100%';
                navLinks.style.background = '#040914';
                navLinks.style.padding = '24px';
                navLinks.style.borderBottom = '1px solid rgba(0, 242, 254, 0.25)';
            }
        });
    }
}

/* ==========================================================================
   2. HERO MISSION CONTROL MULTI-SPECTRAL HUD TABS
   ========================================================================== */
const SPECTRAL_MODES = {
    'rgb': {
        name: 'True Color (RGB 10m)',
        bg: 'radial-gradient(circle at center, rgba(16, 185, 129, 0.12) 0%, transparent 75%), #040914',
        band1: 'Band 2 (Blue): 0.490 µm',
        band2: 'Band 3 (Green): 0.560 µm',
        band3: 'Band 4 (Red): 0.665 µm',
        band4: 'Resolution: 10m GSD',
        node1Color: '#00e676',
        node2Color: '#10b981',
        node3Color: '#38bdf8',
        badge: 'SENTINEL-2 MSI: NATURAL CANOPY REFLECTANCE'
    },
    'ndvi': {
        name: 'Vegetation Index (NDVI)',
        bg: 'radial-gradient(circle at center, rgba(0, 230, 118, 0.18) 0%, transparent 75%), #040e0c',
        band1: 'NDVI Index: 0.82',
        band2: 'NIR (B8): 0.842 µm',
        band3: 'Red (B4): 0.665 µm',
        band4: 'Canopy Cover: 94.6%',
        node1Color: '#00e676',
        node2Color: '#00e676',
        node3Color: '#a7f3d0',
        badge: 'VEGETATIVE VIGOR: DENSE HIGH-YIELD CANOPY'
    },
    'ndwi': {
        name: 'Moisture Index (NDWI)',
        bg: 'radial-gradient(circle at center, rgba(0, 242, 254, 0.18) 0%, transparent 75%), #030d1c',
        band1: 'NDWI Moisture: +0.48',
        band2: 'Green (B3): 0.560 µm',
        band3: 'NIR (B8): 0.842 µm',
        band4: 'Turgor Status: HYDRATED',
        node1Color: '#00f2fe',
        node2Color: '#38bdf8',
        node3Color: '#60a5fa',
        badge: 'TURGOR TELEMETRY: OPTIMAL IRRIGATION STATUS'
    },
    'ccs': {
        name: 'Sucrose Chemistry (CCS)',
        bg: 'radial-gradient(circle at center, rgba(245, 158, 11, 0.18) 0%, transparent 75%), #140d04',
        band1: 'CCS Sugar: 12.85%',
        band2: 'Brix: 21.8°Bx',
        band3: 'Pol: 18.2%',
        band4: 'Window: PEAK (5 DAYS)',
        node1Color: '#f59e0b',
        node2Color: '#00e676',
        node3Color: '#fbbf24',
        badge: 'PRE-HARVEST SUCROSE INVERSION FORECAST: PEAK STAGE'
    }
};

function initMultiSpectralHud() {
    const tabs = document.querySelectorAll('.hud-tab-btn');
    const radarBox = document.getElementById('heroRadarBox');
    const badgeEl = document.getElementById('heroRadarBadge');
    const b1 = document.getElementById('hudBand1');
    const b2 = document.getElementById('hudBand2');
    const b3 = document.getElementById('hudBand3');
    const b4 = document.getElementById('hudBand4');

    if (!tabs.length || !radarBox) return;

    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            tabs.forEach(t => t.classList.remove('active'));
            e.currentTarget.classList.add('active');

            const modeKey = e.currentTarget.dataset.mode;
            const data = SPECTRAL_MODES[modeKey] || SPECTRAL_MODES['rgb'];

            radarBox.style.background = data.bg;
            if (badgeEl) badgeEl.textContent = data.badge;
            if (b1) b1.textContent = data.band1;
            if (b2) b2.textContent = data.band2;
            if (b3) b3.textContent = data.band3;
            if (b4) b4.textContent = data.band4;
        });
    });
}

/* ==========================================================================
   3. INTERACTIVE SUCROSE RIPENING & LOSS SIMULATOR
   ========================================================================== */
const VARIETY_DATA = {
    'Co 86032': { name: 'Co 86032 (Nira)', peakAge: 400, baseCcs: 12.8, baseBrix: 21.6, decayRate: 0.048, optimalWindow: [375, 425] },
    'Co 0265': { name: 'Co 0265 (Phule)', peakAge: 375, baseCcs: 12.1, baseBrix: 20.8, decayRate: 0.065, optimalWindow: [350, 400] },
    'Co 0118': { name: 'Co 0118 (High Sugar Early)', peakAge: 330, baseCcs: 13.4, baseBrix: 22.4, decayRate: 0.075, optimalWindow: [310, 355] },
    'MS 10001': { name: 'MS 10001 (Early Heavy)', peakAge: 345, baseCcs: 13.1, baseBrix: 22.0, decayRate: 0.070, optimalWindow: [320, 365] }
};

let currentVariety = 'Co 86032';

function initRipeningSimulator() {
    const varietyBtns = document.querySelectorAll('.variety-btn');
    const ageSlider = document.getElementById('simCropAgeSlider');
    const ageVal = document.getElementById('simCropAgeVal');
    const standingSlider = document.getElementById('simStandingDaysSlider');
    const standingVal = document.getElementById('simStandingDaysVal');

    if (!ageSlider || !standingSlider) return;

    varietyBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            varietyBtns.forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');
            currentVariety = e.currentTarget.dataset.variety;
            updateRipeningSimulation();
        });
    });

    ageSlider.addEventListener('input', (e) => {
        const days = parseInt(e.target.value);
        const months = (days / 30.4).toFixed(1);
        ageVal.textContent = days + ' Days (' + months + ' Mo)';
        updateRipeningSimulation();
    });

    standingSlider.addEventListener('input', (e) => {
        const days = parseInt(e.target.value);
        standingVal.textContent = days + ' Days Standing Delay';
        updateRipeningSimulation();
    });

    updateRipeningSimulation();
    window.addEventListener('resize', updateRipeningSimulation);
}

function updateRipeningSimulation() {
    const profile = VARIETY_DATA[currentVariety] || VARIETY_DATA['Co 86032'];
    const ageSlider = document.getElementById('simCropAgeSlider');
    const standingSlider = document.getElementById('simStandingDaysSlider');

    if (!ageSlider || !standingSlider) return;

    const ageDays = parseInt(ageSlider.value);
    const standingDays = parseInt(standingSlider.value);

    const deltaPeak = ageDays - profile.peakAge;
    let maturationFactor = 1.0;

    if (deltaPeak < 0) {
        maturationFactor = Math.max(0.65, 1.0 - Math.pow(deltaPeak / 160, 2) * 0.45);
    } else {
        const naturalDecay = Math.pow(deltaPeak / 180, 1.6) * 0.35;
        const postPeakStandingDecay = (standingDays * profile.decayRate * 0.08);
        maturationFactor = Math.max(0.60, 1.0 - naturalDecay - postPeakStandingDecay);
    }

    const currentCcs = (profile.baseCcs * maturationFactor).toFixed(2);
    const currentBrix = (profile.baseBrix * (0.8 + 0.2 * maturationFactor)).toFixed(1);
    const currentPol = (currentCcs * 1.34 - (currentBrix * 0.22)).toFixed(2);

    const dailyLossKgPerMt = (standingDays > 0) ? (standingDays * 0.42 + (standingDays * standingDays * 0.012)).toFixed(1) : 0;
    const financialLossLakhs = ((dailyLossKgPerMt * 5000 / 100) * 3600 / 100000).toFixed(2);

    const ccsEl = document.getElementById('simMetricCcs');
    const brixEl = document.getElementById('simMetricBrix');
    const polEl = document.getElementById('simMetricPol');
    const lossMoneyEl = document.getElementById('simLossMoney');
    const alertBox = document.getElementById('simWindowAlert');

    if (ccsEl) ccsEl.textContent = currentCcs + '%';
    if (brixEl) brixEl.textContent = currentBrix + '°Bx';
    if (polEl) polEl.textContent = currentPol + '%';
    if (lossMoneyEl) lossMoneyEl.textContent = '₹' + financialLossLakhs + ' Lakhs';

    if (alertBox) {
        alertBox.className = 'sim-window-alert';
        if (standingDays > 14 || ageDays > (profile.optimalWindow[1] + 15)) {
            alertBox.classList.add('sim-window-danger');
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> <div><strong>CRITICAL POST-MATURITY INVERSION LOSS:</strong> Standing past biological peak. Cane is shedding ' + dailyLossKgPerMt + ' kg sugar per tonne crushed. Issue high-priority harvest cutting docket immediately.</div>';
        } else if (ageDays >= profile.optimalWindow[0] && ageDays <= profile.optimalWindow[1] && standingDays <= 7) {
            alertBox.classList.add('sim-window-optimal');
            alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> <div><strong>OPTIMAL HARVEST RECOVERY WINDOW:</strong> Peak commercial sucrose state (CCS ' + currentCcs + '% | Brix ' + currentBrix + '°Bx). Schedule into current 7-day crushing batch.</div>';
        } else if (ageDays < profile.optimalWindow[0]) {
            alertBox.classList.add('sim-window-warning');
            alertBox.innerHTML = '<i class="fa-solid fa-clock"></i> <div><strong>IMMATURE VEGETATIVE STATE:</strong> Sugar synthesis active in stalk. Cutting now leaves ~' + (profile.baseCcs - currentCcs).toFixed(1) + '% sugar unformed in field. Delay cutting slip by ~' + (profile.optimalWindow[0] - ageDays) + ' days.</div>';
        } else {
            alertBox.classList.add('sim-window-warning');
            alertBox.innerHTML = '<i class="fa-solid fa-hourglass-half"></i> <div><strong>MATURITY PLATEAU:</strong> Cane at late plateau. Standing loss is accumulating at ₹' + financialLossLakhs + ' L / day for a 5,000 TCD mill. Queue into next transport roster.</div>';
        }
    }

    renderRipeningSvgChart(profile, ageDays, currentCcs);
}

function renderRipeningSvgChart(profile, currentAge, currentCcs) {
    const container = document.getElementById('simGraphCanvasWrap');
    if (!container) return;

    const width = container.clientWidth || 550;
    const height = 180;
    const padding = { top: 24, right: 30, bottom: 30, left: 45 };

    const minDay = 240;
    const maxDay = 520;
    const minCcs = 8.0;
    const maxCcs = 14.5;

    function getX(day) {
        return padding.left + ((day - minDay) / (maxDay - minDay)) * (width - padding.left - padding.right);
    }

    function getY(ccs) {
        return height - padding.bottom - ((ccs - minCcs) / (maxCcs - minCcs)) * (height - padding.top - padding.bottom);
    }

    let points = [];
    for (let d = minDay; d <= maxDay; d += 10) {
        let delta = d - profile.peakAge;
        let ccs;
        if (delta < 0) {
            ccs = profile.baseCcs * (1.0 - Math.pow(delta / 160, 2) * 0.45);
        } else {
            ccs = profile.baseCcs * (1.0 - Math.pow(delta / 180, 1.6) * 0.35);
        }
        points.push(getX(d).toFixed(1) + ',' + getY(ccs).toFixed(1));
    }

    const pathD = 'M ' + points.join(' L ');
    const optX1 = getX(profile.optimalWindow[0]).toFixed(1);
    const optX2 = getX(profile.optimalWindow[1]).toFixed(1);
    const currentX = getX(currentAge).toFixed(1);
    const currentY = getY(parseFloat(currentCcs)).toFixed(1);

    const svg = '<svg viewBox="0 0 ' + width + ' ' + height + '" width="100%" height="100%">' +
        '<rect x="' + optX1 + '" y="' + padding.top + '" width="' + (optX2 - optX1) + '" height="' + (height - padding.top - padding.bottom) + '" fill="rgba(0, 230, 118, 0.12)" rx="4" />' +
        '<text x="' + ((parseFloat(optX1) + parseFloat(optX2)) / 2) + '" y="' + (padding.top + 14) + '" fill="#00e676" font-size="9" font-family="monospace" font-weight="bold" text-anchor="middle">OPTIMAL 10-DAY HARVEST WINDOW</text>' +
        '<line x1="' + padding.left + '" y1="' + getY(10) + '" x2="' + (width - padding.right) + '" y2="' + getY(10) + '" stroke="rgba(255,255,255,0.06)" stroke-dasharray="3,3" />' +
        '<line x1="' + padding.left + '" y1="' + getY(12) + '" x2="' + (width - padding.right) + '" y2="' + getY(12) + '" stroke="rgba(255,255,255,0.06)" stroke-dasharray="3,3" />' +
        '<line x1="' + padding.left + '" y1="' + getY(14) + '" x2="' + (width - padding.right) + '" y2="' + getY(14) + '" stroke="rgba(255,255,255,0.06)" stroke-dasharray="3,3" />' +
        '<text x="' + (padding.left - 8) + '" y="' + (getY(10) + 3) + '" fill="#64748b" font-size="9" text-anchor="end">10%</text>' +
        '<text x="' + (padding.left - 8) + '" y="' + (getY(12) + 3) + '" fill="#64748b" font-size="9" text-anchor="end">12%</text>' +
        '<text x="' + (padding.left - 8) + '" y="' + (getY(14) + 3) + '" fill="#64748b" font-size="9" text-anchor="end">14%</text>' +
        '<path d="' + pathD + '" fill="none" stroke="#00f2fe" stroke-width="3" stroke-linecap="round" />' +
        '<line x1="' + currentX + '" y1="' + padding.top + '" x2="' + currentX + '" y2="' + (height - padding.bottom) + '" stroke="#f59e0b" stroke-width="2" stroke-dasharray="4,3" />' +
        '<circle cx="' + currentX + '" cy="' + currentY + '" r="6" fill="#f59e0b" stroke="#ffffff" stroke-width="2" />' +
        '<text x="' + currentX + '" y="' + (height - padding.bottom + 18) + '" fill="#f59e0b" font-size="10" font-family="monospace" font-weight="bold" text-anchor="middle">Day ' + currentAge + ' (' + currentCcs + '%)</text>' +
        '</svg>';

    container.innerHTML = svg;
}

/* ==========================================================================
   4. MILL RECOVERY ROI CALCULATOR
   ========================================================================== */
function initRoiCalculator() {
    const tcdSlider = document.getElementById('roiTcdSlider');
    const tcdVal = document.getElementById('roiTcdVal');
    const daysSlider = document.getElementById('roiDaysSlider');
    const daysVal = document.getElementById('roiDaysVal');
    const recoverySlider = document.getElementById('roiRecoverySlider');
    const recoveryVal = document.getElementById('roiRecoveryVal');
    const priceSlider = document.getElementById('roiPriceSlider');
    const priceVal = document.getElementById('roiPriceVal');

    if (!tcdSlider || !recoverySlider) return;

    function recalculateRoi() {
        const tcd = parseInt(tcdSlider.value);
        const days = parseInt(daysSlider.value);
        const boost = parseFloat(recoverySlider.value);
        const pricePerQtl = parseInt(priceSlider.value);

        if (tcdVal) tcdVal.textContent = tcd.toLocaleString() + ' TCD';
        if (daysVal) daysVal.textContent = days + ' Days Season';
        if (recoveryVal) recoveryVal.textContent = '+' + boost.toFixed(2) + '% Recovery';
        if (priceVal) priceVal.textContent = '₹' + pricePerQtl + ' / Quintal';

        const totalCaneCrushed = tcd * days; // MT
        const additionalSugarMt = (totalCaneCrushed * (boost / 100));
        const additionalSugarQuintals = additionalSugarMt * 10;
        const additionalSugarBags = Math.round(additionalSugarQuintals * 2); // 50kg bags

        const extraRevenueInr = additionalSugarQuintals * pricePerQtl;
        const additionalSugarRevenueCrores = (extraRevenueInr / 10000000).toFixed(2);

        // Logistics & fleet scheduling fuel savings (est ₹25/MT cane crushed)
        const freightSavingsInr = totalCaneCrushed * 26;
        const freightSavingsCrores = (freightSavingsInr / 10000000).toFixed(2);

        const totalFinancialImpact = (parseFloat(additionalSugarRevenueCrores) + parseFloat(freightSavingsCrores)).toFixed(2);

        const totalCaneEl = document.getElementById('roiTotalCane');
        const recoveryBoostEl = document.getElementById('roiRecoveryBoost');
        const sugarBagsEl = document.getElementById('roiSugarBags');
        const sugarRevEl = document.getElementById('roiSugarRev');
        const freightSaveEl = document.getElementById('roiFreightSave');
        const totalImpactEl = document.getElementById('roiTotalImpact');

        if (totalCaneEl) totalCaneEl.textContent = (totalCaneCrushed / 100000).toFixed(2) + ' Lakh MT';
        if (recoveryBoostEl) recoveryBoostEl.textContent = '+' + boost.toFixed(2) + '%';
        if (sugarBagsEl) sugarBagsEl.textContent = '+' + additionalSugarBags.toLocaleString() + ' Bags';
        if (sugarRevEl) sugarRevEl.textContent = '₹' + additionalSugarRevenueCrores + ' Cr';
        if (freightSaveEl) freightSaveEl.textContent = '₹' + freightSavingsCrores + ' Cr';
        if (totalImpactEl) totalImpactEl.textContent = '₹' + totalFinancialImpact + ' Cr';
    }

    tcdSlider.addEventListener('input', recalculateRoi);
    daysSlider.addEventListener('input', recalculateRoi);
    recoverySlider.addEventListener('input', recalculateRoi);
    priceSlider.addEventListener('input', recalculateRoi);

    recalculateRoi();
}

/* ==========================================================================
   5. CADASTRAL GAT & GHOST PLOT AUDIT SHOWCASE
   ========================================================================== */
function initCadastralAuditShowcase() {
    const btnLegit = document.getElementById('auditTabLegit');
    const btnGhost = document.getElementById('auditTabGhost');

    const plotBadge = document.getElementById('auditPlotBadge');
    const plotTitle = document.getElementById('auditPlotTitle');
    const mapMock = document.getElementById('auditMapMock');
    const valNdvi = document.getElementById('auditValNdvi');
    const valArea = document.getElementById('auditValArea');
    const valCcs = document.getElementById('auditValCcs');
    const valStatus = document.getElementById('auditValStatus');
    const valDocket = document.getElementById('auditValDocket');

    if (!btnLegit || !btnGhost) return;

    btnLegit.addEventListener('click', () => {
        btnLegit.className = 'audit-tab-btn active legit';
        btnGhost.className = 'audit-tab-btn';

        if (plotBadge) plotBadge.innerHTML = '<span class="badge badge-green"><i class="fa-solid fa-circle-check"></i> VERIFIED PARCEL</span>';
        if (plotTitle) plotTitle.textContent = 'Gat 142 - Babhaleshwar (Farmer: Balasaheb Vikhe)';
        if (mapMock) {
            mapMock.style.background = 'radial-gradient(circle, rgba(0, 230, 118, 0.25) 0%, rgba(9, 19, 38, 0.95) 75%)';
            mapMock.innerHTML = '<div style="text-align:center;"><div style="color:#00e676; font-size:2rem; margin-bottom:6px;"><i class="fa-solid fa-satellite-dish"></i></div><div style="font-size:0.88rem; font-family:monospace; color:#ffffff;">Sentinel-2 Canopy Density: <strong>94.2%</strong></div><div style="font-size:0.75rem; color:#94a3b8; margin-top:4px;">Walked GPS Perimeter matches 7/12 MahaBhuNaksha Record (1.82 Ha)</div></div>';
        }
        if (valNdvi) valNdvi.innerHTML = '<span style="color:#00e676; font-weight:700;">0.78 (High Vigor Canopy)</span>';
        if (valArea) valArea.innerHTML = 'Registered: 1.80 Ha | Walked: 1.82 Ha <span style="color:#00e676;">(+1.1% Match)</span>';
        if (valCcs) valCcs.innerHTML = '<span style="color:#00f2fe; font-weight:700;">12.4% CCS (Peak Ripening)</span>';
        if (valStatus) valStatus.innerHTML = '<span style="color:#00e676; font-weight:800;">CONFIRMED AUTHENTIC CANE</span>';
        if (valDocket) valDocket.innerHTML = '<span class="badge badge-green">APPROVED FOR CRUSH DISPATCH</span>';
    });

    btnGhost.addEventListener('click', () => {
        btnGhost.className = 'audit-tab-btn active ghost';
        btnLegit.className = 'audit-tab-btn';

        if (plotBadge) plotBadge.innerHTML = '<span class="badge badge-danger"><i class="fa-solid fa-triangle-exclamation"></i> GHOST GAT FRAUD</span>';
        if (plotTitle) plotTitle.textContent = 'Gat 89 - Ghotan Sector 4 (Farmer: Registered Placeholder)';
        if (mapMock) {
            mapMock.style.background = 'radial-gradient(circle, rgba(239, 68, 68, 0.28) 0%, rgba(15, 10, 15, 0.95) 75%)';
            mapMock.innerHTML = '<div style="text-align:center;"><div style="color:#ef4444; font-size:2rem; margin-bottom:6px;"><i class="fa-solid fa-triangle-exclamation"></i></div><div style="font-size:0.88rem; font-family:monospace; color:#ffffff;">Sentinel-2 Canopy Density: <strong style="color:#ef4444;">0.0% (Zero Standing Cane)</strong></div><div style="font-size:0.75rem; color:#fca5a5; margin-top:4px;">Barren / Fallow Soil Syndicate Scam - Automated Slip Blocked</div></div>';
        }
        if (valNdvi) valNdvi.innerHTML = '<span style="color:#ef4444; font-weight:700;">0.14 (Fallow Land / Barren)</span>';
        if (valArea) valArea.innerHTML = 'Registered: 3.50 Ha | Real Cane: 0.00 Ha <span style="color:#ef4444;">(-100% Divergence)</span>';
        if (valCcs) valCcs.innerHTML = '<span style="color:#94a3b8;">N/A (No Crop Standing)</span>';
        if (valStatus) valStatus.innerHTML = '<span style="color:#ef4444; font-weight:800;">GHOST PLOT / SUBSIDY THEFT</span>';
        if (valDocket) valDocket.innerHTML = '<span class="badge badge-danger">HARVEST SLIP BLOCKED & REJECTED</span>';
    });
}

/* ==========================================================================
   6. BILINGUAL LANGUAGE TOGGLE (EN / MARATHI) - CLEAN UTF-8
   ========================================================================== */
const I18N = {
    en: {
        heroTitle: 'Autonomous Sugarcane Intelligence from Orbit to Mill Crushing',
        heroSubtitle: 'Empowering Sugar Mills & Agricultural Cooperatives with AI-driven pre-harvest sucrose forecasting, cadastral Gat reconciliation, and capacity-balanced harvest scheduling. Maximize sugar recovery (CCS), eliminate ghost-plot fraud, and cut harvest-to-crush delays.',
        btnLaunchConsole: 'Launch Mill Console (320 Plots)',
        btnCalcRoi: 'Calculate Mill Recovery ROI',
        statCcs: 'Recovery Gain',
        statImpact: 'Annual Addition',
        statFraud: 'Ghost Gat Theft'
    },
    mr: {
        heroTitle: 'उपग्रह रिमोट सेन्सिंग व AI द्वारे साखर कारखान्यांसाठी स्वयंचलित शेती बुद्धिमत्ता',
        heroSubtitle: 'साखर कारखान्यांसाठी उपग्रहाद्वारे परिपक्वता अंदाज (CCS), महाभूनकाशा ७/१२ गट पडताळणी, आणि तोडणी वाहतूक नियंत्रण प्रणाली. साखर उतारा वाढवा, बोगस नोंदी रोखा आणि कारखान्याचा नफा वाढवा.',
        btnLaunchConsole: 'मिल ऑपरेशन्स कन्सोल सुरू करा (३२० प्लॉट्स)',
        btnCalcRoi: 'साखर उतारा ROI गणक',
        statCcs: 'साखर उतारा वाढ',
        statImpact: 'वार्षिक नफा वाढ',
        statFraud: 'बोगस गटामुळे होणारे नुकसान'
    }
};

let currentLang = 'en';

function initLanguageToggle() {
    const langBtn = document.getElementById('langToggleBtn');
    if (!langBtn) return;

    langBtn.addEventListener('click', () => {
        currentLang = (currentLang === 'en') ? 'mr' : 'en';
        langBtn.innerHTML = (currentLang === 'en') ? '<i class="fa-solid fa-globe"></i> EN | मराठी' : '<i class="fa-solid fa-globe"></i> मराठी | EN';

        const data = I18N[currentLang];
        const titleEl = document.getElementById('heroMainTitle');
        const subEl = document.getElementById('heroMainSubtitle');
        const launchBtn = document.getElementById('heroLaunchBtn');
        const roiBtn = document.getElementById('heroRoiBtn');

        if (titleEl) {
            titleEl.innerHTML = (currentLang === 'en') 
                ? 'Autonomous Sugarcane Intelligence <span class="gradient-cyan">From Orbit To</span> <span class="gradient-emerald">Mill Crushing</span>'
                : 'उपग्रह रिमोट सेन्सिंग व AI <span class="gradient-cyan">द्वारे साखर कारखान्यांसाठी</span> <span class="gradient-emerald">स्वयंचलित शेती बुद्धिमत्ता</span>';
        }
        if (subEl) subEl.textContent = data.heroSubtitle;
        if (launchBtn) launchBtn.innerHTML = '<i class="fa-solid fa-gauge-high"></i> ' + data.btnLaunchConsole;
        if (roiBtn) roiBtn.innerHTML = '<i class="fa-solid fa-calculator"></i> ' + data.btnCalcRoi;
    });
}

/* ==========================================================================
   7. SUGAR MILL ENTERPRISE ACCOUNT & VIP GATEWAY MODAL
   ========================================================================== */
let selectedMillRole = 'Managing Director (MD)';

function initMillAuthModal() {
    const openBtn = document.getElementById('btnOpenMillAuthModal');
    const modal = document.getElementById('millAuthModalOverlay');
    const closeBtn = document.getElementById('btnCloseMillAuthModal');

    if (openBtn && modal) {
        openBtn.addEventListener('click', (e) => {
            e.preventDefault();
            modal.classList.add('active');
        });
    }

    if (closeBtn && modal) {
        closeBtn.addEventListener('click', () => {
            modal.classList.remove('active');
        });
    }

    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    }

    renderActiveMillNavbar();
}

function renderActiveMillNavbar() {
    const container = document.getElementById('navMillAuthContainer');
    if (!container) return;

    const rawProfile = sessionStorage.getItem('ikshu_mill_profile');
    if (rawProfile) {
        try {
            const profile = JSON.parse(rawProfile);
            container.innerHTML = `
                <div style="display:inline-flex; align-items:center; gap:8px;">
                    <a href="console.html" class="btn-telemetry-portal" title="Active Mill: ${profile.millName}">
                        <i class="fa-solid fa-circle" style="font-size:0.55rem; color:#00e676;"></i>
                        <span>${profile.shortName || 'Samarth SSK'} (${profile.shortRole || 'MD'})</span>
                    </a>
                    <button onclick="signOutMill()" style="background:transparent; border:none; color:#94a3b8; cursor:pointer;" title="Sign out">
                        <i class="fa-solid fa-arrow-right-from-bracket"></i>
                    </button>
                </div>
            `;
        } catch (e) {
            console.error('Error parsing mill profile', e);
        }
    }
}

window.selectMillRole = function(el, roleName) {
    document.querySelectorAll('.role-choice-card').forEach(c => c.classList.remove('selected'));
    el.classList.add('selected');
    selectedMillRole = roleName;
};

window.handleMillSignIn = function(e) {
    e.preventDefault();
    const sel = document.getElementById('selFactoryCode');
    const factoryCode = sel ? sel.value : 'SAMARTH_SSK';
    const factoryText = sel ? sel.options[sel.selectedIndex].text : 'Samarth SSK Ltd.';

    let shortRole = 'MD';
    if (selectedMillRole.includes('Chemist')) shortRole = 'Chemist';
    if (selectedMillRole.includes('Cane')) shortRole = 'Cane Dept';

    const profile = {
        millCode: factoryCode,
        millName: factoryText,
        shortName: factoryText.split(' ')[0] + ' SSK',
        role: selectedMillRole,
        shortRole: shortRole,
        timestamp: new Date().toISOString()
    };

    sessionStorage.setItem('ikshu_mill_profile', JSON.stringify(profile));
    window.location.href = 'console.html';
};

window.signOutMill = function() {
    sessionStorage.removeItem('ikshu_mill_profile');
    window.location.reload();
};

/* ==========================================================================
   8. PILOT DEMO CONTACT FORM
   ========================================================================== */
function initContactForm() {
    const form = document.getElementById('pilotContactForm');
    const statusMsg = document.getElementById('formStatusMsg');

    if (!form) return;

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const millName = document.getElementById('inputMillName').value;
        const contactPerson = document.getElementById('inputContactPerson').value;
        const phone = document.getElementById('inputPhone').value;

        if (statusMsg) {
            statusMsg.style.display = 'block';
            statusMsg.innerHTML = '<div style="background:rgba(0,230,118,0.15); border:1px solid #00e676; color:#a7f3d0; padding:12px; border-radius:6px; font-size:0.85rem;"><i class="fa-solid fa-circle-check"></i> Pilot Request Logged for <strong>' + millName + '</strong>. Our cane engineering team will reach out to ' + contactPerson + ' (' + phone + ') within 2 business hours.</div>';
        }

        form.reset();
    });
}
