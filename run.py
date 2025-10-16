#!/usr/bin/env python3
"""
Скрипт для запуска Discord бота Яндекс.Музыки
"""

import sys
import os
import logging
from pathlib import Path

# Добавляем текущую директорию в путь Python
sys.path.insert(0, str(Path(__file__).parent))

def check_requirements():
    """Проверка наличия необходимых файлов и переменных окружения"""
    required_files = ['bot.py', 'config.py', 'yandex_client.py', 'music_player.py']
    
    for file in required_files:
        if not os.path.exists(file):
            print(f"Файл {file} не найден!")
            return False
    
    # Проверяем наличие .env файла
    if not os.path.exists('.env'):
        print("Файл .env не найден!")
        print("Создайте файл .env на основе env_example.txt")
        return False
    
    return True

def main():
    """Основная функция запуска"""
    print("Запуск Discord бота Яндекс.Музыки...")
    
    # Проверяем требования
    if not check_requirements():
        print("Не все требования выполнены!")
        sys.exit(1)
    
    try:
        # Импортируем и запускаем бота
        from bot import bot, DISCORD_TOKEN
        
        if not DISCORD_TOKEN:
            print("DISCORD_TOKEN не найден в переменных окружения!")
            print("Убедитесь, что файл .env содержит правильный токен бота.")
            sys.exit(1)
        
        from config import YANDEX_TOKEN
        if not YANDEX_TOKEN:
            print("YANDEX_TOKEN не найден в переменных окружения!")
            print("Убедитесь, что файл .env содержит токен Яндекс.Музыки.")
            print("Инструкции по получению токена в файле YANDEX_TOKEN_GUIDE.md")
            sys.exit(1)
        
        print("Все проверки пройдены!")
        print("Запускаю бота...")
        
        bot.run(DISCORD_TOKEN)
        
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем")
    except Exception as e:
        print(f"Ошибка запуска бота: {e}")
        logging.error(f"Ошибка запуска бота: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
