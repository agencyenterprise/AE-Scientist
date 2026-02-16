import logging
import logging.config

CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(levelname)s [%(asctime)s] %(name)s - %(message)s",
        },
    },
    "handlers": {
        "stderr": {
            "class": logging.StreamHandler,
            "formatter": "standard",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "aigraph": {
            "handlers": ["stderr"],
            "level": logging.DEBUG,
        },
    },
}


def init() -> None:
    logging.config.dictConfig(CONFIG)
