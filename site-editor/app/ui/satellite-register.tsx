'use client';

import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, ChevronLeft, ChevronRight, Download, Upload } from 'lucide-react';
import { parseCSV } from './csv';
import {useLanguage,cropLabel,priorityLabel} from './language';
import {estimatedRecovery} from '../../lib/recovery';
import {satelliteStatusLabel} from '../../lib/satellite-status';

type RegisterRow = { plotNo: string; status: string; complete: boolean; sourceTimestamp: string; data: Record<string, string> };
type Summary = { total: number; unharvested: number; harvested: number; incomplete: number };
const PAGE_SIZE = 100;
const field = (row: RegisterRow, key: string) => row.data[key] ?? '';
const display = (value: string) => value ? value : '—';
const areaDisplay = (row: RegisterRow) => {
  const registered = field(row, 'registered_area_ha').trim();
  if (registered) return `${registered} ha · registered`;
  const acres = Number(field(row, 'Geodesic Walked Acres'));
  return Number.isFinite(acres) && acres > 0 ? `${(acres * 0.4046856422).toFixed(2)} ha · walked` : '—';
};
const ageDisplay = (row: RegisterRow) => field(row, 'crop_age_days') || field(row, 'True Crop Age as of Oct 22 (Days)') || '—';
type ImportResult={error?:string;ok?:boolean;count?:number;unharvested?:number;harvestedArchived?:number;incomplete?:number};
type UploadCheckpoint={fileKey:string;snapshotId:string;nextRow:number};
const uploadCheckpointKey = 'ikshu-oct2026-register-upload-v1';

async function postImport(body: Record<string, unknown>) {
  let lastError: Error | undefined;
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      const response = await fetch('/api/satellite-register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const result = await response.json() as ImportResult;
      if (response.ok) return result;
      const error = new Error(result.error || 'Could not stage the satellite register batch.');
      if (response.status < 500 && response.status !== 429) throw error;
      lastError = error;
    } catch (error) {
      if (error instanceof Error && !/fetch|network|temporar/i.test(error.message)) throw error;
      lastError = error instanceof Error ? error : new Error('Temporary network error.');
    }
    await new Promise(resolve => setTimeout(resolve, Math.min(1500 * 2 ** attempt, 12000)));
  }
  throw new Error(`${lastError?.message || 'Network connection failed.'} Re-upload the same file to resume from the last confirmed batch; the currently active register stays unchanged.`);
}

