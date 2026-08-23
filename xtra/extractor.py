import os
import re
import json
from abc import ABC, abstractmethod
from typing import List, Optional
import httpx
from xtra.models import ExtractedIngredient

class ExtractionError(Exception):
    """Raised when ingredient extraction fails."""
    pass

class BaseIngredientExtractor(ABC):
    """Abstract interface for extracting structured ingredients from recipe text."""

    @abstractmethod
    async def extract(self, ingredients_text: str) -> List[ExtractedIngredient]:
        """Extract structured ingredients from the given recipe text.

        Args:
            ingredients_text: Raw ingredients text from the recipe.

        Returns:
            List of structured ExtractedIngredient instances.

        Raises:
            ExtractionError: If extraction cannot be completed.
        """
        pass

class LLMIngredientExtractor(BaseIngredientExtractor):
    """Extracts structured culinary ingredients using an LLM (Ollama or OpenAI-compatible endpoint)."""

    DEFAULT_HOST = "http://localhost:11434"
    DEFAULT_MODEL = "qwen2.5:3b"
    DEFAULT_TIMEOUT = 180.0

    def __init__(
        self,
        host: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        http_client: Optional[httpx.AsyncClient] = None
    ):
        raw_host = host or os.environ.get("OLLAMA_HOST") or os.environ.get("LLM_BASE_URL") or self.DEFAULT_HOST
        self.host = raw_host.rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL") or os.environ.get("LLM_MODEL") or self.DEFAULT_MODEL
        env_timeout = os.environ.get("OLLAMA_TIMEOUT") or os.environ.get("LLM_TIMEOUT")
        self.timeout = timeout if timeout is not None else (float(env_timeout) if env_timeout else self.DEFAULT_TIMEOUT)
        self._external_client = http_client

    @property
    def is_openai_compat(self) -> bool:
        return self.host.endswith("/v1")

    @property
    def endpoint(self) -> str:
        if self.is_openai_compat:
            return f"{self.host}/chat/completions"
        return f"{self.host}/api/chat"

    def _build_prompt(self, ingredients_text: str) -> str:
        return (
            "Extract culinary ingredients from the following recipe text. "
            "Return ONLY a JSON array of objects where each object has:\n"
            "- 'name': clean, normalized base ingredient name in Dutch suitable for supermarket search (e.g. 'prei', 'kroketten', 'witte kool', 'bloem', 'boter'). "
            "IMPORTANT: Strip all descriptions, preparation methods, states, and parenthetical text (e.g. 'Prei (het wit van prei)' -> 'prei', 'Kroketjes (diepvries)' -> 'kroketten', 'rode ui, gesnipperd' -> 'rode ui'). "
            "Translate English to Dutch.\n"
            "- 'quantity': the numerical quantity (e.g. 250, 0.5, 2) or null if not specified.\n"
            "- 'unit': the quantity unit (e.g. 'g', 'kg', 'ml', 'l', 'el', 'tl', 'stuk', 'teentje') or null if not specified.\n\n"
            "Rules:\n"
            "- If multiple ingredients are combined on one line (e.g. 'peper en zout' or 'tijm, laurier, bieslook, boter'), split them into separate objects.\n"
            "- Ignore non-ingredient notes, tips, and commentary (e.g. 'Cocktail tip', 'naar smaak').\n\n"
            "Example output:\n"
            "[\n"
            '  {"name": "kipfilet", "quantity": 300, "unit": "g"},\n'
            '  {"name": "prei", "quantity": 0.25, "unit": "stuk"},\n'
            '  {"name": "kroketten", "quantity": null, "unit": null},\n'
            '  {"name": "zout", "quantity": null, "unit": null}\n'
            "]\n\n"
            f"Recipe ingredients text:\n{ingredients_text}"
        )

    async def _send_request(self, client: httpx.AsyncClient, prompt: str) -> str:
        system_msg = "You are a culinary ingredient extraction assistant. Output only a valid JSON array of objects."
        
        if self.is_openai_compat:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1
            }
            resp = await client.post(self.endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        else:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {"temperature": 0.1}
            }
            resp = await client.post(self.endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")

    def _parse_response(self, content: str) -> List[ExtractedIngredient]:
        json_match = re.search(r"\[.*?\]", content, re.DOTALL)
        if not json_match:
            raise ExtractionError(f"LLM did not return a valid JSON array. Output was: {content}")

        try:
            parsed = json.loads(json_match.group(0))
        except json.JSONDecodeError as e:
            raise ExtractionError(f"Failed to decode JSON from LLM response: {content}") from e

        if not isinstance(parsed, list):
            raise ExtractionError(f"Expected JSON array from LLM, got: {type(parsed)}")

        results: List[ExtractedIngredient] = []
        for item in parsed:
            if isinstance(item, dict) and item.get("name"):
                results.append(ExtractedIngredient(
                    name=str(item["name"]).strip(),
                    quantity=item.get("quantity"),
                    unit=item.get("unit")
                ))
            elif isinstance(item, str) and item.strip():
                results.append(ExtractedIngredient(
                    name=item.strip(),
                    quantity=None,
                    unit=None
                ))

        return results

    async def extract(self, ingredients_text: str) -> List[ExtractedIngredient]:
        if not ingredients_text.strip():
            return []

        prompt = self._build_prompt(ingredients_text)

        try:
            if self._external_client:
                content = await self._send_request(self._external_client, prompt)
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    content = await self._send_request(client, prompt)
        except ExtractionError:
            raise
        except Exception as e:
            raise ExtractionError(f"Failed to query LLM for ingredient extraction at {self.endpoint}: {e}") from e

        return self._parse_response(content)

# Default alias
IngredientExtractor = LLMIngredientExtractor
