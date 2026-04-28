from __future__ import annotations


class CancellationError(Exception):
    def __init__(self):
        super().__init__("Canceled")


def is_cancellation_error(error: object) -> bool:
    return isinstance(error, CancellationError)


def illegal_argument(name: str | None = None) -> ValueError:
    if name:
        return ValueError(f"Illegal argument: {name}")

    return ValueError("Illegal argument")


def illegal_state(name: str | None = None) -> ValueError:
    if name:
        return ValueError(f"Illegal state: {name}")

    return ValueError("Illegal state")


class ReadonlyError(TypeError):
    def __init__(self, name: str | None = None):
        if name:
            super().__init__(f"{name} is read-only and cannot be changed")
        else:
            super().__init__("Cannot change read-only property")


def get_error_message(err: object) -> str:
    if not err:
        return "Error"

    message = getattr(err, "message", None)
    if message:
        return str(message)

    return str(err)


class NotImplementedError_(Exception):
    def __init__(self, message: str | None = None):
        super().__init__(message or "NotImplemented")


class NotSupportedError(Exception):
    def __init__(self, message: str | None = None):
        super().__init__(message or "NotSupported")


class ExpectedError(Exception):
    is_expected = True


class ErrorNoTelemetry(Exception):
    name = "CodeExpectedError"

    @staticmethod
    def from_error(err: Exception) -> ErrorNoTelemetry:
        if isinstance(err, ErrorNoTelemetry):
            return err

        result = ErrorNoTelemetry(str(err))
        return result

    @staticmethod
    def is_error_no_telemetry(err: Exception) -> bool:
        return getattr(err, "name", None) == "CodeExpectedError"


class BugIndicatingError(Exception):
    def __init__(self, message: str | None = None):
        super().__init__(message or "An unexpected bug occurred.")
