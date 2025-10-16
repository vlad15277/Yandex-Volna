import os
from dotenv import load_dotenv

load_dotenv()

# Discord Bot Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
PREFIX = os.getenv('PREFIX', '!')

# Yandex Music Configuration
YANDEX_TOKEN = os.getenv('YANDEX_TOKEN')

# Bot Settings
MAX_QUEUE_SIZE = int(os.getenv('MAX_QUEUE_SIZE', 50))
MAX_SONG_LENGTH = 600  # 10 minutes in seconds

# Error Messages
ERROR_MESSAGES = {
    'no_voice_channel': 'Вы должны быть в голосовом канале!',
    'not_in_voice': 'Бот не подключен к голосовому каналу!',
    'queue_full': f'Очередь переполнена! Максимум {MAX_QUEUE_SIZE} треков.',
    'song_too_long': f'Трек слишком длинный! Максимум {MAX_SONG_LENGTH // 60} минут.',
    'yandex_auth_failed': 'Ошибка авторизации в Яндекс.Музыке!',
    'no_results': 'Трек не найден!',
    'playback_error': 'Ошибка воспроизведения!'
}
