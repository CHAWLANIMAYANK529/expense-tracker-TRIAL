"""Monthly budget compared with spending. No advice is generated."""

WARNING_RATIO = 0.8


def budget_snapshot(spent, budget_amount):
    """Compare spending with a monthly budget.

    Remaining is budget minus spent, so it is negative once the budget is passed.
    The warning and exceeded states follow the percentage shown on the page,
    so a figure that rounds to 80% or 100% uses that message.
    The message reports the percentage; it does not suggest what to buy.
    """
    spent = round(float(spent or 0), 2)
    budget_amount = round(float(budget_amount or 0), 2)
    if budget_amount <= 0:
        return {
            "configured": False,
            "amount": 0.0,
            "spent": spent,
            "remaining": None,
            "percent": None,
            "bar_width": 0,
            "level": "none",
            "message": None,
        }

    remaining = round(budget_amount - spent, 2)
    percent = int(round(spent / budget_amount * 100))
    warning_percent = int(WARNING_RATIO * 100)
    if percent >= 100:
        level = "exceeded"
        message = "Your monthly budget has been exceeded."
    elif percent >= warning_percent:
        level = "warning"
        message = f"You have used {percent}% of your monthly budget."
    else:
        level = "ok"
        message = None
    return {
        "configured": True,
        "amount": budget_amount,
        "spent": spent,
        "remaining": remaining,
        "percent": percent,
        "bar_width": max(0, min(percent, 100)),
        "level": level,
        "message": message,
    }
