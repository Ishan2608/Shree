"""
test_agent.py — Artha Automated Agent Test Runner
===================================================
Run from the project root:
    python tests/scripts/test_agent.py

Fires 5 predefined prompts at the agent in a single session,
checks each response against expected signals, prints results live,
and saves a full log to tests/logs/agent_test_YYYYMMDD_HHMMSS.md

Pass criteria per prompt:
  - Response is non-empty
  - Minimum length (guards against empty/error replies)
  - At least one expected keyword present in the response
  - No hard error phrases ("I cannot", "I don't have access", "error")
  - Optional: data block present (for chart-expected prompts)

Exit code: 0 if all pass, 1 if any fail.
"""

import sys
import os
import asyncio
import json
import re
import time
import textwrap
from datetime import datetime

# ── Path bootstrap ─────────────────────────────────────────────────────────────
_HERE         = os.path.dirname(os.path.abspath(__file__))
_TESTS_DIR    = os.path.dirname(_HERE)
_PROJECT_ROOT = os.path.dirname(_TESTS_DIR)
sys.path.insert(0, _PROJECT_ROOT)
_LOGS_DIR = os.path.join(_TESTS_DIR, "logs")
# ──────────────────────────────────────────────────────────────────────────────

# ── Colorama ──────────────────────────────────────────────────────────────────
try:
    from colorama import init as _cinit, Fore, Back, Style
    _cinit(autoreset=True)
except ImportError:
    class Fore:
        CYAN=MAGENTA=WHITE=RED=GREEN=YELLOW=LIGHTCYAN_EX=LIGHTMAGENTA_EX=\
        LIGHTWHITE_EX=LIGHTYELLOW_EX=LIGHTGREEN_EX=LIGHTRED_EX=BLACK=RESET=""
    class Back:
        CYAN=MAGENTA=RED=GREEN=BLUE=BLACK=YELLOW=RESET=""
    class Style:
        BRIGHT=DIM=RESET_ALL=NORMAL=""

# ── Theme: Neon Dusk (same as test_tools / test_run) ─────────────────────────
TEAL      = Style.BRIGHT + Fore.CYAN
SOFT_TEAL = Fore.CYAN
DIM_TEAL  = Style.DIM   + Fore.CYAN
LIME      = Style.BRIGHT + Fore.LIGHTGREEN_EX
CORAL     = Style.BRIGHT + Fore.LIGHTYELLOW_EX
PINK      = Style.BRIGHT + Fore.LIGHTMAGENTA_EX
SOFT_PINK = Fore.MAGENTA
WHITE     = Style.BRIGHT + Fore.WHITE
MUTED     = Style.DIM   + Fore.WHITE
ERR_FG    = Style.BRIGHT + Fore.LIGHTRED_EX

BG_PASS   = Back.GREEN   + Style.BRIGHT + Fore.BLACK
BG_FAIL   = Back.RED     + Style.BRIGHT + Fore.WHITE
BG_WARN   = Back.YELLOW  + Style.BRIGHT + Fore.BLACK
BG_HPASS  = Back.CYAN    + Style.BRIGHT + Fore.BLACK   # hard pass (data block)
BG_PROMPT = Back.MAGENTA + Style.BRIGHT + Fore.WHITE
BG_HEADER = Back.BLACK   + Style.BRIGHT + Fore.CYAN

RESET = Style.RESET_ALL
W     = 86


# ── Primitives ────────────────────────────────────────────────────────────────

def _c(color: str, text: str) -> str:
    return f"{color}{text}{RESET}"

def _strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", s)

def _blank():   print()
def _thin():    print(_c(DIM_TEAL,  "─" * W))
def _thick():   print(_c(TEAL,      "━" * W))

def _section(label: str):
    _blank()
    print(f"  {_c(SOFT_PINK, '╠═')}  {_c(CORAL, label)}")

def _kv(key: str, val, indent: int = 4):
    print(" " * indent + _c(CORAL, key) + _c(SOFT_PINK, " · ") + _c(WHITE, str(val)))

def _preview(label: str, text: str, chars: int = 160, indent: int = 4):
    clean   = str(text).replace("\n", " ").strip()
    snippet = clean[:chars] + (_c(MUTED, " …") if len(clean) > chars else "")
    prefix  = " " * indent
    print(textwrap.fill(
        snippet,
        width=W - indent,
        initial_indent=prefix + _c(CORAL, label) + _c(SOFT_PINK, " · "),
        subsequent_indent=prefix + " " * (len(label) + 3),
    ))


# ── Test case definition ──────────────────────────────────────────────────────

class Case:
    """One prompt + its pass criteria."""
    def __init__(
        self,
        num:           int,
        label:         str,
        prompt:        str,
        min_len:       int        = 80,
        keywords:      list[str]  = None,
        hard_fail:     list[str]  = None,
        expect_data:   bool       = False,
        expect_disclaimer: bool   = False,
    ):
        self.num              = num
        self.label            = label
        self.prompt           = prompt
        self.min_len          = min_len
        self.keywords         = [k.lower() for k in (keywords or [])]
        self.hard_fail        = [h.lower() for h in (hard_fail or DEFAULT_HARD_FAIL)]
        self.expect_data      = expect_data
        self.expect_disclaimer= expect_disclaimer


