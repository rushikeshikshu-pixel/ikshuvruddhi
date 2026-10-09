/**
 * IKSHU INTELLIGENCE - Flagship Platform Scripts
 * Domain: ikshuintelligence.com | SatCane AI & IkshuVruddhi Engine
 */

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initRipeningSimulator();
    initRoiCalculator();
    initCadastralAuditShowcase();
    initLanguageToggle();
    initDnsModal();
    initContactForm();
    initMillAuthModal();
});

/* ==========================================================================
   1. NAVIGATION & SCROLL
   ========================================================================== */
function initNavigation() {
    const nav = document.querySelector('.site-nav');
    const mobileBtn = document.querySelector('.mobile-menu-toggle');
    const navLinks = document.querySelector('.nav-links');

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
                navLinks.style.top = '76px';
                navLinks.style.left = '0';
                navLinks.style.width = '100%';
                navLinks.style.background = '#050913';
                navLinks.style.padding = '24px';
                navLinks.style.borderBottom = '1px solid rgba(0, 242, 254, 0.2)';
            }
        });
    }
}

/* ==========================================================================
   2. INTERACTIVE SUCROSE RIPENING & LOSS SIMULATOR
   ========================================================================== */
const VARIETY_DATA = {
    'Co 86032': { name: 'Co 86032 (Nira)', peakAge: 400, baseCcs: 12.8, baseBrix: 21.6, decayRate: 0.048, optimalWindow: [375, 425] },
    'Co 0265': { name: 'Co 0265 (Phule)', peakAge: 375, baseCcs: 12.1, baseBrix: 20.8, decayRate: 0.065, optimalWindow: [350, 400] },
    'MS 10001': { name: 'MS 10001 (Early)', peakAge: 345, baseCcs: 13.2, baseBrix: 22.2, decayRate: 0.072, optimalWindow: [320, 365] },
    'Co 92005': { name: 'Co 92005', peakAge: 385, baseCcs: 12.4, baseBrix: 21.2, decayRate: 0.052, optimalWindow: [360, 410] },
    'CoM 0265': { name: 'CoM 0265 (Heavy)', peakAge: 390, baseCcs: 11.9, baseBrix: 20.4, decayRate: 0.058, optimalWindow: [365, 415] },
    'Phule 10001': { name: 'Phule 10001', peakAge: 360, baseCcs: 12.9, baseBrix: 21.9, decayRate: 0.060, optimalWindow: [335, 380] }
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
        standingVal.textContent = days + ' Days Standing';
        updateRipeningSimulation();
    });

    updateRipeningSimulation();
}

function updateRipeningSimulation() {
    const profile = VARIETY_DATA[currentVariety] || VARIETY_DATA['Co 86032'];
    const ageDays = parseInt(document.getElementById('simCropAgeSlider').value);
    const standingDays = parseInt(document.getElementById('simStandingDaysSlider').value);

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
    const lossKgEl = document.getElementById('simLossKg');
    const lossMoneyEl = document.getElementById('simLossMoney');
    const alertBox = document.getElementById('simWindowAlert');

    if (ccsEl) ccsEl.textContent = currentCcs + '%';
    if (brixEl) brixEl.textContent = currentBrix + '°';
    if (polEl) polEl.textContent = currentPol + '%';
    if (lossKgEl) lossKgEl.textContent = dailyLossKgPerMt + ' kg/MT';
    if (lossMoneyEl) lossMoneyEl.textContent = '₹' + financialLossLakhs + ' L';

    if (alertBox) {
        alertBox.className = 'sim-window-alert';
        if (standingDays > 14 || ageDays > (profile.optimalWindow[1] + 15)) {
            alertBox.classList.add('sim-window-danger');
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> <strong>CRITICAL LOSS:</strong> Standing past maturity. Inversion active. Cane losing ' + dailyLossKgPerMt + ' kg sugar per tonne. Prioritize instant harvest docket.';
        } else if (ageDays >= profile.optimalWindow[0] && ageDays <= profile.optimalWindow[1] && standingDays <= 7) {
            alertBox.classList.add('sim-window-optimal');
            alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> <strong>OPTIMAL PEAK WINDOW:</strong> Peak commercial sucrose stage (CCS ' + currentCcs + '%). Cut within current 10-day capacity horizon.';
        } else if (ageDays < profile.optimalWindow[0]) {
            alertBox.classList.add('sim-window-warning');
            alertBox.innerHTML = '<i class="fa-solid fa-clock"></i> <strong>IMMATURE CANE:</strong> Pre-peak vegetative stage. Sugar accumulation active. Postpone harvest slip by ~' + (profile.optimalWindow[0] - ageDays) + ' days.';
        } else {
            alertBox.classList.add('sim-window-warning');
            alertBox.innerHTML = '<i class="fa-solid fa-hourglass-half"></i> <strong>MODERATE STANDING STRESS:</strong> Ripening plateau reached. Sequence into next dispatch batch.';
        }
    }

    renderRipeningSvgChart(profile, ageDays, currentCcs);
}

