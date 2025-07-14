class OpsmithException(Exception):
    """Base exception class for all opsmith exceptions."""

    pass


class MonolithicDeploymentError(OpsmithException):
    """Raised for errors specific to the monolithic deployment strategy."""

    pass
