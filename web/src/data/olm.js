// OLM math + COLIP anchors + demo scenarios.
// Mirrors viz/dashboard.html and viz/render_examples.py so the React app
// agrees with whatever the bridge or chatbot produces. The aroma synthesizer
// is a rule-based stand-in for the live COLIP forward pass — when the bridge
// starts emitting an `aroma` field we use that instead.

export const COMPOUNDS = {
  CO2:    { label: 'CO₂',   name: 'carbon dioxide',    baseline: 450,  warn: 800,  bad: 1200 },
  NH3:    { label: 'NH₃',   name: 'ammonia',           baseline: 100,  warn: 150,  bad: 250  },
  NO:     { label: 'NO',    name: 'nitric oxide',      baseline: 5,    warn: 10,   bad: 15   },
  NO2:    { label: 'NO₂',   name: 'nitrogen dioxide',  baseline: 5,    warn: 10,   bad: 15   },
  CO:     { label: 'CO',    name: 'carbon monoxide',   baseline: 600,  warn: 1000, bad: 1500 },
  C2H5OH: { label: 'EtOH',  name: 'ethanol',           baseline: 100,  warn: 300,  bad: 500  },
  H2:     { label: 'H₂',    name: 'hydrogen',          baseline: 130,  warn: 180,  bad: 220  },
  CH4:    { label: 'CH₄',   name: 'methane',           baseline: 350,  warn: 450,  bad: 550  },
  VOC:    { label: 'VOC',   name: 'volatile organics', baseline: 1500, warn: 2500, bad: 3500 },
};

export const RADAR_KEYS = ['NH3','CO','VOC','CO2','NO','NO2','C2H5OH','H2','CH4'];

// COLIP aroma anchors — must match demo.py and viz/dashboard.html.
export const AROMA_ANCHORS = [
  { label: 'Fresh air',             desc: 'fresh clean outdoor air, no pollutants, pure breathable',                 filter: false },
  { label: 'Urban pollution',       desc: 'diesel exhaust fumes, nitrogen dioxide, carbon monoxide, traffic',         filter: true  },
  { label: 'Cigarette smoke',       desc: 'cigarette tobacco smoke, burnt paper, nicotine fumes',                     filter: true  },
  { label: 'Ammonia / cleaning',    desc: 'ammonia bleach cleaning chemicals disinfectant',                           filter: true  },
  { label: 'Cooking / kitchen',     desc: 'cooking food smells, kitchen fumes, frying oil, burnt food',               filter: false },
  { label: 'Mould / damp',          desc: 'mold mildew musty damp basement, fungal spores',                           filter: true  },
  { label: 'Petrol / fuel',         desc: 'petrol gasoline fuel station, hydrocarbons, VOC solvent fumes',            filter: true  },
  { label: 'Industrial / chemical', desc: 'industrial chemical factory, solvent, paint fumes, acetone',               filter: true  },
  { label: 'Smoke / fire',          desc: 'wood smoke bonfire wildfire, burnt carbon particulates',                   filter: true  },
  { label: 'Floral / natural',      desc: 'floral perfume flowers garden, fresh natural botanical scent',             filter: false },
];

// ── Demo scenarios — produce a synthetic Scentience sample ───────────────────
const jitter = (mid, range) => Math.max(0, mid + (Math.random() * 2 - 1) * range);