function renderRipeningSvgChart(profile, currentAge, currentCcs) {
    const container = document.getElementById('simGraphCanvasWrap');
    if (!container) return;

    const width = container.clientWidth || 500;
    const height = 180;
    const padding = { top: 20, right: 30, bottom: 30, left: 40 };

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
        '<text x="' + ((parseFloat(optX1) + parseFloat(optX2))/2) + '" y="' + (padding.top + 14) + '" fill="#10b981" font-size="10" font-family="monospace" text-anchor="middle">PEAK HARVEST WINDOW</text>' +
        '<line x1="' + padding.left + '" y1="' + getY(10) + '" x2="' + (width - padding.right) + '" y2="' + getY(10) + '" stroke="rgba(255,255,255,0.06)" stroke-dasharray="3,3" />' +
        '<line x1="' + padding.left + '" y1="' + getY(12) + '" x2="' + (width - padding.right) + '" y2="' + getY(12) + '" stroke="rgba(255,255,255,0.06)" stroke-dasharray="3,3" />' +
        '<line x1="' + padding.left + '" y1="' + getY(14) + '" x2="' + (width - padding.right) + '" y2="' + getY(14) + '" stroke="rgba(255,255,255,0.06)" stroke-dasharray="3,3" />' +
        '<text x="' + (padding.left - 8) + '" y="' + (getY(10) + 3) + '" fill="#64748b" font-size="10" text-anchor="end">10%</text>' +
        '<text x="' + (padding.left - 8) + '" y="' + (getY(12) + 3) + '" fill="#64748b" font-size="10" text-anchor="end">12%</text>' +
        '<text x="' + (padding.left - 8) + '" y="' + (getY(14) + 3) + '" fill="#64748b" font-size="10" text-anchor="end">14%</text>' +
        '<path d="' + pathD + '" fill="none" stroke="#00f2fe" stroke-width="3" stroke-linecap="round" />' +
        '<line x1="' + currentX + '" y1="' + padding.top + '" x2="' + currentX + '" y2="' + (height - padding.bottom) + '" stroke="#f59e0b" stroke-width="2" stroke-dasharray="4,3" />' +
        '<circle cx="' + currentX + '" cy="' + currentY + '" r="6" fill="#f59e0b" stroke="#ffffff" stroke-width="2" />' +
        '<text x="' + currentX + '" y="' + (height - padding.bottom + 18) + '" fill="#f59e0b" font-size="10" font-family="monospace" text-anchor="middle">Day ' + currentAge + '</text>' +
        '</svg>';

    container.innerHTML = svg;
}

