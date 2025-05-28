# ThoughtMachine‑Experimental

> ⚠️ **Experimental Project** — under heavy development. Expect breaking changes.

ThoughtMachine‑Experimental is a playground for building an **agentic system** that can **write, modify, and execute its own "thoughts"** (modular skills) while interacting with users in natural language. It aims to bridge everyday automation (e.g. desktop tasks) and advanced coding workflows under a single, self‑evolving framework.

---

## Vision

1. **Self‑Modifying Agents** – Agents can generate new thoughts or refactor existing ones when prompted or when their own planning deems it beneficial.
2. **Composable Thoughts** – Each thought is an isolated module (Python + metadata) that can be chained into larger workflows.
3. **Human‑in‑the‑Loop** – A chat interface lets users inspect, approve, or edit code before execution.
4. **Environment Control** – Thoughts can invoke local shell commands, manipulate files, control GUI automation, or call external APIs / LLMs.

---

## Repository Layout

| Path                      | Purpose                                            |
| ------------------------- | -------------------------------------------------- |
| `thoughtmachine/agents`   | Core runtime, planner, and execution engine        |
| `thoughtmachine/thoughts` | Built‑in example thoughts                          |
| `cli.py` & `server.py`    | CLI and FastAPI chat server                        |
| `docs/`                   | Additional technical notes & architecture sketches |

---

## Quick Start

```bash
# 1 · Clone
$ git clone https://github.com/theEmptyAi/ThoughtMachine-Experimental.git
$ cd ThoughtMachine-Experimental

# 2 · (Optional) create & activate a virtualenv
$ python -m venv .venv && source .venv/bin/activate

# 3 · Install core deps (add `openai` if you plan to call LLMs)
$ pip install -r requirements.txt

# 4 · Run the CLI
$ python cli.py
```

If you plan to use an LLM thought, export an API key first (e.g. `export OPENAI_API_KEY=sk‑…`).

---

## Chat‑Driven Examples

### 1 · Creating a Non‑LLM Thought (simple automation)

```
user > create a thought RenameScreenshots that watches my Desktop and renames any file starting with "+Screenshot" to "Screenshot‑<timestamp>.png".

agent > ✓ Thought `RenameScreenshots` created and saved under thoughts/filesystem/rename_screenshots.py.
agent > Execute now? (yes/no)
```

*After confirming*, the agent starts a watcher thread; new screenshots are renamed automatically.

---

### 2 · Creating an LLM‑Powered Thought (email drafting)

```
user > create a thought DraftEmail that uses gpt‑4o to write a polite reply when I paste any incoming email text.

agent > ✓ Thought `DraftEmail` generated. It calls openai.ChatCompletion with a predefined system prompt.
agent > API key detected. Ready to run. Activate? (yes/no)
```

Once activated, you can pipe an email body to the agent; it stores the draft in `~/Drafts/`.

---

### 3 · Composing Complex Workflows

```
user > plan: when a new PDF appears in ~/Downloads, 1) extract text, 2) summarise with DraftSummary (LLM), 3) email me the summary via SendMail.

agent > Generated composite thought `AutoPDFDigest` linking:
    • FileWatcher  → PDFTextExtractor → DraftSummary → SendMail
agent > Schedule set to run every 10 min.
```

---

## Roadmap

* [ ] Robust dependency graph & caching
* [ ] GUI inspector for live thought graphs
* [ ] Policy sandboxing (restrict destructive commands)
* [ ] Plugin system for community thoughts

### Contributing

Pull requests and idea tickets are welcome! Given the experimental nature, please open an issue before large changes.

### License

This project is released under the **MIT License** unless noted otherwise.

---

## Disclaimer

This codebase is a research sandbox. **Use at your own risk.** The authors are not liable for unintended actions triggered by autonomous thoughts.
