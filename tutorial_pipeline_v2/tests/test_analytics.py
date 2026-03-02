"""Tests for analytics calculations."""

from core.analytics_engine import calculate_revenue_estimate


def test_revenue_calculation() -> None:
    """Revenue estimate should use configured platform proxies."""
    analytics = {
        "by_platform": {
            "devto": {"estimated_reads": 1000, "estimated_revenue": 0.0},
            "hashnode": {"estimated_reads": 500, "estimated_revenue": 0.0},
            "blogger": {"visits": 400, "estimated_revenue": 0.0},
            "telegram": {"subscribers": 100, "estimated_revenue": 0.0},
        }
    }

    revenue = calculate_revenue_estimate(analytics)

    # 1000*0.02 + 500*0.015 + 400*0.03 + 100*0.02 = 41.5
    assert revenue == 41.5