export const SCENARIOS = {
  calm: () => ({
    NH3: jitter(90, 30),  CO: jitter(550, 200), VOC: jitter(1200, 500),
    CO2: jitter(480, 80), NO: jitter(3, 3),     NO2: jitter(3, 3),
    C2H5OH: jitter(80, 60), H2: jitter(140, 30), CH4: jitter(380, 40),
    ENV_temperatureC: jitter(22, 0.6), ENV_humidity: jitter(45, 4),
  }),
  meeting: () => ({
    NH3: jitter(280, 70), CO: jitter(950, 250), VOC: jitter(2800, 600),
    CO2: jitter(950, 200), NO: jitter(5, 4),    NO2: jitter(6, 4),
    C2H5OH: jitter(120, 80), H2: jitter(150, 30), CH4: jitter(400, 40),
    ENV_temperatureC: jitter(24, 0.4), ENV_humidity: jitter(38, 3),
  }),
  commute: () => ({
    NH3: jitter(160, 50), CO: jitter(1300, 400), VOC: jitter(3300, 800),
    CO2: jitter(700, 150), NO: jitter(14, 6),   NO2: jitter(16, 6),
    C2H5OH: jitter(200, 100), H2: jitter(160, 30), CH4: jitter(420, 40),
    ENV_temperatureC: jitter(20, 1.2), ENV_humidity: jitter(60, 8),
  }),
  workout: () => ({
    NH3: jitter(220, 60), CO: jitter(700, 300), VOC: jitter(1800, 500),
    CO2: jitter(600, 100), NO: jitter(4, 3),    NO2: jitter(4, 3),
    C2H5OH: jitter(90, 60), H2: jitter(180, 40), CH4: jitter(410, 40),
    ENV_temperatureC: jitter(23, 0.5), ENV_humidity: jitter(55, 5),
  }),
};

// ── OLM math (mirrors the bridge and demo.py) ────────────────────────────────
export const scoreNH3 = (v) => v > 250 ? 3 : v > 150 ? 2 : v > 100 ? 1 : 0;
export const scoreCO  = (v) => v > 1000 ? 2 : v > 500 ? 1 : 0;
export const scoreVOC = (v) => v > 3000 ? 2 : v > 2000 ? 1 : 0;

export const penaltyCO2 = (v) => v > 1000 ? 3 : v > 800 ? 2 : v > 600 ? 1 : 0;
export const penaltyNO  = (v) => v > 15 ? 2 : v > 10 ? 1 : 0;
export const penaltyNO2 = (v) => v > 15 ? 2 : v > 10 ? 1 : 0;
export const penaltyVOC = (v) => v > 3000 ? 3 : v > 2000 ? 2 : v > 1000 ? 1 : 0;

export function synthesizeAroma(s) {
  const nh3 = s.NH3 ?? 0, co = s.CO ?? 0, voc = s.VOC ?? 0;
  const no  = s.NO  ?? 0, no2 = s.NO2 ?? 0;
  const eth = s.C2H5OH ?? 0, ch4 = s.CH4 ?? 0, h2 = s.H2 ?? 0;
  const hum = s.ENV_humidity ?? 45;

  const bias = {
    'Fresh air':             0.20 + Math.max(0, 1 - (voc + co + nh3) / 6000) * 0.08,
    'Urban pollution':       0.21 + Math.min(1, (co + no + no2*2) / 1500) * 0.13,
    'Cigarette smoke':       0.21 + Math.min(1, (co + voc/2) / 2500) * 0.11,
    'Ammonia / cleaning':    0.21 + Math.min(1, nh3 / 250) * 0.14,
    'Cooking / kitchen':     0.21 + Math.min(1, (ch4 + voc/3) / 3000) * 0.10,
    'Mould / damp':          0.21 + Math.min(1, hum / 100) * 0.07 + Math.min(1, h2 / 250) * 0.04,
    'Petrol / fuel':         0.21 + Math.min(1, (eth + voc/2) / 2500) * 0.12,
    'Industrial / chemical': 0.21 + Math.min(1, (voc + co) / 4000) * 0.13,
    'Smoke / fire':          0.21 + Math.min(1, (co + voc/3) / 3000) * 0.11,
    'Floral / natural':      0.21 + Math.min(1, (eth/3) / 200) * 0.05,
  };

  const ranked = AROMA_ANCHORS.map((a) => ({
    label: a.label,
    desc:  a.desc,
    filter_recommended: a.filter,
    score: Math.max(0.20, Math.min(0.36, bias[a.label] + (Math.random() - 0.5) * 0.012)),
  })).sort((x, y) => y.score - x.score);

  return { top: ranked, filter_recommended: ranked[0].filter_recommended };
}

