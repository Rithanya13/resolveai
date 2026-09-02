"""Assembles the ResolveAI incident-resolution graph.

    START -> classify -> retrieve -> gather_evidence -> assess
                                                            |
                                          (confidence gate) +--> resolve --(value gate)--> execute_action -> finalize -> END
                                                            |                    \\
                                                            +--> human_review <---+
                                                                      |
                                                     (interrupt / resume) -> execute_action | finalize

Both places an agent could act unsupervised -- a low-confidence read of the
evidence, or a resolution whose dollar value crosses the auto-approve limit
-- route through the same `human_review` interrupt node instead of a second,
divergent code path. One HITL mechanism, two triggers.
"""

from __future__ import annotations

from functools import partial

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from resolveai.graph.nodes import (
    GraphDeps,
    assess_node,
    classify_node,
    execute_action_node,
    finalize_node,
    gather_evidence_node,
    human_review_node,
    resolve_node,
    retrieve_node,
    route_after_assess,
    route_after_human_review,
    route_after_resolve,
)
from resolveai.graph.state import IncidentState


def build_graph(deps: GraphDeps, checkpointer: BaseCheckpointSaver | None = None):
    graph = StateGraph(IncidentState)

    graph.add_node("classify", partial(classify_node, deps=deps))
    graph.add_node("retrieve", partial(retrieve_node, deps=deps))
    graph.add_node("gather_evidence", partial(gather_evidence_node, deps=deps))
    graph.add_node("assess", partial(assess_node, deps=deps))
    graph.add_node("resolve", partial(resolve_node, deps=deps))
    graph.add_node("human_review", partial(human_review_node, deps=deps))
    graph.add_node("execute_action", partial(execute_action_node, deps=deps))
    graph.add_node("finalize", partial(finalize_node, deps=deps))

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "retrieve")
    graph.add_edge("retrieve", "gather_evidence")
    graph.add_edge("gather_evidence", "assess")
    graph.add_conditional_edges("assess", route_after_assess, {"resolve": "resolve", "human_review": "human_review"})
    graph.add_conditional_edges(
        "resolve", route_after_resolve, {"execute_action": "execute_action", "human_review": "human_review"}
    )
    graph.add_conditional_edges(
        "human_review", route_after_human_review, {"execute_action": "execute_action", "finalize": "finalize"}
    )
    graph.add_edge("execute_action", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=checkpointer)
