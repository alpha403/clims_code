"""CLI entry point: `clims` (interactive) and `clims -p "prompt"` (headless)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _force_utf8_output() -> None:
    """Windows consoles default to cp1252 and crash on emoji / arrows / box-drawing.
    Try reconfigure first; fall back to wrapping the raw buffer directly."""
    import io, os

    # Set console code page to UTF-8 on Windows (affects the terminal itself)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass

    # Propagate UTF-8 to any subprocess we spawn
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8:replace")

    for attr in ("stdout", "stderr"):
        stream = getattr(sys, attr)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            # reconfigure not available (e.g. stream already wrapped) — rewrap the buffer
            buf = getattr(stream, "buffer", None)
            if buf:
                try:
                    setattr(sys, attr, io.TextIOWrapper(
                        buf, encoding="utf-8", errors="replace", line_buffering=True
                    ))
                except Exception:
                    pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8_output()
    parser = argparse.ArgumentParser(prog="clims", description="clims_code agent")
    parser.add_argument("-p", "--print", dest="prompt", help="headless: run one prompt and exit")
    parser.add_argument("--provider", help="override provider")
    parser.add_argument("--model", help="override model")
    parser.add_argument("--mode", help="permission mode: default|acceptEdits|plan|bypass")
    parser.add_argument("--output-format", choices=["text", "json", "stream-json"],
                        default="text", help="headless output format")
    parser.add_argument("--resume", action="store_true", help="resume the most recent session")
    parser.add_argument("-i", "--image", action="append", default=[],
                        help="attach an image file to the prompt (repeatable)")
    args = parser.parse_args(argv)
    if args.resume:
        import os as _os
        _os.environ["CLIMS_RESUME"] = "1"

    import os
    if args.provider:
        os.environ["CLIMS_PROVIDER"] = args.provider
    if args.model:
        os.environ["CLIMS_MODEL"] = args.model
    if args.mode:
        os.environ["CLIMS_PERMISSION_MODE"] = args.mode

    if args.prompt:
        return _headless(args.prompt, args.output_format, args.image)

    from clims_cli.repl import run
    return run()


def _headless(prompt: str, output_format: str = "text", images: list | None = None) -> int:
    import json
    from clims_cli.repl import build_agent, _make_event_printer
    from clims_core.agent.message import Message
    from clims_core.config import load_config

    cwd = Path.cwd()
    cfg = load_config(cwd)
    if not cfg.api_key:
        print("error: no API key (BYOK). Set DEEPSEEK_API_KEY/ANTHROPIC_API_KEY/CLIMS_API_KEY.",
              file=sys.stderr)
        return 2
    agent = build_agent(cfg, cwd)
    if images:
        from clims_core.images import build_image_message
        user_msg = build_image_message(prompt, images, cwd)
    else:
        user_msg = Message.user(prompt)

    if output_format == "stream-json":
        # emit one JSON object per event (JSONL) — for programmatic consumers
        def on_event(ev):
            print(json.dumps(_event_to_dict(ev)), flush=True)
        result = agent.send([user_msg], on_event)
        print(json.dumps({"type": "result", "stop_reason": result.stop_reason,
                          "input_tokens": result.input_tokens,
                          "output_tokens": result.output_tokens}), flush=True)
    elif output_format == "json":
        result = agent.send([user_msg], lambda e: None)
        print(json.dumps({
            "result": result.messages[-1].text() if result.messages else "",
            "stop_reason": result.stop_reason,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }, indent=2))
    else:
        result = agent.send([user_msg], _make_event_printer())
        print()
    return 0 if result.stop_reason != "error" else 1


def _event_to_dict(ev) -> dict:
    d = {"type": ev.type}
    if ev.type in ("text_delta", "thinking_delta"):
        d["text"] = ev.text
    elif ev.type == "tool_use":
        d.update(name=ev.tool_name, input=ev.tool_input)
    elif ev.type == "tool_result":
        d.update(name=ev.tool_name, is_error=ev.is_error, content=ev.message)
    elif ev.type == "usage":
        d.update(input_tokens=ev.input_tokens, output_tokens=ev.output_tokens)
    elif ev.type == "done":
        d["stop_reason"] = ev.stop_reason
    elif ev.type == "error":
        d["message"] = ev.message
    return d


if __name__ == "__main__":
    raise SystemExit(main())
