from __future__ import annotations

import logging

from bot.client import HelzerXBot
from bot.config import Settings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    settings = Settings.from_env()
    bot = HelzerXBot(settings)
    bot.run(settings.token, log_handler=None)


if __name__ == "__main__":
    main()
