class SeisLabDataError(Exception):
    pass


class UserNotAllowedError(SeisLabDataError):
    pass


class DuplicateResourceError(SeisLabDataError):
    pass
