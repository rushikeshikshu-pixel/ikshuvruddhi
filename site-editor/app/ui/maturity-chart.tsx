'use client';

import { useState } from 'react';
import { Sparkles, Calendar, TrendingUp } from 'lucide-react';

type VarietyData = {
  name: string;
  type: string;
  peakDays: string;
  points: { ageMonths: number; brix: number; pol: number; recovery: number }[];
};

const VARIETIES: Record<string, VarietyData> = {
  'CO-86032': {
    name: 'Co-86032 (Nira)',
    type: 'Early-Mid Maturing · High Sugar Champion',
    peakDays: '330–360 Days',
    points: [
      { ageMonths: 8, brix: 14.8, pol: 11.2, recovery: 7.8 },
      { ageMonths: 9, brix: 16.5, pol: 13.1, recovery: 8.9 },
      { ageMonths: 10, brix: 18.2, pol: 15.0, recovery: 10.1 },
      { ageMonths: 11, brix: 19.8, pol: 16.8, recovery: 11.2 },
      { ageMonths: 12, brix: 20.6, pol: 17.6, recovery: 11.8 },
      { ageMonths: 13, brix: 21.0, pol: 17.9, recovery: 12.0 },
      { ageMonths: 14, brix: 20.4, pol: 17.1, recovery: 11.4 },
    ]
  },
  'CO-265': {
    name: 'Co-0265 (Phule 265)',
    type: 'Mid-Late Maturing · High Tonnage & Drought Resilient',
    peakDays: '360–390 Days',
    points: [
      { ageMonths: 8, brix: 13.9, pol: 10.4, recovery: 7.2 },
      { ageMonths: 9, brix: 15.6, pol: 12.2, recovery: 8.3 },
      { ageMonths: 10, brix: 17.4, pol: 14.1, recovery: 9.4 },
      { ageMonths: 11, brix: 18.9, pol: 15.8, recovery: 10.5 },
      { ageMonths: 12, brix: 19.9, pol: 16.9, recovery: 11.3 },
      { ageMonths: 13, brix: 20.4, pol: 17.4, recovery: 11.7 },
      { ageMonths: 14, brix: 20.2, pol: 17.0, recovery: 11.3 },
    ]
  }
};

