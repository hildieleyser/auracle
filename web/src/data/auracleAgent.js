// Auracle agent — turns a free-form question into an honest, specific answer
// grounded in the live OLM stream. No LLM, no canned strings: the agent
// reads the same `latest` analysis and `history` that the Dashboard
// renders, classifies the user's intent with simple keyword matching, and
// returns a reply built from actual sensor numbers.

import { COMPOUNDS, RADAR_KEYS } from './olm.js';

// ── compound knowledge — used for explanations and recommendations ──────
const COMPOUND_INFO = {
  CO2: {
    aliases: ['co2', 'co₂', 'carbon dioxide', 'co 2'],
    role:    'ventilation indicator',
    blurb:   'CO₂ rises when a room is poorly ventilated. Above ~1000 ppm cognition starts to dip.',
    actions: [
      { from: 1000, do: 'open a window now — the room is stuffy.' },
      { from: 800,  do: 'crack a window soon — air is going stale.' },
      { from: 600,  do: 'still comfortable; nothing to do.' },
    ],
  },
  NH3: {
    aliases: ['nh3', 'nh₃', 'ammonia'],
    role:    'sweat / cleaning-product marker',
    blurb:   'Ammonia comes from cleaning products and rises with sweat under stress.',
    actions: [
      { from: 250, do: 'check for ammonia cleaners or kitty litter nearby; otherwise, take a breath — the body is producing more.' },
      { from: 150, do: 'mild elevation; if no cleaning products are around it can track stress.' },
    ],
  },
  VOC: {
    aliases: ['voc', 'vocs', 'volatile', 'organic compound'],
    role:    'general air-quality bucket (paint, cleaners, cooking)',
    blurb:   'VOCs are organic gases from paint, cleaners, cooking, body odor. High levels irritate eyes and nose.',
    actions: [
      { from: 3000, do: 'ventilate now and run a HEPA-plus-carbon filter. Look for solvents or strong cooking smells.' },
      { from: 2000, do: 'open a window; investigate fragranced products, paint, or cooking byproducts.' },
      { from: 1000, do: 'mild — typical indoor level after cooking or with scented products.' },
    ],
  },
  CO: {
    aliases: ['carbon monoxide', ' co '],
    role:    'combustion / safety',
    blurb:   'CO is mostly produced by combustion (cars, gas stoves). High indoor CO is a safety issue.',
    actions: [
      { from: 1000, do: 'leave the area and ventilate immediately. Check gas appliances.' },
      { from: 500,  do: 'check gas appliances and ventilation.' },
    ],
  },
  NO: {
    aliases: ['nitric oxide', ' no '],
    role:    'traffic / combustion',
    blurb:   'NO comes from vehicle exhaust and gas burners. Mostly an outdoor/cooking signal.',
    actions: [
      { from: 15, do: 'reduce exposure to traffic or gas appliances.' },
    ],
  },
  NO2: {
    aliases: ['no2', 'no₂', 'nitrogen dioxide'],
    role:    'traffic / gas stoves',
    blurb:   'NO₂ comes from traffic and gas stoves and irritates airways.',
    actions: [
      { from: 15, do: 'turn the range hood on / open a window.' },
    ],
  },
  C2H5OH: {
    aliases: ['ethanol', 'alcohol', 'c2h5oh', 'etoh'],
    role:    'metabolic / ambient',
    blurb:   'Trace ethanol is normal — comes from metabolism, hand sanitizer, or alcohol nearby.',
    actions: [],
  },
  H2: {
    aliases: ['h2', 'h₂', 'hydrogen'],
    role:    'gut metabolism',
    blurb:   'H₂ is mostly produced by gut bacteria — a background reading.',
    actions: [],
  },
  CH4: {
    aliases: ['ch4', 'ch₄', 'methane'],
    role:    'gut / ambient',
    blurb:   'Methane comes from gut microbes and ambient sources.',
    actions: [],
  },
};

// ── helpers ─────────────────────────────────────────────────────────────

function matches(text, alternatives) {
  return alternatives.some((a) => text.includes(a));
}

