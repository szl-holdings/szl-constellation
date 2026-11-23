"""Bounded publication fan-out channels (propose-only).

Doctrine (leader-study, #58 read-only; FastAPI/asyncio websockets and
three.js instancing leaders studied, NOT executed): every publisher
proceeds regardless of slow subscribers; a full subscriber drops-oldest
AND counts the drop (never silent, never blocks).

Staleness (Kimi W32 amend 5): last_seen_ts is set at subscribe and
updated ONLY on successful enqueue; a subscriber is STALE iff
(now_ts - last_seen_ts) > stale_window_s, strictly greater, so exactly
equal is NOT stale; publish evaluates staleness at now_ts BEFORE
delivery, and every roll report carries the stale flag per subscriber.

Reconciliation accounting (Kimi W32 amend 6), disclosed: delivered
counts cumulative SUCCESSFUL ENQUEUES, and dropped counts cumulative
drop-oldest EVICTIONS, therefore per subscriber
enqueued_total == queued_now + dropped, and globally
published_total * live_subscribers == sum(enqueued_total). We do NOT
claim published == messages_currently_queued + dropped (that identity
is false under drop-oldest, which evicts already-enqueued messages).

Honest limitation, verbatim: an in-process synchronous model; NOT
asyncio/FastAPI websockets; no network; STALE is a report mark only and
does not stop delivery; the three.js side is out of scope here.

Propose-only, unsigned; merges are owned by the estate signature wall.
No status claims are made about any other pull request.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Dict, Optional

SCHEMA_VERSION = "szl.channels/v1"
BANNER = "PROPOSAL_ONLY_UNSIGNED"


class ChannelError(ValueError):
    """A channel operation input is malformed."""


class Channel:
    """Bounded-queue fan-out with honest drop accounting and staleness."""

    def __init__(self, max_queue: int, stale_window_s: float,
                 clock=None):
        if not isinstance(max_queue, int) or isinstance(max_queue, bool) or max_queue < 1:
            raise ChannelError("max_queue must be a positive int")
        if not stale_window_s or stale_window_s <= 0:
            raise ChannelError("stale_window_s must be positive")
        self.max_queue = max_queue
        self.stale_window_s = stale_window_s
        self._clock = clock or time.monotonic
        self.published_total = 0
        self._subs: Dict[str, dict] = {}

    def subscribe(self, sid: str):
        if not sid or not isinstance(sid, str):
            raise ChannelError("sid must be a non-empty string")
        if sid in self._subs:
            raise ChannelError("sid already subscribed: " + sid)
        self._subs[sid] = {"queue": deque(maxlen=self.max_queue),
                           "dropped": 0, "enqueued_total": 0,
                           "last_seen_ts": self._clock()}

    def unsubscribe(self, sid: str):
        if sid not in self._subs:
            raise ChannelError("unknown subscriber: " + str(sid))
        del self._subs[sid]

    def publish(self, msg, now_ts: Optional[float] = None) -> Dict[str, object]:
        """Deliver to every live subscriber. Staleness is evaluated at
        now_ts BEFORE delivery (amend 5); full queues drop-oldest and
        count, never silently and never-blocking (amend 7); last_seen_ts
        updates ONLY on successful enqueue."""
        if now_ts is None:
            now_ts = self._clock()
        self.published_total += 1
        delivered = 0
        dropped_this_pub = 0
        stale_rows = []
        for sid, sub in sorted(self._subs.items()):
            stale_rows.append({"sid": sid,
                               "silent_s": now_ts - sub["last_seen_ts"],
                               "stale_at_publish": (now_ts - sub["last_seen_ts"]) > self.stale_window_s})
            q = sub["queue"]
            if len(q) == q.maxlen:
                q.popleft()  # drop-oldest, counted, never silent
                sub["dropped"] += 1
                dropped_this_pub += 1
            q.append(msg)
            delivered += 1
            sub["enqueued_total"] += 1
            sub["last_seen_ts"] = now_ts  # updated ONLY on successful enqueue
        return {"schema_version": SCHEMA_VERSION, "banner": BANNER,
                "published_total": self.published_total,
                "delivered_this_publish": delivered,
                "dropped_this_publish": dropped_this_pub,
                "stale_at_publish": stale_rows,
                "reconciliation": ("delivered counts cumulative successful enqueues; "
                                   "dropped counts drop-oldest evictions; per subscriber "
                                   "enqueued_total == queued_now + dropped; globally "
                                   "published_total * live_subscribers == sum(enqueued_total)")}

    def roll(self, now_ts: Optional[float] = None) -> Dict[str, object]:
        """Honest per-subscriber report: STALE is a mark, not a guess."""
        now_ts = now_ts if now_ts is not None else self._clock()
        rows = []
        for sid, sub in sorted(self._subs.items()):
            silent = now_ts - sub["last_seen_ts"]
            rows.append({"sid": sid, "queued": len(sub["queue"]),
                         "dropped": sub["dropped"],
                         "enqueued_total": sub["enqueued_total"],
                         "silent_s": silent,
                         "stale": silent > self.stale_window_s})
        return {"schema_version": SCHEMA_VERSION, "banner": BANNER,
                "published_total": self.published_total,
                "subscribers": rows,
                "stale_disclosure": "STALE marks silence beyond the window; "
                                    "it does not disconnect or stop delivery"}
