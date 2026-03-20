"""
test_run.py — Terminal Chat Client for Shree_v2

A menu-driven terminal interface that talks directly to the agent (via run_agent())
without needing the FastAPI server or any frontend.

Features
--------
  - Full multi-turn conversation with the agent
  - File upload via typed path OR a small Tkinter file-picker dialog
  - Text context injection (paste raw text into the session)
  - View uploaded files in the current session
  - Clear/reset session
  - Coloured output so agent replies are easy to read
  - Data block summary: when the agent returns chart data, the key fields are
    printed in a compact table so you can verify the structure

Usage
-----
    python test_run.py

No server needed. Calls run_agent() and session_store directly.
Requires .env to be present with valid GEMINI_API_KEY.

Menu Commands (type at the prompt)
-----------------------------------
  /upload   -> Open file picker (Tkinter) or type a path manually
  /context  -> Paste multi-line text context into the session
  /files    -> List files uploaded in this session
  /clear    -> Reset session (clears history + deletes uploaded files)
  /new      -> Start a brand-new session with a fresh session ID
  /session  -> Show current session ID
  /help     -> Show this command list
  /quit     -> Exit
  anything else -> Sent as a chat message to the agent
"""

import asyncio
import os
import sys
import shutil
import uuid
import json
from datetime import datetime

# ── Optional colour support (works on most terminals; gracefully degrades) ───
try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init(autoreset=True)
    _HAS_COLOR = True
except ImportError:
    _HAS_COLOR = False

    class Fore:      # noqa: F811  — stub when colorama absent
        CYAN = GREEN = YELLOW = RED = MAGENTA = BLUE = WHITE = ""

    class Style:     # noqa: F811
        BRIGHT = RESET_ALL = DIM = ""


