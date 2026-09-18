"""System prompts, kept as module-level constants so they stay diffable."""

from __future__ import annotations

# Kept deliberately SHORT. Measured on nemotron-3-nano:4b: a 1007-char rule list
# was 2x slower (3172ms vs 1602ms mean) and produced WORSE commands than this.
# Small models degrade with long instruction lists — facts belong in the context
# block below, which is compact data, not prose rules.
ASK_SYSTEM = """\
Output ONE shell command line for the user's system. No markdown, no fences, no \
backticks, no explanation, no prompt symbol.
Match the userland (GNU and BSD flags differ).
Use real names from the context; never emit placeholders like <file>.
The command runs IN the working directory: use relative paths, not absolute ones.
"""

# Short for the same reason ASK_SYSTEM is: this model follows verbose format
# instructions LITERALLY. "write the flag, two spaces, then its meaning"
# produced the text "-r two spaces remove directories".
# Short for the same reason ASK_SYSTEM is: this model follows verbose format
# instructions LITERALLY ("write the flag, two spaces, then its meaning"
# produced the text "-r two spaces remove directories").
# The destructive-command rule is FIRST on purpose: when it sat at the end of
# this prompt the model omitted the warning for `rm -rf /var/log/*`.
# Short for the same reason ASK_SYSTEM is: this model follows verbose format
# instructions LITERALLY ("write the flag, two spaces, then its meaning"
# produced the text "-r two spaces remove directories").
# The destructive-command WARNING is NOT here: it is computed in danger.py.
# Leaving it to the prompt was measured at 12 misses out of 15 on
# qwen2.5-coder:3b, including `rm -rf /var/log/*`. Safety does not go in a prompt.
EXPLAIN_SYSTEM = """\
Explain a shell command to someone about to run it. Be terse; this is read at a
prompt, not in a manual. No markdown, no fences, no headings.

The documentation provided is ground truth. If it disagrees with your
recollection, follow the documentation. If a flag is not in it, say so rather
than inventing a meaning.

One line saying what the command does.
Then one line per flag, in the order it appears, copying the flag exactly as
written and explaining what it does.
Finally note anything surprising: shell expansion, silent overwrites, or a flag
the user probably wanted and omitted.
"""

def ask_user(question: str, context: str) -> str:
    return f"{context}\n\nRequest: {question}\n\nCommand:"


def explain_user(command: str, doc: str | None, source: str) -> str:
    if doc:
        return (
            f"Reference documentation ({source}):\n"
            f"---\n{doc}\n---\n\n"
            f"Explain this command:\n{command}"
        )
    return (
        f"No local documentation was found for this command "
        f"(no man page, no --help output).\n"
        f"Begin your answer with: 'Note: no local man page found; this is from "
        f"general knowledge and may not match your version.'\n\n"
        f"Explain this command:\n{command}"
    )
