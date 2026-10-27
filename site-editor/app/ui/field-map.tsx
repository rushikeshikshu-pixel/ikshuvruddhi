'use client';

import React, { useEffect, useRef, useState, useMemo } from 'react';
import type { Plot } from '../types';
import { useLanguage } from './language';
import {estimatedRecovery} from '../../lib/recovery';

export interface FieldMapProps {
  plots?: Plot[];
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

type BoundaryFeature = { plotId: string; geometry: any };
const escapeHtml = (value: unknown) => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char] || char));

export default function FieldMap({ plots, samples, interactive = true, className, onSelectPlot }: FieldMapProps) {
  const { language, t, format } = useLanguage();
  const [mapPage,setMapPage]=useState(0);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const featureLayersRef = useRef<Map<string, any>>(new Map());
  const initialFitRef = useRef(false);
  const layersRef = useRef<{ googleHybrid?: any; googleRoadmap?: any; esriSat?: any; markersGroup?: any; radiusGroup?: any }>({});
  
  const [mapReady, setMapReady] = useState(false);
  const [mapType, setMapType] = useState<'hybrid' | 'roadmap'>('hybrid');
  const [layerMode, setLayerMode] = useState<'harvest' | 'canopy' | 'priority'>('harvest');
  const [filterPriority, setFilterPriority] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [selectedPlot, setSelectedPlot] = useState<any>(null);
  const [boundaryFeatures, setBoundaryFeatures] = useState<Record<string, BoundaryFeature['geometry']>>({});
  const [boundaryCount, setBoundaryCount] = useState(0);
  const [boundaryLoading, setBoundaryLoading] = useState(false);

  const activePlots = useMemo(() => plots || [], [plots]);
  const visiblePlots = useMemo(() => {
    const filtered = activePlots.filter(plot => filterPriority === 'ALL' || plot.priority === filterPriority);
    const start=Math.min(mapPage,Math.max(0,Math.ceil(filtered.length/300)-1))*300;
    const subset = filtered.slice(start, start+300);
    if (selectedPlot && !subset.some(plot => plot.id === selectedPlot.id) && (filterPriority === 'ALL' || selectedPlot.priority === filterPriority)) subset.push(selectedPlot);
    return subset;
  }, [activePlots, filterPriority, selectedPlot,mapPage]);
  const visiblePolygonCount = visiblePlots.filter(plot => plot.id && boundaryFeatures[plot.id]).length;

  useEffect(() => {
    let cancelled = false;
    const ids = visiblePlots.map(plot => plot.id).filter((id): id is string => Boolean(id));
    if (!ids.length) { setBoundaryFeatures({}); setBoundaryCount(0); return; }
    setBoundaryLoading(true);
    fetch(`/api/satellite?view=map&ids=${encodeURIComponent(ids.join(','))}`, { cache: 'no-store' })
      .then(async response => {
        const result = await response.json() as { boundaryCount?: number; boundaries?: BoundaryFeature[] };
        if (!response.ok) throw new Error('Polygon layer is unavailable.');
        if (cancelled) return;
        setBoundaryCount(Number(result.boundaryCount || 0));
        setBoundaryFeatures(Object.fromEntries((result.boundaries || []).map(boundary => [boundary.plotId, boundary.geometry])));
      })
      .catch(() => { if (!cancelled) { setBoundaryFeatures({}); setBoundaryCount(0); } })
      .finally(() => { if (!cancelled) setBoundaryLoading(false); });
    return () => { cancelled = true; };
  }, [visiblePlots]);

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
      const googleHybrid = L.tileLayer(`https://{s}.google.com/vt/lyrs=y&hl=${language}&x={x}&y={y}&z={z}`, {
        maxZoom: 20,
        subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
      });

      // Google Roadmap tileLayer
      const googleRoadmap = L.tileLayer(`https://{s}.google.com/vt/lyrs=m&hl=${language}&x={x}&y={y}&z={z}`, {
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
          <div style="font-size:11px;font-weight:700;letter-spacing:1px;color:#aa7950;margin-bottom:3px;">${t('FACTORY HUB','कारखाना केंद्र')}</div>
          <div style="font-size:15px;font-weight:700;color:#183b36;margin-bottom:4px;">${t('Gangamai Sugar Mill','गंगामाई साखर कारखाना')}</div>
          <div style="font-size:12px;color:#555;margin-bottom:8px;">${t('Shevgaon, Ahmednagar','शेवगाव, अहिल्यानगर')}</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;background:#f7f7ed;padding:8px;border-radius:4px;font-size:11px;">
            <div><strong>${t('Dataset','डेटासेट')}:</strong><br/>${escapeHtml(activePlots[0]?.sourceTimestamp||'—')}</div>
            <div><strong>${t('Active plots','सक्रिय प्लॉट')}:</strong><br/>${format(activePlots.length,0)}</div>
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
        initialFitRef.current=false;
        setMapReady(false);
      }
    };
  }, [language,activePlots.length]);

  // Draw only saved plot geometries. Approximate village offsets are not plot boundaries.
  useEffect(() => {
    if (!mapReady || !mapInstanceRef.current || !layersRef.current.markersGroup) return;

    import('leaflet').then((leafletModule) => {
      const L = (leafletModule as any).default || leafletModule;
      const polygonLayer = layersRef.current.markersGroup;
      polygonLayer.clearLayers();
      featureLayersRef.current.clear();
      const bounds = L.latLngBounds([]);

      for (const p of visiblePlots) {
        const geometry = p.id ? boundaryFeatures[p.id] : undefined;
        if (!geometry) continue;
        let color = '#10b981';
        let fillOpacity = 0.28;
        let weight = 1.5;
        let statusLabel = '';

        const isHarvested = p.tonnage === 0 || p.priority === 'Harvested' || (p.harvestTier && p.harvestTier.includes('Harvested'));
        const ndviVal = Number(p.ndvi ?? 0);

        if (layerMode === 'harvest') {
          if (isHarvested) {
            color = '#dc2626'; // Red - 100% cut
            fillOpacity = 0.70;
            weight = 2;
            statusLabel = t('HARVESTED (0 MT)','तोडणी पूर्ण (० टन)');
          } else if (p.harvestTier && p.harvestTier.includes('Tier 1')) {
            color = '#ea580c'; // Orange - Ready to cut
            fillOpacity = 0.55;
            weight = 1.8;
            statusLabel = t('TIER 1 (HARVEST NOW)','तोडणीस योग्य (टियर १)');
          } else if (p.harvestTier && p.harvestTier.includes('Tier 2')) {
            color = '#f59e0b'; // Amber - Mid-maturity
            fillOpacity = 0.45;
            weight = 1.5;
            statusLabel = t('TIER 2 (MID-MATURITY)','मध्यम परिपक्व (२-३ आठवडे)');
          } else {
            color = '#10b981'; // Green - Standing cane
            fillOpacity = 0.35;
            weight = 1.2;
            statusLabel = t('TIER 3 (STANDING CANE)','उभा ऊस (४-६ आठवडे)');
          }
        } else if (layerMode === 'canopy') {
          if (ndviVal >= 0.60) {
            color = '#047857'; // Lush Dark Green
            fillOpacity = 0.68;
            weight = 1.5;
            statusLabel = t('DENSE CANOPY (NDVI > 0.60)','दाट ऊस छत्र (NDVI > ०.६०)');
          } else if (ndviVal >= 0.45) {
            color = '#10b981'; // Healthy Green
            fillOpacity = 0.50;
            weight = 1.5;
            statusLabel = t('HEALTHY CANOPY (0.45-0.60)','चांगले छत्र (०.४५-०.६०)');
          } else if (ndviVal >= 0.35) {
            color = '#f59e0b'; // Ripening / Low Canopy
            fillOpacity = 0.48;
            weight = 1.5;
            statusLabel = t('SPARSE/RIPENING (0.35-0.45)','विरळ/पिकणारा ऊस');
          } else {
            color = '#dc2626'; // Zero Canopy / Cleared
            fillOpacity = 0.75;
            weight = 2;
            statusLabel = t('ZERO CANOPY (NDVI < 0.35)','शून्य छत्र / तोडलेला ऊस');
          }
        } else {
          // Priority Mode
          const isReady = p.priority === 'Ready';
          const isReview = p.priority === 'Review';
          color = isReady ? '#10b981' : isReview ? '#f59e0b' : '#ef4444';
          fillOpacity = 0.28;
          statusLabel = isReady ? t('MARKED READY','तोडणीस तयार') : isReview ? t('MANUAL REVIEW','व्यवस्थापक पडताळणी') : t('HOLD','थांबवा');
        }

        const safePlotNo = escapeHtml(p.plotNo);
        const safeVillage = escapeHtml(p.village);
        const safeGatNo = escapeHtml(p.gatNo || ('Gat ' + p.plotNo));
        const safeFarmer = escapeHtml(p.farmerName || 'खातेदार शेतकरी');
        const bhulekhUrl = escapeHtml(p.bhulekh712Url || 'https://bhulekh.mahabhumi.gov.in/');

        const popupHtml = `
          <div style="font-family:Arial,sans-serif;padding:6px;min-width:240px;line-height:1.4;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
              <span style="font-weight:700;font-size:14px;color:#183b36;">${safePlotNo}</span>
              <span style="background:${color}22;color:${color};font-weight:700;font-size:10px;padding:2px 6px;border-radius:3px;border:1px solid ${color}44;">${statusLabel}</span>
            </div>
            <div style="font-size:12px;color:#666;margin-bottom:6px;">📍 ${safeVillage} · ${t('supplied survey outline','पुरवलेली सर्वेक्षण सीमा')}</div>
            
            <div style="font-size:11px;color:#065f46;background:#ecfdf5;padding:5px 8px;border-radius:4px;margin-bottom:6px;border:1px solid #a7f3d0;display:flex;justify-content:space-between;align-items:center;">
              <span>📜 <strong>${safeGatNo}</strong> · ${safeFarmer}</span>
              <a href="${bhulekhUrl}" target="_blank" rel="noopener noreferrer" style="color:#047857;text-decoration:none;font-weight:700;font-size:10px;background:#fff;padding:2px 5px;border-radius:3px;border:1px solid #a7f3d0;">७/१२ ↗</a>
            </div>

            ${isHarvested ? `<div style="font-size:11px;background:#fef2f2;padding:4px 8px;border-radius:4px;margin-bottom:6px;border:1px solid #fecaca;color:#b91c1c;font-weight:700;">🔴 ${t('5-Day Satellite Confirmed Harvest: 0.0 MT Standing','उपग्रह पडताळणी: तोडणी पूर्ण (० टन उभा)')}</div>` : ''}

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;background:#f9fafb;padding:8px;border-radius:4px;font-size:11px;margin-bottom:8px;border:1px solid #e5e7eb;">
              <div><span style="color:#6b7280;">${t('Variety','वाण')}:</span><br/><strong>${escapeHtml(p.variety)}</strong></div>
              <div><span style="color:#6b7280;">${t('Cane type','ऊस प्रकार')}:</span><br/><strong>${escapeHtml(p.caneType)}</strong></div>
              <div><span style="color:#6b7280;">${t('Area','क्षेत्र')}:</span><br/><strong>${p.area} ha</strong> (${(p.area * 2.471).toFixed(1)} ac)</div>
              <div><span style="color:#6b7280;">NDVI:</span><br/><strong>${p.ndvi ?? '—'}</strong></div>
            </div>

            <div style="font-size:12px;padding:6px 0;color:#183b36;">${t('Predicted','अंदाजित')} Pol: <strong>${p.predictedPol??'—'}%</strong> · Brix: <strong>${p.predictedBrix??'—'}</strong> · CCS: <strong>${p.predictedCcs??'—'}%</strong><br/>${t('Estimated recovery','अंदाजित साखर उतारा')}: <strong>${format(estimatedRecovery(p.predictedCcs))}%</strong> · CCS × 0.754<br/>${t('Standing tonnage','उभ्या उसाचे वजन')}: <strong>${p.tonnage??'—'} MT</strong></div>
            <div style="font-size:10px;color:#6b7280;display:flex;justify-content:space-between;border-top:1px solid #eee;padding-top:6px;">
              <span>${t('Planting','लागवड')}: ${escapeHtml(p.plantingDate || '—')}</span>
              <span>${t('Cloud','ढग')}: ${p.cloud ?? '—'}${p.cloud == null ? '' : '%'}</span>
            </div>
            <button 
              id="viz-btn-${escapeHtml(p.id)}" 
              style="margin-top:8px;width:100%;background:#1d5146;color:#fff;border:none;padding:6px;border-radius:4px;font-size:11px;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:5px;"
            >
              👁️ ${t('Open 7/12 & plot verification','७/१२ व प्लॉट पडताळणी उघडा')}
            </button>
          </div>
        `;

        const polygon = L.geoJSON(geometry, { style: { color, weight, opacity: 0.95, fillColor: color, fillOpacity } });
        polygon.bindPopup(popupHtml);
        polygon.on('popupopen', () => {
          const btn = document.getElementById(`viz-btn-${p.id}`);
          if (btn && onSelectPlot) {
            btn.onclick = (e) => {
              e.preventDefault();
              onSelectPlot(p);
            };
          }
        });
        polygon.on('click', () => setSelectedPlot(p));
        polygon.addTo(polygonLayer);
        featureLayersRef.current.set(p.id, polygon);
        bounds.extend(polygon.getBounds());
      }

      if (!initialFitRef.current && visiblePolygonCount > 0 && bounds.isValid()) {
        mapInstanceRef.current.fitBounds(bounds, { padding: [24, 24], maxZoom: 13 });
        initialFitRef.current = true;
      }
      if (selectedPlot?.id && featureLayersRef.current.has(selectedPlot.id)) {
        const selectedLayer = featureLayersRef.current.get(selectedPlot.id);
        mapInstanceRef.current.flyToBounds(selectedLayer.getBounds(), { padding: [40, 40], maxZoom: 17, duration: 0.8 });
      }
    });
  }, [visiblePlots, boundaryFeatures, visiblePolygonCount, selectedPlot, mapReady, language, layerMode]);

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

    const matchedPlot = activePlots.find(p => p.plotNo.toLowerCase() === query) || activePlots.find(p => p.plotNo.toLowerCase().includes(query));
    if (matchedPlot) {
      setFilterPriority('ALL');
      setSelectedPlot(matchedPlot);
      return;
    }

    const matchedVillagePlot = activePlots.find(p => p.boundaryAvailable&&p.village.toLowerCase().includes(query)) || activePlots.find(p => p.village.toLowerCase().includes(query));
    if (matchedVillagePlot) { setFilterPriority('ALL'); setSelectedPlot(matchedVillagePlot); }
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
      {interactive&&activePlots.length>0&&<>
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
          placeholder={t('Search any plot number or village…','कोणताही प्लॉट क्रमांक किंवा गाव शोधा…')}
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
          🛰️ {t('Satellite','उपग्रह')}
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
          🗺️ {t('Roadmap','रस्ते नकाशा')}
        </button>

        {/* Heatmap Layer View Modes */}
        <div style={{ display: 'inline-flex', background: 'rgba(255,255,255,0.95)', padding: '2px', borderRadius: '18px', boxShadow: '0 2px 6px rgba(0,0,0,0.18)', gap: '2px' }}>
          <button
            type="button"
            onClick={() => setLayerMode('harvest')}
            title={t('Show harvested vs standing cane heatmap','तोडणी झालेला व उभा ऊस हीटमॅप')}
            style={{
              border: 'none',
              padding: '4px 10px',
              fontSize: '11px',
              fontWeight: 700,
              borderRadius: '16px',
              cursor: 'pointer',
              background: layerMode === 'harvest' ? '#dc2626' : 'transparent',
              color: layerMode === 'harvest' ? '#fff' : '#374151',
              transition: 'all 0.15s ease',
            }}
          >
            🔥 {t('Harvest Heatmap','तोडणी हीटमॅप')}
          </button>
          <button
            type="button"
            onClick={() => setLayerMode('canopy')}
            title={t('Show detected cane canopy density (NDVI)','उपग्रहाधारित कॅनोपी घनता (NDVI)')}
            style={{
              border: 'none',
              padding: '4px 10px',
              fontSize: '11px',
              fontWeight: 700,
              borderRadius: '16px',
              cursor: 'pointer',
              background: layerMode === 'canopy' ? '#047857' : 'transparent',
              color: layerMode === 'canopy' ? '#fff' : '#374151',
              transition: 'all 0.15s ease',
            }}
          >
            🌿 {t('Canopy Density','कॅनोपी घनता')}
          </button>
          <button
            type="button"
            onClick={() => setLayerMode('priority')}
            title={t('Show operational priority','कारखाना नियोजन प्राधान्य')}
            style={{
              border: 'none',
              padding: '4px 10px',
              fontSize: '11px',
              fontWeight: 700,
              borderRadius: '16px',
              cursor: 'pointer',
              background: layerMode === 'priority' ? '#1d5146' : 'transparent',
              color: layerMode === 'priority' ? '#fff' : '#374151',
              transition: 'all 0.15s ease',
            }}
          >
            📋 {t('Priority','प्राधान्य')}
          </button>
        </div>

        <button
          type="button"
          onClick={() => {setFilterPriority(p => p === 'Ready' ? 'ALL' : 'Ready');setMapPage(0)}}
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
          🟢 {filterPriority === 'Ready' ? t('Ready only','फक्त तयार') : t('Filter ready','तयार प्लॉट')}
        </button>
      </div>

      <div style={{ position: 'absolute', top: '60px', right: '12px', zIndex: 1000, maxWidth: 'min(360px, 48vw)', background: 'rgba(255,255,255,0.96)', borderRadius: '8px', padding: '7px 10px', boxShadow: '0 2px 8px rgba(0,0,0,0.18)', color: '#374151', fontSize: '11px' }}>
        {boundaryLoading ? t('Loading supplied plot outlines…','पुरवलेल्या प्लॉट सीमा लोड होत आहेत…') : <><strong>{format(visiblePolygonCount,0)}</strong> {t('outlines shown','सीमा दाखवल्या')} · {format(boundaryCount,0)} / {format(activePlots.length,0)} {t('outlines available','सीमा उपलब्ध')}<br/>{t('Search all plots, or change layer page.','सर्व प्लॉट शोधा किंवा नकाशाचे पृष्ठ बदला.')}{selectedPlot&&!boundaryFeatures[selectedPlot.id]&&!boundaryLoading&&<div style={{marginTop:6,color:'#8a541d'}}>{t('No source outline for plot','या प्लॉटची मूळ सीमा नाही')}: {selectedPlot.plotNo} <button type="button" onClick={()=>onSelectPlot?.(selectedPlot)}>{t('View record','नोंद पहा')}</button></div>}<div style={{display:'flex',gap:8,alignItems:'center',marginTop:5}}><button type="button" disabled={!mapPage} onClick={()=>{setMapPage(Math.max(0,mapPage-1));setSelectedPlot(null)}}>{t('Previous','मागील')}</button><span>{mapPage+1} / {Math.max(1,Math.ceil(activePlots.filter(p=>filterPriority==='ALL'||p.priority===filterPriority).length/300))}</span><button type="button" disabled={(mapPage+1)*300>=activePlots.filter(p=>filterPriority==='ALL'||p.priority===filterPriority).length} onClick={()=>{setMapPage(mapPage+1);setSelectedPlot(null)}}>{t('Next','पुढील')}</button></div></>}

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
            title={t('Zoom in','जवळून पहा')}
            style={{ width: '34px', height: '34px', border: 'none', background: '#fff', fontSize: '18px', fontWeight: 'bold', color: '#444', cursor: 'pointer', borderBottom: '1px solid #eee' }}
          >
            +
          </button>
          <button 
            type="button" 
            onClick={zoomOut} 
            title={t('Zoom out','दूरून पहा')}
            style={{ width: '34px', height: '34px', border: 'none', background: '#fff', fontSize: '18px', fontWeight: 'bold', color: '#444', cursor: 'pointer' }}
          >
            −
          </button>
        </div>

        <button 
          type="button" 
          onClick={recenterMill} 
          title={t('Center Gangamai mill','गंगामाई कारखान्यावर जा')}
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
          title={isFullscreen ? t('Exit fullscreen','पूर्ण स्क्रीन बंद करा') : t('Fullscreen map','पूर्ण स्क्रीन नकाशा')}
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
          flexWrap: 'wrap',
          maxWidth: 'calc(100% - 120px)',
        }}
      >
        {layerMode === 'harvest' ? (
          <>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#dc2626' }} />
              <strong>{activePlots.filter(p => p.tonnage === 0 || p.priority === 'Harvested' || (p.harvestTier && p.harvestTier.includes('Harvested'))).length}</strong> {t('Harvested (0 MT)','तोडणी पूर्ण (० टन)')}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ea580c' }} />
              <strong>{activePlots.filter(p => p.harvestTier && p.harvestTier.includes('Tier 1')).length}</strong> {t('Tier 1 (Cut Now)','टियर १ (तयार)')}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#f59e0b' }} />
              <strong>{activePlots.filter(p => p.harvestTier && p.harvestTier.includes('Tier 2')).length}</strong> {t('Tier 2 (2-3 Wks)','टियर २ (२-३ आठवडे)')}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981' }} />
              <strong>{activePlots.filter(p => !(p.tonnage === 0 || p.priority === 'Harvested' || (p.harvestTier && p.harvestTier.includes('Harvested'))) && !(p.harvestTier && (p.harvestTier.includes('Tier 1') || p.harvestTier.includes('Tier 2')))).length}</strong> {t('Standing Cane','उभा ऊस')}
            </span>
          </>
        ) : layerMode === 'canopy' ? (
          <>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#047857' }} />
              <strong>{activePlots.filter(p => Number(p.ndvi ?? 0) >= 0.60).length}</strong> {t('Dense (>0.60)','दाट छत्र')}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981' }} />
              <strong>{activePlots.filter(p => Number(p.ndvi ?? 0) >= 0.45 && Number(p.ndvi ?? 0) < 0.60).length}</strong> {t('Healthy (0.45-0.60)','चांगले')}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#f59e0b' }} />
              <strong>{activePlots.filter(p => Number(p.ndvi ?? 0) >= 0.35 && Number(p.ndvi ?? 0) < 0.45).length}</strong> {t('Sparse (0.35-0.45)','विरळ')}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#dc2626' }} />
              <strong>{activePlots.filter(p => Number(p.ndvi ?? 0) < 0.35).length}</strong> {t('Zero/Cut (<0.35)','शून्य/कापलेला')}
            </span>
          </>
        ) : (
          <>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981' }} />
              <strong>{activePlots.filter(p => p.priority === 'Ready').length}</strong> {t('Ready','तयार')}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#f59e0b' }} />
              <strong>{activePlots.filter(p => p.priority === 'Review').length}</strong> {t('Review','पडताळणी')}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ef4444' }} />
              <strong>{activePlots.filter(p => p.priority === 'Hold').length}</strong> {t('Hold','थांबवा')}
            </span>
          </>
        )}
        <span style={{ borderLeft: '1px solid #d1d5db', paddingLeft: '10px', color: '#6b7280', fontSize: '10px' }}>
          🏢 {t('Gangamai mill · 7/12 Cadastral Boundaries','गंगामाई कारखाना · ७/१२ भूकर सीमा')}
        </span>
      </div>

      </>}
      {/* Leaflet Map Mount Container */}
      <div ref={mapContainerRef} style={{ width: '100%', height: '100%', minHeight: isFullscreen ? '100vh' : '380px' }} />
    </div>
  );
}
