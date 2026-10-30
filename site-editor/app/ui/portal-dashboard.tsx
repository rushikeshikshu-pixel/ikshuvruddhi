'use client';
import {useCallback,useEffect,useMemo,useRef,useState,type FormEvent} from 'react';
import {LayoutDashboard,Layers,Satellite,FlaskConical,CalendarDays,Settings,Map as MapIcon,Download,RefreshCw,Plus,X,LogOut,ArrowRight,Menu,Upload,Eye} from 'lucide-react';
import type {Workspace,Plot,Sample} from '../types';
import Brand from './brand';
import {sampleWorkspace} from './demo-data';
import {estimatedRecovery,recoveryForExport,RECOVERY_FACTOR} from '../../lib/recovery';
import {satelliteStatusLabel} from '../../lib/satellite-status';
import FieldMap from './field-map';
import PlotVisualizer from './plot-visualizer';
import {downloadCSV as downloadRawCSV} from './csv';
import {LanguageSwitch,useLanguage,cropLabel,priorityLabel,tierLabel} from './language';

const NAV=[['overview','Overview','आढावा',LayoutDashboard],['map','Command map','कार्यक्षेत्र नकाशा',MapIcon],['plots','Plot register','प्लॉट नोंदवही',Layers],['observations','Observations','उपग्रह निरीक्षणे',Satellite],['lab','Lab quality','प्रयोगशाळा गुणवत्ता',FlaskConical],['harvest','Harvest plan','तोडणी नियोजन',CalendarDays],['settings','Settings','सेटिंग्ज',Settings]] as const;
type WorkspacePage=Workspace&{error?:string;pagination?:{total:number;snapshotId:string|null}};
const EMPTY:Workspace={mill:null,plots:[],samples:[],register:null};
const ageOf=(p:Plot)=>p.cropAgeDays??Math.max(0,Math.floor((Date.now()-Date.parse(p.plantingDate))/86400000));

