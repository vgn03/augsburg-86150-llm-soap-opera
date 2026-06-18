# Augsburg 86150 🎬

> A living, self-writing soap opera performed by local LLMs — no script, just
> characters with secrets they're desperate to hide.

**Augsburg 86150** is a multi-agent simulation. Local language models play the
staff of a small Augsburg IT company — *Gruber Systemhaus GmbH* — on an ordinary
Monday: the coffee machine is broken, the quarterly numbers loom, and every
single person has a corpse in the cellar. Nobody is given lines. The characters
just *talk* — driven by their personality, their secret, and their evolving
relationships. Over a month-long season they **remember**, suspicion compounds,
and — people being people — the secrets eventually **break**.

It runs entirely **offline on CPU** (built on a salvaged Dell PowerEdge R740 via
[Ollama](https://ollama.com)). The dialogue is German.

---

## The idea

Let LLMs talk to each other with no goal and no grounding, and they don't become
lifelike — they spiral. Each turn amplifies the last until "fix the server"
becomes a heist movie with slam poetry. The cure isn't *more* freedom, it's the
right constraints:

- **Information asymmetry** — every character guards a secret the others don't know.
- **A director** — a narrator keeps scenes coherent; a showrunner paces the arc.
- **Living state** — characters carry stress, suspicion, relationships and memory
  that persist and evolve, so autonomy produces *coherence* instead of chaos.

The result is drama instead of drift — and characters that feel like real
coworkers having a bad month.

---

## How it works

**Agents for everything.** Each character, the narrator/stage-manager, the
showrunner and the end-of-day reflection are all separate LLM calls.

- **The secret-engine** — everyone has a catastrophic secret and guards it with
  white knuckles. When the topic gets poked, their *cover* (`secret_guard`)
  erodes a little, listeners grow suspicious, and stress rises. Cover erodes
  *slowly* — a secret only **breaks** after sustained pressure, then detonates
  into public fallout that everyone remembers.
- **Living state & continuity** — a 3-tier memory (permanent identity · permanent
  canon facts · a rolling 2-week episodic window) plus a nightly **reflection**
  pass that updates each character's state, relationship matrix and private
  diary. Day *N+1* remembers day *N*.
- **Time** — *day = episode*, *week = Mon–Sat* (five workdays + a Saturday bar
  night where alcohol loosens tongues), *month ≈ one season* (24 episodes). The
  month-end crunch is the season finale; pressure ratchets week by week.
- **Emergent turn-taking** — poke someone's secret or call their name and they
  jump in next, overriding the director.
- **Tracked dimensions** — caffeine ☕ (the coffee machine is broken, so it only
  drains), a suspicion map, near-misses, story momentum, and live tic-detection.
- **Show-feel** — auto episode titles, a "Was bisher geschah" recap each morning,
  and a pompous Feuilleton critic that reviews finished episodes.

---

## The cast

| Figur | Rolle | Geheimnis (Kern) | Modell |
|---|---|---|---|
| **Herbert Gruber** | Chef, cholerisch | 80.000 € Firmengeld beim Online-Poker verzockt | gemma3:12b |
| **Gisela Wimmer** | Praktikantin | Hat Freitag die Kunden-Produktionsdatenbank gelöscht | mistral |
| **Carmen Gruber** | Buchhaltung, eiskalt | Heimlich einen Detektiv auf Herbert angesetzt | gemma3:12b |
| **Frau Schmidt** | Putzfrau | Weiß *alles* — sie belauscht nachts jeden | gemma3:12b |
| **Viktor Falk** | "IT-Auditor" | In Wahrheit Carmens Privatdetektiv | gemma3:12b |
| **Hausmeister Brunner** | Hausmeister | Cousin von Frau Schmidt, illegaler Zweitschlüssel | llama3.2 |

Casting is by *naturel*: reasoning models leak their chain-of-thought into
dialogue, so **characters run on clean instruct models** (gemma/llama/mistral),
while the **director, showrunner and reflection run on `qwen3:30b-a3b`** — there
the output is forced JSON, so reasoning is fine. Gisela on Mistral is deliberate:
she grew up in England and slips into Denglisch under stress — a tokenizer quirk
turned into a built-in lie-detector.

---

## The viewer

A dependency-free web dashboard (`viewer.py`, default `:8086`):

- **Live** — the conversation as it's written, with a persona panel (all stats in
  %) and a **Godfather console**: type a command and it lands on the next
  narrator turn ("Stromausfall im Viertel" → the lights go out).
- **Flip cards** — front = live stats (stress, suspicion, secret-exposure…),
  click to flip → back = the dossier (🔒 secret, relationship matrix, diary).
- **Characters** (`/characters`) — the full cross-day dossier.
- Episodes named *Woche 1 · Montag … Woche 4 · Samstagnacht 🍸* with auto titles.

---

## Setup

Requires [Ollama](https://ollama.com), Python 3.10+, and the `requests` package.

```bash
pip install requests
ollama pull qwen3:30b-a3b gemma3:12b mistral llama3.2
```

## Run

```bash
python3 run_season.py        # a full month (24 episodes) — long-running serial
# or:  run_week.py (Mon–Sat) · run_slice.py (2-day proof)

python3 scorer.py            # side-process: scores the subjective persona axes
python3 viewer.py --port 8086   # the dashboard
```

Then open `http://localhost:8086` and watch the month unfold.

---

## Files

| | |
|---|---|
| `engine.py` | the day orchestrator: narrator loop, figure agents, reflection, reveal mechanic |
| `mechanics.py` | deterministic state rules (secret-engine, caffeine, drinking, tic-detection) |
| `state.py` | the state + 3-tier memory spine |
| `llm.py` | thin Ollama binding (chat + structured JSON) |
| `viewer.py` | the web dashboard (stdlib only) |
| `scorer.py` | side-process that rates the subjective persona axes |
| `critic.py` | the Feuilleton critic |
| `run_season.py` / `run_week.py` / `run_slice.py` | runners (month / week / proof) |
| `characters/*.json` | the cast — identity (personality + secret) + living state |
| `docs/DESIGN_v2.md` | the full architecture / design doc |

---

*by vgn03 & Wlanium — getting multi-agent systems to behave, disguised as a comedy.*
