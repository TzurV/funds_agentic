"""LangGraph definition — deterministic pipeline graph without LLMs.
Each node is a python function that takes/returns a {"state": ...} dict.
"""
from __future__ import annotations
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from .nodes.config_node import config_node
from .nodes.input_node import input_node
from .nodes.browser_node import browser_node
from .nodes.sectors_node import sectors_node
from .nodes.funds_node import funds_node
from .nodes.normalize_write_node import normalize_write_node


def build_graph():
    g = StateGraph(dict)
    g.add_node("config_node", config_node)
    g.add_node("input_node", input_node)
    g.add_node("browser_node", browser_node)
    g.add_node("sectors_node", sectors_node)
    g.add_node("funds_node", funds_node)
    g.add_node("normalize_write_node", normalize_write_node)

    g.set_entry_point("config_node")
    g.add_edge("config_node", "input_node")
    g.add_edge("input_node", "browser_node")
    g.add_edge("browser_node", "sectors_node")
    g.add_edge("sectors_node", "funds_node")
    g.add_edge("funds_node", "normalize_write_node")
    g.add_edge("normalize_write_node", END)

    return g.compile()
