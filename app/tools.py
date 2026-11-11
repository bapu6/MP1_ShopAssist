"""ShopAssist's tools - YOU own this file.

Three tools, all READ-ONLY: they look things up and check rules. None of them cancels, refunds or changes anything -
actions that change data need a human approval step (Module 6), so customers do those on the website.

Remember Session 21, Section 7: type hints catch "abc", but they don't catch a WRONG VALUE. A tool that gets a
nonsense argument must RAISE ValueError with a message that says what's wrong. agent.run_tool() turns that into an
"INVALID: ..." message for the model, so the model asks the customer instead of guessing (S20's Fix B).
"""
import json
import re
from datetime import date
from pathlib import Path

from langchain_core.tools import tool

DATA = json.loads((Path(__file__).resolve().parents[1] / "data" / "orders.json").read_text(encoding="utf-8"))
ORDERS = {o["order_id"]: o for o in DATA["orders"]}
TODAY = date.fromisoformat(DATA["store_today"])          # fixed, so every run gives the same answers

RETURN_WINDOW_DAYS = 10                                  # normal returns: within 10 days of delivery
DAMAGED_WINDOW_DAYS = 30                                 # damaged / defective / wrong item: within 30 days
NON_RETURNABLE = {"innerwear", "groceries", "gift_cards"}
REASONS = {"wrong_size", "changed_mind", "damaged", "defective", "wrong_item", "not_as_described"}
ORDER_ID = re.compile(r"^ORD-\d{5}$")
METRO_PREFIXES = {"11", "40", "50", "56", "60", "70"}    # Delhi, Mumbai, Hyderabad, Bengaluru, Chennai, Kolkata


def _find(order_id: str) -> dict:
    """Look an order up. Raises ValueError for bad format or non-existent order."""
    if not ORDER_ID.match(order_id):
        raise ValueError(f"order_id must look like ORD-12345, got {order_id!r}")
    if order_id not in ORDERS:
        raise ValueError(f"no order {order_id} - ask the customer to check the order number")
    return ORDERS[order_id]


@tool(parse_docstring=True)
def get_order_status(order_id: str) -> dict:
    """Status of ONE order: placed, shipped, out for delivery, delivered or cancelled, with its dates. Use when the
    customer asks where their order is or when it will arrive. Do NOT use it for general policy questions.

    Args:
        order_id: the order number exactly as the customer gave it, e.g. ORD-10233
    """
    o = _find(order_id)
    keys = ("order_id", "item", "status", "ordered_on", "delivered_on", "expected_delivery", "cancelled_on")
    return {k: o[k] for k in keys if k in o} | {"store_today": TODAY.isoformat()}


@tool(parse_docstring=True)
def get_delivery_estimate(pincode: str, speed: str = "standard") -> dict:
    """How many working days delivery takes to an Indian pincode, and what it costs. Use when the customer asks how
    long delivery will take to their area, or the price of express delivery.

    Args:
        pincode: the 6-digit Indian postal code, e.g. 500081
        speed: "standard" or "express"
    """
    if not (len(pincode) == 6 and pincode.isdigit()):
        raise ValueError(f"pincode must be exactly 6 digits, got {pincode!r}")
    if speed not in ("standard", "express"):
        raise ValueError(f"speed must be 'standard' or 'express', got {speed!r}")
    metro = pincode[:2] in METRO_PREFIXES
    if speed == "express":
        return {"pincode": pincode, "speed": "express", "days": "next day" if metro else "2-3 working days",
                "charge_rupees": 99}
    return {"pincode": pincode, "speed": "standard", "days": "2-3 working days" if metro else "4-6 working days",
            "charge_rupees": 0, "note": "free standard delivery on orders above Rs 499; Rs 49 below that"}


@tool(parse_docstring=True)
def check_return_eligibility(order_id: str, reason: str) -> dict:
    """Check if an order can be returned under Northwind Store's return policy. Use when a customer asks whether
    they can return an item, or wants to initiate a return for a delivered order. Do NOT use it for general return
    policy questions.

    Args:
        order_id: the order number in ORD-12345 format, e.g. ORD-10231
        reason: customer's reason for return ('wrong_size', 'changed_mind', 'damaged', 'defective', 'wrong_item', 'not_as_described')
    """
    if reason not in REASONS:
        raise ValueError(f"reason must be one of {sorted(REASONS)}, got {reason!r}")
    o = _find(order_id)
    if o.get("status") != "delivered":
        return {"eligible": False, "why": f"not delivered yet (status is {o.get('status')})"}
    if o.get("category") in NON_RETURNABLE:
        return {"eligible": False, "why": f"{o['category']} is non-returnable"}
    window = DAMAGED_WINDOW_DAYS if reason in {"damaged", "defective", "wrong_item"} else RETURN_WINDOW_DAYS
    days = (TODAY - date.fromisoformat(o["delivered_on"])).days
    if days > window:
        return {"eligible": False, "why": f"delivered {days} days ago; window is {window} days"}
    return {
        "eligible": True,
        "days_since_delivery": days,
        "window_days": window,
        "refund_rupees": o["price"],
        "how": "start the return on the website: My Orders > Return",
    }


TOOLS = {"get_order_status": get_order_status, "get_delivery_estimate": get_delivery_estimate,
         "check_return_eligibility": check_return_eligibility}