export default function MaturityChart() {
  const [selectedVariety, setSelectedVariety] = useState<'CO-86032' | 'CO-265'>('CO-86032');
  const [activeMonth, setActiveMonth] = useState<number>(12);

  const data = VARIETIES[selectedVariety];
  const activePt = data.points.find(p => p.ageMonths === activeMonth) || data.points[4];

  // SVG dimensions
  const width = 640;
  const height = 220;
  const padLeft = 45;
  const padRight = 30;
  const padTop = 20;
  const padBottom = 35;

  const chartW = width - padLeft - padRight;
  const chartH = height - padTop - padBottom;

  const minMonth = 8;
  const maxMonth = 14;
  const minVal = 6;
  const maxVal = 22;

  const getX = (m: number) => padLeft + ((m - minMonth) / (maxMonth - minMonth)) * chartW;
  const getY = (v: number) => padTop + chartH - ((v - minVal) / (maxVal - minVal)) * chartH;

  const makePath = (key: 'brix' | 'pol' | 'recovery') => {
    return data.points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${getX(p.ageMonths)} ${getY(p[key])}`).join(' ');
  };

  return (
    <section className="panel" style={{ marginTop: '22px' }}>
      <div className="panel-header" style={{ flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div className="eyebrow">FIELD SCIENCE · CANE QUALITY ACCUMULATION</div>
          <h2>Maturity & Sugar Ripening Profile</h2>
          <p>Multi-temporal sugar accumulation curve based on factory command agro-climatic standards.</p>
        </div>
        <div style={{ display: 'flex', gap: '8px', marginLeft: 'auto' }}>
          {(['CO-86032', 'CO-265'] as const).map(vKey => (
            <button
              key={vKey}
              className={`button ${selectedVariety === vKey ? 'primary' : 'secondary'}`}
              style={{ fontSize: '11px', padding: '6px 12px' }}
              onClick={() => setSelectedVariety(vKey)}
            >
              {vKey}
            </button>
          ))}
        </div>
      </div>

      <div style={{ padding: '0 24px 20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
          <div>
            <strong style={{ fontSize: '13px', color: 'var(--ink)' }}>{data.name}</strong>
            <span style={{ fontSize: '11px', color: 'var(--muted)', marginLeft: '10px' }}>{data.type}</span>
          </div>
          <div style={{ display: 'flex', gap: '14px', fontSize: '11px', alignItems: 'center' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: '10px', height: '10px', borderRadius: '2px', background: '#e0a93b' }} /> Brix (°Bx)
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: '10px', height: '10px', borderRadius: '2px', background: '#2e7d32' }} /> Pol in Juice (%)
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: '10px', height: '10px', borderRadius: '2px', background: '#00838f' }} /> Recovery (%)
            </span>
          </div>
        </div>

        {/* Responsive SVG Chart */}
        <div style={{ width: '100%', overflowX: 'auto' }}>
          <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', maxHeight: '240px', display: 'block' }}>
            {/* Grid lines */}
            {[8, 12, 16, 20].map(val => (
              <g key={val}>
                <line x1={padLeft} y1={getY(val)} x2={width - padRight} y2={getY(val)} stroke="#e0ded0" strokeDasharray="3 3" />
                <text x={padLeft - 8} y={getY(val) + 4} textAnchor="end" fontSize="10" fill="#8c887b">{val}%</text>
              </g>
            ))}

            {/* Peak harvest window highlight */}
            <rect
              x={getX(11.5)}
              y={padTop}
              width={getX(13.5) - getX(11.5)}
              height={chartH}
              fill="#2e7d32"
              opacity="0.08"
            />
            <text x={getX(12.5)} y={padTop + 14} textAnchor="middle" fontSize="10" fill="#2e7d32" fontWeight="bold">
              PEAK HARVEST WINDOW
            </text>

            {/* Curves */}
            <path d={makePath('brix')} fill="none" stroke="#e0a93b" strokeWidth="2.5" strokeLinecap="round" />
            <path d={makePath('pol')} fill="none" stroke="#2e7d32" strokeWidth="2.5" strokeLinecap="round" />
            <path d={makePath('recovery')} fill="none" stroke="#00838f" strokeWidth="2.5" strokeLinecap="round" />

            {/* Data points */}
            {data.points.map(p => {
              const cx = getX(p.ageMonths);
              const isSelected = p.ageMonths === activeMonth;
              return (
                <g key={p.ageMonths} style={{ cursor: 'pointer' }} onClick={() => setActiveMonth(p.ageMonths)}>
                  <line x1={cx} y1={padTop} x2={cx} y2={padTop + chartH} stroke={isSelected ? '#203d31' : '#f0eee5'} strokeWidth={isSelected ? 1.5 : 1} />
                  <circle cx={cx} cy={getY(p.brix)} r={isSelected ? 5 : 3.5} fill="#e0a93b" />
                  <circle cx={cx} cy={getY(p.pol)} r={isSelected ? 5 : 3.5} fill="#2e7d32" />
                  <circle cx={cx} cy={getY(p.recovery)} r={isSelected ? 5 : 3.5} fill="#00838f" />
                  <text x={cx} y={height - 12} textAnchor="middle" fontSize="10" fill={isSelected ? '#203d31' : '#8c887b'} fontWeight={isSelected ? 'bold' : 'normal'}>
                    M{p.ageMonths}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        {/* Selected Month Detail Strip */}
        <div style={{ display: 'flex', gap: '16px', background: '#f7f6ed', padding: '12px 16px', borderRadius: '4px', marginTop: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Calendar size={16} color="#49654d" />
            <span style={{ fontSize: '11px', fontWeight: 'bold', color: '#203d31' }}>Month {activePt.ageMonths} (~{activePt.ageMonths * 30} Days)</span>
          </div>
          <div style={{ display: 'flex', gap: '16px', marginLeft: 'auto', fontSize: '11px' }}>
            <span>Brix: <strong style={{ color: '#b37d14' }}>{activePt.brix}°Bx</strong></span>
            <span>Pol in Juice: <strong style={{ color: '#2e7d32' }}>{activePt.pol}%</strong></span>
            <span>Mill Recovery: <strong style={{ color: '#00838f' }}>{activePt.recovery}%</strong></span>
            <span>Recommended: <strong style={{ color: activePt.ageMonths >= 12 && activePt.ageMonths <= 13 ? '#2e7d32' : '#888' }}>{activePt.ageMonths >= 12 && activePt.ageMonths <= 13 ? 'Prime Harvesting' : activePt.ageMonths < 12 ? 'Vegetative Growth' : 'Over-mature'}</strong></span>
          </div>
        </div>
      </div>
    </section>
  );
}
