# Discord Message Collection and Label Archive Project Instructions

Read `docs/HANDOFF.md` before working on this project.

- This workspace owns collected Discord messages and confirmed human-label events.
- Discord access is read-only through the isolated Edge debug profile; never type, post, react, edit, or delete Discord content.
- Keep Qwen, Ollama, automatic trade interpretation, Webull, brokers, SIM, paper, and LIVE trading outside this project.
- Preserve the legacy V5 evaluation files and holdout artifacts unless Greg explicitly requests archival or removal.
- Keep credentials, browser profiles, runtime databases, and raw message exports local and untracked.
- V6 is the sole operator for collection and conversational labeling. It may invoke V5-owned commands, but it must never edit `data/messages.sqlite3` or `data/human_label_events.jsonl` directly.
