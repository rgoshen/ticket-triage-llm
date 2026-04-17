import logging
import sys
from typing import ClassVar


class StructuredFormatter(logging.Formatter):
    BASE_FORMAT: ClassVar[str] = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

    def __init__(self) -> None:
        super().__init__(fmt=self.BASE_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S%z")


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())

    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        root.addHandler(handler)
