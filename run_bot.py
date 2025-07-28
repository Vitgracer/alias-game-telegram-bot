# main.py
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from config import BOT_TOKEN

# basic logging turned on 
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global variable for game state 
GAME_STATES = {}

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ Showed how to play the game """

    help_text = (
        "**Доступные команды:**\n"
        "/start - Начать новую игру Alias.\n"
        "/cancel - Отменить текущую игру.\n"
        "/help - Показать это сообщение помощи.\n\n"
        "**Как играть:**\n"
        "1. Запустите игру с помощью /start.\n"
        "2. Выберите язык и сложность.\n"
        "3. Введите количество команд и их названия.\n"
        "4. Установите длину раунда и количество слов для победы.\n"
        "5. Во время раунда объясняйте слова. Нажимайте ✅, если слово объяснено, ❌, если пропущено.\n"
        "6. Игра заканчивается, когда команда набирает заданное количество слов.\n"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    # add basic commands 
    application.add_handler(CommandHandler("help", help_command))
    
    # run bot 
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()