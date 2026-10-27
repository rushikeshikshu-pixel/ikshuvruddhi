'use client';
import {createContext,useContext,useEffect,useState,type ReactNode} from 'react';
type Language='mr'|'en';
const Context=createContext({language:'mr' as Language,setLanguage:(_language:Language)=>{}});
export function LanguageProvider({children}:{children:ReactNode}){
 const [language,setLanguage]=useState<Language>('mr');
 useEffect(()=>{const saved=localStorage.getItem('ikshu-language');if(saved==='en'||saved==='mr')setLanguage(saved)},[]);
 useEffect(()=>{document.documentElement.lang=language},[language]);
 const update=(value:Language)=>{setLanguage(value);localStorage.setItem('ikshu-language',value)};
 return <Context.Provider value={{language,setLanguage:update}}>{children}</Context.Provider>;
}
export function useLanguage(){const context=useContext(Context);return {...context,t:(en:string,mr:string)=>context.language==='mr'?mr:en,format:(value:number|null|undefined,digits=2)=>value==null||!Number.isFinite(value)?'—':new Intl.NumberFormat(context.language==='mr'?'mr-IN':'en-IN',{numberingSystem:'latn',maximumFractionDigits:digits}).format(value),date:(value:string|null|undefined)=>value?new Date(value.slice(0,10)+'T12:00:00').toLocaleDateString(context.language==='mr'?'mr-IN':'en-IN',{day:'2-digit',month:'short',year:'numeric'}):'—'};}
export function Text({en,mr}:{en:string;mr:string}){const {t}=useLanguage();return <>{t(en,mr)}</>}
export function LanguageSwitch(){const {language,setLanguage}=useLanguage();return <div className="language-switch" aria-label="Language / भाषा"><button type="button" lang="mr" aria-pressed={language==='mr'} onClick={()=>setLanguage('mr')}>मराठी</button><button type="button" lang="en" aria-pressed={language==='en'} onClick={()=>setLanguage('en')}>English</button></div>}
export function cropLabel(value:string,language:string){return language==='en'?value:(({'Suru':'सुरू','Khodwa':'खोडवा','Adsali':'आडसाली','Purva Hungami':'पूर्वहंगामी','Other':'इतर'} as Record<string,string>)[value]||value)}
export function priorityLabel(value:string,language:string){return language==='en'?value:(({'Review':'पडताळणी','Ready':'तोडणीस तयार','Hold':'थांबवा','Unharvested':'तोडणी बाकी','Harvested':'तोडणी पूर्ण'} as Record<string,string>)[value]||value)}
export function tierLabel(value:string|undefined,language:string){if(!value)return '—';if(language==='en')return value;if(value.startsWith('Review:'))return 'पडताळणी: नवीन प्रयोगशाळा निकाल व तोडणी परवानगी आवश्यक';if(value.includes('Tier 1'))return 'स्तर १: उत्तम पक्वता (आता तोडणी)';if(value.includes('Tier 2'))return 'स्तर २: मध्यम पक्वता (२–३ आठवडे)';if(value.includes('Tier 3'))return 'स्तर ३: उशिराची पक्वता (४–६ आठवडे थांबा)';return value;}
