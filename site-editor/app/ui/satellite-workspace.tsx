'use client';
import {useEffect,useState} from 'react';
import {useLanguage} from './language';
import SatellitePanel,{type SatellitePlot} from './satellite-panel';

export default function SatelliteWorkspace(){
 const {t}=useLanguage();
 const [plots,setPlots]=useState<SatellitePlot[]|null>(null);
 const [error,setError]=useState('');
 useEffect(()=>{
  let active=true;
  void fetch('/api/workspace?view=satellite',{cache:'no-store'}).then(async response=>{
   const data=await response.json() as {plots:SatellitePlot[];error?:string};
   if(!response.ok)throw Error(data.error||'Unable to load your plots.');
   if(active)setPlots(data.plots);
  }).catch(error=>{if(active)setError((error as Error).message)});
  return()=>{active=false};
 },[]);
 if(error)return <section className="panel empty-state" role="alert">{error}<a className="button secondary" href="/satellite">{t('Retry','पुन्हा प्रयत्न करा')}</a></section>;
 if(!plots)return <section className="panel empty-state">{t('Loading the active plot register…','सक्रिय प्लॉट नोंदवही लोड होत आहे…')}</section>;
 if(!plots.length)return <section className="panel empty-state"><h2>{t('Add your plot register first.','प्रथम प्लॉट नोंदवही जोडा.')}</h2><p>{t('Plot numbers and boundaries are required for imagery searches.','उपग्रह प्रतिमा शोधण्यासाठी प्लॉट क्रमांक व सीमा आवश्यक आहेत.')}</p><a className="button primary" href="/portal">{t('Open dashboard','डॅशबोर्ड उघडा')}</a></section>;
 return <SatellitePanel plots={plots}/>;
}
