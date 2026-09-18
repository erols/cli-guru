# cli-guru — zsh integration (macOS default shell).
# Not a port of the bash file: zsh uses ZLE widgets and $BUFFER/$CURSOR.
#
# Ctrl-X Ctrl-A : ask     Ctrl-X Ctrl-H : explain

[[ -o interactive ]] || return 0
command -v cli-guru >/dev/null 2>&1 || return 0

__cli_guru_key_taken() {
  local cur
  cur=$(bindkey "$1" 2>/dev/null)
  [[ -z $cur || $cur == *" undefined-key" || $cur == *" self-insert" ]] && return 1
  return 0
}

# See cli-guru.bash: /dev/tty is fatal where there is no controlling terminal.
__cli_guru_errfile=/dev/null
if ( exec </dev/tty ) 2>/dev/null; then
  __cli_guru_run() { cli-guru "$@" 2>"$__cli_guru_errfile" </dev/tty; }
else
  __cli_guru_run() { cli-guru "$@" 2>"$__cli_guru_errfile"; }
fi

__cli_guru_ask() {
  local out hist err
  hist=$(fc -ln -${CLI_GURU_HISTORY_LINES:-10} 2>/dev/null)
  __cli_guru_errfile=$(mktemp 2>/dev/null) || __cli_guru_errfile=/dev/null
  out=$(CLI_GURU_HISTORY="$hist" __cli_guru_run ask -- "$BUFFER")
  if [[ $__cli_guru_errfile != /dev/null ]]; then
    err=$(cat "$__cli_guru_errfile" 2>/dev/null)
    rm -f "$__cli_guru_errfile"
  fi
  __cli_guru_errfile=/dev/null
  # stderr carries the destructive-command warning and failure reasons.
  [[ -n $err ]] && printf '\n%s\n' "$err" && zle reset-prompt
  [[ -n $out ]] || return 0
  BUFFER="$out"
  CURSOR=${#BUFFER}
}

__cli_guru_explain() {
  [[ -n $BUFFER ]] || return 0
  printf '\n'
  if ( exec </dev/tty ) 2>/dev/null; then
    cli-guru explain -- "$BUFFER" </dev/tty
  else
    cli-guru explain -- "$BUFFER"
  fi
  printf '\n'
  zle reset-prompt
}

zle -N __cli_guru_ask
zle -N __cli_guru_explain

__cli_guru_bind() {
  local seq=$1 widget=$2
  if [[ ${CLI_GURU_FORCE_KEY:-0} != 1 ]] && __cli_guru_key_taken "$seq"; then
    local held="$(bindkey "$seq" | awk '{print $2}')"
    print -u2 "cli-guru: $seq is bound to $held; set CLI_GURU_KEY, or CLI_GURU_FORCE_KEY=1"
    return 1
  fi
  bindkey "$seq" "$widget"
}

__cli_guru_bind "${CLI_GURU_KEY:-^X^A}" __cli_guru_ask
__cli_guru_bind "${CLI_GURU_KEY_EXPLAIN:-^X^H}" __cli_guru_explain
