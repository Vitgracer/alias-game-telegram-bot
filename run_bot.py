import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    ContextTypes, 
    filters
)
from data.loaders import load_words
from game.state import DEFAULT_GAME_STATE
from config import BOT_TOKEN

# basic logging turned on 
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global variable for game state 
GAME_STATES = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Here we process messages from the user depending on the current state"""
    chat_id = update.effective_chat.id
    if 'next_step' in context.user_data:
        step = context.user_data['next_step']

        if step == 'set_num_teams':
            try:
                num_teams = int(update.message.text)
                if 2 <= num_teams <= 4:
                    GAME_STATES[chat_id]['teams'] = [{'name': f'Команда {i+1}', 'score': 0} for i in range(num_teams)]
                    GAME_STATES[chat_id]['total_scores'] = {f'Команда {i+1}': 0 for i in range(num_teams)}
                    await update.message.reply_text(
                        f"Установлено {num_teams} команды. Теперь введите названия команд по одному сообщению, начиная с первой команды."
                    )
                    context.user_data['current_team_naming_index'] = 0
                    context.user_data['next_step'] = 'set_team_names'
                else:
                    await update.message.reply_text("Пожалуйста, введите число от 2 до 4.")
            except ValueError:
                await update.message.reply_text("Это не число. Пожалуйста, введите количество команд (от 2 до 4)")

        elif step == 'set_team_names':
            current_index = context.user_data['current_team_naming_index']
            team_name = update.message.text.strip()
            if team_name:
                GAME_STATES[chat_id]['teams'][current_index]['name'] = team_name
                GAME_STATES[chat_id]['total_scores'][team_name] = 0
                context.user_data['current_team_naming_index'] += 1

                if context.user_data['current_team_naming_index'] < len(GAME_STATES[chat_id]['teams']):
                    await update.message.reply_text(
                        f"Введите название для {GAME_STATES[chat_id]['teams'][context.user_data['current_team_naming_index']]['name']}:"
                    )
                else:
                    del context.user_data['current_team_naming_index']
                    await update.message.reply_text(
                        "Названия команд установлены. Теперь введите длину раунда в секундах (например, 60, 90, 120):"
                    )
                    context.user_data['next_step'] = 'set_round_time'
            else:
                await update.message.reply_text("Название команды не может быть пустым. Попробуйте еще раз.")

        elif step == 'set_round_time':
            try:
                round_time = int(update.message.text)
                if round_time > 0:
                    GAME_STATES[chat_id]['round_time'] = round_time
                    await update.message.reply_text(
                        "Длина раунда установлена. Теперь введите число объясненных слов для победы:"
                    )
                    context.user_data['next_step'] = 'set_words_to_win'
                else:
                    await update.message.reply_text("Время раунда должно быть положительным числом. Попробуйте еще раз.")
            except ValueError:
                await update.message.reply_text("Это не число. Пожалуйста, введите длину раунда в секундах:")

        elif step == 'set_words_to_win':
            try:
                words_to_win = int(update.message.text)
                if words_to_win > 0:
                    GAME_STATES[chat_id]['words_to_win'] = words_to_win
                    del context.user_data['next_step'] # finish game settings 
                    GAME_STATES[chat_id]['in_game'] = True
                    await update.message.reply_text("Настройки игры завершены! Начинаем игру.")
                    #await start_round(update, context)
                else:
                    await update.message.reply_text("Число слов для победы должно быть положительным числом. Попробуйте еще раз.")
            except ValueError:
                await update.message.reply_text("Это не число. Пожалуйста, введите число объясненных слов для победы:")

async def set_difficulty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set up difficulty and suggest to choose the number of teams."""
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    difficulty = query.data.split('_')[2]
    GAME_STATES[chat_id]['difficulty'] = difficulty
    GAME_STATES[chat_id]['words'] = load_words(GAME_STATES[chat_id]['language'], difficulty, logger)

    await query.edit_message_text(
        "Отлично! Теперь введите количество команд (от 2 до 4):"
    )
    context.user_data['next_step'] = 'set_num_teams'

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ Set langiage and complexity """
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    lang_code = query.data.split('_')[2]
    GAME_STATES[chat_id]['language'] = lang_code

    keyboard = [
        [InlineKeyboardButton("Простой", callback_data='set_difficulty_easy')],
        [InlineKeyboardButton("Средний", callback_data='set_difficulty_medium')],
        [InlineKeyboardButton("Сложный", callback_data='set_difficulty_hard')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"Вы выбрали {lang_code.upper()} язык. Теперь выберите сложность:",
        reply_markup=reply_markup
    )

async def start_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ Set up game configuration """
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    GAME_STATES[chat_id] = DEFAULT_GAME_STATE.copy() # Сброс состояния игры

    keyboard = [
        [InlineKeyboardButton("Немецкий", callback_data='set_lang_de')],
        [InlineKeyboardButton("Английский", callback_data='set_lang_en')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "Выберите язык игры:",
        reply_markup=reply_markup
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs the app and suggest to start the game"""
    chat_id = update.effective_chat.id
    GAME_STATES[chat_id] = DEFAULT_GAME_STATE.copy()

    keyboard = [[InlineKeyboardButton("Начать новую игру", callback_data='start_game')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Привет! Я бот для игры в Alias. Нажми НАЧАТЬ НОВУЮ ИГРУ, чтобы приступить!",
        reply_markup=reply_markup,
        parse_mode='Markdown'
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

    # commands processing 
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("start", start))
    
    # buttons processing 
    application.add_handler(CallbackQueryHandler(start_game_callback, pattern='^start_game$'))
    application.add_handler(CallbackQueryHandler(set_language, pattern='^set_lang_'))
    application.add_handler(CallbackQueryHandler(set_difficulty, pattern='^set_difficulty_'))

    # user input processing (text)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # run bot 
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()