/* ==========================================================================
   3. MILL RECOVERY ROI CALCULATOR
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

    if (!tcdSlider) return;

    function recalculateRoi() {
        const tcd = parseInt(tcdSlider.value);
        const days = parseInt(daysSlider.value);
        const baselineRecovery = parseFloat(recoverySlider.value);
        const pricePerQuintal = parseInt(priceSlider.value);

        if (tcdVal) tcdVal.textContent = tcd.toLocaleString() + ' TCD';
        if (daysVal) daysVal.textContent = days + ' Days';
        if (recoveryVal) recoveryVal.textContent = baselineRecovery.toFixed(1) + '%';
        if (priceVal) priceVal.textContent = '₹' + pricePerQuintal.toLocaleString();

        const totalCaneCrushed = tcd * days;
        const projectedRecoveryBoost = 0.58;
        const newRecovery = (baselineRecovery + projectedRecoveryBoost).toFixed(2);
        
        const additionalSugarBags = Math.round(totalCaneCrushed * (projectedRecoveryBoost / 10));
        const additionalSugarRevenueCrores = ((additionalSugarBags * pricePerQuintal) / 10000000).toFixed(2);
        
        const freightSavingsCrores = ((totalCaneCrushed * 22) / 10000000).toFixed(2);
        const totalFinancialImpact = (parseFloat(additionalSugarRevenueCrores) + parseFloat(freightSavingsCrores)).toFixed(2);

        const totalCaneEl = document.getElementById('roiTotalCane');
        const recoveryBoostEl = document.getElementById('roiRecoveryBoost');
        const sugarBagsEl = document.getElementById('roiSugarBags');
        const sugarRevEl = document.getElementById('roiSugarRev');
        const freightSaveEl = document.getElementById('roiFreightSave');
        const totalImpactEl = document.getElementById('roiTotalImpact');

        if (totalCaneEl) totalCaneEl.textContent = (totalCaneCrushed / 100000).toFixed(2) + ' Lakh MT';
        if (recoveryBoostEl) recoveryBoostEl.textContent = '+' + projectedRecoveryBoost + '% (' + baselineRecovery.toFixed(1) + '% → ' + newRecovery + '%)';
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
   4. CADASTRAL GAT & GHOST PLOT AUDIT SHOWCASE
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
            mapMock.style.background = 'radial-gradient(circle, rgba(0, 230, 118, 0.3) 0%, rgba(9, 19, 38, 0.95) 75%)';
            mapMock.innerHTML = '<div style="text-align:center;"><div style="color:#00e676; font-size:1.8rem; margin-bottom:4px;"><i class="fa-solid fa-satellite-dish"></i></div><div style="font-size:0.85rem; font-family:monospace; color:#ffffff;">Sentinel-2 Canopy Density: <strong>94.2%</strong></div><div style="font-size:0.75rem; color:#94a3b8;">Walked GPS Perimeter matches 7/12 BhuNaksha Land Record</div></div>';
        }
        if (valNdvi) valNdvi.innerHTML = '<span style="color:#00e676; font-weight:700;">0.78 (High Vigor) [M]</span>';
        if (valArea) valArea.innerHTML = 'Registered: 1.80 Ha | Walked: 1.82 Ha <span style="color:#00e676;">(+1.1% Match) [D]</span>';
        if (valCcs) valCcs.innerHTML = '<span style="color:#00f2fe; font-weight:700;">12.4% CCS (Peak Ripening) [X]</span>';
        if (valStatus) valStatus.innerHTML = '<span style="color:#00e676; font-weight:800;">CONFIRMED AUTHENTIC CANE</span>';
        if (valDocket) valDocket.innerHTML = '<span class="badge badge-green">APPROVED FOR CRUSH DISPATCH</span>';
    });

    btnGhost.addEventListener('click', () => {
        btnGhost.className = 'audit-tab-btn active ghost';
        btnLegit.className = 'audit-tab-btn';

        if (plotBadge) plotBadge.innerHTML = '<span class="badge badge-danger"><i class="fa-solid fa-skull-crossbones"></i> FRAUD DETECTED</span>';
        if (plotTitle) plotTitle.textContent = 'Gat 89 - Ghotan Sector 4 (Farmer: Registered Placeholder)';
        if (mapMock) {
            mapMock.style.background = 'radial-gradient(circle, rgba(239, 68, 68, 0.35) 0%, rgba(15, 10, 15, 0.95) 75%)';
            mapMock.innerHTML = '<div style="text-align:center;"><div style="color:#ef4444; font-size:1.8rem; margin-bottom:4px;"><i class="fa-solid fa-triangle-exclamation"></i></div><div style="font-size:0.85rem; font-family:monospace; color:#ffffff;">Sentinel-2 Canopy Density: <strong style="color:#ef4444;">0.0% (Zero Vegetation)</strong></div><div style="font-size:0.75rem; color:#fca5a5;">Barren Soil / Ghost Plot - Slip Blocked by IkshuVruddhi Engine</div></div>';
        }
        if (valNdvi) valNdvi.innerHTML = '<span style="color:#ef4444; font-weight:700;">0.14 (Fallow Land / Barren) [M]</span>';
        if (valArea) valArea.innerHTML = 'Registered: 3.50 Ha | Real Cane: 0.00 Ha <span style="color:#ef4444;">(-100% Divergence) [D]</span>';
        if (valCcs) valCcs.innerHTML = '<span style="color:#94a3b8;">N/A (No Crop Standing) [?]</span>';
        if (valStatus) valStatus.innerHTML = '<span style="color:#ef4444; font-weight:800;">GHOST PLOT / PHANTOM SUBSIDY FRAUD</span>';
        if (valDocket) valDocket.innerHTML = '<span class="badge badge-danger">HARVEST DOCKET BLOCKED & REJECTED</span>';
    });
}

/* ==========================================================================
   5. BILINGUAL LANGUAGE TOGGLE (EN / MARATHI)
   ========================================================================== */
