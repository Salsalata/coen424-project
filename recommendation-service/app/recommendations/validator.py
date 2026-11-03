"""Correctness rules for a recommendation answer (our canary criteria table).

An AI agent can return a well-formed, confident, wrong answer with status 200
(lecture "Inference as a Utility", slide 15), so every answer is checked:

  1. every product id exists in the catalog;
  2. no product the user already bought;
  3. no duplicates;
  4. exactly `limit` items, or every remaining product if fewer exist;
  5. every item has a non-empty reason (the response schema requires it).
"""

from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    valid: bool
    problems: list = field(default_factory=list)


def validate_items(items, context, limit):
    problems = []
    ids = [item.get("productId") for item in items]

    unknown = [i for i in ids if i not in context.products]
    if unknown:
        problems.append(f"unknown product ids: {unknown}")
    bought = [i for i in ids if i in context.purchased]
    if bought:
        problems.append(f"already purchased: {bought}")
    if len(set(ids)) != len(ids):
        problems.append("duplicate product ids")
    expected = min(limit, len(context.available))
    if len(ids) != expected:
        problems.append(f"expected {expected} items, got {len(ids)}")
    if any(not isinstance(item.get("reason"), str) or not item["reason"].strip() for item in items):
        problems.append("every item needs a reason")
    return ValidationResult(valid=not problems, problems=problems)
