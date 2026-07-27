"""User registration and product usage analytics."""

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from ..core.mongodb import get_collection
from ..core.utils import utc_now, utc_now_iso

LOCAL_TZ = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class ActivitySource:
    collection: str
    date_field: str
    user_field: str
    feature: str


ACTIVITY_SOURCES = (
    ActivitySource("usage_events", "created_at", "user_id", "page_view"),
    ActivitySource("diagnosis_sn_history", "created_at", "user_id", "diagnosis_run"),
    ActivitySource("diagnosis_feedback", "created_at", "user_id", "feedback"),
    ActivitySource("knowledge_documents", "uploaded_at", "user_id", "knowledge_base"),
)


def _period_bounds(days: int) -> tuple[str, str, str, str, list[str]]:
    today = utc_now().astimezone(LOCAL_TZ).date()
    start_date = today - timedelta(days=days - 1)
    previous_start_date = start_date - timedelta(days=days)
    end_date = today + timedelta(days=1)

    def to_utc_iso(value) -> str:
        local_dt = datetime.combine(value, time.min, tzinfo=LOCAL_TZ)
        return local_dt.astimezone(timezone.utc).isoformat()

    labels = [
        (start_date + timedelta(days=offset)).isoformat() for offset in range(days)
    ]
    return (
        to_utc_iso(start_date),
        to_utc_iso(end_date),
        to_utc_iso(previous_start_date),
        to_utc_iso(start_date),
        labels,
    )


def _change_percent(current: int, previous: int) -> float:
    if previous == 0:
        return 100.0 if current else 0.0
    return round((current - previous) / previous * 100, 1)


def _date_group_pipeline(
    *, date_field: str, user_field: str | None, since: str, until: str
) -> list[dict[str, Any]]:
    group: dict[str, Any] = {"_id": "$_day", "count": {"$sum": 1}}
    if user_field:
        group["users"] = {
            "$addToSet": {
                "$convert": {
                    "input": f"${user_field}",
                    "to": "string",
                    "onError": "",
                    "onNull": "",
                }
            }
        }
    return [
        {"$match": {date_field: {"$gte": since, "$lt": until}}},
        {
            "$set": {
                "_day": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": {
                            "$convert": {
                                "input": f"${date_field}",
                                "to": "date",
                                "onError": None,
                                "onNull": None,
                            }
                        },
                        "timezone": "Asia/Shanghai",
                    }
                }
            }
        },
        {"$match": {"_day": {"$ne": None}}},
        {"$group": group},
        {"$sort": {"_id": 1}},
    ]


async def _daily_rows(
    collection_name: str,
    date_field: str,
    user_field: str | None,
    since: str,
    until: str,
) -> list[dict[str, Any]]:
    cursor = get_collection(collection_name).aggregate(
        _date_group_pipeline(
            date_field=date_field,
            user_field=user_field,
            since=since,
            until=until,
        )
    )
    return await cursor.to_list(length=None)


async def _user_metrics(
    collection_name: str,
    date_field: str,
    user_field: str,
    user_ids: list[str],
) -> dict[str, dict[str, Any]]:
    if not user_ids:
        return {}
    cursor = get_collection(collection_name).aggregate(
        [
            {"$match": {user_field: {"$in": user_ids}}},
            {
                "$group": {
                    "_id": f"${user_field}",
                    "count": {"$sum": 1},
                    "last_at": {"$max": f"${date_field}"},
                }
            },
        ]
    )
    rows = await cursor.to_list(length=None)
    return {str(row["_id"]): row for row in rows if row.get("_id") is not None}


