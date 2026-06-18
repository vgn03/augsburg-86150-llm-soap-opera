# Augsburg 86150 — Design v2: The Living Serial

> Master plan for evolving the soap from anthology (resets every run) into a
> serial with continuity, character development, and a weekly arc.
> Status: PLAN ONLY — no code yet. Built from the Tom+Claude design sessions.

---

## 1. The vision

Today it's **Groundhog Day**: every run is the same Monday, secrets buried
again, zero memory. Target: a **living serial** where characters remember,
relationships evolve, secrets stay revealed once they're out, and the cast
*develops like real people* across a week.

---

## 2. Time structure (Tom's idea)

- **A day = one episode.** No more abstract "Szene 1..30" counter.
- **Mon–Fri = workdays**: the day runs from morning arrival → through the
  workday (coffee break, lunch at the Döner am Königsplatz, afternoon) →
  evening, everyone goes home. The day **ends when work ends** — a natural
  climax, not a budget cutoff. (Fixes the "frayed finale" problem: episodes
  used to end when the scene-counter ran out, mid-sentence.)
- **Saturday = off-duty** (Tom's idea): bars/clubs, drinking. The week's
  pressure detonates socially once the professional filter is gone.
- **The week = one season.** Friday's quarterly-numbers deadline = the
  professional climax; Saturday = the social/personal climax. Optional
  **Sunday** hangover coda.
- Within a day: the narrator advances a **clock** (≈08:00→18:00). Beats are
  time-stamped moments ("11:15 — Büroküche"), not numbered scenes.

The week arc is **already written into the secrets**: Herbert's poker
reckoning is "before Friday's numbers", Gisela's deleted DB "before her
evaluation Wed/Thu", Frau Schmidt cleans "at night". The deadline structure
exists — we just frame the calendar around it.

---



> **Update (Tom): STAFFEL = MONAT.** Day=Episode, Woche=Mo-Sa (Arbeit+Bar), **~4 Wochen = ein Monat = eine Staffel** (24 Episoden). Der Quartals-/Monats-abschluss am Monatsende ist das STAFFELFINALE; weekly Freitag ist nur Ende der Arbeitswoche. Runner: run_season.py. Druck waechst ueber den Monat.

## 3. The character model — the SPINE

Each character = **static core** + **living state** (the new part).

**Static core** (as today, in the JSON): personality, voice, and the SECRET.

**Living state** (new, persists & evolves):
- **Emotional axes**: stress, mood, and on Saturday `drunkenness`.
- **Secret-guard**: how much of their secret has already slipped / how close
  others are. (See §4.1 — this mechanic EXISTS.)
- **Goal of the day**: assigned fresh each morning (see §4.2).
- **Relationships**: an NxN matrix — trust / suspicion / affection toward
  each other character (see §4.3).
- **Memory**: accumulated canon (what happened, what's now public) + a
  private **diary** (see §5).

The secret is the *permanent hidden drive*; the daily goal is the *surface
objective*. They're often in tension — today's goal may risk exposing the
secret. That tension is the engine.

---

## 4. Mechanics

### 4.1 The secret-leak engine — EXISTS, keep & feed it
Everyone guards their secret but **slips a little under pressure**, which
makes the others curious. This is already implemented and is the core drama
motor. The new state system *feeds* it: higher stress / drunkenness → higher
slip probability. We don't rebuild this — we wire the new axes into it.

### 4.2 Daily goals (director-assigned, different every day)
- The **director/showrunner assigns each character a goal each morning**,
  varying day to day, always consistent with their secret.
  (e.g. Gisela Mon: "stop anyone opening the production DB"; Carmen Tue:
  "get Viktor alone and learn what he's found".)
- Goals drive **emergent turn-taking**: a character speaks when their goal is
  *threatened* — no director needed to pick the next speaker.
- Goals are **evaluated at day's end** by the reflection pass → success/failure
  feeds character development (confidence vs. desperation).

### 4.3 Relationship matrix
- NxN: how each character feels about each other (trust / suspicion /
  affection). Updates daily via reflection.
- Drives who-engages-whom and suspicion escalation across the week
  (Carmen→Gisela suspicion climbing all week → detonates Saturday).
- **Integrate into the existing viewer persona-boxes** (Tom built the panel —
  extend it with the matrix, don't build a new UI).

### 4.4 Drunkenness (Saturday) — Tom's idea
- A state axis that rises per drink and **lowers the secret-guard**.
- Per-character tolerance AND choice: Carmen stays sober and *hunts*; Gisela
  drunk → her stress-Denglisch goes full English (same dial we already
  built); Herbert → maudlin, nearly confesses the 80k; Viktor fakes drinking,
  stays sharp.
- **Authored as specific behaviors** (oversharing, repeating, sentimental),
  NOT "act drunk" — small models turn that into word-salad. Drunk ≠
  incoherent. Bigger models play it properly.

### 4.5 Emergent turn-taking
- Replace "director picks next_speaker" with **desire-to-speak**: after each
  line, characters who are provoked / whose goal is threatened want the floor;
  the most pressured speaks. Directly-addressed characters auto-respond.
- The director shrinks to a stage-manager + showrunner (§4.6).

### 4.6 Director, split into two jobs
- **Stage manager** (per-turn, light): clock, location, who's present,
  scene cuts. Keeps coherence — the guardrail that stops the Test-1 drift.
- **Showrunner** (per-day, big model): plans the next day's big beat
  (authored escalation), assigns goals, can drop a **second secret** mid-week
  to re-energize a sagging middle.

### 4.7 Reflection pass (end of each day)
A big model reads each character's day and:
- updates their living state (stress carryover, etc.)
- updates the relationship matrix
- writes their **diary** entry
- evaluates their **goal** (achieved?) → development
- updates **season canon** (what's now public knowledge)
This is the bridge between episodes — it makes Day 2's Carmen remember Day 1.

---

## 4a. Tracked dimensions (COMMITTED — Tom picked these 5)

1. **Caffeine** ☕ (per-character, 0–100). The coffee machine is broken, so it
   only **drains** through the workday — no refills. Lower caffeine → higher
   irritability (shorter, snippier lines; lowers patience in the relationship
   axis). Resets overnight. Sibling of Saturday's `drunkenness` (one drains,
   the other rises). Grounded in the premise; gives the day a built-in mood
   curve. → state axis defined Phase 1, effects wired Phase 5 (day-frame).

2. **Suspicion map** (load-bearing). Per **(observer → secret)**: how strongly
   each character suspects each hidden secret (0–1). Rises when the secret-owner
   slips or the topic gets near. Drives investigation (high suspicion → that
   observer probes the owner) and feeds the showrunner (broad high suspicion →
   secret is ripe to break). The secret-engine made visible. → Phase 4.

3. **Secret near-misses** (per secret, counter). Increments each time a secret
   *almost* surfaces then gets deflected. A reveal-pressure gauge: showrunner
   threshold (e.g. ≥3) can force the reveal so secrets don't circle forever
   (our recurring failure). → Phase 4.

4. **Story momentum** (global, load-bearing). Is the plot advancing or spinning?
   Rises on plot events (slip, new suspicion, alliance shift, reveal); flags when
   N turns pass with no event. Low momentum → showrunner/stage-manager injects a
   beat or hard scene cut. The **automated fix for the "Geplänkel" stall** we
   fought by hand all week. → Phase 4.

5. **Tic / repetition auto-detection** (per-character, quality control). Live
   monitor of repeated sentence-openers / n-grams across a character's recent
   lines; flags when a pattern exceeds threshold. On flag: inject an anti-tic
   nudge into that character's next prompt AND surface it in the Characters tab.
   The **automated Carmen-"Wie"-counter** — replaces our manual counting.
   → Phase 2 (pulled early; it's our debug/quality instrument).

Synergy: #2+#3+#4 all feed the **showrunner's** reveal/anti-stall logic; #1 and
drunkenness are siblings on the state axis; #5 ships early as a dev tool.

## 5. Show-feel layer
- **Diaries**: each character writes a private 1–2 sentence POV entry per day.
  Double duty: memory seed + readable content (a viewer panel).
- **Episode titles**: auto-generated, evocative ("Montag: Der kalte Kaffee")
  instead of timestamps.
- **"Was bisher geschah" recap**: auto-generated at episode start — both the
  memory-injection mechanism AND content.
- **Feuilleton critic** (from the original project doc): a big model reviews
  each episode. Comedy + a free quality-signal.
- **Hörspiel / TTS**: existing plan (HOERSPIEL_PLAN.md, Piper).

---

## 5a. Viewer structure (Tom) — modes of watching
Split the viewer into views by what you're doing, not flat pages:
- **Live** — the conversation, full focus, + a SLIM live-meter strip
  (stress / drama-meter / goal-of-the-day) so real-time movement stays visible.
- **Characters (dossier)** — full per-character cards + relationship matrix +
  diaries (private POV). Read between episodes. NOTE: build a basic version
  EARLY (Phase 1) — it's the window onto characters/<name>.json and doubles as
  the debug tool to verify continuity in the Phase 2 slice (watch the matrix &
  diaries change Day1→Day2). Prettify in polish.
- **Season (later)** — week arc, canon/public facts, episode titles, recaps,
  Feuilleton critic. Showrunner view.

## 6. Model strategy
**Tiered.** 30b for load-bearing roles — Carmen (the hunter), the showrunner,
the reflection/diary pass — small models for bit players. The R740's
two-socket NUMA headroom (see BENCH.md) is what makes running the big ones
affordable. Spend compute where the drama lives.

---

## 7. Data shape (concrete, not code yet)
- `season_state.json` — day counter, canon facts, what's public, the week's
  planned beats.
- `characters/<name>.json` — static core + living state + relationship row +
  diary log.
- per-day transcript (`transkript_*.md`, as today).
- The viewer reads these to render persona boxes + relationships + diaries.

---

## 8. What already exists (KEEP — don't rebuild)
- The orchestrator engine (narrator-loop, JSON regie, context-isolation,
  round-robin fallback, godfather override).
- The **secret-leak / slip mechanic** (§4.1).
- The viewer + persona panel (stress/mood/suspicion/drama meter) — EXTEND it.
- The recast cast (Herbert 12b, Gisela Mistral+Denglisch, Carmen qwen3:14b
  @ repeat_penalty 1.4, …).
- NUMA two-socket knowledge for the model tiering.

---

## 9. Build sequence (incremental — prove each layer before the next)
- **Phase 0** — this plan. ✅
- **Phase 1** — *State + memory spine*: a per-character state file that
  survives a run. Nothing else works without it.
- **Phase 2** — *2-day / 3-character slice* (Herbert, Gisela, Carmen — the
  core triangle): Day 1 → reflection → Day 2 *remembers* Day 1. **PROVE THE
  LOOP HERE** before scaling.
- **Phase 3** — *Goals + emergent turn-taking*.
- **Phase 4** — *Relationship matrix + viewer integration + showrunner*.
- **Phase 5** — *Full week* (Mon–Fri day-frame, clock, all 6 characters).
- **Phase 6** — *Saturday + drunkenness*.
- **Phase 7** — *Polish*: diaries, titles, recap, critic, TTS.

**Rule:** the 2-day/3-character slice (Phase 2) is the proof of concept. If
continuity + goals + state make those three feel alive across two days, we
scale with confidence. If we build the whole week-and-bar cathedral first and
it drifts, we won't know which layer broke.

---

## 10. Decisions

### DECIDED
1. **Persistence (Tom):** stress + relationships + diaries persist from day one.
   Memory in **three tiers**:
   - *Identity* — name/personality/secret — permanent, in every prompt
     ("each person knows his identity constantly").
   - *Canon* — landmark facts (revealed secrets, betrayals) — permanent,
     distilled out of episodes, never fade.
   - *Episodic detail* — rolling **2-week window** (~12 days); older days
     compress (landmark facts promote to canon, rest fades).
2. **Models (Tom): 30b on every character — YES.** All roles run the SAME
   `qwen3:30b-a3b` → Ollama loads it ONCE (~19 GB), serves all via prompt+state.
   RAM is a non-issue (~30 GB of 183). Cost is per-turn speed, acceptable for a
   background serial. Personality comes from STATE, not model-hunting.
   (Different big model per character = the only thing RAM can't do; not wanted.)

### DECIDED (cont.)
3. **Casting — REVISED by Phase-2 empirical finding (14.→18.06.):**
   The A/B answered itself immediately. `qwen3:30b-a3b` is a **reasoning model**
   and **leaks chain-of-thought into dialogue** ("His reaction should be...")
   no matter the prompt — unusable for FIGURES who must output only a spoken
   line. No instruct model (gemma/llama/mistral) does this.
   → **Figures run CLEAN INSTRUCT models, not the reasoning 30b.**
     - Herbert, Carmen: `gemma3:12b` (clean, in-character, proven).
     - Gisela: `mistral` (the Denglisch keeper).
   → **`qwen3:30b-a3b` stays for narrator / showrunner / reflection** — there
     reasoning is fine because we force structured JSON and extract it.
   Lesson: "bigger = better" is false for the figure role; reasoning models are
   the wrong tool when you need a bare utterance. (Premium clean upgrade later:
   gemma3:27b for figures.)

### STILL OPEN (don't block Phase 1)
4. **Sunday**: hangover coda, or skip (Sat = season finale)?
5. **Godfather override** stays in the new model? (Assumed yes.)
6. **Reset switch**: keep ability to start a fresh season (wipe state)?
