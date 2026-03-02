"""Autonomous tutorial pipeline that runs end-to-end without manual intervention."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

import schedule

from config import settings
from core.analytics_engine import update_analytics
from core.content_generator import detect_language, generate_tutorial
from core.trend_analyzer import aggregate_trending_topics, load_trends_cache, save_trends_cache
from publishers import publish_to_blogger, publish_to_devto, publish_to_hashnode, publish_to_telegram
from utils.historial import append_item, update_item
from utils.logger import get_logger
from utils.paths import ensure_dirs, p

logger = get_logger(__name__)


class AutonomousPipeline:
    """Autonomous pipeline that discovers, generates, and publishes tutorials daily."""

    def __init__(self, category: str = "programming") -> None:
        ensure_dirs()
        self.category = category
        self.state_file = p("data", "autonomous_state.json")
        self.processed_topics = self._load_processed_topics()
        self.cron_markers = self._load_cron_markers()

    def _load_state_payload(self) -> Dict[str, Any]:
        try:
            with open(self.state_file, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _load_processed_topics(self) -> set[str]:
        payload = self._load_state_payload()
        topics = payload.get("processed_topics", [])
        return {str(topic).strip().lower() for topic in topics if str(topic).strip()}

    def _load_cron_markers(self) -> set[str]:
        payload = self._load_state_payload()
        markers = payload.get("cron_markers", [])
        return {str(marker).strip() for marker in markers if str(marker).strip()}

    def _prune_cron_markers(self, keep_days: int = 14) -> None:
        threshold = datetime.now() - timedelta(days=max(1, keep_days))
        kept: set[str] = set()
        for marker in self.cron_markers:
            date_text = marker.split("|", 1)[0]
            try:
                slot_date = datetime.strptime(date_text, "%Y-%m-%d")
            except ValueError:
                continue
            if slot_date >= threshold:
                kept.add(marker)
        self.cron_markers = kept

    def _save_state(self) -> None:
        self._prune_cron_markers()
        payload = {
            "processed_topics": sorted(self.processed_topics),
            "cron_markers": sorted(self.cron_markers),
            "updated_at": datetime.now().isoformat(),
        }
        with open(self.state_file, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def daily_analysis(self) -> List[Dict[str, Any]]:
        """Refresh trend cache from all configured sources."""
        logger.info("Daily trends analysis started")
        topics = aggregate_trending_topics(category=self.category, limit=20)
        save_trends_cache(topics, category=self.category)
        logger.info("Daily trends analysis completed topics=%s", len(topics))
        return topics

    def _topic_key(self, topic: str) -> str:
        return str(topic).strip().lower()

    def _publish_all(self, tutorial: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        results: Dict[str, Dict[str, Any]] = {}
        collected_urls: Dict[str, str] = dict(tutorial.get("urls", {}))

        for platform, publisher in (
            ("devto", publish_to_devto),
            ("hashnode", publish_to_hashnode),
            ("blogger", publish_to_blogger),
        ):
            try:
                results[platform] = publisher(tutorial)
                if results[platform].get("success") and results[platform].get("url"):
                    collected_urls[platform] = str(results[platform]["url"])
            except Exception as exc:  # pragma: no cover
                logger.error("Publish failed platform=%s error=%s", platform, exc, exc_info=True)
                results[platform] = {
                    "success": False,
                    "platform": platform,
                    "error": str(exc),
                }

        telegram_payload = {**tutorial, "urls": collected_urls}
        try:
            results["telegram"] = publish_to_telegram(telegram_payload)
        except Exception as exc:  # pragma: no cover
            logger.error("Publish failed platform=telegram error=%s", exc, exc_info=True)
            results["telegram"] = {
                "success": False,
                "platform": "telegram",
                "error": str(exc),
            }

        return results

    def generate_and_publish(self) -> Dict[str, Any]:
        """Generate and publish one tutorial from freshest unprocessed trend."""
        logger.info("Autonomous generation cycle started")
        topics = load_trends_cache(category=self.category)
        if not topics:
            topics = self.daily_analysis()

        for topic_data in topics:
            topic = str(topic_data.get("title", "")).strip()
            if not topic:
                continue

            key = self._topic_key(topic)
            if key in self.processed_topics:
                continue

            logger.info("Generating tutorial topic=%s", topic)
            try:
                tutorial = generate_tutorial(
                    topic=topic,
                    length=settings.DEFAULT_LENGTH,
                    tutorial_type="technical",
                    force_english=True,
                )
                if detect_language(str(tutorial.get("content", ""))) != "en":
                    logger.warning("Skipping non-English tutorial topic=%s", topic)
                    continue

                stored = append_item(tutorial)
                results = self._publish_all(stored)

                successful_platforms = [name for name, result in results.items() if result.get("success")]
                urls = {
                    name: result.get("url")
                    for name, result in results.items()
                    if result.get("success") and result.get("url")
                }
                updates = {
                    "platforms_published": successful_platforms,
                    "urls": urls,
                }

                updated_tutorial = update_item(stored["id"], updates) or {**stored, **updates}
                update_analytics(updated_tutorial, results)

                self.processed_topics.add(key)
                self._save_state()

                logger.info("Autonomous publish completed topic=%s success=%s", topic, successful_platforms)
                return {
                    "success": True,
                    "topic": topic,
                    "tutorial_id": updated_tutorial.get("id"),
                    "results": results,
                }
            except Exception as exc:
                logger.error("Autonomous cycle failed topic=%s error=%s", topic, exc, exc_info=True)
                continue

        logger.warning("No publishable topics available in current cycle")
        return {
            "success": False,
            "error": "No publishable topics available",
            "checked_topics": len(topics),
        }

    def _schedule_publish_jobs(self) -> None:
        daily_times = [time_str.strip() for time_str in settings.AUTO_PUBLISH_TIMES if time_str.strip()]
        max_per_day = max(1, int(settings.AUTO_GENERATE_PER_DAY))
        for time_str in daily_times[:max_per_day]:
            schedule.every().day.at(time_str).do(self.generate_and_publish)
            logger.info("Scheduled generation job at %s", time_str)

    def run_forever(self) -> None:
        """Start autonomous scheduler loop."""
        trends_time = f"{int(settings.TRENDS_UPDATE_HOUR):02d}:00"
        schedule.every().day.at(trends_time).do(self.daily_analysis)
        logger.info("Scheduled trends job at %s", trends_time)

        self._schedule_publish_jobs()

        logger.info("Autonomous pipeline started")
        while True:
            schedule.run_pending()
            time.sleep(60)

    def _publish_hours(self) -> set[int]:
        hours: set[int] = set()
        for raw in settings.AUTO_PUBLISH_TIMES:
            value = str(raw).strip()
            if ":" not in value:
                continue
            hour_text, _ = value.split(":", 1)
            try:
                hours.add(int(hour_text))
            except ValueError:
                continue
        return hours

    def _is_in_cron_window(self, now: datetime) -> bool:
        window = max(1, int(settings.CRON_WINDOW_MINUTES))
        return int(now.minute) < window

    def _slot_marker(self, now: datetime, job: str, hour: int) -> str:
        return f"{now.strftime('%Y-%m-%d')}|{job}|{int(hour):02d}"

    def _slot_due(self, now: datetime, hour: int, job: str) -> bool:
        marker = self._slot_marker(now, job=job, hour=hour)
        if marker in self.cron_markers:
            return False
        target = now.replace(hour=int(hour), minute=0, second=0, microsecond=0)
        return now >= target

    def _mark_slot_done(self, now: datetime, hour: int, job: str) -> None:
        marker = self._slot_marker(now, job=job, hour=hour)
        self.cron_markers.add(marker)
        self._save_state()

    def _run_cron_dispatch(self) -> Dict[str, Any]:
        now = datetime.now(ZoneInfo(settings.PIPELINE_TIMEZONE))
        if not self._is_in_cron_window(now):
            logger.info("Cron dispatch skipped outside window local_time=%s", now.isoformat())
            return {"success": True, "skipped": True, "reason": "outside_window", "local_time": now.isoformat()}

        actions: List[str] = []
        results: Dict[str, Any] = {}

        publish_hours = sorted(self._publish_hours())
        trends_hour = int(settings.TRENDS_UPDATE_HOUR)

        if self._slot_due(now=now, hour=trends_hour, job="trends"):
            actions.append("trends")
            results["trends"] = self.daily_analysis()
            self._mark_slot_done(now=now, hour=trends_hour, job="trends")

        due_publish_slots = [hour for hour in publish_hours if self._slot_due(now=now, hour=hour, job="publish")]
        if due_publish_slots:
            actions.append("publish")
            publish_results: List[Dict[str, Any]] = []
            for slot_hour in due_publish_slots:
                slot_result = self.generate_and_publish()
                self._mark_slot_done(now=now, hour=slot_hour, job="publish")

                no_topics = (
                    not slot_result.get("success")
                    and str(slot_result.get("error", "")).lower() == "no publishable topics available"
                )
                if no_topics:
                    slot_result["success"] = True
                    slot_result["skipped"] = True
                    slot_result["reason"] = "no_publishable_topics"
                    slot_result["slot_hour"] = slot_hour
                    publish_results.append(slot_result)
                    break

                slot_result["slot_hour"] = slot_hour
                publish_results.append(slot_result)

            results["publish"] = publish_results

        if not actions:
            logger.info("Cron dispatch no matching jobs local_hour=%s", now.hour)
            return {"success": True, "skipped": True, "reason": "no_matching_jobs", "local_time": now.isoformat()}

        publish_result = results.get("publish")
        if isinstance(publish_result, dict) and not publish_result.get("success"):
            if str(publish_result.get("error", "")).lower() == "no publishable topics available":
                logger.info("Cron dispatch publish skipped: no new topics")
                publish_result["success"] = True
                publish_result["skipped"] = True

        return {
            "success": True,
            "actions": actions,
            "results": results,
            "local_time": now.isoformat(),
        }

    def run_once(self, job: str = "full") -> Dict[str, Any]:
        """Execute one autonomous cycle without scheduler loop."""
        selected = str(job).strip().lower()
        if selected == "trends":
            topics = self.daily_analysis()
            return {"success": True, "job": "trends", "topics": len(topics)}
        if selected == "publish":
            result = self.generate_and_publish()
            if not result.get("success") and str(result.get("error", "")).lower() == "no publishable topics available":
                return {"success": True, "job": "publish", "skipped": True, "reason": "no_publishable_topics"}
            return {"success": bool(result.get("success")), "job": "publish", "result": result}
        if selected == "cron":
            return self._run_cron_dispatch()

        topics = self.daily_analysis()
        result = self.generate_and_publish()
        if not result.get("success") and str(result.get("error", "")).lower() == "no publishable topics available":
            result = {"success": True, "skipped": True, "reason": "no_publishable_topics"}
        return {
            "success": bool(result.get("success")),
            "job": "full",
            "topics": len(topics),
            "result": result,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomous tutorial pipeline runner.")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit.")
    parser.add_argument(
        "--job",
        default="full",
        choices=["full", "trends", "publish", "cron"],
        help="Job type for --once mode.",
    )
    parser.add_argument("--category", default="programming", help="Trend category to analyze.")
    args = parser.parse_args()

    pipeline = AutonomousPipeline(category=args.category)
    if args.once:
        result = pipeline.run_once(job=args.job)
        logger.info("One-shot run completed result=%s", result)
        return 0 if result.get("success") else 1

    pipeline = AutonomousPipeline(category=args.category)
    pipeline.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
