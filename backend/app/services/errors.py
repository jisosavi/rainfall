class NotFoundError(Exception):
    """A station, or any data for the request, doesn't exist (REST: 404)."""


class InvalidRequestError(Exception):
    """The request can't be answered as asked, e.g. a range that's too long (REST: 422)."""