const I18N = {
    en: {
        heroTitle: 'Autonomous Sugarcane Intelligence from Orbit to Mill Crushing',
        heroSubtitle: 'Empowering Sugar Mills & Agricultural Cooperatives with AI-driven pre-harvest sucrose forecasting, cadastral Gat reconciliation, and capacity-balanced harvest scheduling. Maximize sugar recovery (CCS), eliminate ghost-plot fraud, and cut harvest-to-crush delays.',
        btnLaunchConsole: 'Launch Operational Console',
        btnCalcRoi: 'Calculate Mill Recovery ROI'
    },
    mr: {
        heroTitle: 'उपग्रह रिमोट सेन्सिंग व AI द्वारे ऊस गाळप व साखर उतारा नियोजन',
        heroSubtitle: 'साखर कारखान्यांसाठी सॅटेलाईट रिमोट सेन्सिंग, गट नंबर 7/12 अचूक पडताळणी, तोडणी आधी साखर उतारा (CCS) अंदाज आणि रोजच्या गाळप क्षमतेनुसार स्वयंचलित तोडणी प्रोग्राम.',
        btnLaunchConsole: 'लाईव्ह ऑपरेशनल कन्सोल उघडा',
        btnCalcRoi: 'कारखाना साखर उतारा नफा कॅल्क्युलेटर'
    }
};

let currentLang = 'en';

function initLanguageToggle() {
    const langBtn = document.getElementById('langToggleBtn');
    if (!langBtn) return;

    langBtn.addEventListener('click', () => {
        currentLang = (currentLang === 'en') ? 'mr' : 'en';
        langBtn.innerHTML = (currentLang === 'en') ? '🌐 EN | मराठी' : '🌐 मराठी | EN';

        const data = I18N[currentLang];
        const titleEl = document.getElementById('heroMainTitle');
        const subEl = document.getElementById('heroMainSubtitle');
        const launchBtn = document.getElementById('heroLaunchBtn');
        const roiBtn = document.getElementById('heroRoiBtn');

        if (titleEl) titleEl.textContent = data.heroTitle;
        if (subEl) subEl.textContent = data.heroSubtitle;
        if (launchBtn) launchBtn.innerHTML = '<i class="fa-solid fa-gauge-high"></i> ' + data.btnLaunchConsole;
        if (roiBtn) roiBtn.innerHTML = '<i class="fa-solid fa-calculator"></i> ' + data.btnCalcRoi;
    });
}

/* ==========================================================================
   6. DNS CONFIGURATION MODAL (Fixing ERR_NAME_NOT_RESOLVED)
   ========================================================================== */
