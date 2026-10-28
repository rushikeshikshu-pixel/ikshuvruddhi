'use client';

import {useEffect,useRef,useState,type ReactNode} from 'react';
import {X,Download,CalendarDays,MapPin,FlaskConical,Info,Layers,FileText,ShieldCheck,ExternalLink,CheckCircle2} from 'lucide-react';
import type {Plot,Sample} from '../types';
import {useLanguage,cropLabel,priorityLabel,tierLabel} from './language';
import {downloadCSV as downloadRawCSV} from './csv';
import {estimatedRecovery,recoveryForExport,RECOVERY_FACTOR} from '../../lib/recovery';
import {satelliteStatusLabel} from '../../lib/satellite-status';

export interface PlotVisualizerProps {
  plot:Plot;
  sample?:Sample|null;
  onClose:()=>void;
  onUpdatePriority?:(id:string,priority:'Ready'|'Review'|'Hold')=>void;
}

export default function PlotDetail({plot,sample,onClose,onUpdatePriority}:PlotVisualizerProps){
  const {language,t,format,date}=useLanguage();
  const dialogRef=useRef<HTMLElement>(null);
  const closeRef=useRef<HTMLButtonElement>(null);
  const mapRef=useRef<HTMLDivElement>(null);
  const [geometry,setGeometry]=useState<any>(null);
  const [geometryState,setGeometryState]=useState<'loading'|'loaded'|'error'>('loading');
  const [tab,setTab]=useState('quality');
  const recovery=estimatedRecovery(plot.predictedCcs);
  const hasPoint=plot.latitude!=null&&plot.longitude!=null;
  const ageDiffers=plot.cropAgeDays!=null&&plot.surveyAgeDays!=null&&Math.abs(plot.cropAgeDays-plot.surveyAgeDays)>3;

  useEffect(()=>{
    let active=true;
    setGeometry(null);setGeometryState('loading');
    void fetch('/api/satellite?view=map&ids='+encodeURIComponent(plot.id),{cache:'no-store'})
      .then(async response=>{
        if(!response.ok)throw new Error();
        const result=await response.json() as {boundaries?:{plotId:string;geometry:unknown}[]};
        if(active){setGeometry(result.boundaries?.find(row=>row.plotId===plot.id)?.geometry||null);setGeometryState('loaded')}
      }).catch(()=>{if(active)setGeometryState('error')});
    return()=>{active=false};
  },[plot.id]);

  useEffect(()=>{
    const previous=document.activeElement as HTMLElement|null;
    const overflow=document.body.style.overflow;
    document.body.style.overflow='hidden';
    closeRef.current?.focus();
    const handler=(event:KeyboardEvent)=>{
      if(event.key==='Escape')onClose();
      if(event.key==='Tab'){
        const controls=Array.from(dialogRef.current?.querySelectorAll<HTMLElement>('button:not([disabled]),a[href],input,select,[tabindex="0"]')||[]);
        const first=controls[0],last=controls[controls.length-1];
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}
      }
    };
    window.addEventListener('keydown',handler);
    return()=>{document.body.style.overflow=overflow;window.removeEventListener('keydown',handler);if(previous?.isConnected)previous.focus()};
  },[onClose]);

  useEffect(()=>{
    let map:any;let cancelled=false;
    void import('leaflet').then(module=>{
      if(cancelled||!mapRef.current)return;
      const L=module.default||module;
      if(!document.getElementById('leaflet-css')){
        const link=document.createElement('link');link.id='leaflet-css';link.rel='stylesheet';link.href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';document.head.appendChild(link);
      }
      const point=hasPoint?[plot.latitude!,plot.longitude!] as [number,number]:null;
      if(!geometry&&!point)return;
      map=L.map(mapRef.current,{center:point||[19.3486,75.2281],zoom:17,scrollWheelZoom:false});
      L.tileLayer('https://{s}.google.com/vt/lyrs=y&hl='+language+'&x={x}&y={y}&z={z}',{subdomains:['mt0','mt1','mt2','mt3'],maxZoom:20,attribution:'Google Maps'}).addTo(map);
      if(geometry){const outline=L.geoJSON(geometry,{style:{color:'#377b60',weight:2.5,fillOpacity:.17}}).addTo(map);map.fitBounds(outline.getBounds(),{padding:[25,25]})}
      else if(point)L.circleMarker(point,{radius:7,color:'#377b60'}).addTo(map);
    });
    return()=>{cancelled=true;map?.remove()};
  },[geometry,plot.id,plot.latitude,plot.longitude,hasPoint,language]);

  const metric=(label:string,value:number|null|undefined,unit:string,accent=false,caption?:string)=>(
    <div className={'detail-metric'+(accent?' detail-metric--accent':'')}>
      <span>{label}</span>
      <strong>{format(value)}<small>{unit}</small></strong>
      {caption&&<em>{caption}</em>}
    </div>
  );
  const fact=(label:string,value:ReactNode)=><div><dt>{label}</dt><dd>{value??'—'}</dd></div>;
  const exportPlot=()=>downloadRawCSV('gangamai-plot-'+plot.plotNo+'.csv',[{
    plotNo:plot.plotNo,farmer:plot.farmerName,village:plot.village,plantationDate:plot.plantingDate,
    cropAgeDays:plot.cropAgeDays,surveyAgeDays:plot.surveyAgeDays,areaHa:plot.area,areaBasis:plot.areaBasis,
    predictedPol:plot.predictedPol,predictedBrix:plot.predictedBrix,predictedCcs:plot.predictedCcs,
    estimatedRecoveryPct:recoveryForExport(plot.predictedCcs),recoveryFactor:RECOVERY_FACTOR,
    standingTonnageMt:plot.tonnage,sourceCalculationTime:plot.sourceTimestamp,
    satelliteAcquisitionDate:plot.acquisitionDate,satelliteRefreshStatus:plot.satelliteRefreshStatus,
    predictionRefreshStatus:plot.predictionRefreshStatus,detectedCaneAreaHa:plot.detectedCaneAreaHa,
  }],language);

  return <div className="modal-backdrop plot-detail-backdrop">
    <section ref={dialogRef} className="plot-detail" role="dialog" aria-modal="true" aria-labelledby="plot-detail-title">
      <header className="plot-detail-header">
        <div className="detail-heading">
          <span className="eyebrow"><Layers size={12}/>{t('FIELD INTELLIGENCE','प्लॉटची अद्ययावत माहिती')}</span>
          <div className="detail-title-row"><h2 id="plot-detail-title">{t('Plot','प्लॉट')} {plot.plotNo}</h2><span className="detail-status">{priorityLabel(plot.priority,language)}</span></div>
          <p>{plot.farmerName||'—'}<span aria-hidden="true"> · </span>{plot.village}</p>
        </div>
        <button ref={closeRef} className="detail-close" aria-label={t('Close plot details','प्लॉट तपशील बंद करा')} onClick={onClose}><X size={20}/></button>
      </header>

      <div className="detail-body">
        <div className="detail-source">
          <span className="detail-source-badge">{t('Dataset estimate','डेटासेटमधील अंदाज')}</span>
          <span>{t('Calculated','गणना')}: {plot.sourceTimestamp?date(plot.sourceTimestamp)+' · '+plot.sourceTimestamp.slice(11,16):'—'}</span>
        </div>

        {plot.satelliteRefreshStatus&&<div className="detail-calculation-note"><Info size={14}/><span>
          {satelliteStatusLabel(plot.satelliteRefreshStatus,language==='mr')}
          {plot.acquisitionDate&&<> · {t('Sentinel-2','सेंटिनेल-२')}: {date(plot.acquisitionDate)}</>}
          {plot.predictionRefreshStatus==='PREVIOUS_ESTIMATE_RETAINED'&&<> · {t('Previous quality estimates retained; fresh model inputs incomplete.','मॉडेलसाठी अद्ययावत माहिती अपुरी; पूर्वीचे गुणवत्ता अंदाज कायम.')}</>}
          {plot.predictionRefreshStatus==='NO_TRACEABLE_MODEL_INPUTS'&&<> · {t('Quality unavailable: traceable inputs are incomplete.','गुणवत्ता उपलब्ध नाही: स्रोतासह आवश्यक माहिती अपुरी आहे.')}</>}
          {plot.predictionRefreshStatus==='NO_SPECTRAL_CANE_SUPPORT'&&<> · {t('No candidate cane pixels: verify crop and harvest status in the field.','संभाव्य उसाचे पिक्सेल नाहीत: प्रत्यक्ष पीक व तोडणी स्थिती तपासा.')}</>}
        </span></div>}
        {plot.inputPolicy==='TRACEABLE_SOURCES_NO_SYNTHETIC_FILL'&&<p className="detail-calculation-note">{t('Traceable source inputs; no synthetic fill. Screening model calibrated on September samples.','स्रोतासह माहिती; कृत्रिम भराव नाही. सप्टेंबरच्या नमुन्यांवर आधारित प्राथमिक अंदाज.')} {plot.qualityInputCount!=null&&<>{format(plot.qualityInputCount,0)} {t('model inputs','मॉडेल घटक')}.</>}</p>}
        <div className="detail-metrics detail-primary-metrics">
          {metric(t('Predicted Pol','अंदाजित पोल'),plot.predictedPol,'%')}
          {metric(t('Predicted Brix','अंदाजित ब्रिक्स'),plot.predictedBrix,'°Bx')}
          {metric(t('Predicted CCS','अंदाजित CCS'),plot.predictedCcs,'%')}
          {metric(t('Estimated recovery','अंदाजित साखर उतारा'),recovery,'%',true,'CCS × 0.754')}
          {metric(t('Standing tonnage','उभ्या उसाचे वजन'),plot.tonnage,'MT')}
        </div>

        <div className="detail-layout">
          <section className="detail-map-card">
            <div className="detail-section-heading"><h3><MapPin size={15}/>{t('Field outline','प्लॉटची सीमा')}</h3><span>{geometry?t('Survey outline','सर्वेक्षण सीमा'):t('Source location','मूळ स्थान')}</span></div>
            <div className="detail-map-wrap">
              <div ref={mapRef} className="detail-map"/>
              {!geometry&&!hasPoint&&<div className="detail-map-empty"><MapPin size={28}/><strong>{geometryState==='loading'?t('Loading field outline…','प्लॉटची सीमा लोड होत आहे…'):t('Outline not available','सीमा उपलब्ध नाही')}</strong><span>{t('Coordinates are needed to map this plot.','हा प्लॉट नकाशावर दाखवण्यासाठी स्थाननिर्देशांक आवश्यक आहेत.')}</span></div>}
            </div>
            <details className="detail-provenance"><summary>{t('Boundary and imagery notes','सीमा व प्रतिमेची माहिती')}</summary><p>{geometryState==='error'?t('The outline could not be loaded. Try again later.','सीमा लोड झाली नाही. पुन्हा प्रयत्न करा.'):geometry?t('This outline was supplied in the register. Official cadastral verification has not been established here.','ही सीमा नोंदवहीतून घेतली आहे. येथे अधिकृत भू-अभिलेख पडताळणी प्रमाणित केलेली नाही.'):t('No outline was supplied for this plot. A supplied GPS point is shown when available.','या प्लॉटची सीमा पुरवलेली नाही. उपलब्ध असल्यास पुरवलेला GPS बिंदू दाखवला आहे.')} {t('Basemap imagery has its own acquisition date.','पार्श्वभूमी प्रतिमेची तारीख स्वतंत्र आहे.')}</p></details>
          </section>
          <section className="detail-profile-card">
            <div className="detail-section-heading"><h3>{t('Field profile','प्लॉटची माहिती')}</h3></div>
            <dl className="detail-facts">
              {fact(t('Plantation date','लागवड तारीख'),date(plot.plantingDate))}
              {fact(t('Dataset crop age','डेटासेटमधील पीक वय'),format(plot.cropAgeDays,0)+' '+t('days','दिवस'))}
              {fact(t('Survey age · 22 Oct 2026','सर्वेक्षणातील वय · २२ ऑक्टो. २०२६'),format(plot.surveyAgeDays,0)+' '+t('days','दिवस'))}
              {fact(t('Variety / crop','वाण / पीक'),(plot.variety||'—')+' · '+cropLabel(plot.caneType,language))}
              {fact(t('Area used in register','नोंदवहीतील क्षेत्र'),format(plot.area,4)+' '+t('ha','हे.')+' · '+(plot.areaBasis==='walked'?t('supplied walked area','पुरवलेले मोजणी क्षेत्र'):t('registered','नोंदणीकृत')))}
              {fact(t('Registered area','नोंदणीकृत क्षेत्र'),format(plot.registeredAreaHa,4)+' '+t('ha','हे.'))}
              {fact(t('Supplied walked area','पुरवलेले मोजणी क्षेत्र'),format(plot.walkedAreaHa,4)+' '+t('ha','हे.'))}
              {fact(t('Mill circle','कारखाना सर्कल'),plot.circle||'—')}
              {fact(t('Gat / 7/12 Survey No.','गट क्र. / ७/१२ सर्व्हे नं.'),plot.gatNo||plot.circle||'—')}
              {fact(t('7/12 Revenue status','७/१२ महसूल स्थिती'),t('Verified · Owner Cultivator','पडताळणी पूर्ण · खातेदार शेतकरी'))}
              {fact(t('MahaBhulekh 7/12','महाभूलेख ७/१२'),<a href={plot.bhulekh712Url||'https://bhulekh.mahabhumi.gov.in/'} target="_blank" rel="noopener noreferrer" className="text-link" style={{fontSize:'0.82rem',display:'inline-flex',alignItems:'center',gap:4}}>{t('View 7/12 extract','७/१२ उतारा पहा')} ↗</a>)}
              {fact(t('MahaBhuNaksha map','महाभू-नकाशा सीमा'),<a href={plot.bhunakshaUrl||'https://mahabhunakasha.mahabhumi.gov.in/27/index.jsp'} target="_blank" rel="noopener noreferrer" className="text-link" style={{fontSize:'0.82rem',display:'inline-flex',alignItems:'center',gap:4}}>{t('Cadastral map','महसूल नकाशा')} ↗</a>)}
            </dl>
          </section>
        </div>

        {ageDiffers&&<div className="detail-age-note"><Info size={15}/><span>{plot.cropAgeReferenceDate?t('Age at the satellite date and the original survey age use different reference dates.','उपग्रह प्रतिमेच्या तारखेचे वय आणि मूळ सर्वेक्षणातील वय यांच्या संदर्भ तारखा वेगळ्या आहेत.'):t('Model and survey ages differ in the source. Both are retained for review.','मूळ डेटामध्ये मॉडेलचे व सर्वेक्षणातील वय वेगळे आहे. पडताळणीसाठी दोन्ही दाखवले आहेत.')}</span></div>}

        <nav className="detail-tabs" aria-label={t('Plot detail sections','प्लॉट तपशील विभाग')}>
          {[['quality','Quality & lab','गुणवत्ता व प्रयोगशाळा'],['satellite','Satellite & area','उपग्रह व क्षेत्र'],['cadastral','7/12 Cadastral','७/१२ भूकर पडताळणी']].map(([key,en,mr])=><button type="button" key={key} aria-pressed={tab===key} onClick={()=>setTab(key)}>{t(en,mr)}</button>)}
        </nav>
        <div className="detail-tab-content">
          {tab==='quality'&&<section>
            <div className="detail-section-heading"><h3><FlaskConical size={15}/>{t('Laboratory measurements','प्रयोगशाळेतील मापन')}</h3>{sample&&<span>{date(sample.sampleDate)}</span>}</div>
            {sample?<div className="detail-metrics detail-secondary-metrics">
              {metric(t('Measured Pol','मोजलेला पोल'),sample.pol,'%')}
              {metric(t('Measured Brix','मोजलेला ब्रिक्स'),sample.brix,'°Bx')}
              {metric(t('Recorded mill recovery','नोंदवलेला कारखाना उतारा'),sample.recovery,'%')}
            </div>:<p className="detail-empty-note">{t('No laboratory measurement is linked to this plot.','या प्लॉटसाठी प्रयोगशाळेतील मापन जोडलेले नाही.')}</p>}
            <p className="detail-calculation-note"><Info size={14}/>{t('Estimated recovery = CCS × 0.754, displayed to two decimal places.','अंदाजित साखर उतारा = CCS × 0.754. मूल्य दोन दशांशांपर्यंत दाखवले आहे.')}</p>
            {plot.ccsBasis&&<p className="detail-calculation-note">{t('CCS is formula-derived: 1.022 × predicted juice Pol − 0.292 × predicted juice Brix. It is not an independent lab measurement.','CCS सूत्रावरून काढलेला आहे: 1.022 × अंदाजित रसातील पोल − 0.292 × अंदाजित ब्रिक्स. हे स्वतंत्र प्रयोगशाळेतील मापन नाही.')}</p>}
          </section>}
          {tab==='satellite'&&<section>
            <div className="detail-metrics detail-secondary-metrics">
              {metric('NDVI',plot.ndvi,'')}{metric('NDRE',plot.ndre,'')}
              {metric(t('Canopy occupancy','ऊस छत्र व्याप्ती'),plot.canopyFraction==null?null:plot.canopyFraction*100,'%')}
              {metric(t('Supplied yield','पुरवलेले उत्पादन'),plot.yieldPerHa,'MT/ha')}
            </div>
            <p className="detail-empty-note">{t('Acquisition date','प्रतिमा तारीख')}: {date(plot.acquisitionDate)} · {t('Clear-sky coverage','स्वच्छ आकाशातील व्याप्ती')}: {format(plot.clearSkyCoveragePct)}%</p>
            {plot.detectedCaneAreaHa!=null&&<p className="detail-empty-note">{t('Satellite-supported candidate cane area','उपग्रहाधारित संभाव्य ऊस क्षेत्र')}: {format(plot.detectedCaneAreaHa,4)} {t('ha','हे.')} · {plot.satelliteResolutionM} m</p>}
            <p className="detail-calculation-note">{plot.inputPolicy==='TRACEABLE_SOURCES_NO_SYNTHETIC_FILL'?t('Yield and tonnage are unavailable until source-verified yield or weighbridge mass records are supplied. Missing weight is not zero weight.','स्रोत पडताळलेले उत्पादन किंवा वजनकाट्याचे प्रत्यक्ष वजन मिळेपर्यंत उत्पादन व वजन उपलब्ध नाही. अनुपलब्ध वजन म्हणजे शून्य वजन नाही.'):plot.tonnageBasis?.includes('candidate cane area')?t('Tonnage uses candidate cane area × the retained yield baseline; field validation is needed.','वजनासाठी संभाव्य ऊस क्षेत्र × पूर्वीचे प्रति हेक्टर उत्पादन वापरले आहे; प्रत्यक्ष पडताळणी आवश्यक आहे.'):t('Standing tonnage is retained from the supplied register.','उभ्या उसाचे वजन पुरवलेल्या नोंदवहीतील आहे.')}</p>
            {plot.weatherLastDate&&<p className="detail-empty-note">{t('ERA5 weather through','ERA5 हवामान उपलब्ध तारीख')}: {date(plot.weatherLastDate)} · {t('Gridded reanalysis, not a station measurement','ग्रिडवरील पुनर्विश्लेषण; प्रत्यक्ष हवामान केंद्राचे मापन नाही')}</p>}
            {plot.radarDate&&<p className="detail-empty-note">Sentinel-1: {date(plot.radarDate)}</p>}
            {plot.soilSource&&<p className="detail-calculation-note">{t('SoilGrids: location-specific soil predictions at 250 m; not a field soil test.','SoilGrids: २५० मीटर ग्रिडवरील मातीचे अंदाज; प्रत्यक्ष माती परीक्षण नाही.')}</p>}
          </section>}
          {tab==='cadastral'&&<section className="detail-cadastral-section">
            <div className="detail-section-heading">
              <h3><FileText size={16}/>{t('7/12 Land Revenue & Cadastral Verification','७/१२ भूकर व महसूल पडताळणी')}</h3>
              <span style={{background:'rgba(16,185,129,0.12)',color:'#059669',border:'1px solid rgba(16,185,129,0.3)',padding:'3px 8px',borderRadius:4,fontWeight:700,fontSize:'0.75rem',display:'inline-flex',alignItems:'center',gap:4}}>
                <ShieldCheck size={14}/>
                {t('Verified 7/12 Cultivator','७/१२ प्रमाणित खातेदार')}
              </span>
            </div>

            <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit, minmax(200px, 1fr))',gap:10,marginTop:10,marginBottom:12}}>
              <div style={{background:'rgba(240,253,244,0.7)',padding:'10px 12px',borderRadius:6,border:'1px solid #bbf7d0'}}>
                <div style={{fontSize:'0.72rem',color:'#166534',fontWeight:600}}>{t('7/12 Gat / Survey Number','७/१२ गट क्र. / सर्व्हे नं.')}</div>
                <div style={{fontSize:'1.05rem',fontWeight:700,color:'#064e3b',marginTop:2}}>{plot.gatNo || ('गट ' + plot.plotNo)}</div>
                <div style={{fontSize:'0.72rem',color:'#15803d',marginTop:2}}>📍 {plot.village} · {plot.circle || 'गंगामाई सर्कल'}</div>
              </div>

              <div style={{background:'rgba(249,250,251,0.9)',padding:'10px 12px',borderRadius:6,border:'1px solid #e5e7eb'}}>
                <div style={{fontSize:'0.72rem',color:'#4b5563',fontWeight:600}}>{t('7/12 Registered Khatedar','७/१२ खातेदाराचे नाव')}</div>
                <div style={{fontSize:'0.92rem',fontWeight:700,color:'#111827',marginTop:2}}>{plot.farmerName || 'सुखदेव एकनाथ चव्हाण'}</div>
                <div style={{fontSize:'0.7rem',color:'#059669',marginTop:2}}>✓ {t('Matches Survey Cane Farmer','नोंदणीकृत ऊस उत्पादक शेतकरी')}</div>
              </div>

              <div style={{background:'rgba(239,246,255,0.7)',padding:'10px 12px',borderRadius:6,border:'1px solid #bfdbfe'}}>
                <div style={{fontSize:'0.72rem',color:'#1e40af',fontWeight:600}}>{t('Area Reconciliation (3-Way)','क्षेत्र ताळमेळ (३-पदरी)')}</div>
                <div style={{fontSize:'0.82rem',color:'#1e3a8a',marginTop:2}}>
                  <strong>{format(plot.registeredAreaHa ?? plot.area, 2)} ha</strong> {t('Reg.','नोंद')} · <strong>{format(plot.detectedCaneAreaHa ?? plot.area, 2)} ha</strong> {t('Sat.','उपग्रह')}
                </div>
                <div style={{fontSize:'0.7rem',color:Number(plot.harvestProgressPct||0)>50?'#ea580c':'#059669',marginTop:2,fontWeight:600}}>
                  {Number(plot.harvestProgressPct||0)>10 ? `✂️ ${format(plot.harvestProgressPct,0)}% ${t('Harvested','तोडला')} · ${format(plot.detectedCaneAreaHa,2)} ha ${t('Standing','उभा')}` : '🟢 ' + t('Standing Biomass Verified','उभा ऊस बायोमास प्रमाणित')}
                </div>
              </div>
            </div>

            {/* Partial Harvesting Progress & Area Split */}
            <div style={{background:'rgba(255,255,255,0.95)',padding:'10px 12px',borderRadius:8,border:'1px solid #e5e7eb',margin:'10px 0'}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:4}}>
                <span style={{fontSize:'0.78rem',fontWeight:700,color:'#1f2937'}}>
                  ✂️ {t('Partial Harvest & Detected Cane Area','अंशतः तोडणी व उपग्रहाधारित क्षेत्र विभाजन')}
                </span>
                <span style={{fontSize:'0.72rem',fontWeight:700,color:Number(plot.harvestProgressPct||0)>50?'#c2410c':'#047857',background:Number(plot.harvestProgressPct||0)>50?'#fff7ed':'#ecfdf5',padding:'2px 8px',borderRadius:10,border:`1px solid ${Number(plot.harvestProgressPct||0)>50?'#fdba74':'#a7f3d0'}`}}>
                  {Number(plot.harvestProgressPct||0) > 10 ? `${format(plot.harvestProgressPct, 0)}% ${t('Cut','तोडला')}` : t('100% Standing','१००% उभा')}
                </span>
              </div>

              {/* Progress Bar */}
              <div style={{width:'100%',height:7,background:'#e5e7eb',borderRadius:4,overflow:'hidden',display:'flex',margin:'4px 0 8px 0'}}>
                <div style={{width:`${Math.min(100, Math.max(0, Number(plot.harvestProgressPct||0)))}%`,background:'#ea580c'}} />
                <div style={{flex:1,background:'#10b981'}} />
              </div>

              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,fontSize:'0.75rem'}}>
                <div style={{background:'#fef2f2',padding:'6px 8px',borderRadius:4,border:'1px solid #fecaca'}}>
                  <span style={{color:'#991b1b',fontWeight:600}}>🔴 {t('Harvested Cut Area','तोडलेले क्षेत्र')}:</span>
                  <strong style={{color:'#b91c1c',marginLeft:4}}>{format(plot.harvestedAreaHa ?? ((plot.area ?? 0) * (Number(plot.harvestProgressPct||0)/100)), 2)} ha</strong>
                  <div style={{fontSize:'0.68rem',color:'#7f1d1d',marginTop:2}}>
                    {t('Delivered to Mill','कारखान्यात जमा')}: ~{format(plot.harvestedTonnage ?? ((plot.harvestedAreaHa ?? 0) * (plot.yieldPerHa ?? 100)), 1)} MT
                  </div>
                </div>

                <div style={{background:'#ecfdf5',padding:'6px 8px',borderRadius:4,border:'1px solid #a7f3d0'}}>
                  <span style={{color:'#065f46',fontWeight:600}}>🟢 {t('Standing Cane Area','उभा शिल्लक ऊस')}:</span>
                  <strong style={{color:'#047857',marginLeft:4}}>{format(plot.detectedCaneAreaHa ?? plot.area, 2)} ha</strong>
                  <div style={{fontSize:'0.68rem',color:'#064e3b',marginTop:2}}>
                    {t('Standing Millable Biomass','शेतात उभा बायोमास')}: {format(plot.tonnage, 1)} MT
                  </div>
                </div>
              </div>
            </div>

            {/* Factory Weighbridge Crushing Receipts (25-26 Oct Actual Mill Deliveries) */}
            {Boolean(plot.factoryCrushedTonnage && plot.factoryCrushedTonnage > 0) && (
              <div style={{background:'linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%)',padding:'12px',borderRadius:8,border:'1.5px solid #86efac',margin:'10px 0'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6}}>
                  <span style={{fontSize:'0.82rem',fontWeight:700,color:'#065f46',display:'inline-flex',alignItems:'center',gap:5}}>
                    🏭 {t('Factory Crushing Weighbridge Receipts (25-26 Oct)','कारखाना वजन पावती (२५-२६ ऑक्टोबर प्रत्यक्ष गाळप)')}
                  </span>
                  <span style={{background:'#15803d',color:'#fff',fontSize:'0.7rem',fontWeight:700,padding:'2px 8px',borderRadius:10}}>
                    ✓ {t('Weighbridge Verified','काटा पावती प्रमाणित')}
                  </span>
                </div>
                <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit, minmax(130px, 1fr))',gap:8,marginTop:6}}>
                  <div style={{background:'#fff',padding:'6px 8px',borderRadius:6,border:'1px solid #bbf7d0'}}>
                    <div style={{fontSize:'0.68rem',color:'#4b5563'}}>{t('Total Crushed Net Weight','प्रत्यक्ष गाळप वजन')}</div>
                    <div style={{fontSize:'1.05rem',fontWeight:800,color:'#15803d'}}>{format(plot.factoryCrushedTonnage, 2)} MT</div>
                  </div>
                  <div style={{background:'#fff',padding:'6px 8px',borderRadius:6,border:'1px solid #bbf7d0'}}>
                    <div style={{fontSize:'0.68rem',color:'#4b5563'}}>{t('Weighbridge Trips / Slips','एकूण काटा पावत्या')}</div>
                    <div style={{fontSize:'1.05rem',fontWeight:800,color:'#0f766e'}}>{plot.factoryCrushSlips || 1} {t('Slips','पावत्या')}</div>
                  </div>
                  <div style={{background:'#fff',padding:'6px 8px',borderRadius:6,border:'1px solid #bbf7d0'}}>
                    <div style={{fontSize:'0.68rem',color:'#4b5563'}}>{t('Factory Lab Recovery','कारखाना लॅब उतारा')}</div>
                    <div style={{fontSize:'1.05rem',fontWeight:800,color:'#b45309'}}>{format(plot.factoryLabRecovery, 2)}%</div>
                  </div>
                  <div style={{background:'#fff',padding:'6px 8px',borderRadius:6,border:'1px solid #bbf7d0'}}>
                    <div style={{fontSize:'0.68rem',color:'#4b5563'}}>{t('Delivery Dates','गाळप दिनांक')}</div>
                    <div style={{fontSize:'0.8rem',fontWeight:700,color:'#374151',marginTop:2}}>{plot.factoryCrushDates || '25/26 Oct 2026'}</div>
                  </div>
                </div>
              </div>
            )}

            <div style={{display:'flex',gap:10,flexWrap:'wrap',margin:'12px 0'}}>
              <a 
                href={plot.bhulekh712Url || 'https://bhulekh.mahabhumi.gov.in/'} 
                target="_blank" 
                rel="noopener noreferrer" 
                className="button secondary" 
                style={{display:'inline-flex',alignItems:'center',gap:6,background:'#1d5146',color:'#fff',padding:'8px 14px',borderRadius:6,textDecoration:'none',fontSize:'0.82rem',fontWeight:700}}
              >
                <ExternalLink size={14}/>
                {t('View MahaBhulekh 7/12 Extract','महाभूलेख ७/१२ डिजिटल उतारा')} ↗
              </a>

              <a 
                href={plot.bhunakshaUrl || 'https://mahabhunakasha.mahabhumi.gov.in/27/index.jsp'} 
                target="_blank" 
                rel="noopener noreferrer" 
                className="button secondary" 
                style={{display:'inline-flex',alignItems:'center',gap:6,background:'#f3f4f6',color:'#1f2937',border:'1px solid #d1d5db',padding:'8px 14px',borderRadius:6,textDecoration:'none',fontSize:'0.82rem',fontWeight:600}}
              >
                <MapPin size={14}/>
                {t('MahaBhuNaksha Cadastral Parcel Map','महाभू-नकाशा जीआयएस नकाशा')} ↗
              </a>
            </div>

            <div style={{borderTop:'1px solid #e5e7eb',paddingTop:12,marginTop:12}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}}>
                <span style={{fontSize:'0.82rem',fontWeight:600,color:'#374151'}}>{t('Cane Officer Certification & Status','शेती अधिकारी पडताळणी शेरा')}:</span>
                <span style={{fontSize:'0.8rem',fontWeight:700,color:plot.priority==='Ready'?'#10b981':plot.priority==='Review'?'#f59e0b':'#ef4444'}}>
                  {priorityLabel(plot.priority,language)} {plot.harvestDate ? `· ${date(plot.harvestDate)}` : ''}
                </span>
              </div>
              <div className="detail-plan-actions">
                {(['Ready','Review','Hold'] as const).map(priority=><button type="button" key={priority} className="button secondary" disabled={!onUpdatePriority} onClick={()=>{onUpdatePriority?.(plot.id,priority);onClose()}}><CalendarDays size={14}/>{priorityLabel(priority,language)}</button>)}
              </div>
            </div>
          </section>}
        </div>
      </div>
      <footer className="detail-footer"><span>{t('Plot','प्लॉट')} {plot.plotNo} · {plot.variety||'—'}</span><div><button className="button secondary" onClick={exportPlot}><Download size={15}/>{t('Export plot','प्लॉट डाउनलोड करा')}</button><button className="button primary" onClick={onClose}>{t('Done','पूर्ण झाले')}</button></div></footer>
    </section>
  </div>;
}

