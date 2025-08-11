
import logging
import sys
import os

from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("axiom-node")

stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.setFormatter(
    logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s"
    )
)

logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


class Config(BaseModel):
	host: str
	port: int

CONFIG = Config(
	host=os.environ.get("HOST", ""),
	port=int(os.environ["PORT"]),
)

if __name__ == "__main__":
	pass
