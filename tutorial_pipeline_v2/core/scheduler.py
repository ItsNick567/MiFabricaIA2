"""Scheduling and automated publication queue."""

from __future__ import annotations

import json
import random
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List

from core.analytics_engine import update_analytics
from publishers import publish_to_platforms
from utils.historial import update_item
from utils.logger import get_logger
from utils.paths import DATA_QUEUE_FILE, ensure_dirs

logger = get_logger(__name__)


class PublicationQueue:
    """Persistent queue for scheduled publications."""

    def __init__(self, queue_file: str = DATA_QUEUE_FILE) -> None:
        self.queue_file = queue_file
        self.queue = self.load_queue()

    def load_queue(self) -> List[Dict[str, Any]]:
        """Load queue from disk."""
        ensure_dirs()
        try:
            with open(self.queue_file, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, list):
                return payload
        except Exception:
            pass
        return []

    def save_queue(self) -> None:
        """Save queue to disk."""
        with open(self.queue_file, "w", encoding="utf-8") as handle:
            json.dump(self.queue, handle, ensure_ascii=False, indent=2)

    def schedule(self, tutorial_data: Dict[str, Any], platforms: List[str], publish_datetime: datetime) -> str:
        """Schedule a publication job."""
        job_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        job = {
            "id": job_id,
            "tutorial": tutorial_data,
            "platforms": platforms,
            "scheduled_for": publish_datetime.isoformat(),
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "results": None,
            "completed_at": None,
        }
        self.queue.append(job)
        self.save_queue()
        logger.info("Scheduled publication job=%s for=%s", job_id, publish_datetime.isoformat())
        return job_id

    def get_pending_jobs(self) -> List[Dict[str, Any]]:
        """Return all due pending jobs."""
        now = datetime.now()
        due: List[Dict[str, Any]] = []
        for job in self.queue:
            if job.get("status") != "pending":
                continue
            try:
                eta = datetime.fromisoformat(str(job.get("scheduled_for")))
            except ValueError:
                continue
            if eta <= now:
                due.append(job)
        return due

    def mark_completed(self, job_id: str, results: Dict[str, Any]) -> None:
        """Mark queue job as completed."""
        for job in self.queue:
            if str(job.get("id")) == str(job_id):
                job["status"] = "completed"
                job["results"] = results
                job["completed_at"] = datetime.now().isoformat()
                break
        self.save_queue()

    def mark_failed(self, job_id: str, error: str) -> None:
        """Mark queue job as failed."""
        for job in self.queue:
            if str(job.get("id")) == str(job_id):
                job["status"] = "failed"
                job["results"] = {"error": error}
                job["completed_at"] = datetime.now().isoformat()
                break
        self.save_queue()


def optimal_publishing_strategy(tutorial_count_per_week: int = 3) -> List[datetime]:
    """Suggest publication slots for the next 7 days."""
    best_times = {
        "devto": [(8, 0), (13, 0), (19, 0)],
        "hashnode": [(9, 0), (14, 0), (20, 0)],
        "telegram": [(7, 0), (12, 0), (18, 0), (21, 0)],
        "blogger": [(10, 0), (15, 0), (20, 30)],
    }

    candidates = []
    now = datetime.now()
    default_days = [0, 2, 4, 6]
    selected_days = default_days[: max(1, tutorial_count_per_week)]

    for day_offset in selected_days:
        base_date = now + timedelta(days=day_offset)
        hour, minute = random.choice(best_times["hashnode"])
        slot = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if slot <= now:
            slot += timedelta(days=1)
        candidates.append(slot)

    return sorted(candidates)


def execute_pending_jobs(queue: PublicationQueue | None = None) -> List[Dict[str, Any]]:
    """Run all due jobs once and return execution summary."""
    pub_queue = queue or PublicationQueue()
    pending_jobs = pub_queue.get_pending_jobs()
    executed: List[Dict[str, Any]] = []

    for job in pending_jobs:
        job_id = str(job.get("id"))
        tutorial = dict(job.get("tutorial") or {})
        platforms = [str(platform).lower() for platform in job.get("platforms", [])]

        try:
            results = publish_to_platforms(tutorial_data=tutorial, platforms=platforms)
            pub_queue.mark_completed(job_id, results)

            urls = {platform: result.get("url") for platform, result in results.items() if result.get("url")}
            published = [platform for platform, result in results.items() if result.get("success")]

            tutorial_updates = {
                "platforms_published": list(sorted(set((tutorial.get("platforms_published") or []) + published))),
                "urls": {**(tutorial.get("urls") or {}), **urls},
            }
            update_item(str(tutorial.get("id", "")), tutorial_updates)
            update_analytics(tutorial_item={**tutorial, **tutorial_updates}, publish_results=results)
            executed.append({"job_id": job_id, "status": "completed", "results": results})
        except Exception as exc:
            logger.error("Queue job failed id=%s: %s", job_id, exc, exc_info=True)
            pub_queue.mark_failed(job_id, str(exc))
            executed.append({"job_id": job_id, "status": "failed", "error": str(exc)})

    return executed


class BackgroundWorker:
    """Simple polling worker for scheduled jobs."""

    def __init__(self, interval_seconds: int = 60) -> None:
        self.interval_seconds = interval_seconds
        self.queue = PublicationQueue()

    def run_once(self) -> List[Dict[str, Any]]:
        """Execute due jobs once."""
        return execute_pending_jobs(self.queue)

    def run_forever(self) -> None:
        """Continuously process queue at fixed interval."""
        logger.info("Scheduler worker started interval=%ss", self.interval_seconds)
        while True:
            try:
                execute_pending_jobs(self.queue)
            except Exception as exc:  # pragma: no cover
                logger.error("Worker cycle error: %s", exc, exc_info=True)
            time.sleep(self.interval_seconds)
