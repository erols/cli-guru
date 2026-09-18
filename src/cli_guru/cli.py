"""Command-line entry point.

`ask` stdout is pasted straight into a live shell prompt, so it prints the
command and NOTHING else. Every diagnostic goes to stderr.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__, config, context, danger, install, manpage, prompts, sanitise
from .backend import BackendError, OllamaBackend


def _err(msg: str) -> None:
    print(f"cliai: {msg}", file=sys.stderr)


def _backend(cfg, timeout_key: str = "timeout") -> OllamaBackend:
    timeout = int(cfg.get(timeout_key, cfg["timeout"]))
    return OllamaBackend(
        cfg["host"], cfg["model"], timeout, str(cfg.get("keep_alive", "8h"))
    )


def _joined(parts: List[str]) -> str:
    """Join the trailing words into one line.

    argparse.REMAINDER is used for these positionals so that `cliai explain ls -la`
    works: with nargs="*", argparse claims `-la` as an unknown option and exits 2.
    A leading `--` (which the shell widget always passes) is dropped here.
    """
    parts = list(parts)
    if parts and parts[0] == "--":
        parts = parts[1:]
    return " ".join(parts).strip()


def cmd_ask(args, cfg) -> int:
    question = _joined(args.text)
    if not question:
        try:
            question = input("cliai> ").strip()
        except (EOFError, KeyboardInterrupt):
            return 1
    if not question:
        return 1

    ctx = context.collect(cfg)
    user = prompts.ask_user(question, context.render(ctx, bool(cfg.get("include_tools"))))
    if args.debug:
        print(f"--- system ---\n{prompts.ASK_SYSTEM}\n--- user ---\n{user}", file=sys.stderr)

    try:
        raw, thinking = _backend(cfg).chat(
            prompts.ASK_SYSTEM, user, think=bool(cfg["think"]), num_predict=160
        )
    except BackendError as exc:
        _err(str(exc))
        return 1

    if args.debug and thinking:
        print(f"--- thinking ---\n{thinking}", file=sys.stderr)

    command = sanitise.command(raw)
    if not command:
        _err("model returned no usable command")
        return 1
    # The command goes to stdout (the readline buffer); the warning goes to
    # stderr, which the shell widget prints above the prompt. Deterministic, so
    # it does not depend on the model having noticed.
    warning = danger.banner(command)
    if warning:
        print(warning, file=sys.stderr)
    print(command)
    return 0


def cmd_explain(args, cfg) -> int:
    line = _joined(args.text)
    if not line:
        _err("nothing to explain")
        return 1

    cmd, sub = manpage.base_command(line)
    # Opt-in only: fetching docs must not execute the command under explanation.
    run_help = bool(getattr(args, "run_help", False)) or bool(cfg.get("explain_run_help"))
    doc, source = manpage.fetch(cmd, sub, run_help=run_help)
    if doc:
        doc = manpage.truncate(doc, int(cfg["max_man_chars"]))

    user = prompts.explain_user(line, doc, source)
    if args.debug:
        print(f"--- source: {source} ({len(doc or '')} chars) ---", file=sys.stderr)

    try:
        raw, thinking = _backend(cfg, "timeout_explain").chat(
            prompts.EXPLAIN_SYSTEM, user, think=bool(cfg["think_explain"]), num_predict=700
        )
    except BackendError as exc:
        _err(str(exc))
        return 1

    if args.debug and thinking:
        print(f"--- thinking ---\n{thinking}", file=sys.stderr)

    text = sanitise.prose(raw)
    if not text:
        _err("model returned no explanation")
        return 1
    # cliai owns the warning, not the model: qwen2.5-coder:3b missed 12 of 15
    # destructive commands when this was left to the prompt.
    warning = danger.banner(line)
    if warning:
        print(warning)
        # Drop a duplicate warning line the model may have produced anyway.
        stripped = [ln for ln in text.splitlines() if not ln.upper().lstrip().startswith("WARNING")]
        text = "\n".join(stripped).strip()
    print(text)
    if source == "none":
        _err("no local man page found — answer is from general knowledge")
    return 0


def cmd_check(args, cfg) -> int:
    try:
        print(_backend(cfg).check())
    except BackendError as exc:
        _err(str(exc))
        return 1
    ctx = context.collect(cfg)
    print(f"shell: {ctx['shell']}  userland: {ctx['userland']}  os: {ctx['os']}")
    return 0


def _script_for(shell: str) -> Path:
    """Adapters live inside the package, so an installed wheel finds them too."""
    name, _ = install.SHELL_FILES[shell]
    return Path(__file__).resolve().parent / "shell" / name


def cmd_install(args, cfg) -> int:
    shell = args.shell or install.detect_shell()
    if shell not in install.SHELL_FILES:
        _err(f"unsupported shell {shell!r} (expected bash, zsh or powershell)")
        return 1
    script = _script_for(shell)
    if not script.exists():
        _err(f"shell integration file not found: {script}")
        return 1
    try:
        rc, current, new = install.plan(shell, script)
    except ValueError as exc:
        _err(str(exc))
        return 1

    if current == new:
        print(f"already installed in {rc} (nothing to do)")
        return 0
    if args.dry_run:
        print(install.diff(rc, current, new))
        print("\n(dry run — nothing written)")
        return 0

    bak = install.write(rc, current, new)
    print(f"installed cliai ({shell}) in {rc}")
    if bak:
        print(f"backup: {bak}")
    print("keys: Ctrl-X Ctrl-A = ask, Ctrl-X Ctrl-H = explain")
    print(f"start a new shell, or run:  . {rc}")
    return 0


def cmd_uninstall(args, cfg) -> int:
    shell = args.shell or install.detect_shell()
    if shell not in install.SHELL_FILES:
        _err(f"unsupported shell {shell!r}")
        return 1
    try:
        rc, current, new = install.uninstall_plan(shell)
    except ValueError as exc:
        _err(str(exc))
        return 1
    if current == new:
        print(f"cliai is not installed in {rc}")
        return 0
    if args.dry_run:
        print(install.diff(rc, current, new))
        print("\n(dry run — nothing written)")
        return 0
    install.write(rc, current, new, backup=False)
    print(f"removed cliai block from {rc}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cliai",
        description="Plain-language shell commands from a local ollama model.",
    )
    parser.add_argument("--version", action="version", version=f"cliai {__version__}")
    parser.add_argument("--debug", action="store_true",
                        help="dump prompt and model reasoning to stderr")
    parser.add_argument("--model", help="override the model")
    parser.add_argument("--host", help="override the ollama host")

    sub = parser.add_subparsers(dest="command", required=True)

    p_ask = sub.add_parser("ask", help="plain language -> one shell command")
    p_ask.add_argument("text", nargs=argparse.REMAINDER)
    p_ask.set_defaults(func=cmd_ask)

    p_exp = sub.add_parser("explain", help="explain a command using its man page")
    p_exp.add_argument("--run-help", action="store_true",
                       help="if no man page exists, RUN `<cmd> --help` to get its docs")
    p_exp.add_argument("text", nargs=argparse.REMAINDER)
    p_exp.set_defaults(func=cmd_explain)

    p_chk = sub.add_parser("check", help="verify ollama is reachable and the model is pulled")
    p_chk.set_defaults(func=cmd_check)

    p_ins = sub.add_parser("install", help="add the cliai block to your shell rc file")
    p_ins.add_argument("--shell", choices=sorted(install.SHELL_FILES))
    p_ins.add_argument("--dry-run", action="store_true", help="print the diff, write nothing")
    p_ins.set_defaults(func=cmd_install)

    p_uni = sub.add_parser("uninstall", help="remove the cliai block from your shell rc file")
    p_uni.add_argument("--shell", choices=sorted(install.SHELL_FILES))
    p_uni.add_argument("--dry-run", action="store_true")
    p_uni.set_defaults(func=cmd_uninstall)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # `cliai --check` is documented alongside the `check` subcommand.
    argv = ["check" if a == "--check" else a for a in argv]

    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = config.load({"model": args.model, "host": args.host})
    try:
        return int(args.func(args, cfg))
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
