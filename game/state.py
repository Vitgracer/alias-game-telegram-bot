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

# Global variable for game state 
GAME_STATES = {}