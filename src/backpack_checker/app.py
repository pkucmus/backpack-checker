import logging
from collections.abc import Iterable
from enum import Enum
from pathlib import Path
from typing import Any

from textual import on, work
from textual.app import App, ComposeResult, SystemCommand
from textual.containers import (
    Horizontal,
    HorizontalGroup,
    Vertical,
    VerticalGroup,
    VerticalScroll,
)
from textual.lazy import Lazy
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Collapsible,
    Digits,
    Footer,
    Header,
    Label,
    Markdown,
    RichLog,
)

from backpack_checker.checker import BaseCheck, Necessity
from backpack_checker.log_handler import RichLogHandler

BASE_DIR = Path(__file__).parent

rich_log_widget = RichLog(id="logs", classes="hidden", max_lines=1000)
rich_log_widget.border_title = "Logs"


logging.basicConfig(
    level="INFO",
    handlers=[RichLogHandler(rich_log_widget)],
    format="%(message)s",
    datefmt="[%X]",
)
LOGGER = logging.getLogger(__name__)


class CheckerState(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    NOT_RUN = "not_run"


class Content(VerticalScroll):
    """Non focusable vertical scroll."""


class Checker(VerticalGroup):
    """A widget to display the status of a checker."""

    state: reactive[CheckerState] = reactive(CheckerState.NOT_RUN, recompose=True)

    class Completed(Message):
        check: BaseCheck
        state: CheckerState

        def __init__(self, check: BaseCheck, state: CheckerState):
            self.check = check
            self.state = state
            super().__init__()

    def __init__(self, index_number: int, check: BaseCheck, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.index_number = index_number
        self.check = check

    def compose(self) -> ComposeResult:
        if self.state == CheckerState.SUCCESS:
            self.add_class("success")
        elif self.state == CheckerState.ERROR:
            self.add_class("error")
        elif self.state == CheckerState.WARNING:
            self.add_class("warning")
        with VerticalGroup():
            with HorizontalGroup():
                yield Digits(str(self.index_number + 1))
                yield Markdown(self.check.name)
                yield Label(self.check.necessity.value)
            with Collapsible(
                title="Explanation",
                collapsed=False
                if self.state in (CheckerState.ERROR, CheckerState.WARNING)
                else True,
            ):
                yield Markdown(self.check.explanation)

    @work(exclusive=True, thread=True)
    async def invoke_check(self) -> None:
        try:
            result = await self.check()
        except Exception:
            LOGGER.error(
                "Error running check %s",
                self.check.__class__.__name__,
                extra={"check": self.check, "__class__": self.check.__class__},
            )
            result = False

        if result:
            self.state = CheckerState.SUCCESS
        else:
            if self.check.necessity == Necessity.REQUIRED:
                self.state = CheckerState.ERROR
            else:
                self.state = CheckerState.WARNING

        self.post_message(self.Completed(self.check, self.state))

    async def on_mount(self) -> None:
        self.call_after_refresh(self.invoke_check)


class Heading(Vertical):
    success = reactive(0, recompose=True)
    to_go = reactive(0, recompose=True)
    errors = reactive(0, recompose=True)

    def __init__(self, total: int, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.total = total
        self.was_done = False

    def compute_to_go(self) -> int:
        to_go = self.total - self.success - self.errors
        if to_go < 0:
            to_go = 0

        if to_go == 0:
            self.notify_done()
        return to_go

    def notify_done(self) -> None:
        if not self.was_done:
            self.was_done = True
            self.notify("All checks are done!")

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="success"):
                yield Label("Success")
                yield Digits(str(self.success))
            with Vertical(id="to_go"):
                yield Label("To Go")
                yield Digits(str(self.to_go))
            with Vertical(id="errors"):
                yield Label("Errors")
                yield Digits(str(self.errors))


WHAT_IS_BACKPACK = """\
# What is this app?

This is a backpack app. It is supposed to tell you which tools you should take with you
when you go on a journey. 

## How does it work?

It checks if you have the necessary tools installed on your system. If you don't, it 
will tell you what you need to install. If you do, it will tell you that you are ready
to go.
"""


class BackpackApp(App):
    """A Textual app to manage stopwatches."""

    TITLE = "Backpack"
    CSS_PATH = BASE_DIR / "default.tcss"
    checks: list[BaseCheck]
    checks_done: reactive[int] = reactive(0, recompose=True)

    def __init__(self, checks: list[BaseCheck]):
        self.checks = checks
        super().__init__()

    @on(Checker.Completed)
    def update_counts(self, message: Checker.Completed) -> None:
        heading = self.query_one(Heading)
        if message.state in (CheckerState.SUCCESS, CheckerState.WARNING):
            heading.success += 1
        elif message.state == CheckerState.ERROR:
            heading.errors += 1

    def on_mount(self) -> None:
        self.theme = "catppuccin-mocha"

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Footer()
        yield Heading(len(self.checks))
        with Content():
            yield rich_log_widget
            yield Markdown(WHAT_IS_BACKPACK)
            for index, check in enumerate(self.checks):
                yield Lazy(Checker(index, check))

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)

        yield SystemCommand(
            "Toggle Logs",
            "Show or hide the log panel in the top of the main screen",
            self.toggle_logs,
        )

    async def toggle_logs(self) -> None:
        self.query_one("#logs").toggle_class("hidden")
