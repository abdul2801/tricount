"""Flask routes."""
from flask import Blueprint, render_template, jsonify
from app.tricount_service import get_service

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Main dashboard page."""
    service = get_service()
    try:
        summary = service.get_summary()
        members = service.get_members()
        transactions = service.get_transactions()
        member_spending = service.get_member_spending()
        category_breakdown = service.get_category_breakdown()
        statistics = service.get_statistics()
        
        # Extract unique categories from transactions for filter
        categories = list(set(tx.get("category", "UNCATEGORIZED") for tx in transactions))
        categories.sort()
        
        monthly_spending = service.get_monthly_spending()

        return render_template(
            "dashboard.html",
            summary=summary,
            members=members,
            transactions=transactions,
            member_spending=member_spending,
            category_breakdown=category_breakdown,
            statistics=statistics,
            categories=categories,
            monthly_spending=monthly_spending,
        )
    except Exception as e:
        return render_template("error.html", error=str(e)), 500


@main_bp.route("/api/members")
def api_members():
    """API endpoint for members data."""
    try:
        service = get_service()
        members = service.get_members()
        return jsonify(members)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@main_bp.route("/api/transactions")
def api_transactions():
    """API endpoint for transactions data."""
    try:
        service = get_service()
        transactions = service.get_transactions()
        return jsonify(transactions)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@main_bp.route("/api/summary")
def api_summary():
    """API endpoint for tricount summary."""
    try:
        service = get_service()
        summary = service.get_summary()
        return jsonify(summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@main_bp.route("/api/analytics")
def api_analytics():
    """API endpoint for analytics data."""
    try:
        service = get_service()
        return jsonify({
            "member_spending": service.get_member_spending(),
            "category_breakdown": service.get_category_breakdown(),
            "statistics": service.get_statistics(),
            "monthly_spending": service.get_monthly_spending(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@main_bp.route("/api/cache/clear", methods=["POST"])
def api_cache_clear():
    """Clear the cache and force a fresh fetch on next request."""
    try:
        get_service().clear_cache()
        return jsonify({"ok": True, "message": "Cache cleared"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