DEFAULT_HARD_FAIL = [
    "i cannot", "i don't have access", "i am unable",
    "as an ai, i", "i'm not able to",
]

# ── 5 test cases — covers all major tool categories within Groq free-tier TPM ─

CASES = [
    Case(
        num=1,
        label="General Knowledge — no tools needed",
        prompt=(
            "What is SWEAT equity? Briefly explain PE ratio "
            "and what a good PE looks like for Indian IT stocks."
        ),
        min_len=150,
        keywords=["sweat equity", "pe", "earnings"],
        expect_data=False,
        expect_disclaimer=False,
    ),
    Case(
        num=2,
        label="News + Ticker + Stock Info — tool chaining",
        prompt=(
            "Search latest news on the Indian oil and gas sector. "
            "Pick the single most impacted company, find its NSE ticker, "
            "then get its current price, PE ratio, and analyst consensus."
        ),
        min_len=200,
        keywords=["price", "pe", "nse", "analyst"],
        expect_data=False,
        expect_disclaimer=True,
    ),
    Case(
        num=3,
        label="Stock History + Chart — memory + data block",
        prompt=(
            "Get 3 months of daily price history for that company and show the chart data."
        ),
        min_len=50,
        keywords=["close", "high", "low", "date"],
        expect_data=True,
        expect_disclaimer=False,
    ),
    Case(
        num=4,
        label="Forecast — Chronos ML model + chart",
        prompt=(
            "Forecast the next 10 trading days for that company. "
            "What does the model predict?"
        ),
        min_len=150,
        keywords=["forecast", "median", "day"],
        expect_data=True,
        expect_disclaimer=True,
    ),
    Case(
        num=5,
        label="Web Search — USD/INR + RBI, no prior context needed",
        prompt=(
            "What is the current USD to INR exchange rate? "
            "Also find the latest RBI monetary policy stance."
        ),
        min_len=150,
        keywords=["inr", "rbi", "rate"],
        expect_data=False,
        expect_disclaimer=False,
    ),
]


# ── Result ────────────────────────────────────────────────────────────────────

class Result:
    def __init__(self, case: Case):
        self.case        = case
        self.response    = ""
        self.data        = None
        self.elapsed     = 0.0
        self.checks:     list[tuple[str, bool, str]] = []  # (label, passed, detail)
        self.passed      = False

    def add_check(self, label: str, passed: bool, detail: str = ""):
        self.checks.append((label, passed, detail))

    @property
    def all_passed(self) -> bool:
        return all(ok for _, ok, _ in self.checks)


# ── Checker ───────────────────────────────────────────────────────────────────

def evaluate(case: Case, response: str, data: dict | None) -> Result:
    r   = Result(case)
    r.response = response
    r.data     = data
    low        = response.lower()

    # 1. Non-empty
    r.add_check("Non-empty response",
                len(response.strip()) > 0,
                f"got {len(response)} chars")

    # 2. Minimum length
    r.add_check(f"Min length ≥ {case.min_len} chars",
                len(response.strip()) >= case.min_len,
                f"got {len(response.strip())}")

    # 3. Keyword presence (any one match is enough)
    if case.keywords:
        found = [k for k in case.keywords if k in low]
        r.add_check(f"Keywords [{', '.join(case.keywords[:3])}{'…' if len(case.keywords)>3 else ''}]",
                    len(found) > 0,
                    f"matched: {found or 'none'}")

    # 4. Hard-fail phrases (none should be present)
    hits = [h for h in case.hard_fail if h in low]
    r.add_check("No refusal phrases",
                len(hits) == 0,
                f"found: {hits}" if hits else "clean")

    # 5. Data block (if expected)
    if case.expect_data:
        r.add_check("Data block present",
                    data is not None,
                    "chart_type=" + (data.get("chart_type","?") if data else "missing"))

    # 6. Disclaimer (if expected)
    if case.expect_disclaimer:
        has = "not financial advice" in low
        r.add_check("Disclaimer present",
                    has,
                    "found" if has else "missing")

    r.passed = r.all_passed
    return r


# ── Rendering ─────────────────────────────────────────────────────────────────

def _render_summary(results: list[Result]):
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    total_t = sum(r.elapsed for r in results)

    _blank()
    _thick()
    print(f"  {_c(BG_HEADER, '  SUMMARY  ')}  "
          f"{_c(BG_PASS, f'  {passed} passed  ')}   "
          f"{_c(BG_FAIL, f'  {failed} failed  ') if failed else _c(BG_HPASS, '  0 failed  ')}   "
          f"{_c(MUTED, f'  {total_t:.1f}s total')}")
    _thin()

    for r in results:
        badge = _c(BG_PASS, " ✔ ") if r.passed else _c(BG_FAIL, " ✖ ")
        t_str = _c(MUTED, f"{r.elapsed:5.1f}s")
        print(f"  {badge}  {t_str}  {_c(WHITE, r.case.label)}")

    _thick()
    _blank()


