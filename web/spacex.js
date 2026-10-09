/**
 * IKSHU INTELLIGENCE - SpaceX Style Mission Engine
 * Domain: ikshuintelligence.com
 */

document.addEventListener('DOMContentLoaded', () => {
    initNavAndScroll();
    initDrawers();
    initMenu();
    initRipeningSimulation();
    initRoiCalculator();
    initCadastralAudit();
    initContactForm();
});

/* ==========================================================================
   NAVIGATION & ACTIVE SCROLL
   ========================================================================== */
function initNavAndScroll() {
    const nav = document.querySelector('.spacex-nav');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            nav.classList.add('scrolled');
        } else {
            nav.classList.remove('scrolled');
        }
    });
}

/* ==========================================================================
   HAMBURGER MENU
   ========================================================================== */
function initMenu() {
    const btn = document.getElementById('btnMenuToggle');
    const menu = document.getElementById('spacexMenu');
    const overlay = document.getElementById('drawerOverlay');

    if (!btn || !menu) return;

    btn.addEventListener('click', () => {
        const isOpen = menu.classList.contains('active');
        if (isOpen) {
            closeAllDrawers();
        } else {
            closeAllDrawers();
            menu.classList.add('active');
            if (overlay) overlay.classList.add('active');
        }
    });

    document.querySelectorAll('.menu-nav-list a').forEach(link => {
        link.addEventListener('click', () => {
            closeAllDrawers();
        });
    });
}

/* ==========================================================================
   SLIDE-OVER DRAWERS
   ========================================================================== */
function initDrawers() {
    const overlay = document.getElementById('drawerOverlay');

    document.querySelectorAll('[data-open-drawer]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = btn.getAttribute('data-open-drawer');
            openDrawer(targetId);
        });
    });

    document.querySelectorAll('.btn-drawer-close').forEach(btn => {
        btn.addEventListener('click', () => {
            closeAllDrawers();
        });
    });

    if (overlay) {
        overlay.addEventListener('click', () => {
            closeAllDrawers();
        });
    }

    // DNS Quick copy buttons
    document.querySelectorAll('.copy-badge').forEach(badge => {
        badge.addEventListener('click', () => {
            const text = badge.getAttribute('data-copy');
            navigator.clipboard.writeText(text).then(() => {
                const original = badge.innerHTML;
                badge.innerHTML = '✓ COPIED';
                setTimeout(() => { badge.innerHTML = original; }, 2000);
            });
        });
    });
}