function findCompound(text) {
  for (const [k, info] of Object.entries(COMPOUND_INFO)) {
    if (info.aliases.some((a) => text.includes(a))) return k;
  }
  return null;
}

function unitFor(key) {
  return key === 'CO2' ? 'ppm' : 'ppb';
}

function elevated(latest) {
  if (!latest?.sensors) return [];
  return RADAR_KEYS
    .map((k) => {
      const v = latest.sensors[k];
      const c = COMPOUNDS[k];
      if (v == null) return null;
      return { key: k, value: v, c, normWarn: v / c.warn, normBad: v / c.bad };
    })
    .filter((r) => r && r.value >= r.c.warn)
    .sort((a, b) => b.normBad - a.normBad);
}

function topDriver(latest) {
  // which compound is closest to its 'bad' threshold?
  if (!latest?.sensors) return null;
  return RADAR_KEYS
    .map((k) => ({ key: k, ratio: (latest.sensors[k] ?? 0) / COMPOUNDS[k].bad }))
    .sort((a, b) => b.ratio - a.ratio)[0];
}

function actionFor(key, value) {
  const info = COMPOUND_INFO[key];
  if (!info) return null;
  for (const a of info.actions) {
    if (value >= a.from) return a.do;
  }
  return null;
}

function fmt(n) {
  return n >= 100 ? n.toFixed(0) : n.toFixed(1);
}

// ── intent handlers ─────────────────────────────────────────────────────

function statusReply(status, latest) {
  const ageSec = status.lastReceivedAt
    ? Math.max(0, (Date.now() - status.lastReceivedAt) / 1000)
    : null;
  if (!status.bridgeUrl) {
    return 'No live source configured. Open the Dashboard tab, tap the status row, and paste a bridge URL — until then I can only describe simulated readings.';
  }
  if (status.source === 'connecting') {
    return `Connecting to ${trimUrl(status.bridgeUrl)} now…`;
  }
  if (status.source === 'demo') {
    return `Bridge at ${trimUrl(status.bridgeUrl)} isn't reachable, so what you see is the simulated stream. Open the Dashboard's status row to swap sources.`;
  }
  if (ageSec == null) {
    return `Connected to ${trimUrl(status.bridgeUrl)} — waiting on the first sample.`;
  }
  const fresh = ageSec < 15
    ? `last sample ${ageSec.toFixed(1)}s ago`
    : `last sample ${ageSec.toFixed(0)}s ago — stale`;
  const sensorsLine = status.sensorsInBroadcast
    ? `Raw sensor record is in every frame — every panel reflects real readings.`
    : `Sensor record isn't included in the broadcast, so radar/timeline use the rule-based fallback. AQI and stress are still real.`;
  return `Live from ${trimUrl(status.bridgeUrl)}, ${fresh}. ${sensorsLine}`;
}

function airSummary(latest) {
  if (!latest) return 'Just connected — give me a few seconds for the first reading.';
  const aqi   = latest.air_quality.aqi;
  const level = latest.air_quality.level;
  const driver = topDriver(latest);
  const elev = elevated(latest);
  let line2;
  if (elev.length === 0) {
    line2 = 'Nothing is elevated — every channel sits below its warn threshold.';
  } else {
    const top = elev[0];
    line2 = `${top.c.label} is the limiting factor at ${fmt(top.value)} ${unitFor(top.key)} (warn ≥ ${top.c.warn}).`;
  }
  return `Air quality is ${level} (${aqi}/10). ${line2}`;
}

function elevatedReply(latest) {
  if (!latest) return 'Hold on — first reading hasn\'t come in yet.';
  const elev = elevated(latest);
  if (elev.length === 0) {
    return 'Nothing is over the line. Every gas channel is below its warn threshold right now.';
  }
  const lines = elev.slice(0, 4).map((e) => {
    const zone = e.value >= e.c.bad ? 'high' : 'elevated';
    return `• ${e.c.label} — ${fmt(e.value)} ${unitFor(e.key)} (${zone}; warn ≥ ${e.c.warn}, bad ≥ ${e.c.bad})`;
  });
  return `${elev.length} channel${elev.length === 1 ? '' : 's'} above the warn line:\n${lines.join('\n')}`;
}

