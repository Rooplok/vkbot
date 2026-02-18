import logging
import sys

from vkbottle.bot import Bot

from .config import Settings
from .handlers import register_handlers


def setup_logging() -> None:
    """Простейшая настройка логов в stdout (видно в docker logs)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stdout,
    )


def main():
    setup_logging()
    log = logging.getLogger(__name__)

    settings = Settings()  # читает .env
    bot = Bot(token=settings.vk_group_token)

    register_handlers(bot, settings)

    log.info("VK bot starting (Long Poll)...")
    bot.run_forever()


if __name__ == "__main__":
    main()
