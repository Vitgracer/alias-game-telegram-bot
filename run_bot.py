# main.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from config import BOT_TOKEN

# basic logging turned on 
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global variable for game state 
GAME_STATES = {}

DEFAULT_GAME_STATE = {
    'in_game': False,
    'language': None,
    'teams': [],
    'current_team_index': 0,
    'round_time': 60, # seconds
    'words_to_win': 15,
    'current_round_words': [],
    'explained_words_count': 0,
    'skipped_words_count': 0,
    'current_word_index': 0,
    'round_timer_message_id': None,
    'timer_start_time': None,
    'difficulty': None,
    'total_scores': {} # Final score for each team
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs the app and suggest to start the game"""
    chat_id = update.effective_chat.id
    GAME_STATES[chat_id] = DEFAULT_GAME_STATE.copy()

    keyboard = [[InlineKeyboardButton("Начать новую игру", callback_data='start_game')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Привет! Я бот для игры в Alias. Нажми **Начать новую игру**, чтобы приступить!",
        reply_markup=reply_markup
    )

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
    # create basic application
    application = Application.builder().token(BOT_TOKEN).build()

    # add basic commands 
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("start", start))
    
    # run bot 
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()