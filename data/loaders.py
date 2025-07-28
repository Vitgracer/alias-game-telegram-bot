import json


def load_words(language, difficulty, logger):
    path_to_file = f"data/words/{language}_{difficulty}_words.json"
    try:
        with open(path_to_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"No file with the words found: {path_to_file}")
        return []