# ── Logger ────────────────────────────────────────────────────────────────────

class AgentTestLogger:
    def __init__(self):
        os.makedirs(_LOGS_DIR, exist_ok=True)
        ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = os.path.join(_LOGS_DIR, f"agent_test_{ts}.md")
        self._w(f"# Artha Agent Test Run\n\n"
                f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n")

    def _w(self, text: str):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(text)

    def log_result(self, r: Result):
        status = "✔ PASS" if r.passed else "✖ FAIL"
        self._w(
            f"\n## [{r.case.num}] {status} — {r.case.label}\n\n"
            f"**Prompt:** {r.case.prompt}\n\n"
            f"**Time:** {r.elapsed:.1f}s\n\n"
            f"**Checks:**\n"
        )
        for label, ok, detail in r.checks:
            mark = "✔" if ok else "✖"
            self._w(f"- {mark} {label}" + (f"  — {detail}" if detail else "") + "\n")
        self._w(f"\n**Response:**\n\n{r.response}\n\n")
        if r.data:
            self._w(f"**Data block:**\n```json\n{json.dumps(r.data, indent=2, default=str)}\n```\n")
        self._w("\n---\n")

    def close(self, passed: int, failed: int, total_t: float):
        self._w(f"\n## Result: {passed} passed, {failed} failed  ({total_t:.1f}s total)\n")
        print(_c(MUTED, f"\n  Log → {os.path.relpath(self.path)}"))


# ── Runner ────────────────────────────────────────────────────────────────────

async def run():
    # Import project
    try:
        from agent import run_agent
        from utils.session_store import append_message, get_files
        from config import settings
    except ImportError as e:
        print(_c(ERR_FG, f"\n  Import error: {e}"))
        print(_c(MUTED,  "  Activate your venv and ensure .env exists."))
        sys.exit(1)

    session_id = f"autotest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger     = AgentTestLogger()
    results: list[Result] = []

    _blank()
    _thick()
    print(f"  {_c(BG_HEADER, '  ARTHA  ')}  {_c(WHITE, 'Automated Agent Test')}  "
          f"{_c(MUTED, datetime.now().strftime('%Y-%m-%d  %H:%M:%S'))}")
    print(f"  {_c(MUTED, f'Session: {session_id}')}  "
          f"{_c(MUTED, f'  {len(CASES)} prompts  ·  sequential  ·  shared memory')}")
    _thick()

    for idx, case in enumerate(CASES, 1):
        # Live prompt display
        _blank()
        num_lbl = _c(BG_PROMPT, f"  {idx}/{len(CASES)}  ")
        print(f"  {num_lbl}  {_c(CORAL, case.label)}")
        _preview("Prompt", case.prompt, chars=130)
        print(_c(DIM_TEAL, f"  {'· ' * 20}"))

        # Build enriched message (same logic as main.py / test_run.py)
        files = get_files(session_id)
        if files:
            file_names = ", ".join(f["filename"] for f in files)
            enriched = (
                f"{case.prompt}\n\n"
                f"[System note: session_id='{session_id}'. "
                f"Files in session: {file_names}. "
                f"Use parse_document_tool(session_id) or "
                f"search_documents_tool(session_id, query).]"
            )
        else:
            enriched = (
                f"{case.prompt}\n\n"
                f"[System note: session_id='{session_id}'. No files uploaded yet.]"
            )

        t0 = time.time()
        try:
            result_raw = await run_agent(session_id, enriched)
            elapsed    = time.time() - t0
            response   = result_raw.get("text", "")
            data       = result_raw.get("data")

            # Append to session history so subsequent prompts have full memory
            append_message(session_id, "user",      enriched)
            append_message(session_id, "assistant", response)

        except Exception as e:
            elapsed  = time.time() - t0
            response = f"[AGENT ERROR: {type(e).__name__}: {e}]"
            data     = None

        # Evaluate
        r         = evaluate(case, response, data)
        r.elapsed = elapsed
        results.append(r)

        # Render inline result (compact — no thick rules between cases)
        overall = _c(BG_PASS, " PASS ") if r.passed else _c(BG_FAIL, " FAIL ")
        print(f"  {overall}  {_c(MUTED, f'{elapsed:.1f}s')}")
        for label, ok, detail in r.checks:
            badge = _c(BG_PASS, " ✔ ") if ok else _c(BG_FAIL, " ✖ ")
            print(f"    {badge}  {_c(WHITE, label)}"
                  + (_c(MUTED, f"  {detail}") if detail else ""))
        _preview("Reply", response, chars=180)
        if data:
            _kv("  data", f"chart_type={data.get('chart_type','?')}  "
                          f"keys={list(data.keys())[:4]}", indent=4)
        _thin()

        logger.log_result(r)

    _render_summary(results)

    passed  = sum(1 for r in results if r.passed)
    failed  = len(results) - passed
    total_t = sum(r.elapsed for r in results)
    logger.close(passed, failed, total_t)

    sys.exit(0 if failed == 0 else 1)


def main():
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print(_c(ERR_FG, "\n  Interrupted."))
        sys.exit(1)


if __name__ == "__main__":
    main()
