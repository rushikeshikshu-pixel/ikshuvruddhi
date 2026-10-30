'use client';

import React, { useEffect, useRef, useState, useMemo } from 'react';

export interface FieldMapProps {
  plots?: Array<{
    id?: string;
    plotNo: string;
    village: string;
    variety: string;
    caneType: string;
    area: number;
    plantingDate?: string;
    acquisitionDate?: string | null;
    cloud?: number | null;
    ndvi?: number | null;
    harvestDate?: string | null;
    priority?: string;
  }>;
  samples?: Array<{
    plotId: string;
    pol?: number;
    brix?: number;
    recovery?: number | null;
  }>;
  interactive?: boolean;
  className?: string;
  onSelectPlot?: (plot: any) => void;
}

// Gangamai Sugar Mill Central Coordinates (Shevgaon / Najik Babhulgaon, Ahmednagar)
const GANGAMAI_COORDS: [number, number] = [19.3486, 75.2281];

// Primary village centroids within Gangamai Sugar Mill Command Area
const VILLAGE_CENTROIDS: Record<string, [number, number]> = {
  'shevgaon': [19.3486, 75.2281],
  'sainathnagar': [19.3620, 75.2450],
  'majaleshahar': [19.3850, 75.2710],
  'bodhegaon': [19.2950, 75.3850],
  'samangaon': [19.3320, 75.2100],
  'bhatkudgaon': [19.3750, 75.1850],
  'akhadwade': [19.3510, 75.2650],
  'akhadwade (shevgaon)': [19.3510, 75.2650],
  'erandgaon': [19.4120, 75.2340],
  'dadegaon': [19.3900, 75.3100],
  'malichinchora': [19.3200, 75.1600],
  'ghotan': [19.2780, 75.2950],
  'wadala': [19.5968, 75.4200],
  'telwadi': [19.4950, 75.3800],
  'eklahera': [19.3100, 75.2600],
  'shirasgaon': [19.4500, 75.1200],
  'field cluster a': [19.3650, 75.2380],
  'field cluster b': [19.3420, 75.2600],
  'field cluster c': [19.3280, 75.2050],
};

function getCoordsForPlot(village: string, plotNo: string): [number, number] {
  const vKey = (village || '').trim().toLowerCase();
  let base = VILLAGE_CENTROIDS[vKey];
  if (!base) {
    let hash = 0;
    for (let i = 0; i < vKey.length; i++) hash = ((hash << 5) - hash + vKey.charCodeAt(i)) | 0;
    const latOffset = ((Math.abs(hash) % 400) - 200) * 0.0006;
    const lngOffset = ((Math.abs(hash >> 3) % 400) - 200) * 0.0006;
    base = [GANGAMAI_COORDS[0] + latOffset, GANGAMAI_COORDS[1] + lngOffset];
  }
  let pHash = 0;
  for (let i = 0; i < plotNo.length; i++) pHash = ((pHash << 5) - pHash + plotNo.charCodeAt(i)) | 0;
  const pLat = base[0] + ((Math.abs(pHash) % 100) - 50) * 0.00015;
  const pLng = base[1] + ((Math.abs(pHash >> 2) % 100) - 50) * 0.00015;
  return [pLat, pLng];
}

