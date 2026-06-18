#!/usr/bin/env python3
"""
Augsburg 86150 - Live-Viewer & Godfather-Konsole
=================================================
Zeigt Transkripte als Live-Webseite: rechts eine Sidebar mit allen
Episoden (klickbar, Archiv), Hauptansicht folgt default der neuesten
Aufzeichnung. Godfather-Anweisungen landen in godfather.txt, der
Orchestrator injiziert sie beim naechsten Erzaehler-Turn.

Benutzung:
  python3 viewer.py            # lauscht auf 0.0.0.0:8086
  python3 viewer.py --port 9000

Keine Abhaengigkeiten ausser Python-Stdlib. Markdown wird clientseitig
gerendert (marked.js via CDN - Kiste hat Internet).
"""

import argparse
import json
import re
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

BASE_DIR = Path(__file__).resolve().parent
GODFATHER_FILE = BASE_DIR / "godfather.txt"
TRANSCRIPT_RE = re.compile(r"^transkript_[0-9A-Za-z_]+\.md$")
WEEKDAYS_FULL = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag",
                 "Samstag", "Sonntag"]

PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Augsburg 86150 — Live</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
  body { background:#14121a; color:#e8e4da; font-family:Georgia,serif;
         margin:0; }
  #layout { display:flex; max-width:1500px; margin:0; gap:1.5rem;
            padding:1.5rem; align-items:flex-start; }
  #main { flex:1; min-width:0; }
  h1,h2 { font-family:Futura,'Trebuchet MS',sans-serif; }
  #titlebar { display:flex; justify-content:space-between; align-items:baseline;
              border-bottom:2px solid #c9a227; margin-bottom:1rem; }
  #titlebar h1 { color:#c9a227; margin:.2rem 0; }
  #status { color:#777; font-size:.85rem; }
  #script h2 { color:#c9a227; border-bottom:1px dotted #444; padding-bottom:.2rem; }
  #script blockquote { color:#9a93a8; border-left:3px solid #c9a227;
                       margin-left:0; padding-left:1rem; font-style:italic; }
  #script strong { color:#7ec8e3; }
  /* Pro-Figur-Farben (per JS auf die Sprecher-strong-Tags gesetzt) */
  #script strong.sp-herbert  { color:#ff6b5e; }
  #script strong.sp-gisela   { color:#6ee7a8; }
  #script strong.sp-carmen   { color:#5fc9ff; }
  #script strong.sp-schmidt  { color:#c9a8ff; }
  #script strong.sp-viktor   { color:#f5d142; }
  #script strong.sp-brunner  { color:#f0a868; }
  #script strong.sp-other    { color:#9aa0aa; }
  #godfather { position:sticky; bottom:0; background:#1d1a26; padding:1rem;
               border:1px solid #c9a227; border-radius:8px; margin-top:2rem; }
  #godfather label { color:#c9a227; font-family:sans-serif; font-size:.9rem; }
  #godfather form { display:flex; gap:.5rem; margin-top:.4rem; }
  #godfather input { flex:1; background:#14121a; color:#e8e4da;
                     border:1px solid #555; border-radius:4px; padding:.5rem; }
  #godfather button { background:#c9a227; color:#14121a; border:none;
                      border-radius:4px; padding:.5rem 1rem; font-weight:bold;
                      cursor:pointer; }
  #feedback { color:#7ec8e3; font-size:.85rem; min-height:1.2em; margin-top:.3rem; }
  /* Sidebar */
  #sidebar { width:430px; flex-shrink:0; position:sticky; top:1.5rem;
             max-height:calc(100vh - 3rem); overflow-y:auto;
             background:#1d1a26; border:1px solid #3a3548; border-radius:8px;
             padding:.8rem; font-family:sans-serif; }
  .sb-head { color:#c9a227; margin:.2rem 0 .5rem; font-size:.95rem;
             font-weight:bold; display:flex; justify-content:space-between;
             align-items:center; }
  #epHead { cursor:pointer; user-select:none; }
  #epToggle { color:#7ec8e3; font-size:.8rem; }
  .sb-head .sub { color:#7ec8e3; font-weight:normal; font-size:.72rem; }
  .ep { display:block; padding:.45rem .5rem; margin-bottom:.3rem;
        border-radius:5px; cursor:pointer; font-size:.82rem; color:#bbb;
        border:1px solid transparent; }
  .ep:hover { background:#2a2638; }
  .ep.sel { border-color:#c9a227; color:#fff; background:#2a2638; }
  .ep .when { color:#7ec8e3; font-weight:bold; }
  .ep .live { color:#4ade80; font-weight:bold; }
  .ep .size { color:#666; float:right; font-weight:normal; }
  .ep .eptitle { color:#c9a227; font-size:.72rem; font-style:italic; margin-top:.15rem; }
  /* Personen-Panel */
  #personaPanel { margin-top:1rem; border-top:1px solid #3a3548; padding-top:.7rem; }
  #personas { display:grid; grid-template-columns:1fr; gap:.55rem; }
  /* Flip-Card: Vorderseite = Live-Stats, Rueckseite = Dossier */
  .pcard { perspective:1100px; height:212px; cursor:pointer; }
  .pcard-inner { position:relative; width:100%; height:100%;
                 transition:transform .55s; transform-style:preserve-3d; }
  .pcard.flipped .pcard-inner { transform:rotateY(180deg); }
  .pface { position:absolute; inset:0; backface-visibility:hidden;
           -webkit-backface-visibility:hidden; background:#14121a;
           border:1px solid #2f2a3d; border-radius:6px; font-size:.78rem; }
  .pface.back { transform:rotateY(180deg); }
  /* Scroll auf innerem Wrapper, NICHT auf der 3D-Flaeche (sonst bricht
     backface-visibility in Chrome -> beide Seiten sichtbar). */
  .pf-scroll { position:absolute; inset:0; overflow-y:auto; padding:.5rem .6rem; }
  .flip-hint { position:absolute; top:.3rem; right:.5rem; color:#5a5566; font-size:.72rem; }
  .pcard .pname { font-weight:bold; font-size:.86rem; margin-bottom:.35rem;
                  display:flex; justify-content:space-between; padding-right:1rem; }
  .pcard .pname .pcount { color:#666; font-weight:normal; font-size:.7rem; }
  .dossier .dsh { color:#c9a227; font-size:.66rem; text-transform:uppercase;
                  letter-spacing:.03em; margin:.4rem 0 .15rem; }
  .dossier .drel { font-size:.72rem; color:#9aa0aa; margin:.08rem 0; }
  .dossier .dfact { color:#cdc6da; font-size:.72rem; margin:.06rem 0; }
  .dossier .ddiary { font-style:italic; color:#bbb; font-size:.72rem; margin:.12rem 0; }
  .dossier .ddiary i { color:#7ec8e3; font-style:normal; }
  .stat { display:flex; align-items:center; gap:.4rem; margin:.12rem 0;
          cursor:help; }
  .stat .lbl { width:72px; color:#9a93a8; flex-shrink:0; white-space:nowrap; }
  .stat .track { flex:1; height:7px; background:#26222f; border-radius:4px;
                 overflow:hidden; }
  .stat .fill { display:block; height:100%; background:#c9a227; border-radius:4px; }
  .stat .num { width:38px; text-align:right; color:#cfc8d8; flex-shrink:0; }
  .stat .num.dim { color:#5a5566; }
  .pmood { margin-top:.35rem; color:#bbb; font-style:italic; }
  .phost { margin-top:.2rem; color:#ff8a7a; font-size:.74rem; }
  #drama { margin-top:.6rem; padding:.5rem .6rem; background:#221a1a;
           border:1px solid #5e3535; border-radius:6px; font-size:.8rem; }
  #drama .dlabel { color:#ff8a7a; font-weight:bold; }
  #drama .dtrack { height:9px; background:#26222f; border-radius:4px;
                   overflow:hidden; margin-top:.3rem; }
  #drama .dfill { display:block; height:100%;
                  background:linear-gradient(90deg,#c9a227,#ff5e5e); }
  .pmuted { color:#666; font-size:.78rem; padding:.4rem 0; }
  /* Sprecher-Farben auch ausserhalb von #script (Personen-Karten) */
  .sp-herbert{color:#ff6b5e} .sp-gisela{color:#6ee7a8} .sp-carmen{color:#5fc9ff}
  .sp-schmidt{color:#c9a8ff} .sp-viktor{color:#f5d142} .sp-brunner{color:#f0a868}
  .sp-other{color:#9aa0aa}
  /* Secret-Tracker */
  .psecret { margin-top:.4rem; padding-top:.35rem; border-top:1px dashed #2f2a3d; }
  .psecret .slabel { color:#c9a8ff; font-size:.74rem; margin-bottom:.15rem; }
  .psecret .srev { color:#ff5e5e; font-weight:bold; }
  .stat .fill.sfill { background:#a06bff; }
  #plot { margin-top:.6rem; padding:.5rem .6rem; background:#1a1622;
          border:1px solid #4a3a5e; border-radius:6px; font-size:.8rem; }
  #plot .plabel { color:#c9a8ff; font-weight:bold; }
</style>
</head>
<body>
<div id="layout">
  <div id="main">
    <div id="titlebar">
      <h1>🎬 Augsburg 86150</h1>
      <span><a href="/characters" style="color:#c9a227;font-size:.82rem;text-decoration:none">🎭 Personen</a> &nbsp;·&nbsp; <span id="status">verbinde …</span></span>
    </div>
    <div id="script"><em>Warte auf Transkript …</em></div>

    <div id="godfather">
      <label>👑 GODFATHER — dein Wort ist Gesetz (wirkt beim n&auml;chsten Erz&auml;hler-Turn):</label>
      <form id="gform">
        <input id="gtext" type="text" autocomplete="off"
               placeholder="z.B. Stromausfall im ganzen Viertel. Frau Schmidt verplappert sich.">
        <button type="submit">Eingrätschen</button>
      </form>
      <div id="feedback"></div>
    </div>
  </div>
  <div id="sidebar">
    <div class="sb-head" id="epHead">📼 Episoden <span id="epToggle">▶</span></div>
    <div id="eplist"><em style="color:#666">lade …</em></div>
    <div id="personaPanel">
      <div class="sb-head">🎭 Personen <span class="sub" id="personaEp"></span></div>
      <div id="personas"><div class="pmuted">…</div></div>
      <div id="plot"></div>
      <div id="drama"></div>
    </div>
  </div>
</div>

<script>
const scriptDiv = document.getElementById('script');
const statusEl  = document.getElementById('status');
const epList    = document.getElementById('eplist');
const personasEl = document.getElementById('personas');
const dramaEl    = document.getElementById('drama');
const plotEl     = document.getElementById('plot');
const personaEpEl = document.getElementById('personaEp');
let charsByName = {};            // Dossier-Daten aus /api/characters
const flipped = new Set();       // welche Karten gerade umgedreht sind

// Klick dreht die Karte (Flip-State ueberlebt Live-Updates via Set)
personasEl.addEventListener('click', (e) => {
  const card = e.target.closest('.pcard');
  if (!card) return;
  const n = card.dataset.name;
  if (flipped.has(n)) { flipped.delete(n); card.classList.remove('flipped'); }
  else { flipped.add(n); card.classList.add('flipped'); }
});

function pct(x) { return Math.round((Number(x) || 0) * 100) + '%'; }
function dossierHtml(c) {
  if (!c) return '<div class="pmuted">keine Daten</div>';
  const st = c.state || {};
  let h = `<div class="pname"><span class="${speakerClass(c.identity.name)}">`
        + `${esc(c.identity.name)}</span></div>`;
  if (c.identity.secret)
    h += `<div class="dsh">🔒 Geheimnis (nur du)</div>`
       + `<div class="dfact" style="color:#c9a8ff">`
       + `${esc(c.identity.secret.replace(/^DEIN GEHEIMNIS:\\s*/, ''))}</div>`;
  h += `<div class="dsh">Zustand</div>`
     + `<div class="drel">☕ Koffein ${st.caffeine}% · Selbstvertrauen ${pct(st.confidence)}`
     + ` · Deckung ${pct(st.secret_guard)}`
     + (st.drunkenness > 0 ? ` · Promille ${st.drunkenness}%` : '') + `</div>`;
  if (st.goal_today) h += `<div class="ddiary">🎯 ${esc(st.goal_today)}</div>`;
  const rel = c.relationships || {};
  if (Object.keys(rel).length) {
    h += '<div class="dsh">Beziehungen</div>';
    for (const [t, r] of Object.entries(rel))
      h += `<div class="drel"><span class="${speakerClass(t)}">${esc(t.split(' ')[0])}</span>`
         + ` — Vertrauen ${pct(r.trust)} · Misstrauen ${pct(r.suspicion)} · Zuneigung ${pct(r.affection)}</div>`;
  }
  const sus = c.suspicion_of_secrets || {};
  if (Object.keys(sus).length) {
    h += '<div class="dsh">Verdacht</div>';
    for (const [t, v] of Object.entries(sus))
      h += `<div class="drel">${esc(t.split(' ')[0])}: ${pct(v)}</div>`;
  }
  const canon = (c.memory && c.memory.canon) || [];
  if (canon.length) h += '<div class="dsh">Weiß sicher</div>'
    + canon.map(x => `<div class="dfact">• ${esc(x.fact)}</div>`).join('');
  const di = c.diary || [];
  if (di.length) h += '<div class="dsh">Tagebuch</div>'
    + di.slice(-4).map(x => `<div class="ddiary"><i>T${x.day}:</i> „${esc(x.entry)}"</div>`).join('');
  if (!Object.keys(rel).length && !di.length && !canon.length)
    h += '<div class="pmuted" style="margin-top:.5rem">Noch keine Entwicklung — '
       + 'fuellt sich nach dem ersten Reflexions-Lauf (Tagesende).</div>';
  return h;
}
let lastContent = '', stickToBottom = true;
let selected = null;   // null = immer der neuesten Folge folgen (LIVE)
let epData = [];           // gecachte Episodenliste
let collapsed = true;      // Episodenliste eingeklappt -> nur gewaehlte Folge
let lastStatsKey = '';     // verhindert unnoetiges Neu-Rendern der Karten

window.addEventListener('scroll', () => {
  stickToBottom = (window.innerHeight + window.scrollY) >= document.body.offsetHeight - 60;
});

// Jede Figur kriegt ihre eigene Farbe ueber eine CSS-Klasse am <strong>.
// Markdown kann das nicht, also nachtraeglich im DOM.
const SPEAKER_CLASS = [
  [/^herbert/i, 'sp-herbert'], [/^gisela/i, 'sp-gisela'],
  [/^carmen/i,  'sp-carmen'],  [/^frau schmidt/i, 'sp-schmidt'],
  [/^viktor/i,  'sp-viktor'],  [/^hausmeister|^brunner/i, 'sp-brunner'],
];
function colorizeSpeakers() {
  scriptDiv.querySelectorAll('strong').forEach(el => {
    const t = el.textContent.replace(/:\\s*$/, '').trim();
    const hit = SPEAKER_CLASS.find(([re]) => re.test(t));
    el.classList.add(hit ? hit[1] : 'sp-other');
  });
}

function fmtName(f) {
  const m = f.match(/transkript_(\\d{4})(\\d{2})(\\d{2})_(\\d{2})(\\d{2})(\\d{2})/);
  if (!m) return f;
  return `${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]}`;
}
function fmtEp(t) {
  if (!t.weekday) return fmtName(t.file);
  const base = (t.weekday === 'Samstag') ? `${t.weekday}nacht 🍸` : t.weekday;
  return t.week ? `Woche ${t.week} · ${base}` : base;
}

async function refreshList() {
  try {
    const r = await fetch('/api/transcripts');
    epData = await r.json();
  } catch (e) { /* Liste behalten */ }
  renderList();
}

function renderList() {
  epList.innerHTML = '';
  document.getElementById('epToggle').textContent = collapsed ? '▶' : '▼';
  epData.forEach((t, i) => {
    const isSel = selected ? (t.file === selected) : i === 0;
    // Eingeklappt: nur die gewaehlte (bzw. LIVE-)Folge zeigen.
    if (collapsed && !isSel) return;
    const div = document.createElement('div');
    div.className = 'ep' + (isSel ? ' sel' : '');
    div.innerHTML = `<span class="when">${fmtEp(t)}</span>`
      + (i === 0 ? ' <span class="live">● LIVE</span>' : '')
      + `<span class="size">${(t.size/1024).toFixed(1)}k</span>`
      + (t.title ? `<div class="eptitle">»${esc(t.title)}«</div>` : '');
    div.onclick = () => {
      selected = (i === 0) ? null : t.file;
      collapsed = true;                 // nach Auswahl wieder einklappen
      lastContent = ''; lastStatsKey = '';
      renderList(); refreshContent(); refreshStats();
    };
    epList.appendChild(div);
  });
}

document.getElementById('epHead').onclick = () => { collapsed = !collapsed; renderList(); };

// ---- Persona-Stats ----
const RATED = [['snark','Snark'], ['sturheit','Sturheit'], ['neugier','Neugier'],
               ['logik_emotion','Logik↔Emo'], ['stress','Stress'], ['verdacht','Verdacht']];

function speakerClass(name) {
  const hit = SPEAKER_CLASS.find(([re]) => re.test(name));
  return hit ? hit[1] : 'sp-other';
}
function esc(s) {
  return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;')
                  .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function statRow(label, obj) {
  const v = obj ? (obj.value || 0) : 0;
  const ev = obj ? (obj.evidence || '') : '';
  const dim = (ev === 'kein Signal') ? ' dim' : '';   // kein Signal -> gedimmt
  return `<div class="stat" title="${esc(ev)}">`
    + `<span class="lbl">${label}</span>`
    + `<span class="track"><span class="fill" style="width:${v*10}%"></span></span>`
    + `<span class="num${dim}">${v*10}%</span></div>`;
}

async function refreshStats() {
  const surl = '/api/stats' + (selected ? `?file=${encodeURIComponent(selected)}` : '');
  let d, cd;
  try {
    [d, cd] = await Promise.all([
      fetch(surl).then(r => r.json()).catch(() => ({})),
      fetch('/api/characters').then(r => r.json()).catch(() => ({characters: [], season: {}})),
    ]);
  } catch (e) { return; }
  charsByName = {};
  (cd.characters || []).forEach(c => { charsByName[c.identity.name] = c; });

  const personas = d.personas || {};
  const roster = (cd.characters || []).map(c => c.identity.name);
  roster.sort((a, b) => (personas[b]?.dominance || 0) - (personas[a]?.dominance || 0));

  // Rebuild nur bei Aenderung; Flip-State steckt im Set -> ueberlebt.
  const key = JSON.stringify([selected, d.turn_count, roster.map(n =>
    [(charsByName[n]?.diary || []).length,
     Object.keys(charsByName[n]?.relationships || {}).length,
     personas[n]?.dominance || 0])]);
  if (key === lastStatsKey) return;
  lastStatsKey = key;
  personaEpEl.textContent = d.scene_count ? `${d.scene_count} Szenen` : '';

  const secretByChar = {};
  (d.secrets || []).forEach(s => { secretByChar[s.character] = s; });

  let html = '';
  for (const name of roster) {
    const p = personas[name];
    const c = charsByName[name];
    let front = `<span class="flip-hint">⇄</span><div class="pname">`
      + `<span class="${speakerClass(name)}">${esc(name)}</span>`;
    if (p && p.spoke) front += `<span class="pcount" title="Redebeiträge · Wörter">`
      + `${p.dominance}× · ${p.verbosity}w</span>`;
    else front += `<span class="pcount">`
      + `${c && c.identity.active_from_day > 1 ? 'ab Tag ' + c.identity.active_from_day : 'still'}</span>`;
    front += `</div>`;
    if (p && p.spoke && p.rated) {
      for (const [k, label] of RATED) front += statRow(label, p.rated[k]);
      if (p.rated.stimmung) front += `<div class="pmood">„${esc(p.rated.stimmung)}"</div>`;
      if (p.conflict && p.conflict.target)
        front += `<div class="phost" title="${esc(p.conflict.evidence || '')}">`
          + `Im Streit mit: ${esc(p.conflict.target)} (${p.conflict.intensity}/10)</div>`;
      const sec = secretByChar[name];
      if (sec) front += `<div class="psecret" title="${esc(sec.evidence || '')}">`
        + `<div class="slabel">🔒 ${esc(sec.label || 'Geheimnis')}`
        + (sec.revealed ? ' <span class="srev">enthüllt</span>' : '') + `</div>`
        + `<div class="stat"><span class="lbl">Enthüllt</span><span class="track">`
        + `<span class="fill sfill" style="width:${sec.exposure || 0}%"></span></span>`
        + `<span class="num">${sec.exposure || 0}%</span></div></div>`;
    } else if (c) {
      const st = c.state || {};
      front += statRow('Stress', {value: Math.round((st.stress || 0) * 10), evidence: ''});
      front += `<div class="stat"><span class="lbl">Koffein</span><span class="track">`
        + `<span class="fill" style="width:${st.caffeine || 0}%"></span></span>`
        + `<span class="num">${st.caffeine}</span></div>`;
      front += `<div class="pmood">„${esc(st.mood || '')}"</div>`;
      front += `<div class="pmuted">noch nicht im Bild</div>`;
    } else front += '<div class="pmuted">—</div>';

    const back = `<span class="flip-hint">⇄</span><div class="dossier">${dossierHtml(c)}</div>`;
    html += `<div class="pcard${flipped.has(name) ? ' flipped' : ''}" data-name="${esc(name)}">`
      + `<div class="pcard-inner">`
      + `<div class="pface front"><div class="pf-scroll">${front}</div></div>`
      + `<div class="pface back"><div class="pf-scroll">${back}</div></div>`
      + `</div></div>`;
  }
  personasEl.innerHTML = html || '<div class="pmuted">keine Figuren</div>';

  const plot = d.plot || {revealed: 0, total: 0};
  plotEl.innerHTML = `<span class="plabel">🔓 Geheimnisse enthüllt</span>`
    + `<span style="float:right">${plot.revealed}/${plot.total}</span>`;
  const di = d.drama_index || {value: 0};
  dramaEl.innerHTML = `<span class="dlabel">🔥 Drama / Chaos</span>`
    + `<span style="float:right">${di.value}/10</span>`
    + `<span class="dtrack"><span class="dfill" style="width:${(di.value || 0) * 10}%"></span></span>`;
  dramaEl.title = `Ø Stress ${di.avg_stress ?? '?'}`;
}

async function refreshContent() {
  try {
    const url = selected ? `/api/transcript?file=${encodeURIComponent(selected)}`
                         : '/api/transcript';
    const r = await fetch(url);
    const d = await r.json();
    statusEl.textContent = (d.file || 'kein Transkript gefunden')
                         + (selected ? ' (Archiv)' : '');
    if (d.content && d.content !== lastContent) {
      lastContent = d.content;
      scriptDiv.innerHTML = marked.parse(d.content);
      colorizeSpeakers();
      if (!selected && stickToBottom) window.scrollTo(0, document.body.scrollHeight);
    }
  } catch (e) { statusEl.textContent = 'Verbindung weg …'; }
}

setInterval(() => { refreshList(); refreshContent(); refreshStats(); }, 2000);
refreshList(); refreshContent(); refreshStats();

document.getElementById('gform').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const input = document.getElementById('gtext');
  const text = input.value.trim();
  if (!text) return;
  await fetch('/api/godfather', {method:'POST', body: text});
  input.value = '';
  document.getElementById('feedback').textContent =
    '✓ Anweisung deponiert — der Erzähler kriegt sie beim nächsten Turn.';
  setTimeout(() => document.getElementById('feedback').textContent = '', 5000);
});
</script>
</body>
</html>
"""


def all_transcripts() -> list[Path]:
    """Alle transkript_*.md, neueste zuerst."""
    return sorted(BASE_DIR.glob("transkript_*.md"), reverse=True)


CHAR_DIR = BASE_DIR / "characters"
SEASON_FILE = BASE_DIR / "season.json"


def all_character_states() -> dict:
    chars = []
    for p in sorted(CHAR_DIR.glob("*.json")):
        try:
            chars.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            pass
    season = {}
    if SEASON_FILE.is_file():
        try:
            season = json.loads(SEASON_FILE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {"characters": chars, "season": season}


CHARACTERS_PAGE = """<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Augsburg 86150 — Personen</title>
<style>
  body{background:#14121a;color:#e8e4da;font-family:Georgia,serif;margin:0;padding:1.2rem;}
  a{color:#c9a227;} .top{display:flex;justify-content:space-between;align-items:baseline;
    border-bottom:2px solid #c9a227;margin-bottom:1rem;}
  h1{color:#c9a227;font-family:Futura,'Trebuchet MS',sans-serif;margin:.2rem 0;font-size:1.3rem;}
  #day{color:#7ec8e3;font-size:.9rem;}
  #grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:1rem;}
  .card{background:#1d1a26;border:1px solid #3a3548;border-radius:9px;padding:.8rem .9rem;}
  .hd{display:flex;justify-content:space-between;align-items:baseline;
     border-bottom:1px dotted #444;padding-bottom:.35rem;margin-bottom:.5rem;}
  .nm{font-weight:bold;font-size:1.05rem;font-family:sans-serif;}
  .meta{color:#777;font-size:.72rem;}
  .sect{margin:.5rem 0;font-size:.82rem;}
  .sh{color:#c9a227;font-family:sans-serif;font-size:.74rem;text-transform:uppercase;
     letter-spacing:.04em;margin-bottom:.3rem;}
  .b{display:flex;align-items:center;gap:.4rem;margin:.15rem 0;}
  .bl{width:104px;color:#9a93a8;flex-shrink:0;font-size:.76rem;}
  .bt{flex:1;height:7px;background:#26222f;border-radius:4px;overflow:hidden;}
  .bf{display:block;height:100%;border-radius:4px;}
  .bn{width:34px;text-align:right;color:#cfc8d8;font-size:.74rem;}
  .mood{margin-top:.3rem;color:#bbb;} .goal{margin-top:.25rem;color:#f0d878;font-style:italic;}
  .rel{display:flex;align-items:center;gap:.45rem;margin:.12rem 0;font-size:.76rem;}
  .rt{width:80px;font-weight:bold;} .mini{color:#9aa0aa;}
  .fact{color:#cdc6da;margin:.1rem 0;} .fact i{color:#666;}
  .diary{color:#bbb;font-style:italic;margin:.2rem 0;} .diary i{color:#7ec8e3;font-style:normal;}
  .empty{color:#555;}
</style></head><body>
<div class="top"><h1>🎭 Augsburg 86150 — Personen</h1>
  <span><span id="day">…</span> &nbsp;·&nbsp; <a href="/">← Live</a></span></div>
<div id="grid"><p class="empty">lade …</p></div>
<script>
const SP=[[/^herbert/i,'#ff6b5e'],[/^gisela/i,'#6ee7a8'],[/^carmen/i,'#5fc9ff'],
  [/frau schmidt/i,'#c9a8ff'],[/viktor/i,'#f5d142'],[/brunner|hausmeister/i,'#f0a868']];
const col=n=>{const h=SP.find(([r])=>r.test(n));return h?h[1]:'#9aa0aa';};
const esc=s=>(''+(s||'')).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
function bar(label,v,max,c){const p=Math.max(0,Math.min(100,Math.round((v/max)*100)));
  return `<div class="b"><span class="bl">${esc(label)}</span><span class="bt">`
    +`<span class="bf" style="width:${p}%;background:${c}"></span></span>`
    +`<span class="bn">${p}%</span></div>`;}
const rpct=x=>Math.round((+x||0)*100)+'%';
async function load(){
  let d; try{d=await(await fetch('/api/characters')).json();}catch(e){return;}
  document.getElementById('day').textContent=`Tag ${d.season.day||0} · ${d.season.weekday||'—'}`;
  let html='';
  for(const c of d.characters){
    const id=c.identity,st=c.state,nm=id.name,k=col(nm);
    html+=`<div class="card" style="border-color:${k}55"><div class="hd">`
      +`<span class="nm" style="color:${k}">${esc(nm)}</span>`
      +`<span class="meta">${esc(id.role)} · ${esc(id.model)}`
      +`${id.active_from_day>1?` · ab Tag ${id.active_from_day}`:''}</span></div>`;
    html+=`<div class="sect">`+bar('Stress',st.stress,1,'#ff7a6b')
      +bar('Koffein',st.caffeine,100,'#c9a227')+bar('Selbstvertrauen',st.confidence,1,'#6ee7a8')
      +(st.drunkenness>0?bar('Promille',st.drunkenness,100,'#a06bff'):'')
      +`<div class="mood">Stimmung: <b>${esc(st.mood)}</b></div>`
      +(st.goal_today?`<div class="goal">🎯 ${esc(st.goal_today)}</div>`:'')+`</div>`;
    const rel=c.relationships||{};
    if(Object.keys(rel).length){html+=`<div class="sect"><div class="sh">Beziehungen</div>`;
      for(const [t,r] of Object.entries(rel)) html+=`<div class="rel">`
        +`<span class="rt" style="color:${col(t)}">${esc(t.split(' ')[0])}</span>`
        +`<span class="mini">Vertrauen ${rpct(r.trust)}</span><span class="mini">Misstrauen ${rpct(r.suspicion)}</span>`
        +`<span class="mini">Zuneigung ${rpct(r.affection)}</span></div>`;
      html+=`</div>`;}
    const sus=c.suspicion_of_secrets||{};
    if(Object.keys(sus).length){html+=`<div class="sect"><div class="sh">Verdacht (Geheimnisse)</div>`;
      for(const [t,v] of Object.entries(sus)) html+=bar(t.split(' ')[0],v,1,'#f5d142');
      html+=`</div>`;}
    const canon=(c.memory&&c.memory.canon)||[];
    if(canon.length){html+=`<div class="sect"><div class="sh">Weiß sicher</div>`
      +canon.map(x=>`<div class="fact">• ${esc(x.fact)} <i>(Tag ${x.day})</i></div>`).join('')+`</div>`;}
    const di=c.diary||[];
    if(di.length){html+=`<div class="sect"><div class="sh">Tagebuch</div>`
      +di.slice(-6).map(x=>`<div class="diary"><i>Tag ${x.day}:</i> „${esc(x.entry)}"</div>`).join('')+`</div>`;}
    html+=`</div>`;
  }
  document.getElementById('grid').innerHTML=html||'<p class="empty">Noch keine Figuren.</p>';
}
setInterval(load,3000);load();
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif url.path == "/characters":
            self._send(200, CHARACTERS_PAGE.encode(), "text/html; charset=utf-8")
        elif url.path == "/api/characters":
            self._send(200, json.dumps(all_character_states(), ensure_ascii=False).encode(),
                       "application/json")
        elif url.path == "/api/transcripts":
            titles = {}
            tf = BASE_DIR / "titles.json"
            if tf.is_file():
                try:
                    titles = json.loads(tf.read_text(encoding="utf-8"))
                except Exception:  # noqa: BLE001
                    pass
            data = []
            for t in all_transcripts():
                m = re.search(r"_d(\d+)_", t.name)
                day = int(m.group(1)) if m else None
                # Monat/Staffel: 6-Tage-Wochen (Mo-Sa)
                week = ((day - 1) // 6 + 1) if day else None
                weekday = WEEKDAYS_FULL[(day - 1) % 6] if day else None
                data.append({"file": t.name, "size": t.stat().st_size,
                             "day": day, "week": week, "weekday": weekday,
                             "title": titles.get(t.name, "")})
            self._send(200, json.dumps(data, ensure_ascii=False).encode(),
                       "application/json")
        elif url.path == "/api/transcript":
            wanted = parse_qs(url.query).get("file", [None])[0]
            if wanted:
                # Nur validierte Dateinamen, kein Pfad-Gefrickel
                if not TRANSCRIPT_RE.match(wanted) or not (BASE_DIR / wanted).is_file():
                    self._send(404, b'{"error": "not found"}', "application/json")
                    return
                t = BASE_DIR / wanted
            else:
                ts = all_transcripts()
                t = ts[0] if ts else None
            data = {
                "file": t.name if t else None,
                "content": t.read_text(encoding="utf-8") if t else "",
            }
            self._send(200, json.dumps(data).encode(), "application/json")
        elif url.path == "/api/stats":
            # Persona-Stats aus der Sidecar-Datei stats_<ts>.json. Fehlt sie,
            # kommt {} zurueck -> Dashboard zeigt "noch keine Auswertung".
            wanted = parse_qs(url.query).get("file", [None])[0]
            if wanted:
                if not TRANSCRIPT_RE.match(wanted):
                    self._send(200, b"{}", "application/json")
                    return
                tname = wanted
            else:
                ts = all_transcripts()
                tname = ts[0].name if ts else None
            if not tname:
                self._send(200, b"{}", "application/json")
                return
            suffix = tname[len("transkript_"):].replace(".md", ".json")
            sidecar = BASE_DIR / ("stats_" + suffix)
            if not sidecar.is_file():
                self._send(200, b"{}", "application/json")
                return
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            # Subjektive Achsen (snark/sturheit/neugier/logik_emotion) aus dem
            # Scorer-Sidecar drueberlegen, falls vorhanden.
            traits_file = BASE_DIR / ("traits_" + suffix)
            if traits_file.is_file():
                try:
                    traits = json.loads(traits_file.read_text(encoding="utf-8"))
                    for name, p in (data.get("personas") or {}).items():
                        if name in traits and p.get("rated"):
                            p["rated"].update(traits[name])
                except Exception:  # noqa: BLE001
                    pass
            self._send(200, json.dumps(data, ensure_ascii=False).encode(),
                       "application/json")
        else:
            self._send(404, b"404", "text/plain")

    def do_POST(self):
        if self.path == "/api/godfather":
            length = int(self.headers.get("Content-Length", 0))
            text = self.rfile.read(length).decode("utf-8").strip()
            if text:
                # Anhaengen statt ueberschreiben: mehrere Eingriffe vor dem
                # naechsten Erzaehler-Turn gehen sonst verloren.
                with GODFATHER_FILE.open("a", encoding="utf-8") as f:
                    f.write(text + "\n")
            self._send(200, b'{"ok": true}', "application/json")
        else:
            self._send(404, b"404", "text/plain")

    def log_message(self, fmt, *fargs):
        pass  # kein Request-Spam auf stdout


def main():
    ap = argparse.ArgumentParser(description="Augsburg 86150 Live-Viewer")
    ap.add_argument("--port", type=int, default=8086)
    args = ap.parse_args()
    srv = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"Live-Viewer laeuft: http://0.0.0.0:{args.port}  (Strg+C beendet)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
