# cliai — zsh integration (macOS default shell).
# Not a port of the bash file: zsh uses ZLE widgets and $BUFFER/$CURSOR.
#
# Ctrl-X Ctrl-A : ask     Ctrl-X Ctrl-H : explain

[[ -o interactive ]] || return 0
command -v cliai >/dev/null 2>&1 || return 0

__cliai_key_taken() {
  local cur
  cur=$(bindkey "$1" 2>/dev/null)
  [[ -z $cur || $cur == *" undefined-key" || $cur == *" self-insert" ]] && return 1
  return 0
}

# See cliai.bash: /dev/tty is fatal where there is no controlling terminal.
__cliai_errfile=/dev/null
if ( exec </dev/tty ) 2>/dev/null; then
  __cliai_run() { cliai "$@" 2>"$__cliai_errfile" </dev/tty; }
else
  __cliai_run() { cliai "$@" 2>"$__cliai_errfile"; }
fi

__cliai_ask() {
  local out hist err
  hist=$(fc -ln -${CLIAI_HISTORY_LINES:-10} 2>/dev/null)
  __cliai_errfile=$(mktemp 2>/dev/null) || __cliai_errfile=/dev/null
  out=$(CLIAI_HISTORY="$hist" __cliai_run ask -- "$BUFFER")
  if [[ $__cliai_errfile != /dev/null ]]; then
    err=$(cat "$__cliai_errfile" 2>/dev/null)
    rm -f "$__cliai_errfile"
  fi
  __cliai_errfile=/dev/null
  # stderr carries the destructive-command warning and failure reasons.
  [[ -n $err ]] && printf '\n%s\n' "$err" && zle reset-prompt
  [[ -n $out ]] || return 0
  BUFFER="$out"
  CURSOR=${#BUFFER}
}

__cliai_explain() {
  [[ -n $BUFFER ]] || return 0
  printf '\n'
  if ( exec </dev/tty ) 2>/dev/null; then
    cliai explain -- "$BUFFER" </dev/tty
  else
    cliai explain -- "$BUFFER"
  fi
  printf '\n'
  zle reset-prompt
}

zle -N __cliai_ask
zle -N __cliai_explain

__cliai_bind() {
  local seq=$1 widget=$2
  if [[ ${CLIAI_FORCE_KEY:-0} != 1 ]] && __cliai_key_taken "$seq"; then
    print -u2 "cliai: $seq is bound to $(bindkey "$seq" | awk '{print $2}'); set CLIAI_KEY, or CLIAI_FORCE_KEY=1"
    return 1
  fi
  bindkey "$seq" "$widget"
}

__cliai_bind "${CLIAI_KEY:-^X^A}" __cliai_ask
__cliai_bind "${CLIAI_KEY_EXPLAIN:-^X^H}" __cliai_explain
