"""FastAPI backend + HTML chat UI for the LangGraph agent."""
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage
from agent_graph import GRAPH

app = FastAPI(title="Org Assistant")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
HERE = Path(__file__).resolve().parent


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []     # [{"role":"user"/"assistant","content":...}]


def to_messages(history):
    out = []
    for h in history:
        out.append(HumanMessage(h["content"]) if h["role"] == "user" else AIMessage(h["content"]))
    return out


@app.get("/")
def home():
    return FileResponse(HERE / "chat.html")


@app.post("/chat")
def chat(req: ChatRequest):
    msgs = to_messages(req.history) + [HumanMessage(req.message)]
    state = GRAPH.invoke({"messages": msgs, "category": ""})
    return {"category": state["category"], "reply": state["messages"][-1].content}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)