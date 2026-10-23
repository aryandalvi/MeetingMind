# NLP techniques used in MeetingMind

This document explains each technique, why it was chosen, and where it lives in the code.

## 1. Preprocessing ([preprocessing.py](../backend/app/nlp/preprocessing.py))

- **Normalisation:** Unicode NFKC, curly quotes to straight quotes, invisible characters removed.
- **Speaker grammar:** a regular expression recognises `Name: text`, `[00:01:23] Name: text`, `Name (12:05): text`, `00:12 - Name: text` and `**Name:** text`. Otter/Teams-style headers (`Name  0:15` on its own line) and WebVTT `<v Name>` tags are handled too. A label counts as a speaker only if it looks like a name: at most 4 capitalised words, not a stop-label such as `Note`, `Agenda` or `Action items`.
- **Metadata:** `Meeting:`, `Date:` and `Attendees:` lines are kept out of the speech. The `Date:` line supplies the meeting date when the user gives none, and attendees help resolve names.
- **Utterances and sentences:** consecutive lines from the same speaker are merged into one utterance, then split into sentences with spaCy. Each sentence gets an id (`s12`) that every piece of evidence refers to.

## 2. Linguistic analysis (spaCy `en_core_web_sm`)

A single pass gives tokens, lemmas, POS tags, dependency trees, noun chunks and named entities. These support:

- the imperative check: the first verb is the root with tag `VB`/`VBP` and has no `nsubj`;
- verb lemmas in "Who's **picking** up X?" → "pick up X";
- pronoun antecedents: "The checkout crash is on our side, and I'll fix **it**" → "Fix the checkout crash";
- named entities (PERSON, ORG, GPE, DATE, MONEY, PRODUCT, …), merged with speaker labels, with generic acronyms filtered out.

## 3. Sentence embeddings (Sentence-Transformers `all-MiniLM-L6-v2`)

MiniLM maps a sentence to a 384-dimensional vector, so cosine similarity measures semantic closeness. It was chosen because it is small (90 MB), fast on CPU and strong on semantic textual similarity. Its uses:

- **Nearest-prototype classification.** Each extractor has a handful of hand-written positive and negative example sentences, and a candidate's *margin* = max similarity to the positives − max similarity to the negatives. Weak rule matches need a positive margin; strong rule matches are only flagged if the margin is very negative. This is a few-shot, training-free classifier.
- **De-duplication** of action items (cosine ≥ 0.86) and decisions.
- **Topic segmentation** (section 7), **keyphrase re-ranking** (section 8), and **summary evidence linking**.

If the model cannot load, a hashed bag-of-n-grams vector keeps segmentation and de-duplication working, and semantic checks are switched off.

## 4. Action items ([actions.py](../backend/app/nlp/actions.py))

1. **Candidate patterns**, ordered from most to least explicit:
   - labels: `Action: Lucia to test the CSV import`;
   - self-commitments: `I'll / I'm going to / let me / I can …`;
   - named commitments: `Marcus will …`, `Elena to contact …` (the name must resolve to a speaker, attendee, PERSON entity or team);
   - requests: `Priya, can you …?`, `Could you please …?`, `Can someone …?`, `Who's picking up …?`;
   - assignments: `Assign X to Y`;
   - collective: `We need to …`, `Let's …`;
   - bare imperatives.

   Long sentences are split into clauses, so commitments in the middle of a sentence are found.
2. **Filters:** past-tense reports, hypotheticals, negations near the cue, "no promises" offers, contingencies ("If X, we'll Y" is treated as a decision), suggestions ("we should consider"), meeting logistics ("let's move on", "let's meet again") and recaps.
3. **Semantic check:** the prototype margin, with a threshold that depends on how explicit the pattern was.
4. **Owner resolution:**
   - the speaker for "I"; the named person for third-person commitments;
   - the vocative for "Name, can you…";
   - otherwise the next speaker whose reply starts with acceptance ("Sure", "Will do", "Me", "I'll take that"), which is marked as inferred;
   - otherwise **Unassigned**, with the reason.
