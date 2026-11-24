# Northline — Knowledge Workspace demo kit


The video and screenshots preserve the earlier recorded demonstration. The current application uses refreshed source documents; see the project’s latest evaluation report for the current benchmark. The measurements shown in this recording describe that earlier run.

An edited, narrated walkthrough of real screenshots captured from the local application. This is not an uninterrupted screen recording. Product content was not fabricated or replaced. Detail crops and explanatory graphics are labeled separately.

## Included

- Northline-Preview-4K.gif: a 30-second looping walkthrough at 3840 × 2160, approximately 4.2 MiB.
- Northline-Preview-1080p.gif: the same walkthrough at 1920 × 1080, approximately 1.9 MiB.
- Northline-Demo-1080p.mp4: H.264/AAC video, subtitle track and scene chapters.
- Northline-Narration-Ryan.mp3: standalone narration with the same scene pauses as the video.
- Northline-Demo.en.srt: external subtitles aligned using the pipeline’s Whisper word timings.
- screenshots/: nine designed 3840 × 2160 PNGs for a portfolio or presentation.
- raw/: original 2× browser captures and captured page text. Desktop 1440 × 900 CSS pixels; mobile 390 × 844.
- index.html: offline video player and screenshot gallery. Open locally in a browser.
- production/storyboard.html and story.json: editable layout, narrative, and synthetic narration script.
- production/capture-checks.json: capture environment and browser-error result.

## Demo sequence

- LOCAL AI / INDUSTRIAL SUPPORT: From scattered manuals to inspectable answers.
- 01 / ORGANIZE THE KNOWLEDGE: One workspace. Eleven source documents.
- 02 / INSPECT THE INPUT: Check the text before it reaches the model.
- 03 / TRACE THE RETRIEVAL: See what the retriever actually found.
- 04 / ASK A REAL QUESTION: A specific fault. A specific model. A concise answer.
- 05 / VERIFY THE EVIDENCE: Correct value. Wrong source number.
- 06 / MAKE FAILURE VISIBLE: Keep the failure. Retry the step. Inspect the result.
- 07 / MEASURE THE TRADEOFFS: Evidence beyond the happy path.
- EXPLORE / INSPECT / REPRODUCE: Run it locally. Follow the evidence. Improve what fails.

## Evidence and limitations

Northline Industrial Systems Inc. is fictional. The supplied documents are generated demonstration materials. The workspace was built on an existing Vue/FastAPI RAG codebase; the underlying framework is not claimed as original work.

The captured live answer correctly says 20,000 but attributes it to Source 2. The explicit number is in Source 1. This defect is deliberately retained and discussed in the demo. The screenshot recovery example is an empty-file parse failure followed by source replacement and a real successful retry, using a temporary fixture that was deleted afterward. It is separate from the three previously completed SIGKILL restart checks.

Evaluation figures come from the earlier recorded run, preserved in evaluations/recorded-demo/summary.json and the included production/evidence/ report. They are historical development measurements, not a new benchmark or production/customer outcome. The 222-test count and restart checks refer to the repository's verification record.

Narration uses local Qwen3-TTS 1.7B CustomVoice bf16, speaker Ryan, through the supplied ai-video-pipeline. Its configured calm documentary style is retained. Whisper large-v3-turbo aligns the captions. The updated video runs approximately 2 minutes 22 seconds. Product screenshots were taken via Playwright/Chrome because the Browser plugin was unavailable. Capture had no uncaught JavaScript errors. The running app was not restyled or modified for these images.

## Suggested portfolio caption

An industrial-support RAG workspace using local Ollama models. This walkthrough demonstrates document ingestion, retrieval inspection, source verification, safe retries, and measured evaluation—including a real citation mismatch that remains to be fixed.

## Audio regeneration record

The supplied pipeline was used directly through its pipeline.tts and pipeline.subtitles modules, with its existing tools/audio virtual environment and cached models. No new model downloads were required. Source code and configuration in the supplied project were not changed. A working configuration and per-shot WAV/metadata/Whisper timings are in production/qwen-audio/. The lead-in is 0.4 seconds to match the demo composition.

The text of all nine Whisper transcriptions matches the script after case and punctuation normalization. This is an automated content check, not a guarantee of subjective voice quality or perfect phoneme alignment. Captions do not overlap or cross scene boundaries.

The screenshot images and narration script are unchanged. Scene durations, captions, chapter markers, and final audio were regenerated for the new voice. The older Samantha version was retained in a temporary backup outside this kit.

## Regenerate the animated preview

Run `python3 production/build_readme_gif.py` with FFmpeg installed. It uses the original nine 4K screenshots and exports both resolutions with a 30-second infinite loop.
