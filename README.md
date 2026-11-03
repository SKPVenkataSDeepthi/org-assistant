# Org Assistant (LangGraph + LangChain + Ollama)
Internal agentic assistant. Routes each message to chitchat / irrelevant / guidance / assist,
and answers only: SAST findings, security ticket timelines, and the Project-2 LLM security report.

## Run
1. Start Ollama (`ollama pull llama3.2`).
2. Export the Project-2 report to `report/report.json`:
   npx promptfoo export <evalId> -o report/report.json
3. `pip install -r requirements.txt`
4. Terminal mode: `python cli.py`
   Web mode: `python backend.py` then `streamlit run frontend.py`

## Routing
- chitchat  — greetings/small talk
- irrelevant — off-policy, politely refused
- guidance  — explains how (no data lookup)
- assist    — fetches SAST / ticket / report data via LangChain tools