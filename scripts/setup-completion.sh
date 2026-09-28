# Optional TAB-completion step for setup.sh (#294). Sourced, not executed.
#
# llmwiki_offer_completion asks once whether to add the llmwiki completion
# line to the rc file of the user's login shell ($SHELL): ~/.zshrc for zsh,
# ~/.bashrc for bash, or ~/.bash_profile for bash on macOS, where terminals
# start bash as a login shell that does not read ~/.bashrc. It does nothing on
# a non-TTY stdin or when LLMWIKI_SKIP_COMPLETION=1. Must run with the repo
# root as the working directory so `python3 -c` imports this checkout.

llmwiki_offer_completion() {
  [ -t 0 ] || return 0
  [ "${LLMWIKI_SKIP_COMPLETION:-}" != "1" ] || return 0

  local shell_name rc answer result
  shell_name="${SHELL:-}"
  shell_name="${shell_name##*/}"
  case "$shell_name" in
    bash)
      if [ "$(uname 2>/dev/null)" = "Darwin" ]; then
        rc="$HOME/.bash_profile"
      else
        rc="$HOME/.bashrc"
      fi
      ;;
    zsh) rc="$HOME/.zshrc" ;;
    *)
      echo
      echo "==> TAB completion: setup only edits bash and zsh startup files."
      echo "    To add it yourself, put this line in your shell's startup file:"
      python3 -c 'from llmwiki.shell_completion import completion_line; print(completion_line("bash"))' || \
        echo "    (could not print the completion line)"
      return 0
      ;;
  esac

  echo
  printf "Add llmwiki TAB completion to %s? [Y/n] " "$rc"
  read -r answer || answer=""
  case "$answer" in
    n|N|no|NO) return 0 ;;
  esac
  if result=$(python3 -c 'import sys; from pathlib import Path; from llmwiki.shell_completion import install_rc_line; print(install_rc_line(Path(sys.argv[1]), sys.argv[2]))' "$rc" "$shell_name"); then
    echo "    $result: $rc (open a new terminal to use it)"
  else
    echo "    (TAB completion setup did not complete)"
  fi
}
