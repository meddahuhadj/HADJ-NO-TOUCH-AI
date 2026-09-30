import json
import urllib.request
from typing import Optional, Dict, Any
from intents.intent_definitions import IntentType, IntentResult
from intents.intent_recognizer import IntentRecognizer


class LocalAIAdapter:
    """
    Adapter for an optional Local LLM (e.g. Ollama localhost:11434 or llama.cpp server).
    Gracefully falls back to the deterministic Rule-Based IntentRecognizer if no local LLM is running.
    """

    def __init__(self, ollama_host: str = "http://127.0.0.1:11434"):
        self.ollama_host = ollama_host
        self.rule_engine = IntentRecognizer()
        self.is_llm_available = False
        self._check_availability()

    def _check_availability(self):
        try:
            req = urllib.request.Request(f"{self.ollama_host}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                if resp.status == 200:
                    self.is_llm_available = True
                    print("[LocalAIAdapter] Local LLM server detected (Ollama).")
        except Exception:
            self.is_llm_available = False

    def parse_with_fallback(self, natural_query: str) -> IntentResult:
        """
        Parses user query. If local LLM is reachable, tries LLM prompt; otherwise uses local rule engine.
        """
        # Always run deterministic rule engine first for fast zero-latency response
        rule_result = self.rule_engine.parse(natural_query)
        if rule_result.intent_type != IntentType.UNKNOWN:
            return rule_result

        # If rule engine couldn't understand and local LLM is available, query LLM
        if self.is_llm_available:
            llm_result = self._query_local_llm(natural_query)
            if llm_result:
                return llm_result

        return rule_result

    def _query_local_llm(self, query: str) -> Optional[IntentResult]:
        """Queries local Ollama endpoint."""
        prompt = (
            f"You are the intent parser for HADJ NO-TOUCH AI. "
            f"Convert this command: '{query}' into JSON: {{\"intent\": \"LAUNCH_APP\"|\"OPEN_FOLDER\"|\"VOLUME_UP\"..., \"target\": \"...\"}}. "
            f"Respond ONLY with valid JSON."
        )
        try:
            payload = json.dumps({
                "model": "qwen2.5:1.5b",
                "prompt": prompt,
                "stream": False,
                "format": "json"
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self.ollama_host}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                resp_json = json.loads(res_data.get("response", "{}"))
                intent_name = resp_json.get("intent", "UNKNOWN")
                target = resp_json.get("target")

                if hasattr(IntentType, intent_name):
                    return IntentResult(
                        intent_type=getattr(IntentType, intent_name),
                        target=target,
                        confidence=0.88,
                        original_text=query
                    )
        except Exception:
            pass

        return None
