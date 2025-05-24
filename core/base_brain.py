from openai import OpenAI
import os
from dotenv import load_dotenv

class BaseBrain:
    def __init__(self, model_name="gpt-4o-mini", temperature=0.7):
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model  = model_name
        self.temp   = temperature

    # internal
    def _call(self, messages, *, json_mode: bool):
        params = dict(model=self.model, temperature=self.temp)
        if json_mode:
            params["response_format"] = {"type": "json_object"}
        rsp = self.client.chat.completions.create(messages=messages, **params)
        return rsp.choices[0].message.content.strip()

    # helpers
    def generate_json(self, user_msg: str, system_prompt: str):
        msgs = [{"role": "system", "content": system_prompt},
                {"role": "user",   "content": "Respond only with a JSON object.\n\n" + user_msg}]
        return self._call(msgs, json_mode=True)

    def generate_text(self, user_msg: str, system_prompt: str):
        msgs = [{"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_msg}]
        return self._call(msgs, json_mode=False)

    # ------------------------------------------------------------------
    # Planner helper – used by code_planner, dev_planner, etc.
    # ------------------------------------------------------------------
    async def plan(self, query, *, system_prompt: str = ""):
        """
        Convenience wrapper: run the LLM in *JSON mode* and give back the
        parsed Python object, so planner thoughts can simply do

            plan = await llm.plan(payload)

        Without repeating json.dumps / json.loads every time.
        """
        import json

        # normalise input
        if not isinstance(query, str):
            query = json.dumps(query, ensure_ascii=False)

        # get raw JSON from the model…
        raw = self.generate_json(query, system_prompt=system_prompt)

        # …and return a Python object (or a safe fallback)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {
                "ok": False,
                "flow": None,
                "missing": [],
                "question": "Sorry – I produced invalid JSON. Could you rephrase?"
            }
