"""v1: the rule-based microservice. Fixed logic, written by us:

  score = (interest in the product's category) * 100 + popularity
  interest = sum over the user's recent events in that category of
             3 per purchase, 2 per cart add, 1 per view

Products the user already bought are never recommended. A new user with no
events simply gets the most popular products. Same input, same answer.
"""

VERB = {"purchase": "bought", "cart": "added to cart", "view": "viewed"}


class RulesRecommender:
    name = "rules"

    def recommend(self, context, limit):
        def score(p):
            return context.category_scores.get(p["category"], 0) * 100 + p.get("popularity", 0)

        # highest score first; equal scores in id order, so the answer never changes
        ranked = sorted(context.available, key=lambda p: (-score(p), p["id"]))
        return [{"productId": p["id"], "reason": self._reason(context, p)} for p in ranked[:limit]]

    @staticmethod
    def _reason(context, product):
        for e in context.events:  # newest first
            seen = context.products.get(e["productId"])
            if seen and seen["category"] == product["category"]:
                return f"Popular in {product['category']}, like the {seen['name']} you {VERB[e['type']]}"
        return "Popular with all shoppers"