class UserAnalyticsService:
    async def track_event(self, user: dict[str, Any], feature: str) -> None:
        await get_collection("usage_events").insert_one(
            {
                "user_id": str(user.get("id") or ""),
                "itcode": str(user.get("itcode") or ""),
                "event_type": "page_view",
                "feature": feature,
                "created_at": utc_now_iso(),
            }
        )

    async def get_overview(
        self,
        *,
        days: int,
        page: int,
        limit: int,
        search: str | None,
    ) -> dict[str, Any]:
        since, until, previous_since, previous_until, day_labels = _period_bounds(days)
        users = get_collection("users")

        current_filter = {"created_at": {"$gte": since, "$lt": until}}
        previous_filter = {
            "created_at": {"$gte": previous_since, "$lt": previous_until}
        }

        source_current_counts = [
            get_collection(source.collection).count_documents(
                {source.date_field: {"$gte": since, "$lt": until}}
            )
            for source in ACTIVITY_SOURCES
        ]
        source_previous_counts = [
            get_collection(source.collection).count_documents(
                {source.date_field: {"$gte": previous_since, "$lt": previous_until}}
            )
            for source in ACTIVITY_SOURCES
        ]

        today_since = _period_bounds(1)[0]
        (
            total_users,
            new_users,
            previous_new_users,
            *usage_counts,
        ) = await asyncio.gather(
            users.count_documents({}),
            users.count_documents(current_filter),
            users.count_documents(previous_filter),
            *source_current_counts,
            *source_previous_counts,
        )
        current_usage_counts = usage_counts[: len(ACTIVITY_SOURCES)]
        previous_usage_counts = usage_counts[len(ACTIVITY_SOURCES) :]
        total_usage = sum(current_usage_counts)
        previous_total_usage = sum(previous_usage_counts)

        active_users, previous_active_users, today_active_users = await asyncio.gather(
            self._active_user_ids(since, until),
            self._active_user_ids(previous_since, previous_until),
            self._active_user_ids(today_since, until),
        )

        daily, features, user_page = await asyncio.gather(
            self._daily_series(day_labels, since, until),
            self._feature_usage(since, until),
            self._user_page(page=page, limit=limit, search=search),
        )

        active_count = len(active_users)
        return {
            "summary": {
                "total_users": total_users,
                "new_users": new_users,
                "active_users": active_count,
                "today_active_users": len(today_active_users),
                "total_usage": total_usage,
                "avg_usage_per_active_user": round(total_usage / active_count, 1)
                if active_count
                else 0,
                "changes": {
                    "new_users": _change_percent(new_users, previous_new_users),
                    "active_users": _change_percent(
                        active_count, len(previous_active_users)
                    ),
                    "total_usage": _change_percent(total_usage, previous_total_usage),
                },
            },
            "daily": daily,
            "features": features,
            "users": user_page,
            "generated_at": utc_now_iso(),
        }

    async def _active_user_ids(self, since: str, until: str) -> set[str]:
        tasks = [
            get_collection(source.collection).distinct(
                source.user_field,
                {source.date_field: {"$gte": since, "$lt": until}},
            )
            for source in ACTIVITY_SOURCES
        ]
        tasks.append(
            get_collection("users").distinct(
                "_id", {"last_login_at": {"$gte": since, "$lt": until}}
            )
        )
        results = await asyncio.gather(*tasks)
        return {str(user_id) for values in results for user_id in values if user_id}

    async def _daily_series(
        self, day_labels: list[str], since: str, until: str
    ) -> list[dict[str, Any]]:
        rows = await asyncio.gather(
            _daily_rows("users", "created_at", None, since, until),
            _daily_rows("users", "last_login_at", "_id", since, until),
            *[
                _daily_rows(
                    source.collection,
                    source.date_field,
                    source.user_field,
                    since,
                    until,
                )
                for source in ACTIVITY_SOURCES
            ],
        )
        registrations = {row["_id"]: row["count"] for row in rows[0]}
        activity_rows = rows[1:]
        result = []
        for day in day_labels:
            active_ids: set[str] = set()
            usage_count = 0
            for index, source_rows in enumerate(activity_rows):
                row = next(
                    (item for item in source_rows if item.get("_id") == day), None
                )
                if not row:
                    continue
                active_ids.update(str(value) for value in row.get("users", []) if value)
                if (
                    index > 0
                ):  # last_login_at contributes activity, not an extra usage event.
                    usage_count += int(row.get("count", 0))
            result.append(
                {
                    "date": day,
                    "new_users": int(registrations.get(day, 0)),
                    "active_users": len(active_ids),
                    "usage_count": usage_count,
                }
            )
        return result

    async def _feature_usage(self, since: str, until: str) -> list[dict[str, Any]]:
        event_cursor = get_collection("usage_events").aggregate(
            [
                {"$match": {"created_at": {"$gte": since, "$lt": until}}},
                {"$group": {"_id": "$feature", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]
        )
        event_rows, action_counts = await asyncio.gather(
            event_cursor.to_list(length=None),
            asyncio.gather(
                *[
                    get_collection(source.collection).count_documents(
                        {source.date_field: {"$gte": since, "$lt": until}}
                    )
                    for source in ACTIVITY_SOURCES[1:]
                ]
            ),
        )
        counts = {
            str(row.get("_id") or "other"): int(row.get("count", 0))
            for row in event_rows
        }
        for source, count in zip(ACTIVITY_SOURCES[1:], action_counts):
            counts[source.feature] = counts.get(source.feature, 0) + int(count)
        return [
            {"feature": feature, "count": count}
            for feature, count in sorted(
                counts.items(), key=lambda item: item[1], reverse=True
            )
            if count > 0
        ]

    async def _user_page(
        self, *, page: int, limit: int, search: str | None
    ) -> dict[str, Any]:
        query: dict[str, Any] = {}
        if search and search.strip():
            pattern = re.escape(search.strip())
            query = {
                "$or": [
                    {"name": {"$regex": pattern, "$options": "i"}},
                    {"itcode": {"$regex": pattern, "$options": "i"}},
                    {"email": {"$regex": pattern, "$options": "i"}},
                ]
            }
        collection = get_collection("users")
        total = await collection.count_documents(query)
        cursor = (
            collection.find(query, {"profile": 0})
            .sort("created_at", -1)
            .skip((page - 1) * limit)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        user_ids = [str(doc["_id"]) for doc in docs]
        metrics = await asyncio.gather(
            *[
                _user_metrics(
                    source.collection,
                    source.date_field,
                    source.user_field,
                    user_ids,
                )
                for source in ACTIVITY_SOURCES
            ]
        )

        now = utc_now()
        items = []
        for doc in docs:
            user_id = str(doc["_id"])
            user_metrics = [
                source_metrics.get(user_id, {}) for source_metrics in metrics
            ]
            last_candidates = [doc.get("last_login_at")]
            last_candidates.extend(metric.get("last_at") for metric in user_metrics)
            last_active_at = max(
                (value for value in last_candidates if value), default=""
            )
            status = "inactive"
            if last_active_at:
                try:
                    parsed = datetime.fromisoformat(
                        str(last_active_at).replace("Z", "+00:00")
                    )
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    age_days = (now - parsed.astimezone(timezone.utc)).days
                    status = (
                        "active"
                        if age_days <= 7
                        else "dormant"
                        if age_days <= 30
                        else "inactive"
                    )
                except ValueError:
                    pass
            items.append(
                {
                    "id": user_id,
                    "name": doc.get("name") or doc.get("itcode") or "未知用户",
                    "itcode": doc.get("itcode") or "",
                    "email": doc.get("email") or "",
                    "created_at": doc.get("created_at") or "",
                    "last_login_at": doc.get("last_login_at") or "",
                    "last_active_at": last_active_at,
                    "login_count": int(doc.get("login_count") or 0),
                    "diagnosis_count": int(user_metrics[1].get("count", 0)),
                    "usage_count": sum(
                        int(metric.get("count", 0)) for metric in user_metrics
                    ),
                    "status": status,
                }
            )
        return {"items": items, "total": total, "page": page, "limit": limit}


_service: UserAnalyticsService | None = None


def get_user_analytics_service() -> UserAnalyticsService:
    global _service
    if _service is None:
        _service = UserAnalyticsService()
    return _service