function recommendation(latest) {
  if (!latest) return 'Give me a moment — no readings yet.';
  const elev = elevated(latest);
  if (elev.length === 0) {
    return `Air quality is ${latest.air_quality.level} (${latest.air_quality.aqi}/10). Nothing to act on — go about your day.`;
  }
  const advice = elev.slice(0, 3).map((e) => {
    const a = actionFor(e.key, e.value);
    return a
      ? `• ${e.c.label} ${fmt(e.value)} ${unitFor(e.key)} → ${a}`
      : `• ${e.c.label} ${fmt(e.value)} ${unitFor(e.key)} (above warn).`;
  });
  return `What to do based on the live reading:\n${advice.join('\n')}`;
}

function trendReply(history) {
  if (!history || history.length < 4) return 'Not enough history yet — give it a minute.';
  const half = Math.floor(history.length / 2);
  const oldHalf = history.slice(0, half);
  const newHalf = history.slice(half);
  const avg = (xs, fn) => xs.reduce((s, x) => s + fn(x), 0) / xs.length;
  const aqiOld = avg(oldHalf, (a) => a.air_quality.aqi);
  const aqiNew = avg(newHalf, (a) => a.air_quality.aqi);
  const stressOld = avg(oldHalf, (a) => a.hormone.stress_score);
  const stressNew = avg(newHalf, (a) => a.hormone.stress_score);
  const dAqi = aqiNew - aqiOld;
  const dStress = stressNew - stressOld;
  const aqiDir    = Math.abs(dAqi) < 0.3   ? 'flat'      : dAqi > 0    ? 'improving' : 'worsening';
  const stressDir = Math.abs(dStress) < 0.3 ? 'unchanged' : dStress > 0 ? 'rising'    : 'falling';
  return `Comparing the last ${newHalf.length} samples to the previous ${oldHalf.length}: AQI ${aqiDir} (${aqiOld.toFixed(1)} → ${aqiNew.toFixed(1)}), stress ${stressDir} (${stressOld.toFixed(1)} → ${stressNew.toFixed(1)}).`;
}

function stressReply(latest) {
  if (!latest) return 'No reading yet.';
  const h = latest.hormone;
  const c = h.contributions;
  const drivers = Object.entries(c)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => `${COMPOUNDS[k].label} +${v}`);
  const driverStr = drivers.length ? drivers.join(', ') : 'no contributors above threshold';
  return `Composite stress score: ${h.stress_score}/7 (${h.stress_level}). Built from threshold points on NH₃ / CO / VOC — currently: ${driverStr}.\n\nNote: this is a transparent rule, not a real cortisol measurement.`;
}

function compoundReply(key, latest) {
  const c = COMPOUNDS[key];
  const info = COMPOUND_INFO[key];
  if (!latest?.sensors || latest.sensors[key] == null) {
    return `${c.label} (${c.name}): ${info.blurb}\nNo current reading available.`;
  }
  const v = latest.sensors[key];
  const u = unitFor(key);
  const zone = v >= c.bad ? 'high' : v >= c.warn ? 'elevated' : 'normal';
  const baseline = `Baseline ~${c.baseline} ${u} · warn ≥ ${c.warn} · bad ≥ ${c.bad}.`;
  const action = actionFor(key, v);
  const actLine = action ? `\n→ ${action}` : '';
  return `${c.label} is ${fmt(v)} ${u} (${zone}). ${info.blurb}\n${baseline}${actLine}`;
}

