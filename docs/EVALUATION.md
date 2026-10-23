# Evaluation

## Dataset

[backend/evaluation/labels.json](../backend/evaluation/labels.json) holds manually labelled gold annotations for 10 transcripts, each from a different domain: product launch, student capstone, incident review, fundraising gala, sprint planning, outpatient clinic, sales pipeline, research lab, construction site and school council. The transcripts use 6 different formats: bracketed timestamps, `Name (mm:ss):`, Otter-style headers, uppercase labels, WebVTT and plain `Name:` lines. In total there are **125 gold items**: 53 action items (each with an owner and a deadline label), 26 decisions (with status), 32 risks and blockers (with kind) and 14 open questions. The annotation guidelines are stored in the same file.

Each gold item lists one or more distinctive evidence substrings. A predicted item matches a gold item if any of its evidence sentences contains one of them (greedy one-to-one matching). Precision = matched predictions / predictions; recall = matched gold / gold.

**Baseline:** one item per sentence containing a cue word ("will", "need to", "decided", "risk", "?" …), with the speaker as owner.

## Protocol and honesty notes

| Split | How it was used |
|---|---|
| **dev** (3 transcripts) | Used throughout development to find and fix errors. |
| **test** (4) | Written and labelled before its first run. That first run is frozen in [RESULTS_heldout_v1.md](../backend/evaluation/RESULTS_heldout_v1.md). Error analysis on it then led to general fixes (e.g. `Action:` labels, "who's picking up…", hedged answers, the "even if" concession, a broader problem lexicon, a filler-question bug that dropped real questions), so its later scores are **post-hoc** and over-optimistic. |
| **holdout-2** (3) | Written and labelled after all changes, then evaluated once with no further tuning. This is the most honest estimate. |

All labels were written by one annotator (the project author), with no inter-annotator agreement measured. The splits are small, so differences of ±0.1 F1 are within noise.

## Results

Run `cd backend && python -m evaluation.evaluate`; the full tables are written to [RESULTS.md](../backend/evaluation/RESULTS.md).

### Micro-averaged F1 over all four categories

| Split | System P | System R | System F1 | Baseline F1 |
|---|---|---|---|---|
| dev | 0.81 | 0.96 | 0.88 | 0.65 |
| test, frozen first run | 0.77 | 0.58 | **0.66** | 0.61 |
| test, post-hoc | 0.92 | 1.00 | 0.96 | 0.61 |
| **holdout-2** | 0.86 | 0.69 | **0.76** | 0.53 |

### Holdout-2 per category

| Category | P | R | F1 | Baseline F1 |
|---|---|---|---|---|
| Action items | 0.80 | 0.92 | 0.86 | 0.61 |
| Decisions | 1.00 | 0.50 | 0.67 | 0.50 |
| Risks & blockers | 0.80 | 0.40 | 0.53 | 0.33 |
| Unresolved questions | 1.00 | 1.00 | 1.00 | 0.50 |

| Attribute (matched items) | System | Baseline |
|---|---|---|
| Owner accuracy | 1.00 (12/12) | 0.58 |
| Deadline (normalised date) accuracy | 1.00 (12/12) | 0.42 |
| Decision status accuracy | 1.00 (4/4) | 0.67 |
| Risk vs blocker accuracy | 0.75 (3/4) | 0.50 |

## Interpretation

- **Action items generalise well,** and owners and deadlines are reliable once an item is found. The reply-based owner inference and the date rules are the strongest parts of the system.
- **Precision is higher than recall** in every split. When MeetingMind is unsure it tends to stay silent rather than invent, which suits a tool whose output people act on.
- **Decisions and risks** depend on cue lexicons. The holdout-2 misses were phrasings such as "We're keeping the tower crane until the roof is done", "the fair stays in the gym", "Heavy rain Thursday afternoon" and "two workers were seen without harnesses": implicit decisions and risks with no decision or problem vocabulary. A trained classifier on a larger corpus would be the next step (see the README's future enhancements).
- The gap between the frozen test run (0.66) and the post-hoc rerun (0.96) shows how easily a rule-based system overfits the examples it is tuned on, which is why holdout-2 was added.

## Summary quality

Abstractive summaries are not scored with ROUGE, because there are no reference summaries. Their faithfulness is handled by the grounding checks described in [NLP_TECHNIQUES.md](NLP_TECHNIQUES.md#9-summarization-summarizerpy), and the checks are unit-tested on known failure cases.
