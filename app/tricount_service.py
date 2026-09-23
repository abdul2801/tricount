"""Service to fetch and cache Tricount data."""
import time
import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict
from tricount import load_client
from dataclasses import asdict
from config import CREDENTIALS_PATH, TRICOUNT_ID, CACHE_TTL

logger = logging.getLogger(__name__)


class TricountService:
    """Service to interact with Tricount API."""
    
    def __init__(self):
        """Initialize the service with client and cache."""
        self.client = load_client(str(CREDENTIALS_PATH))
        self.tricount = self.client.join_tricount(TRICOUNT_ID)
        self._cache = {}
        self._cache_times = {}
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache entry is still valid."""
        if key not in self._cache_times:
            return False
        is_valid = time.time() - self._cache_times[key] < CACHE_TTL
        if is_valid:
            logger.debug(f"Cache HIT for {key}")
        else:
            logger.debug(f"Cache EXPIRED for {key}")
        return is_valid
    
    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached value if valid."""
        if self._is_cache_valid(key):
            return self._cache[key]
        return None
    
    def _set_cache(self, key: str, value: Any) -> None:
        """Set cache with timestamp."""
        self._cache[key] = value
        self._cache_times[key] = time.time()
        logger.debug(f"Cached {key} for {CACHE_TTL}s")
    
    def get_members(self) -> List[Dict[str, Any]]:
        """Get all members in the tricount."""
        cached = self._get_cached("members")
        if cached is not None:
            return cached
        
        members = self.tricount.members
        result = [
            {
                "id": m.id,
                "uuid": m.uuid,
                "name": m.display_name,
                "status": m.status,
            }
            for m in members
        ]
        self._set_cache("members", result)
        return result
    
    def get_transactions(self) -> List[Dict[str, Any]]:
        """Get all transactions in the tricount."""
        cached = self._get_cached("transactions")
        if cached is not None:
            return cached
        
        transactions = self.tricount.transactions
        result = []
        
        # Emoji mapping for categories
        category_emoji = {
            "FOOD": "🍽️",
            "HOUSING": "🏠",
            "ENTERTAINMENT": "🎮",
            "TRANSPORT": "🚗",
            "SHOPPING": "🛍️",
            "UTILITIES": "💡",
            "GENERAL": "💸",
            "UNCATEGORIZED": "📝",
        }
        
        for tx in transactions:
            # Get payer (who paid - negative amount in allocations)
            payer_name = "Unknown"
            
            # Find who paid by looking for negative amount in allocations
            if hasattr(tx, 'allocations') and tx.allocations:
                for allocation in tx.allocations:
                    if allocation.amount.as_float < 0:  # Payer has negative amount
                        member = self.tricount.get_member_by_uuid(allocation.membership_uuid)
                        if member:
                            payer_name = member.display_name
                            break
            
            # Get all allocations (who it was split between)
            allocations = []
            if hasattr(tx, 'allocations') and tx.allocations:
                for allocation in tx.allocations:
                    member = self.tricount.get_member_by_uuid(allocation.membership_uuid)
                    member_name = member.display_name if member else "Unknown"
                    amount = abs(allocation.amount.as_float)
                    if amount > 0:  # Only include positive amounts (who it was for)
                        allocations.append({
                            "member": member_name,
                            "amount": amount,
                        })
            
            emoji = category_emoji.get(tx.category, "💸")
            
            tx_dict = {
                "id": tx.id,
                "uuid": tx.uuid,
                "amount": abs(tx.amount.as_float),
                "currency": tx.amount.currency,
                "description": tx.description,
                "category": tx.category,
                "emoji": emoji,
                "date": str(tx.date)[:10],  # normalize to YYYY-MM-DD
                "payer": payer_name,
                "allocations": allocations,
            }
            
            result.append(tx_dict)
        
        # Sort by date descending (newest first)
        result.sort(key=lambda x: x["date"], reverse=True)
        self._set_cache("transactions", result)
        return result
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of the tricount."""
        return {
            "title": self.tricount.title,
            "id": self.tricount.id,
            "currency": self.tricount.currency,
            "category": self.tricount.category,
            "is_archived": self.tricount.is_archived,
            "member_count": len(self.get_members()),
            "transaction_count": len(self.get_transactions()),
        }
    
    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        self._cache_times.clear()


    def get_member_spending(self) -> List[Dict[str, Any]]:
        """Get total spending per member."""
        cached = self._get_cached("member_spending")
        if cached is not None:
            return cached
        
        spending = defaultdict(float)
        for tx in self.tricount.transactions:
            amount = abs(tx.amount.as_float)
            # Add spending for each person who paid
            owner = self.tricount.get_member_by_uuid(tx.membership_uuid_owner)
            if owner:
                spending[owner.display_name] += amount
        
        result = [
            {"name": name, "amount": amount}
            for name, amount in sorted(spending.items(), key=lambda x: x[1], reverse=True)
        ]
        self._set_cache("member_spending", result)
        return result
    
    def get_category_breakdown(self) -> List[Dict[str, Any]]:
        """Get spending breakdown by category."""
        cached = self._get_cached("category_breakdown")
        if cached is not None:
            return cached
        
        category_map = {
            "TRAVEL": "🛏 Travel",
            "ENTERTAINMENT": "🎤 Entertainment",
            "GROCERIES": "🛒 Groceries",
            "HEALTHCARE": "🦷 Healthcare",
            "INSURANCE": "🧯 Insurance",
            "RENT_AND_UTILITIES": "🏠 Rent & Utilities",
            "FOOD_AND_DRINK": "🍔 Food & Drink",
            "SHOPPING": "🛍 Shopping",
            "TRANSPORT": "🚕 Transport",
            "OTHER": "✋ Other",
            "UNCATEGORIZED": "📝 Uncategorized",
        }
        
        spending = defaultdict(float)
        for tx in self.tricount.transactions:
            amount = abs(tx.amount.as_float)
            category = tx.category or "UNCATEGORIZED"
            spending[category] += amount
        
        result = [
            {
                "name": category_map.get(cat, cat),
                "amount": amount,
                "category": cat,
            }
            for cat, amount in sorted(spending.items(), key=lambda x: x[1], reverse=True)
        ]
        self._set_cache("category_breakdown", result)
        return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get various statistics about the tricount."""
        cached = self._get_cached("statistics")
        if cached is not None:
            return cached
        
        transactions = self.tricount.transactions
        if not transactions:
            return {
                "total_spent": 0,
                "average_transaction": 0,
                "largest_transaction": 0,
                "number_of_transactions": 0,
            }
        
        amounts = [abs(tx.amount.as_float) for tx in transactions]
        
        result = {
            "total_spent": sum(amounts),
            "average_transaction": sum(amounts) / len(amounts) if amounts else 0,
            "largest_transaction": max(amounts) if amounts else 0,
            "number_of_transactions": len(amounts),
        }
        self._set_cache("statistics", result)
        return result


    def get_monthly_spending(self) -> List[Dict[str, Any]]:
        """Get total spending per month (last 12 months), sorted oldest→newest."""
        cached = self._get_cached("monthly_spending")
        if cached is not None:
            return cached

        from collections import defaultdict
        monthly = defaultdict(float)

        for tx in self.tricount.transactions:
            # tx.date may be a date object or an ISO string like "2026-03-15"
            date = tx.date
            if isinstance(date, str):
                key = date[:7]  # "YYYY-MM"
            else:
                key = f"{date.year}-{date.month:02d}"
            monthly[key] += abs(tx.amount.as_float)

        # Sort and take last 12 months
        sorted_months = sorted(monthly.items())[-12:]

        result = [{"month": k, "amount": round(v, 2)} for k, v in sorted_months]
        self._set_cache("monthly_spending", result)
        return result


# Singleton instance
_service = None


def get_service() -> TricountService:
    """Get or create the service instance."""
    global _service
    if _service is None:
        _service = TricountService()
    return _service