function aromaReply(latest) {
  if (!latest?.sensors) return 'No reading yet.';
  // Honest about the lack of COLIP: describe the *pattern* in real numbers
  // rather than fake cosine similarities.
  const elev = elevated(latest);
  if (elev.length === 0) {
    return 'No olfactory pattern stands out — every channel is at or below baseline. Reads as fresh air.';
  }
  const top = elev.slice(0, 3).map((e) => `${e.c.label} ${fmt(e.value)} ${unitFor(e.key)}`).join(', ');
  let inference;
  const has = (k) => elev.some((e) => e.key === k);
  if (has('NH3') && !has('CO')) inference = 'pattern reads cleaning-product / sweat.';
  else if (has('CO') && has('VOC')) inference = 'pattern reads combustion / poor ventilation (cooking, traffic).';
  else if (has('VOC') && !has('CO')) inference = 'pattern reads solvents or fragranced products.';
  else if (has('CO2') && !has('VOC')) inference = 'pattern reads stuffy room — humans breathing, not enough fresh air.';
  else inference = 'pattern is mixed; no single category dominates.';
  return `Above-baseline channels: ${top}.\n${inference}\n\n(Real COLIP aroma classification needs the model running on the bridge — until then this is rule-based pattern matching.)`;
}

function filterReply(latest) {
  if (!latest) return 'No reading yet.';
  const a = latest.device_actions;
  if (!a.activate_filter) {
    return `Filter recommendation: stay off. Air quality is ${latest.air_quality.level} (${latest.air_quality.aqi}/10) and stress is ${latest.hormone.stress_level}.`;
  }
  return `Filter recommendation: ${a.filter_mode}, fan ${a.fan_speed}%, ~${a.duration_minutes} min. Triggered by AQI ${latest.air_quality.aqi}/10 / stress ${latest.hormone.stress_level}.`;
}

function fallback(latest) {
  if (!latest) return "I'm reading the live OLM stream. Try: how's the air, what's elevated, should I ventilate, or ask about a specific compound (CO₂, NH₃, VOC).";
  const aqi = latest.air_quality.aqi;
  const level = latest.air_quality.level;
  const driver = topDriver(latest);
  const driverStr = driver
    ? `${COMPOUNDS[driver.key].label} ${fmt(latest.sensors?.[driver.key] ?? 0)} ${unitFor(driver.key)}`
    : '—';
  return `Right now: ${level} air at AQI ${aqi}/10, leading channel ${driverStr}.\n\nAsk me about a specific compound, what's elevated, what to do, the trend, or whether the data is real.`;
}

function trimUrl(url) {
  return (url || '').replace(/^wss?:\/\//, '');
}

// ── public entry point ──────────────────────────────────────────────────

export function respond(text, ctx = {}) {
  const t = (text || '').trim().toLowerCase();
  if (!t) return "I'm here whenever you're ready.";

  const { latest = null, history = [], status = {} } = ctx;

  if (matches(t, ['is this real', 'is the data real', 'is it live', 'live?', 'real?', 'are you connected', "where's this from", 'where is this from', 'source'])) {
    return statusReply(status, latest);
  }

  if (matches(t, ["how's the air", 'how is the air', 'whats the air', "what's the air", 'air right now', 'current air', 'aqi', 'air quality', "what's it like", "how's it going"])) {
    return airSummary(latest);
  }

  if (matches(t, ['elevated', "what's high", 'whats high', "what's bad", 'whats bad', 'over the limit', 'above normal', 'concerns', 'problems', "what's wrong", 'whats wrong'])) {
    return elevatedReply(latest);
  }

  // Specific intents win over generic 'should i…'
  if (matches(t, ['filter', 'purifier', 'fan speed', 'turn on the fan'])) {
    return filterReply(latest);
  }

  if (matches(t, ['stress', 'cortisol', 'tension', 'anxious', 'anxiety'])) {
    return stressReply(latest);
  }

  const cmp = findCompound(t);
  if (cmp) return compoundReply(cmp, latest);

  if (matches(t, ['smell', 'aroma', 'scent', 'odor', 'odour'])) {
    return aromaReply(latest);
  }

  if (matches(t, ['trend', 'better', 'worse', 'last few', 'last hour', 'changing', 'getting'])) {
    return trendReply(history);
  }

  if (matches(t, ['should i', 'recommend', 'recommendation', 'advice', 'what do i do', 'should we', 'is it safe', 'safe to', 'what now'])) {
    return recommendation(latest);
  }

  return fallback(latest);
}