function initDnsModal() {
    const openBtn = document.getElementById('btnOpenDnsModal');
    const modal = document.getElementById('dnsModalOverlay');
    const closeBtn = document.getElementById('btnCloseDnsModal');

    if (!modal) return;

    if (openBtn) {
        openBtn.addEventListener('click', (e) => {
            e.preventDefault();
            modal.classList.add('active');
        });
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            modal.classList.remove('active');
        });
    }

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
        }
    });

    document.querySelectorAll('.copy-badge').forEach(badge => {
        badge.addEventListener('click', () => {
            const text = badge.dataset.copy;
            navigator.clipboard.writeText(text).then(() => {
                const original = badge.innerHTML;
                badge.innerHTML = '✓ Copied';
                setTimeout(() => { badge.innerHTML = original; }, 2000);
            });
        });
    });
}

/* ==========================================================================
   7. CONTACT FORM
   ========================================================================== */
function initContactForm() {
    const form = document.getElementById('pilotContactForm');
    const successMsg = document.getElementById('contactSuccessMsg');

    if (!form) return;

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const mill = document.getElementById('formMillName').value;
        const name = document.getElementById('formContactName').value;
        const email = document.getElementById('formEmail').value;
        const phone = document.getElementById('formPhone').value;
        const tcd = document.getElementById('formTcd').value;
        const notes = document.getElementById('formNotes').value;

        const subject = encodeURIComponent('Ikshu Intelligence Pilot Request: ' + mill + ' (' + tcd + ' TCD)');
        const body = encodeURIComponent(
            'Mill/Organization: ' + mill + '\n' +
            'Representative: ' + name + '\n' +
            'Email: ' + email + '\n' +
            'Phone/WhatsApp: ' + phone + '\n' +
            'Crushing Capacity: ' + tcd + ' TCD\n' +
            'Requirements:\n' + notes + '\n'
        );

        const mailtoUri = 'mailto:contact@ikshuintelligence.com?subject=' + subject + '&body=' + body;
        
        if (successMsg) {
            successMsg.style.display = 'block';
            successMsg.innerHTML = '<i class="fa-solid fa-circle-check"></i> Opening email client to send request to <strong>contact@ikshuintelligence.com</strong>...';
        }

        setTimeout(() => {
            window.location.href = mailtoUri;
        }, 800);
    });
}

