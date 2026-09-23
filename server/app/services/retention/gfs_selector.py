"""Calendar-Aware Grandfather-Father-Son (GFS) selector for RetroVault V5.

Selects recovery points to protect across Daily, Weekly, Monthly, and Yearly tiers
using calendar boundaries and timezone awareness.
"""

import datetime
from typing import Dict, List, Set, Tuple
from zoneinfo import ZoneInfo


class GFSSelector:
    """
    Evaluates a collection of RecoveryPoints against GFS retention rules.
    Assigns each RecoveryPoint to applicable tiers: Daily, Weekly, Monthly, Yearly, Keep-Last.
    """

    def __init__(
        self,
        keep_last: int = 10,
        daily_count: int = 7,
        weekly_count: int = 4,
        monthly_count: int = 12,
        yearly_count: int = 7,
        timezone_name: str = "UTC",
    ):
        self.keep_last = max(1, keep_last)
        self.daily_count = daily_count
        self.weekly_count = weekly_count
        self.monthly_count = monthly_count
        self.yearly_count = yearly_count
        try:
            self.tz = ZoneInfo(timezone_name)
        except Exception:
            self.tz = datetime.timezone.utc

    def _to_tz(self, dt: datetime.datetime) -> datetime.datetime:
        """Ensure datetime has timezone and is converted to target timezone."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(self.tz)

    def evaluate_points(
        self,
        recovery_points: List[any],
        now: datetime.datetime = None,
    ) -> Dict[int, Dict[str, any]]:
        """
        Evaluate a list of RecoveryPoint objects (ordered or unordered).
        Returns a mapping of rp.id -> {
            "keep": bool,
            "tier": str,  # 'MANUAL', 'NEWEST', 'KEEP_LAST', 'YEARLY', 'MONTHLY', 'WEEKLY', 'DAILY', or 'EXPIRED'
            "is_daily": bool,
            "is_weekly": bool,
            "is_monthly": bool,
            "is_yearly": bool,
            "reason": str,
        }
        """
        if not recovery_points:
            return {}

        now_dt = now or datetime.datetime.now(self.tz)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=self.tz)
        else:
            now_dt = now_dt.astimezone(self.tz)

        # Sort newest first
        sorted_points = sorted(
            recovery_points,
            key=lambda rp: rp.created_at if rp.created_at.tzinfo else rp.created_at.replace(tzinfo=datetime.timezone.utc),
            reverse=True,
        )

        results: Dict[int, Dict[str, any]] = {}
        for rp in sorted_points:
            results[rp.id] = {
                "keep": False,
                "tier": "EXPIRED",
                "is_daily": False,
                "is_weekly": False,
                "is_monthly": False,
                "is_yearly": False,
                "reason": "Retention window exceeded",
            }

        # Rule 1: Manual protection is absolute
        for rp in sorted_points:
            if getattr(rp, "is_manual_protected", False):
                results[rp.id]["keep"] = True
                results[rp.id]["tier"] = "MANUAL"
                results[rp.id]["reason"] = "Manually protected from expiration"

        # Rule 2: Single newest valid recovery point is ALWAYS kept unconditionally
        newest_rp = sorted_points[0]
        results[newest_rp.id]["keep"] = True
        if results[newest_rp.id]["tier"] == "EXPIRED":
            results[newest_rp.id]["tier"] = "NEWEST"
            results[newest_rp.id]["reason"] = "Latest recovery point protection"

        # Rule 3: Keep-Last N points
        keep_last_count = 0
        for rp in sorted_points:
            if keep_last_count < self.keep_last:
                results[rp.id]["keep"] = True
                if results[rp.id]["tier"] == "EXPIRED":
                    results[rp.id]["tier"] = "KEEP_LAST"
                    results[rp.id]["reason"] = f"Within keep-last {self.keep_last} points"
                keep_last_count += 1

        # Calendar groupings: map calendar key -> newest recovery point in that bucket
        daily_buckets: Dict[str, any] = {}    # YYYY-MM-DD
        weekly_buckets: Dict[str, any] = {}   # YYYY-Www
        monthly_buckets: Dict[str, any] = {}  # YYYY-MM
        yearly_buckets: Dict[str, any] = {}   # YYYY

        for rp in sorted_points:
            dt = self._to_tz(rp.created_at)
            day_key = dt.strftime("%Y-%m-%d")
            year, week, _ = dt.isocalendar()
            week_key = f"{year}-W{week:02d}"
            month_key = dt.strftime("%Y-%m")
            year_key = dt.strftime("%Y")

            # Since sorted_points is newest first, the first one encountered is the latest in that period
            if day_key not in daily_buckets:
                daily_buckets[day_key] = rp
            if week_key not in weekly_buckets:
                weekly_buckets[week_key] = rp
            if month_key not in monthly_buckets:
                monthly_buckets[month_key] = rp
            if year_key not in yearly_buckets:
                yearly_buckets[year_key] = rp

        # Apply Yearly GFS
        sorted_years = sorted(yearly_buckets.keys(), reverse=True)[:self.yearly_count]
        for y_key in sorted_years:
            rp = yearly_buckets[y_key]
            results[rp.id]["keep"] = True
            results[rp.id]["is_yearly"] = True
            if results[rp.id]["tier"] in ("EXPIRED", "KEEP_LAST", "NEWEST"):
                results[rp.id]["tier"] = "YEARLY"
                results[rp.id]["reason"] = f"Protected by Yearly GFS ({y_key})"

        # Apply Monthly GFS
        sorted_months = sorted(monthly_buckets.keys(), reverse=True)[:self.monthly_count]
        for m_key in sorted_months:
            rp = monthly_buckets[m_key]
            results[rp.id]["keep"] = True
            results[rp.id]["is_monthly"] = True
            if results[rp.id]["tier"] in ("EXPIRED", "KEEP_LAST", "NEWEST"):
                results[rp.id]["tier"] = "MONTHLY"
                results[rp.id]["reason"] = f"Protected by Monthly GFS ({m_key})"

        # Apply Weekly GFS
        sorted_weeks = sorted(weekly_buckets.keys(), reverse=True)[:self.weekly_count]
        for w_key in sorted_weeks:
            rp = weekly_buckets[w_key]
            results[rp.id]["keep"] = True
            results[rp.id]["is_weekly"] = True
            if results[rp.id]["tier"] in ("EXPIRED", "KEEP_LAST", "NEWEST"):
                results[rp.id]["tier"] = "WEEKLY"
                results[rp.id]["reason"] = f"Protected by Weekly GFS ({w_key})"

        # Apply Daily GFS
        sorted_days = sorted(daily_buckets.keys(), reverse=True)[:self.daily_count]
        for d_key in sorted_days:
            rp = daily_buckets[d_key]
            results[rp.id]["keep"] = True
            results[rp.id]["is_daily"] = True
            if results[rp.id]["tier"] in ("EXPIRED", "KEEP_LAST", "NEWEST"):
                results[rp.id]["tier"] = "DAILY"
                results[rp.id]["reason"] = f"Protected by Daily GFS ({d_key})"

        return results