export default function FieldMap({ plots, samples, interactive = true, className, onSelectPlot }: FieldMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const layersRef = useRef<{ googleHybrid?: any; googleRoadmap?: any; esriSat?: any; markersGroup?: any; radiusGroup?: any }>({});
  
  const [mapReady, setMapReady] = useState(false);
  const [mapType, setMapType] = useState<'hybrid' | 'roadmap'>('hybrid');
  const [filterPriority, setFilterPriority] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [selectedPlot, setSelectedPlot] = useState<any>(null);

  // Fallback demo plots if none passed
  const activePlots = useMemo(() => {
    if (plots && plots.length > 0) return plots;
    return [
      { id: 'p1', plotNo: 'GM-00003', village: 'Sainathnagar', variety: 'CO-265', caneType: 'Adsali', area: 0.8, plantingDate: '2025-07-20', ndvi: 0.75, cloud: 5, priority: 'Ready', harvestDate: '2026-10-25' },
      { id: 'p2', plotNo: 'GM-00004', village: 'Sainathnagar', variety: 'CO-265', caneType: 'Adsali', area: 0.8, plantingDate: '2025-07-19', ndvi: 0.76, cloud: 5, priority: 'Ready', harvestDate: '2026-10-26' },
      { id: 'p3', plotNo: 'GM-00006', village: 'Sainathnagar', variety: 'CO-265', caneType: 'Adsali', area: 1.6, plantingDate: '2025-07-23', ndvi: 0.77, cloud: 5, priority: 'Ready', harvestDate: '2026-10-27' },
      { id: 'p4', plotNo: 'GM-00009', village: 'Majaleshahar', variety: 'CO-265', caneType: 'Adsali', area: 0.7, plantingDate: '2025-08-01', ndvi: 0.78, cloud: 5, priority: 'Ready', harvestDate: '2026-10-28' },
      { id: 'p5', plotNo: 'GM-00012', village: 'Bhatkudgaon', variety: 'CO-265', caneType: 'Adsali', area: 0.4, plantingDate: '2025-07-06', ndvi: 0.80, cloud: 5, priority: 'Ready', harvestDate: '2026-10-30' },
      { id: 'p6', plotNo: 'GM-00013', village: 'Akhadwade', variety: 'CO-265', caneType: 'Adsali', area: 0.9, plantingDate: '2025-08-05', ndvi: 0.71, cloud: 12, priority: 'Review', harvestDate: '2026-11-15' },
      { id: 'p7', plotNo: 'GM-00015', village: 'Bodhegaon', variety: 'CO-86032', caneType: 'Adsali', area: 1.2, plantingDate: '2025-07-21', ndvi: 0.81, cloud: 4, priority: 'Ready', harvestDate: '2026-11-01' },
      { id: 'p8', plotNo: 'GM-00017', village: 'Samangaon', variety: 'CO-265', caneType: 'Adsali', area: 0.8, plantingDate: '2025-07-15', ndvi: 0.74, cloud: 5, priority: 'Ready', harvestDate: '2026-11-02' },
      { id: 'p9', plotNo: 'GM-00021', village: 'Malichinchora', variety: 'VSI-08005', caneType: 'Suru', area: 0.5, plantingDate: '2025-11-10', ndvi: 0.65, cloud: 8, priority: 'Hold', harvestDate: null },
      { id: 'p10', plotNo: 'GM-00033', village: 'Erandgaon', variety: 'CO-86032', caneType: 'Khodwa', area: 1.1, plantingDate: '2025-09-12', ndvi: 0.73, cloud: 6, priority: 'Review', harvestDate: '2026-12-05' },
      { id: 'p11', plotNo: 'GM-00045', village: 'Dadegaon', variety: 'CO-265', caneType: 'Adsali', area: 1.4, plantingDate: '2025-07-18', ndvi: 0.79, cloud: 3, priority: 'Ready', harvestDate: '2026-10-29' },
      { id: 'p12', plotNo: 'GM-00052', village: 'Ghotan', variety: 'CO-265', caneType: 'Adsali', area: 0.9, plantingDate: '2025-08-02', ndvi: 0.68, cloud: 7, priority: 'Review', harvestDate: '2026-11-20' },
    ];
  }, [plots]);

  // Load Leaflet dynamically and mount map
  useEffect(() => {
    let map: any = null;
    let isCancelled = false;

    // Inject Leaflet CSS link if not already present
    if (typeof document !== 'undefined' && !document.getElementById('leaflet-css')) {
      const link = document.createElement('link');
      link.id = 'leaflet-css';
      link.rel = 'stylesheet';
      link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.appendChild(link);
    }

    import('leaflet').then((leafletModule) => {
      if (isCancelled || !mapContainerRef.current) return;
      const L = (leafletModule as any).default || leafletModule;

      // Fix default marker icon assets
      delete (L.Icon.Default.prototype as any)._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
        iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
        shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
      });

      // Create map instance centered at Gangamai Sugar Mill
      map = L.map(mapContainerRef.current, {
        center: GANGAMAI_COORDS,
        zoom: 12,
        minZoom: 9,
        maxZoom: 19,
        zoomControl: false,
        attributionControl: false,
      });
      mapInstanceRef.current = map;

      // Google Satellite Hybrid tileLayer
      const googleHybrid = L.tileLayer('https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
        maxZoom: 20,
        subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
      });

      // Google Roadmap tileLayer
      const googleRoadmap = L.tileLayer('https://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', {
        maxZoom: 20,
        subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
      });

      // Esri World Imagery fallback
      const esriSat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 19,
      });

      googleHybrid.addTo(map);

      const markersGroup = L.layerGroup().addTo(map);
      const radiusGroup = L.layerGroup().addTo(map);

      layersRef.current = { googleHybrid, googleRoadmap, esriSat, markersGroup, radiusGroup };

      // Add Gangamai Factory Hub Marker
      const factoryIcon = L.divIcon({
        className: 'gangamai-factory-pin',
        html: '<div style="background:#1d5146;color:#f6f8c2;border:2.5px solid #fff;border-radius:50%;width:36px;height:36px;display:flex;align-items:center;justify-content:center;box-shadow:0 0 16px rgba(29,81,70,0.9);font-size:18px;cursor:pointer;">🏢</div>',
        iconSize: [36, 36],
        iconAnchor: [18, 18],
      });

      const factoryMarker = L.marker(GANGAMAI_COORDS, { icon: factoryIcon, zIndexOffset: 1000 }).addTo(map);
      factoryMarker.bindPopup(`
        <div style="font-family:Arial,sans-serif;padding:6px 4px;min-width:210px;">
          <div style="font-size:11px;font-weight:700;letter-spacing:1px;color:#aa7950;margin-bottom:3px;">CENTRAL FACTORY HUB</div>
          <div style="font-size:15px;font-weight:700;color:#183b36;margin-bottom:4px;">Gangamai Sugar Mill</div>
          <div style="font-size:12px;color:#555;margin-bottom:8px;">Shevgaon, Ahmednagar · Weighbridge Active</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;background:#f7f7ed;padding:8px;border-radius:4px;font-size:11px;">
            <div><strong>Crushing Cap:</strong><br/>7,500 TCD</div>
            <div><strong>Command Area:</strong><br/>28,847 Plots</div>
          </div>
        </div>
      `);

      // Add 10km, 20km, 30km concentric command radius circles
      L.circle(GANGAMAI_COORDS, { radius: 10000, color: '#10b981', weight: 1.5, dashArray: '6,6', fillOpacity: 0.04 }).addTo(radiusGroup);
      L.circle(GANGAMAI_COORDS, { radius: 20000, color: '#f59e0b', weight: 1.5, dashArray: '6,6', fillOpacity: 0.02 }).addTo(radiusGroup);
      L.circle(GANGAMAI_COORDS, { radius: 30000, color: '#ef4444', weight: 1.5, dashArray: '6,6', fillOpacity: 0.015 }).addTo(radiusGroup);

      setMapReady(true);
    });

    return () => {
      isCancelled = true;
      if (map) {
        map.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // Update Markers based on activePlots & filter
  useEffect(() => {
    if (!mapReady || !mapInstanceRef.current || !layersRef.current.markersGroup) return;

    import('leaflet').then((leafletModule) => {
      const L = (leafletModule as any).default || leafletModule;
      const markersGroup = layersRef.current.markersGroup;
      markersGroup.clearLayers();

      const filtered = activePlots.filter(p => {
        if (filterPriority === 'ALL') return true;
        if (filterPriority === 'Partial') {
          const hp = p.harvestProgressPct != null ? p.harvestProgressPct : (p.priority === 'Ready' ? 35 : (p.harvestDate ? 25 : 0));
          return hp > 0 && hp < 100;
        }
        return p.priority === filterPriority;
      });

      const displaySubset = filtered.length > 300 ? filtered.slice(0, 300) : filtered;

      for (const p of displaySubset) {
        const coords = getCoordsForPlot(p.village, p.plotNo);
        const isReady = p.priority === 'Ready';
        const isReview = p.priority === 'Review';
        const harvestPct = p.harvestProgressPct != null ? p.harvestProgressPct : (isReady ? 35 : (p.harvestDate ? 25 : 0));
        const isPartial = harvestPct > 0 && harvestPct < 100;
        const color = isPartial ? '#f59e0b' : isReady ? '#10b981' : isReview ? '#f59e0b' : '#ef4444';
        const statusLabel = isPartial ? `PARTIAL HARVEST (${harvestPct}% CUT)` : isReady ? 'READY FOR CUTTING' : isReview ? 'HARVEST REVIEW' : 'HOLD / VEGETATIVE';
        const yieldTons = Number((72 + ((p.ndvi ?? 0.75) * 32) + (p.caneType === 'Adsali' ? 18 : 6)).toFixed(1));
        const initialTons = Number((p.area * yieldTons).toFixed(1));
        const remainingTons = Number(Math.max(0, initialTons * (1 - harvestPct / 100)).toFixed(1));
        const trolliesLeft = Math.max(0, Math.ceil(remainingTons / 12));

        const customPin = L.divIcon({
          className: 'plot-pin',
          html: `<div style="background:${color};width:14px;height:14px;border-radius:50%;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.4);cursor:pointer;transition:transform 0.2s;" title="${p.plotNo} - ${p.village}"></div>`,
          iconSize: [14, 14],
          iconAnchor: [7, 7],
        });

        const marker = L.marker(coords, { icon: customPin });
        
        const popupHtml = `
          <div style="font-family:Arial,sans-serif;padding:6px;min-width:230px;line-height:1.4;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
              <span style="font-weight:700;font-size:14px;color:#183b36;">${p.plotNo}</span>
              <span style="background:${color}22;color:${color};font-weight:700;font-size:10px;padding:2px 6px;border-radius:3px;border:1px solid ${color}44;">${statusLabel}</span>
            </div>
            <div style="font-size:12px;color:#666;margin-bottom:8px;">📍 ${p.village} · Gangamai Command</div>
            
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;background:#f9fafb;padding:8px;border-radius:4px;font-size:11px;margin-bottom:8px;border:1px solid #e5e7eb;">
              <div><span style="color:#6b7280;">Variety:</span><br/><strong>${p.variety}</strong></div>
              <div><span style="color:#6b7280;">Cane Type:</span><br/><strong>${p.caneType}</strong></div>
              <div><span style="color:#6b7280;">Area:</span><br/><strong>${p.area} ha</strong> (${(p.area * 2.471).toFixed(1)} ac)</div>
              <div><span style="color:#6b7280;">NDVI Vigor:</span><br/><strong>${p.ndvi ?? '0.75'}</strong></div>
            </div>

            <div style="background:#ecfdf5;border:1px solid #a7f3d0;padding:6px 8px;borderRadius:4px;font-size:11px;margin-bottom:8px;">
              <div style="display:flex;justify-content:space-between;color:#065f46;font-weight:700;">
                <span>🌾 Standing on Field:</span>
                <span>${remainingTons} MT</span>
              </div>
              <div style="display:flex;justify-content:space-between;color:#047857;font-size:10px;margin-top:2px;">
                <span>Harvest: ${harvestPct}% Cut (~${trolliesLeft} Trollies Left)</span>
                <span style="color:#0284c7;font-weight:600;">🛰️ 1–2d Multi-Sat</span>
              </div>
            </div>

            <div style="font-size:10px;color:#6b7280;display:flex;justify-content:space-between;border-top:1px solid #eee;padding-top:6px;">
              <span>Planting: ${p.plantingDate || '2025-07-20'}</span>
              <span>Cloud: ${p.cloud ?? 5}%</span>
            </div>
            <button 
              id="viz-btn-${p.plotNo}" 
              style="margin-top:8px;width:100%;background:#1d5146;color:#fff;border:none;padding:6px;border-radius:4px;font-size:11px;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:5px;"
            >
              👁️ Open Plot Biophysical Dossier
            </button>
          </div>
        `;

        marker.bindPopup(popupHtml);
        marker.on('popupopen', () => {
          const btn = document.getElementById(`viz-btn-${p.plotNo}`);
          if (btn && onSelectPlot) {
            btn.onclick = (e) => {
              e.preventDefault();
              onSelectPlot(p);
            };
          }
        });
        marker.on('click', () => setSelectedPlot(p));
        marker.addTo(markersGroup);
      }
    });
  }, [activePlots, filterPriority, mapReady]);

  function switchMapType(type: 'hybrid' | 'roadmap') {
    if (!mapReady || !mapInstanceRef.current || !layersRef.current.googleHybrid) return;
    const { googleHybrid, googleRoadmap } = layersRef.current;
    setMapType(type);
    if (type === 'hybrid') {
      mapInstanceRef.current.removeLayer(googleRoadmap);
      mapInstanceRef.current.addLayer(googleHybrid);
    } else {
      mapInstanceRef.current.removeLayer(googleHybrid);
      mapInstanceRef.current.addLayer(googleRoadmap);
    }
  }

  function recenterMill() {
    if (!mapReady || !mapInstanceRef.current) return;
    mapInstanceRef.current.flyTo(GANGAMAI_COORDS, 12, { duration: 1.2 });
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!searchQuery.trim() || !mapReady || !mapInstanceRef.current) return;
    const query = searchQuery.trim().toLowerCase();

    const matchedPlot = activePlots.find(p => p.plotNo.toLowerCase().includes(query));
    if (matchedPlot) {
      const coords = getCoordsForPlot(matchedPlot.village, matchedPlot.plotNo);
      mapInstanceRef.current.flyTo(coords, 16, { duration: 1.5 });
      setSelectedPlot(matchedPlot);
      return;
    }

    const matchedVillage = Object.keys(VILLAGE_CENTROIDS).find(v => v.includes(query));
    if (matchedVillage) {
      const coords = VILLAGE_CENTROIDS[matchedVillage];
      mapInstanceRef.current.flyTo(coords, 14, { duration: 1.5 });
      return;
    }
  }

  function zoomIn() {
    if (mapInstanceRef.current) mapInstanceRef.current.zoomIn();
  }
  function zoomOut() {
    if (mapInstanceRef.current) mapInstanceRef.current.zoomOut();
  }

  return (
    <div 
      className={`google-radar-container ${className || ''}`} 
      style={{
        position: 'relative', 
        width: '100%', 
        height: isFullscreen ? '100vh' : '100%',
        minHeight: isFullscreen ? '100vh' : '380px',
        borderRadius: isFullscreen ? '0' : '8px',
        overflow: 'hidden',
        background: '#151912',
        boxShadow: '0 8px 30px rgba(0,0,0,0.12)',
        zIndex: isFullscreen ? 99999 : 1,
        ...(isFullscreen ? { position: 'fixed', top: 0, left: 0, right: 0, bottom: 0 } : {})
      }}
    >
      {/* Search Bar - Google Maps Style */}
      <form 
        onSubmit={handleSearch} 
        style={{
          position: 'absolute',
          top: '12px',
          left: '12px',
          right: '12px',
          maxWidth: '360px',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          background: '#fff',
          borderRadius: '8px',
          boxShadow: '0 2px 10px rgba(0,0,0,0.25)',
          padding: '4px 10px',
        }}
      >
        <span style={{ fontSize: '14px', color: '#6b7280', marginRight: '8px' }}>🔍</span>
        <input 
          type="text" 
          placeholder="Search village (e.g. Shevgaon, Majaleshahar) or Plot..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{
            flex: 1,
            border: 'none',
            outline: 'none',
            fontSize: '12px',
            color: '#1f2937',
            background: 'transparent',
            padding: '6px 0',
          }}
        />
        {searchQuery && (
          <button 
            type="button" 
            onClick={() => setSearchQuery('')} 
            style={{ border: 'none', background: 'none', color: '#9ca3af', cursor: 'pointer', padding: '4px' }}
          >
            ✕
          </button>
        )}
      </form>

      {/* Layer & Filter Pills */}
      <div 
        style={{
          position: 'absolute',
          top: '60px',
          left: '12px',
          zIndex: 1000,
          display: 'flex',
          flexWrap: 'wrap',
          gap: '6px',
        }}
      >
        <button
          type="button"
          onClick={() => switchMapType('hybrid')}
          style={{
            border: 'none',
            padding: '5px 10px',
            fontSize: '11px',
            fontWeight: 600,
            borderRadius: '16px',
            cursor: 'pointer',
            background: mapType === 'hybrid' ? '#1d5146' : 'rgba(255,255,255,0.92)',
            color: mapType === 'hybrid' ? '#fff' : '#374151',
            boxShadow: '0 2px 6px rgba(0,0,0,0.18)',
          }}
        >
          🛰️ Satellite
        </button>
        <button
          type="button"
          onClick={() => switchMapType('roadmap')}
          style={{
            border: 'none',
            padding: '5px 10px',
            fontSize: '11px',
            fontWeight: 600,
            borderRadius: '16px',
            cursor: 'pointer',
            background: mapType === 'roadmap' ? '#1d5146' : 'rgba(255,255,255,0.92)',
            color: mapType === 'roadmap' ? '#fff' : '#374151',
            boxShadow: '0 2px 6px rgba(0,0,0,0.18)',
          }}
        >
          🗺️ Roadmap
        </button>
        <button
          type="button"
          onClick={() => setFilterPriority(p => p === 'Ready' ? 'ALL' : 'Ready')}
          style={{
            border: 'none',
            padding: '5px 10px',
            fontSize: '11px',
            fontWeight: 600,
            borderRadius: '16px',
            cursor: 'pointer',
            background: filterPriority === 'Ready' ? '#10b981' : 'rgba(255,255,255,0.92)',
            color: filterPriority === 'Ready' ? '#fff' : '#374151',
            boxShadow: '0 2px 6px rgba(0,0,0,0.18)',
          }}
        >
          🟢 {filterPriority === 'Ready' ? 'Ready Only' : 'Filter Ready'}
        </button>
        <button
          type="button"
          onClick={() => setFilterPriority(p => p === 'Partial' ? 'ALL' : 'Partial')}
          style={{
            border: 'none',
            padding: '5px 10px',
            fontSize: '11px',
            fontWeight: 600,
            borderRadius: '16px',
            cursor: 'pointer',
            background: filterPriority === 'Partial' ? '#f59e0b' : 'rgba(255,255,255,0.92)',
            color: filterPriority === 'Partial' ? '#fff' : '#374151',
            boxShadow: '0 2px 6px rgba(0,0,0,0.18)',
          }}
        >
          🌾 {filterPriority === 'Partial' ? 'Partial Harvest' : 'Partial Cut (1-2d)'}
        </button>
      </div>

      {/* Google Maps Controls (Bottom Right) */}
      <div 
        style={{
          position: 'absolute',
          right: '12px',
          bottom: '45px',
          zIndex: 1000,
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', background: '#fff', borderRadius: '4px', boxShadow: '0 2px 8px rgba(0,0,0,0.2)', overflow: 'hidden' }}>
          <button 
            type="button" 
            onClick={zoomIn} 
            title="Zoom In"
            style={{ width: '34px', height: '34px', border: 'none', background: '#fff', fontSize: '18px', fontWeight: 'bold', color: '#444', cursor: 'pointer', borderBottom: '1px solid #eee' }}
          >
            +
          </button>
          <button 
            type="button" 
            onClick={zoomOut} 
            title="Zoom Out"
            style={{ width: '34px', height: '34px', border: 'none', background: '#fff', fontSize: '18px', fontWeight: 'bold', color: '#444', cursor: 'pointer' }}
          >
            −
          </button>
        </div>

        <button 
          type="button" 
          onClick={recenterMill} 
          title="Center Gangamai Sugar Mill"
          style={{
            width: '34px',
            height: '34px',
            borderRadius: '4px',
            border: 'none',
            background: '#fff',
            boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
            fontSize: '16px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#1d5146'
          }}
        >
          🎯
        </button>

        <button 
          type="button" 
          onClick={() => setIsFullscreen(!isFullscreen)} 
          title={isFullscreen ? "Exit Fullscreen" : "Fullscreen Radar"}
          style={{
            width: '34px',
            height: '34px',
            borderRadius: '4px',
            border: 'none',
            background: '#fff',
            boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
            fontSize: '14px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#444'
          }}
        >
          {isFullscreen ? '✖' : '⛶'}
        </button>
      </div>

      {/* Floating Status Footer Bar */}
      <div 
        style={{
          position: 'absolute',
          left: '12px',
          bottom: '12px',
          zIndex: 1000,
          background: 'rgba(255,255,255,0.95)',
          backdropFilter: 'blur(4px)',
          borderRadius: '4px',
          padding: '5px 12px',
          fontSize: '11px',
          color: '#1f2937',
          boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981' }} />
          <strong>{activePlots.filter(p => p.priority === 'Ready').length}</strong> Ready
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#f59e0b' }} />
          <strong>{activePlots.filter(p => p.priority === 'Review').length}</strong> Review
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ef4444' }} />
          <strong>{activePlots.filter(p => p.priority === 'Hold').length}</strong> Hold
        </span>
        <span style={{ borderLeft: '1px solid #d1d5db', paddingLeft: '10px', color: '#6b7280', fontSize: '10px' }}>
          🏢 Gangamai Mill Center · 19.348°N 75.228°E
        </span>
      </div>

      {/* Leaflet Map Mount Container */}
      <div ref={mapContainerRef} style={{ width: '100%', height: '100%', minHeight: isFullscreen ? '100vh' : '380px' }} />
    </div>
  );
}