# ── Tkinter file picker (optional — falls back to path input if unavailable) ─
def _pick_file_tkinter() -> str | None:
    """
    Open a small Tkinter file dialog. Returns the selected filepath or None
    if the user cancelled or Tkinter is unavailable.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()          # Hide the empty root window
        root.attributes("-topmost", True)
        filepath = filedialog.askopenfilename(
            title="Select a file to upload to Shree",
            filetypes=[
                ("Supported files",
                 "*.pdf *.docx *.doc *.xlsx *.xls *.csv *.txt *.ppt *.pptx"),
                ("PDF files",       "*.pdf"),
                ("Word documents",  "*.docx *.doc"),
                ("Excel files",     "*.xlsx *.xls"),
                ("CSV files",       "*.csv"),
                ("Text files",      "*.txt"),
                ("PowerPoint",      "*.ppt *.pptx"),
                ("All files",       "*.*"),
            ],
        )
        root.destroy()
        return filepath if filepath else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Lazy imports — these pull in the project modules.
# Done here (not at top-level) so we get a clean error message if the user
# forgot to activate their venv or set up .env.
# ─────────────────────────────────────────────────────────────────────────────

def _import_project() -> tuple:
    """
    Import project modules and return (run_agent, session_store funcs, settings).
    Prints a friendly error and exits if something is missing.
    """
    try:
        from agent import run_agent  # noqa
        from utils.session_store import (
            append_message, get_history, add_file,
            get_files, clear_session,
        )
        from utils.doc_parser import parse_uploaded_file
        from config import settings
        return run_agent, append_message, get_history, add_file, get_files, clear_session, parse_uploaded_file, settings
    except ImportError as e:
        print(f"\n{Fore.RED}Import error: {e}")
        print(f"{Fore.YELLOW}Make sure you are running from the project root with your venv active.")
        print(f"{Fore.YELLOW}Also check that your .env file exists with GEMINI_API_KEY set.\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Fore.RED}Startup error: {e}\n")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# DISPLAY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

BANNER = r"""
╔══════════════════════════════════════════════════════════╗
║      ⣿  S H R E E  —  AI Financial Analyst  ⣿            ║
║          Terminal Chat Client    v1.0                    ║
╚══════════════════════════════════════════════════════════╝
"""

HELP_TEXT = """
┌─────────────────────────────────────────────────────────┐
│  COMMANDS                                               │
├──────────────┬──────────────────────────────────────────┤
│  /upload     │  Upload a file (picker or type path)     │
│  /context    │  Inject raw text context                 │
│  /files      │  List uploaded files this session        │
│  /clear      │  Reset session (clears files + history)  │
│  /new        │  Start a brand-new session               │
│  /session    │  Show current session ID                 │
│  /help       │  Show this help                          │
│  /quit       │  Exit                                    │
├──────────────┴──────────────────────────────────────────┤
│  Anything else is sent as a message to the agent.       │
└─────────────────────────────────────────────────────────┘
"""


def _print_banner():
    print(f"{Fore.CYAN}{Style.BRIGHT}{BANNER}{Style.RESET_ALL}")


def _print_help():
    print(f"{Fore.CYAN}{HELP_TEXT}{Style.RESET_ALL}")


def _print_separator():
    print(f"{Fore.WHITE}{Style.DIM}{'─' * 60}{Style.RESET_ALL}")


def _print_agent_reply(text: str, data: dict | None):
    """Pretty-print the agent's text reply and summarise the data block if present."""
    _print_separator()
    print(f"{Fore.GREEN}{Style.BRIGHT}Shree:{Style.RESET_ALL}")
    # Indent each line for visual separation
    for line in text.split("\n"):
        print(f"  {line}")

    if data:
        _print_separator()
        print(f"{Fore.MAGENTA}{Style.BRIGHT}📊 Data Block — {data.get('chart_type', 'unknown').upper()}{Style.RESET_ALL}")
        chart_type = data.get("chart_type", "")
        if chart_type == "candlestick":
            dates = data.get("dates", [])
            closes = data.get("close", [])
            print(f"  Ticker  : {data.get('ticker', 'n/a')}")
            print(f"  Period  : {data.get('period', 'n/a')}  |  Interval: {data.get('interval', 'n/a')}")
            print(f"  Candles : {len(dates)}")
            if dates:
                print(f"  Range   : {dates[0]}  →  {dates[-1]}")
            if closes:
                print(f"  Close   : first={closes[0]}  last={closes[-1]}")
        elif chart_type == "forecast":
            print(f"  Symbol   : {data.get('symbol', 'n/a')}")
            print(f"  Horizon  : {data.get('horizon_days', 'n/a')} days")
            hist = data.get("historical_dates", [])
            med  = data.get("forecast_median", [])
            if hist:
                print(f"  History  : {len(hist)} data points, last date = {hist[-1]}")
            if med:
                print(f"  Forecast : {len(med)} points  |  median range {min(med):.2f} – {max(med):.2f}")
            note = data.get("note", "")
            if note:
                print(f"\n  {Fore.YELLOW}⚠ {note[:120]}{'...' if len(note) > 120 else ''}{Style.RESET_ALL}")
        elif chart_type in ("line", "bar"):
            vals = data.get("values", [])
            print(f"  Label : {data.get('label', 'n/a')}")
            print(f"  Points: {len(vals)}")
        elif chart_type == "table":
            rows = data.get("rows", [])
            cols = data.get("columns", [])
            print(f"  Columns : {len(cols)}  |  Rows: {len(rows)}")
        else:
            # Unknown chart type — just dump the top-level keys
            keys = [k for k in data.keys() if k != "chart_type"]
            print(f"  Keys : {', '.join(keys[:10])}")
    _print_separator()


def _print_status(msg: str):
    print(f"{Fore.YELLOW}  ▸ {msg}{Style.RESET_ALL}")


def _print_error(msg: str):
    print(f"{Fore.RED}  ✖ {msg}{Style.RESET_ALL}")


