"""In-memory mock enterprise data backing the MCP tool servers.

Stands in for a real CRM/ticketing/order system. Swapping this module for a
real API client is the only change needed to point the same MCP tool
interface at production systems -- the graph and the MCP protocol layer
don't change.
"""

from __future__ import annotations

CUSTOMERS: dict[str, dict] = {
    "cust_1001": {
        "customer_id": "cust_1001",
        "name": "Jordan Alvarez",
        "email": "jordan.alvarez@example.com",
        "phone": "+1-555-0101",
        "orders": ["order_5001"],
    },
    "cust_1002": {
        "customer_id": "cust_1002",
        "name": "Priya Nair",
        "email": "priya.nair@example.com",
        "phone": "+1-555-0102",
        "orders": ["order_5002", "order_5003"],
    },
    "cust_1003": {
        "customer_id": "cust_1003",
        "name": "Sam Whitfield",
        "email": "sam.whitfield@example.com",
        "phone": "+1-555-0103",
        "orders": [],
    },
    "cust_1004": {
        "customer_id": "cust_1004",
        "name": "Morgan Feld",
        "email": "morgan.feld@example.com",
        "phone": "+1-555-0104",
        "orders": ["order_5004"],
    },
}

ORDERS: dict[str, dict] = {
    "order_5001": {
        "order_id": "order_5001",
        "customer_id": "cust_1001",
        "amount_usd": 84.99,
        "status": "shipped",
        "tracking_status": "no movement for 7 business days past SLA",
    },
    "order_5002": {
        "order_id": "order_5002",
        "customer_id": "cust_1002",
        "amount_usd": 42.50,
        "status": "delivered",
        "tracking_status": "delivered",
    },
    "order_5003": {
        "order_id": "order_5003",
        "customer_id": "cust_1002",
        "amount_usd": 42.50,
        "status": "delivered",
        "tracking_status": "delivered",
    },
    "order_5004": {
        "order_id": "order_5004",
        "customer_id": "cust_1004",
        "amount_usd": 899.00,
        "status": "shipped",
        "tracking_status": "no movement for 9 business days past SLA",
    },
}

TICKETS: dict[str, list[dict]] = {
    "cust_1001": [
        {"ticket_id": "tkt_9001", "subject": "Order hasn't arrived", "status": "open"},
    ],
    "cust_1002": [
        {"ticket_id": "tkt_9002", "subject": "Charged twice for one order", "status": "open"},
    ],
    "cust_1003": [],
    "cust_1004": [
        {"ticket_id": "tkt_9003", "subject": "High-value order never arrived", "status": "open"},
    ],
}