export default function SatelliteRegister() {
  const {language,t,format,date}=useLanguage();
  const [rows, setRows] = useState<RegisterRow[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [filteredTotal, setFilteredTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('Unharvested');
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const load = useCallback(async (nextOffset = 0) => {
    const params = new URLSearchParams({ offset: String(nextOffset), limit: String(PAGE_SIZE) });
    if (query.trim()) params.set('q', query.trim());
    if (status !== 'All') params.set('status', status);
    const response = await fetch(`/api/satellite-register?${params}`, { cache: 'no-store' });
    const result = await response.json() as {error?:string;rows:RegisterRow[];summary:Summary;filteredTotal:number};
    if (!response.ok) throw new Error(result.error || 'Could not load the satellite register.');
    setRows(result.rows || []); setSummary(result.summary || null); setFilteredTotal(result.filteredTotal || 0); setOffset(nextOffset);
  }, [query, status]);

  useEffect(() => { void load(0).catch(e => setError(e.message)); }, [load]);

  async function upload(file: File) {
    setBusy(true); setError(''); setMessage(''); setProgress(t('Reading file…','फाइल वाचत आहे…'));
    try {
      if (file.size > 100_000_000) throw new Error('Choose a CSV smaller than 100 MB.');
      const parsed = parseCSV(await file.text());
      if (parsed.length !== 29384) throw new Error(`Expected the 29,384-row October register; found ${parsed.length.toLocaleString()} rows. No rows were activated.`);
      const required = ['Plot No', 'registered_area_ha', 'crop_age_days', 'predicted_brix_bx', 'predicted_pol_juice_pct', 'predicted_ccs_pct', 'latest_satellite_calculation_timestamp'];
      for (const name of required) if (!Object.hasOwn(parsed[0], name)) throw new Error(`Missing source column: ${name}`);
      const plotNumbers = parsed.map(row => String(row['Plot No'] || '').trim());
      if (plotNumbers.some(value => !value) || new Set(plotNumbers).size !== plotNumbers.length) throw new Error('Plot numbers must be present and unique.');
      const timestamps = [...new Set(parsed.map(row => String(row.latest_satellite_calculation_timestamp || '').trim()).filter(Boolean))];
      if (timestamps.length !== 1) throw new Error('This upload must contain one consistent satellite calculation timestamp.');
      const fileKey = `${file.name}|${file.size}|${file.lastModified}|${parsed.length}`;
      let checkpoint: UploadCheckpoint | null = null;
      try { checkpoint = JSON.parse(localStorage.getItem(uploadCheckpointKey) || 'null') as UploadCheckpoint | null; } catch { checkpoint = null; }
      const snapshotId = checkpoint?.fileKey === fileKey ? checkpoint.snapshotId : crypto.randomUUID();
      const batchSize = 200;
      const resumeAt = checkpoint?.fileKey === fileKey ? Math.min(parsed.length, Math.floor(checkpoint.nextRow / batchSize) * batchSize) : 0;
      if (resumeAt) setProgress(`Resuming from ${resumeAt.toLocaleString()} / ${parsed.length.toLocaleString()} confirmed rows…`);
      for (let start = resumeAt; start < parsed.length; start += batchSize) {
        const batch = parsed.slice(start, start + batchSize).map(row => ({ plotNo: String(row['Plot No']).trim(), sourceTimestamp: String(row.latest_satellite_calculation_timestamp).trim(), data: row }));
        setProgress(`${t('Sending rows','नोंदी पाठवत आहे')} ${(start+1).toLocaleString()}–${Math.min(start+batch.length,parsed.length).toLocaleString()} / ${parsed.length.toLocaleString()}…`);
        await postImport({ action: 'import', snapshotId, rows: batch });
        localStorage.setItem(uploadCheckpointKey, JSON.stringify({ fileKey, snapshotId, nextRow: start + batch.length }));
        setProgress(`${t('Confirmed rows','पुष्टी झालेल्या नोंदी')} ${Math.min(start+batch.length,parsed.length).toLocaleString()} / ${parsed.length.toLocaleString()}…`);
      }
      setProgress(t('Validating and activating the register…','नोंदवहीची पडताळणी व सक्रिय करणे सुरू आहे…'));
      const finalized = await postImport({ action: 'finalize', snapshotId, expectedCount: parsed.length, confirmedHarvestedCount: 410 });
      localStorage.removeItem(uploadCheckpointKey);
      setMessage(`${Number(finalized.unharvested).toLocaleString()} unharvested rows loaded; ${Number(finalized.harvestedArchived).toLocaleString()} harvested plots archived; ${Number(finalized.incomplete).toLocaleString()} rows flagged for missing area or crop age.`);
      setQuery(''); setStatus('Unharvested');
      await load(0);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); setProgress(''); }
  }

  return <>
    <div className="metric-grid" style={{marginBottom:18}}>
      <section className="metric"><div><span>{t('Latest register rows','नवीनतम नोंदवहीतील प्लॉट')}</span></div><strong>{format(summary?.unharvested,0)}</strong><p>{t('Unharvested plots','तोडणी बाकी प्लॉट')}</p></section>
      <section className="metric"><div><span>{t('Complete for area & age','क्षेत्र व वय पूर्ण उपलब्ध')}</span></div><strong>{summary?format(summary.unharvested-summary.incomplete,0):'—'}</strong><p>{t('Area and maturity review fields','क्षेत्र व परिपक्वता पडताळणीची माहिती')}</p></section>
      <section className="metric"><div><span>{t('Missing area or age','क्षेत्र किंवा वय अनुपलब्ध')}</span></div><strong>{format(summary?.incomplete,0)}</strong><p>{t('Rows requiring review','पडताळणी आवश्यक नोंदी')}</p></section>
      <section className="metric"><div><span>{t('Harvested and archived','तोडणी पूर्ण व संग्रहित')}</span></div><strong>{format(summary?.harvested,0)}</strong><p>{t('Retained from prior register','मागील नोंदवहीतून जतन केलेले')}</p></section>
    </div>
    <section className="panel" style={{marginBottom:18}}><div className="panel-header"><div><h2>{t('Update the active dataset','सक्रिय डेटासेट अद्ययावत करा')}</h2><p>{t('Upload the supplied 29,384-row CSV. The activated dataset is shared across the dashboard.','पुरवलेली २९,३८४ नोंदींची CSV फाइल अपलोड करा. सक्रिय डेटासेट संपूर्ण डॅशबोर्डवर वापरला जातो.')}</p></div></div>
      <div className="notice info"><AlertCircle size={18}/><span>{t('Pol, Brix and CCS are supplied predictions. Blank registered hectares use converted walked acres, labeled as walked area. Survey crop age is used when the standard age field is blank. Estimated recovery = CCS × 0.754.','पोल, ब्रिक्स व CCS हे पुरवलेले अंदाज आहेत. नोंदणीकृत क्षेत्र रिकामे असल्यास GPS मोजणीचे एकर हेक्टरमध्ये रूपांतरित करून स्पष्टपणे दर्शवले जातात. सामान्य वय रिकामे असल्यास सर्वेक्षणातील पीक वय वापरले जाते. अंदाजित साखर उतारा = CCS × 0.754.')}</span></div>
      <label className="upload-zone" style={{marginTop:14}}><Upload size={24}/><strong>{busy?progress||t('Updating…','अद्ययावत होत आहे…'):t('Choose latest CSV register','नवीनतम CSV नोंदवही निवडा')}</strong><input type="file" accept=".csv,text/csv" disabled={busy} onChange={event=>{const file=event.target.files?.[0];if(file)void upload(file);event.target.value=''}}/></label>
      {error&&<div className="notice error" role="alert" style={{marginTop:12}}>{t('Import error: ','अपलोडमध्ये अडचण: ')}{error}</div>}{message&&<div className="notice success" role="status" style={{marginTop:12}}>{message}</div>}
    </section>
    <section className="panel"><div className="panel-header" style={{flexWrap:'wrap',gap:12}}><div><h2>{t('All plot estimates','सर्व प्लॉटचे अंदाज')}</h2><p>{format(summary?.unharvested,0)} {t('unharvested plots · 100 rows per page · Source calculation time:','तोडणी बाकी प्लॉट · प्रत्येक पृष्ठावर १०० नोंदी · मूळ गणना वेळ:')} {rows.find(row=>row.status==='Unharvested')?.sourceTimestamp||'—'}</p></div>
      <div style={{display:'flex',gap:8,flexWrap:'wrap'}}><input aria-label={t('Search plot number','प्लॉट क्रमांक शोधा')} placeholder={t('Search plot number','प्लॉट क्रमांक शोधा')} value={query} onChange={event=>setQuery(event.target.value)}/><select aria-label={t('Register status','नोंदवही स्थिती')} value={status} onChange={event=>setStatus(event.target.value)}><option value="All">{t('All','सर्व')}</option><option value="Unharvested">{t('Unharvested','तोडणी बाकी')}</option><option value="Harvested">{t('Harvested','तोडणी पूर्ण')}</option></select><a className="button secondary" href={`/api/satellite-register?format=csv&lang=${language}${status!=='All'?`&status=${encodeURIComponent(status)}`:''}${query.trim()?`&q=${encodeURIComponent(query.trim())}`:''}`}><Download size={16}/>{t('Download all filtered rows','निवडलेल्या सर्व नोंदी डाउनलोड करा')}</a></div></div>
      <div className="table-scroll"><table><thead><tr>{[t('Plot','प्लॉट'),t('Farmer','शेतकरी'),t('Village','गाव'),t('Plantation date','लागवड तारीख'),t('Crop / variety','ऊस प्रकार / वाण'),t('Area (ha)','क्षेत्र (हे.)'),t('Age (days)','वय (दिवस)'),t('Predicted Pol (%)','अंदाजित पोल (%)'),t('Predicted Brix (°Bx)','अंदाजित ब्रिक्स (°Bx)'),t('Predicted CCS (%)','अंदाजित CCS (%)'),t('Estimated recovery (%)','अंदाजित साखर उतारा (%)'),t('Standing tonnage (MT)','उभ्या उसाचे वजन (MT)'),t('Status','स्थिती')].map(label=><th key={label}>{label}</th>)}</tr></thead><tbody>
      {rows.map(row=><tr key={`${row.plotNo}-${row.status}`}><td><strong>{row.plotNo}</strong></td><td>{display(field(row,'Farmer Name'))}</td><td>{display(field(row,'Village')||field(row,'village'))}</td><td>{date(field(row,'Plantation Date (Raw Ground Survey)')||field(row,'planting_date'))}</td><td>{cropLabel(field(row,'Cane Type')||field(row,'caneType'),language)} · {display(field(row,'Variety Name')||field(row,'Variety')||field(row,'variety'))}</td><td>{field(row,'registered_area_ha').trim()?`${format(Number(field(row,'registered_area_ha')))} ${t('ha · registered','हे. · नोंदणीकृत')}`:Number(field(row,'Geodesic Walked Acres'))>0?`${format(Number(field(row,'Geodesic Walked Acres'))*0.4046856422)} ${t('ha · walked','हे. · GPS मोजणी')}`:'—'}</td><td>{format(Number(ageDisplay(row)),0)}</td><td>{display(field(row,'predicted_pol_juice_pct'))}</td><td>{display(field(row,'predicted_brix_bx'))}</td><td>{display(field(row,'predicted_ccs_pct'))}</td><td className="recovery-value" title="CCS × 0.754">{format(estimatedRecovery(field(row,'predicted_ccs_pct')))}</td><td>{display(field(row,'Standing Millable Tonnage (MT)'))}</td><td>{priorityLabel(row.status,language)}{field(row,'prediction_refresh_status')==='NO_SPECTRAL_CANE_SUPPORT'&&<small className="plot-cell-meta">{t('No candidate cane pixels; field check needed','संभाव्य उसाचे पिक्सेल नाहीत; प्रत्यक्ष तपासणी आवश्यक')}</small>}{field(row,'prediction_refresh_status')==='NO_TRACEABLE_MODEL_INPUTS'&&<small className="plot-cell-meta">{t('Quality inputs unavailable','गुणवत्तेसाठी माहिती अनुपलब्ध')}</small>}{field(row,'satellite_refresh_status')&&<small className="plot-cell-meta">{date(field(row,'satellite_acquisition_date'))} · {satelliteStatusLabel(field(row,'satellite_refresh_status'),language==='mr')}</small>}</td></tr>)}
      {!rows.length&&<tr><td colSpan={13}>{t('No matching records.','जुळणाऱ्या नोंदी नाहीत.')}</td></tr>}</tbody></table></div>
      <div className="table-footer"><span>{filteredTotal?`${format(offset+1,0)}–${format(Math.min(offset+rows.length,filteredTotal),0)} / ${format(filteredTotal,0)}`:'0'}</span><div className="boundary-actions"><button className="button secondary" disabled={busy||offset===0} onClick={()=>void load(Math.max(0,offset-PAGE_SIZE)).catch(e=>setError(e.message))}><ChevronLeft size={16}/>{t('Previous','मागील')}</button><button className="button secondary" disabled={busy||offset+PAGE_SIZE>=filteredTotal} onClick={()=>void load(offset+PAGE_SIZE).catch(e=>setError(e.message))}>{t('Next','पुढील')}<ChevronRight size={16}/></button></div></div>
    </section>
  </>;
}