export function olmAnalyze(s) {
  const nh3 = s.NH3 ?? 0, co = s.CO ?? 0, voc = s.VOC ?? 0;
  const co2 = s.CO2 ?? 400, no = s.NO ?? 0, no2 = s.NO2 ?? 0;

  const stress = scoreNH3(nh3) + scoreCO(co) + scoreVOC(voc);
  const aqi = Math.max(0, 10 - penaltyCO2(co2) - penaltyNO(no) - penaltyNO2(no2) - penaltyVOC(voc));
  const stressLevel = stress >= 5 ? 'high' : stress >= 3 ? 'moderate' : 'low';
  const qualityLevel = aqi >= 8 ? 'excellent' : aqi >= 6 ? 'good' : aqi >= 4 ? 'moderate' : 'poor';
  const filtration = aqi < 6;
  const conf = Math.min(stress * 0.15, 0.95);

  const t = new Date();
  const hh = String(t.getHours()).padStart(2, '0');
  const mm = String(t.getMinutes()).padStart(2, '0');
  const parts = [
    `${hh}:${mm} · ${(s.ENV_temperatureC ?? 22).toFixed(1)}°C, ${(s.ENV_humidity ?? 45).toFixed(0)}% RH.`,
  ];
  if (stressLevel === 'high') parts.push(`Elevated stress markers (~${(nh3*0.05).toFixed(1)} ng/m³, ${Math.round(conf*100)}% conf).`);
  else if (stressLevel === 'moderate') parts.push(`Moderate stress (${Math.round(conf*100)}% conf).`);
  else parts.push(`Stress normal.`);
  parts.push(qualityLevel === 'excellent' ? `Air excellent (AQI ${aqi}/10).`
           : qualityLevel === 'good'      ? `Air good (AQI ${aqi}/10).`
           : qualityLevel === 'moderate'  ? `Air moderate (AQI ${aqi}/10).`
                                          : `Air poor (AQI ${aqi}/10).`);
  if (filtration || stressLevel !== 'low') {
    parts.push(stressLevel === 'high' ? 'Stress-response filtration, 30 min.' : 'Standard purification, 15 min.');
  }

  return {
    type: 'olm_analysis',
    timestamp: t.toISOString(),
    natural_language_summary: parts.join(' '),
    sensors: s,
    hormone: {
      stress_score: stress,
      stress_level: stressLevel,
      confidence: conf,
      cortisol_estimate_ng_m3: nh3 * 0.05,
      contributions: { NH3: scoreNH3(nh3), CO: scoreCO(co), VOC: scoreVOC(voc) },
    },
    air_quality: {
      aqi, level: qualityLevel,
      penalties: { CO2: penaltyCO2(co2), NO: penaltyNO(no), NO2: penaltyNO2(no2), VOC: penaltyVOC(voc) },
    },
    aroma: synthesizeAroma(s),
    device_actions: {
      activate_filter:  filtration || stressLevel !== 'low',
      filter_mode:      stressLevel === 'high' ? 'stress_reduction' : 'standard',
      duration_minutes: stressLevel === 'high' ? 30 : 15,
      alert_level:      stress,
      fan_speed:        stressLevel === 'high' ? 85 : 65,
    },
  };
}

export function scenarioFromMetrics(msg) {
  const m = msg.raw_metrics || {};
  const conf = m.stress_confidence ?? 0;
  const aqi  = m.air_quality_score ?? 8;
  const guess = conf > 0.6 ? 'meeting' : conf > 0.3 ? 'workout' : aqi < 5 ? 'commute' : 'calm';
  return SCENARIOS[guess]();
}
