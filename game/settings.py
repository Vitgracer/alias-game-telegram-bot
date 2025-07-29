from utils.logger import LOGGER
from telegram.ext import Application


async def set_default_commands(application: Application):
    commands = [
        ("start", "Start a new game"),
        ("cancel", "Cancel the current game"),
        ("help", "Show a help message")
    ]
    await application.bot.set_my_commands(commands)
    LOGGER.info("Start bots commands are set up!")