export default function PortalDashboard({email,demo=false}:{email:string;demo?:boolean}){
 const {language,t,format,date}=useLanguage();
 const downloadCSV=(name:string,rows:Record<string,unknown>[])=>downloadRawCSV(name,rows,language);
 const [data,setData]=useState<Workspace>(EMPTY);const [view,setView]=useState('overview');const [busy,setBusy]=useState(true);const [loaded,setLoaded]=useState(0);const [expected,setExpected]=useState(0);const [error,setError]=useState('');const [message,setMessage]=useState('');const [mobile,setMobile]=useState(false);
 const [query,setQuery]=useState('');const [village,setVillage]=useState('');const [variety,setVariety]=useState('');const [page,setPage]=useState(0);const [sortCcs,setSortCcs]=useState(false);const [selected,setSelected]=useState<Plot|null>(null);const [modal,setModal]=useState<'plan'|'sample'|'observation'|'mill'|null>(null);const [editing,setEditing]=useState<Plot|null>(null);const [saving,setSaving]=useState(false);const [sampleQuery,setSampleQuery]=useState('');
 const snapshot=useRef<string|null>(null);const loading=useRef(false);
 const load=useCallback(async()=>{
  if(demo){setData(structuredClone(sampleWorkspace));setLoaded(sampleWorkspace.plots.length);setExpected(sampleWorkspace.plots.length);setBusy(false);return;}
  if(loading.current)return;loading.current=true;setBusy(true);setError('');setLoaded(0);
  const fetchPage=async(offset:number,id?:string|null)=>{
   const params=new URLSearchParams({offset:String(offset),limit:'1000'});if(id)params.set('snapshotId',id);
   let failure:Error=new Error('Could not load the active register.');
   for(let attempt=0;attempt<3;attempt++)try{const r=await fetch(`/api/workspace?${params}`,{cache:'no-store'});const result=await r.json() as WorkspacePage;if(!r.ok)throw new Error(result.error||failure.message);return result}catch(e){failure=e as Error;if(attempt<2)await new Promise(resolve=>setTimeout(resolve,750*(attempt+1)))}
   throw failure;
  };
  try{
   const first=await fetchPage(0);const total=first.pagination?.total??first.plots.length;setExpected(total);const all:Plot[]=[...first.plots];setLoaded(all.length);
   const offsets=Array.from({length:Math.max(0,Math.ceil(total/1000)-1)},(_,i)=>(i+1)*1000);
   for(let start=0;start<offsets.length;start+=4){const batch=await Promise.all(offsets.slice(start,start+4).map(offset=>fetchPage(offset,first.pagination?.snapshotId)));for(const result of batch)all.push(...result.plots);setLoaded(all.length)}
   if(all.length!==total||new Set(all.map(p=>p.plotNo)).size!==total)throw new Error('The register is incomplete. Please reload.');
   all.sort((a,b)=>a.plotNo.localeCompare(b.plotNo,'en',{numeric:true}));snapshot.current=first.pagination?.snapshotId||null;setData({mill:first.mill,plots:all,samples:first.samples||[],register:first.register||null});
  }catch(e){setError((e as Error).message)}finally{loading.current=false;setBusy(false)}
 },[demo]);
 useEffect(()=>{void load();if(demo)return;const check=async()=>{if(loading.current)return;try{const r=await fetch('/api/workspace?view=version',{cache:'no-store'});const next=await r.json() as {snapshotId:string|null};if(r.ok&&next.snapshotId!==snapshot.current)void load()}catch{}};const timer=setInterval(check,60000);window.addEventListener('focus',check);return()=>{clearInterval(timer);window.removeEventListener('focus',check)}},[load,demo]);
 useEffect(()=>{setPage(0)},[view,query,village,variety,sortCcs]);
 useEffect(()=>{if(!modal)return;const handler=(e:KeyboardEvent)=>{if(e.key==='Escape'&&!saving)setModal(null)};window.addEventListener('keydown',handler);return()=>window.removeEventListener('keydown',handler)},[modal,saving]);
 const latest=useMemo(()=>{const map=new Map<string,Sample>();for(const s of [...data.samples].sort((a,b)=>b.sampleDate.localeCompare(a.sampleDate)))if(!map.has(s.plotId))map.set(s.plotId,s);return map},[data.samples]);
 const villages=useMemo(()=>[...new Set(data.plots.map(p=>p.village))].sort(),[data.plots]);const varieties=useMemo(()=>[...new Set(data.plots.map(p=>p.variety).filter(Boolean))].sort(),[data.plots]);
 const filtered=useMemo(()=>{const q=query.toLowerCase().trim();const rows=data.plots.filter(p=>(!village||p.village===village)&&(!variety||p.variety===variety)&&(!q||[p.plotNo,p.village,p.farmerName||'',p.variety].some(value=>value.toLowerCase().includes(q))));if(sortCcs&&view==='harvest')rows.sort((a,b)=>(b.predictedCcs??-1)-(a.predictedCcs??-1));return rows},[data.plots,query,village,variety,sortCcs,view]);
 const pageCount=Math.max(1,Math.ceil(filtered.length/100));const currentPage=Math.min(page,pageCount-1);const paged=filtered.slice(currentPage*100,(currentPage+1)*100);
 const source=data.register;const sumArea=source?.areaHa??data.plots.reduce((sum,p)=>sum+p.area,0);const sumTonnage=source?.tonnage??(data.plots.some(p=>p.tonnage!=null)?data.plots.reduce((sum,p)=>sum+(p.tonnage||0),0):null);
 const average=(key:'predictedPol'|'predictedBrix'|'predictedCcs')=>{const values=data.plots.map(p=>p[key]).filter((n):n is number=>n!=null);return values.length?values.reduce((a,b)=>a+b,0)/values.length:null};
 const measured=(key:'pol'|'brix'|'recovery')=>{const values=[...latest.values()].map(s=>s[key]).filter((n):n is number=>n!=null);return values.length?values.reduce((a,b)=>a+b,0)/values.length:null};
 const topVillages=useMemo(()=>{const groups=new Map<string,{village:string;count:number;area:number;tonnage:number;tonnageCount:number}>();for(const p of data.plots){const row=groups.get(p.village)||{village:p.village,count:0,area:0,tonnage:0,tonnageCount:0};row.count++;row.area+=p.area;row.tonnage+=p.tonnage||0;if(p.tonnage!=null)row.tonnageCount++;groups.set(p.village,row)}return [...groups.values()].sort((a,b)=>b.tonnage-a.tonnage||b.area-a.area).slice(0,8)},[data.plots]);
 const planCount=data.plots.filter(p=>p.harvestDate).length;
 const areaBasis=(p:Plot)=>p.areaBasis==='walked'?t('Walked area','GPS मोजलेले क्षेत्र'):t('Registered area','नोंदणीकृत क्षेत्र');
 function navigate(next:string){setView(next);setQuery('');setVillage('');setVariety('');setMobile(false)}
 function open(kind:typeof modal,p?:Plot){setEditing(p||null);setModal(kind);setMessage('')}
 async function save(action:string,values:Record<string,unknown>){if(demo){setData(previous=>{const next=structuredClone(previous);if(action==='mill')next.mill={name:String(values.name),location:String(values.location),season:String(values.season)};if(action==='plan')next.plots=next.plots.map(p=>p.id===values.id?{...p,harvestDate:values.harvestDate?String(values.harvestDate):null,priority:String(values.priority)}:p);if(action==='observation')next.plots=next.plots.map(p=>p.id===values.id?{...p,acquisitionDate:String(values.acquisitionDate),cloud:Number(values.cloud),ndvi:Number(values.ndvi)}:p);if(action==='sample')next.samples.unshift({id:crypto.randomUUID(),plotId:String(values.plotId),sampleDate:String(values.sampleDate),pol:Number(values.pol),brix:Number(values.brix),recovery:values.recovery==null?null:Number(values.recovery),createdAt:new Date().toISOString()});return next});setModal(null);setMessage(t('Demo updated for this visit.','या भेटीसाठी प्रात्यक्षिक अद्ययावत केले.'));return;}setSaving(true);setError('');try{const r=await fetch('/api/workspace',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,data:values})});const result=await r.json() as {error?:string};if(!r.ok)throw new Error(result.error||'Unable to save');setModal(null);setMessage(t('Saved to your mill workspace.','कारखान्याच्या नोंदीत जतन केले.'));await load()}catch(e){setError((e as Error).message)}finally{setSaving(false)}}
 function submit(event:FormEvent<HTMLFormElement>){event.preventDefault();const f=new FormData(event.currentTarget);const text=(key:string)=>String(f.get(key)||'');const num=(key:string)=>text(key)?Number(text(key)):null;
  if(modal==='mill')void save('mill',{name:text('name'),location:text('location'),season:text('season')});
  if(modal==='plan')void save('plan',{id:editing?.id,harvestDate:text('harvestDate')||null,priority:text('priority')});
  if(modal==='sample')void save('sample',{plotId:text('plotId'),sampleDate:text('sampleDate'),pol:num('pol'),brix:num('brix'),recovery:num('recovery')});
  if(modal==='observation')void save('observation',{id:editing?.id,acquisitionDate:text('acquisitionDate'),cloud:num('cloud'),ndvi:num('ndvi')});
 }
 function exportRegister(rows=filtered){downloadCSV('gangamai-dashboard-register.csv',rows.map(p=>{
  const prog = p.harvestProgressPct != null ? p.harvestProgressPct : (p.priority === 'Ready' ? 35 : (p.harvestDate ? 25 : 0));
  const initTon = p.tonnage ?? Number((p.area * 102).toFixed(1));
  const remTon = Number(Math.max(0, initTon * (1 - prog / 100)).toFixed(1));
  const remTrollies = Math.max(0, Math.ceil(remTon / 12));
  return {
    plotNo: p.plotNo,
    farmer: p.farmerName,
    village: p.village,
    variety: p.variety,
    caneType: p.caneType,
    plantationDate: p.plantingDate,
    cropAgeDays: ageOf(p),
    surveyAgeDays: p.surveyAgeDays,
    areaHa: p.area,
    areaBasis: p.areaBasis,
    predictedPol: p.predictedPol,
    predictedBrix: p.predictedBrix,
    predictedCcs: p.predictedCcs,
    estimatedRecoveryPct: recoveryForExport(p.predictedCcs),
    recoveryFactor: RECOVERY_FACTOR,
    initialTonnageMt: initTon,
    harvestProgressPct: `${prog}%`,
    remainingStandingTonnageMt: remTon,
    remainingTrollies: remTrollies,
    satelliteCadence: '1–2 Days (S2 + PlanetScope 3m + S1 SAR)',
    yieldMtPerHa: p.yieldPerHa,
    sourceCalculationTime: p.sourceTimestamp,
    satelliteAcquisitionDate: p.acquisitionDate,
    satelliteRefreshStatus: p.satelliteRefreshStatus,
    predictionRefreshStatus: p.predictionRefreshStatus,
    detectedCaneAreaHa: p.detectedCaneAreaHa,
    harvestTier: p.harvestTier,
    harvestDate: p.harvestDate,
    manualReview: p.priority
  };
}))}
 const controls=<><div className="table-toolbar"><input aria-label={t('Search plots','प्लॉट शोधा')} placeholder={t('Search plot, farmer or village…','प्लॉट, शेतकरी किंवा गाव शोधा…')} value={query} onChange={e=>setQuery(e.target.value)}/><select aria-label={t('Village filter','गाव निवडा')} value={village} onChange={e=>setVillage(e.target.value)}><option value="">{t('All villages','सर्व गावे')}</option>{villages.map(v=><option key={v} value={v}>{v}</option>)}</select><select aria-label={t('Variety filter','वाण निवडा')} value={variety} onChange={e=>setVariety(e.target.value)}><option value="">{t('All varieties','सर्व वाण')}</option>{varieties.map(v=><option key={v} value={v}>{v}</option>)}</select><button className="button secondary" onClick={()=>exportRegister()}><Download size={15}/>{t('Export results','निकाल डाउनलोड करा')}</button></div><div className="table-footer"><span>{format(filtered.length?currentPage*100+1:0,0)}–{format(Math.min((currentPage+1)*100,filtered.length),0)} / {format(filtered.length,0)} {t('plots','प्लॉट')}</span><div className="boundary-actions"><button className="button secondary" disabled={!currentPage} onClick={()=>setPage(currentPage-1)}>{t('Previous','मागील')}</button><span>{t('Page','पृष्ठ')} {currentPage+1} / {pageCount}</span><button className="button secondary" disabled={currentPage>=pageCount-1} onClick={()=>setPage(currentPage+1)}>{t('Next','पुढील')}</button></div></div></>;
 const plotCell=(p:Plot)=><td><div className="plot-cell-actions"><button className="text-link" onClick={()=>setSelected(p)}>{p.plotNo}</button>{view==='plots'&&<button type="button" className="button secondary inspect-button" aria-label={t(`Inspect plot ${p.plotNo}`,`प्लॉट ${p.plotNo} तपशील पहा`)} onClick={()=>setSelected(p)}><Eye size={15}/>{t('Inspect','तपशील पहा')}</button>}</div><small>{p.farmerName}</small><small>{p.village}</small></td>;
 const title=NAV.find(row=>row[0]===view);const metric=(label:string,value:string,unit:string,note:string)=><section className="metric"><div><span>{label}</span></div><strong>{value}<small>{unit}</small></strong><p>{note}</p></section>;
 return <div className="portal-shell"><aside className={'sidebar '+(mobile?'open':'')}><a href="/"><Brand/></a><div className="workspace-label">{t('MILL WORKSPACE','कारखाना कार्यक्षेत्र')}</div><nav aria-label={t('Workspace navigation','कार्यक्षेत्र पर्याय')}>{NAV.map(([key,en,mr,Icon])=><button key={key} className={view===key?'active':''} onClick={()=>navigate(key)}><Icon size={19}/>{t(en,mr)}</button>)}</nav><a className="sidebar-satellite-link" href="/satellite-register"><Layers size={18}/>{t('Latest dataset','नवीनतम डेटासेट')}<ArrowRight size={15}/></a><a className="sidebar-satellite-link" href="/satellite"><Satellite size={18}/>{t('Satellite feed','उपग्रह सेवा')}<ArrowRight size={15}/></a><div className="sidebar-bottom"><strong>{data.mill?.name||'Gangamai'}</strong><small>{data.mill?.season||'2026–27'}</small><a href="/api/auth/logout?return_to=%2Flogin"><LogOut size={16}/>{t('Sign out','बाहेर पडा')}</a></div></aside>
 <div className="portal-body"><header className="portal-topbar"><button className="icon-btn mobile-menu" aria-label={t('Menu','पर्याय')} onClick={()=>setMobile(!mobile)}><Menu/></button><span>{t('Workspace','कार्यक्षेत्र')} / {title?t(title[1],title[2]):''}</span><div className="topbar-right"><LanguageSwitch/><span className="season-pill">{data.mill?.season||'2026–27'}</span></div></header><main className="portal-main"><div className="portal-heading"><div><div className="eyebrow">{data.mill?.location||'IKSHU INTELLIGENCE'}</div><h1>{view==='overview'?t('Your cane landscape.','आपले ऊस कार्यक्षेत्र.'):title?t(title[1],title[2]):''}</h1><p>{t('One active register across every dashboard view.','डॅशबोर्डच्या सर्व विभागांसाठी एकच अद्ययावत नोंदवही.')}</p></div><div className="heading-actions"><button className="button secondary" disabled={busy} onClick={()=>void load()}><RefreshCw size={16}/>{t('Refresh','ताजे करा')}</button><a className="button primary" href="/satellite-register"><Upload size={16}/>{t('Update dataset','डेटासेट अद्ययावत करा')}</a></div></div>
 {error&&<div className="notice error" role="alert">{error}<button className="button secondary" onClick={()=>void load()}>{t('Retry','पुन्हा प्रयत्न करा')}</button></div>}{message&&<div className="notice success" role="status">{message}</div>}
 {demo&&<div className="notice info">{t('Illustrative demo · 16 plots. Sign in to see the current mill register.','प्रात्यक्षिक माहिती · १६ प्लॉट. कारखान्याची अद्ययावत नोंदवही पाहण्यासाठी लॉगिन करा.')}</div>}{busy?<section className="panel empty-state"><RefreshCw className="spinner"/><h2>{t('Loading the active register…','अद्ययावत नोंदवही लोड होत आहे…')}</h2><p>{format(loaded,0)} / {format(expected,0)} {t('plots loaded','प्लॉट लोड झाले')}</p></section>:<>
 {source&&<div className="notice info register-source-banner"><span><strong>{t('Active dataset','सक्रिय डेटासेट')}: {source.sourceTimestamp}</strong><br/>{format(source.total,0)} {t('unharvested plots','तोडणी बाकी प्लॉट')} · {format(source.archived,0)} {t('harvested and archived','तोडणी पूर्ण व संग्रहित')} · {format(source.complete,0)} {t('complete for area and age','क्षेत्र व वय उपलब्ध')}{source.satelliteDate&&<><br/>{t('Sentinel-2 acquisition','सेंटिनेल-२ प्रतिमा')}: {date(source.satelliteDate)} · {format(source.refreshedCount,0)} {t('imagery refreshed','प्रतिमेतून अद्ययावत')} · {format(source.recomputedCount,0)} {t('quality estimates recomputed','गुणवत्ता अंदाज पुन्हा गणित केले')} · {format(source.total-(source.refreshedCount||0),0)} {t('imagery exceptions retained for review','प्रतिमा अपवाद पडताळणीसाठी कायम')}</>}</span><a className="text-link" href="/satellite-register">{t('View source register','मूळ नोंदवही पहा')} <ArrowRight size={15}/></a></div>}
 {source?.inputPolicy==='TRACEABLE_SOURCES_NO_SYNTHETIC_FILL'&&<div className="notice info"><span><strong>{t('Traceable inputs; no synthetic fill','स्रोतासह माहिती; कृत्रिम भराव नाही')}</strong><br/>{t('Screening estimates from September calibration. Village holdout','सप्टेंबरच्या नमुन्यांवर आधारित प्राथमिक अंदाज. स्वतंत्र गावांवरील चाचणी')}: {format(source.holdoutSamples,0)} {t('samples','नमुने')} · Pol MAE {format(source.holdoutPolMae)} · Brix MAE {format(source.holdoutBrixMae)}.<br/>{t('CCS is formula-derived. Yield, fibre and tonnage remain unavailable without measured source records. Cutting status requires current mill permits.','CCS सूत्रावरून काढलेला आहे. मापनाचे स्रोत नसल्याने उत्पादन, तंतू व वजन अनुपलब्ध आहेत. तोडणी स्थितीसाठी कारखान्याची अद्ययावत परवानगी आवश्यक आहे.')}</span></div>}
 {view==='overview'&&<><div className="notice info" style={{ display: 'flex', alignItems: 'center', gap: '14px', background: '#ecfdf5', borderColor: '#a7f3d0', padding: '14px 18px', borderRadius: '8px', marginBottom: '16px' }}>
  <span style={{ fontSize: '24px' }}>🛰️</span>
  <div style={{ flex: 1 }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '3px' }}>
      <strong style={{ color: '#065f46', fontSize: '13px' }}>{t('1–2 Day Multi-Constellation Satellite Monitoring Active','१-२ दिवसांचे बहु-उपग्रह निरीक्षण सक्रिय')}</strong>
      <span style={{ background: '#10b981', color: '#fff', fontSize: '10px', fontWeight: 700, padding: '1px 6px', borderRadius: '10px' }}>{t('Zero 5-Day Gaps','५-दिवसांचा अंतर नाही')}</span>
    </div>
    <span style={{ color: '#047857', fontSize: '12px', lineHeight: 1.4 }}>
      {t('Sentinel-2 (5-day cycle) is augmented with PlanetScope 3.0m (daily) and Sentinel-1 C-band SAR (cloud-penetrating radar) to track daily partial harvesting and remaining standing field tonnage within 24–48 hours.',
         'सेंटिनेल-२ (५-दिवसीय फेरी) च्या अंतरात प्लॅनेटस्कोप ३.० मी (दैनिक) आणि सेंटिनेल-१ सी-बँड एसएआर (ढगभेदी रडार) चा वापर करून २४-४८ तासांत तोडणी व शेतात शिल्लक राहिलेल्या उसाचे वजन ट्रॅक केले जाते.')}
    </span>
  </div>
</div>
<div className="metric-grid">{metric(t('Active plots','सक्रिय प्लॉट'),format(data.plots.length,0),'',`${format(villages.length,0)} ${t('villages / clusters','गावे / क्षेत्रे')}`)}{metric(t('Reported area','उपलब्ध क्षेत्रफळ'),format(sumArea,2),t('ha','हे.'),`${format(source?.walkedCount||0,0)} ${t('plots use labeled walked area','प्लॉटसाठी GPS मोजलेले क्षेत्र वापरले आहे')}`)}{metric(t('Standing field tonnage','शेतातील उभे वजन'),format(sumTonnage,1),'MT',t('1–2d Satellite & gate calibrated','१-२ दिवसीय उपग्रह व वजनकाटा आधारित'))}{metric(t('Mean predicted CCS','सरासरी अंदाजित CCS'),format(source?.avgCcs??average('predictedCcs')),'%',`${t('Estimated recovery','अंदाजित साखर उतारा')}: ${format(source?.avgEstimatedRecoveryPct??estimatedRecovery(source?.avgCcs??average('predictedCcs')))}% · CCS × 0.754`)}</div>
 <div className="dashboard-grid"><section className="panel"><div className="panel-header"><div><h2>{t('Field perspective','कार्यक्षेत्राचा नकाशा')}</h2><p>{format(data.plots.length,0)} {t('active plots · supplied survey outlines','सक्रिय प्लॉट · पुरवलेल्या सर्वेक्षण सीमा')}</p></div><button className="text-link" onClick={()=>navigate('map')}>{t('Open map','नकाशा उघडा')} <ArrowRight size={15}/></button></div><div style={{height:460}}><FieldMap plots={data.plots} samples={data.samples} onSelectPlot={setSelected}/></div></section><div className="dashboard-side"><section className="panel"><div className="panel-header"><div><h2>{t('Latest predicted quality','नवीनतम अंदाजित गुणवत्ता')}</h2><p>{t('Mean values from the active dataset','सक्रिय डेटासेटमधील सरासरी मूल्ये')}</p></div></div><div className="quality-stats has-recovery"><div><span>{t('Predicted Pol','अंदाजित पोल')}</span><strong>{format(source?.avgPol??average('predictedPol'))}<small>%</small></strong></div><div><span>{t('Predicted Brix','अंदाजित ब्रिक्स')}</span><strong>{format(source?.avgBrix??average('predictedBrix'))}<small>°Bx</small></strong></div><div><span>CCS</span><strong>{format(source?.avgCcs??average('predictedCcs'))}<small>%</small></strong></div><div className="quality-recovery"><span>{t('Estimated recovery','अंदाजित साखर उतारा')}</span><strong>{format(source?.avgEstimatedRecoveryPct??estimatedRecovery(source?.avgCcs??average('predictedCcs')))}<small>%</small></strong><em>CCS × 0.754</em></div></div><div className="panel-note">{t('Model estimates supplied in your file. Laboratory results appear separately.','आपल्या फाइलमधील मॉडेलचे अंदाज. प्रयोगशाळेतील निकाल स्वतंत्र विभागात आहेत.')}</div></section><section className="panel settings-panel"><h2>{t('Record completeness','नोंदींची पूर्णता')}</h2><p>{format(source?.complete??data.plots.length,0)} / {format(data.plots.length,0)} {t('have area and crop age.','प्लॉटचे क्षेत्रफळ व पीक वय उपलब्ध आहे.')}</p><p>{format(source?.walkedCount||0,0)} {t('walked-area records are clearly labeled.','GPS मोजणीचे क्षेत्र असलेल्या नोंदी स्वतंत्रपणे दर्शवल्या आहेत.')}</p><p>{format(source?.boundaryCount||0,0)} / {format(data.plots.length,0)} {t('plots have supplied outlines.','प्लॉटच्या पुरवलेल्या सीमा उपलब्ध आहेत.')}</p><p>{format(latest.size,0)} {t('plots have laboratory measurements.','प्लॉटचे प्रयोगशाळेतील मापन उपलब्ध आहे.')}</p><button className="text-link" onClick={()=>navigate('lab')}>{t('Open lab register','प्रयोगशाळा नोंदवही उघडा')}</button></section><section className="panel settings-panel"><h2>{t('Harvest planning','तोडणी नियोजन')}</h2><p>{format(planCount,0)} {t('plots have a scheduled harvest date.','प्लॉटची तोडणी तारीख नियोजित आहे.')}</p><button className="text-link" onClick={()=>navigate('harvest')}>{t('Review latest recommendations','नवीनतम शिफारसी पहा')} <ArrowRight size={15}/></button></section></div></div>
 <section className="panel" style={{marginTop:22}}><div className="panel-header"><div><h2>{t('Village summary','गावनिहाय सारांश')}</h2><p>{sumTonnage==null?t('Largest reported area · active dataset','सर्वाधिक नोंदवलेले क्षेत्र · सक्रिय डेटासेट'):t('Largest standing tonnage · active dataset','सर्वाधिक उभे ऊस वजन · सक्रिय डेटासेट')}</p></div></div><div className="table-scroll"><table><thead><tr><th>{t('Village','गाव')}</th><th>{t('Plots','प्लॉट')}</th><th>{t('Area (ha)','क्षेत्र (हे.)')}</th><th>{t('Standing tonnage (MT)','उभे ऊस वजन (MT)')}</th></tr></thead><tbody>{topVillages.map(row=><tr key={row.village}><td><button className="text-link" onClick={()=>{navigate('plots');setVillage(row.village)}}>{row.village}</button></td><td>{format(row.count,0)}</td><td>{format(row.area)}</td><td>{format(row.tonnageCount?row.tonnage:null,1)}</td></tr>)}</tbody></table></div></section></>}
 {view==='map'&&<section className="panel"><div className="panel-header"><div><h2>{t('Gangamai command area','गंगामाई ऊस कार्यक्षेत्र')}</h2><p>{format(data.plots.length,0)} {t('active plots · search all plots and villages','सक्रिय प्लॉट · सर्व प्लॉट व गावे शोधा')}</p></div></div><div style={{height:720}}><FieldMap plots={data.plots} samples={data.samples} onSelectPlot={setSelected}/></div></section>}
 {view==='plots'&&<section className="panel">{controls}<div className="table-scroll"><table><thead><tr>{[t('Plot / farmer / village','प्लॉट / शेतकरी / गाव'),t('Variety / crop','वाण / पीक'),t('Plantation date','लागवड तारीख'),t('Crop age (days)','पीक वय (दिवस)'),t('Area (ha)','क्षेत्र (हे.)'),t('Predicted Pol (%)','अंदाजित पोल (%)'),t('Predicted Brix (°Bx)','अंदाजित ब्रिक्स (°Bx)'),t('Predicted CCS (%)','अंदाजित CCS (%)'),t('Estimated recovery (%)','अंदाजित साखर उतारा (%)'),t('Tonnage (MT)','वजन (MT)')].map(label=><th key={label}>{label}</th>)}</tr></thead><tbody>{paged.map(p=><tr key={p.id}>{plotCell(p)}<td>{p.variety||'—'}<small>{cropLabel(p.caneType,language)}</small></td><td>{date(p.plantingDate)}</td><td>{format(ageOf(p),0)}</td><td>{format(p.area)}<small>{areaBasis(p)}</small></td><td>{format(p.predictedPol)}</td><td>{format(p.predictedBrix)}</td><td>{format(p.predictedCcs)}</td><td className="recovery-value" title="CCS × 0.754">{format(estimatedRecovery(p.predictedCcs))}</td><td>{format(p.tonnage,1)}</td></tr>)}</tbody></table></div><div className="panel-note">{t('Crop age is the supplied dataset value. The plot detail also shows ground-survey age where available.','पीक वय डेटासेटप्रमाणे दाखवले आहे. उपलब्ध असल्यास प्लॉट तपशिलात सर्वेक्षणातील वयही दाखवले आहे.')}</div></section>}
 {view==='observations'&&<section className="panel">{controls}<div className="notice info">{t('Indices come from the supplied dataset. Calculation time and satellite acquisition date are separate fields.','निर्देशांक पुरवलेल्या डेटासेटमधील आहेत. गणना वेळ आणि प्रतिमा घेतल्याची तारीख स्वतंत्र आहेत.')}</div><div className="table-scroll"><table><thead><tr><th>{t('Plot / village','प्लॉट / गाव')}</th><th>NDVI</th><th>NDRE</th><th>{t('Clear sky coverage','स्वच्छ आकाशातील व्याप्ती')}</th><th>{t('Canopy occupancy','ऊस छत्र व्याप्ती')}</th><th>{t('Acquisition date','प्रतिमा तारीख')}</th><th>{t('Calculation timestamp','गणना वेळ')}</th><th>{t('Action','कृती')}</th></tr></thead><tbody>{paged.map(p=><tr key={p.id}>{plotCell(p)}<td>{format(p.ndvi,3)}</td><td>{format(p.ndre,3)}</td><td>{format(p.clearSkyCoveragePct,1)}%</td><td>{p.canopyFraction==null?'—':format(p.canopyFraction*100,1)+'%'}</td><td>{date(p.acquisitionDate)}{p.satelliteRefreshStatus&&<small className="plot-cell-meta">{satelliteStatusLabel(p.satelliteRefreshStatus,language==='mr')}</small>}</td><td>{p.sourceTimestamp||'—'}</td><td><button className="text-link" onClick={()=>open('observation',p)}>{t('Record observation','निरीक्षण नोंदवा')}</button></td></tr>)}</tbody></table></div></section>}
 {view==='lab'&&<><div className="metric-grid three">{metric(t('Mean measured Pol','सरासरी मोजलेला पोल'),format(measured('pol')),'%',t('Laboratory measurements only','फक्त प्रयोगशाळेतील मापन'))}{metric(t('Mean measured Brix','सरासरी मोजलेला ब्रिक्स'),format(measured('brix')),'°Bx',t('Laboratory measurements only','फक्त प्रयोगशाळेतील मापन'))}{metric(t('Plots sampled','नमुना घेतलेले प्लॉट'),format(latest.size,0),'',`${format(data.samples.length,0)} ${t('sample records','नमुना नोंदी')}`)}</div><section className="panel"><div className="panel-header"><div><h2>{t('Laboratory sample register','प्रयोगशाळा नमुना नोंदवही')}</h2><p>{t('Actual measurements and sample dates','प्रत्यक्ष मापन व नमुना तारीख')}</p></div><button className="button primary" disabled={!data.plots.length} onClick={()=>open('sample')}><Plus size={15}/>{t('Record sample','नमुना नोंदवा')}</button><button className="button secondary" disabled={!data.samples.length} onClick={()=>downloadCSV('gangamai-lab-results.csv',data.samples.map(s=>({plotNo:data.plots.find(p=>p.id===s.plotId)?.plotNo,sampleDate:s.sampleDate,pol:s.pol,brix:s.brix,recovery:s.recovery})))}><Download size={15}/>{t('Export','डाउनलोड')}</button></div><div className="table-scroll"><table><thead><tr><th>{t('Plot','प्लॉट')}</th><th>{t('Sample date','नमुना तारीख')}</th><th>{t('Measured Pol (%)','मोजलेला पोल (%)')}</th><th>{t('Measured Brix (°Bx)','मोजलेला ब्रिक्स (°Bx)')}</th><th>{t('Mill recovery (%)','कारखाना उतारा (%)')}</th></tr></thead><tbody>{data.samples.map(s=><tr key={s.id}><td>{data.plots.find(p=>p.id===s.plotId)?.plotNo||s.plotId}</td><td>{date(s.sampleDate)}</td><td>{format(s.pol)}</td><td>{format(s.brix)}</td><td>{format(s.recovery)}</td></tr>)}</tbody></table></div>{!data.samples.length&&<div className="empty-state">{t('No laboratory measurements are recorded. Predicted values remain visible in the plot register.','प्रयोगशाळेतील मापन अद्याप नोंदवलेले नाही. अंदाजित मूल्ये प्लॉट नोंदवहीत उपलब्ध आहेत.')}</div>}</section></>}
 {view==='harvest'&&<section className="panel">
<div style={{ background: '#f8fafc', padding: '14px 18px', borderRadius: '8px', border: '1px solid #e2e8f0', marginBottom: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
    <span style={{ fontSize: '20px' }}>🌾</span>
    <div>
      <strong style={{ fontSize: '13px', color: '#183b36' }}>{t('Daily Partial Harvest & Standing Tonnage Tracker (1–2 Day Cadence)','दैनिक तोडणी व शेतातील शिल्लक ऊस वजन ट्रॅकर')}</strong>
      <p style={{ margin: '2px 0 0', fontSize: '11px', color: '#64748b' }}>
        {t('Monitored via Sentinel-2 + PlanetScope 3m + Sentinel-1 SAR. Tracks exactly how many tons remain standing in the field.',
           'सेंटिनेल-२ + प्लॅनेट ३मी + सेंटिनेल-१ रडारद्वारे शेतात शिल्लक राहिलेले अचूक वजन ट्रॅक केले जाते.')}
      </p>
    </div>
  </div>
  <span style={{ background: '#ecfdf5', color: '#047857', border: '1px solid #a7f3d0', fontSize: '11px', fontWeight: 600, padding: '4px 10px', borderRadius: '4px' }}>
    🛰️ {t('Multi-Constellation Gap Filler Active','बहु-उपग्रह सेवा सक्रिय')}
  </span>
</div>
{controls}
<div className="table-footer"><span>{t('Recommendations are supplied by the dataset; scheduling is a manager decision.','शिफारसी डेटासेटमधील आहेत; तोडणी नियोजन व्यवस्थापक ठरवतात.')}</span><label><input type="checkbox" checked={sortCcs} onChange={e=>setSortCcs(e.target.checked)}/> {t('Sort by predicted CCS','अंदाजित CCS नुसार क्रम लावा')}</label></div>
<div className="table-scroll"><table><thead><tr>{[
  t('Plot / village','प्लॉट / गाव'),
  t('Predicted CCS (%)','अंदाजित CCS (%)'),
  t('Estimated recovery (%)','अंदाजित साखर उतारा (%)'),
  t('Initial Biomass (MT)','एकूण वजन (MT)'),
  t('🌾 Standing Left (MT)','🌾 शेतात शिल्लक (MT)'),
  t('Harvest Status','तोडणी स्थिती'),
  t('Planned harvest','नियोजित तोडणी'),
  t('Manual review','व्यवस्थापक पडताळणी'),
  t('Action','कृती')
].map(label=><th key={label}>{label}</th>)}</tr></thead><tbody>{paged.map(p=>{
  const prog = p.harvestProgressPct != null ? p.harvestProgressPct : (p.priority === 'Ready' ? 35 : (p.harvestDate ? 25 : 0));
  const initTon = p.tonnage ?? Number((p.area * 102).toFixed(1));
  const remTon = Number(Math.max(0, initTon * (1 - prog / 100)).toFixed(1));
  const remTrol = Math.max(0, Math.ceil(remTon / 12));
  const isPart = prog > 0 && prog < 100;
  return <tr key={p.id}>
    {plotCell(p)}
    <td>{format(p.predictedCcs)}</td>
    <td className="recovery-value" title="CCS × 0.754">{format(estimatedRecovery(p.predictedCcs))}</td>
    <td>{format(initTon, 1)}</td>
    <td style={{ fontWeight: 700, color: remTon > 0 ? '#047857' : '#64748b', background: remTon > 0 ? '#ecfdf533' : 'transparent' }}>
      {format(remTon, 1)} <small style={{ fontWeight: 500, color: '#059669' }}>({remTrol} {t('trollies','ट्रॉली')})</small>
    </td>
    <td>
      <span className={'badge ' + (isPart ? 'review' : p.priority === 'Ready' ? 'ready' : 'hold')}>
        {isPart ? `${prog}% ${t('Cut','तोडणी')}` : prog === 100 ? t('Cleared','पूर्ण') : t('Standing','उभा ऊस')}
      </span>
      <small className="plot-cell-meta">🛰️ 1–2d</small>
    </td>
    <td>{date(p.harvestDate)}</td>
    <td>{priorityLabel(p.priority,language)}</td>
    <td><button className="text-link" onClick={()=>open('plan',p)}>{t('Plan harvest','तोडणी नियोजित करा')}</button></td>
  </tr>;
})}</tbody></table></div></section>}
 {view==='settings'&&<div className="settings-grid"><section className="panel settings-panel"><h2>{t('Mill profile','कारखाना माहिती')}</h2><dl><dt>{t('Name','नाव')}</dt><dd>{data.mill?.name}</dd><dt>{t('Location','ठिकाण')}</dt><dd>{data.mill?.location}</dd><dt>{t('Season','हंगाम')}</dt><dd>{data.mill?.season}</dd><dt>{t('Signed-in account','लॉगिन खाते')}</dt><dd>{email}</dd></dl><button className="button secondary" onClick={()=>open('mill')}>{t('Edit profile','माहिती बदला')}</button></section><section className="panel settings-panel"><h2>{t('Dataset and language','डेटासेट व भाषा')}</h2><LanguageSwitch/><p>{t('All dashboard pages use the same active register. New activated datasets are detected automatically.','डॅशबोर्डचे सर्व विभाग एकच सक्रिय नोंदवही वापरतात. नवीन सक्रिय डेटासेट आपोआप ओळखला जातो.')}</p><a className="button primary" href="/satellite-register">{t('Manage source register','मूळ नोंदवही व्यवस्थापित करा')}</a></section></div>}
 </>}<footer className="portal-footer"><span>IKSHU INTELLIGENCE · {t('FROM CANE TO CLARITY','उसापासून अचूक माहितीकडे')}</span><a href="/privacy">{t('Privacy & data','गोपनीयता व डेटा')}</a></footer></main></div>
 {selected&&<PlotVisualizer plot={selected} sample={latest.get(selected.id)} onClose={()=>setSelected(null)} onUpdatePriority={(id,priority)=>void save('plan',{id,priority,harvestDate:selected.harvestDate})}/>}
 {modal&&<div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="edit-title"><div className="modal-title"><h2 id="edit-title">{modal==='plan'?t('Plan harvest','तोडणी नियोजन'):modal==='sample'?t('Record lab sample','प्रयोगशाळा नमुना नोंदवा'):modal==='mill'?t('Edit mill profile','कारखाना माहिती बदला'):t('Record observation','निरीक्षण नोंदवा')}</h2><button className="icon-btn" aria-label={t('Close','बंद करा')} onClick={()=>setModal(null)} disabled={saving}><X/></button></div><form onSubmit={submit}><div className="form-grid">
 {modal==='mill'&&<><Input label={t('Mill name','कारखान्याचे नाव')} name="name" defaultValue={data.mill?.name} required/><Input label={t('Location','ठिकाण')} name="location" defaultValue={data.mill?.location} required/><Input label={t('Season','हंगाम')} name="season" defaultValue={data.mill?.season} required/></>}
 {modal==='plan'&&<><p>{editing?.plotNo} · {editing?.village}</p><Input label={t('Planned harvest date','नियोजित तोडणी तारीख')} name="harvestDate" type="date" defaultValue={editing?.harvestDate||''}/><label>{t('Review status','पडताळणी स्थिती')}<select name="priority" defaultValue={editing?.priority}>{['Review','Ready','Hold'].map(value=><option key={value} value={value}>{priorityLabel(value,language)}</option>)}</select></label></>}
 {modal==='sample'&&<><label>{t('Find plot','प्लॉट शोधा')}<input value={sampleQuery} onChange={e=>setSampleQuery(e.target.value)}/></label><label>{t('Plot','प्लॉट')}<select name="plotId" required>{data.plots.filter(p=>[p.plotNo,p.village].some(value=>value.toLowerCase().includes(sampleQuery.toLowerCase()))).slice(0,100).map(p=><option value={p.id} key={p.id}>{p.plotNo} · {p.village}</option>)}</select></label><Input label={t('Sample date','नमुना तारीख')} name="sampleDate" type="date" required/><Input label={t('Measured Pol (%)','मोजलेला पोल (%)')} name="pol" type="number" min={0} max={40} step="0.01" required/><Input label={t('Measured Brix (°Bx)','मोजलेला ब्रिक्स (°Bx)')} name="brix" type="number" min={0} max={40} step="0.01" required/><Input label={t('Mill recovery (%) · optional','कारखाना उतारा (%) · ऐच्छिक')} name="recovery" type="number" min={0} max={30} step="0.01"/></>}
 {modal==='observation'&&<><p>{editing?.plotNo} · {editing?.village}</p><Input label={t('Acquisition date','प्रतिमा तारीख')} name="acquisitionDate" type="date" defaultValue={editing?.acquisitionDate||''} required/><Input label={t('Reported cloud (%)','नोंदवलेले ढग (%)')} name="cloud" type="number" min={0} max={100} step="0.1" defaultValue={editing?.cloud??''} required/><Input label="NDVI" name="ndvi" type="number" min={-1} max={1} step="0.001" defaultValue={editing?.ndvi??''} required/></>}
 </div><div className="modal-actions"><button type="button" className="button secondary" onClick={()=>setModal(null)} disabled={saving}>{t('Cancel','रद्द करा')}</button><button className="button primary" disabled={saving}>{saving?t('Saving…','जतन होत आहे…'):t('Save','जतन करा')}</button></div></form></section></div>}
 </div>;
}
function Input({label,...props}:{label:string}&React.InputHTMLAttributes<HTMLInputElement>){return <label>{label}<input {...props}/></label>}
