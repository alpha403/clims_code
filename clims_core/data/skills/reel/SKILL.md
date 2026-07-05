---
name: reel
description: When the user wants to create a short-form vertical video, reel, TikTok, Instagram Reel, or YouTube Short for any brand, product, niche, or topic -- run this skill
---

Produce a complete 1080x1920 short-form vertical reel (40-50s) for the following brief:

**Brief:** $ARGUMENTS

If the brief is missing key details, ask for them before proceeding:
- **Brand:** name, colors (hex), logo location (if any)
- **Topic / hook:** what is this reel about?
- **Presenter:** real person (photo path), AI-generated character, or voiceover only?
- **Voice:** clone from a reference file, or use a generic energetic voice?
- **Output destination:** where should the final mp4 be saved?

Once you have the brief, work through every stage below. All pipeline scripts live in `C:\Users\Alienware\Desktop\clims_code\bench\`. Derive a short lowercase slug `{rid}` from the topic (e.g. "Germany visa" -> `germany`, "fitness app launch" -> `fitnessapp`).

---

## STAGE 0 — RESEARCH & SCRIPT

Run 3-4 parallel web-research agents (WebSearch + WebFetch) on the topic. Gather:
- Key facts, stats, and surprising angles that stop the scroll
- The exact language the target audience uses about this topic
- What competing content in this niche looks like (hook patterns, pacing, CTAs)
- 2-3 potential hook angles — pick the strongest one

Write the script:
- 110-130 words (~40-46s at natural pace)
- First 3 words ARE the hook — no warm-up, no intro
- Punchy VJ beats: short sentences, not essay prose
- Ends with a Comment-X CTA (`Comment "{keyword}" below`)
- Flag any unverifiable stats with "verify before publishing"

Phoneme-correct ANY words the TTS will mispronounce (brand names, foreign words, unusual proper nouns) — write them as plain phonetic spelling before passing to TTS.

---

## STAGE 1 — VOICE

**Using Chatterbox TTS (cbvenv):**

Add the reel to `bench\reels.py` REELS dict:
```python
"{rid}": {
    "voice_text": [
        # Script split at sentence boundaries, each chunk ≤220 chars, phoneme-corrected
        "Chunk one.",
        "Chunk two.",
    ],
    "char_seed": <integer, unique per reel for visual variety>,
    "broll_prompts": ["<topic-relevant image prompt 1>", "<topic-relevant image prompt 2>"]
}
```

Generate voice:
```powershell
& "C:\Users\Alienware\Desktop\clims_code\cbvenv\Scripts\python.exe" `
    "C:\Users\Alienware\Desktop\clims_code\bench\gen_voice_batch.py" `
    {rid}
```

Outputs:
- `bench\voice_{rid}.wav` — raw
- `bench\voice_{rid}_slow.wav` — atempo=0.93 slowed (~7% longer, gives LTX-2.3 more frames per phoneme for lip-sync)

**Reference audio:** use `bench\energetic_ref10.wav` for a high-energy delivery, or swap in a brand-specific reference clip if provided. exaggeration=0.55, cfg_weight=0.45.

---

## STAGE 2 — WORD TIMINGS

Write `bench\reel_cfg.json`:
```json
{"id": "{rid}"}
```

```powershell
& "C:\Users\Alienware\Desktop\clims_code\cbvenv\Scripts\python.exe" `
    "C:\Users\Alienware\Desktop\clims_code\bench\timings_voice.py"
```

Writes `bench\voice_words_{rid}.json` — word-level timestamps used for subtitle sync and semantic b-roll placement.

---

## STAGE 3 — SUBTITLES

Add topic-specific highlight words to the `KEY` set in `make_subs.py` (brand name, product name, key numbers, power words that should pulse in the highlight style), then:

```powershell
$env:PYTHONUTF8 = "1"
& "C:\Users\Alienware\Desktop\clims_code\cbvenv\Scripts\python.exe" `
    "C:\Users\Alienware\Desktop\clims_code\bench\make_subs.py"
```

Writes `bench\subs_{rid}.ass`.

Post-scan every Dialogue line in the .ass file for Whisper mis-hearings of phonetic names — fix them before assembly.

---

## STAGE 4 — CUT PLAN

Read `bench\voice_words_{rid}.json` to find sentence boundaries and semantic visual moments. Author `bench\cut_plan_{rid}.json`:

**Rules:**
- Exactly 4 TH segments + 3 BR segments, strictly alternating: TH BR TH BR TH BR TH
- Each TH segment ≤9s (LTX-2.3 hi-res hard ceiling at 1024x1792)
- BR cuts fall at sentence/word gaps in the audio — never mid-word
- BR placement is SEMANTIC: insert where the script references something visual (a stat, a place, a product, a concept)
- BR `"info"` must match a key in the `SCENES` dict in `bench\infographics.py`
- `"total"` = exact duration of `voice_{rid}_slow.wav`

```json
{
  "voice": "voice_{rid}_slow.wav",
  "total": <float seconds>,
  "items": [
    {"type": "TH", "i": 0, "start": 0.00,      "end": <≤9.0>},
    {"type": "BR", "i": 0, "start": <end_th0>, "end": <end_br0>, "info": "<scene_key>"},
    {"type": "TH", "i": 1, "start": <end_br0>, "end": <≤9s later>},
    {"type": "BR", "i": 1, "start": <end_th1>, "end": <end_br1>, "info": "<scene_key>"},
    {"type": "TH", "i": 2, "start": <end_br1>, "end": <≤9s later>},
    {"type": "BR", "i": 2, "start": <end_th2>, "end": <end_br2>, "info": "<scene_key>"},
    {"type": "TH", "i": 3, "start": <end_br2>, "end": <total>}
  ]
}
```

Decide the 3 BR scene keys now — you will create or reuse them in Stage 7.

---

## STAGE 5 — PRESENTER / SEED IMAGE

Options depending on the brief:

**A — Real person (photo provided):** use the photo directly as the LTX-2.3 seed. SCP to Bunny ComfyUI input.

**B — AI-generated character:** generate via nano-banana (Gemini `gemini-2.5-flash-image`, multi-image: identity ref + environment ref) or ComfyUI charconst (PuLID + Flux2-Klein on Bunny). Use a different seed integer per reel for visual variety while keeping identity consistent.

**C — Voiceover only (no talking head):** skip Stages 5 and 6. Replace all TH items with additional BR infographic scenes. Adjust cut plan accordingly.

SCP the seed to Bunny:
```bash
scp -i C:/Users/Alienware/.ssh/bunny_omnisvg <seed.png> \
    Bunny@100.84.108.103:"C:/Users/Bunny/Desktop/ComfyUI_windows_portable/ComfyUI/input/"
