# Narration transcript

## LOCAL AI / INDUSTRIAL SUPPORT

Meet Knowledge Workspace: a local AI support platform for the fictional Northline Industrial Systems. Follow a technician from a device fault to an answer, then inspect the evidence behind it.

## 01 / ORGANIZE THE KNOWLEDGE

The workspace organizes eleven source documents across three knowledge bases. Administrators can upload, preview, parse, split, and embed files, while checking their status in one place.

## 02 / INSPECT THE INPUT

Start with the input. This spreadsheet contains the gateway fault codes. The parsing preview exposes the extracted table, so an engineer can check the content before indexing it.

## 03 / TRACE THE RETRIEVAL

For error five zero two two, retrieval testing exposes the selected passages, their scores, and timing. The fault-code reference appears first, making retrieval behavior visible before generation.

## 04 / ASK A REAL QUESTION

Now ask the assistant about the G T E three thousand Pro. The live local model returns the correct limit: twenty thousand data points. Next, inspect its source attribution.

## 05 / VERIFY THE EVIDENCE

This capture exposes a citation defect. The answer names source two, but the explicit limit appears in source one. The inspector makes the mismatch visible. Citation accuracy still needs improvement.

## 06 / MAKE FAILURE VISIBLE

Processing history preserves a failed attempt beside its successful retry. Separately, kill-and-restart tests passed for parsing, splitting, and embedding. Partial output is cleaned before an administrator retries.

## 07 / MEASURE THE TRADEOFFS

The development evaluation records one hundred fifty comparisons across fifty questions. Hybrid retrieval passed seventeen of eighteen selected technical fact checks, versus fifteen for vector search. These are development results, not production accuracy.

## EXPLORE / INSPECT / REPRODUCE

Run the stack locally with Docker Compose and host Ollama. The repository includes architecture, contribution notes, recovery tests, and documented limitations. I built it on an existing RAG codebase and demonstrated it with fictional company materials.