# Assessment A (design review) — app.html

Design-specificity: content authored, chrome interchangeable. Authored: per-family glyphs, Peloton-only spec rows (Rotate + tilt, Slat belt, Form Assist), fit-finder questions mapping to real purchase anxieties, "No hardware" handling, Peloton red accent. Interchangeable: wordmark is tracked Inter + red dot, 7 series colours are arbitrary dataviz hues, skeleton (chips → cards → table → charts → multiples → quiz) is a generic BI comparison template; Momentum/Members are analyst panels. Peloton's visual world (photography, black/white contrast, motion) absent.

Heuristics (26/40): 1 Status 3 (no aria-live; 5th chip / last deselect silent) · 2 Real world 3 ("Launched BEST"; 68% on every regional row) · 3 Control 2 (no reset/undo/URL state) · 4 Consistency 3 (regions mouse-only; two "best" vocabularies) · 5 Error prevention 3 (budget min 0) · 6 Recognition 3 (colour→product memory) · 7 Flexibility 2 · 8 Minimal 3 (12 ungrouped rows, BEST on ties) · 9 Recovery 2 (empty states no next step; errors only in title tooltip) · 10 Help 2 (scores unexplained).

Cognitive load failed: minimal choices (7 chips, 5 goals), chunking (12 rows, 5 panels), progressive disclosure, working memory, single focus (analytics vs shopper quiz).

Emotional journey: peak = instant recolour on chip tap; valley = Momentum→Members trough with flat 68% bars; end = compare-top scrolls up, loses the "why".

Strengths: direct-labelled trend lines + "Leader" sublines; fit-finder "why" strings; graceful data fallback + pill.

Priority issues:
- P0 contrast/tie semantics: td.best::after 10px red; .tag.win ~3.9:1; --text-3 ~3.3:1 on th, .kv, .hint.
- P1 chart scaling at 768px (regions svg scales to 70px rows); cards wrap 3+1.
- P1 ending drops the user: no sticky recap after compare-top jump.
- P2 silent limits at 4 chips / last deselect.
- P2 sample regional mix identical per product.

Personas: Alex (no shortcuts, no shareable state, region filter not applied to "Where it sells"); Sam (no fieldset/legend for option groups, no table equivalent for charts, tooltip mouse-only, no aria-live, no :focus-visible on .chip/.opt, rank colour-alone); Casey (.opt 35.5px, .seg 31.5px, checkbox 19.5px; regions no touch; range hard one-handed; no persistence).

Minor: sections lack aria-labelledby; wordmark dot reads as badge; "Cardio hardware" jargon; units style inconsistent; dark --text-3 ≈4.1:1.

Questions: would a shopper miss Momentum/Members? why is Cycling pre-answered? what if product photos were the selector?
