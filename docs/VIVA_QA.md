# Viva questions and answers

## Project and design

**1. What problem does MeetingMind solve?**
It turns unstructured meeting transcripts into structured, verifiable information: summaries, decisions, action items with owners and deadlines, risks, open questions, entities, keywords and next steps. Every item is backed by transcript evidence, so people can trust or correct it.

**2. Why a hybrid of rules and ML instead of one large language model?**
The project had to run offline on a laptop with no paid APIs. Small pretrained models can't reliably extract structured fields on their own. Rules over a dependency parse are precise and explainable for commitment patterns, and sentence embeddings add semantic generalisation and act as a veto. Every decision can be traced and explained, which matters when people act on the output.

**3. Why is the backend stateless?**
For privacy and simplicity: there is no database to secure, nothing to leak, and no history to clean up. The browser holds the report, sends it back for export, and the server renders it. A side effect is that edits are always included in exports, because the export is generated from whatever the client sends.

**4. How do you show real progress rather than a fake progress bar?**
The pipeline calls a progress callback at the start and end of each of its 11 stages (and per summary chunk). FastAPI runs the pipeline in a worker thread, pushes the events into an `asyncio.Queue` with `call_soon_threadsafe`, and streams them as NDJSON. The progress bar counts completed server stages.

**5. How are models loaded efficiently?**
A thread-safe `ModelRegistry` lazily loads each model once per process and caches it. It records load times and failures, exposes their state in `/api/health`, and can preload in the background (`MEETINGMIND_PRELOAD_MODELS`). On failure the pipeline falls back (extractive summary, hashed vectors, or a blank spaCy pipeline) and reports a warning instead of crashing.

## NLP techniques

**6. What does spaCy contribute?**
Sentence segmentation, POS tags, dependency parses, lemmas, noun chunks and named entities. These drive the imperative check (root verb with no subject), lemma recovery ("Who's picking up…" → "pick up"), pronoun antecedents ("fix it" → "fix the checkout crash"), noun-phrase filtering of keyphrases, and the entity list.

**7. How do sentence embeddings help?**
MiniLM maps sentences to vectors where cosine similarity reflects meaning. We use them for:
- a few-shot nearest-prototype classifier (the margin between similarity to positive and negative examples);
- de-duplicating restated tasks;
- topic segmentation;
- KeyBERT-style keyphrase ranking with MMR;
- linking summary sentences to their evidence.

**8. Explain the nearest-prototype margin.**
For a candidate sentence s: margin = max over positive examples p of cos(s, p) − max over negative examples n of cos(s, n). A positive margin means s resembles the positive examples more than the hard negatives. Explicit patterns ("I'll…") are accepted unless the margin is very negative; weak patterns ("let's…") need a positive margin. It needs no training data.

**9. How is the owner of an action item determined?**
In priority order:
1. the speaker for "I"-commitments;
2. the named person for "Marcus will…" or "Elena to…";
3. the vocative for "Priya, can you…";
4. otherwise, the next speaker whose reply starts with acceptance ("Sure", "Will do", "Me");
5. otherwise **Unassigned**, with a reason.

Inferred owners are marked `inferred_from_reply` and flagged for review. Owners are never invented.

**10. How are relative deadlines normalised?**
Deterministic rules relative to the meeting date: "tomorrow" = +1 day; "end of week" = Friday; "next Friday" = Friday of next week, flagged if it could mean this Friday; "in two weeks" = +14 days; "end of Q2" = 30 June. Explicit dates use `dateparser`, with year inference and month/day ambiguity flags. Vague timing ("ASAP", "end of sprint") has no date by design.

**11. Why not use dateparser for everything?**
Its handling of relative business expressions is inconsistent and undocumented ("next Friday", "EOW", quarters), and it can't express ambiguity. Our rules are testable, documented and flag uncertainty; dateparser handles the explicit formats it is good at.

**12. How do you distinguish decisions from suggestions?**
- Suggestions ("maybe we should", "what if", "how about"), hypotheticals ("if we were to") and questions are filtered out.
- Decisions need cues ("we decided", "approved", "let's go with", "we won't"), with separate lexicons for rejected and tentative or conditional decisions.
- A suggestion becomes an *inferred agreement* only when another speaker explicitly agrees ("Agreed", "Works for me").
- A tag question ("…, right?") counts only if someone confirms it.

