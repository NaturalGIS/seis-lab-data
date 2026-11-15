def N_(message: str) -> str:
    """Mark a message as translatable without translating it.

    The translation extraction collects the messages passed to `N_`, while the
    message itself stays in its source language. This suits messages that are
    produced outside of a request, such as in the workers, and translated later
    by the stream handlers into the locale of each of their viewers.

    More info:

    https://docs.python.org/3/library/gettext.html#deferred-translations
    """
    return message


class SeisLabDataError(Exception):
    """Application error carrying a translatable message.

    `message` is an untranslated message template, marked with `N_`, which may hold
    `%(name)s`-style placeholders for the values of `params`. The string
    representation of the error is the template with its values interpolated, in
    the source language.
    """

    def __init__(self, message: str, **params: str | int) -> None:
        super().__init__(message % params if params else message)
        self.message = message
        self.params = params


class UserNotAllowedError(SeisLabDataError):
    pass


class DuplicateResourceError(SeisLabDataError):
    pass
