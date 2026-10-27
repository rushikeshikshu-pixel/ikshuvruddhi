'use client';

import { useEffect, useMemo, useState } from 'react';
import { Activity, AlertCircle, ArrowRight, Cloud, Download, LoaderCircle, Satellite, ShieldCheck, Sprout, Upload } from 'lucide-react';
import type { Plot } from '../types';
import { parseCSV } from './csv';
import {useLanguage} from './language';

type Scene = { id: string; date: string; datetime: string; sensor: 'S1' | 'S2'; cloud: number | null; orbit: number | null; direction: string | null };
type Observation = Record<string, any>;
export type SatellitePlot = Pick<Plot,'id'|'plotNo'|'village'>;
type Meta = { configured: boolean; model: { version: string; status: string; trainingSamples: number; trainingGroups: number; validation: string; features: string[]; featureCount: number; laterDateValidation: string; predictionNote:string; ccsDefinition:string; metrics: Record<string, { model: { MAE: number; RMSE: number; R2: number }; mean_baseline: { MAE: number }; laterDate: {MAE:number;R2:number}; withinOnePointPct:number }> }; boundaries: { plotId: string; hash: string }[]; observations?: Observation[] };

export default function SatellitePanel({ plots }: { plots: SatellitePlot[] }) {
  const {t,format,date}=useLanguage();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [plotId, setPlotId] = useState('');
  const [plotSearch,setPlotSearch]=useState('');
  const [boundaryProgress,setBoundaryProgress]=useState('');
  const [sensor, setSensor] = useState<'S2' | 'S1'>('S2');
  const [acquisitionDate, setAcquisitionDate] = useState('');
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [selectedScene, setSelectedScene] = useState<Scene | null>(null);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [file, setFile] = useState('');

  const selectedPlot = plots.find(plot => plot.id === plotId);
  const filteredPlots=plots.filter(plot=>[plot.plotNo,plot.village].some(value=>value.toLowerCase().includes(plotSearch.toLowerCase())));
  const plotOptions=filteredPlots.slice(0,100);if(selectedPlot&&!plotOptions.some(plot=>plot.id===selectedPlot.id))plotOptions.unshift(selectedPlot);
  const boundaryIds = useMemo(() => new Set(meta?.boundaries.map(boundary => boundary.plotId) || []), [meta]);

  async function request(path: string, init?: RequestInit) {
    const response = await fetch(path, { ...init, cache: 'no-store' });
    const body = await response.json() as Record<string, any>;
    if (!response.ok) throw new Error(body.error || `Satellite request failed (${response.status})`);
    return body;
  }

  async function refresh(plot = plotId) {
    const summary = await request('/api/satellite') as Meta;
    setMeta(summary);
    if (plot) {
      const detail = await request(`/api/satellite?plotId=${encodeURIComponent(plot)}`) as Meta;
      setObservations(detail.observations || []);
    }
  }

  useEffect(() => { void refresh('').catch(error => setError((error as Error).message)); }, []);
  useEffect(() => {
    setScenes([]); setSelectedScene(null); setObservations([]); setError('');
    if (plotId) void refresh(plotId).catch(error => setError((error as Error).message));
  }, [plotId]);

  async function uploadBoundaries(input: File) {
    setBusy(true); setError(''); setNotice(''); setFile(input.name);
    try {
      if (input.size > 20_000_000) throw new Error('Boundary file must be under 20 MB.');
      const text = await input.text();
      let features: { plotNo: string; geometry: unknown }[];
      if (/\.csv$/i.test(input.name)) {
        const rows = parseCSV(text);
        features = rows.map((row, i) => {
          const plotNo = String(row.plotNo ?? row['Plot No'] ?? row.plot_no ?? '').trim();
          const outline = String(row['Plot Area Lat Long'] ?? row.boundary ?? row.geometry ?? '').trim();
          if (!plotNo || !outline) throw new Error(`CSV row ${i + 2} needs Plot No and Plot Area Lat Long columns.`);
          const ring = outline.split('#').map(pair => pair.trim().split(',').map(Number));
          if (ring.some(pair => pair.length !== 2 || !Number.isFinite(pair[0]) || !Number.isFinite(pair[1]) || Math.abs(pair[0]) > 90 || Math.abs(pair[1]) > 180)) throw new Error(`CSV row ${i + 2} has invalid latitude/longitude coordinates.`);
          const coordinates = ring.map(([lat, lon]) => [lon, lat]);
          if (coordinates.length < 3) throw new Error(`CSV row ${i + 2} has fewer than three boundary points.`);
          const first = coordinates[0], last = coordinates[coordinates.length - 1];
          if (first[0] !== last[0] || first[1] !== last[1]) coordinates.push([...first]);
          return { plotNo, geometry: { type: 'Polygon', coordinates: [coordinates] } };
        });
      } else {
        const source = JSON.parse(text);
        if (source.type !== 'FeatureCollection' || !Array.isArray(source.features)) throw new Error('Choose a GeoJSON FeatureCollection or a CSV exported from the mill workbook.');
        features = source.features.map((feature: any, i: number) => {
          const properties = feature.properties || {};
          const plotNo = String(properties.plotNo ?? properties.plot_no ?? properties['Plot No'] ?? properties.plot ?? '').trim();
          if (!plotNo) throw new Error(`Feature ${i + 1} is missing a plotNo property.`);
          return { plotNo, geometry: feature.geometry };
        });
      }
      if (!features.length) throw new Error('The GeoJSON file contains no field boundaries.');
      if (new Set(features.map(feature => feature.plotNo)).size !== features.length) throw new Error('The file contains a plot number more than once.');
      for (let i = 0; i < features.length; i += 500) {
        const batch = features.slice(i, i + 500);
        setBoundaryProgress(`${(i + batch.length).toLocaleString()} / ${features.length.toLocaleString()} boundaries saved…`);
        await request('/api/satellite', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'boundaryImport', plotId: plots[0]?.id, features: batch }) });
      }
      setNotice(`${features.length} plot boundaries saved to this private workspace.`);
      await refresh(plotId);
    } catch (error) { setError((error as Error).message); }
    finally { setBusy(false); setBoundaryProgress(''); }
  }

  async function searchScenes(event: React.FormEvent) {
    event.preventDefault(); if (!selectedPlot || !meta?.configured) return;
    setBusy(true); setError(''); setNotice(''); setScenes([]); setSelectedScene(null);
    try {
      const result = await request('/api/satellite', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'catalogue', plotId, sensor, date: acquisitionDate || undefined }) });
      setScenes(result.scenes || []);
      if (!result.scenes?.length) setNotice(t('No acquisition matched this field and date. Try another date or sensor.','या शेतासाठी व तारखेसाठी प्रतिमा मिळाली नाही. दुसरी तारीख किंवा सेन्सर निवडा.'));
    } catch (error) { setError((error as Error).message); }
    finally { setBusy(false); setBoundaryProgress(''); }
  }

  async function processScene(scene: Scene) {
    if (!selectedPlot) return;
    setBusy(true); setError(''); setNotice(''); setSelectedScene(scene);
    try {
      const result = await request('/api/satellite', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'measure', plotId, sensor: scene.sensor, sceneId: scene.id, date: scene.date, datetime: scene.datetime, cloud: scene.cloud, orbit: scene.orbit, direction: scene.direction }) });
      setObservations(prev => [result.observation, ...prev.filter(item => !(item.date === result.observation.date && item.sensor === result.observation.sensor))]);
      setNotice(result.cached ? t('Showing the saved observation.','जतन केलेले निरीक्षण दाखवत आहे.') : t('Observation and acquisition metadata saved.','निरीक्षण व प्रतिमेची माहिती जतन केली.'));
      await refresh(plotId);
    } catch (error) { setError((error as Error).message); }
    finally { setBusy(false); setBoundaryProgress(''); }
  }

  async function downloadTemplate() {
    const sample = { type: 'FeatureCollection', features: [{ type: 'Feature', properties: { plotNo: 'PLOT-001' }, geometry: { type: 'Polygon', coordinates: [[[75.1, 19.3], [75.1002, 19.3], [75.1002, 19.3002], [75.1, 19.3002], [75.1, 19.3]]] } }] };
    const url = URL.createObjectURL(new Blob([JSON.stringify(sample, null, 2)], { type: 'application/geo+json' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'ikshu-boundary-template.geojson'; anchor.click(); URL.revokeObjectURL(url);
  }

  const fmt = (v: unknown, digits = 3) => typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—';

  return <>
    <section className="panel satellite-intro"><div className="panel-header"><div><h2>{t('Satellite observations','उपग्रह निरीक्षणे')}</h2><p>{t('Optical and radar observations for the active register.','सक्रिय नोंदवहीसाठी ऑप्टिकल व रडार निरीक्षणे.')}</p></div><Satellite size={20}/></div><div className="satellite-intro-body">
      {meta&&<p>{format(meta.boundaries.length,0)} / {format(plots.length,0)} {t('plots have connected outlines.','प्लॉटच्या सीमा जोडलेल्या आहेत.')} {format(Math.max(0,plots.length-meta.boundaries.length),0)} {t('plots need an outline.','प्लॉटसाठी सीमा आवश्यक आहे.')}</p>}
      <p>{t('Supplied register outlines are available automatically. Search recent acquisitions or select a date. Sentinel-2 uses optical imagery; Sentinel-1 provides radar observations through cloud.','नोंदवहीतील पुरवलेल्या सीमा आपोआप उपलब्ध आहेत. अलीकडील प्रतिमा शोधा किंवा तारीख निवडा. सेंटिनेल-२ ऑप्टिकल प्रतिमा वापरतो; सेंटिनेल-१ ढगांमधून रडार निरीक्षणे पुरवतो.')}</p>
      <div className="notice info"><ShieldCheck size={18}/><span>{t('An imagery request sends the selected outline and date to Copernicus Data Space.','प्रतिमेच्या विनंतीसाठी निवडलेली सीमा व तारीख Copernicus Data Space कडे पाठवली जाते.')}</span></div>
      {!meta?.configured&&<div className="satellite-setup"><strong>{t('Satellite account setup required','उपग्रह खाते जोडणे आवश्यक')}</strong><span>{t('The site administrator needs to configure CDSE_CLIENT_ID and CDSE_CLIENT_SECRET in the production environment.','साइट प्रशासकाने उत्पादन वातावरणात CDSE_CLIENT_ID व CDSE_CLIENT_SECRET जोडणे आवश्यक आहे.')}</span></div>}
      <div className="boundary-tools"><div><strong>{t('Add or correct a field outline','शेताची सीमा जोडा किंवा दुरुस्त करा')}</strong><span>{t('Upload GeoJSON or a boundary CSV with matching plot numbers.','जुळणारे प्लॉट क्रमांक असलेली GeoJSON किंवा सीमा CSV फाइल अपलोड करा.')}</span></div><div className="boundary-actions"><button className="button secondary" type="button" onClick={()=>void downloadTemplate()}><Download size={15}/>{t('Template','नमुना फाइल')}</button><label className="button secondary upload-boundary"><Upload size={15}/>{busy?boundaryProgress||t('Working…','प्रक्रिया सुरू आहे…'):t('Upload boundaries','सीमा अपलोड करा')}<input type="file" accept=".geojson,.json,.csv,application/geo+json,application/json,text/csv" disabled={busy||!plots.length} onChange={event=>{const selected=event.target.files?.[0];if(selected)void uploadBoundaries(selected);event.target.value=''}}/></label></div></div>{file&&<p>{t('Selected file','निवडलेली फाइल')}: {file}</p>}
    </div></section>
    <section className="panel satellite-browser"><div className="panel-header"><div><h2>{t('Find imagery for a plot','प्लॉटसाठी उपग्रह प्रतिमा शोधा')}</h2><p>{t('Search all active plots by plot number or village. The selector displays 100 matches at a time.','सर्व सक्रिय प्लॉट क्रमांक किंवा गावानुसार शोधा. निवड यादीत एका वेळी १०० जुळणाऱ्या नोंदी दिसतात.')}</p></div><Cloud size={19}/></div><form className="satellite-query" onSubmit={searchScenes}>
      <label>{t('Find plot','प्लॉट शोधा')}<input value={plotSearch} onChange={event=>setPlotSearch(event.target.value)} placeholder={t('Plot number or village','प्लॉट क्रमांक किंवा गाव')}/></label><label>{t('Plot','प्लॉट')}<select required value={plotId} onChange={event=>setPlotId(event.target.value)}><option value="">{t('Choose plot','प्लॉट निवडा')}</option>{plotOptions.map(plot=><option key={plot.id} value={plot.id}>{plot.plotNo} · {plot.village}{boundaryIds.has(plot.id)?'':t(' · outline needed',' · सीमा आवश्यक')}</option>)}</select></label>
      <label>{t('Sensor','सेन्सर')}<select value={sensor} onChange={event=>setSensor(event.target.value as 'S1'|'S2')}><option value="S2">{t('Sentinel-2 · optical','सेंटिनेल-२ · ऑप्टिकल')}</option><option value="S1">{t('Sentinel-1 · radar','सेंटिनेल-१ · रडार')}</option></select></label><label>{t('Date · optional','तारीख · ऐच्छिक')}<input type="date" value={acquisitionDate} onChange={event=>setAcquisitionDate(event.target.value)}/></label><button className="button primary" disabled={busy||!selectedPlot||!boundaryIds.has(plotId)||!meta?.configured}>{busy?<LoaderCircle className="spin" size={16}/>:t('Search acquisitions','उपग्रह प्रतिमा शोधा')}<ArrowRight size={16}/></button>
    </form>{selectedPlot&&!boundaryIds.has(plotId)&&<div className="small-text">{t('Add the plot outline to search imagery.','उपग्रह प्रतिमा शोधण्यासाठी प्लॉटची सीमा जोडा.')}</div>}{error&&<div className="notice error" role="alert"><AlertCircle size={18}/>{error}</div>}{notice&&<div className="notice success" role="status">{notice}</div>}
    {scenes.length>0&&<div className="table-scroll"><table><thead><tr>{[t('Acquisition','प्रतिमा तारीख'),t('Sensor','सेन्सर'),t('Cloud (%)','ढग (%)'),t('Orbit','कक्षा'),t('Action','कृती')].map(label=><th key={label}>{label}</th>)}</tr></thead><tbody>{scenes.map(scene=><tr key={scene.id}><td>{date(scene.date)}</td><td>{scene.sensor}</td><td>{fmt(scene.cloud,1)}</td><td>{scene.orbit??'—'}</td><td><button className="text-link" disabled={busy} onClick={()=>void processScene(scene)}>{busy&&selectedScene?.id===scene.id?t('Processing…','प्रक्रिया सुरू आहे…'):t('Process plot pixels','प्लॉट पिक्सेल प्रक्रिया करा')}</button></td></tr>)}</tbody></table></div>}</section>
    <section className="panel settings-panel"><h2>{t('Current quality predictions','सध्याचे गुणवत्ता अंदाज')}</h2><p>{t('Pol, Brix, CCS and tonnage from your imported dataset are available across the dashboard. New satellite measurements are stored with their actual acquisition dates.','आयात केलेल्या डेटासेटमधील पोल, ब्रिक्स, CCS व वजन संपूर्ण डॅशबोर्डवर उपलब्ध आहेत. नवीन उपग्रह मापन त्यांच्या प्रत्यक्ष प्रतिमा तारखेसह जतन केले जातात.')}</p><a className="button secondary" href="/satellite-register">{t('Open latest predictions','नवीनतम अंदाज उघडा')}<ArrowRight size={15}/></a></section>
    {observations.length>0&&<section className="panel"><div className="panel-header"><div><h2>{selectedPlot?.plotNo} · {t('Saved observations','जतन केलेली निरीक्षणे')}</h2><p>{t('Pixel measurements with actual acquisition metadata.','प्रत्यक्ष प्रतिमा माहितीसह पिक्सेल मापन.')}</p></div></div><div className="table-scroll"><table><thead><tr>{[t('Date / sensor','तारीख / सेन्सर'),t('Status','स्थिती'),t('Valid coverage (%)','वैध व्याप्ती (%)'),'NDVI','NDRE','LSWI',t('Radar signal','रडार संकेत')].map(label=><th key={label}>{label}</th>)}</tr></thead><tbody>{observations.map((observation,index)=><tr key={`${observation.sensor}-${observation.date}-${index}`}><td>{date(observation.date)}<small>{observation.sensor}</small></td><td>{observation.status==='Screened optical observation'?t('Screened optical observation','पडताळलेले ऑप्टिकल निरीक्षण'):observation.status}</td><td>{fmt(observation.cleanCoverage??observation.validCoverage,1)}</td><td>{fmt(observation.ndvi)}</td><td>{fmt(observation.ndre)}</td><td>{fmt(observation.lswi)}</td><td>{observation.sensor==='S1'?`VV ${fmt(observation.vvDb,1)} dB · VH ${fmt(observation.vhDb,1)} dB`:'—'}</td></tr>)}</tbody></table></div></section>}
  </>;
}
