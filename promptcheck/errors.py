"""Domain errors. Services raise these; main.py maps them to HTTP status codes."""


class DomainError(Exception):
    status_code = 400


class NotFoundError(DomainError):
    status_code = 404


class InvalidInputError(DomainError):
    status_code = 422


class ConflictError(DomainError):
    status_code = 409
