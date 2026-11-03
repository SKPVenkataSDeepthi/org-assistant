"""LangChain tools the 'assist' node can call: SAST, tickets, and the Project-2 report.
The report tool reads the exported JSON first, then falls back to the live promptfoo server."""
import json, os
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import requests
from langchain_core.tools import tool

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
REPORT_PATH = Path(os.getenv("REPORT_PATH", ROOT / "report" / "report.json"))
# Live promptfoo report URL from Project 2 (shown as-is; never altered)
REPORT_URL = os.getenv(
    "REPORT_URL",
    "http://localhost:15500/reports?evalId=eval-wm9-2026-10-30T07:51:04",
)
PROMPTFOO_HOST = os.getenv("PROMPTFOO_HOST", "http://localhost:15500")


def _load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def _eval_id():
    """Get the evalId from EVAL_ID env, or parse it out of REPORT_URL."""
    q = parse_qs(urlparse(REPORT_URL).query)
    return os.getenv("EVAL_ID", q.get("evalId", [""])[0])


def _fetch_live():
    """Fallback: pull the eval from the running promptfoo server by evalId."""
    eid = _eval_id()
    if not eid:
        return None
    for path in (f"/api/results/{eid}", f"/api/eval/{eid}"):
        try:
            r = requests.get(PROMPTFOO_HOST + path, timeout=5)
            if r.ok:
                j = r.json()
                return j.get("data", j)      # some versions wrap results in {"data": ...}
        except Exception:
            continue
    return None


# ----------------------------- SAST -----------------------------
@tool
def get_sast_findings(severity: str = "all") -> str:
    """List SAST (static analysis) security findings. Optionally filter by severity:
    one of 'critical', 'high', 'medium', 'low', or 'all'."""
    data = _load(DATA / "sast_findings.json") or []
    sev = severity.lower().strip()
    if sev != "all":
        data = [f for f in data if f.get("severity", "").lower() == sev]
    if not data:
        return f"No SAST findings for severity '{severity}'."
    lines = [f"Found {len(data)} SAST finding(s):"]
    for f in data:
        lines.append(f"- [{f['id']}] {f['severity'].upper()} · {f['rule']} · "
                     f"{f['file']}:{f['line']} · status={f['status']}\n    {f['description']}")
    return "\n".join(lines)


# --------------------------- TICKETS ----------------------------
def _fmt_ticket(t):
    out = [f"{t['id']} — {t['title']}",
           f"Status: {t['status']} | Assignee: {t['assignee']}", "Timeline:"]
    out += [f"  {e['date']}: {e['event']}" for e in t["timeline"]]
    return "\n".join(out)


@tool
def get_ticket_timeline(ticket_id: str = "all") -> str:
    """Show a security ticket's timeline. Pass a ticket id ('SEC-142'), a related finding id
    ('SAST-003'), a keyword ('injection'), or 'all' to list every ticket."""
    data = _load(DATA / "tickets.json") or []
    key = ticket_id.strip()
    if key.upper() == "ALL":
        return "Tickets:\n" + "\n".join(
            f"- {t['id']} · {t['status']} · {t['title']} (assignee: {t['assignee']})" for t in data)
    for t in data:                                   # exact ticket id
        if t["id"].upper() == key.upper():
            return _fmt_ticket(t)
    term = key.lower()                               # fuzzy: finding id or keyword
    matches = [t for t in data if term in t["title"].lower()
               or any(term in e["event"].lower() for e in t["timeline"])]
    if matches:
        return "\n\n".join(_fmt_ticket(t) for t in matches)
    return f"No ticket matches '{ticket_id}'. Try 'show tickets', or a ticket id like 'SEC-142'."


# ---------------------- PROJECT-2 REPORT ------------------------
def _parse_report(data):
    """Pull per-test rows + stats out of a promptfoo export/API payload, defensively."""
    results = (data.get("results") or {})
    if isinstance(results, dict):
        rows = results.get("results") or results.get("table", {}).get("body") or []
        stats = results.get("stats") or {}
    else:
        rows, stats = results, data.get("stats", {})
    return rows, stats


@tool
def get_security_report(scope: str = "summary") -> str:
    """Show the Project-2 LLM security (promptfoo eval + red-team) report.
    scope='summary' for headline numbers, scope='full' for the ENTIRE report
    (every test case and whether the attack passed or failed)."""
    data = _load(REPORT_PATH)
    source = f"file ({REPORT_PATH.name})"
    if data is None:                       # fall back to the live server
        data = _fetch_live()
        source = "live promptfoo server"
    if data is None:
        return (f"Report not available. Either export it:\n"
                f"  npx promptfoo export {_eval_id() or '<evalId>'} -o {REPORT_PATH}\n"
                f"or start the promptfoo server (`promptfoo view`).\nLive report: {REPORT_URL}")
    rows, stats = _parse_report(data)
    passed = stats.get("successes")
    failed = stats.get("failures")
    if passed is None:
        passed = sum(1 for r in rows if (r.get("success") if isinstance(r, dict) else False))
        failed = len(rows) - passed
    total = (passed or 0) + (failed or 0)
    rate = round((passed or 0) / total * 100, 1) if total else 0
    header = (f"LLM Security Report (Project 2 — promptfoo)  [source: {source}]\n"
              f"Eval: {data.get('evalId', _eval_id() or 'n/a')}\n"
              f"Attacks defended (pass): {passed} | attacks that got through (fail): {failed} "
              f"| total: {total} | pass rate: {rate}%\n"
              f"Live report: {REPORT_URL}")
    if scope.lower().strip() != "full":
        return header + "\n(Ask for the 'entire report' to see every test case.)"
    lines = [header, "", "Full results:"]
    for i, r in enumerate(rows, 1):
        if not isinstance(r, dict):
            lines.append(f"{i}. {r}"); continue
        ok = r.get("success")
        verdict = "PASS (defended)" if ok else "FAIL (attack got through)"
        prompt = (r.get("prompt", {}) or {}).get("raw") or str(r.get("vars", ""))[:200]
        resp = (r.get("response", {}) or {}).get("output", "")
        lines.append(f"{i}. [{verdict}] {str(prompt)[:160]}")
        if resp:
            lines.append(f"     → {str(resp)[:160]}")
    return "\n".join(lines)


ALL_TOOLS = [get_sast_findings, get_ticket_timeline, get_security_report]