/* ==========================================================================
   8. SUGAR MILL ENTERPRISE ACCOUNT & GATEWAY LOGIC
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
                <div class="mill-logged-in-container">
                    <a href="console.html" class="mill-logged-in-badge" title="Active Factory: ${profile.millName}">
                        <i class="fa-solid fa-circle" style="font-size:0.5rem; color:#10b981;"></i>
                        <span>${profile.shortName || 'Factory'} (${profile.shortRole || 'Staff'})</span>
                    </a>
                    <button onclick="signOutMill()" class="mill-switch-btn" title="Sign out of factory account">
                        <i class="fa-solid fa-right-from-bracket"></i>
                    </button>
                </div>
            `;
        } catch (e) {
            console.error('Error parsing mill profile', e);
        }
    }
}

function switchMillAuthTab(tab) {
    const btnSignIn = document.getElementById('tabBtnSignIn');
    const btnSandbox = document.getElementById('tabBtnSandbox');
    const btnRegister = document.getElementById('tabBtnRegister');

    const contentSignIn = document.getElementById('tabContentSignIn');
    const contentSandbox = document.getElementById('tabContentSandbox');
    const contentRegister = document.getElementById('tabContentRegister');

    if (!btnSignIn || !contentSignIn) return;

    btnSignIn.classList.remove('active');
    btnSandbox.classList.remove('active');
    btnRegister.classList.remove('active');

    contentSignIn.style.display = 'none';
    contentSandbox.style.display = 'none';
    contentRegister.style.display = 'none';

    if (tab === 'signin') {
        btnSignIn.classList.add('active');
        contentSignIn.style.display = 'block';
    } else if (tab === 'sandbox') {
        btnSandbox.classList.add('active');
        contentSandbox.style.display = 'block';
    } else if (tab === 'register') {
        btnRegister.classList.add('active');
        contentRegister.style.display = 'block';
    }
}

function selectMillRole(el, roleName) {
    document.querySelectorAll('.role-choice-card').forEach(c => c.classList.remove('selected'));
    el.classList.add('selected');
    selectedMillRole = roleName;
}

function handleMillSignIn(e) {
    e.preventDefault();
    const sel = document.getElementById('selFactoryCode');
    const opt = sel.options[sel.selectedIndex];
    const pin = (document.getElementById('millAuthPin').value || '').trim().toLowerCase();
    const err = document.getElementById('millAuthErr');

    const validPins = ['ikshu2026', 'sugar2026', 'ikshu-gangamai', 'ikshu-admin', 'rushikesh2026'];

    if (validPins.includes(pin)) {
        const millProfile = {
            millCode: sel.value,
            millName: opt.dataset.name || opt.text,
            shortName: (opt.dataset.name || '').includes('Gangamai') ? 'Gangamai SSK' : 
                       (opt.dataset.name || '').includes('Samarth') ? 'Samarth SSK' : 'Sugar Mill',
            tcd: opt.dataset.tcd || '4,500 TCD',
            location: opt.dataset.loc || 'Maharashtra',
            role: selectedMillRole,
            shortRole: selectedMillRole.includes('Managing') ? 'MD' :
                       selectedMillRole.includes('Agri') ? 'CAO' :
                       selectedMillRole.includes('Chemist') ? 'Lab' : 'Field',
            authTime: new Date().toISOString()
        };

        sessionStorage.setItem('ikshu_enterprise_auth', 'granted');
        sessionStorage.setItem('ikshu_mill_profile', JSON.stringify(millProfile));

        const modal = document.getElementById('millAuthModalOverlay');
        if (modal) modal.classList.remove('active');

        // Redirect to console
        window.location.href = 'console.html';
    } else {
        if (err) err.style.display = 'flex';
    }
}

function launchSandboxMill(millName, role, millCode, tcd) {
    const millProfile = {
        millCode: millCode,
        millName: millName,
        shortName: millName.includes('Gangamai') ? 'Gangamai SSK' : 
                   millName.includes('Samarth') ? 'Samarth SSK' : 'Sandbox Mill',
        tcd: tcd,
        location: 'Maharashtra Command Area',
        role: role,
        shortRole: role.includes('Managing') ? 'MD' :
                   role.includes('Agri') ? 'CAO' :
                   role.includes('Chemist') ? 'Lab' : 'Field',
        isSandbox: true,
        authTime: new Date().toISOString()
    };

    sessionStorage.setItem('ikshu_enterprise_auth', 'granted');
    sessionStorage.setItem('ikshu_mill_profile', JSON.stringify(millProfile));

    const modal = document.getElementById('millAuthModalOverlay');
    if (modal) modal.classList.remove('active');

    window.location.href = 'console.html';
}

function openNewMillRegisterTab() {
    const modal = document.getElementById('millAuthModalOverlay');
    if (modal) {
        modal.classList.add('active');
        switchMillAuthTab('register');
    }
}

function handleNewMillRegister(e) {
    e.preventDefault();
    const name = document.getElementById('regMillName').value;
    const loc = document.getElementById('regMillLocation').value;
    const tcd = document.getElementById('regMillTcd').value;
    const role = document.getElementById('regMillRole').value;
    const email = document.getElementById('regMillEmail').value;
    const phone = document.getElementById('regMillPhone').value;

    alert('Sugar Mill Provisioning Request Received for ' + name + ' (' + tcd + ').\n\nOur agricultural remote sensing team will contact ' + email + ' / ' + phone + ' within 24 hours with your customized factory tenant code.\n\nLaunching instant evaluator sandbox now...');

    launchSandboxMill(name, role, 'MILL-PROV-' + Math.floor(Math.random() * 900 + 100), tcd);
}

function signOutMill() {
    sessionStorage.removeItem('ikshu_enterprise_auth');
    sessionStorage.removeItem('ikshu_mill_profile');
    window.location.reload();
}
