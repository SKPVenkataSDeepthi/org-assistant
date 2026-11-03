"""LangGraph router: deterministic classification + deterministic tool dispatch,
so the report is shown exactly as promptfoo produced it (no paraphrasing/hallucination)."""
import re
from typing import TypedDict, Annotated, Literal
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from tools import get_sast_findings, get_ticket_timeline, get_security_report

MODEL = "llama3.2"
llm = ChatOllama(model=MODEL, temperature=0.1)
CATEGORIES = ["chitchat", "irrelevant", "guidance", "assist"]

class ChatState(TypedDict):
    messages: Annotated[list, add_messages]
    category: str

# ---------- 1. classifier: deterministic rules first, LLM only for the fuzzy cases ----------
GUIDANCE_PAT = ["how do i", "how to", "what is", "what are", "what does", "what's a",
                "whats a", "explain", "define", "difference between", "meaning of"]
ASSIST_PAT   = ["show", "list", "display", "give me", "pull up", "fetch", "get me",
                "timeline", "report", "finding", "findings", "status of", "tickets"]

CLASSIFY_PROMPT = """Classify this message for an INTERNAL company assistant that only covers
SAST findings, security ticket timelines, and the LLM security report.
Reply with ONE word only: chitchat, irrelevant, guidance, or assist.
- chitchat: greetings, thanks, small talk.
- irrelevant: anything off-policy (weather, jokes, general knowledge, customer requests).
Message: "{message}"
Answer:"""

def classify(state: ChatState):
    t = state["messages"][-1].content.lower().strip()
    # Clear "do a task / fetch data" signals  → assist
    if any(p in t for p in ASSIST_PAT) or re.search(r"\b(sec|sast|cwe)-\d+", t):
        # but "what is a SAST finding" is a definition → guidance
        if any(p in t for p in ["what is", "what are", "what's a", "whats a", "explain", "define"]):
            return {"category": "guidance"}
        return {"category": "assist"}
    # Clear "explain / how-to" signals → guidance
    if any(p in t for p in GUIDANCE_PAT):
        return {"category": "guidance"}
    # Everything else (greetings vs off-topic) → let the LLM decide
    raw = llm.invoke(CLASSIFY_PROMPT.format(message=t)).content.strip().lower()
    return {"category": next((c for c in ["chitchat", "irrelevant"] if c in raw), "irrelevant")}

def route(state: ChatState) -> Literal["chitchat", "irrelevant", "guidance", "assist"]:
    return state["category"]

# ---------- 2. branch nodes ----------
def chitchat(state: ChatState):
    sys = SystemMessage("You are a friendly internal company assistant. Reply in ONE short sentence, "
                        "then remind the user you help with SAST findings, ticket timelines, and the security report.")
    return {"messages": [llm.invoke([sys] + state["messages"][-1:])]}

def irrelevant(state: ChatState):
    return {"messages": [AIMessage(
        "That's outside what I can help with. I'm an internal assistant limited to SAST security "
        "findings, security ticket timelines, and the LLM security report. "
        "Try: “show critical SAST findings” or “timeline for SEC-142”.")]}

GUIDANCE_SYS = """You are an internal company assistant. Explain CONCEPTS and HOW-TO only, in scope
(SAST findings, ticket timelines, the LLM security report). Keep it to a few sentences.
NEVER invent or state specific findings, ticket IDs, dates, numbers, or report results.
If the user wants actual data, tell them to ask directly (e.g. 'show critical SAST findings' or
'timeline for SEC-142') and the system will fetch it."""

def guidance(state: ChatState):
    return {"messages": [llm.invoke([SystemMessage(GUIDANCE_SYS)] + state["messages"][-1:])]}

def assist(state: ChatState):
    """Deterministic dispatch: pick the tool from keywords, return its output VERBATIM."""
    t = state["messages"][-1].content.lower()
    if "report" in t:
        scope = "full" if any(w in t for w in ["entire", "full", "all", "complete", "everything", "detailed"]) else "summary"
        out = get_security_report.invoke({"scope": scope})
    elif "timeline" in t or "ticket" in t or re.search(r"\b(sec|sast|cwe)-\d+", t):
        m = re.search(r"\b((?:sec|sast|cwe)-\d+)", t, re.I)
        out = get_ticket_timeline.invoke({"ticket_id": m.group(1) if m else "all"})
    elif "sast" in t or "finding" in t or "vulnerab" in t:
        sev = next((s for s in ["critical", "high", "medium", "low"] if s in t), "all")
        out = get_sast_findings.invoke({"severity": sev})
    else:
        out = ("I can fetch three things: SAST findings (“show critical SAST findings”), "
               "a ticket timeline (“timeline for SEC-142”), or the security report "
               "(“show the entire security report”).")
    return {"messages": [AIMessage(out)]}

# ---------- 3. build graph ----------
def build_graph():
    g = StateGraph(ChatState)
    for name, fn in [("classify", classify), ("chitchat", chitchat),
                     ("irrelevant", irrelevant), ("guidance", guidance), ("assist", assist)]:
        g.add_node(name, fn)
    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", route,
                            {"chitchat": "chitchat", "irrelevant": "irrelevant",
                             "guidance": "guidance", "assist": "assist"})
    for n in ["chitchat", "irrelevant", "guidance", "assist"]:
        g.add_edge(n, END)
    return g.compile()

GRAPH = build_graph()