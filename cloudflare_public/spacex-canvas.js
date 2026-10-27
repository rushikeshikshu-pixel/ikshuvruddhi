/**
 * IKSHU INTELLIGENCE - ORBITAL TELEMETRY & RADAR CANVAS ENGINE
 * High-performance, 60 FPS HTML5 Canvas rendering satellite orbits,
 * radar sweeps, and Maharashtra sugarcane belt telemetry.
 */

(function() {
    'use strict';

    const canvas = document.getElementById('spaceCanvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let width = 0;
    let height = 0;
    let animationFrameId = null;
    let isVisible = true;

    // Sugarcane mill cluster coordinates & telemetry markers
    const MILL_RADAR_NODES = [
        { name: 'AHILYANAGAR CLUSTER', lat: '19.52° N', lon: '75.02° E', xRatio: 0.42, yRatio: 0.38, ccs: '12.4%', vigor: '0.82', status: 'PEAK' },
        { name: 'JALNA SAMARTH SSK', lat: '19.84° N', lon: '75.88° E', xRatio: 0.65, yRatio: 0.32, ccs: '12.1%', vigor: '0.79', status: 'PEAK' },
        { name: 'KOLHAPUR SOUTH BELT', lat: '16.70° N', lon: '74.24° E', xRatio: 0.32, yRatio: 0.72, ccs: '13.1%', vigor: '0.88', status: 'HARVEST' },
        { name: 'SOLAPUR COOPERATIVE', lat: '17.65° N', lon: '75.90° E', xRatio: 0.68, yRatio: 0.64, ccs: '11.8%', vigor: '0.74', status: 'MONITOR' },
        { name: 'PUNE EAST IRRIGATION', lat: '18.52° N', lon: '74.50° E', xRatio: 0.45, yRatio: 0.54, ccs: '12.6%', vigor: '0.84', status: 'PEAK' }
    ];

    // Starfield particles
    const STARS_COUNT = 90;
    let stars = [];

    // Satellite orbits (Sentinel-2A, Sentinel-2B, Landsat-9)
    const ORBITS = [
        {
            name: 'SENTINEL-2A (ESA)',
            radiusXRatio: 0.45,
            radiusYRatio: 0.28,
            tilt: -0.25,
            speed: 0.00045,
            angle: 0.2,
            color: '#00f2fe',
            altitude: '786 km'
        },
        {
            name: 'SENTINEL-2B (ESA)',
            radiusXRatio: 0.52,
            radiusYRatio: 0.32,
            tilt: 0.35,
            speed: 0.00038,
            angle: 2.8,
            color: '#00e676',
            altitude: '786 km'
        },
        {
            name: 'LANDSAT-9 (USGS/NASA)',
            radiusXRatio: 0.58,
            radiusYRatio: 0.36,
            tilt: -0.42,
            speed: 0.00028,
            angle: 4.5,
            color: '#38bdf8',
            altitude: '705 km'
        }
    ];

    let radarAngle = 0;
    const RADAR_SPEED = 0.012;

    function resize() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
        initStars();
    }

    function initStars() {
        stars = [];
        for (let i = 0; i < STARS_COUNT; i++) {
            stars.push({
                x: Math.random() * width,
                y: Math.random() * height,
                size: Math.random() * 1.5 + 0.4,
                alpha: Math.random() * 0.7 + 0.2,
                alphaSpeed: (Math.random() * 0.01 + 0.005) * (Math.random() > 0.5 ? 1 : -1)
            });
        }
    }

    function drawStars() {
        for (let i = 0; i < stars.length; i++) {
            const s = stars[i];
            s.alpha += s.alphaSpeed;
            if (s.alpha > 0.85 || s.alpha < 0.15) {
                s.alphaSpeed = -s.alphaSpeed;
            }

            ctx.fillStyle = `rgba(255, 255, 255, ${s.alpha.toFixed(2)})`;
            ctx.beginPath();
            ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    function drawOrbits() {
        const cx = width * 0.5;
        const cy = height * 0.48;

        ORBITS.forEach(orbit => {
            orbit.angle += orbit.speed;

            const rx = width * orbit.radiusXRatio;
            const ry = height * orbit.radiusYRatio;

            ctx.save();
            ctx.translate(cx, cy);
            ctx.rotate(orbit.tilt);

            // Elliptical trajectory line
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.035)';
            ctx.lineWidth = 1;
            ctx.setLineDash([4, 8]);
            ctx.beginPath();
            ctx.ellipse(0, 0, rx, ry, 0, 0, Math.PI * 2);
            ctx.stroke();
            ctx.setLineDash([]);

            // Satellite position on ellipse
            const sx = Math.cos(orbit.angle) * rx;
            const sy = Math.sin(orbit.angle) * ry;

            // Satellite glow halo
            const grad = ctx.createRadialGradient(sx, sy, 0, sx, sy, 18);
            grad.addColorStop(0, orbit.color);
            grad.addColorStop(0.3, orbit.color + '44');
            grad.addColorStop(1, 'transparent');
            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.arc(sx, sy, 18, 0, Math.PI * 2);
            ctx.fill();

            // Satellite core
            ctx.fillStyle = '#ffffff';
            ctx.beginPath();
            ctx.arc(sx, sy, 2.5, 0, Math.PI * 2);
            ctx.fill();

            // Solar panels wings
            ctx.strokeStyle = orbit.color;
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.moveTo(sx - 7, sy);
            ctx.lineTo(sx + 7, sy);
            ctx.stroke();

            // Faint telemetry tag (only visible on wide screens)
            if (width > 1024) {
                ctx.font = '9px "JetBrains Mono", monospace';
                ctx.fillStyle = 'rgba(255, 255, 255, 0.35)';
                ctx.fillText(`${orbit.name} [${orbit.altitude}]`, sx + 12, sy + 3);
            }

            ctx.restore();
        });
    }

    function drawRadarCenter() {
        // Position radar near top right quadrant behind the hero HUD
        const rx = width * (width > 900 ? 0.72 : 0.5);
        const ry = height * (width > 900 ? 0.42 : 0.48);
        const maxRadius = Math.min(width, height) * 0.38;

        // Concentric range rings
        ctx.strokeStyle = 'rgba(0, 242, 254, 0.04)';
        ctx.lineWidth = 1;
        for (let r = maxRadius * 0.25; r <= maxRadius; r += maxRadius * 0.25) {
            ctx.beginPath();
            ctx.arc(rx, ry, r, 0, Math.PI * 2);
            ctx.stroke();
        }

        // Crosshairs
        ctx.strokeStyle = 'rgba(0, 242, 254, 0.04)';
        ctx.beginPath();
        ctx.moveTo(rx - maxRadius, ry);
        ctx.lineTo(rx + maxRadius, ry);
        ctx.moveTo(rx, ry - maxRadius);
        ctx.lineTo(rx, ry + maxRadius);
        ctx.stroke();

        // Rotating radar beam
        radarAngle += RADAR_SPEED;
        const beamAngle = radarAngle % (Math.PI * 2);

        const sweepGrad = ctx.createRadialGradient(rx, ry, 0, rx, ry, maxRadius);
        sweepGrad.addColorStop(0, 'rgba(0, 242, 254, 0.1)');
        sweepGrad.addColorStop(1, 'transparent');

        ctx.save();
        ctx.translate(rx, ry);
        ctx.rotate(beamAngle);

        ctx.fillStyle = sweepGrad;
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.arc(0, 0, maxRadius, -0.4, 0);
        ctx.closePath();
        ctx.fill();

        // Leading edge line
        ctx.strokeStyle = 'rgba(0, 242, 254, 0.35)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(maxRadius, 0);
        ctx.stroke();

        ctx.restore();

        // Draw radar telemetry nodes
        MILL_RADAR_NODES.forEach((node, idx) => {
            const nx = rx + (node.xRatio - 0.5) * maxRadius * 1.6;
            const ny = ry + (node.yRatio - 0.5) * maxRadius * 1.6;

            // Distance to beam
            const dx = nx - rx;
            const dy = ny - ry;
            let nodeAngle = Math.atan2(dy, dx);
            if (nodeAngle < 0) nodeAngle += Math.PI * 2;

            let diff = beamAngle - nodeAngle;
            if (diff < 0) diff += Math.PI * 2;
            const isNearBeam = diff < 0.35;

            // Node dot
            const color = node.status === 'PEAK' ? '#00e676' : (node.status === 'HARVEST' ? '#00f2fe' : '#f59e0b');
            ctx.fillStyle = isNearBeam ? '#ffffff' : color;
            ctx.beginPath();
            ctx.arc(nx, ny, isNearBeam ? 3.5 : 2, 0, Math.PI * 2);
            ctx.fill();

            if (isNearBeam) {
                // Expanding pulse ring
                ctx.strokeStyle = color;
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.arc(nx, ny, 10, 0, Math.PI * 2);
                ctx.stroke();

                // Telemetry tag
                if (width > 800) {
                    ctx.font = '8px "JetBrains Mono", monospace';
                    ctx.fillStyle = 'rgba(0, 242, 254, 0.7)';
                    ctx.fillText(`${node.name} [CCS ${node.ccs}]`, nx + 12, ny + 3);
                }
            }
        });
    }

    function animate() {
        if (!isVisible) return;

        ctx.clearRect(0, 0, width, height);

        drawStars();
        drawOrbits();
        drawRadarCenter();

        animationFrameId = requestAnimationFrame(animate);
    }

    // Optimization: pause animation if tab is hidden
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            isVisible = false;
            if (animationFrameId) cancelAnimationFrame(animationFrameId);
        } else {
            isVisible = true;
            animate();
        }
    });

    window.addEventListener('resize', resize);
    window.addEventListener('orientationchange', resize);

    resize();
    animate();
})();