def _print_success(msg: str):
    print(f"{Fore.GREEN}  ✔ {msg}{Style.RESET_ALL}")


# ─────────────────────────────────────────────────────────────────────────────
# COMMAND HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

def cmd_upload(session_id: str, add_file_fn, settings) -> None:
    """
    Handle /upload command.
    Offers Tkinter file picker first; falls back to manual path entry.
    Copies the file into the uploads/ directory and registers it in the session.
    """
    print(f"\n{Fore.CYAN}Upload a file{Style.RESET_ALL}")
    print("  [1] Open file picker (Tkinter)")
    print("  [2] Type file path manually")
    print("  [0] Cancel")
    choice = input(f"\n{Fore.WHITE}  Choice: {Style.RESET_ALL}").strip()

    filepath = None

    if choice == "1":
        _print_status("Opening file picker…")
        filepath = _pick_file_tkinter()
        if not filepath:
            _print_status("No file selected. Upload cancelled.")
            return
    elif choice == "2":
        filepath = input(f"  {Fore.WHITE}Enter full file path: {Style.RESET_ALL}").strip().strip('"').strip("'")
    else:
        _print_status("Upload cancelled.")
        return

    if not filepath or not os.path.isfile(filepath):
        _print_error(f"File not found: '{filepath}'")
        return

    ext = os.path.splitext(filepath)[1].lower()
    allowed = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".txt", ".ppt", ".pptx"}
    if ext not in allowed:
        _print_error(f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(allowed))}")
        return

    # Copy into uploads/ directory
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_id  = str(uuid.uuid4())
    filename = os.path.basename(filepath)
    dest     = os.path.join(settings.UPLOAD_DIR, f"{file_id}_{filename}")
    shutil.copy2(filepath, dest)

    add_file_fn(session_id, file_id, dest, filename)
    _print_success(f"Uploaded '{filename}'")
    _print_success(f"File ID : {file_id}")
    print(f"  {Fore.CYAN}You can now ask: 'What does my uploaded document say about X?'{Style.RESET_ALL}\n")


def cmd_context(session_id: str, append_message_fn) -> None:
    """
    Handle /context command.
    Reads multi-line input until the user types END on its own line.
    Stores it as a system message in the session.
    """
    print(f"\n{Fore.CYAN}Paste your context below.{Style.RESET_ALL}")
    print(f"  Type {Fore.YELLOW}END{Style.RESET_ALL} on its own line when done. Type {Fore.YELLOW}CANCEL{Style.RESET_ALL} to abort.\n")

    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip().upper() == "END":
            break
        if line.strip().upper() == "CANCEL":
            _print_status("Context injection cancelled.")
            return
        lines.append(line)

    if not lines:
        _print_status("No context provided.")
        return

    context_text = "\n".join(lines)
    content = f"[User-provided context]:\n{context_text}"
    append_message_fn(session_id, "system", content)
    _print_success(f"Context added ({len(context_text)} characters). The agent will consider it on the next message.\n")


def cmd_files(session_id: str, get_files_fn) -> None:
    """Handle /files command — list files uploaded in this session."""
    files = get_files_fn(session_id)
    if not files:
        _print_status("No files uploaded in this session yet.")
        return
    print(f"\n{Fore.CYAN}  Uploaded files in session '{session_id}':{Style.RESET_ALL}")
    for i, f in enumerate(files, 1):
        exists = "✔" if os.path.exists(f["filepath"]) else "✖ MISSING"
        print(f"  [{i}] {Fore.WHITE}{f['filename']}{Style.RESET_ALL}  |  id: {f['file_id']}  |  {exists}")
    print()