**13. How does topic segmentation work?**
It is TextTiling with embeddings. For each gap between sentences, compare the mean embedding of the 3 sentences before and after it; the depth score measures how deep the similarity valley is relative to the nearby peaks. Agenda phrases ("Moving on to…") add a strong bonus, and boundaries are chosen by depth with a minimum segment size.

**14. Explain the keyword pipeline.**
- YAKE proposes candidates using statistical features (no training).
- We keep candidates that are spaCy noun phrases and add multi-word noun chunks.
- We score each candidate by its embedding similarity to the whole meeting, its YAKE rank and its frequency.
- Maximal Marginal Relevance picks a diverse top 15.

**15. Which summarization model, and why?**
DistilBART fine-tuned on SAMSum, a dataset of chat dialogues. Dialogue-tuned models handle "Speaker: text" input much better than news summarizers, and DistilBART is small enough for a CPU. In our comparison it was more faithful than a larger meeting-summary model, which stated a conditional plan as fact.

**16. How do you summarize transcripts longer than the model's 1024-token limit?**
Hierarchical (map-reduce) summarization:
1. segment into topics;
2. split each topic into chunks of at most 850 tokens on turn boundaries;
3. summarize each chunk;
4. re-summarize if the joined chunk summaries are still too long;
5. build the executive summary from the topic summaries.

**17. How do you reduce hallucination in summaries?**
Each generated sentence is:
- **removed** if it contains a name or number that is not in the transcript, or if it is semantically unlike every transcript sentence;
- marked **weakly supported** if its names or numbers never occur near each other in the transcript (catching conflations), or if it claims "X will…" without a matching action item owned by X.

Each sentence also shows its supporting evidence. Decision and follow-up summaries are generated from the extracted data, not by the model.

**18. Are the "strong/moderate/weak" labels probabilities?**
No. They combine pattern explicitness with the semantic margin and are not calibrated against real frequencies, so presenting them as percentages would be misleading. The UI explains this.

## Evaluation and testing

**19. How did you evaluate?**
On 10 manually labelled transcripts (125 gold items) in three splits: dev (used for tuning), test (frozen first run, then post-hoc) and holdout-2 (written after all changes, run once). We report precision, recall and F1 per category by evidence-sentence matching, plus owner, deadline, status and kind accuracy on matched items, and compare against a keyword baseline.

**20. What were the results?**
On holdout-2, micro-F1 was 0.76 against 0.53 for the baseline. Action items scored F1 0.86; owner and deadline accuracy were 100% on matched items. Decisions reached 0.67 and risks 0.53, both limited by recall. The frozen first test run was 0.66, which revealed overfitting; we report it rather than hide it.

**21. Why is precision higher than recall, and is that acceptable?**
The rules require explicit evidence, so unusual phrasings get missed rather than invented. For a tool whose outputs people act on, missing an item, which the user can add manually, is less harmful than inventing a decision or owner.

**22. What do the automated tests cover?**
There are 112 backend tests:
- input validation;
- file uploads, including bad files, size limits and temp-file cleanup;
- speaker formats;
- owners, deadlines, decisions versus suggestions, risks and questions;
- evidence integrity;
- model-failure fallbacks;
- long-transcript chunking and grounding;
- the real summarizer;
- stream stage order;
- every export, including that user edits appear in each format, and CSV injection.

There are also 15 frontend tests (all 12 views render, edits propagate, and the processing handoff and errors).

## Privacy, limitations, future work

**23. What privacy guarantees are there, and what are their limits?**
No database or history, uploads deleted immediately, no transcript content in logs, local models, and the report held only in browser memory. The limits: an operator could modify the server to log data, the first run downloads models from Hugging Face (no user data is sent), and a Colab Gradio share link is public while it is active.

**24. What are the main limitations?**
Lexicon-bound recall for decisions and risks, a small single-annotator evaluation, abstractive summaries that can still misattribute details, the small spaCy NER model, no pronoun coreference, the need for speaker labels to assign "I'll…" commitments, CPU latency (about 30 s for a 650-word meeting), and English text only.

**25. How would you improve it?**
- Fine-tune a sentence classifier on annotated meeting corpora (AMI, ICSI) for decisions, actions and risks.
- Add coreference resolution and a stronger NER model.
- Use an NLI-based faithfulness check for summaries.
- Add Whisper speech-to-text with diarisation, and calendar (.ics) or task-tracker exports.
