from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ Showed how to play the game """

    help_text = (
        "*Available commands:*\n\n"
        "/start – Start a new TalkFast game 🚀\n"
        "/cancel – Cancel the current game ❌\n"
        "/help – Show this help message 🆘\n\n"
        
        "*How to play:*\n\n"
        "1\\. Start the game using /start\n"
        "2\\. Choose the language and difficulty\n"
        "3\\. Enter the number of teams and their names\n"
        "4\\. Set the round duration and number of words to win\n"
        "5\\. During the round, explain words:\n"
        "   ✅  Press if the word is explained\n"
        "   ❌  Press if the word is skipped\n"
        "6\\. The game ends when a team reaches the goal\n"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN_V2)