def cmd_clear(session_id: str, get_files_fn, clear_session_fn) -> None:
    """Handle /clear — delete uploaded files from disk and wipe session state."""
    confirm = input(
        f"  {Fore.RED}This will delete all files and history for this session. Confirm? (y/N): {Style.RESET_ALL}"
    ).strip().lower()
    if confirm != "y":
        _print_status("Clear cancelled.")
        return

    files = get_files_fn(session_id)
    deleted = 0
    for f in files:
        if os.path.exists(f["filepath"]):
            os.remove(f["filepath"])
            deleted += 1

    clear_session_fn(session_id)
    _print_success(f"Session cleared. {deleted} file(s) deleted from disk.\n")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────────────────────────────────────

async def _chat_loop():
    # Import project modules
    (
        run_agent, append_message, get_history, add_file,
        get_files, clear_session, parse_uploaded_file, settings
    ) = _import_project()

    _print_banner()
    _print_help()

    session_id = f"cli_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"  Session ID : {Fore.YELLOW}{session_id}{Style.RESET_ALL}")
    print(f"  Type {Fore.CYAN}/help{Style.RESET_ALL} for commands, {Fore.CYAN}/quit{Style.RESET_ALL} to exit.\n")

    while True:
        # ── Prompt ────────────────────────────────────────────────────────────
        try:
            user_input = input(f"{Fore.BLUE}{Style.BRIGHT}You: {Style.RESET_ALL}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Fore.YELLOW}Exiting. Goodbye!{Style.RESET_ALL}")
            break

        if not user_input:
            continue

        # ── Commands ──────────────────────────────────────────────────────────
        cmd = user_input.lower()

        if cmd in ("/quit", "/exit", "/q"):
            print(f"\n{Fore.YELLOW}Goodbye!{Style.RESET_ALL}")
            break

        elif cmd == "/help":
            _print_help()

        elif cmd == "/session":
            print(f"  Current session ID: {Fore.YELLOW}{session_id}{Style.RESET_ALL}\n")

        elif cmd == "/files":
            cmd_files(session_id, get_files)

        elif cmd == "/upload":
            cmd_upload(session_id, add_file, settings)

        elif cmd == "/context":
            cmd_context(session_id, append_message)

        elif cmd == "/clear":
            cmd_clear(session_id, get_files, clear_session)
            # After clear, re-use same session_id (store was wiped, ADK session still exists
            # but will be re-created on the next agent call — harmless)

        elif cmd == "/new":
            # Commit: clear current session first, then generate new ID
            confirm = input(
                f"  {Fore.YELLOW}Start a new session? Current session will be cleared. (y/N): {Style.RESET_ALL}"
            ).strip().lower()
            if confirm == "y":
                cmd_clear(session_id, get_files, clear_session)
                session_id = f"cli_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                print(f"  New session ID : {Fore.YELLOW}{session_id}{Style.RESET_ALL}\n")

        elif cmd.startswith("/"):
            _print_error(f"Unknown command '{user_input}'. Type /help for the command list.")

        # ── Chat message → agent ──────────────────────────────────────────────
        else:
            # Inject session_id so document tools can look up uploaded files
            files = get_files(session_id)
            message = user_input
            if files:
                file_names = ", ".join(f["filename"] for f in files)
                message = (
                    f"{user_input}\n\n"
                    f"[System note: session_id='{session_id}'. "
                    f"Files uploaded in this session: {file_names}. "
                    f"Use tool_parse_document or tool_search_documents with this session_id to access them.]"
                )

            append_message(session_id, "user", user_input)
            _print_status("Thinking…")
            try:
                result = await run_agent(session_id, message)
                append_message(session_id, "assistant", result["text"])
                _print_agent_reply(result["text"], result.get("data"))
            except Exception as e:
                _print_error(f"Agent error: {e}")
                print(f"  {Fore.YELLOW}(Check your GEMINI_API_KEY in .env and your Gemini API quota at https://ai.dev/rate-limit){Style.RESET_ALL}\n")


def main():
    """Entry point — runs the async chat loop."""
    try:
        asyncio.run(_chat_loop())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Interrupted. Goodbye!{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
