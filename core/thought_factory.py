import json, types, pathlib, sys, textwrap, asyncio, fnmatch, io, contextlib
from core.base_thought import BaseThought
from core.base_brain import BaseBrain

class ThoughtFactory:
    """
    * loads every thought*.json
    * hot-reloads on change
    * injects a ready-made BaseBrain into the thought's state as   state["__llm"]
    """
    def __init__(self, dir="thoughts"):
        self.dir = pathlib.Path(dir)
        self.reg = {}
        # profile-specific thought patterns:   cid → [glob, …]
        self.patterns = {}
        self._load_all()
        asyncio.create_task(self._watch())

    # ---------- loading ----------------------------------------------------
    def _safe_exec(self, src: str, mod_name: str):
        mod = types.ModuleType(mod_name)
        exec(compile(textwrap.dedent(src), mod_name, "exec"), mod.__dict__, mod.__dict__)
        sys.modules[mod_name] = mod
        return mod


    def _load_all(self):
        """
        Find every   thoughts/<thought_name>/thought.json   (any depth)
        and load/compile it.
        """
        for p in self.dir.rglob("thought.json"):          # <── changed
            self._load(p)

    async def _watch(self):
        """
        Hot-reload thought folders.  Walk through every thought.json once per second
        and reload those whose mtime changed.
        """
        stamp = {p: p.stat().st_mtime for p in self.dir.rglob("thought.json")}
        while True:
            await asyncio.sleep(1)
            for p in self.dir.rglob("thought.json"):
                m = p.stat().st_mtime
                if m != stamp.get(p):
                    print(f"[factory] reload {p}")
                    self._load(p)
                    stamp[p] = m


    def _load(self, path: pathlib.Path):
        folder = path.parent                          # thoughts/<n>/
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"[factory] skipping invalid JSON in {path}")
            return
        except UnicodeDecodeError:
            print(f"[factory] skipping file with encoding issues in {path}")
            return

        # ---------------------------------------------------------------- code
        code_path = folder / "code.py"
        code_src  = code_path.read_text(encoding="utf-8")
        mod       = self._safe_exec(code_src, f"thought_{spec['name']}")

        # ---------------------------------------------------------------- prompt
        prompt_path = folder / "prompt.txt"
        prompt_txt  = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else None

        # ---------------------------------------------------------------- model settings
        model = spec.get("model", "gpt-4o-mini")
        temp  = spec.get("temperature", 0.7)

        async def _runner(state, **kw):
            state["__llm"]    = BaseBrain(model, temp)
            state["__prompt"] = prompt_txt

            # ── capture anything the thought prints ──────────────────────────
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                res = await mod.run(state, **kw)

            logs = buf.getvalue()
            if logs:
                if not isinstance(res, dict):
                    res = {}
                # stash logs so the Executor can forward them
                res["__logs"] = logs
            return res

        self.reg[spec["name"]] = BaseThought(
            spec["name"],
            _runner,
            spec.get("inputs", []),
            spec.get("outputs", []),
            spec.get("description", "")
        )


    # ---------- public helpers --------------------------------------------
    async def run(self, name: str, state: dict, **kw):
        return await self.reg[name].run(state, **kw)

    # ---------- profile filtering -------------------------------
    def set_pattern(self, cid: str, patterns):
        """Restrict visible thoughts for a conversation id."""
        if isinstance(patterns, str):
            patterns = [patterns]
        self.patterns[cid] = patterns or ["*"]

    def _filter(self, cid: str | None, names):
        if cid is None or cid not in self.patterns:
            return names
        pats = self.patterns[cid]
        return [n for n in names if any(fnmatch.fnmatch(n, p) for p in pats)]

    def catalogue(self, cid: str | None = None, group: str | None = None):
        """Return list of thoughts visible in this conversation."""
        names = list(self.reg.keys())
        names = self._filter(cid, names)
        if group == "dev":
            names = [n for n in names if n.startswith("dev_")]
        return names

    def describe(self, cid: str | None = None, group: str | None = None):
        return [{"name": n, "desc": self.reg[n].desc}
                for n in self.catalogue(cid, group)]
