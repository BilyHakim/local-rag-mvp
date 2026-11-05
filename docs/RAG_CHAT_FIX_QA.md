# RAG chat diagnosis, 2026-11-05

Observed: backend and Ollama responded, nomic-embed-text was installed, Qdrant
refused connections, and Docker Desktop's engine was not running. Docker Desktop
was started and the existing Qdrant container brought up. Qdrant now responds 200.

After restoring Qdrant, a real GPT-6 Luna request failed at evidence selection:
the provider reported finish_reason length with the previous 64-token limit.
The Command Code adapter now reserves reasoning capacity and lowers effort for
supported GPT/Gemini families. Truncated/empty responses have safe diagnostics.

Pure greetings bypass external dependencies; substantive questions still require
retrieval and grounding. Connection failures identify Qdrant or embedding safely.

Validation:

- Full backend suite: 130 passed.
- Live localhost greeting with selected GPT-6 Luna: HTTP 200, greeting, no sources.
- Direct real Command Code RAG: insufficient_evidence, no exception.
- Final live localhost RAG with GPT-6 Luna: HTTP 200, insufficient_evidence,
  five candidate sources. This verifies request completion, not answer quality
  for arbitrary company questions.
- An intervening live provider attempt returned 502; the final retry succeeded.
  External provider availability and token needs can still vary by model.
- No API keys, source text, or provider response bodies printed by diagnosis.
