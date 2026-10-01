# Asisten JUP latency + retrieval — 2026-10-02

Erik: "getting an answer really takes time". Measured end to end through the UI path (chat + background task).

## Causes found
- Retrieval itself is fast (70–90 ms). Time is in 2–4 model rounds per answer, each paying MiMo's
  time-to-first-token (normally ~1 s, spikes to ~12 s; OpenRouter has ONE provider, Xiaomi, no failover).
- 600–1,400 reasoning tokens per answer; every builtin tool enabled (~5k-token baseline prompt).
- Embedding model was all-MiniLM-L6-v2 (English-only) on an Indonesian KB; vector-only search; so the
  first search missed and the model searched again / grepped / opened files.
- KB collections carry no grants (ADR-0015) and the vendor tools checked grants on model-attached
  collections → non-admin staff got NO KB results (admins did). Voice model had 8 single files, not the
  collections.
- Vendor grep treated "(?i)direktur" as literal text → "No matches".

## Changes (all live on ent-os-00066-5tn, image b5e1dfb27)
1. Asisten JUP `custom_params.reasoning.effort = low`; builtinTools = time, files, knowledge only.
2. Voice model `asisten-jup-suara` knowledge = JUP Strategy KB + JUP Staff Contributions.
   Before-values: `.planning/model-settings-before-latency-fix-2026-10-02.json`.
3. Hybrid search on, TOP_K_RERANKER 5 (before: `.planning/rag-config-before-hybrid-2026-10-02.json`).
4. PR #48: model-attached collections readable by the model's users (`_can_read_knowledge`);
   multilingual-e5-small baked + query/passage prefixes; live model switched by API, /knowledge/reindex
   (59 files, 118 s), label-only restart (00065).
5. PR #49: grep regex detection recognises `(?` and `\b`.

## Result (same questions, UI path)
| Question | Before | After |
|---|---|---|
| BP BUMD & pengangkatan direksi | 18.5 s | 7.0 s, correct |
| Siapa direktur utama JUP? | 30 s (correct) / later "not found" | 5.4 s, correct |
| Direksi dan komisaris JUP | — | 7.8 s, correct |
| PAM Jaya Rorotan | — | 13.7 s, correct (on 00065) |

## Open
- MiMo TTFT spikes remain; next lever is a model trial (Erik's call).
- A real non-admin check of KB answers waits on Rully's account (#46).
- Test chats "Uji kecepatan …" in Erik's account.
