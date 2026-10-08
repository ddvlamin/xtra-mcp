import re
from typing import List, Optional, Union, Tuple, Any
from xtra.models import Product, ExtractedIngredient

def format_ingredient_label(item: Union[ExtractedIngredient, dict, str]) -> str:
    """Formats an ingredient object into a readable label with quantity and unit."""
    if isinstance(item, ExtractedIngredient):
        name = item.name
        qty = item.quantity
        unit = item.unit
    elif isinstance(item, dict):
        name = item.get("name", "")
        qty = item.get("quantity")
        unit = item.get("unit")
    else:
        return str(item)

    qty_str = ""
    if qty is not None and unit is not None:
        qty_str = f" ({qty} {unit})"
    elif qty is not None:
        qty_str = f" ({qty})"
    elif unit is not None:
        qty_str = f" ({unit})"

    return f"{name}{qty_str}"

def format_resolved_products_list(
    resolved_items: List[Tuple[ExtractedIngredient, Product]]
) -> str:
    """Formats resolved products into markdown bullet list items with [productId=...]."""
    lines = []
    for ing, prod in resolved_items:
        label = format_ingredient_label(ing)
        lines.append(f"- {label} [productId={prod.product_id}]")
    return "\n".join(lines)

def append_or_update_recipe_section(
    recipe_content: str,
    section_title: str,
    section_body: str
) -> str:
    """Appends or cleanly updates a markdown section in recipe content."""
    pattern = rf"##\s*{re.escape(section_title)}\s*\n.*?(?=\n##|\Z)"
    new_section = f"## {section_title}\n{section_body.strip()}\n"
    if re.search(pattern, recipe_content, flags=re.DOTALL):
        return re.sub(pattern, new_section.strip(), recipe_content, flags=re.DOTALL).rstrip() + "\n"
    else:
        trimmed = recipe_content.rstrip()
        return f"{trimmed}\n\n{new_section}"

def format_ambiguous_options_markdown(
    ingredient: str,
    query: str,
    options: List[Any],
    has_more: bool = False,
    next_offset: Optional[int] = None
) -> str:
    """Formats ambiguous options into a numbered markdown list with category and Next page option."""
    lines = [f"Ambiguous ingredient '{ingredient}' (query: '{query}'). Options:"]
    for i, opt in enumerate(options, 1):
        name = opt.get("name") if isinstance(opt, dict) else opt.name
        brand = opt.get("brand") if isinstance(opt, dict) else opt.brand
        pid = opt.get("product_id") if isinstance(opt, dict) else opt.product_id
        top_cat = opt.get("top_category_name") if isinstance(opt, dict) else getattr(opt, "top_category_name", None)
        brand_str = f" [{brand}]" if brand else ""
        cat_str = f" - {top_cat}" if top_cat else ""
        lines.append(f"{i}. {name}{brand_str} ({pid}){cat_str}")
    if has_more:
        next_hint = f" (offset {next_offset})" if next_offset is not None else ""
        lines.append(f"{len(options) + 1}. Next page{next_hint} (see more options)")
    return "\n".join(lines)


def format_session_progress_presentation(
    session: Any,
    active_item: Optional[Any],
    limit: int = 5
) -> str:
    """Formats a clean, focused single-ingredient progress presentation for interactive sessions."""
    if session.is_completed:
        lines = [
            f"🎉 All ingredients resolved ({session.resolved_count}/{session.total_count}):",
            ""
        ]
        for item in session.ingredients:
            prod_name = item.resolved_product.name if item.resolved_product else "Unknown"
            pid = item.resolved_product.product_id if item.resolved_product else ""
            lines.append(f"✅ {item.name} -> {prod_name} ({pid})")
        return "\n".join(lines)

    if not active_item:
        return "No active ingredient awaiting selection."

    idx = session.get_active_item_index() or 0
    step_num = idx + 1
    total = session.total_count

    paged = active_item.candidate_products[active_item.current_offset : active_item.current_offset + limit]
    has_more = (active_item.current_offset + limit) < len(active_item.candidate_products)
    next_offset = active_item.current_offset + limit if has_more else None

    lines = [
        f"[{step_num}/{total}] Finding: {active_item.name} (query: '{active_item.query}')",
        ""
    ]

    if not paged:
        lines.append("No matching products found in catalog.")
        lines.append("Please specify a custom search query or product ID.")
    else:
        for i, prod in enumerate(paged, 1):
            brand_str = f" [{prod.brand}]" if prod.brand else ""
            cat_str = f" - {prod.top_category_name}" if prod.top_category_name else ""
            lines.append(f"{i}. {prod.name}{brand_str} ({prod.product_id}){cat_str}")

        if has_more:
            lines.append(f"{len(paged) + 1}. Next page (offset {next_offset}) (see more options)")

        lines.append("")
        lines.append(f"(Showing {active_item.current_offset + 1}–{active_item.current_offset + len(paged)} of {len(active_item.candidate_products)} options. Reply with a number, product ID, or request next page.)")

    return "\n".join(lines)
