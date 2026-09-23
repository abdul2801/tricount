"""Service to fetch and cache Tricount data."""
import time
import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict
from tricount import load_client
from config import CREDENTIALS_PATH, TRICOUNT_ID, CACHE_TTL

logger = logging.getLogger(__name__)

CATEGORY_MAP = {
    "TRAVEL":            "✈️ Travel",
    "ENTERTAINMENT":     "🎮 Entertainment",
    "GROCERIES":         "🛒 Groceries",
    "HEALTHCARE":        "🏥 Healthcare",
    "INSURANCE":         "🧯 Insurance",
    "RENT_AND_UTILITIES":"🏠 Rent & Utilities",
    "FOOD_AND_DRINK":    "🍔 Food & Drink",
    "SHOPPING":          "🛍️ Shopping",
    "TRANSPORT":         "🚕 Transport",
    "OTHER":             "✋ Other",
    "UNCATEGORIZED":     "📝 Uncategorized",
    "FOOD":              "🍽️ Food",
    "HOUSING":           "🏠 Housing",
    "GENERAL":           "💸 General",
    "UTILITIES":         "💡 Utilities",
}

CATEGORY_EMOJI = {
    "FOOD": "🍽️", "FOOD_AND_DRINK": "🍔", "HOUSING": "🏠",
    "ENTERTAINMENT": "🎮", "TRANSPORT": "🚕", "SHOPPING": "🛍️",
    "UTILITIES": "💡", "TRAVEL": "✈️", "GROCERIES": "🛒",
    "HEALTHCARE": "🏥", "GENERAL": "💸", "UNCATEGORIZED": "📝",
    "RENT_AND_UTILITIES": "🏠", "OTHER": "✋", "INSURANCE": "🧯",
}


class TricountService:
    """Service to interact with Tricount API with TTL caching."""

    def __init__(self):
        self.client   = load_client(str(CREDENTIALS_PATH))
        self.tricount = self.client.join_tricount(TRICOUNT_ID)
        self._cache:       Dict[str, Any]   = {}
        self._cache_times: Dict[str, float] = {}

    # ── Cache helpers ─────────────────────────────────────────────────────────

    def _get(self, key: str) -> Optional[Any]:
        if key in self._cache_times and time.time() - self._cache_times[key] < CACHE_TTL:
            logger.debug("Cache HIT: %s", key)
            return self._cache[key]
        logger.debug("Cache MISS: %s", key)
        return None

    def _set(self, key: str, value: Any) -> Any:
        self._cache[key]       = value
        self._cache_times[key] = time.time()
        return value

    def clear_cache(self) -> None:
        self._cache.clear()
        self._cache_times.clear()
        # Re-join the tricount so the transaction list is fetched fresh from the API
        self.tricount = self.client.join_tricount(TRICOUNT_ID)
        logger.info("Cache cleared and tricount re-fetched")

    # ── Raw transactions (source of truth) ───────────────────────────────────

    def get_transactions(self) -> List[Dict[str, Any]]:
        cached = self._get("transactions")
        if cached is not None:
            return cached

        # Re-join to get latest data from the API
        self.tricount = self.client.join_tricount(TRICOUNT_ID)

        result = []
        for tx in self.tricount.transactions:
            # Payer is always the owner of the transaction
            owner  = self.tricount.get_member_by_uuid(tx.membership_uuid_owner)
            payer_name = owner.display_name if owner else "Unknown"

            # Allocations — everyone's share (raw amounts are negative, take abs)
            allocations = []
            if hasattr(tx, "allocations") and tx.allocations:
                for alloc in tx.allocations:
                    member = self.tricount.get_member_by_uuid(alloc.membership_uuid)
                    name   = member.display_name if member else "Unknown"
                    amt    = abs(alloc.amount.as_float)
                    if amt > 0:
                        allocations.append({"member": name, "amount": amt})

            result.append({
                "id":          tx.id,
                "uuid":        tx.uuid,
                "amount":      abs(tx.amount.as_float),
                "currency":    tx.amount.currency,
                "description": tx.description,
                "category":    tx.category or "UNCATEGORIZED",
                "emoji":       CATEGORY_EMOJI.get(tx.category, "💸"),
                "date":        str(tx.date)[:10],
                "payer":       payer_name,
                "allocations": allocations,
            })

        result.sort(key=lambda x: x["date"], reverse=True)
        return self._set("transactions", result)

    # ── Derived — all computed from cached transactions ───────────────────────

    def get_members(self) -> List[Dict[str, Any]]:
        cached = self._get("members")
        if cached is not None:
            return cached
        result = [
            {"id": m.id, "uuid": m.uuid, "name": m.display_name, "status": m.status}
            for m in self.tricount.members
        ]
        return self._set("members", result)

    def get_member_spending(self) -> List[Dict[str, Any]]:
        cached = self._get("member_spending")
        if cached is not None:
            return cached

        spending: Dict[str, float] = defaultdict(float)
        for tx in self.get_transactions():          # use cached transactions
            spending[tx["payer"]] += tx["amount"]

        result = [
            {"name": name, "amount": round(amt, 2)}
            for name, amt in sorted(spending.items(), key=lambda x: x[1], reverse=True)
        ]
        return self._set("member_spending", result)

    def get_category_breakdown(self) -> List[Dict[str, Any]]:
        cached = self._get("category_breakdown")
        if cached is not None:
            return cached

        spending: Dict[str, float] = defaultdict(float)
        for tx in self.get_transactions():          # use cached transactions
            spending[tx["category"]] += tx["amount"]

        result = [
            {
                "name":     CATEGORY_MAP.get(cat, cat.replace("_", " ").title()),
                "amount":   round(amt, 2),
                "category": cat,
            }
            for cat, amt in sorted(spending.items(), key=lambda x: x[1], reverse=True)
        ]
        return self._set("category_breakdown", result)

    def get_statistics(self) -> Dict[str, Any]:
        cached = self._get("statistics")
        if cached is not None:
            return cached

        txs = self.get_transactions()               # use cached transactions
        if not txs:
            return self._set("statistics", {
                "total_spent": 0, "average_transaction": 0,
                "largest_transaction": 0, "number_of_transactions": 0,
            })

        amounts = [t["amount"] for t in txs]
        return self._set("statistics", {
            "total_spent":          round(sum(amounts), 2),
            "average_transaction":  round(sum(amounts) / len(amounts), 2),
            "largest_transaction":  round(max(amounts), 2),
            "number_of_transactions": len(amounts),
        })

    def get_monthly_spending(self) -> List[Dict[str, Any]]:
        cached = self._get("monthly_spending")
        if cached is not None:
            return cached

        monthly: Dict[str, float] = defaultdict(float)
        for tx in self.get_transactions():          # use cached transactions
            monthly[tx["date"][:7]] += tx["amount"]

        result = [
            {"month": k, "amount": round(v, 2)}
            for k, v in sorted(monthly.items())[-12:]
        ]
        return self._set("monthly_spending", result)

    def get_summary(self) -> Dict[str, Any]:
        cached = self._get("summary")
        if cached is not None:
            return cached
        result = {
            "title":             self.tricount.title,
            "id":                self.tricount.id,
            "currency":          self.tricount.currency,
            "category":          self.tricount.category,
            "is_archived":       self.tricount.is_archived,
            "member_count":      len(self.get_members()),
            "transaction_count": len(self.get_transactions()),
        }
        return self._set("summary", result)


# ── Singleton ─────────────────────────────────────────────────────────────────

_service: Optional[TricountService] = None


def get_service() -> TricountService:
    global _service
    if _service is None:
        _service = TricountService()
    return _service
