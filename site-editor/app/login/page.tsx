'use client';

import { useState } from 'react';
import Brand from '../ui/brand';
import {useLanguage,LanguageSwitch} from '../ui/language';
import FieldMap from '../ui/field-map';
import { ArrowUpRight, ShieldCheck, ArrowLeft, Lock, Mail, AlertCircle, Loader2, KeyRound } from 'lucide-react';

export default function Login() {
  const {t}=useLanguage();
  const [email, setEmail] = useState('gangamai@ikshuintelligence.com');
  const [password, setPassword] = useState('Gangamai#Sugar2026');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = (await res.json()) as { ok?: boolean; error?: string; redirect?: string };
      if (!res.ok || !data.ok) {
        throw new Error(data.error || 'Invalid credentials');
      }
      const target=new URLSearchParams(window.location.search).get('return_to');
      window.location.href=target?.startsWith('/')&&!target.startsWith('//')?target:data.redirect||'/portal';
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Unable to sign in. Please verify your credentials.';
      setError(message);
      setLoading(false);
    }
  }

  function setGangamaiPreset() {
    setEmail('gangamai@ikshuintelligence.com');
    setPassword('Gangamai#Sugar2026');
    setError('');
  }

  return (
    <main className="login-page">
      <div className="login-panel">
        <a href="/"><Brand /></a>
        <a className="back-link" href="/"><ArrowLeft size={16} /> {t('Back to Ikshu','इक्षूकडे परत')}</a>
        <div className="eyebrow">{t('SUGAR MILL WORKSPACE','साखर कारखाना कार्यक्षेत्र')}</div>
        <LanguageSwitch/><h1>{t('Welcome to','आपल्या')}<br/><em>{t('your command area.','कार्यक्षेत्रात स्वागत आहे.')}</em></h1>
        <p>{t('Sign in with your mill credentials to manage registered plots, laboratory quality, and harvest schedules.','नोंदणीकृत प्लॉट, प्रयोगशाळा गुणवत्ता आणि तोडणी नियोजनासाठी कारखान्याच्या खात्याने लॉगिन करा.')}</p>

        {error && (
          <div className="notice error" style={{ margin: '14px 0', padding: '10px 14px', borderRadius: '4px' }}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleLogin} className="login-form">
          <div className="login-field">
            <label htmlFor="mill-email">{t('Mill Account Email','कारखान्याच्या खात्याचा ईमेल')}</label>
            <div className="input-with-icon">
              <Mail size={16} className="input-icon" />
              <input
                id="mill-email"
                type="email"
                required
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="gangamai@ikshuintelligence.com"
                disabled={loading}
              />
            </div>
          </div>

          <div className="login-field">
            <label htmlFor="mill-password">{t('Password','पासवर्ड')}</label>
            <div className="input-with-icon">
              <Lock size={16} className="input-icon" />
              <input
                id="mill-password"
                type="password"
                required
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder={t('Enter password','पासवर्ड लिहा')}
                disabled={loading}
              />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '4px 0 10px' }}>
            <button
              type="button"
              className="preset-btn"
              onClick={setGangamaiPreset}
              title="Auto-fill Gangamai Sugar credentials"
            >
              <KeyRound size={13} /> {t('Fill Gangamai account','गंगामाई खाते भरा')}
            </button>
          </div>

          <button
            type="submit"
            className="button primary login-button"
            style={{ width: '100%', justifyContent: 'center' }}
            disabled={loading}
          >
            {loading ? (
              <>
                <Loader2 size={18} className="spinner" />
                <span>{t('Signing in…','लॉगिन होत आहे…')}</span>
              </>
            ) : (
              <>
                <span>{t('Sign in with password','पासवर्डने लॉगिन करा')}</span>
                <ArrowUpRight size={18} />
              </>
            )}
          </button>
        </form>

        <div className="login-note" style={{ marginTop: '22px' }}>
          <ShieldCheck size={20} />
          <span>{t('Active account: ','सक्रिय खाते: ')}<strong>gangamai@ikshuintelligence.com</strong> · Gangamai Industries and Commerce Ltd.</span>
        </div>

        <a className="text-link" href="/demo" style={{ marginTop: '16px' }}>
          {t('Explore a sample workspace','प्रात्यक्षिक कार्यक्षेत्र पहा')} <ArrowUpRight size={16} />
        </a>
        <small style={{ marginTop: '20px', display: 'block' }}>
          {t('Read our ','आमची ')}<a href="/privacy">{t('privacy notice','गोपनीयता सूचना')}</a>{t(' before continuing.',' पुढे जाण्यापूर्वी वाचा.')}
        </small>
      </div>

      <aside className="login-visual">
        <FieldMap />
        <div>
          <span className="eyebrow">{t('CONNECTED CANE WORKSPACE','एकत्रित ऊस कार्यक्षेत्र')}</span>
          <h2>{t('Every observation.','प्रत्येक निरीक्षणातून')}<br/>{t('A clearer perspective.','अधिक स्पष्ट माहिती.')}</h2>
          <p>{t('Field records, laboratory measurements and harvest planning, together.','शेत नोंदी, प्रयोगशाळेतील मापन आणि तोडणी नियोजन एकत्र.')}</p>
        </div>
      </aside>
    </main>
  );
}

