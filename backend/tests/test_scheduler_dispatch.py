"""Tests for the scheduler tick — dispatch of due follow-up messages + the
Mark-as-paid endpoint that cancels any still-scheduled sends.

Both flows share a helper that seeds a `payment_hub` (status=active) with the
4 scheduled rows `approve_plan` would have produced, so each test can pick the
exact status transitions it wants to exercise without going through the full
approve flow (that path is covered by test_section4_approve.py)."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.providers.whatsapp import SentMessage
from app.repositories import store
from app.services import follow_ups
from app.util import gen_token, iso, new_id


ORG = "org_sched"


@pytest_asyncio.fixture(autouse=True)
async def _wipe():
    c = AsyncIOMotorClient(settings.MONGO_URL)
    db = c[settings.DB_NAME]
    for k in ("payment_hubs", "payment_hub_contacts", "follow_up_plans",
              "follow_up_messages", "whatsapp_messages"):
        await db[k].delete_many({})
    yield
    c.close()


async def _seed_active_hub_with_schedule(*, esc1: bool = False) -> tuple[str, list[dict]]:
    hub_id = new_id()
    await store.insert_payment_hub({
        "id": hub_id, "org_id": ORG, "upload_id": "u",
        "public_token": gen_token(16), "invoice_number": "INV-S",
        "client_name": "Kestrel", "amount_paise": 8500000,
        "currency": "INR", "due_date": "2026-01-01",
        "business_payment_details": "UPI: me@bank",
        "status": "active", "handling_mode": "dueo_handles",
        "llm_status": "ok", "created_at": iso(), "updated_at": iso(),
    })
    poc = {"name": "Amit Rao", "phone": "+15551234567", "email": "amit@k.co"}
    e1 = {"name": "Priya Nair", "phone": "+15559999999", "email": "priya@k.co"} if esc1 else None
    rows = follow_ups.build_scheduled_rows(
        hub={"id": hub_id, "due_date": "2026-01-01", "invoice_number": "INV-S",
             "client_name": "Kestrel", "amount_paise": 8500000,
             "public_token": "tok"},
        plan_id="p1", tone="professional", poc=poc, esc1=e1,
        business_name="Alpha Co", public_base="https://a.co",
    )
    await store.insert_follow_up_messages_bulk(rows)
    return hub_id, rows


def test_build_scheduled_rows_cadence_and_snapshot():
    """Cadence, category, and recipient-snapshot behaviour without any DB."""
    poc = {"name": "Amit Rao", "phone": "+11", "email": "a@k.co"}
    e1 = {"name": "Priya Nair", "phone": "+22", "email": "p@k.co"}
    rows_with = follow_ups.build_scheduled_rows(
        hub={"id": "h1", "due_date": "2026-01-01", "invoice_number": "INV",
             "client_name": "Kestrel", "amount_paise": 100000, "public_token": "t"},
        plan_id="p", tone="firm", poc=poc, esc1=e1,
        business_name="A Co", public_base="https://a.co",
    )
    assert len(rows_with) == 4
    # Cadence: 3, 7, 14, 30 days after 2026-01-01 @ 09:00 UTC
    expected_days = ["2026-01-04", "2026-01-08", "2026-01-15", "2026-01-31"]
    for r, day in zip(rows_with, expected_days):
        assert r["scheduled_for"].startswith(day + "T09:00")
    # POC on 2 & 3, esc-1 on 4 & 5
    assert [r["contact_role"] for r in rows_with] == ["poc", "poc", "escalation_1", "escalation_1"]
    assert rows_with[0]["contact_phone"] == "+11" and rows_with[0]["category"] == "follow_up"
    assert rows_with[2]["contact_phone"] == "+22" and rows_with[2]["category"] == "escalation"

    # Fallback: no escalation_1 -> those slots go to POC as follow_up
    rows_no = follow_ups.build_scheduled_rows(
        hub={"id": "h2", "due_date": "2026-01-01", "invoice_number": "INV",
             "client_name": "K", "amount_paise": 100000, "public_token": "t"},
        plan_id="p", tone="professional", poc=poc, esc1=None,
        business_name="A Co", public_base="https://a.co",
    )
    assert [r["contact_role"] for r in rows_no] == ["poc"] * 4
    assert [r["category"] for r in rows_no] == ["follow_up"] * 4
    assert all(r["contact_phone"] == "+11" for r in rows_no)


@pytest.mark.asyncio
async def test_dispatch_due_sends_only_ready_rows():
    hub_id, rows = await _seed_active_hub_with_schedule()
    # Only rows with scheduled_for <= cutoff should send. Use a cutoff between
    # row 2 (day 7) and row 3 (day 14).
    cutoff = "2026-01-10T00:00:00+00:00"
    sent_addrs = []

    class Fake:
        async def send_freeform(self, to, body, status_callback=None):
            sent_addrs.append(to)
            return SentMessage(provider_id="SM_" + new_id()[:6], status="queued")

    with patch("app.services.follow_ups.wa_provider", Fake()):
        summary = await follow_ups.dispatch_due(now_iso=cutoff)

    assert summary == {"sent": 2, "failed": 0, "skipped": 0, "cutoff": cutoff}
    assert sent_addrs == ["+15551234567", "+15551234567"]
    fu = await store.list_follow_up_messages_for_hub(hub_id)
    statuses = sorted([m["status"] for m in fu])
    assert statuses == ["scheduled", "scheduled", "sent", "sent"]
    wa = await store.list_whatsapp_for_hub(hub_id)
    assert len(wa) == 2 and all(m["direction"] == "outbound" for m in wa)


@pytest.mark.asyncio
async def test_dispatch_skips_paid_hub_and_records_reason():
    hub_id, _ = await _seed_active_hub_with_schedule()
    await store.update_payment_hub(hub_id, {"status": "paid"})
    cutoff = "2027-01-01T00:00:00+00:00"

    class Fake:
        async def send_freeform(self, to, body, status_callback=None):
            raise AssertionError("send must NOT be called for paid hub")

    with patch("app.services.follow_ups.wa_provider", Fake()):
        summary = await follow_ups.dispatch_due(now_iso=cutoff)

    assert summary["sent"] == 0
    assert summary["skipped"] == 4
    fu = await store.list_follow_up_messages_for_hub(hub_id)
    assert all(m["status"] == "skipped" for m in fu)
    assert all(m["skip_reason"] == "hub_status=paid" for m in fu)


@pytest.mark.asyncio
async def test_dispatch_records_failure_but_continues():
    hub_id, _ = await _seed_active_hub_with_schedule()
    cutoff = "2027-01-01T00:00:00+00:00"

    calls = {"n": 0}

    class Flaky:
        async def send_freeform(self, to, body, status_callback=None):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("twilio 500")
            return SentMessage(provider_id="SM_" + new_id()[:6], status="queued")

    with patch("app.services.follow_ups.wa_provider", Flaky()):
        summary = await follow_ups.dispatch_due(now_iso=cutoff)

    assert summary["sent"] == 3 and summary["failed"] == 1
    fu = await store.list_follow_up_messages_for_hub(hub_id)
    failed = [m for m in fu if m["status"] == "failed"]
    assert len(failed) == 1 and "twilio 500" in failed[0]["error"]


@pytest.mark.asyncio
async def test_atomic_claim_never_hands_out_same_row_twice():
    hub_id, _ = await _seed_active_hub_with_schedule()
    cutoff = "2027-01-01T00:00:00+00:00"
    seen = set()
    for _ in range(4):
        c = await store.claim_scheduled_follow_up(cutoff)
        assert c is not None
        assert c["id"] not in seen
        seen.add(c["id"])
    # No more scheduled rows to claim
    assert (await store.claim_scheduled_follow_up(cutoff)) is None
