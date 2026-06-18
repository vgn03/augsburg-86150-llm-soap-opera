#!/usr/bin/env python3
"""
engine.py — Augsburg 86150 v2: Tages-Orchestrator + Reflexion + Continuity.

Ablauf eines Tages:
  1. Showrunner weist jeder Figur ein TAGESZIEL zu (LLM, 1 Call).
  2. Tages-Loop: Stage-Manager (Erzaehler) fuehrt Szenen + Sprecherwahl;
     jede Figur spricht als Agent mit INJIZIERTEM Zustand (Stress, Koffein,
     Ziel, Erinnerung, Verdacht) + Live-Tic-Nudge.
  3. Pro Replik laufen die deterministischen Mechaniken (mechanics.py):
     Koffein-Schwund, Geheimnis-Anstich -> Stress/Deckung/Verdacht/near_miss,
     Momentum, Tic-Detektion.
  4. Reflexion (LLM pro Figur): schreibt Zustand, Beziehungen, Verdacht,
     Tagebuch und canon-Fakten zurueck -> Tag N+1 ERINNERT sich.

Agents for everything: Showrunner, Erzaehler, jede Figur, Reflexion = je ein Call.
"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any

import llm
import mechanics
import state as S

BASE = Path(__file__).resolve().parent
GODFATHER_FILE = BASE / "godfather.txt"   # Live-Eingriffe aus dem Viewer

ACTOR_RULES = ("Antworte NUR als deine Figur, in direkter Rede, hoechstens 3 "
               "Saetze. Kein Erzaehltext, keine Sternchen-Aktionen, kein Markdown. "
               "Du kennst die Geheimnisse der anderen NICHT - nur was im Drehbuch "
               "steht. Dein eigenes Geheimnis waere eine KATASTROPHE, wenn es "
               "rauskaeme - du haeltst es mit aller Kraft: du leugnest, lenkst ab, "
               "gehst in die Offensive, selbst wenn man dich direkt darauf "
               "anspricht. Erst wenn du voellig in der Enge oder zu betrunken bist, "
               "broeckelt es - und auch dann straeubst du dich. Nur lateinische "
               "Schrift. KRITISCH: Gib AUSSCHLIESSLICH die woertlich gesprochene "
               "Replik aus - keine Analyse, keine Vorrede, kein 'Okay'/'Let me'/'I "
               "need to', kein lautes Nachdenken, keine Erklaerung. Beginne SOFORT "
               "mit den Worten der Figur.")

# qwen3 leakt trotz think=False manchmal sein Reasoning in den Text. Erkennen
# und einmal haerter nachfordern, sonst aus dem Text bergen.
_REASON = re.compile(
    r"^\s*(okay|alright|so[,\s]|let me|let's|i need|i should|the user|"
    r"looking at|first[,\s]|hmm|as \w+ gruber|based on|the scene|now,|well,|"
    r"he |his |she |her |they |maybe|perhaps|since |given )", re.I)


def _looks_reasoning(t: str) -> bool:
    if not t:
        return True
    if _REASON.match(t):
        return True
    low = t.lower()
    return ("i need to respond" in low or "next line" in low
            or "my secret" in low or "the user is asking" in low)


def _trim_sentences(t: str, max_s: int = 3) -> str:
    parts = re.split(r"(?<=[.!?])\s+", t.strip())
    return " ".join(parts[:max_s]).strip()


def figure_say(char: dict, sysp: str, usr: str, rp: float) -> str:
    """Figuren-Call mit Schutz gegen Reasoning-Leak UND Erzaehltext/Regie."""
    name = char["identity"]["name"]
    first = re.escape(name.split()[0])

    def _clean(t: str) -> str:
        t = re.sub(r"\([^)]*\)", "", t)   # (Regieanweisungen) raus
        t = re.sub(r"\*[^*]*\*", "", t)   # *Sternchen-Aktionen* raus
        return t.strip().strip('"').strip()

    def _bad(t: str) -> bool:
        if not t or _looks_reasoning(t):
            return True
        # Selbst-Narration: beginnt mit eigenem Namen + KEIN Doppelpunkt
        return bool(re.match(rf"^{first}\b(?!\s*[:\-])", t))

    last = ""
    for attempt in range(2):
        sp = sysp if attempt == 0 else (
            sysp + "\n\nNUR die woertlich gesprochene Replik der Figur. KEINE "
            "Handlungsbeschreibung ('Sie schaut/zeigt'), keine Klammern, kein "
            "Erzaehltext, keine Vorrede. Sofort die Worte.")
        last = _clean(llm.chat(char["identity"]["model"], sp, usr,
                               temperature=0.85 if attempt == 0 else 0.6,
                               extra={"repeat_penalty": rp, "repeat_last_n": 1024}))
        if not _bad(last):
            return _trim_sentences(last)
    # Bergung: erste brauchbare Zeile
    for ln in [l.strip() for l in last.splitlines() if l.strip()]:
        if not _bad(_clean(ln)):
            return _trim_sentences(_clean(ln))
    return _trim_sentences(last)

DAY_PHASES = ["Morgens (Ankunft im Buero)", "Vormittag", "Mittag",
              "Nachmittag", "Feierabend (Tag klingt aus)"]

WEEKDAYS_FULL = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag",
                 "Samstag", "Sonntag"]

# Eine STAFFEL = ein MONAT = 4 Arbeitswochen a 6 Tage (Mo-Sa) = 24 Tage.
WEEK_DAYS = 6                 # Mo-Sa (Sonntag frei)
SEASON_WEEKS = 4
SEASON_DAYS = WEEK_DAYS * SEASON_WEEKS   # 24

# Faellt die Deckung (secret_guard) eines Geheimnistraegers unter diese Schwelle
# und wird das Geheimnis erneut angestochen, PLATZT es (Enthuellung).
REVEAL_GUARD = 0.18


def week_of(day: int) -> int:
    return (day - 1) // WEEK_DAYS + 1


def weekday_of(day: int) -> str:
    return WEEKDAYS_FULL[(day - 1) % WEEK_DAYS]   # Mo..Sa


def clock_str(turn: int, max_turns: int,
              start_min: int = 8 * 60, end_min: int = 17 * 60 + 30) -> str:
    """Uhr, linear ueber die Beitraege. Default Arbeitstag 08:00->17:30."""
    t = start_min + int((turn / max(max_turns, 1)) * (end_min - start_min))
    return f"{(t // 60) % 24:02d}:{t % 60:02d}"


def phase_for_bar(turn: int, max_turns: int) -> str:
    f = turn / max(max_turns, 1)
    if f < 0.4:
        return "Die Bar fuellt sich"
    if f < 0.75:
        return "Mitten in der Nacht"
    return "Spaete Stunde (alle angetrunken)"


def phase_for(timestr: str) -> str:
    h = int(timestr.split(":")[0])
    if h < 10:
        return "Morgens (Ankunft)"
    if h < 12:
        return "Vormittag"
    if h < 13:
        return "Mittagspause (Doener am Koenigsplatz?)"
    if h < 16:
        return "Nachmittag"
    return "Feierabend (Tag klingt aus)"


def deadline_note(season: dict) -> str:
    """Druck Richtung STAFFELFINALE (Monatsabschluss/Quartalscrunch am Monatsende).
    Waechst ueber den Monat; Freitag ist nur Ende der Arbeitswoche."""
    day = season.get("day", 1)
    left = max(0, SEASON_DAYS - day)
    wkend = " (Ende der Arbeitswoche)" if season.get("weekday") == "Freitag" else ""
    if left <= 1:
        return ("FINALE: Der Monatsabschluss/Quartalscrunch ist JETZT faellig - "
                "alles spitzt sich zu, die Wahrheit muss raus.")
    weeks = (left + WEEK_DAYS - 1) // WEEK_DAYS
    return (f"DRUCK: Noch ~{weeks} Woche(n) bis zum Quartalsabschluss am "
            f"Monatsende{wkend}. Die Anspannung waechst Tag fuer Tag.")

NARRATOR_SCHEMA = {
    "type": "object",
    "properties": {
        "scene": {"type": "string"},
        "next_speaker": {"type": "string"},
        "direction": {"type": "string"},
        "the_end": {"type": "boolean"},
    },
    "required": ["scene", "next_speaker", "direction", "the_end"],
}

DAYFOCUS_SCHEMA = {
    "type": "object",
    "properties": {"day_focus": {"type": "string"}},
    "required": ["day_focus"],
}

REFLECT_SCHEMA = {
    "type": "object",
    "properties": {
        "stress": {"type": "number"},
        "mood": {"type": "string"},
        "confidence": {"type": "number"},
        "diary": {"type": "string"},
        "today_summary": {"type": "string"},
        "canon": {"type": "array", "items": {"type": "string"}},
        "relationships": {
            "type": "array",
            "items": {"type": "object",
                      "properties": {"name": {"type": "string"},
                                     "trust": {"type": "number"},
                                     "suspicion": {"type": "number"},
                                     "affection": {"type": "number"}},
                      "required": ["name", "trust", "suspicion", "affection"]},
        },
    },
    "required": ["stress", "mood", "confidence", "diary", "today_summary"],
}

NARRATOR_MODEL = "qwen3:30b-a3b"
SHOWRUNNER_MODEL = "qwen3:30b-a3b"
REFLECT_MODEL = "qwen3:30b-a3b"
# Freitext (Titel, Recap) braucht ein CLEANES Instruct-Modell - qwen3 leakt
# sonst sein Reasoning ("Okay, let's tackle this..."). JSON-Rollen sind ok.
TEXT_MODEL = "gemma3:12b"

PREMISE = ("IT-Firma 'Gruber Systemhaus GmbH', Augsburger Maximilianstrasse. "
           "Der Kaffeeautomat ist kaputt, die Quartalszahlen stehen an, und "
           "jeder hier hat eine Leiche im Keller.")

BAR_PREMISE = ("Samstagnacht. Die Belegschaft der Gruber Systemhaus GmbH ist "
               "privat in einer Bar/einem Club am Augsburger Koenigsplatz "
               "gelandet - kein Chef-Modus, keine Hierarchie. Der Alkohol "
               "fliesst, die Zungen lockern sich, und was die Woche ueber "
               "unter dem Deckel blieb, droht heute Nacht herauszurutschen.")


# ---------------------------------------------------------------------------
def showrunner_plan(season: dict, chars: dict[str, dict],
                    premise: str = PREMISE) -> None:
    """Setzt nur einen leisen 'day_focus' (Regie-Notiz fuer den Erzaehler) -
    KEINE Tagesziele. Die Figuren handeln frei, getrieben von ihrem Geheimnis,
    ihrer Persoenlichkeit und ihren Beziehungen."""
    threads = "; ".join(t["q"] for t in season["open_threads"])
    sys = ("Du bist der SHOWRUNNER. Lege EINEN 'day_focus' fest: ein Satz, welche "
           "Spannung heute im Hintergrund schwelt und sich Richtung Freitag "
           "zuspitzt. Das ist nur DEINE Regie-Notiz fuer die Inszenierung - KEIN "
           "Auftrag an die Figuren; die handeln frei und alltagsnah.")
    usr = (f"PRAEMISSE: {premise}\nTAG: {season['weekday']} (Tag {season['day']}).\n"
           f"{deadline_note(season)}\nOFFENE FAEDEN: {threads}\n"
           f"BISHER BEKANNT: {', '.join(season.get('public_facts', [])) or 'noch nichts'}\n\n"
           "Gib day_focus als JSON.")
    out = llm.chat_json(SHOWRUNNER_MODEL, sys, usr, DAYFOCUS_SCHEMA)
    season["day_focus"] = out.get("day_focus", "")


def speaker_context(char: dict, scene: str, public: list[str], direction: str,
                    tic_nudge: str | None) -> str:
    st = char["state"]
    suspicions = char.get("suspicion_of_secrets", {})
    suspect_note = ""
    if suspicions:
        top = max(suspicions, key=suspicions.get)
        if suspicions[top] >= 0.5:
            suspect_note = (f"\n(Im Hinterkopf: du ahnst, dass {top.split()[0]} etwas "
                            f"verbirgt - aber bohr nur, wenn es sich natuerlich ergibt.)")
    mem = S.build_memory_context(char)
    parts = [
        mem if mem else "",
        f"\nDEIN ZUSTAND: Stress {st['stress']:.2f}, Stimmung {st['mood']}. "
        f"{mechanics.caffeine_note(char)} {mechanics.drunk_note(char)}".rstrip(),
        suspect_note,
        "\nVERHALTE DICH WIE EIN ECHTER KOLLEGE: Begruessung am Morgen, Kaffee-"
        "Gejammer, Smalltalk, Wochenende, das Wetter, normale Arbeit, kleine "
        "Sticheleien. Dein Ziel und dein Geheimnis schwelen nur im Untergrund und "
        "scheinen BLOSS AB UND ZU durch oder kommen unter Druck hoch - sie sind "
        "nicht der Inhalt jeder Aeusserung. Bleib alltagsnah und sinnvoll, kein "
        "aufgesetztes Drama.",
        f"\nAKTUELLE SZENE: {scene}",
        "\nBISHERIGES GESPRAECH:\n" + ("\n".join(public[-14:]) if public else "(Szene beginnt.)"),
        f"\nREGIE AN DICH: {direction or 'Reagiere natuerlich auf die Situation.'}",
        f"\n{tic_nudge}" if tic_nudge else "",
        f"\n\nGeh auf das zuletzt Gesagte ein, wie ein echter Mensch im Buero. "
        f"Du bist {char['identity']['name']}. Dein naechster Satz:",
    ]
    return "\n".join(p for p in parts if p)


def make_title(transcript: str) -> str:
    """Knackiger, ironischer Episodentitel wie in der Fernsehzeitung."""
    sys = ("Gib dieser Soap-Episode EINEN knackigen, ironischen deutschen Titel "
           "(3-6 Woerter), wie eine Fernsehzeitung. Nur der Titel, sonst nichts.")
    try:
        t = llm.chat(TEXT_MODEL, sys, f"Episode:\n{transcript[:4000]}\n\nTitel:",
                     temperature=0.8, num_predict=24)
    except Exception:  # noqa: BLE001
        return ""
    return t.strip().strip('"').splitlines()[0][:80] if t.strip() else ""


def make_recap(season: dict, chars: dict[str, dict]) -> str:
    """'Was bisher geschah' aus canon-Fakten + letzten Tagebucheintraegen."""
    bits = list(season.get("public_facts", []))
    for c in chars.values():
        for cf in c["memory"]["canon"][-2:]:
            bits.append(cf["fact"])
        if c["diary"]:
            bits.append(f"{c['identity']['name'].split()[0]}: {c['diary'][-1]['entry']}")
    if not bits:
        return ""
    sys = ("Fasse als 'Was bisher geschah' einer Soap in 2-3 spannenden deutschen "
           "Saetzen zusammen. Nur die Zusammenfassung.")
    try:
        return llm.chat(TEXT_MODEL, sys,
                        "BEKANNT:\n- " + "\n- ".join(bits[:12]) + "\n\nWas bisher geschah:",
                        temperature=0.6, num_predict=160).strip()
    except Exception:  # noqa: BLE001
        return ""


def write_stats(tpath: Path, chars: dict[str, dict], said: dict[str, list],
                season: dict, turn_count: int, scene_count: int) -> None:
    """Schreibt das stats_*.json-Sidecar im Schema des Persona-Panels (live)."""
    personas: dict[str, Any] = {}
    stresses: list[float] = []
    for c in chars.values():
        n = c["identity"]["name"]
        st = c["state"]
        lines = said.get(n, [])
        words = sum(len(l.split()) for l in lines)
        sus = c.get("suspicion_of_secrets", {})
        top = max(sus, key=sus.get) if sus else None
        rated = {
            "stress": {"value": round(st["stress"] * 10),
                       "evidence": f"Koffein {st['caffeine']}"},
            "verdacht": {"value": round((sus[top] if top else 0) * 10),
                         "evidence": f"verdaechtigt {top.split()[0]}" if top else "kein Signal"},
            "neugier": {"value": 0, "evidence": "kein Signal"},
            "snark": {"value": 0, "evidence": "kein Signal"},
            "sturheit": {"value": 0, "evidence": "kein Signal"},
            "logik_emotion": {"value": 0, "evidence": "kein Signal"},
            "stimmung": st.get("mood", ""),
        }
        personas[n] = {"spoke": bool(lines), "dominance": len(lines),
                       "verbosity": round(words / len(lines)) if lines else 0,
                       "rated": rated}
        if top and sus[top] >= 0.4:
            personas[n]["conflict"] = {"target": top, "intensity": round(sus[top] * 10),
                                       "evidence": "wachsender Verdacht"}
        if lines:
            stresses.append(st["stress"])
    secrets = []
    for o, e in season["secret_exposure"].items():
        if o not in chars:
            continue
        guard = chars[o]["state"].get("secret_guard", 1.0)
        exposure = 100 if e["revealed"] else round((1 - guard) * 100)
        secrets.append({
            "character": o, "label": "Geheimnis", "revealed": e["revealed"],
            "exposure": exposure,
            "evidence": ("AUFGEFLOGEN" if e["revealed"]
                         else f"Deckung {guard:.2f} · {e['near_misses']} Anstiche")})
    data = {
        "scored_at": turn_count, "turn_count": turn_count, "scene_count": scene_count,
        "personas": personas, "secrets": secrets,
        "plot": {"revealed": sum(1 for e in season["secret_exposure"].values() if e["revealed"]),
                 "total": len(season["secret_exposure"])},
        "drama_index": {"value": round(season["momentum"] * 10),
                        "avg_stress": round(sum(stresses) / len(stresses) * 10, 1) if stresses else 0,
                        "hostility_coverage": "-"},
    }
    sidecar = tpath.parent / ("stats_" + tpath.name[len("transkript_"):].replace(".md", ".json"))
    sidecar.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_day(season: dict, chars: dict[str, dict], max_turns: int = 18,
            mode: str = "work") -> Path:
    bar = mode == "bar"
    premise = BAR_PREMISE if bar else PREMISE
    showrunner_plan(season, chars, premise)
    names = [c["identity"]["name"] for c in chars.values()]
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    tpath = BASE / f"transkript_v2_d{season['day']}_{ts}.md"
    head = f"{season['weekday']}nacht 🍸" if bar else f"{season['weekday']} (Tag {season['day']})"
    lines = [f"# Augsburg 86150 — {head}\n"]

    recap = make_recap(season, chars) if season["day"] > 1 else ""
    if recap:
        lines.append(f"*Was bisher geschah:* {recap}\n")
        tpath.write_text("\n".join(lines), encoding="utf-8")

    public: list[str] = []
    said: dict[str, list[str]] = {n: [] for n in names}
    last_speaker = None
    forced_next = None     # emergente Reaktion: angestochene/angesprochene Figur kontert
    reveal_directive = ""  # gesetzt, wenn ein Geheimnis platzt -> naechster Erzaehler-Turn
    cur_scene = ""
    turns_in_scene = 0
    scene_n = 0
    MIN_TURNS_PER_SCENE = 6    # Szene laeuft mind. so lange (echtes Gespraech)
    MAX_TURNS_PER_SCENE = 13   # ... danach draengt der Erzaehler zum Schnitt

    def log(s: str) -> None:
        lines.append(s)
        tpath.write_text("\n".join(lines), encoding="utf-8")

    for turn in range(max_turns):
        if bar:
            clock = clock_str(turn, max_turns, 20 * 60, 25 * 60)
            phase = phase_for_bar(turn, max_turns)
            feierabend = turn >= int(max_turns * 0.82)
        else:
            clock = clock_str(turn, max_turns)
            phase = phase_for(clock)
            feierabend = phase.startswith("Feierabend")
        # ---- Stage-Manager / Erzaehler ----
        # ---- GODFATHER: Live-Eingriff aus dem Viewer (absolute Prioritaet) ----
        godfather = ""
        if GODFATHER_FILE.exists():
            note = GODFATHER_FILE.read_text(encoding="utf-8").strip()
            if note:
                godfather = note
                log(f"\n> 🎬 *[DER GODFATHER GREIFT EIN: {note}]*\n")
                GODFATHER_FILE.write_text("", encoding="utf-8")

        long_scene = turns_in_scene >= MAX_TURNS_PER_SCENE
        cut_hint = ("\nDIESE SZENE LAEUFT LANG GENUG - setze JETZT einen Schnitt "
                    "an einen NEUEN Ort/Zeitpunkt.\n" if long_scene else "")
        press = ("Die Woche ist vorbei - heute Nacht faellt, was unter dem Deckel war."
                 if bar else deadline_note(season))
        nctx = (f"PRAEMISSE: {premise}\nTAG: {season['weekday']}, {clock} Uhr ({phase}).\n"
                + (f"!!! ANWEISUNG VOM SENDERCHEF (ABSOLUTE PRIORITAET, setz das "
                   f"JETZT dramaturgisch um): {godfather} !!!\n" if godfather else "")
                + (f"!!! {reveal_directive} !!!\n" if reveal_directive else "")
                + f"{press}\n"
                + (f"WAS BISHER GESCHAH: {recap}\n" if recap else "")
                + f"HEUTIGER FOKUS: {season.get('day_focus', '-')}\n"
                f"FIGUREN: {', '.join(names)}\nMOMENTUM: {season['momentum']:.2f} "
                f"(niedrig = Szene stockt, setz einen Reiz).\n"
                f"Aktuelle Szene laeuft seit {turns_in_scene} Beitraegen.{cut_hint}\n"
                "BISHER:\n" + ("\n".join(public[-18:]) if public else "(leer)") +
                (f"\n\nEs ist {clock} Uhr, {'die Nacht neigt sich' if bar else 'Feierabend naht'} "
                 "- wenn genug passiert ist, the_end=true." if feierabend else "") +
                "\nGib Regie als JSON (scene leer lassen wenn Szene weiterlaeuft).")
        reveal_directive = ""   # feuert nur einmal
        nsys = ("Du bist der ERZAEHLER/Stage-Manager. Du sprichst nie Dialog. LASS "
                "GESPRAECHE ATMEN: eine Szene laeuft 6-12 Beitraege, nicht jede Replik "
                "eine neue Szene - 'scene' meist leer lassen (Szene laeuft weiter). "
                "Setze nur bei echtem Wechsel eine kurze neue Szene (max 2 Saetze, "
                "echter Augsburger Ort, bei Ortswechsel kurz begruenden). Inszeniere "
                "einen GANZ NORMALEN Arbeitstag: Ankunft & Begruessung am Morgen, "
                "Kaffee, Smalltalk, Mittagspause, normale Arbeit - das Drama schwelt "
                "darunter und bricht nur GELEGENTLICH durch (vor allem wenn der Druck "
                "steigt), nicht in jeder Szene. Waehle die naechste Figur (nie zweimal "
                "dieselbe hintereinander), gib ihr 1 Satz Regie - oft einfach Alltag, "
                "nur ab und zu Richtung Geheimnis/Konflikt.")
        try:
            r = llm.chat_json(NARRATOR_MODEL, nsys, nctx, NARRATOR_SCHEMA)
        except Exception as e:  # noqa: BLE001
            log(f"\n> [Erzaehler-Stoerung: {e}]"); break

        # Szenenschnitt nur, wenn die aktuelle Szene lang genug lief (sonst
        # setzt der Erzaehler jeden Turn eine neue Szene -> Thrash).
        if r.get("scene") and (not cur_scene or turns_in_scene >= MIN_TURNS_PER_SCENE):
            cur_scene = r["scene"]
            turns_in_scene = 0
            scene_n += 1
            log(f"\n---\n\n> *{clock} Uhr · {phase}* — {cur_scene}\n")
        if r.get("the_end") and turn > max_turns // 2:
            log(f"\n---\n\n**Feierabend.** *(Tag {season['day']}, {turn} Beitraege)*")
            break

        # Emergent: wenn jemand provoziert wurde, kontert er JETZT (ueberstimmt
        # die Erzaehlerwahl). Sonst waehlt der Erzaehler.
        if forced_next and forced_next in chars and forced_next != last_speaker:
            sp = forced_next
        else:
            sp = r.get("next_speaker")
            sp = next((n for n in names if sp and (sp.lower() in n.lower()
                       or n.split()[0].lower() in sp.lower())), None)
            if not sp or sp == last_speaker:
                sp = names[turn % len(names)]
                if sp == last_speaker:
                    sp = names[(turn + 1) % len(names)]
        forced_next = None
        char = chars[sp]

        # ---- Figur spricht ----
        tic = mechanics.detect_tic(said[sp])
        sysp = f"{char['identity']['core_prompt']}\n\n{char['identity']['secret']}\n\n{ACTOR_RULES}"
        usr = speaker_context(char, cur_scene, public, r.get("direction", ""), tic)
        rp = char["state"].get("repeat_penalty", 1.18)
        try:
            line = figure_say(char, sysp, usr, rp)
        except Exception as e:  # noqa: BLE001
            log(f"\n> [{sp} verpasst den Einsatz: {e}]"); continue
        # Cosmetic: fuehrende Sternchen / selbst vorangestellten Namen strippen
        line = re.sub(r"^[*\s]+", "", line)
        line = re.sub(rf"^{re.escape(sp.split()[0])}\s*[:\-]\s*", "", line, flags=re.I)
        line = line.strip().strip('"').strip()
        if not line:
            continue

        log(f"**{sp}:** {line}\n")
        public.append(f"{sp}: {line}")
        said[sp].append(line)
        last_speaker = sp
        turns_in_scene += 1

        # ---- Mechaniken ----
        if bar:
            mechanics.drink(char)
        else:
            mechanics.drain_caffeine(char)
        evs = mechanics.apply_line_effects(sp, line, chars, season)
        if evs:
            log(f"> _[{', '.join(evs)} · momentum {season['momentum']:.2f}]_\n")
        write_stats(tpath, chars, said, season, turn + 1, scene_n)  # Live-Panel

        # Emergente Reaktion bestimmen: angestochenes Geheimnis kontert zuerst,
        # sonst die namentlich angesprochene Figur.
        forced_next = None
        for ev in evs:
            if ev.startswith("near_miss:"):
                o = ev.split(":", 1)[1]
                if o in chars and o != sp:
                    forced_next = o
                    break
        if not forced_next:
            for other in names:
                if other != sp and re.search(
                        rf"\b{re.escape(other.split()[0])}\b", line):
                    forced_next = other
                    break

        # GEHEIMNIS PLATZT: Anstich bei kollabierter Deckung = die Enthuellung.
        for ev in evs:
            if not ev.startswith("near_miss:"):
                continue
            o = ev.split(":", 1)[1]
            exp = season["secret_exposure"].get(o, {})
            if (o in chars and not exp.get("revealed")
                    and chars[o]["state"]["secret_guard"] <= REVEAL_GUARD):
                exp["revealed"] = True
                fact = chars[o]["identity"].get("reveal_fact",
                                                f"{o}s Geheimnis ist aufgeflogen.")
                season.setdefault("public_facts", []).append(fact)
                chars[o]["state"]["secret_guard"] = 0.0
                for other in chars:
                    if other != o:
                        chars[other].setdefault("suspicion_of_secrets", {})[o] = 1.0
                season["momentum"] = 1.0
                reveal_directive = (
                    f"ENTHUELLUNG JETZT: {fact} Inszeniere die Konfrontation - "
                    f"{o.split()[0]} wird ertappt oder gesteht, alle reagieren darauf.")
                forced_next = o
                log(f"\n> 🔓 **GEHEIMNIS GEPLATZT:** {fact}\n")
                break

    # Episodentitel generieren + ablegen
    title = make_title("\n".join(lines))
    if title:
        lines.insert(1, f'### „{title}"\n')
        tpath.write_text("\n".join(lines), encoding="utf-8")
        tf = BASE / "titles.json"
        titles = json.loads(tf.read_text(encoding="utf-8")) if tf.exists() else {}
        titles[tpath.name] = title
        tf.write_text(json.dumps(titles, ensure_ascii=False, indent=2), encoding="utf-8")
    return tpath


def reflect(season: dict, chars: dict[str, dict], transcript: str) -> None:
    """Pro Figur: Zustand/Beziehungen/Tagebuch/canon zurueckschreiben."""
    day = season["day"]
    for c in chars.values():
        n = c["identity"]["name"]
        others = [x["identity"]["name"] for x in chars.values()
                  if x["identity"]["name"] != n]
        sys = ("Du bist die REFLEXION. Lies den Tag aus Sicht EINER Figur und "
               "aktualisiere ihren inneren Zustand ehrlich. Schreibe ein kurzes, "
               "privates Tagebuch (1-2 Saetze, Ich-Form). Nenne nur WIRKLICHE "
               "Landmark-Fakten als canon (z.B. ein aufgedecktes Geheimnis, ein "
               "Verrat - sonst leer). WICHTIG: Fuelle 'relationships' fuer JEDE "
               "andere Figur, mit der sie heute zu tun hatte - trust/suspicion/"
               "affection je 0.0-1.0, basierend auf dem heutigen Verlauf.")
        usr = (f"FIGUR: {n} ({c['identity']['role']}).\n"
               f"IHR GEHEIMNIS: {c['identity']['secret']}\n"
               f"ANDERE FIGUREN HEUTE: {', '.join(others)}\n"
               f"Aktueller Stress: {c['state']['stress']:.2f}, Stimmung {c['state']['mood']}.\n\n"
               f"DREHBUCH VON HEUTE:\n{transcript[:6000]}\n\n"
               "Gib die Aktualisierung als JSON (inkl. relationships zu den anderen).")
        try:
            out = llm.chat_json(REFLECT_MODEL, sys, usr, REFLECT_SCHEMA)
        except Exception:  # noqa: BLE001
            continue
        st = c["state"]
        st["stress"] = round(float(out.get("stress", st["stress"])), 3)
        st["mood"] = out.get("mood", st["mood"])
        st["confidence"] = round(float(out.get("confidence", st["confidence"])), 3)
        if out.get("diary"):
            S.add_diary(c, day, out["diary"])
        if out.get("today_summary"):
            S.add_episodic(c, day, out["today_summary"])
        for fact in out.get("canon", []) or []:
            S.add_canon(c, fact, day)
        for rel in out.get("relationships", []) or []:
            tgt = rel.get("name")
            if tgt and tgt != n:
                c["relationships"][tgt] = {
                    "trust": round(float(rel.get("trust", 0.5)), 2),
                    "suspicion": round(float(rel.get("suspicion", 0.3)), 2),
                    "affection": round(float(rel.get("affection", 0.3)), 2)}
        # taegliche Achsen zuruecksetzen, Identitaet/Memory bleiben
        st["caffeine"] = 100
        st["goal_today"] = None
        S.save_character(c)
    S.save_season(season)
