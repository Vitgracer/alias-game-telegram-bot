import time
import random 
from telegram.constants import ParseMode
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    ContextTypes, 
    filters
)
from game.help import help_command
from game.state import (
    DEFAULT_GAME_STATE,
    GAME_STATES
)
from game.settings import set_default_commands
from data.loaders import load_words
from utils.logger import LOGGER
from config import BOT_TOKEN


async def start_next_round_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.delete_message() # remove previos button
    await start_round(update, context)

async def show_final_scores(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int = None) -> None:
    if update and update.effective_chat:
        chat_id = update.effective_chat.id
    elif chat_id is None:
        raise ValueError("No chat_id provided to show_final_scores")

    game_state = GAME_STATES[chat_id]

    scores_text = "--- **Final Score** ---\n"
    for team_name, score in game_state['total_scores'].items():
        scores_text += f"**{team_name}**: {score} points\n"
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
            "Game canceled. You can start a new game with /start."
    )

async def end_round(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int = None) -> None:
    """ Finish round and move to the next one """
    if chat_id is None: # If call not from the force function 
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
        text=f"Round for **{current_team['name']}** is over!\n"
             f"Words explained: {game_state['explained_words_count']}\n"
             f"Words skipped: {game_state['skipped_words_count']}\n"
             f"Points this round: {score_this_round}\n"
             f"Total score for team **{current_team['name']}**: {current_team['score']}\n\n",
        parse_mode='Markdown'
    )

    # win? 
    for team in game_state['teams']:
        if team['score'] >= game_state['words_to_win']:
            game_state['in_game'] = False # game is finished 
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"**WIN!!!** Team **{team['name']}** achieved {team['score']} points and won!",
                parse_mode='Markdown'
            )
            await show_final_scores(update, context, chat_id)
            return

    # To the next team 
    game_state['current_team_index'] = (game_state['current_team_index'] + 1) % len(game_state['teams'])

    # next round? 
    keyboard = [[InlineKeyboardButton("Start the next round", callback_data='start_next_round')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Get ready, it's the next turn for team: **{game_state['teams'][game_state['current_team_index']]['name']}**",
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
        await query.edit_message_text("Game is not active.")
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
        LOGGER.warning(f"Impossible to delete the message. {e}")

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
            text="⌛️ Time's up!"
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
                text=f"⏰⏰⏰ *{remaining_time}* seconds left ⏰⏰⏰",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e:
            LOGGER.warning(f"Error while updating the timer message: {e}")
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
        text=f"⏰⏰⏰ *{game_state['round_time']}* seconds left ⏰⏰⏰",
        parse_mode=ParseMode.MARKDOWN_V2
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
        [InlineKeyboardButton("✅ Understood", callback_data='word_explained')],
        [InlineKeyboardButton("❌ Skip", callback_data='word_skipped')]
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
        await update.message.reply_text("❌ The game hasn't started yet. Use /start to begin.")
        return

    current_team = game_state['teams'][game_state['current_team_index']]
    await context.bot.send_message(
        chat_id=chat_id,
        text = ( f"🚨 The round for team *{current_team['name']}* is starting\\! \n"
                 f"⏳ You have *{game_state['round_time']}* seconds\\. \n\n" 
                 f"🚀🚀🚀 *Get ready\\! 🚀🚀🚀*" ),
        parse_mode=ParseMode.MARKDOWN_V2
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
                    GAME_STATES[chat_id]['teams'] = [{'name': f'Team {i+1}', 'score': 0} for i in range(num_teams)]
                    await update.message.reply_text(
                        f"✅ *{num_teams} teams* set\\.\n" \
                         "Now enter team names one by one, starting with the *first team*\\.",
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                    context.user_data['current_team_naming_index'] = 0
                    context.user_data['next_step'] = 'set_team_names'
                else:
                    await update.message.reply_text("🚫 Please enter a number between 2 and 4.")
            except ValueError:
                await update.message.reply_text("🚫 That's not a number. Try again:")

        elif step == 'set_team_names':
            current_index = context.user_data['current_team_naming_index']
            team_name = update.message.text.strip()
            if team_name:
                GAME_STATES[chat_id]['teams'][current_index]['name'] = team_name
                GAME_STATES[chat_id]['total_scores'][team_name] = 0
                context.user_data['current_team_naming_index'] += 1

                if context.user_data['current_team_naming_index'] < len(GAME_STATES[chat_id]['teams']):
                    await update.message.reply_text(
                        f"✏️ Enter the name for the next team:"
                    )
                else:
                    del context.user_data['current_team_naming_index']
                    await update.message.reply_text(
                        "🕗 Now enter the round duration in seconds:"
                    )
                    context.user_data['next_step'] = 'set_round_time'
            else:
                await update.message.reply_text("🚫 The team name cannot be empty. Please try again.")

        elif step == 'set_round_time':
            try:
                round_time = int(update.message.text)
                if round_time > 0:
                    GAME_STATES[chat_id]['round_time'] = round_time
                    await update.message.reply_text(
                        "🔢 Enter the number of explained words needed to win:"
                    )
                    context.user_data['next_step'] = 'set_words_to_win'
                else:
                    await update.message.reply_text("🚫 The round time must be a positive number. Try again:")
            except ValueError:
                await update.message.reply_text("🚫 This is not a number. Please enter the round duration in seconds:")

        elif step == 'set_words_to_win':
            try:
                words_to_win = int(update.message.text)
                if words_to_win > 0:
                    GAME_STATES[chat_id]['words_to_win'] = words_to_win
                    del context.user_data['next_step'] # finish game settings 
                    GAME_STATES[chat_id]['in_game'] = True
                    await update.message.reply_text("✅ Game settings are complete!")
                    await start_round(update, context)
                else:
                    await update.message.reply_text("🚫 The number of words must be a positive number. Try again:")
            except ValueError:
                await update.message.reply_text("🚫 This is not a number. Try again:")

async def set_difficulty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set up difficulty and suggest to choose the number of teams."""
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    difficulty = query.data.split('_')[2]
    GAME_STATES[chat_id]['difficulty'] = difficulty
    GAME_STATES[chat_id]['words'] = load_words(GAME_STATES[chat_id]['language'], difficulty, LOGGER)

    await query.edit_message_text(
        "🧑‍🤝‍🧑 Enter the number of teams (from 2 to 4):"
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
        [InlineKeyboardButton("🟢 Easy", callback_data='set_difficulty_easy')],
        [InlineKeyboardButton("🟠 Medium", callback_data='set_difficulty_medium')],
        [InlineKeyboardButton("🔴 Hard", callback_data='set_difficulty_hard')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "🎯 Select the difficulty level:",
        reply_markup=reply_markup
    )

async def start_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ Set up game configuration """
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    GAME_STATES[chat_id] = DEFAULT_GAME_STATE.copy()

    keyboard = [
        [InlineKeyboardButton("🇩🇪 Deutsch", callback_data='set_lang_de')],
        [InlineKeyboardButton("🇬🇧 English", callback_data='set_lang_en')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "🌐 *Choose the game language*:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs the app and suggest to start the game"""
    chat_id = update.effective_chat.id
    GAME_STATES[chat_id] = DEFAULT_GAME_STATE.copy()

    keyboard = [[InlineKeyboardButton("Start a new game", callback_data='start_game')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Hi\\! I'm a bot for playing *TalkFast* 🎉\n\n"
        "Click *START NEW GAME* 🔄 to get started\\!",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )

def main() -> None:
    # create basic application
    application = Application.builder().token(BOT_TOKEN).build()
    application.job_queue.run_once(set_default_commands, 0)

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