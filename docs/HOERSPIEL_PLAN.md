# Hörspiel-Plan: Augsburg 86150 → Audio

> Konzept, aus einem fertigen Transkript ein gesprochenes Hörspiel zu machen.
> Stand: 13.06.2026, ausgearbeitet während der Finetuning-Schicht.
> Wlanium = ON → self-hosted, läuft auf dem R740, keine Cloud-TTS.

## 1. Ziel

Eine "gute" Episode (eine, in der die Drama-Mechanik trägt — mind. ein
Geheimnis kippt) wird zur Audio-Datei: jede Figur mit eigener Stimme, der
Erzähler sagt die Szenen an, dazwischen Pausen/Atmo. Ergebnis: eine MP3,
die man sich wie ein echtes Radio-Hörspiel anhören kann.

## 2. Warum das gut zur Soap passt

Das Transkript ist schon perfekt vorstrukturiert:
- `## Szene N` + Blockquote = Erzähler-Ansage
- `**Figur:** Text` = eine Audio-Zeile mit klar zugeordneter Stimme
Das Parsing ist trivial (dasselbe Format, das der Viewer schon rendert).

## 3. TTS-Engine: Piper (Empfehlung)

**Wahl: [Piper](https://github.com/rhasspy/piper)** — neuronales TTS, läuft
schnell auf CPU (kein GPU nötig — wichtig auf dieser Kiste), komplett lokal,
gute deutsche Stimmen frei verfügbar (Thorsten-Voice u.a.).

Warum nicht die Alternativen:
- **Coqui XTTS v2**: Voice-Cloning, top Qualität, aber GPU-hungrig und ~10x
  langsamer auf CPU. Overkill für Take 1. Kandidat für ein späteres
  "Premium-Remaster", wenn eine Folge richtig gut ist.
- **espeak-ng**: roboterhaft, nur als Fallback.
- **Cloud (ElevenLabs etc.)**: scheidet aus (Wlanium=ON, self-hosted).

Caveat Dialekt: Piper-Stimmen sind Hochdeutsch. Herberts Bairisch wird
**vorgelesen wie geschrieben** — der Dialekt steckt im Text, die Stimme
gibt nur Klangfarbe/Tempo. Klingt erfahrungsgemäß trotzdem charmant
("vorgelesener Dialekt"). Echtes bairisches TTS gibt es nicht frei.

## 4. Stimmen-Casting (Piper-Stimmen → Figur)

Idee: Stimmlage/Tempo passend zum Charakter wählen. Konkrete Modell-Zuordnung
beim Bau, hier die Richtung:

| Figur | Stimm-Charakter | Piper-Kandidat |
|---|---|---|
| Erzähler | ruhig, neutral, erzählend | `de_DE-thorsten-high` |
| Herbert | laut, polternd, älter-männlich | `de_DE-thorsten-medium` (höheres Tempo) |
| Gisela | jung, hektisch, weiblich | `de_DE-eva_k-x_low` o.ä. |
| Carmen | kühl, langsam, kontrolliert | `de_DE-kerstin-low` (Tempo runter) |
| Frau Schmidt | älter, raunend | `de_DE-ramona-low` |
| Viktor | trocken, männlich | andere male voice zur Abgrenzung von Herbert |
| Brunner | wortkarg, brummig | tieferes male-Modell |

Stimm-Variation auch über `--length-scale` (Sprechtempo) und ggf.
leichte Tonhöhen-Verschiebung per `sox`/`ffmpeg`, damit nicht zwei Männer
gleich klingen.

## 5. Pipeline (geplante Schritte)

```
transkript_*.md
   │  1. Parser (Python): zerlegt in geordnete Segmente
   │     [{typ: szene|dialog, sprecher, text}], Godfather-Marker raus
   ▼
   │  2. Pro Segment: Piper-Aufruf mit der Figur-Stimme → WAV-Schnipsel
   │     (Erzähler liest Szenenbeschreibung, dann die Dialoge)
   ▼
   │  3. Montage (ffmpeg/sox): Schnipsel aneinander, kurze Pausen zwischen
   │     Repliken, längere zwischen Szenen, optional Atmo-Bett/Jingle am
   │     Szenenschnitt
   ▼
   │  4. Intro/Outro: Titel-Jingle + "Augsburg 86150, eine Soap aus dem
   │     Gruber Systemhaus" gesprochen, Outro mit Cast-Nennung
   ▼
hoerspiel_<ts>.mp3  (+ Kapitelmarken pro Szene)
```

Skript-Arbeitstitel: `hoerspiel.py transkript_<ts>.md` → MP3.
Einzige neue Abhängigkeiten: `piper-tts` (+ Stimm-Modelle), `ffmpeg`.

## 6. Ausbaustufen

- **MVP**: reine Stimmen, Pausen, keine Musik. Beweist die Pipeline.
- **V2**: Intro/Outro-Jingle, Szenen-Atmo (Büro-Tippen, Stadion-Hall,
  Regen am Rathausplatz — passend zum jeweiligen Schauplatz!).
- **V3 "Premium"**: beste Folge mit Coqui XTTS neu vertonen, evtl. echte
  Sprecher-Samples klonen.
- **Live-Variante**: TTS direkt an den Orchestrator hängen → die Soap
  spricht beim Drehen. (Reizvoll, aber Audio-Latenz pro Turn beachten.)

## 7. Entscheidungen für Tom (wenn du aus Kassel zurück bist)

1. **Welche Folge?** Erst eine wirklich gute Episode abwarten (Geheimnis
   kippt sauber), oder schon mit der jetzigen Staffel 1 die Pipeline bauen?
2. **Dialekt-Strategie**: Herbert hochdeutsch vorgelesen lassen (schnell)
   oder experimentieren (Tempo/Pitch-Tricks für mehr "Charakter")?
3. **Umfang MVP vs. V2** für den ersten Wurf.

→ Sobald du grünes Licht gibst, baue ich die `hoerspiel.py`-Pipeline. Piper
+ ffmpeg sind in Minuten installiert, der Parser ist überschaubar.
