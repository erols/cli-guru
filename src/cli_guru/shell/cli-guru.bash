# cli-guru — bash integration.  Sourced from ~/.bashrc by `cli-guru install`.
#
# Ctrl-X Ctrl-A : ask    (plain English on the line -> command replaces the line)
# Ctrl-X Ctrl-H : explain (command on the line -> explanation printed above it)
#
# Override with CLI_GURU_KEY / CLI_GURU_KEY_EXPLAIN before sourcing. cli-guru refuses to
# replace a binding you already use unless CLI_GURU_FORCE_KEY=1.

# Non-interactive shells have no line editor; `bind` warns noisily there.
case $- in *i*) ;; *) return 0 ;; esac
command -v cli-guru >/dev/null 2>&1 || return 0

__cli_guru_key_taken() {
  local cur
  cur=$(bind -p 2>/dev/null | grep -F "\"$1\":" | head -1)
  [[ -z $cur || $cur == *": self-insert"* ]] && return 1
  case $cur in *do-lowercase-version*) return 1 ;; esac
  return 0
}

__cli_guru_bind() {
  local seq=$1 fn=$2 cur
  if [[ ${CLI_GURU_FORCE_KEY:-0} != 1 ]] && __cli_guru_key_taken "$seq"; then
    cur=$(bind -p 2>/dev/null | grep -F "\"$seq\":" | head -1)
    printf 'cli-guru: %s is bound to %s; set CLI_GURU_KEY to another key, or %s\n' \
      "$seq" "${cur#*: }" 'CLI_GURU_FORCE_KEY=1' >&2
    return 1
  fi
  bind -x "\"$seq\": $fn"
}

# `</dev/tty` is needed so an empty line can prompt interactively, but it is
# FATAL where there is no controlling terminal (containers, some ssh/tmux).
# Probe once at source time rather than breaking the common path.
__cli_guru_errfile=/dev/null
if ( exec </dev/tty ) 2>/dev/null; then
  __cli_guru_run() { cli-guru "$@" 2>"$__cli_guru_errfile" </dev/tty; }
else
  __cli_guru_run() { cli-guru "$@" 2>"$__cli_guru_errfile"; }
fi

__cli_guru_ask() {
  local out hist err
  # Captured HERE, not in python: `bind -x` runs in the interactive shell, so
  # this sees live history. A subprocess reading $HISTFILE sees a stale file.
  hist=$(fc -ln -"${CLI_GURU_HISTORY_LINES:-10}" 2>/dev/null)
  __cli_guru_errfile=$(mktemp 2>/dev/null) || __cli_guru_errfile=/dev/null
  out=$(CLI_GURU_HISTORY="$hist" __cli_guru_run ask -- "$READLINE_LINE")
  if [[ $__cli_guru_errfile != /dev/null ]]; then
    err=$(cat "$__cli_guru_errfile" 2>/dev/null)
    rm -f "$__cli_guru_errfile"
  fi
  __cli_guru_errfile=/dev/null
  # stderr carries the destructive-command warning, and the reason on failure
  # ("no ollama at ..."). Showing it beats failing silently; it never touches
  # the buffer.
  [[ -n $err ]] && printf '\n%s\n' "$err"
  # Any failure leaves what the user typed exactly as it was.
  [[ -n $out ]] || return 0
  READLINE_LINE="$out"
  READLINE_POINT=${#READLINE_LINE}
}

__cli_guru_explain() {
  # Deliberately NOT symmetric with ask: you still want to run the command you
  # asked about, so the buffer is left untouched.
  [[ -n $READLINE_LINE ]] || return 0
  printf '\n'
  if ( exec </dev/tty ) 2>/dev/null; then
    cli-guru explain -- "$READLINE_LINE" </dev/tty
  else
    cli-guru explain -- "$READLINE_LINE"
  fi
  printf '\n'
}

__cli_guru_bind "${CLI_GURU_KEY:-\C-x\C-a}" __cli_guru_ask
__cli_guru_bind "${CLI_GURU_KEY_EXPLAIN:-\C-x\C-h}" __cli_guru_explain
