"""Static message templates for the follow-up engine. No LLM at runtime —
we pick a template by (tone, category) and do plain `{var}` substitution.
Tones: professional | warm | firm. Categories: initial | follow_up | escalation.

Every template is authored for WhatsApp (short, single-thread, no HTML)."""
from datetime import date, datetime, timezone


def _fmt_inr(paise: int | None) -> str:
    if not paise:
        return "₹0"
    rupees = paise / 100
    # Indian number formatting: 1,00,000 style
    whole = f"{int(rupees):,}"
    return f"₹{whole}"


def _first_name(full: str | None) -> str:
    if not full:
        return "there"
    return full.strip().split()[0]


def _days_between(due_date_str: str | None) -> int:
    if not due_date_str:
        return 0
    try:
        due = datetime.strptime(due_date_str, "%Y-%m-%d").date()
    except ValueError:
        return 0
    today = datetime.now(timezone.utc).date()
    return (today - due).days  # positive = overdue


TEMPLATES: dict[tuple[str, str], str] = {
    # --- PROFESSIONAL --------------------------------------------------------
    ("professional", "initial"): (
        "Hi {client_first_name},\n\n"
        "Quick reminder from {business_name}: invoice {invoice_number} for {amount} "
        "was due on {due_date}.\n\n"
        "You can review and pay here: {payment_link}\n\n"
        "Let me know if you need anything.\n"
        "— {business_name}"
    ),
    ("professional", "follow_up"): (
        "Hi {client_first_name},\n\n"
        "Following up on invoice {invoice_number} ({amount}) — it's now "
        "{days_overdue} days past due.\n\n"
        "Pay or update us here: {payment_link}\n\n"
        "If it's already paid, please share the reference so we can close it out."
    ),
    ("professional", "escalation"): (
        "Hi {escalation_first_name},\n\n"
        "Reaching out because we haven't heard back from {client_first_name} about "
        "invoice {invoice_number} ({amount}), due {due_date}.\n\n"
        "Could you help move this along? {payment_link}"
    ),
    # --- WARM ---------------------------------------------------------------
    ("warm", "initial"): (
        "Hey {client_first_name},\n\n"
        "Just a friendly nudge — invoice {invoice_number} for {amount} was due "
        "{due_date}. All good on your end?\n\n"
        "Here's the payment page whenever you're ready: {payment_link}\n\n"
        "Cheers,\n"
        "{business_name}"
    ),
    ("warm", "follow_up"): (
        "Hey {client_first_name},\n\n"
        "Circling back on {invoice_number} ({amount}) — {days_overdue} days past "
        "its due date now. No stress, just want to make sure it's not stuck "
        "somewhere.\n\n"
        "Pay or update anytime: {payment_link}"
    ),
    ("warm", "escalation"): (
        "Hey {escalation_first_name}!\n\n"
        "Sorry to loop you in — trying to close out invoice {invoice_number} "
        "({amount}) for {business_name}. It's been overdue for a bit and we "
        "haven't heard from {client_first_name}.\n\n"
        "Any chance you can nudge or take a look? {payment_link}"
    ),
    # --- FIRM ---------------------------------------------------------------
    ("firm", "initial"): (
        "{client_first_name},\n\n"
        "Invoice {invoice_number} for {amount} was due on {due_date}. Please "
        "settle today: {payment_link}\n\n"
        "If there's an issue, reply so we can sort it."
    ),
    ("firm", "follow_up"): (
        "{client_first_name},\n\n"
        "Invoice {invoice_number} ({amount}) is now {days_overdue} days overdue.\n\n"
        "Please pay or reply with a firm date today: {payment_link}"
    ),
    ("firm", "escalation"): (
        "{escalation_first_name},\n\n"
        "Escalating: invoice {invoice_number} ({amount}) for {business_name} is "
        "{days_overdue} days past due and unresolved with {client_first_name}.\n\n"
        "Please intervene: {payment_link}"
    ),
}

TONES = ("professional", "warm", "firm")
CATEGORIES = ("initial", "follow_up", "escalation")


def render(tone: str, category: str, hub: dict, poc: dict | None,
           escalation: dict | None, business_name: str, public_base: str) -> str:
    """Render a template by substituting hub + contact fields. Missing values
    fall back to soft placeholders so the preview always renders something."""
    key = (tone, category)
    if key not in TEMPLATES:
        raise ValueError(f"unknown_template:{tone}/{category}")
    days = _days_between(hub.get("due_date"))
    ctx = {
        "business_name": business_name or "your team",
        "client_first_name": _first_name((poc or {}).get("name") or hub.get("client_name")),
        "escalation_first_name": _first_name((escalation or {}).get("name")) if escalation else "there",
        "invoice_number": hub.get("invoice_number") or "—",
        "amount": _fmt_inr(hub.get("amount_paise")),
        "due_date": hub.get("due_date") or "the due date",
        "days_overdue": max(days, 0),
        "payment_link": f"{public_base.rstrip('/')}/hub/{hub.get('public_token','')}",
    }
    return TEMPLATES[key].format(**ctx)
