import time
import random 
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

async def start_next_round_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.delete_message() # remove previos button
    await start_round(update, context)

async def show_final_scores(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    game_state = GAME_STATES[chat_id]

    scores_text = "--- **Финальный счет** ---\n"
    for team_name, score in game_state['total_scores'].items():
        scores_text += f"**{team_name}**: {score} очков\n"
    scores_text += "-----------------------\n"

    await context.bot.send_message(
        chat_id=chat_id,
        text=scores_text,
        parse_mode='Markdown'
    )
    # clean the state 
    GAME_STATES[chat_id] = DEFAULT_GAME_STATE.copy()

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        GAME_STATES[chat_id] = DEFAULT_GAME_STATE.copy()
        await update.message.reply_text(
            "Игра отменена. Вы можете начать новую игру, используя /start."
    )

async def end_round(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int = None) -> None:
    """ Finish round and move to the next one """
    if chat_id is None: # If call not fron the force function 
        chat_id = update.effective_chat.id

    game_state = GAME_STATES[chat_id]

    if not game_state['in_game']:
        return 

    current_team = game_state['teams'][game_state['current_team_index']]
    score_this_round = game_state['explained_words_count']

    current_team['score'] += score_this_round
    game_state['total_scores'][current_team['name']] += score_this_round

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Раунд для **{current_team['name']}** завершен!\n"
             f"Объяснено слов: {game_state['explained_words_count']}\n"
             f"Пропущено слов: {game_state['skipped_words_count']}\n"
             f"Очки за раунд: {score_this_round}\n"
             f"Общий счет команды **{current_team['name']}**: {current_team['score']}\n\n",
        parse_mode='Markdown'
    )

    # win? 
    max_score = 0
    winning_team = None
    for team in game_state['teams']:
        if team['score'] >= game_state['words_to_win']:
            game_state['in_game'] = False # game is finished 
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"**ПОБЕДА!** Команда **{team['name']}** достигла {team['score']} очков и выиграла игру!",
                parse_mode='Markdown'
            )
            await show_final_scores(update, context)
            return

    # To the next team 
    game_state['current_team_index'] = (game_state['current_team_index'] + 1) % len(game_state['teams'])

    # next round? 
    keyboard = [[InlineKeyboardButton("Начать следующий раунд", callback_data='start_next_round')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Приготовьтесь, следующий ход команды: **{game_state['teams'][game_state['current_team_index']]['name']}**",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def handle_word_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ Process the word: skip or accept """
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    game_state = GAME_STATES[chat_id]

    if not game_state['in_game']:
        await query.edit_message_text("Игра не активна.")
        return

    action = query.data

    if action == 'word_explained':
        game_state['explained_words_count'] += 1
    elif action == 'word_skipped':
        game_state['skipped_words_count'] += 1

    game_state['current_word_index'] += 1

    # remove previous word 
    try:
        await query.delete_message()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")

    # do we have time? 
    elapsed_time = time.time() - game_state['timer_start_time']
    if elapsed_time < game_state['round_time']:
        await show_next_word(update, context)
    else:
        await end_round(update, context)

async def end_round_force(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    game_state = GAME_STATES[chat_id]
    if game_state['in_game']:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Время вышло!"
        )
        await end_round(None, context, chat_id=chat_id)

async def update_timer(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context.job.chat_id
    message_id = context.job.data
    game_state = GAME_STATES[chat_id]

    if not game_state['in_game']:
        context.job.schedule_removal()
        return # If game is not active, stop timer 

    elapsed_time = time.time() - game_state['timer_start_time']
    remaining_time = int(game_state['round_time'] - elapsed_time)

    if remaining_time > 0:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"Осталось: {remaining_time} секунд"
            )
        except Exception as e:
            logger.warning(f"Ошибка при обновлении сообщения таймера: {e}")
            context.job.schedule_removal()
            await end_round_force(chat_id, context)
    else:
        context.job.schedule_removal()
        await end_round_force(chat_id, context)

async def start_timer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ Run round timer """
    chat_id = update.effective_chat.id
    game_state = GAME_STATES[chat_id]

    # first timer message
    timer_message = await context.bot.send_message(
        chat_id=chat_id,
        text=f"Осталось: {game_state['round_time']} секунд"
    )
    game_state['round_timer_message_id'] = timer_message.message_id

    # update timer
    context.application.job_queue.run_repeating(
        callback=update_timer,
        interval=1,
        first=1,
        chat_id=chat_id,
        name=f"timer_{chat_id}",
        data=timer_message.message_id
    )

async def show_next_word(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    game_state = GAME_STATES[chat_id]

    word = list(game_state['current_round_words'].keys())[game_state['current_word_index']]
    translate = game_state['current_round_words'][word]
    keyboard = [
        [InlineKeyboardButton("✅ Понял", callback_data='word_explained')],
        [InlineKeyboardButton("❌ Пропустить", callback_data='word_skipped')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"**{word}** ({translate})",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def start_round(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ New round start! """
    chat_id = update.effective_chat.id
    game_state = GAME_STATES[chat_id]

    if not game_state['in_game']:
        await update.message.reply_text("Игра еще не началась. Используйте /start.")
        return

    current_team = game_state['teams'][game_state['current_team_index']]
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Начинается раунд для команды: **{current_team['name']}**!\n"
             f"У вас {game_state['round_time']} секунд. Приготовьтесь!",
        parse_mode='Markdown'
    )

    # current round status is set to zero 
    game_state['explained_words_count'] = 0
    game_state['skipped_words_count'] = 0
    all_words = list(game_state['words'].keys())
    sampled_words = random.sample(all_words, k=min(len(all_words), 50))
    round_words_dict = {k: game_state['words'][k] for k in sampled_words}
    game_state['current_round_words'] = round_words_dict
    game_state['current_word_index'] = 0

    game_state['timer_start_time'] = time.time()
    await start_timer(update, context)
    await show_next_word(update, context)
    

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
                    await start_round(update, context)
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
    application.add_handler(CommandHandler("cancel", cancel))
    
    # buttons processing 
    application.add_handler(CallbackQueryHandler(start_game_callback, pattern='^start_game$'))
    application.add_handler(CallbackQueryHandler(set_language, pattern='^set_lang_'))
    application.add_handler(CallbackQueryHandler(set_difficulty, pattern='^set_difficulty_'))
    application.add_handler(CallbackQueryHandler(handle_word_action, pattern='^word_'))
    application.add_handler(CallbackQueryHandler(start_next_round_callback, pattern='^start_next_round$'))

    # user input processing (text)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # run bot 
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()