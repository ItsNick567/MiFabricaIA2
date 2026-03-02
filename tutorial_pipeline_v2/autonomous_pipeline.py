"""Autonomous tutorial pipeline that runs end-to-end without manual intervention."""

from __future__ import annotations

import argparse
import json
import re
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
from utils.historial import append_item, cargar_datos, update_item
from utils.logger import get_logger
from utils.paths import ensure_dirs, p

logger = get_logger(__name__)

TOPIC_PREFIX_PATTERNS = (
    r"^\s*getting\s+started\s+with\s+",
    r"^\s*introduction\s+to\s+",
    r"^\s*intro\s+to\s+",
    r"^\s*how\s+to\s+",
    r"^\s*tutorial\s*:\s*",
)
TOPIC_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "from",
    "guide",
    "in",
    "introduction",
    "of",
    "on",
    "the",
    "to",
    "tutorial",
    "using",
    "with",
    "everything",
    "about",
}


class AutonomousPipeline:
    """Autonomous pipeline that discovers, generates, and publishes tutorials daily."""

    def __init__(self, category: str = "programming") -> None:
        ensure_dirs()
        self.category = category
        self.state_file = p("data", "autonomous_state.json")
        self.required_platforms = self._required_platforms()
        self.topic_publications = self._load_topic_publications()
        self._bootstrap_publications_from_history()
        self.processed_topics = self._build_processed_topics()
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
        normalized: set[str] = set()
        for topic in topics:
            raw = str(topic).strip()
            if not raw:
                continue
            canonical = self._topic_key(raw)
            normalized.add(canonical or raw.lower())
        return normalized

    def _load_topic_publications(self) -> Dict[str, Dict[str, Any]]:
        payload = self._load_state_payload()
        raw = payload.get("topic_publications", {})
        if not isinstance(raw, dict):
            return {}

        parsed: Dict[str, Dict[str, Any]] = {}
        for raw_key, raw_value in raw.items():
            key = self._topic_key(str(raw_key))
            if not key or not isinstance(raw_value, dict):
                continue

            platforms = {
                str(name).strip().lower()
                for name in raw_value.get("platforms_success", [])
                if str(name).strip()
            }
            urls_raw = raw_value.get("urls", {})
            urls = {
                str(name).strip().lower(): str(url).strip()
                for name, url in urls_raw.items()
                if str(name).strip() and str(url).strip()
            } if isinstance(urls_raw, dict) else {}

            parsed[key] = {
                "topic": str(raw_value.get("topic", "")).strip(),
                "title": str(raw_value.get("title", "")).strip(),
                "tutorial_id": str(raw_value.get("tutorial_id", "")).strip(),
                "platforms_success": sorted(platforms),
                "urls": urls,
                "updated_at": str(raw_value.get("updated_at", "")).strip(),
            }
        return parsed

    def _load_cron_markers(self) -> set[str]:
        payload = self._load_state_payload()
        markers = payload.get("cron_markers", [])
        return {str(marker).strip() for marker in markers if str(marker).strip()}

    def _required_platforms(self) -> List[str]:
        required: List[str] = []
        if settings.DEVTO_API_KEY:
            required.append("devto")
        if settings.HASHNODE_API_KEY and settings.HASHNODE_PUBLICATION_ID:
            required.append("hashnode")
        blogger_refresh_ready = bool(
            settings.BLOGGER_CLIENT_ID and settings.BLOGGER_CLIENT_SECRET and settings.BLOGGER_REFRESH_TOKEN
        )
        if settings.BLOGGER_BLOG_ID and (settings.BLOGGER_ACCESS_TOKEN or blogger_refresh_ready):
            required.append("blogger")
        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHANNEL_ID:
            required.append("telegram")
        if not required:
            required = ["devto", "hashnode", "blogger", "telegram"]
        return required

    def _build_processed_topics(self) -> set[str]:
        processed: set[str] = set(self._load_processed_topics())
        required = set(self.required_platforms)
        if not required:
            return processed

        for key, record in self.topic_publications.items():
            platforms = {str(name).lower() for name in record.get("platforms_success", [])}
            if required.issubset(platforms):
                processed.add(key)
        return processed

    def _bootstrap_publications_from_history(self) -> None:
        history = cargar_datos()
        for item in history:
            topic = str(item.get("topic") or item.get("title") or "").strip()
            if not topic:
                continue
            key = self._topic_key(topic)
            if not key:
                continue

            platforms = {
                str(name).strip().lower()
                for name in item.get("platforms_published", [])
                if str(name).strip()
            }
            urls = {
                str(name).strip().lower(): str(url).strip()
                for name, url in (item.get("urls", {}) or {}).items()
                if str(name).strip() and str(url).strip()
            }
            platforms.update(urls.keys())
            if not platforms and not urls:
                continue

            entry = self.topic_publications.get(
                key,
                {
                    "topic": str(item.get("topic", "")).strip(),
                    "title": str(item.get("title", "")).strip(),
                    "tutorial_id": "",
                    "platforms_success": [],
                    "urls": {},
                    "updated_at": "",
                },
            )

            merged_platforms = set(entry.get("platforms_success", [])) | platforms
            merged_urls = dict(entry.get("urls", {}))
            merged_urls.update(urls)

            timestamp = str(item.get("timestamp", "")).strip() or datetime.now().isoformat()
            existing_timestamp = str(entry.get("updated_at", "")).strip()
            should_replace_id = not existing_timestamp or timestamp >= existing_timestamp
            tutorial_id = str(item.get("id", "")).strip() if should_replace_id else str(entry.get("tutorial_id", ""))

            self.topic_publications[key] = {
                "topic": str(item.get("topic", "")).strip() or str(entry.get("topic", "")).strip(),
                "title": str(item.get("title", "")).strip() or str(entry.get("title", "")).strip(),
                "tutorial_id": tutorial_id,
                "platforms_success": sorted({name.lower() for name in merged_platforms}),
                "urls": merged_urls,
                "updated_at": max(existing_timestamp, timestamp),
            }

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
        topic_publications_payload: Dict[str, Dict[str, Any]] = {}
        for key, value in self.topic_publications.items():
            topic_publications_payload[key] = {
                "topic": str(value.get("topic", "")).strip(),
                "title": str(value.get("title", "")).strip(),
                "tutorial_id": str(value.get("tutorial_id", "")).strip(),
                "platforms_success": sorted(
                    {
                        str(name).strip().lower()
                        for name in value.get("platforms_success", [])
                        if str(name).strip()
                    }
                ),
                "urls": {
                    str(name).strip().lower(): str(url).strip()
                    for name, url in (value.get("urls", {}) or {}).items()
                    if str(name).strip() and str(url).strip()
                },
                "updated_at": str(value.get("updated_at", "")).strip() or datetime.now().isoformat(),
            }

        payload = {
            "processed_topics": sorted(self.processed_topics),
            "cron_markers": sorted(self.cron_markers),
            "required_platforms": self.required_platforms,
            "topic_publications": topic_publications_payload,
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
        text = str(topic or "").strip().lower()
        if not text:
            return ""

        for pattern in TOPIC_PREFIX_PATTERNS:
            text = re.sub(pattern, "", text, flags=re.I)

        raw_tokens = re.findall(r"[a-z0-9+#.-]{2,}", text)
        expanded_tokens: List[str] = []
        for token in raw_tokens:
            pieces = [piece for piece in re.split(r"[._-]+", token) if piece]
            if len(pieces) > 1:
                expanded_tokens.extend(pieces)
            else:
                expanded_tokens.append(token)

        tokens = [token for token in expanded_tokens if len(token) >= 2]
        filtered = [token for token in tokens if token not in TOPIC_STOPWORDS]
        if not filtered:
            filtered = tokens
        if not filtered:
            return text
        return " ".join(filtered[:6])

    def _pending_platforms_for_key(self, key: str) -> List[str]:
        record = self.topic_publications.get(key, {})
        already = {str(name).strip().lower() for name in record.get("platforms_success", []) if str(name).strip()}
        return [platform for platform in self.required_platforms if platform not in already]

    def _find_history_item_for_key(self, key: str, preferred_id: str = "") -> Dict[str, Any] | None:
        history = cargar_datos()
        if preferred_id:
            for item in reversed(history):
                if str(item.get("id", "")).strip() == preferred_id:
                    return item

        for item in reversed(history):
            topic_key = self._topic_key(str(item.get("topic", "")).strip())
            title_key = self._topic_key(str(item.get("title", "")).strip())
            if key and (key == topic_key or key == title_key):
                return item
        return None

    def _publish_to_platforms(
        self,
        tutorial: Dict[str, Any],
        target_platforms: List[str],
        seed_urls: Dict[str, str] | None = None,
    ) -> Dict[str, Dict[str, Any]]:
        target = {str(name).strip().lower() for name in target_platforms if str(name).strip()}
        if not target:
            return {}

        results: Dict[str, Dict[str, Any]] = {}
        collected_urls: Dict[str, str] = {}
        if isinstance(tutorial.get("urls"), dict):
            for platform, url in tutorial["urls"].items():
                if str(platform).strip() and str(url).strip():
                    collected_urls[str(platform).strip().lower()] = str(url).strip()
        if isinstance(seed_urls, dict):
            for platform, url in seed_urls.items():
                if str(platform).strip() and str(url).strip():
                    collected_urls[str(platform).strip().lower()] = str(url).strip()

        for platform, publisher in (
            ("devto", publish_to_devto),
            ("hashnode", publish_to_hashnode),
            ("blogger", publish_to_blogger),
        ):
            if platform not in target:
                continue
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

        if "telegram" in target:
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

    def _update_history_after_publish(
        self,
        tutorial: Dict[str, Any],
        results: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        successful_platforms = {
            str(name).strip().lower()
            for name, result in results.items()
            if isinstance(result, dict) and result.get("success")
        }
        existing_platforms = {
            str(name).strip().lower()
            for name in tutorial.get("platforms_published", [])
            if str(name).strip()
        }
        merged_platforms = sorted(existing_platforms | successful_platforms)

        existing_urls = {
            str(name).strip().lower(): str(url).strip()
            for name, url in (tutorial.get("urls", {}) or {}).items()
            if str(name).strip() and str(url).strip()
        }
        result_urls = {
            str(name).strip().lower(): str(result.get("url")).strip()
            for name, result in results.items()
            if isinstance(result, dict) and result.get("success") and result.get("url")
        }
        merged_urls = {**existing_urls, **result_urls}

        updates = {
            "platforms_published": merged_platforms,
            "urls": merged_urls,
        }
        updated_tutorial = update_item(str(tutorial.get("id", "")), updates) or {**tutorial, **updates}
        update_analytics(updated_tutorial, results)
        return updated_tutorial

    def _merge_topic_publication_state(
        self,
        *,
        key: str,
        topic: str,
        title: str,
        tutorial_id: str,
        results: Dict[str, Dict[str, Any]],
        fallback_urls: Dict[str, str] | None = None,
    ) -> None:
        record = self.topic_publications.get(
            key,
            {
                "topic": "",
                "title": "",
                "tutorial_id": "",
                "platforms_success": [],
                "urls": {},
                "updated_at": "",
            },
        )

        existing_success = {
            str(name).strip().lower()
            for name in record.get("platforms_success", [])
            if str(name).strip()
        }
        new_success = {
            str(name).strip().lower()
            for name, result in results.items()
            if isinstance(result, dict) and result.get("success")
        }
        merged_success = sorted(existing_success | new_success)

        merged_urls = {
            str(name).strip().lower(): str(url).strip()
            for name, url in (record.get("urls", {}) or {}).items()
            if str(name).strip() and str(url).strip()
        }
        if isinstance(fallback_urls, dict):
            for name, url in fallback_urls.items():
                if str(name).strip() and str(url).strip():
                    merged_urls[str(name).strip().lower()] = str(url).strip()
        for name, result in results.items():
            if isinstance(result, dict) and result.get("success") and result.get("url"):
                merged_urls[str(name).strip().lower()] = str(result.get("url")).strip()

        self.topic_publications[key] = {
            "topic": topic or str(record.get("topic", "")).strip(),
            "title": title or str(record.get("title", "")).strip(),
            "tutorial_id": tutorial_id or str(record.get("tutorial_id", "")).strip(),
            "platforms_success": merged_success,
            "urls": merged_urls,
            "updated_at": datetime.now().isoformat(),
        }

        if set(self.required_platforms).issubset(set(merged_success)):
            self.processed_topics.add(key)
        else:
            self.processed_topics.discard(key)
        self._save_state()

    def _retry_pending_topic(self) -> Dict[str, Any] | None:
        for key, record in self.topic_publications.items():
            pending = self._pending_platforms_for_key(key)
            if not pending:
                continue

            tutorial_id = str(record.get("tutorial_id", "")).strip()
            tutorial = self._find_history_item_for_key(key, preferred_id=tutorial_id)
            if not tutorial:
                continue

            topic = str(tutorial.get("topic") or record.get("topic") or "").strip()
            logger.info("Retrying pending platforms topic=%s missing=%s", topic or key, pending)
            results = self._publish_to_platforms(
                tutorial=tutorial,
                target_platforms=pending,
                seed_urls=record.get("urls", {}),
            )
            if not results:
                continue

            updated_tutorial = self._update_history_after_publish(tutorial, results)
            self._merge_topic_publication_state(
                key=key,
                topic=str(updated_tutorial.get("topic", "")).strip(),
                title=str(updated_tutorial.get("title", "")).strip(),
                tutorial_id=str(updated_tutorial.get("id", "")).strip(),
                results=results,
                fallback_urls=record.get("urls", {}),
            )

            successful_platforms = [name for name, result in results.items() if result.get("success")]
            if successful_platforms:
                logger.info("Pending topic retry completed topic=%s success=%s", topic or key, successful_platforms)
                return {
                    "success": True,
                    "retry": True,
                    "topic": topic or str(record.get("topic") or key),
                    "tutorial_id": updated_tutorial.get("id"),
                    "results": results,
                }

        return None

    def generate_and_publish(self) -> Dict[str, Any]:
        """Generate and publish one tutorial from freshest unprocessed trend."""
        logger.info("Autonomous generation cycle started")

        retry_result = self._retry_pending_topic()
        if retry_result:
            return retry_result

        topics = load_trends_cache(category=self.category)
        if not topics:
            topics = self.daily_analysis()

        for topic_data in topics:
            topic = str(topic_data.get("title", "")).strip()
            if not topic:
                continue

            key = self._topic_key(topic)
            if not key:
                continue

            pending_platforms = self._pending_platforms_for_key(key)
            if not pending_platforms:
                continue

            existing_record = self.topic_publications.get(key, {})
            existing_tutorial_id = str(existing_record.get("tutorial_id", "")).strip()
            existing_tutorial = self._find_history_item_for_key(key, preferred_id=existing_tutorial_id)

            if existing_tutorial:
                logger.info("Completing pending platforms from history topic=%s missing=%s", topic, pending_platforms)
                try:
                    results = self._publish_to_platforms(
                        tutorial=existing_tutorial,
                        target_platforms=pending_platforms,
                        seed_urls=existing_record.get("urls", {}),
                    )
                    if not results:
                        continue

                    updated_tutorial = self._update_history_after_publish(existing_tutorial, results)
                    self._merge_topic_publication_state(
                        key=key,
                        topic=str(updated_tutorial.get("topic", "")).strip() or topic,
                        title=str(updated_tutorial.get("title", "")).strip(),
                        tutorial_id=str(updated_tutorial.get("id", "")).strip(),
                        results=results,
                        fallback_urls=existing_record.get("urls", {}),
                    )

                    successful_platforms = [name for name, result in results.items() if result.get("success")]
                    if successful_platforms:
                        logger.info("Autonomous publish completed topic=%s success=%s", topic, successful_platforms)
                        return {
                            "success": True,
                            "topic": topic,
                            "tutorial_id": updated_tutorial.get("id"),
                            "results": results,
                            "retry": True,
                        }
                    continue
                except Exception as exc:
                    logger.error("Autonomous retry failed topic=%s error=%s", topic, exc, exc_info=True)
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
                results = self._publish_to_platforms(stored, pending_platforms)
                if not results:
                    continue

                updated_tutorial = self._update_history_after_publish(stored, results)
                self._merge_topic_publication_state(
                    key=key,
                    topic=topic,
                    title=str(updated_tutorial.get("title", "")).strip(),
                    tutorial_id=str(updated_tutorial.get("id", "")).strip(),
                    results=results,
                    fallback_urls=updated_tutorial.get("urls", {}),
                )

                successful_platforms = [name for name, result in results.items() if result.get("success")]
                logger.info("Autonomous publish completed topic=%s success=%s", topic, successful_platforms)
                if successful_platforms:
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
