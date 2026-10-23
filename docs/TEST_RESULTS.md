# Test results

Recorded on 2026-10-24 on Windows 10, Python 3.14, Node 26, CPU only (no GPU used).

| Suite | Command | Result |
|---|---|---|
| Backend (pytest, includes the slow real-summarizer test) | `cd backend && python -m pytest` | **112 passed** in ~51 s |
| Frontend (Vitest + jsdom) | `cd frontend && npm test` | **15 passed** |
| TypeScript | `cd frontend && npx tsc -b` | no errors |
| Production build | `cd frontend && npm run build` | succeeds |
| Notebook | executed end-to-end with nbclient outside Colab | all cells ran; Colab-only upload/download steps skipped |
| End-to-end (scripted Chrome, against the production build) | dashboard, DOCX upload, sample analysis with live stages, all 12 views, editing, 4 exports, evidence jump | passed; analysis took ~34 s on CPU with models cached; CSV, Markdown and PDF downloads contained the edits |
| Mobile layout (390 px) | dashboard, new analysis, results, action items, evidence | no horizontal overflow, no page errors |

Evaluation metrics: see [EVALUATION.md](EVALUATION.md).

## Backend tests

```text
tests/test_api.py::test_health PASSED
tests/test_api.py::test_analyze_validation_errors[payload0-empty] PASSED
tests/test_api.py::test_analyze_validation_errors[payload1-empty] PASSED
tests/test_api.py::test_analyze_validation_errors[payload2-too short] PASSED
tests/test_api.py::test_analyze_validation_errors[payload3-transcript] PASSED
tests/test_api.py::test_analyze_validation_errors[payload4-meeting_date] PASSED
tests/test_api.py::test_analyze_validation_errors[payload5-does not look like a transcript] PASSED
tests/test_api.py::test_analyze_rejects_too_long PASSED
tests/test_api.py::test_analyze_report_shape PASSED
tests/test_api.py::test_stream_emits_real_stages_then_result PASSED
tests/test_api.py::test_stream_validation_error_is_http_422 PASSED
tests/test_api.py::test_extract_supported_files[txt] PASSED
tests/test_api.py::test_extract_supported_files[txt-utf16] PASSED
tests/test_api.py::test_extract_supported_files[docx] PASSED
tests/test_api.py::test_extract_supported_files[pdf] PASSED
tests/test_api.py::test_extract_rejects_bad_files[notes.exe-MZ\x90\x00-415-Unsupported] PASSED
tests/test_api.py::test_extract_rejects_bad_files[notes.doc-\xd0\xcf\x11\xe0-415-.docx] PASSED
tests/test_api.py::test_extract_rejects_bad_files[empty.txt--400-empty] PASSED
tests/test_api.py::test_extract_rejects_bad_files[fake.pdf-hello this is not a pdf-415-valid PDF] PASSED
tests/test_api.py::test_extract_rejects_bad_files[fake.docx-not a zip-415-valid .docx] PASSED
tests/test_api.py::test_extract_rejects_bad_files[scan.pdf-%PDF-1.3\n%\x93\x8c\x8b\x9e ReportLab Generated PDF document (opensource)\n1 0 obj\n<<\n/F1 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/BaseFont /Helvetica /Encoding /WinAnsiEncoding /Name /F1 /Subtype /Type1 /Type /Font\n>>\nendobj\n3 0 obj\n<<\n/Contents 7 0 R /MediaBox [ 0 0 595.2756 841.8898 ] /Parent 6 0 R /Resources <<\n/Font 1 0 R /ProcSet [ /PDF /Text /ImageB /ImageC /ImageI ]\n>> /Rotate 0 /Trans <<\n\n>> \n  /Type /Page\n>>\nendobj\n4 0 obj\n<<\n/PageMode /UseNone /Pages 6 0 R /Type /Catalog\n>>\nendobj\n5 0 obj\n<<\n/Author (anonymous) /CreationDate (D:20261024010603+05'00') /Creator (anonymous) /Keywords () /ModDate (D:20261024010603+05'00') /Producer (ReportLab PDF Library - \(opensource\)) \n  /Subject (unspecified) /Title (untitled) /Trapped /False\n>>\nendobj\n6 0 obj\n<<\n/Count 1 /Kids [ 3 0 R ] /Type /Pages\n>>\nendobj\n7 0 obj\n<<\n/Filter [ /ASCII85Decode /FlateDecode ] /Length 79\n>>\nstream\nGapQh0MjH"0EdT]\I&[=+U\'`L'iZ)$6a*jL*h3n$6_S?Xs%%q$Dn"MA7P\V7B$Vh>$MD>!1gM+W;~>endstream\nendobj\nxref\n0 8\n0000000000 65535 f \n0000000061 00000 n \n0000000092 00000 n \n0000000199 00000 n \n0000000402 00000 n \n0000000470 00000 n \n0000000731 00000 n \n0000000790 00000 n \ntrailer\n<<\n/ID \n[<5480bba3d885f60f4cca0f08bd6a11c4><5480bba3d885f60f4cca0f08bd6a11c4>]\n% ReportLab generated PDF document -- digest (opensource)\n\n/Info 5 0 R\n/Root 4 0 R\n/Size 8\n>>\nstartxref\n958\n%%EOF\n-422-scanned] PASSED
tests/test_api.py::test_extract_rejects_bad_files[binary.txt-\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03\x00\x01\x02\x03-415-binary] PASSED
tests/test_api.py::test_extract_rejects_oversized_file PASSED
tests/test_api.py::test_temporary_upload_files_are_removed PASSED
tests/test_api.py::test_exports[json-application/json] PASSED
tests/test_api.py::test_exports[csv-text/csv] PASSED
tests/test_api.py::test_exports[markdown-text/markdown] PASSED
tests/test_api.py::test_exports[pdf-application/pdf] PASSED
tests/test_api.py::test_user_edits_are_reflected_in_every_export PASSED
tests/test_api.py::test_csv_neutralises_formula_injection PASSED
tests/test_api.py::test_export_rejects_invalid_report PASSED
tests/test_deadlines.py::test_resolves_explicit_and_relative_dates[send it by Friday-expected0] PASSED
tests/test_deadlines.py::test_resolves_explicit_and_relative_dates[finish it tomorrow-expected1] PASSED
tests/test_deadlines.py::test_resolves_explicit_and_relative_dates[by end of day-expected2] PASSED
tests/test_deadlines.py::test_resolves_explicit_and_relative_dates[by EOD-expected3] PASSED
tests/test_deadlines.py::test_resolves_explicit_and_relative_dates[by end of week-expected4] PASSED
tests/test_deadlines.py::test_resolves_explicit_and_relative_dates[in two weeks-expected5] PASSED
tests/test_deadlines.py::test_resolves_explicit_and_relative_dates[within 3 days-expected6] PASSED
tests/test_deadlines.py::test_resolves_explicit_and_relative_dates[by March 10-expected7] PASSED
tests/test_deadlines.py::test_resolves_explicit_and_relative_dates[by the 15th-expected8] PASSED
tests/test_deadlines.py::test_resolves_explicit_and_relative_dates[due 2026-04-01-expected9] PASSED
tests/test_deadlines.py::test_resolves_explicit_and_relative_dates[by the end of the month-expected10] PASSED
tests/test_deadlines.py::test_resolves_explicit_and_relative_dates[by the end of Q2-expected11] PASSED
tests/test_deadlines.py::test_resolves_explicit_and_relative_dates[Friday next week-expected12] PASSED
tests/test_deadlines.py::test_resolves_explicit_and_relative_dates[on 12/25-expected13] PASSED
tests/test_deadlines.py::test_month_without_year_rolls_into_next_year PASSED
tests/test_deadlines.py::test_ambiguous_dates_are_flagged[by next Friday] PASSED
tests/test_deadlines.py::test_ambiguous_dates_are_flagged[next Wednesday] PASSED
tests/test_deadlines.py::test_ambiguous_dates_are_flagged[due 3/4] PASSED
tests/test_deadlines.py::test_ambiguous_dates_are_flagged[next week] PASSED
tests/test_deadlines.py::test_ambiguous_dates_are_flagged[mid-April] PASSED
tests/test_deadlines.py::test_ambiguous_dates_are_flagged[next month] PASSED
tests/test_deadlines.py::test_bare_weekday_equal_to_meeting_day_is_ambiguous PASSED
tests/test_deadlines.py::test_vague_timing_is_never_converted_to_a_date[ASAP] PASSED
tests/test_deadlines.py::test_vague_timing_is_never_converted_to_a_date[as soon as possible] PASSED
tests/test_deadlines.py::test_vague_timing_is_never_converted_to_a_date[by end of sprint] PASSED
tests/test_deadlines.py::test_vague_timing_is_never_converted_to_a_date[before the launch] PASSED
tests/test_deadlines.py::test_relative_dates_not_resolved_without_meeting_date PASSED
tests/test_deadlines.py::test_explicit_year_resolves_without_meeting_date PASSED
tests/test_deadlines.py::test_no_deadline_invented[I may be late] PASSED
tests/test_deadlines.py::test_no_deadline_invented[we met last Tuesday] PASSED
tests/test_deadlines.py::test_no_deadline_invented[it happened yesterday] PASSED
tests/test_deadlines.py::test_no_deadline_invented[the meeting was great] PASSED
tests/test_deadlines.py::test_prefers_phrase_with_preposition PASSED
tests/test_extraction.py::test_self_commitment_owner_is_speaker PASSED
tests/test_extraction.py::test_named_owner_in_third_person PASSED
tests/test_extraction.py::test_minutes_style_name_to_verb PASSED
tests/test_extraction.py::test_request_with_vocative PASSED
tests/test_extraction.py::test_owner_inferred_from_reply PASSED
tests/test_extraction.py::test_unassigned_when_nobody_volunteers PASSED
tests/test_extraction.py::test_multiple_speakers_each_get_their_items PASSED
tests/test_extraction.py::test_past_tense_and_hypotheticals_are_not_actions PASSED
tests/test_extraction.py::test_clause_level_commitment_with_antecedent PASSED
tests/test_extraction.py::test_vague_reply_is_merged_into_request PASSED
tests/test_extraction.py::test_unlabelled_transcript_still_finds_named_owner PASSED
tests/test_extraction.py::test_decision_statuses PASSED
tests/test_extraction.py::test_suggestions_questions_and_hypotheticals_are_not_decisions PASSED
tests/test_extraction.py::test_agreement_on_proposal_becomes_inferred_decision PASSED
tests/test_extraction.py::test_conditional_decision_is_tentative PASSED
tests/test_extraction.py::test_risks_and_blockers PASSED
tests/test_extraction.py::test_unanswered_and_deferred_questions PASSED
tests/test_extraction.py::test_filler_questions_ignored PASSED
tests/test_extraction.py::test_entities_people_and_keywords PASSED
tests/test_extraction.py::test_every_item_has_evidence_that_exists_in_transcript PASSED
tests/test_extraction.py::test_sample_report_core_items PASSED
tests/test_extraction.py::test_no_meeting_date_uses_header_or_warns PASSED
tests/test_models_and_long.py::test_registry_records_failure_and_raises PASSED
tests/test_models_and_long.py::test_summarizer_failure_falls_back_to_extractive PASSED
tests/test_models_and_long.py::test_all_models_failing_still_produces_a_report PASSED
tests/test_models_and_long.py::test_chunks_respect_token_limit PASSED
tests/test_models_and_long.py::test_long_transcript_hierarchical_summary PASSED
tests/test_models_and_long.py::test_grounding_removes_unsupported_names PASSED
tests/test_models_and_long.py::test_grounding_flags_conflated_facts PASSED
tests/test_models_and_long.py::test_grounding_flags_commitments_without_matching_action PASSED
tests/test_models_and_long.py::test_real_abstractive_summarizer PASSED
tests/test_preprocessing.py::test_basic_speaker_labels_and_sentences PASSED
tests/test_preprocessing.py::test_speaker_formats[[00:01:23] Priya Sharma: We should ship.-Priya Sharma-00:01:23] PASSED
tests/test_preprocessing.py::test_speaker_formats[Priya (12:05): We should ship.-Priya-12:05] PASSED
tests/test_preprocessing.py::test_speaker_formats[00:12 - Priya: We should ship.-Priya-00:12] PASSED
tests/test_preprocessing.py::test_speaker_formats[**Priya:** We should ship.-Priya-None] PASSED
tests/test_preprocessing.py::test_speaker_formats[Speaker 1: We should ship.-Speaker 1-None] PASSED
tests/test_preprocessing.py::test_metadata_lines_are_not_speakers PASSED
tests/test_preprocessing.py::test_otter_style_headers PASSED
tests/test_preprocessing.py::test_webvtt_voice_tags PASSED
tests/test_preprocessing.py::test_srt_numbers_are_skipped PASSED
tests/test_preprocessing.py::test_plain_text_without_speakers_warns PASSED
tests/test_preprocessing.py::test_continuation_lines_merge_into_previous_turn PASSED
tests/test_preprocessing.py::test_speaker_plausibility[Priya-True] PASSED
tests/test_preprocessing.py::test_speaker_plausibility[Dr. Smith-True] PASSED
tests/test_preprocessing.py::test_speaker_plausibility[Note-False] PASSED
tests/test_preprocessing.py::test_speaker_plausibility[So the plan is-False] PASSED
tests/test_preprocessing.py::test_speaker_plausibility[Action items-False] PASSED
============================ 112 passed in 47.26s =============================
```

## Frontend tests

```text
 ✓ src/test/processing.test.tsx > Processing page > shows real stages and hands the report to the results page 91ms
 ✓ src/test/processing.test.tsx > Processing page > shows the server's error message 12ms
 ✓ src/test/results.test.tsx > Results page > renders the overview section 119ms
 ✓ src/test/results.test.tsx > Results page > renders the summary section 44ms
 ✓ src/test/results.test.tsx > Results page > renders the topics section 31ms
 ✓ src/test/results.test.tsx > Results page > renders the decisions section 30ms
 ✓ src/test/results.test.tsx > Results page > renders the actions section 80ms
 ✓ src/test/results.test.tsx > Results page > renders the deadlines section 34ms
 ✓ src/test/results.test.tsx > Results page > renders the risks section 34ms
 ✓ src/test/results.test.tsx > Results page > renders the questions section 37ms
 ✓ src/test/results.test.tsx > Results page > renders the people section 32ms
 ✓ src/test/results.test.tsx > Results page > renders the keywords section 29ms
 ✓ src/test/results.test.tsx > Results page > renders the evidence section 48ms
 ✓ src/test/results.test.tsx > Results page > renders the next section 46ms
 ✓ src/test/results.test.tsx > Results page > edits to an action item update the report used for exports 156ms
 Test Files  2 passed (2)
      Tests  15 passed (15)
```
