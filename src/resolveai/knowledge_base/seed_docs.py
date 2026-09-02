"""Seed policy/runbook documents for the demo knowledge base.

In production these would be synced from a real docs source (Confluence,
Notion, a CMS) via an ingestion pipeline -- out of scope for V1, tracked in
the README roadmap. For now they're static so the retrieval layer and evals
have something real to index.
"""

from __future__ import annotations

from resolveai.retrieval.hybrid_retriever import KnowledgeDoc

SEED_DOCS: list[KnowledgeDoc] = [
    KnowledgeDoc(
        doc_id="policy-refunds-001",
        title="Refund Policy",
        text=(
            "Customers are eligible for a full refund if a defective or incorrect item is reported "
            "within 30 days of delivery. Refunds are issued to the original payment method within "
            "3-5 business days of approval. A refund requires either (a) a confirmed defect reported "
            "by the customer, or (b) a support agent verifying the order was charged but the item was "
            "never fulfilled."
        ),
    ),
    KnowledgeDoc(
        doc_id="policy-shipping-002",
        title="Shipping & Delivery SLAs",
        text=(
            "Standard shipping SLA is 3-7 business days. An order is considered 'not received' if the "
            "carrier tracking shows no movement for 5+ business days past the SLA window, or tracking "
            "shows 'delivered' but the customer disputes receipt. In either case, support should verify "
            "tracking status via the ticketing system before resending or refunding."
        ),
    ),
    KnowledgeDoc(
        doc_id="policy-account-003",
        title="Account Access & Lockouts",
        text=(
            "Accounts are automatically locked after 5 failed login attempts within 15 minutes, as a "
            "fraud-prevention measure. Support can reset access after confirming the customer's identity "
            "against the CRM record (name + email or phone match). Do not reset access without an identity "
            "match on file."
        ),
    ),
    KnowledgeDoc(
        doc_id="policy-billing-004",
        title="Billing Discrepancies",
        text=(
            "Duplicate charges most commonly result from a retried payment after a timeout on the "
            "customer's bank side. Before correcting a billing discrepancy, confirm via the CRM's "
            "transaction history that two charges exist for the same order ID and amount. If confirmed, "
            "the duplicate charge should be reversed, not the original."
        ),
    ),
    KnowledgeDoc(
        doc_id="runbook-escalation-005",
        title="When to Escalate to a Human Agent",
        text=(
            "Escalate to a human agent whenever evidence is insufficient to confirm the customer's claim, "
            "the requested action exceeds $500 in value, or the customer explicitly requests a human. "
            "Low-confidence automated resolutions erode trust faster than a slower, correct one."
        ),
    ),
]
