"""Interactive REPL for Novel-Claude CLI."""
import os
import sys

_HAS_PROMPT_TOOLKIT = False
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.styles import Style
    from prompt_toolkit.key_binding import KeyBindings
    _HAS_PROMPT_TOOLKIT = True
except ImportError:
    pass

from cli.dispatcher import CommandDispatcher
from cli.project_manager import project_manager


def _get_prompt_text() -> str:
    """Generate the prompt string based on current context (text fallback)."""
    project = project_manager.current_project or "none"
    return f"[Novel: {project}] (vol:{project_manager.current_volume}, ch:{project_manager.current_chapter}) > "


if _HAS_PROMPT_TOOLKIT:
    from cli.completer import NovelClaudeCompleter

    def get_prompt() -> FormattedText:
        project = project_manager.current_project or "none"
        vol = project_manager.current_volume
        ch = project_manager.current_chapter
        return FormattedText([
            ('ansicyan', '[Novel: '),
            ('ansigreen bold', project),
            ('ansicyan', '] ('),
            ('ansiyellow', f'vol:{vol}'),
            ('ansicyan', ', '),
            ('ansiyellow', f'ch:{ch}'),
            ('ansicyan', ') > '),
        ])

if _HAS_PROMPT_TOOLKIT:
    # Key bindings for special keys
    kb = KeyBindings()

    @kb.add('c-c', eager=True)
    def _(event):
        """Handle Ctrl-C gracefully."""
        print("\n[Use /exit to quit]", flush=True)

    # REPL Style
    style = Style.from_dict({
        'prompt': '#00aaaa',
        'username': '#00ff00',
        'hostname': '#ff0066',
    })
else:
    kb = None
    style = None


class REPL:
    """Interactive read-eval-print loop for Novel-Claude.
    Supports prompt_toolkit (rich UI) with readline fallback.
    """

    def __init__(self):
        self.dispatcher = CommandDispatcher()
        self._history_file = os.path.expanduser("~/.novel_claude_history")
        self._history = []
        self._load_history()

        if _HAS_PROMPT_TOOLKIT:
            self._pt_history = FileHistory(self._history_file)
            self._pt_completer = NovelClaudeCompleter()
            self._pt_session = PromptSession(
                history=self._pt_history,
                key_bindings=kb,
                style=style,
                completer=self._pt_completer,
            )

    def _load_history(self):
        try:
            with open(self._history_file, "r", encoding="utf-8") as f:
                self._history = [line.rstrip("\n") for line in f.readlines()[-500:]]
        except FileNotFoundError:
            self._history = []

    def _save_history(self):
        try:
            os.makedirs(os.path.dirname(self._history_file), exist_ok=True)
            with open(self._history_file, "w", encoding="utf-8") as f:
                f.write("\n".join(self._history[-500:]) + "\n")
        except Exception:
            pass

    def print_banner(self):
        mode = "PT" if _HAS_PROMPT_TOOLKIT else "readline"
        print("=" * 60)
        print(f"  Novel-Claude V3 Interactive CLI ({mode})")
        print("  Type /help for available commands")
        print("=" * 60)

    def print_error(self, msg: str):
        print(f"[ERROR] {msg}")

    def print_success(self, msg: str):
        print(f"[OK] {msg}")

    def print_info(self, msg: str):
        print(f"[INFO] {msg}")

    def _read_input(self) -> str:
        if _HAS_PROMPT_TOOLKIT:
            return self._pt_session.prompt(get_prompt)
        else:
            return input(_get_prompt_text())

    def run(self):
        self.print_banner()

        while True:
            try:
                user_input = self._read_input()
            except KeyboardInterrupt:
                print()
                continue
            except EOFError:
                break

            if not user_input.strip():
                continue

            self._history.append(user_input)

            # Handle built-in commands
            if user_input.strip() == '/exit':
                print("Goodbye!")
                break

            if user_input.strip() == '/help':
                self._print_help()
                continue

            if user_input.strip() == '/history':
                for i, cmd in enumerate(self._history[-50:]):
                    print(f"  {i}: {cmd}")
                continue

            if user_input.strip() == '/clear':
                print("\033[2J\033[H", end="")
                continue

            # Dispatch command
            result = self.dispatcher.dispatch(user_input)

            if result.get('error'):
                self.print_error(result['error'])
            elif result.get('message'):
                print(result['message'])
            elif result.get('output'):
                print(result['output'])

        # Save state on exit
        project_manager._save_state()
        self._save_history()

    def _print_help(self):
        """Print available commands."""
        help_text = """
Available Commands:
===================

Built-in:
  /help     - Show this help
  /exit     - Exit the CLI
  /clear    - Clear the screen
  /history  - Show command history

Project Management:
  projects create <name> <logline>  - Create a new project
  projects switch <name>           - Switch to a project
  projects list                     - List all projects
  projects info                     - Show current project info
  projects delete <name>            - Delete a project

Novel Workflow (Snowflake Method):
  init <logline>                    - Initialize world (goldfinger → one_sentence)
  expand                            - Expand to story outline
  world                             - Design world setting
  blueprint                        - Generate core blueprint (characters, scenes, orgs)
  plan [volume]                     - Generate volume outlines (10 volumes)
  plan --volume N                   - Generate stage outlines for volume N
  write --volume N --chapters X-Y  - Write chapters
  audit --stage N                   - Audit stage consistency
  audit --chapter N                 - Audit chapter consistency
  track --volume N --chapter M      - Track entity state changes
  reindex --volume N --chapters X-Y - Reindex chapters to RAG
  batch build/submit/sync           - Batch API workflow

File Operations:
  ls [path]                          - List directory
  cat <file>                        - Show file contents
  find <pattern>                     - Find files
  cd <path>                          - Change directory
  pwd                               - Print working directory

Skills:
  skills list                       - List all skills
  skills enable/disable <name>      - Enable/disable a skill
  skills reload [name]               - Reload skills
  skills build <request>             - Build a new skill

Settings:
  settings show                     - Show current settings
  settings set <key> <value>         - Set a config value

Agent:
  agent review -f <file> -i <inst>  - Review files with AI

Note: Commands can also be used without '/' prefix.
        """
        print(help_text)


def start_repl():
    """Entry point to start the REPL."""
    repl = REPL()
    repl.run()