function openDrawer(id) {
    closeAllDrawers();
    const drawer = document.getElementById(id);
    const overlay = document.getElementById('drawerOverlay');
    if (drawer) {
        drawer.classList.add('active');
        if (overlay) overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeAllDrawers() {
    document.querySelectorAll('.spacex-drawer, .spacex-menu-overlay').forEach(el => {
        el.classList.remove('active');
    });
    const overlay = document.getElementById('drawerOverlay');
    if (overlay) overlay.classList.remove('active');
    document.body.style.overflow = 'auto';
}
/* ==========================================================================
   INTERACTIVE SUCROSE RIPENING ENGINE
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

function initRipeningSimulation() {
    const btns = document.querySelectorAll('.drawer-variety-btn');
    const ageSlider = document.getElementById('drawerAgeSlider');
    const ageVal = document.getElementById('drawerAgeVal');
    const standingSlider = document.getElementById('drawerStandingSlider');
    const standingVal = document.getElementById('drawerStandingVal');

    if (!ageSlider || !standingSlider) return;

    btns.forEach(b => {
        b.addEventListener('click', (e) => {
            btns.forEach(x => x.classList.remove('active'));
            e.currentTarget.classList.add('active');
            currentVariety = e.currentTarget.getAttribute('data-variety');
            updateRipeningCalculations();
        });
    });

    ageSlider.addEventListener('input', (e) => {
        const days = parseInt(e.target.value);
        if (ageVal) ageVal.textContent = days + ' DAYS (' + (days/30.4).toFixed(1) + ' MO)';
        updateRipeningCalculations();
    });

    standingSlider.addEventListener('input', (e) => {
        const days = parseInt(e.target.value);
        if (standingVal) standingVal.textContent = days + ' DAYS PAST PEAK';
        updateRipeningCalculations();
    });

    updateRipeningCalculations();
}

function updateRipeningCalculations() {
    const profile = VARIETY_DATA[currentVariety] || VARIETY_DATA['Co 86032'];
    const ageSlider = document.getElementById('drawerAgeSlider');
    const standingSlider = document.getElementById('drawerStandingSlider');
    if (!ageSlider || !standingSlider) return;

    const ageDays = parseInt(ageSlider.value);
    const standingDays = parseInt(standingSlider.value);

    const deltaPeak = ageDays - profile.peakAge;
    let factor = 1.0;

    if (deltaPeak < 0) {
        factor = Math.max(0.65, 1.0 - Math.pow(deltaPeak / 160, 2) * 0.45);
    } else {
        const natDecay = Math.pow(deltaPeak / 180, 1.6) * 0.35;
        const postStanding = (standingDays * profile.decayRate * 0.08);
        factor = Math.max(0.60, 1.0 - natDecay - postStanding);
    }

    const ccs = (profile.baseCcs * factor).toFixed(2);
    const brix = (profile.baseBrix * (0.8 + 0.2 * factor)).toFixed(1);
    const pol = (ccs * 1.34 - (brix * 0.22)).toFixed(2);

    const lossKg = (standingDays > 0) ? (standingDays * 0.42 + (standingDays * standingDays * 0.012)).toFixed(1) : '0.0';
    const lossMoney = ((parseFloat(lossKg) * 5000 / 100) * 3600 / 100000).toFixed(2);

    const elCcs = document.getElementById('resCcs');
    const elBrix = document.getElementById('resBrix');
    const elPol = document.getElementById('resPol');
    const elLoss = document.getElementById('resLoss');
    const elLossMoney = document.getElementById('resLossMoney');

    if (elCcs) elCcs.textContent = ccs + '%';
    if (elBrix) elBrix.textContent = brix + '°';
    if (elPol) elPol.textContent = pol + '%';
    if (elLoss) elLoss.textContent = lossKg + ' kg/MT';
    if (elLossMoney) elLossMoney.textContent = '₹' + lossMoney + ' Lakhs';
}

/* ==========================================================================
   MILL ECONOMIC ROI CALCULATOR
   ========================================================================== */
function initRoiCalculator() {
    const tcdSlider = document.getElementById('drawerTcd');
    const daysSlider = document.getElementById('drawerDays');
    const recSlider = document.getElementById('drawerRec');
    const priceSlider = document.getElementById('drawerPrice');

    if (!tcdSlider) return;

    function recalc() {
        const tcd = parseInt(tcdSlider.value);
        const days = parseInt(daysSlider.value);
        const rec = parseFloat(recSlider.value);
        const price = parseInt(priceSlider.value);

        const lblTcd = document.getElementById('valTcd');
        const lblDays = document.getElementById('valDays');
        const lblRec = document.getElementById('valRec');
        const lblPrice = document.getElementById('valPrice');

        if (lblTcd) lblTcd.textContent = tcd.toLocaleString() + ' TCD';
        if (lblDays) lblDays.textContent = days + ' DAYS';
        if (lblRec) lblRec.textContent = rec.toFixed(1) + '%';
        if (lblPrice) lblPrice.textContent = '₹' + price.toLocaleString();

        const totalCane = tcd * days;
        const recoveryBoost = 0.58;
        const sugarBags = Math.round(totalCane * (recoveryBoost / 10));
        const addRevenueCr = ((sugarBags * price) / 10000000).toFixed(2);
        const freightSaveCr = ((totalCane * 22) / 10000000).toFixed(2);
        const totalImpact = (parseFloat(addRevenueCr) + parseFloat(freightSaveCr)).toFixed(2);

        const elTotalCr = document.getElementById('resRoiImpact');
        const elBags = document.getElementById('resRoiBags');
        const elRev = document.getElementById('resRoiSugar');
        const elFreight = document.getElementById('resRoiFreight');

        if (elTotalCr) elTotalCr.textContent = '₹' + totalImpact + ' CRORES';
        if (elBags) elBags.textContent = '+' + sugarBags.toLocaleString() + ' BAGS';
        if (elRev) elRev.textContent = '₹' + addRevenueCr + ' CR';
        if (elFreight) elFreight.textContent = '₹' + freightSaveCr + ' CR';
    }

    tcdSlider.addEventListener('input', recalc);
    daysSlider.addEventListener('input', recalc);
    recSlider.addEventListener('input', recalc);
    priceSlider.addEventListener('input', recalc);

    recalc();
}

/* ==========================================================================
   CADASTRAL 7/12 & GHOST PLOT AUDIT
   ========================================================================== */
function initCadastralAudit() {
    const btnL = document.getElementById('drawerAuditLegit');
    const btnG = document.getElementById('drawerAuditGhost');
    const display = document.getElementById('drawerAuditBox');

    if (!btnL || !btnG || !display) return;

    btnL.addEventListener('click', () => {
        btnL.classList.add('active');
        btnG.classList.remove('active');
        display.innerHTML = `
            <div style="padding: 16px; border: 1px solid rgba(0, 230, 118, 0.4); background: rgba(0, 230, 118, 0.05); margin-bottom: 16px;">
                <div style="font-size: 0.75rem; color: #00e676; font-weight: 800; letter-spacing: 0.15em;">STATUS: VERIFIED PARCEL [M]</div>
                <h4 style="font-size: 1.1rem; color: #ffffff; margin-top: 4px;">GAT 142 - BABHALESHWAR (BALASAHEB VIKHE)</h4>
            </div>
            <div style="font-family: var(--font-mono); font-size: 0.85rem; line-height: 1.8; color: #d4d4d4;">
                <div>SENTINEL-2 CANOPY DENSITY: <strong style="color: #00e676;">94.2%</strong></div>
                <div>VEGETATION INDEX (NDVI): <strong style="color: #00e676;">0.78 (HIGH VIGOR)</strong></div>
                <div>ACREAGE RECONCILIATION: <strong>1.80 HA REG. vs 1.82 HA WALKED (+1.1%)</strong></div>
                <div>ESTIMATED COMMERCIAL RECOVERY: <strong style="color: #00f2fe;">12.4% CCS</strong></div>
                <div style="margin-top: 10px; color: #00e676; font-weight: 800;">✓ HARVEST DOCKET APPROVED FOR CRUSH DISPATCH</div>
            </div>
        `;
    });

    btnG.addEventListener('click', () => {
        btnG.classList.add('active');
        btnL.classList.remove('active');
        display.innerHTML = `
            <div style="padding: 16px; border: 1px solid rgba(239, 68, 68, 0.4); background: rgba(239, 68, 68, 0.08); margin-bottom: 16px;">
                <div style="font-size: 0.75rem; color: #ef4444; font-weight: 800; letter-spacing: 0.15em;">STATUS: FRAUD DETECTED [?]</div>
                <h4 style="font-size: 1.1rem; color: #ffffff; margin-top: 4px;">GAT 89 - GHOTAN SECTOR 4 (REGISTERED PLACEHOLDER)</h4>
            </div>
            <div style="font-family: var(--font-mono); font-size: 0.85rem; line-height: 1.8; color: #d4d4d4;">
                <div>SENTINEL-2 CANOPY DENSITY: <strong style="color: #ef4444;">0.0% (ZERO CANOPY / BARREN)</strong></div>
                <div>VEGETATION INDEX (NDVI): <strong style="color: #ef4444;">0.14 (FALLOW DIRT)</strong></div>
                <div>ACREAGE DIVERGENCE: <strong style="color: #ef4444;">3.50 HA REG. vs 0.00 HA STANDING (-100%)</strong></div>
                <div>SUCROSE ESTIMATION: <strong style="color: #737373;">N/A (NO CROP)</strong></div>
                <div style="margin-top: 10px; color: #ef4444; font-weight: 800;">✕ HARVEST DOCKET REJECTED & BLOCKED: PHANTOM FRAUD</div>
            </div>
        `;
    });
}

/* ==========================================================================
   CONTACT DISPATCH
   ========================================================================== */
function initContactForm() {
    const form = document.getElementById('spacexContactForm');
    if (!form) return;

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const mill = document.getElementById('spxMill').value;
        const name = document.getElementById('spxName').value;
        const email = document.getElementById('spxEmail').value;
        const phone = document.getElementById('spxPhone').value;
        const tcd = document.getElementById('spxTcd').value;

        const subject = encodeURIComponent('Mission Audit Request: ' + mill + ' (' + tcd + ' TCD)');
        const body = encodeURIComponent(
            'MILL / ORGANIZATION: ' + mill + '\n' +
            'CONTACT PERSON: ' + name + '\n' +
            'EMAIL: ' + email + '\n' +
            'PHONE / WHATSAPP: ' + phone + '\n' +
            'CRUSHING CAPACITY: ' + tcd + ' TCD\n'
        );

        const msg = document.getElementById('spxMsg');
        if (msg) {
            msg.style.display = 'block';
            msg.innerHTML = 'OPENING DISPATCH MAIL CLIENT TO <strong>CONTACT@IKSHUINTELLIGENCE.COM</strong>...';
        }

        setTimeout(() => {
            window.location.href = 'mailto:contact@ikshuintelligence.com?subject=' + subject + '&body=' + body;
        }, 600);
    });
}