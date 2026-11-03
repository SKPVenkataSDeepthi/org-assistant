"""Terminal chat loop. Shows which category each message was routed to."""
from langchain_core.messages import HumanMessage
from agent_graph import GRAPH

def main():
    print("Internal Org Assistant (type 'exit' to quit)")
    print("Try: 'hi' · 'what's the weather' · 'what is SAST?' · 'show critical SAST findings' · "
          "'timeline for SEC-142' · 'show the entire security report'\n")
    history = []
    while True:
        try:
            user = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user.lower() in {"exit", "quit"}:
            break
        if not user:
            continue
        history.append(HumanMessage(user))
        state = GRAPH.invoke({"messages": history, "category": ""})
        history = state["messages"]            # keep conversation memory
        reply = state["messages"][-1].content
        print(f"[routed → {state['category']}]")
        print(f"bot > {reply}\n")

if __name__ == "__main__":
    main()