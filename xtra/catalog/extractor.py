import re
from typing import List, Optional, Tuple, Dict
from xtra.sdk.models import ExtractedIngredient, Product


def extract_ingredients_section(markdown_text: str) -> str:
    """Extracts the raw ingredients section from markdown recipe text."""
    pattern = r"(?:^|\n)##\s*(?:🛒\s*)?(?:Ingredients|Ingrediënten)\b(.*?)(?=\n##|\Z)"
    match = re.search(pattern, markdown_text, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return match.group(1).strip()


def parse_recipe_ingredients(markdown_text: str) -> List[ExtractedIngredient]:
    """Parses individual ingredients from the recipe's ingredients section."""
    section_text = extract_ingredients_section(markdown_text)
    if not section_text:
        return []

    results: List[ExtractedIngredient] = []
    lines = section_text.splitlines()

    for line in lines:
        line = line.strip()
        if not line or not (line.startswith("-") or line.startswith("*")):
            continue

        item_str = line.lstrip("-* ").strip()
        # Remove markdown bold/italics
        item_str = re.sub(r"\*\*([^*]+)\*\*", r"\1", item_str)
        item_str = re.sub(r"\*([^*]+)\*", r"\1", item_str)

        # Handle category prefixes like "Eiwit: 3 kipfilets"
        if ":" in item_str:
            parts = item_str.split(":", 1)
            left = parts[0].strip()
            right = parts[1].strip()

            # Case: "- : 1 sjalotten"
            if not left and right:
                parsed = _parse_quantity_and_name(right)
                if parsed:
                    results.append(parsed)
                continue

            # Case: "- gehakt: 75 g" vs "- Groenten: 1 paprika, 1 courgette"
            # If left contains multiple words with commas, e.g. "Tijm, laurier, bieslook: 10 g"
            if "," in left:
                sub_items = [s.strip() for s in left.split(",") if s.strip()]
                for s in sub_items:
                    results.append(ExtractedIngredient(name=s, quantity=right or None, unit=None))
                continue

            # Normal "- ingredient: quantity"
            parsed_qty = right if right else None
            results.append(ExtractedIngredient(name=left, quantity=parsed_qty, unit=None))
        else:
            # Lines without colons: "- 200g bloem" or "- zout"
            parsed = _parse_quantity_and_name(item_str)
            if parsed:
                results.append(parsed)
            else:
                results.append(ExtractedIngredient(name=item_str, quantity=None, unit=None))

    return results


def _parse_quantity_and_name(text: str) -> Optional[ExtractedIngredient]:
    """Heuristic helper to split '100 g bloem' into quantity and name."""
    text = text.strip()
    if not text:
        return None

    # Match numeric quantity and optional unit at start: e.g. "0.25 kg bloem" or "2 eieren"
    match = re.match(r"^([\d.,]+)\s*([a-zA-Z]+)?\s+(.+)$", text)
    if match:
        qty_str, unit_str, name_str = match.groups()
        try:
            qty = float(qty_str.replace(",", "."))
            if qty.is_integer():
                qty = int(qty)
        except ValueError:
            qty = qty_str
        return ExtractedIngredient(name=name_str.strip(), quantity=qty, unit=unit_str)

    return ExtractedIngredient(name=text, quantity=None, unit=None)


def extract_resolved_products(markdown_text: str) -> List[Dict[str, str]]:
    """Extracts existing entries from ## Resolved Products.

    Returns a list of dicts with keys: 'raw_line', 'ingredient', 'amount', 'productId'.
    """
    pattern = r"(?:^|\n)##\s*Resolved Products\b(.*?)(?=\n##|\Z)"
    match = re.search(pattern, markdown_text, re.IGNORECASE | re.DOTALL)
    if not match:
        return []

    section_text = match.group(1).strip()
    resolved = []
    line_pattern = r"^[-*]\s*(.+?)(?:\s*\(([^)]+)\))?\s*\[productId=([a-zA-Z0-9_-]+)\]"

    for line in section_text.splitlines():
        line = line.strip()
        m = re.match(line_pattern, line)
        if m:
            ing_name = m.group(1).strip()
            amount = m.group(2).strip() if m.group(2) else None
            pid = m.group(3).strip()
            resolved.append({
                "raw_line": line,
                "ingredient": ing_name,
                "amount": amount,
                "productId": pid,
            })
    return resolved


def format_ingredient_label(ingredient: ExtractedIngredient) -> str:
    """Format ingredient name with quantity for display/markdown."""
    name = ingredient.name
    qty = ingredient.quantity
    unit = ingredient.unit

    if qty is not None:
        if unit:
            return f"{name} ({qty} {unit})"
        return f"{name} ({qty})"
    return name


def format_resolved_products_list(
    items: List[Tuple[ExtractedIngredient, str]]
) -> str:
    """Formats tuples of (ingredient, product_id) into standard markdown list."""
    lines = []
    for ing, pid in items:
        label = format_ingredient_label(ing)
        lines.append(f"- {label} [productId={pid}]")
    return "\n".join(lines)


def append_or_update_recipe_section(
    markdown_text: str,
    section_title: str,
    section_body: str
) -> str:
    """Appends or replaces a Markdown section (e.g., 'Resolved Products')."""
    pattern = rf"(##\s*{re.escape(section_title)}\b)(.*?)(?=\n##|\Z)"
    new_section = f"## {section_title}\n{section_body.strip()}\n"

    if re.search(pattern, markdown_text, re.DOTALL):
        updated = re.sub(pattern, new_section.rstrip(), markdown_text, flags=re.DOTALL)
        return updated.strip() + "\n"
    else:
        # Append before footnotes or at end of file
        cleaned = markdown_text.rstrip()
        return f"{cleaned}\n\n{new_section}"


class ExtractionError(Exception):
    """Raised when ingredient extraction fails."""
    pass


class BaseIngredientExtractor:
    """Abstract interface for extracting structured ingredients from recipe text."""
    async def extract(self, ingredients_text: str) -> List[ExtractedIngredient]:
        raise NotImplementedError


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
        http_client: Optional[object] = None
    ):
        import os
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

    async def _send_request(self, client: object, prompt: str) -> str:
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
        import json
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
        import httpx
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


IngredientExtractor = LLMIngredientExtractor