```

---

## STAGE 6 — TALKING HEAD RENDER (Bunny RTX 5090)

```powershell
$env:VOICE    = "voice_{rid}_slow.wav"
$env:SEED     = "<seed_filename>.png"
$env:IDIMG    = "<identity_reference>.png"
$env:PFX      = "th{rid}"
$env:THFILES  = "th_files_{rid}.json"
$env:CUT_PLAN = "cut_plan_{rid}.json"

& "C:\Users\Alienware\Desktop\clims_code\cbvenv\Scripts\python.exe" `
    "C:\Users\Alienware\Desktop\clims_code\bench\th_render_plan.py"
```

Submits each TH segment to ComfyUI (LTX-2.3 i2v 1024x1792, 10S likeness nodes: LTXLikenessGuide 0.9 + LTXLatentAnchorAware + LTXLikenessAnchor), polls until done, downloads results as `bench\th{rid}_seg{i}_raw.mp4`, writes `bench\th_files_{rid}.json`.

**CUDA wedge (GPU stuck at 0% / ~2-3GB after submit):** SSH to Bunny, `taskkill /F /PID <comfyui python pid>`, relaunch `C:\Users\Bunny\start_comfy_direct.bat` in a held-open SSH session, resubmit.

Once Stage 6 is running on the GPU, proceed to Stage 7 in parallel.

---

## STAGE 7 — INFOGRAPHICS (run in parallel with Stage 6)

For each of the 3 BR items, render an animated motion-graphic scene using the PIL engine (`bench\infographics.py`).

**If a matching scene already exists** in `SCENES` dict, render it:
```powershell
$env:PYTHONUTF8 = "1"
cd "C:\Users\Alienware\Desktop\clims_code\bench"
python infographics.py <scene_key> <duration_seconds>
```

**If the brand or topic needs new scenes**, add them to `bench\infographics.py`:

1. Define brand palette at the top of the new function (or pass as parameters):
   ```python
   # Use the brand's actual colors from the brief
   PRIMARY = (<r>, <g>, <b>)    # brand primary
   ACCENT  = (<r>, <g>, <b>)    # brand accent / CTA color
   ```

2. Write the scene function:
   ```python
   def {rid}_{type}(t: float, dur: float):
       img = bg(t)  # or a custom background using the brand palette
       d = ImageDraw.Draw(img)
       header(img, t)  # brand chrome top bar
       footer(img, t)  # brand chrome bottom bar
       # ... animated content using ease_out/ease_io/seg helpers
       return img
   ```

3. Register: `SCENES["{rid}_{type}"] = {rid}_{type}`

4. Render: `python infographics.py {rid}_{type} <duration>`

**Scene content — match to what's being said:**
- Stat/number moment → big number slam-in with animated counter + label cards
- List/checklist moment → animated `check_circle()` reveals
- Comparison/contrast → ✓ vs ✗ panel using `check_circle()` + `big_x()`
- CTA/urgency moment → full-bleed bold text slam with brand footer

Each scene carries REAL content from the script. No empty bullets, no dead space, no tiny text (minimum 48px on a 1080px canvas).

---

## STAGE 8 — ASSEMBLE

Wait for Stage 6 to complete, then:

```powershell
$env:VOICE    = "voice_{rid}_slow.wav"
$env:SUBS     = "subs_{rid}.ass"
$env:OUT      = "<BrandName>_{Topic}_Reel.mp4"
$env:CTA      = 'Comment "{keyword}" below'
$env:CUT_PLAN = "cut_plan_{rid}.json"
$env:THFILES  = "th_files_{rid}.json"

cd "C:\Users\Alienware\Desktop\clims_code\bench"
python assemble_aroll_broll.py
```

Color-matches all TH segments to TH0, concatenates frame-exact, filters captions to TH-only spans, overlays continuous voice, burns subtitles, appends end-card. Final mp4 saved to the output destination from the brief.

**End-card:** the assembler generates a PIL end-card. Update the brand colors in `assemble_aroll_broll.py` end-card section if this is not the default brand (search for the navy/gold hex values and replace with the brief's palette).

---

## DESIGN SELF-CHECK (before reporting done)

- [ ] No dead space or empty frames anywhere
- [ ] No text below 48px on the 1080px canvas (readable on a phone)
- [ ] Brand colors consistent throughout — matches the brief exactly
- [ ] Captions appear only on TH segments, not over infographics
- [ ] B-roll placement is semantic (tied to the words being spoken), not filler
- [ ] Audio duration matches video duration exactly (ffprobe verify)
- [ ] End-card CTA keyword is correct
- [ ] No Whisper mis-hearings left in captions
- [ ] Hook lands in the first 3 seconds — compelling enough to stop the scroll
