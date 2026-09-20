"""Auth: neutral login responses, rate limits, expiry/lockout, invite single-use."""
from datetime import timedelta

import pytest

from app.models import InviteRequestIn
from app.repositories import store
from app.services import auth, leads
from app.util import gen_token, hash_secret, iso, new_id, utcnow


async def _make_active_user(email):
    await store.db.users.delete_many({"email": email})
    uid = new_id()
    await store.db.users.insert_one(
        {"_id": uid, "id": uid, "email": email, "full_name": "T", "mobile": "+919000000000",
         "status": "active", "created_at": iso()}
    )
    return uid


@pytest.mark.asyncio
async def test_neutral_login_message_identical():
    await store.db.rate_limits.delete_many({})
    known = "known_" + new_id()[:6] + "@x.com"
    await _make_active_user(known)
    r_known = await auth.request_code(known, "1.1.1.1")
    r_unknown = await auth.request_code("nobody_" + new_id()[:6] + "@x.com", "1.1.1.2")
    assert r_known == r_unknown == {"message": auth.NEUTRAL_MESSAGE}


@pytest.mark.asyncio
async def test_wrong_code_locks_after_5():
    await store.db.rate_limits.delete_many({})
    await store.db.auth_otps.delete_many({})
    email = "lock_" + new_id()[:6] + "@x.com"
    await _make_active_user(email)
    await auth.request_code(email, "2.2.2.2")
    for _ in range(5):
        with pytest.raises(ValueError):
            await auth.verify_code(email, "000000", "2.2.2.3")
    otp = await store.db.auth_otps.find_one({"email": email, "active": True})
    assert otp["attempts"] >= 5 and otp["locked_until"] is not None


@pytest.mark.asyncio
async def test_new_code_cancels_old():
    await store.db.rate_limits.delete_many({})
    await store.db.auth_otps.delete_many({})
    email = "cancel_" + new_id()[:6] + "@x.com"
    await _make_active_user(email)
    await auth.request_code(email, "3.3.3.3")
    first = await store.db.auth_otps.find_one({"email": email, "active": True})
    await auth.request_code(email, "3.3.3.3")
    assert await store.db.auth_otps.count_documents({"email": email, "active": True}) == 1
    still = await store.db.auth_otps.find_one({"_id": first["_id"]})
    assert still["active"] is False


@pytest.mark.asyncio
async def test_suspended_user_gets_no_code():
    await store.db.rate_limits.delete_many({})
    await store.db.auth_otps.delete_many({})
    email = "susp_" + new_id()[:6] + "@x.com"
    uid = await _make_active_user(email)
    await store.db.users.update_one({"_id": uid}, {"$set": {"status": "suspended"}})
    await auth.request_code(email, "4.4.4.4")
    assert await store.db.auth_otps.count_documents({"email": email, "active": True}) == 0


@pytest.mark.asyncio
async def test_invite_rate_limit_and_dedupe():
    await store.db.rate_limits.delete_many({})
    ip = "9.9.9.10"
    base = "biz_" + new_id()[:6]
    limited = 0
    for i in range(6):
        p = InviteRequestIn(full_name="A", business_name="B", work_email=f"{base}{i}@x.com",
                            mobile="+919000000000", business_type="consulting")
        try:
            await leads.submit_lead(p, ip)
        except ValueError as e:
            if str(e) == "rate_limited":
                limited += 1
    assert limited >= 1

    await store.db.rate_limits.delete_many({})
    dup_email = f"dup_{base}@x.com"
    p = InviteRequestIn(full_name="A", business_name="B", work_email=dup_email,
                        mobile="+919000000000", business_type="consulting")
    await leads.submit_lead(p, "8.8.8.8")
    await leads.submit_lead(p, "8.8.8.8")
    assert await store.db.waitlist_leads.count_documents({"work_email": dup_email}) == 1


@pytest.mark.asyncio
async def test_manual_review_for_other_business_type():
    await store.db.rate_limits.delete_many({})
    email = f"other_{new_id()[:6]}@x.com"
    p = InviteRequestIn(full_name="A", business_name="B", work_email=email,
                        mobile="+919000000000", business_type="other")
    await leads.submit_lead(p, "7.7.7.7")
    lead = await store.db.waitlist_leads.find_one({"work_email": email})
    assert lead["status"] == "manual_review"


@pytest.mark.asyncio
async def test_honeypot_stores_nothing():
    await store.db.rate_limits.delete_many({})
    email = f"honey_{new_id()[:6]}@x.com"
    p = InviteRequestIn(full_name="A", business_name="B", work_email=email,
                        mobile="+919000000000", business_type="consulting", company_website="http://spam")
    res = await leads.submit_lead(p, "6.6.6.6")
    assert res["message"] == leads.CONFIRM_MESSAGE
    assert await store.db.waitlist_leads.count_documents({"work_email": email}) == 0


@pytest.mark.asyncio
async def test_expired_and_reused_invite():
    email = f"inv_{new_id()[:6]}@x.com"
    await store.db.waitlist_leads.delete_many({"work_email": email})
    await store.db.users.delete_many({"email": email})
    token = gen_token(32)
    lead = {
        "id": new_id(), "full_name": "A", "business_name": "B", "work_email": email,
        "mobile": "+919000000000", "business_type": "consulting", "city_state": "",
        "monthly_invoice_volume": "", "udyam_number": None, "status": "approved",
        "invite_token_hash": hash_secret(token),
        "invite_expires_at": iso(utcnow() + timedelta(days=7)), "created_at": iso(),
    }
    await store.db.waitlist_leads.insert_one({**lead, "_id": lead["id"]})
    result = await leads.consume_invite(token)
    assert result["user"]["email"] == email
    with pytest.raises(ValueError):
        await leads.consume_invite(token)

    email2 = f"exp_{new_id()[:6]}@x.com"
    token2 = gen_token(32)
    lead2 = {**lead, "id": new_id(), "work_email": email2, "invite_token_hash": hash_secret(token2),
             "invite_expires_at": iso(utcnow() - timedelta(days=1)), "status": "approved"}
    await store.db.waitlist_leads.insert_one({**lead2, "_id": lead2["id"]})
    with pytest.raises(ValueError):
        await leads.consume_invite(token2)
