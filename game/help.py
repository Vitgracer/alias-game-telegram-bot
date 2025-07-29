from telegram import Update
from telegram.ext import ContextTypes


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ Showed how to play the game """
    help_text = (
        "**Available commands:**\n"
        "/start - Start a new TalkFast game.\n"
        "/cancel - Cancel the current game.\n"
        "/help - Show this help message.\n\n"
        "**How to play:**\n"
        "1. Start the game using /start.\n"
        "2. Choose the language and difficulty.\n"
        "3. Enter the number of teams and their names.\n"
        "4. Set the round duration and the number of words needed to win.\n"
        "5. During the round, explain words. Press ✅ if the word is explained, ❌ if skipped.\n"
        "6. The game ends when a team reaches the set number of words.\n"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')