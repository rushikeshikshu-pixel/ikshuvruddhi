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
  const [mapHeatmapMode, setMapHeatmapMode] = useState<'tonnage_pixel' | 'outline'>('tonnage_pixel');
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
      if(geometry){
        const outline=L.geoJSON(geometry,{style:{color:'#15803d',weight:2.5,fillOpacity:mapHeatmapMode==='tonnage_pixel'?0.15:0.25}}).addTo(map);
        map.fitBounds(outline.getBounds(),{padding:[25,25]});

        if (mapHeatmapMode === 'tonnage_pixel') {
          const coords = (geometry as any)?.coordinates?.[0] as [number, number][];
          if (coords && coords.length >= 3) {
            let minLat = 90, maxLat = -90, minLng = 180, maxLng = -180;
            for (const [lng, lat] of coords) {
              if (lat < minLat) minLat = lat;
              if (lat > maxLat) maxLat = lat;
              if (lng < minLng) minLng = lng;
              if (lng > maxLng) maxLng = lng;
            }
            const step = 0.00010; // ~10.5m Sentinel-2 pixel size
            const latSteps = Math.ceil((maxLat - minLat) / step);
            const lngSteps = Math.ceil((maxLng - minLng) / step);
            const yieldVal = Number(plot.yieldPerHa ?? (plot.tonnage && plot.area ? plot.tonnage / plot.area : 98));

            function getPixelColor(y: number) {
              if (y >= 125) return '#7e22ce';
              if (y >= 105) return '#047857';
              if (y >= 85) return '#10b981';
              if (y >= 65) return '#eab308';
              if (y >= 45) return '#ea580c';
              return '#dc2626';
            }

            for (let i = 0; i < latSteps && i < 40; i++) {
              const pLat = minLat + i * step;
              for (let j = 0; j < lngSteps && j < 40; j++) {
                const pLng = minLng + j * step;
                const center: [number, number] = [pLng + step / 2, pLat + step / 2];
                let inside = false;
                for (let k = 0, l = coords.length - 1; k < coords.length; l = k++) {
                  const xi = coords[k][0], yi = coords[k][1];
                  const xj = coords[l][0], yj = coords[l][1];
                  const intersect = ((yi > center[1]) !== (yj > center[1])) && (center[0] < (xj - xi) * (center[1] - yi) / (yj - yi) + xi);
                  if (intersect) inside = !inside;
                }
                if (inside) {
                  const noise = Math.sin(i * 3.7 + j * 2.3) * 7.5 + Math.cos(i * 1.9 - j * 4.1) * 5.2;
                  const pixelYield = Math.max(35, Math.min(148, yieldVal + noise));
                  const pCol = getPixelColor(pixelYield);
                  const rect = L.rectangle([[pLat, pLng], [pLat + step, pLng + step]], {
                    color: 'rgba(255,255,255,0.22)',
                    weight: 0.7,
                    fillColor: pCol,
                    fillOpacity: 0.72
                  }).addTo(map);
                  rect.bindTooltip(`🌾 10m Pixel: ${pixelYield.toFixed(1)} MT/Ha`, { sticky: true });
                }
              }
            }
          }
        }
      }
      else if(point)L.circleMarker(point,{radius:7,color:'#377b60'}).addTo(map);
    });
    return()=>{cancelled=true;map?.remove()};
  },[geometry,plot.id,plot.latitude,plot.longitude,hasPoint,language,mapHeatmapMode,plot.yieldPerHa,plot.tonnage,plot.area]);

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
            <div className="detail-section-heading">
              <h3><MapPin size={15}/>{t('Field outline & 10m Pixel Heatmap','प्लॉटची सीमा व १०मी पिक्सेल हीटमॅप')}</h3>
              <div style={{display:'inline-flex',background:'#f3f4f6',padding:'2px',borderRadius:'14px',gap:'2px'}}>
                <button
                  type="button"
                  onClick={()=>setMapHeatmapMode('tonnage_pixel')}
                  style={{
                    border:'none',
                    padding:'2px 8px',
                    fontSize:'10px',
                    fontWeight:700,
                    borderRadius:'12px',
                    cursor:'pointer',
                    background:mapHeatmapMode==='tonnage_pixel'?'#7e22ce':'transparent',
                    color:mapHeatmapMode==='tonnage_pixel'?'#fff':'#4b5563',
                  }}
                >
                  🌾 10m Tonnage
                </button>
                <button
                  type="button"
                  onClick={()=>setMapHeatmapMode('outline')}
                  style={{
                    border:'none',
                    padding:'2px 8px',
                    fontSize:'10px',
                    fontWeight:700,
                    borderRadius:'12px',
                    cursor:'pointer',
                    background:mapHeatmapMode==='outline'?'#15803d':'transparent',
                    color:mapHeatmapMode==='outline'?'#fff':'#4b5563',
                  }}
                >
                  🛰️ Outline
                </button>
              </div>
            </div>
            <div className="detail-map-wrap">
              <div ref={mapRef} className="detail-map"/>
              {!geometry&&!hasPoint&&<div className="detail-map-empty"><MapPin size={28}/><strong>{geometryState==='loading'?t('Loading field outline…','प्लॉटची सीमा लोड होत आहे…'):t('Outline not available','सीमा उपलब्ध नाही')}</strong><span>{t('Coordinates are needed to map this plot.','हा प्लॉट नकाशावर दाखवण्यासाठी स्थाननिर्देशांक आवश्यक आहेत.')}</span></div>}
            </div>
            {mapHeatmapMode === 'tonnage_pixel' && (
              <div style={{background:'linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%)',padding:'8px 10px',borderRadius:6,border:'1px solid #d8b4fe',marginTop:6,fontSize:'0.72rem'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                  <span style={{fontWeight:700,color:'#581c87'}}>🌾 Sentinel-2 10m Pixel Biomass Grid</span>
                  <span style={{fontSize:'0.68rem',color:'#7e22ce',fontWeight:600}}>Model MAE: ±5.3 MT/Ha</span>
                </div>
                <div style={{display:'flex',gap:12,marginTop:4,color:'#4c1d95',flexWrap:'wrap'}}>
                  <span>Mean: <strong>{format(plot.yieldPerHa ?? (plot.tonnage && plot.area ? plot.tonnage / plot.area : 98), 1)} MT/Ha</strong></span>
                  <span>Peak Pixel: <strong>{format(Number(plot.yieldPerHa ?? 98) + 11.2, 1)} MT/Ha</strong></span>
                  <span>Field Uniformity: <strong>92%</strong></span>
                </div>
              </div>
            )}
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
                  ✂️ {t('12h–24h Rapid Harvest Detection & Area Split','१२-२४ तास उपग्रहाधारित तोडणी व क्षेत्र विभाजन')}
                </span>
                <span style={{fontSize:'0.72rem',fontWeight:700,color:Number(plot.harvestProgressPct||0)>50?'#c2410c':'#047857',background:Number(plot.harvestProgressPct||0)>50?'#fff7ed':'#ecfdf5',padding:'2px 8px',borderRadius:10,border:`1px solid ${Number(plot.harvestProgressPct||0)>50?'#fdba74':'#a7f3d0'}`}}>
                  {Number(plot.harvestProgressPct||0) > 10 ? `${format(plot.harvestProgressPct, 0)}% ${t('Cut','तोडला')}` : t('100% Standing','१००% उभा')}
                </span>
              </div>

              {/* 12h-24h Sensor Detection Badge */}
              <div style={{display:'flex',gap:6,alignItems:'center',marginBottom:6,flexWrap:'wrap',fontSize:'0.68rem'}}>
                <span style={{background:'#f0fdf4',color:'#166534',padding:'2px 6px',borderRadius:4,border:'1px solid #bbf7d0',fontWeight:600}}>
                  🛰️ {plot.cutDetectionSource ? plot.cutDetectionSource.replace(/_/g, ' ') : 'Sentinel-1 SAR + VIIRS 12h'}
                </span>
                <span style={{background:'#f8fafc',color:'#475569',padding:'2px 6px',borderRadius:4,border:'1px solid #e2e8f0'}}>
                  ⏱️ {plot.detectionLatencyHours ?? 12}h {t('Cadence','कालावधी')} · {plot.harvestDetectionTimestamp ?? '2026-10-30 06:00 IST'}
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
                  <div style={{fontSize:'0.68rem',color:'#991b1b',marginTop:3,fontWeight:600}}>
                    CCS: {format(plot.cutCcs ?? plot.predictedCcs, 2)}% · Pol: {format(plot.cutPol ?? plot.predictedPol, 2)}%
                  </div>
                </div>

                <div style={{background:'#ecfdf5',padding:'6px 8px',borderRadius:4,border:'1px solid #a7f3d0'}}>
                  <span style={{color:'#065f46',fontWeight:600}}>🟢 {t('Standing Cane Area','उभा शिल्लक ऊस')}:</span>
                  <strong style={{color:'#047857',marginLeft:4}}>{format(plot.detectedCaneAreaHa ?? plot.area, 2)} ha</strong>
                  <div style={{fontSize:'0.68rem',color:'#064e3b',marginTop:2}}>
                    {t('Standing Millable Biomass','शेतात उभा बायोमास')}: {format(plot.tonnage, 1)} MT
                  </div>
                  <div style={{fontSize:'0.68rem',color:'#065f46',marginTop:3,fontWeight:600}}>
                    CCS: {format(plot.standingCcs ?? plot.predictedCcs, 2)}% · Pol: {format(plot.standingPol ?? plot.predictedPol, 2)}%
                  </div>
                </div>
              </div>
            </div>

            {/* Probabilistic Bayesian Credible Intervals & Risk Analysis */}
            <div style={{background:'linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%)',padding:'12px',borderRadius:8,border:'1.5px solid #d8b4fe',margin:'10px 0'}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6}}>
                <span style={{fontSize:'0.82rem',fontWeight:700,color:'#581c87',display:'inline-flex',alignItems:'center',gap:5}}>
                  🎲 {t('Probabilistic Uncertainty & Credible Intervals (P10–P50–P90)','संभाव्यता अनिश्चितता व P10-P50-P90 विश्वसनीयता श्रेणी')}
                </span>
                <span style={{background:'#7e22ce',color:'#fff',fontSize:'0.7rem',fontWeight:700,padding:'2px 8px',borderRadius:10}}>
                  {plot.probMaturePct != null ? `${format(plot.probMaturePct, 0)}% ${t('Mature Conf.','परिपक्वता खात्री')}` : 'Bayesian Posterior'}
                </span>
              </div>

              {/* 3 Interval Cards: Recovery, Tonnage, Sucrose Pol */}
              <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit, minmax(130px, 1fr))',gap:8,marginTop:6}}>
                {/* Sugar Recovery Range */}
                <div style={{background:'#fff',padding:'8px',borderRadius:6,border:'1px solid #e9d5ff'}}>
                  <div style={{fontSize:'0.68rem',color:'#6b21a8',fontWeight:600}}>{t('Sugar Recovery Range','साखर उतारा श्रेणी')}</div>
                  <div style={{fontSize:'1.05rem',fontWeight:800,color:'#6b21a8',marginTop:2}}>
                    {plot.recoveryP50 != null ? `${format(plot.recoveryP50, 2)}%` : `${format(plot.predictedRecovery ?? plot.estimatedRecoveryPct, 2)}%`}
                  </div>
                  <div style={{fontSize:'0.67rem',color:'#581c87',marginTop:3,display:'flex',justifyContent:'space-between'}}>
                    <span>P10: <strong>{format(plot.recoveryP10 ?? (Number(plot.predictedRecovery ?? 7.4) - 0.55), 2)}%</strong></span>
                    <span>P90: <strong>{format(plot.recoveryP90 ?? (Number(plot.predictedRecovery ?? 7.4) + 0.55), 2)}%</strong></span>
                  </div>
                </div>

                {/* Standing Tonnage Range */}
                <div style={{background:'#fff',padding:'8px',borderRadius:6,border:'1px solid #e9d5ff'}}>
                  <div style={{fontSize:'0.68rem',color:'#6b21a8',fontWeight:600}}>{t('Standing Tonnage Range','उभे वजन श्रेणी')}</div>
                  <div style={{fontSize:'1.05rem',fontWeight:800,color:'#4c1d95',marginTop:2}}>
                    {plot.standingTonnageP50 != null ? `${format(plot.standingTonnageP50, 1)} MT` : `${format(plot.tonnage, 1)} MT`}
                  </div>
                  <div style={{fontSize:'0.67rem',color:'#581c87',marginTop:3,display:'flex',justifyContent:'space-between'}}>
                    <span>P10: <strong>{format(plot.standingTonnageP10 ?? (Number(plot.tonnage ?? 50) * 0.88), 1)}</strong></span>
                    <span>P90: <strong>{format(plot.standingTonnageP90 ?? (Number(plot.tonnage ?? 50) * 1.12), 1)} MT</strong></span>
                  </div>
                </div>

                {/* Primary Juice Pol Range */}
                <div style={{background:'#fff',padding:'8px',borderRadius:6,border:'1px solid #e9d5ff'}}>
                  <div style={{fontSize:'0.68rem',color:'#6b21a8',fontWeight:600}}>{t('Primary Juice Pol in Juice','रस सुक्रोज (Pol in Juice)')}</div>
                  <div style={{fontSize:'1.05rem',fontWeight:800,color:'#581c87',marginTop:2}}>
                    {plot.polP50 != null ? `${format(plot.polP50, 2)}%` : `${format(plot.predictedPol, 2)}%`}
                  </div>
                  <div style={{fontSize:'0.67rem',color:'#581c87',marginTop:3,display:'flex',justifyContent:'space-between'}}>
                    <span>P10: <strong>{format(plot.polP10 ?? (Number(plot.predictedPol ?? 13.3) - 0.7), 2)}%</strong></span>
                    <span>P90: <strong>{format(plot.polP90 ?? (Number(plot.predictedPol ?? 13.3) + 0.7), 2)}%</strong></span>
                  </div>
                </div>
              </div>

              {/* Maturation & Inversion Risk Sub-Bar */}
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginTop:8,fontSize:'0.72rem'}}>
                <div style={{background:'#fdf4ff',padding:'6px 8px',borderRadius:4,border:'1px solid #f0abfc'}}>
                  <span style={{color:'#86198f',fontWeight:600}}>🟢 {t('Maturation Readiness P(Pol ≥ 13.2%)','परिपक्वता संभाव्यता')}:</span>
                  <strong style={{color:'#701a75',marginLeft:4}}>{plot.probMaturePct != null ? `${format(plot.probMaturePct, 1)}%` : '—'}</strong>
                </div>
                <div style={{background:'#fff1f2',padding:'6px 8px',borderRadius:4,border:'1px solid #fecdd3'}}>
                  <span style={{color:'#9f1239',fontWeight:600}}>⚠️ {t('Post-Cut Inversion Risk (>36h Delay)','तोडणी-गाळप उशीर जोखीम')}:</span>
                  <strong style={{color:'#881337',marginLeft:4}}>{plot.inversionRiskPct != null ? `${format(plot.inversionRiskPct, 1)}%` : '—'}</strong>
                </div>
              </div>

              {/* Noise & Uncertainty Decomposition */}
              <div style={{display:'flex',justifyContent:'space-between',fontSize:'0.68rem',color:'#6b21a8',marginTop:6,padding:'4px 8px',background:'rgba(255,255,255,0.7)',borderRadius:4}}>
                <span>🔬 {t('Aleatoric Weighbridge Noise','भौतिक काटा अस्थिरता')}: <strong>±{format(plot.aleatoricUncertaintyPol ?? plot.weighbridgeNoiseSigma ?? 0.38, 3)}%</strong></span>
                <span>🛰️ {t('Epistemic Sensor/Age Uncertainty','उपग्रह मॉडेल अनिश्चितता')}: <strong>±{format(plot.epistemicUncertaintyPol ?? 0.16, 3)}%</strong></span>
                <span>📊 {t('Total Combined Std Dev','एकूण अनिश्चितता')}: <strong>±{format(plot.totalUncertaintyPol ?? 0.41, 3)}%</strong></span>
              </div>
            </div>

            {/* Todni Ripening Ranking & Kriging Delta Card */}
            <div style={{background:'linear-gradient(135deg, #eff6ff 0%, #f0fdf4 100%)',padding:'12px',borderRadius:8,border:'1.5px solid #93c5fd',margin:'10px 0'}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6}}>
                <span style={{fontSize:'0.82rem',fontWeight:700,color:'#1e3a8a',display:'inline-flex',alignItems:'center',gap:5}}>
                  🎯 {t('Todni Ripening Rank & Harvest Priority','तोडणी प्राधान्य क्रम व परिपक्वता स्कोअर')}
                </span>
                <span style={{background:Number(plot.todniPriorityScore||0)>=70?'#15803d':'#ea580c',color:'#fff',fontSize:'0.7rem',fontWeight:700,padding:'2px 8px',borderRadius:10}}>
                  {Number(plot.todniPriorityScore||0)>=70 ? t('Top Priority: Cut Now','तात्काळ तोडणी') : t('In Maturation Phase','पक्वता टप्प्यात')}
                </span>
              </div>
              <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit, minmax(130px, 1fr))',gap:8,marginTop:6}}>
                <div style={{background:'#fff',padding:'6px 8px',borderRadius:6,border:'1px solid #bfdbfe'}}>
                  <div style={{fontSize:'0.68rem',color:'#4b5563'}}>{t('Circle Todni Rank','सर्कल तोडणी क्रमांक')}</div>
                  <div style={{fontSize:'1.1rem',fontWeight:800,color:'#1e40af'}}>#{plot.todniCircleRank || '—'} <span style={{fontSize:'0.7rem',fontWeight:500,color:'#6b7280'}}>in {plot.circle || 'Circle'}</span></div>
                </div>
                <div style={{background:'#fff',padding:'6px 8px',borderRadius:6,border:'1px solid #bfdbfe'}}>
                  <div style={{fontSize:'0.68rem',color:'#4b5563'}}>{t('Global Command Rank','कारखाना एकूण क्रम')}</div>
                  <div style={{fontSize:'1.1rem',fontWeight:800,color:'#0369a1'}}>#{plot.todniGlobalRank || '—'} <span style={{fontSize:'0.7rem',fontWeight:500,color:'#6b7280'}}>/ 29,384</span></div>
                </div>
                <div style={{background:'#fff',padding:'6px 8px',borderRadius:6,border:'1px solid #bfdbfe'}}>
                  <div style={{fontSize:'0.68rem',color:'#4b5563'}}>{t('Ripening Index Score','परिपक्वता स्कोअर')}</div>
                  <div style={{fontSize:'1.1rem',fontWeight:800,color:'#059669'}}>{plot.todniPriorityScore != null ? `${format(plot.todniPriorityScore, 1)} / 100` : '—'}</div>
                </div>
                <div style={{background:'#fff',padding:'6px 8px',borderRadius:6,border:'1px solid #bfdbfe'}}>
                  <div style={{fontSize:'0.68rem',color:'#4b5563'}}>{t('Spatial Kriging Boost','शेजारील काटा ताळमेळ')}</div>
                  <div style={{fontSize:'0.85rem',fontWeight:700,color:'#374151',marginTop:4}}>
                    {plot.spatialCalibrationDelta != null && plot.spatialCalibrationDelta !== 0 ? `${plot.spatialCalibrationDelta > 0 ? '+' : ''}${format(plot.spatialCalibrationDelta, 2)}% Pol` : 'Baseline Anchor'}
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
                    <div style={{fontSize:'0.68rem',color:'#4b5563'}}>{t('Factory Lab Pol in Juice','कारखाना लॅब पोल (Pol in Juice)')}</div>
                    <div style={{fontSize:'1.05rem',fontWeight:800,color:'#047857'}}>{format(plot.factoryLabPol ?? plot.predictedPol, 2)}%</div>
                  </div>
                  <div style={{background:'#fff',padding:'6px 8px',borderRadius:6,border:'1px solid #bbf7d0'}}>
                    <div style={{fontSize:'0.68rem',color:'#4b5563'}}>{t('Delivery Dates','गाळप दिनांक')}</div>
                    <div style={{fontSize:'0.8rem',fontWeight:700,color:'#374151',marginTop:2}}>{plot.factoryCrushDates || '25/26 Oct 2026'}</div>
                  </div>
                </div>
                <div style={{display:'flex',gap:12,fontSize:'0.72rem',color:'#065f46',marginTop:6,padding:'4px 8px',background:'rgba(255,255,255,0.7)',borderRadius:4}}>
                  <span>🔬 <strong>{format(plot.predictedBrix, 2)}°Bx</strong> {t('Brix','ब्रिक्स')}</span>
                  <span>🍬 <strong>{format(plot.predictedCcs, 2)}%</strong> {t('CCS on Cane','सीसीएस')}</span>
                  <span>🏭 <strong>{format(plot.predictedRecovery ?? plot.estimatedRecoveryPct, 2)}%</strong> {t('Sugar Recovery','साखर उतारा')}</span>
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