5. **Discourse merging:** vague replies ("I'll have that to you this afternoon") and vague follow-up requests ("please do that before Monday") attach their deadline and evidence to the task they refer to. Acceptances fold into the request, and a day-level date replaces a week-level one.
6. **Output:** a cleaned task description ("me" is replaced by the requester's name), deadline, heuristic priority, review reasons and evidence sentences.

## 5. Deadlines ([deadlines.py](../backend/app/nlp/deadlines.py))

- **Explicit dates** (`March 10`, `3rd of May`, `2026-04-01`, `12/25`) are parsed with **dateparser**, relative to the meeting date. A missing year is inferred, and numeric dates such as `3/4` are flagged as ambiguous between month/day and day/month.
- **Relative expressions** use deterministic rules: today/EOD/this afternoon, tomorrow, weekdays (bare, this, next, "Friday next week"), end of week/month/quarter, this or next week/month/quarter, Q1–Q4, in/within N days/weeks/months, "the 15th", early/mid/late month.
- **Ambiguity:** "next Friday" (this coming Friday or the one after?), a bare weekday equal to the meeting day, week- or month-level deadlines, and approximate dates are flagged with an explanation.
- **Vague timing** (ASAP, soon, end of sprint, before the launch) is recorded with *no date*. MeetingMind never invents a calendar date. Without a meeting date, relative expressions stay unresolved and the report warns.

## 6. Decisions, risks, questions

- **Decisions:** separate cue sets for confirmed decisions ("we decided", "approved", "let's go with", "X moves to Friday"), rejections ("decided against", "out of scope", "we won't go above"), and tentative or conditional decisions ("for now", "pending", "unless", "if …, we'll …"). Suggestion, hypothetical and question filters prevent false positives. Tag questions ("we agreed not to support Android 9, right?") count only when someone confirms them, and a proposal followed by "Agreed" or "Works for me" from another speaker becomes an inferred agreement. Plan-like statements without a strong cue must pass the semantic check.
- **Risks and blockers:** a problem and dependency lexicon ("blocked until", "waiting on", "worried", "short-staffed", "rate limited", "gone quiet") with filters for negations ("no blockers"), commitments, suggestions, recaps and short anaphora ("That's a real risk."). Blockers are separated from risks. Severity is a keyword heuristic ("critical", "launch", "security" → high) and is labelled as such.
- **Questions:** a question is unresolved if no other speaker gives a substantive answer within the next three turns, or if the reply defers it ("not sure yet", "let's decide that next week", "hold off"). Hedged replies ("Maybe…") do not count as answers if a deferral follows, and a topic change ("let's move on") counts as no answer. Explicit open issues ("we haven't figured that out yet") are added with the sentence they refer to.

## 7. Topic segmentation ([topics.py](../backend/app/nlp/topics.py))

This follows TextTiling (Hearst, 1997), with embeddings in place of word counts:

- For each gap between sentences, compute the cosine similarity of the mean embeddings of the 3 sentences on each side.
- The **depth score** at a gap is how far the similarity there dips below the nearby peaks on both sides.
- Agenda transitions ("Moving on to…", "Last topic:") add +2 to the depth.
- Boundaries are chosen greedily by depth, with at least 6 sentences per segment and roughly one topic per 12 sentences.
- Each topic is labelled with its best multi-word keyphrase, and its key points are the most central sentences under TextRank.

## 8. Keywords ([keywords.py](../backend/app/nlp/keywords.py))

- **YAKE** (Campos et al., 2020) scores candidate n-grams with unsupervised statistical features (casing, position, frequency, context dispersion). Candidates are kept only if they occur inside a spaCy noun chunk, which removes fragments like "Elena contacts".
- **KeyBERT-style re-ranking:** score = 0.5 × embedding similarity to the whole meeting + 0.3 × YAKE rank + 0.2 × frequency, with a small bonus for multi-word phrases.
- **Maximal Marginal Relevance** (λ = 0.55) picks phrases that are relevant but not redundant with each other. Speaker names, dates and conversational words are excluded.

## 9. Summarization ([summarizer.py](../backend/app/nlp/summarizer.py))

- **Model:** `philschmid/distilbart-cnn-12-6-samsum`, a DistilBART encoder-decoder fine-tuned on SAMSum, a dataset of chat dialogues and their summaries. Dialogue-tuned models handle `Speaker: text` input far better than news summarizers. In a comparison during development, it was more faithful than `knkarthick/MEETING_SUMMARY`, which stated a conditional postponement as fact.
- **Hierarchical (map-reduce) summarization:**
  - each topic's dialogue is split into chunks of at most 850 tokens on turn boundaries;
  - each chunk is summarized with 4-beam search and `no_repeat_ngram_size=3`;
  - if the combined chunk summaries are still long, they are summarized again;
  - the executive summary is generated from the topic summaries.

  This handles transcripts far beyond the model's 1024-token window.
- **Grounding checks** (hallucination control):
  1. A generated sentence is **removed** if it contains a capitalised name or a number that never appears in the transcript.
  2. It is removed if its best cosine similarity to any transcript sentence is below 0.25.
  3. It is marked **weakly supported** if two of its names or numbers never occur within one sentence of each other in the transcript. This catches conflations such as "Android 9 was moved to March 17".
  4. It is marked weakly supported if it claims a person *will* do something and no extracted action item owned by that person matches.

  Each kept sentence carries its two most similar transcript sentences as evidence.
- **Extractive fallback:** TextRank (PageRank over a cosine-similarity graph), boosted for sentences that carry decisions or risks.
- **Decision and follow-up summaries** are generated deterministically from the extracted items, so they cannot hallucinate.

## 10. Recommended next steps ([next_steps.py](../backend/app/nlp/next_steps.py))

Rules over the extracted items produce the recommendations:

- resolve blockers;
- assign owners or deadlines;
- confirm ambiguous dates and tentative decisions;
- mitigate high-severity risks;
- answer open questions;
- check workload when one person owns most tasks;
- prioritise the earliest deadline;
- schedule a follow-up meeting.

Each recommendation includes a rationale and the evidence of the item it is based on, and the UI labels them as MeetingMind's suggestions, not statements from the meeting.

## 11. Reliability principles

- **Evidence everywhere:** every action item, decision, risk, question, entity, deadline and summary sentence references sentence ids.
- **Explicit vs inferred:** `is_inferred`, `owner_source` (named in transcript, self-commitment, addressed request, inferred from reply, unassigned, set by user), `date_type` (explicit, relative, vague, user) and `grounding` (supported, weak).
- **Review flags** come with human-readable reasons.
- **No calibrated-probability claims:** the "signal" labels (strong, moderate, weak) are explicitly described as heuristics.
- **Never invent:** no owner without a source, no date for vague timing, no decision from a suggestion without an explicit agreement.
