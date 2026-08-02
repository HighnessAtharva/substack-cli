"""One exception type, one exit path.

Every predictable failure raises CLIError with a message written for a human
who is mid-task. The top-level entry point prints it and exits 1. Nothing else
in the package calls sys.exit, so the library stays importable and testable.
"""


class CLIError(Exception):
    """A failure the user can act on. The message is the whole UI."""


def die(message):
    raise CLIError(message)
