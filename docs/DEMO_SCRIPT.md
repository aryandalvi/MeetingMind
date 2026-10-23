# Project demonstration script (about 10 minutes)

## Before the demo

- Start both servers: `scripts/start-backend` and `scripts/start-frontend`.
- Run one analysis beforehand so the models are loaded. The first run after starting the server spends about 10 s loading models; the very first run on a machine also downloads ~1.3 GB.
- Keep these open in tabs:
  - http://localhost:5173
  - http://127.0.0.1:8000/docs
  - `samples/sample_minutes.pdf`
- Have a DOCX or PDF transcript ready to upload, for example a copy of `backend/evaluation/data/test_sprint.txt` pasted into Word.

## 1. Problem and idea (1 min)

> "Meetings create decisions and commitments, but they get lost in long transcripts. MeetingMind turns a transcript into a structured, evidence-backed report: who does what by when, what was decided, what could go wrong, and what is still open. Every item links to the exact lines it came from."

Show the **Dashboard**: tagline, feature cards and the privacy card.

## 2. Input (1.5 min)

- Click **Try the sample transcript**. Point out the title, the date ("this is how 'next Friday' becomes a real date") and the context field.
- Drag in the DOCX file to show server-side extraction, the file banner and the editable preview. Then reload the sample.
- Mention the word count, the speaker-line detection and the validation: try **Analyze** on an empty editor to show the error.

## 3. Processing (1 min)

- Click **Analyze meeting**.
- > "These stages are real: the server streams an event as each one starts and finishes, and the times are measured on the server."
- Point out the summarization progress ("Summarising topic 2 of 4").

## 4. Results tour (4 min)

1. **Overview:** counts, talk share by speaker, the models used and processing notes. For example: "1 generated summary sentence was removed because it wasn't supported by the transcript."
2. **Executive summary:** each sentence has "Supported by" evidence. Show the *weakly supported* badge on the conflated sentence:
   > "The model merged two facts; our grounding check caught it because Android 9 and March 17 never appear close together in the transcript."
3. **Decisions:** confirmed, tentative and rejected. Open the evidence for "Android 9 is out of scope":
   > "It was asked as a tag question, 'right?', and only counted because Priya confirmed it."
4. **Action items:**
   - A1, "Fix the checkout crash" from "…and I'll fix **it** by Thursday": clause splitting plus pronoun antecedent.
   - A4, owner *inferred from reply*: "Can someone follow up with legal?" — David: "I'll take that."
   - "Prepare the press release draft — by next Wednesday", flagged as ambiguous.
   - "Write the FAQ", Unassigned:
     > "We never invent owners."
5. **Edit:** change an owner, set a deadline, mark one item done, add a task. Note the *edited* badges.
6. **Deadlines:** resolved dates with "in N days", relative versus explicit, and ambiguity notes.
7. **Risks, Questions and Next steps:** the blocker "until PayFlow releases 4.2"; deferred questions; recommendations with rationale.
8. **Transcript evidence:** click any "Evidence" link to jump to and highlight the sentence; filter by item type.

## 5. Export (1 min)

- **Export → PDF meeting minutes.** Open it and show that the edited owner, status and the new task appear.
- **Export → CSV** and open it in Excel:
  > "Formula-injection safe, UTF-8, ready for a task tracker."

## 6. Under the hood and evaluation (1.5 min)

- Open `/docs` (Swagger) and show the endpoints and the `AnalysisReport` schema.
- The NLP stack: spaCy parsing and NER, MiniLM embeddings for prototype classification, segmentation and keyphrase re-ranking, YAKE, dateparser, and DistilBART-SAMSum with map-reduce summarization and grounding checks.
- Evaluation:
  > "On a held-out set written after development, micro-F1 was 0.76 against a keyword baseline's 0.53, with 100% owner and deadline accuracy on found items. Decision and risk recall are the main limitation. We also report our first held-out result (0.66), which shows how we found the system was overfitting."
- Privacy: no database, uploads deleted, no transcript logging, local models only.

## Backup plan

- If the summarizer is slow or offline, set `MEETINGMIND_SUMMARY_MODE=extractive` and restart; everything else works the same.
- If the backend is down, the header shows **API offline**, and the New Analysis page shows a clear error.
- The Colab notebook (Step 7, Gradio) is an alternative demo environment.
