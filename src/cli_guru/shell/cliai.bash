# cliai — bash integration.  Sourced from ~/.bashrc by `cliai install`.
#
# Ctrl-X Ctrl-A : ask    (plain English on the line -> command replaces the line)
# Ctrl-X Ctrl-H : explain (command on the line -> explanation printed above it)
#
# Override with CLIAI_KEY / CLIAI_KEY_EXPLAIN before sourcing. cliai refuses to
# replace a binding you already use unless CLIAI_FORCE_KEY=1.

# Non-interactive shells have no line editor; `bind` warns noisily there.
case $- in *i*) ;; *) return 0 ;; esac
command -v cliai >/dev/null 2>&1 || return 0

__cliai_key_taken() {
  local cur
  cur=$(bind -p 2>/dev/null | grep -F "\"$1\":" | head -1)
  [[ -z $cur || $cur == *": self-insert"* ]] && return 1
  case $cur in *do-lowercase-version*) return 1 ;; esac
  return 0
}

__cliai_bind() {
  local seq=$1 fn=$2 cur
  if [[ ${CLIAI_FORCE_KEY:-0} != 1 ]] && __cliai_key_taken "$seq"; then
    cur=$(bind -p 2>/dev/null | grep -F "\"$seq\":" | head -1)
    printf 'cliai: %s is bound to %s; set CLIAI_KEY to another key, or CLIAI_FORCE_KEY=1\n' \
      "$seq" "${cur#*: }" >&2
    return 1
  fi
  bind -x "\"$seq\": $fn"
}

# `</dev/tty` is needed so an empty line can prompt interactively, but it is
# FATAL where there is no controlling terminal (containers, some ssh/tmux).
# Probe once at source time rather than breaking the common path.
__cliai_errfile=/dev/null
if ( exec </dev/tty ) 2>/dev/null; then
  __cliai_run() { cliai "$@" 2>"$__cliai_errfile" </dev/tty; }
else
  __cliai_run() { cliai "$@" 2>"$__cliai_errfile"; }
fi

__cliai_ask() {
  local out hist err
  # Captured HERE, not in python: `bind -x` runs in the interactive shell, so
  # this sees live history. A subprocess reading $HISTFILE sees a stale file.
  hist=$(fc -ln -"${CLIAI_HISTORY_LINES:-10}" 2>/dev/null)
  __cliai_errfile=$(mktemp 2>/dev/null) || __cliai_errfile=/dev/null
  out=$(CLIAI_HISTORY="$hist" __cliai_run ask -- "$READLINE_LINE")
  if [[ $__cliai_errfile != /dev/null ]]; then
    err=$(cat "$__cliai_errfile" 2>/dev/null)
    rm -f "$__cliai_errfile"
  fi
  __cliai_errfile=/dev/null
  # stderr carries the destructive-command warning, and the reason on failure
  # ("no ollama at ..."). Showing it beats failing silently; it never touches
  # the buffer.
  [[ -n $err ]] && printf '\n%s\n' "$err"
  # Any failure leaves what the user typed exactly as it was.
  [[ -n $out ]] || return 0
  READLINE_LINE="$out"
  READLINE_POINT=${#READLINE_LINE}
}

__cliai_explain() {
  # Deliberately NOT symmetric with ask: you still want to run the command you
  # asked about, so the buffer is left untouched.
  [[ -n $READLINE_LINE ]] || return 0
  printf '\n'
  if ( exec </dev/tty ) 2>/dev/null; then
    cliai explain -- "$READLINE_LINE" </dev/tty
  else
    cliai explain -- "$READLINE_LINE"
  fi
  printf '\n'
}

__cliai_bind "${CLIAI_KEY:-\C-x\C-a}" __cliai_ask
__cliai_bind "${CLIAI_KEY_EXPLAIN:-\C-x\C-h}" __cliai_explain
