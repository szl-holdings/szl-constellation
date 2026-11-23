import unittest

from channels.chan import Channel, ChannelError

NOW = 10_000.0


class FakeClock:
    """Deterministic clock (Kimi W32 amend 7): never wall-clock sleeps."""

    def __init__(self, start=NOW):
        self.t = float(start)

    def __call__(self):
        return self.t


class ValidationTests(unittest.TestCase):
    def test_malformed_channel_args_rejected(self):
        with self.assertRaises(ChannelError):
            Channel(max_queue=0, stale_window_s=60.0)
        with self.assertRaises(ChannelError):
            Channel(max_queue=True, stale_window_s=60.0)
        with self.assertRaises(ChannelError):
            Channel(max_queue=4, stale_window_s=0)
        with self.assertRaises(ChannelError):
            Channel(max_queue=4, stale_window_s=-1.0)

    def test_subscriber_validation(self):
        ch = Channel(max_queue=4, stale_window_s=60.0)
        with self.assertRaises(ChannelError):
            ch.subscribe("")
        with self.assertRaises(ChannelError):
            ch.subscribe(None)
        with self.assertRaises(ChannelError):
            ch.unsubscribe("nobody")
        ch.subscribe("a")
        with self.assertRaises(ChannelError):
            ch.subscribe("a")  # duplicate sid


class PublishTests(unittest.TestCase):
    def test_full_queue_drops_oldest_and_counts_never_silent(self):
        ch = Channel(max_queue=2, stale_window_s=60.0)
        ch.subscribe("s")
        ch.publish(1)
        ch.publish(2)
        r = ch.publish(3)
        self.assertEqual(r["dropped_this_publish"], 1)
        row = ch.roll()["subscribers"][0]
        self.assertEqual(row["dropped"], 1)
        self.assertEqual(row["queued"], 2)     # oldest (1) was evicted
        self.assertEqual(row["enqueued_total"], 3)
        # Kimi W32 amend 6: per-subscriber identity enqueued_total == queued + dropped
        self.assertEqual(row["enqueued_total"], row["queued"] + row["dropped"])

    def test_publisher_never_blocked_by_full_subscriber(self):
        # Kimi W32 amend 7: deterministic fake clock (no sleeps), a FULL
        # subscriber, and other live subscribers still receiving; publish
        # returns synchronously in bounded time with no exception.
        ch = Channel(max_queue=1, stale_window_s=60.0, clock=FakeClock())
        ch.subscribe("slow")
        ch.subscribe("fast")
        for i in range(10):
            r = ch.publish(i)  # synchronous, unblocked, no sleep involved
            self.assertEqual(r["delivered_this_publish"], 2)  # both still receive
        rows = {row["sid"]: row for row in ch.roll()["subscribers"]}
        # every live subscriber still receives (enqueues) every message even
        # while queues are full: enqueue totals advance, never blocked.
        self.assertEqual(rows["slow"]["enqueued_total"], 10)
        self.assertEqual(rows["fast"]["enqueued_total"], 10)
        # bounded queues evict for BOTH subscribers: counted, never silent,
        # and the per-subscriber identity enqueued == queued + dropped holds.
        self.assertEqual(rows["slow"]["dropped"], 9)
        self.assertEqual(rows["fast"]["dropped"], 9)
        for row in rows.values():
            self.assertEqual(row["enqueued_total"], row["queued"] + row["dropped"])
            self.assertEqual(row["queued"], 1)
        # the latest message is present for every subscriber
        self.assertEqual(list(ch._subs["slow"]["queue"])[-1], 9)
        self.assertEqual(list(ch._subs["fast"]["queue"])[-1], 9)

    def test_totals_reconcile(self):
        # Kimi W32 amend 6: published_total * live_subscribers == sum(enqueued_total),
        # and per subscriber enqueued_total == queued_now + dropped.
        ch = Channel(max_queue=1, stale_window_s=60.0, clock=FakeClock())
        ch.subscribe("a")
        ch.subscribe("b")
        for i in range(5):
            ch.publish(i)
        rows = ch.roll()["subscribers"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(r["enqueued_total"] for r in rows),
                         ch.published_total * 2)
        for r in rows:
            self.assertEqual(r["enqueued_total"], r["queued"] + r["dropped"])

    def test_unsubscribe_stops_delivery(self):
        ch = Channel(max_queue=4, stale_window_s=60.0)
        ch.subscribe("a")
        ch.subscribe("b")
        ch.unsubscribe("a")
        r = ch.publish("x")
        self.assertEqual(r["delivered_this_publish"], 1)
        # unsubscribed subscriber is absent from every report
        self.assertNotIn("a", [row["sid"] for row in ch.roll()["subscribers"]])


class StalenessTests(unittest.TestCase):
    def test_staleness_boundary_exact(self):
        # Kimi W32 amend 5: STALE iff strictly greater; exactly-equal is NOT stale.
        ch = Channel(max_queue=4, stale_window_s=60.0, clock=FakeClock(NOW))
        ch.subscribe("s")  # last_seen_ts == NOW at subscribe
        self.assertFalse(ch.roll(NOW + 60.0)["subscribers"][0]["stale"])   # boundary fresh
        self.assertTrue(ch.roll(NOW + 60.001)["subscribers"][0]["stale"])  # beyond window

    def test_last_seen_updated_only_on_successful_enqueue(self):
        # Kimi W32 amend 5: only a successful enqueue refreshes last_seen_ts.
        ch = Channel(max_queue=4, stale_window_s=60.0, clock=FakeClock(NOW))
        ch.subscribe("s")
        ch.publish("m1", NOW + 10)  # enqueue refreshes last_seen to NOW+10
        row = ch.roll(NOW + 69)["subscribers"][0]
        self.assertFalse(row["stale"])  # silent 59 <= 60
        # staleness evaluated BEFORE delivery at publish time
        r = ch.publish("m2", NOW + 100)
        self.assertTrue(r["stale_at_publish"][0]["stale_at_publish"])  # silent 90 > 60 pre-delivery
        self.assertFalse(ch.roll(NOW + 150)["subscribers"][0]["stale"])  # refresh happened

    def test_stale_mark_disclosed_not_disconnect(self):
        ch = Channel(max_queue=4, stale_window_s=60.0, clock=FakeClock(NOW))
        ch.subscribe("s")
        roll = ch.roll(NOW + 10_000.0)
        self.assertTrue(roll["subscribers"][0]["stale"])
        self.assertIn("does not disconnect", roll["stale_disclosure"])
        r = ch.publish("still-delivered", NOW + 10_000.0)
        self.assertEqual(r["delivered_this_publish"], 1)  # STALE is a mark, delivery continues


if __name__ == "__main__":
    unittest.main()
