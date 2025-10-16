import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging
import os
from config import DISCORD_TOKEN, PREFIX, ERROR_MESSAGES, YANDEX_TOKEN
from yandex_client import YandexMusicClient
from music_player import MusicPlayer
from playlist_manager import PlaylistManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class YandexMusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        # Убираем ненужные привилегированные интенты
        intents.guilds = True
        intents.members = False  # Отключаем Server Members Intent
        
        super().__init__(
            command_prefix=PREFIX,
            intents=intents,
            help_command=None,
            heartbeat_timeout=60.0,  # Увеличиваем timeout для стабильности
            max_messages=1000  # Ограничиваем кэш сообщений
        )
        
        # Используем только токен-клиент
        self.yandex_client = YandexMusicClient()
        self.music_player = MusicPlayer(self)
        self.playlist_manager = PlaylistManager(self.yandex_client)
    
    async def on_ready(self):
        """Событие готовности бота"""
        logger.info(f'{self.user} подключился к Discord!')
        logger.info(f'Бот работает на {len(self.guilds)} серверах')
        
        # Аутентификация в Яндекс.Музыке
        if YANDEX_TOKEN:
            if await self.yandex_client.authenticate_with_token(YANDEX_TOKEN):
                logger.info("Успешная авторизация в Яндекс.Музыке")
            else:
                logger.error("Не удалось авторизоваться в Яндекс.Музыке. Проверьте токен!")
        else:
            logger.error("YANDEX_TOKEN не найден в переменных окружения!")
        
        # Устанавливаем статус бота
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name="🎵 Яндекс.Музыку"
        )
        await self.change_presence(activity=activity)
        # Синхронизация slash-команд для автодополнения (глобально и по серверам)
        try:
            # Небольшая задержка для стабильности
            await asyncio.sleep(2)
            global_synced = await self.tree.sync()
            logger.info(f"Синхронизировано глобальных slash-команд: {len(global_synced)}")
            
            # Синхронизация по серверам с задержкой
            for i, guild in enumerate(self.guilds):
                try:
                    await asyncio.sleep(0.5)  # Задержка между синхронизациями
                    guild_synced = await self.tree.sync(guild=guild)
                    logger.info(f"Синхронизировано для сервера {guild.name} ({guild.id}): {len(guild_synced)}")
                except Exception as ge:
                    logger.error(f"Не удалось синхронизировать для сервера {guild.id}: {ge}")
        except Exception as e:
            logger.error(f"Не удалось синхронизировать slash-команды: {e}")
    
    async def on_command_error(self, ctx, error):
        """Обработка ошибок команд"""
        if isinstance(error, commands.CommandNotFound):
            return
        
        logger.error(f"Ошибка команды {ctx.command}: {error}")
        
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Недостаточно аргументов! Используйте: `{ctx.command.usage}`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Неверный аргумент!")
        else:
            await ctx.send("❌ Произошла ошибка при выполнении команды!")

# Создаем экземпляр бота
bot = YandexMusicBot()

@bot.hybrid_command(name='play', aliases=['p'], description='Поиск и воспроизведение трека')
@app_commands.describe(query='Название трека или ссылка Яндекс.Музыки')
async def play_music(ctx, *, query: str = None):
    """Воспроизведение музыки из Яндекс.Музыки"""
    if not query:
        await ctx.send("❌ Укажите название трека! Пример: `!play название песни`")
        return
    
    # Извлекаем ID трека из URL если передан URL
    track_id = None
    if 'music.yandex.ru/track/' in query:
        try:
            track_id = query.split('music.yandex.ru/track/')[1].split('?')[0].split('/')[0]
            logger.info(f"Извлечен ID трека из URL: {track_id}")
        except:
            pass
    
    if track_id:
        # Если это ID трека, воспроизводим напрямую
        await play_track_by_id(ctx, track_id)
        return
    
    if not await bot.music_player.join_voice_channel(ctx):
        return
    
    # Показываем, что бот ищет трек
    search_msg = await ctx.send("🔍 Ищу трек...")
    
    try:
        # Поиск треков
        tracks = await bot.yandex_client.search_tracks(query, limit=5)
        
        if not tracks:
            await search_msg.edit(content=ERROR_MESSAGES['no_results'])
            return
        
        # Выбираем первый найденный трек
        track = tracks[0]
        
        # Получаем URL для воспроизведения
        track_url = await bot.yandex_client.get_track_url(track['id'])
        
        if not track_url:
            await search_msg.edit(content="❌ Не удалось получить ссылку на трек!")
            return
        
        # Добавляем в очередь
        if await bot.music_player.add_to_queue(ctx, track, track_url):
            await search_msg.edit(content=f"✅ Добавлено в очередь: **{track['title']}** - {track['artist']}")
            
            # Если ничего не играет, начинаем воспроизведение
            voice_client = bot.music_player.get_voice_client(ctx.guild.id)
            if not voice_client.is_playing():
                await bot.music_player.play_next(ctx)
    
    except Exception as e:
        logger.error(f"Ошибка в команде play: {e}")
        await search_msg.edit(content="❌ Произошла ошибка при поиске трека!")

async def play_track_by_id(ctx, track_id):
    """Воспроизведение трека по ID"""
    if not await bot.music_player.join_voice_channel(ctx):
        return
    
    search_msg = await ctx.send("🔍 Загружаю трек по ID...")
    
    try:
        # Получаем информацию о треке по ID
        track_info = await bot.yandex_client.get_track_info_by_id(track_id)
        
        if not track_info:
            await search_msg.edit(content="❌ Трек не найден!")
            return
        
        # Получаем URL для воспроизведения
        track_url = await bot.yandex_client.get_track_url(track_id)
        
        if not track_url:
            await search_msg.edit(content="❌ Не удалось получить ссылку на трек!")
            return
        
        # Добавляем в очередь
        if await bot.music_player.add_to_queue(ctx, track_info, track_url):
            await search_msg.edit(content=f"✅ Добавлено в очередь: **{track_info['title']}** - {track_info['artist']}")
            
            # Если ничего не играет, начинаем воспроизведение
            voice_client = bot.music_player.get_voice_client(ctx.guild.id)
            if not voice_client.is_playing():
                await bot.music_player.play_next(ctx)
    
    except Exception as e:
        logger.error(f"Ошибка воспроизведения трека по ID: {e}")
        await search_msg.edit(content="❌ Произошла ошибка при загрузке трека!")

@bot.hybrid_command(name='mywave', aliases=['mw'], description="Воспроизведение 'Моя волна'")
async def my_wave(ctx):
    """Воспроизведение 'Моя волна' из Яндекс.Музыки"""
    if not await bot.music_player.join_voice_channel(ctx):
        return
    
    search_msg = await ctx.send("🌊 Загружаю 'Моя волна'...")
    
    try:
        # Получаем треки из "Моя волна"
        tracks = await bot.yandex_client.get_my_wave_tracks(limit=1)
        
        if not tracks:
            await search_msg.edit(content="❌ Не удалось загрузить 'Моя волна'!")
            return
        
        # Добавляем только 1 трек в очередь
        if tracks:
            track = tracks[0]  # Берем только первый трек
            
            # Проверяем, что у трека есть ID
            if 'id' not in track or not track['id']:
                await search_msg.edit(content="❌ У трека отсутствует ID!")
                return
            
            track_url = await bot.yandex_client.get_track_url(track['id'])
            
            if track_url and await bot.music_player.add_to_queue(ctx, track, track_url):
                # Создаем кнопки управления
                from music_player import MusicControlView
                view = MusicControlView(bot.music_player, ctx.guild.id)
                
                embed = discord.Embed(
                    title="✅ Добавлен трек из 'Моя волна'",
                    description=f"**{track['title']}**\n{track['artist']}",
                    color=0x00ff00
                )
                
                await search_msg.edit(content=None, embed=embed, view=view)
                
                # Включаем режим "Моя волна" для автоматического обновления треков
                bot.music_player.my_wave_mode[ctx.guild.id] = True
                
                # Если ничего не играет, начинаем воспроизведение
                voice_client = bot.music_player.get_voice_client(ctx.guild.id)
                if not voice_client.is_playing():
                    await bot.music_player.play_next(ctx)
            else:
                await search_msg.edit(content="❌ Не удалось добавить трек в очередь!")
        else:
            await search_msg.edit(content="❌ Не удалось получить треки из 'Моя волна'!")
    
    except Exception as e:
        logger.error(f"Ошибка в команде mywave: {e}")
        await search_msg.edit(content="❌ Произошла ошибка при загрузке 'Моя волна'!")

@bot.command(name='mywavetest')
async def my_wave_test_command(ctx):
    """Тестирование получения 'Моя волна'"""
    try:
        await ctx.send("🔍 Тестирую получение 'Моя волна'...")
        
        tracks = await bot.yandex_client.get_my_wave_tracks(limit=5)
        
        if not tracks:
            await ctx.send("❌ Не удалось получить треки из 'Моя волна'")
            return
        
        embed = discord.Embed(
            title="🎵 Моя волна - Тест",
            description=f"Найдено {len(tracks)} треков",
            color=0x00ff00
        )
        
        for i, track in enumerate(tracks[:5], 1):
            embed.add_field(
                name=f"{i}. {track['title']}",
                value=f"👤 {track['artist']}\n⏱️ {track['duration']}с\n🆔 ID: {track['id']}",
                inline=False
            )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Ошибка команды mywavetest: {e}")
        await ctx.send(f"❌ Ошибка тестирования 'Моя волна': {e}")

@bot.command(name='radiodebug')
async def radio_debug_command(ctx):
    """Отладка радиостанций"""
    try:
        await ctx.send("🔍 Отладка радиостанций...")
        
        # Получаем радиостанции (синхронный вызов)
        stations = bot.yandex_client.client.rotor_stations_dashboard()
        
        if not stations or not hasattr(stations, 'stations'):
            await ctx.send("❌ Не удалось получить радиостанции")
            return
        
        embed = discord.Embed(
            title="📻 Радиостанции",
            description=f"Найдено {len(stations.stations)} станций",
            color=0x00ff00
        )
        
        for i, station in enumerate(stations.stations[:10], 1):
            if hasattr(station, 'station') and station.station:
                station_info = station.station
                station_name = getattr(station_info, 'name', 'Неизвестно')
                station_id = getattr(station_info, 'id', 'N/A')
                
                embed.add_field(
                    name=f"{i}. {station_name}",
                    value=f"🆔 ID: {station_id}",
                    inline=False
                )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Ошибка команды radiodebug: {e}")
        await ctx.send(f"❌ Ошибка отладки радиостанций: {e}")

@bot.command(name='radiotest')
async def radio_test_command(ctx, station_id=None):
    """Тестирование конкретной радиостанции"""
    if not station_id:
        await ctx.send("❌ Укажите ID радиостанции! Пример: `!radiotest user:onyourwave`")
        return
    
    try:
        await ctx.send(f"🔍 Тестирую радиостанцию {station_id}...")
        
        # Получаем треки с радиостанции (синхронный вызов)
        station_tracks = bot.yandex_client.client.rotor_station_tracks(station_id)
        
        if not station_tracks or not hasattr(station_tracks, 'sequence'):
            await ctx.send("❌ Не удалось получить треки с радиостанции")
            return
        
        tracks = []
        for track_short in station_tracks.sequence[:5]:
            if hasattr(track_short, 'track') and track_short.track:
                track = track_short.track
                track_info = {
                    'id': track.id,
                    'title': track.title,
                    'artist': ', '.join([artist.name for artist in track.artists]) if track.artists else 'Неизвестный исполнитель',
                    'duration': track.duration_ms // 1000 if track.duration_ms else 0
                }
                tracks.append(track_info)
        
        if tracks:
            embed = discord.Embed(
                title=f"📻 Радиостанция {station_id}",
                description=f"Найдено {len(tracks)} треков",
                color=0x00ff00
            )
            
            for i, track in enumerate(tracks, 1):
                embed.add_field(
                    name=f"{i}. {track['title']}",
                    value=f"👤 {track['artist']}\n⏱️ {track['duration']}с\n🆔 ID: {track['id']}",
                    inline=False
                )
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Не найдено треков на радиостанции")
        
    except Exception as e:
        logger.error(f"Ошибка команды radiotest: {e}")
        await ctx.send(f"❌ Ошибка тестирования радиостанции: {e}")

@bot.command(name='mywavedirect')
async def my_wave_direct_command(ctx):
    """Прямое тестирование user:onyourwave"""
    try:
        await ctx.send("🔍 Прямое тестирование user:onyourwave...")
        
        tracks = await bot.yandex_client._get_direct_my_wave_tracks(limit=5)
        
        if not tracks:
            await ctx.send("❌ Не удалось получить треки с user:onyourwave")
            return
        
        embed = discord.Embed(
            title="🎵 user:onyourwave - Прямое тестирование",
            description=f"Найдено {len(tracks)} треков",
            color=0x00ff00
        )
        
        for i, track in enumerate(tracks, 1):
            embed.add_field(
                name=f"{i}. {track['title']}",
                value=f"👤 {track['artist']}\n⏱️ {track['duration']}с\n🆔 ID: {track['id']}",
                inline=False
            )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Ошибка команды mywavedirect: {e}")
        await ctx.send(f"❌ Ошибка прямого тестирования user:onyourwave: {e}")

@bot.hybrid_command(name='mywaveoff', description="Отключение режима 'Моя волна'")
async def my_wave_off_command(ctx):
    """Отключение режима 'Моя волна'"""
    try:
        bot.music_player.my_wave_mode[ctx.guild.id] = False
        # Сбрасываем batch_id и список проигранных треков при отключении режима
        if ctx.guild.id in bot.music_player.my_wave_batch_id:
            del bot.music_player.my_wave_batch_id[ctx.guild.id]
        if ctx.guild.id in bot.music_player.played_tracks:
            del bot.music_player.played_tracks[ctx.guild.id]
        await ctx.send("🔴 Режим 'Моя волна' отключен. Треки больше не будут автоматически обновляться.")
    except Exception as e:
        logger.error(f"Ошибка команды mywaveoff: {e}")
        await ctx.send(f"❌ Ошибка отключения режима 'Моя волна': {e}")

@bot.hybrid_command(name='played', description='Показ статистики проигранных треков')
async def played_tracks_command(ctx):
    """Показ статистики проигранных треков"""
    try:
        played_tracks = bot.music_player.get_played_tracks(ctx.guild.id)
        count = len(played_tracks)
        
        if count == 0:
            await ctx.send("📊 Пока не было проиграно ни одного трека")
        else:
            await ctx.send(f"📊 Проиграно треков: **{count}**")
            
    except Exception as e:
        logger.error(f"Ошибка команды played: {e}")
        await ctx.send(f"❌ Ошибка получения статистики: {e}")

@bot.hybrid_command(name='skip', aliases=['s'], description='Пропуск текущего трека')
async def skip_song(ctx):
    """Пропуск текущего трека"""
    await bot.music_player.skip_song(ctx)

@bot.hybrid_command(name='pause', description='Пауза воспроизведения')
async def pause_song(ctx):
    """Пауза воспроизведения"""
    await bot.music_player.pause_song(ctx)

@bot.hybrid_command(name='resume', aliases=['r'], description='Возобновление воспроизведения')
async def resume_song(ctx):
    """Возобновление воспроизведения"""
    await bot.music_player.resume_song(ctx)

@bot.hybrid_command(name='stop', description='Остановка и очистка очереди')
async def stop_playback(ctx):
    """Остановка воспроизведения"""
    await bot.music_player.stop_playback(ctx)

@bot.hybrid_command(name='queue', aliases=['q'], description='Показ текущей очереди')
async def show_queue(ctx):
    """Показ текущей очереди"""
    await bot.music_player.show_queue(ctx)

@bot.hybrid_command(name='disconnect', aliases=['dc'], description='Отключение от голосового канала')
async def disconnect_bot(ctx):
    """Отключение бота от голосового канала"""
    await bot.music_player.disconnect(ctx)

@bot.hybrid_command(name='playlist', aliases=['pl'], description='Поиск и воспроизведение плейлиста')
@app_commands.describe(query='Название плейлиста')
async def play_playlist(ctx, *, query: str = None):
    """Воспроизведение плейлиста"""
    if not query:
        await ctx.send("❌ Укажите название плейлиста! Пример: `!playlist название плейлиста`")
        return
    
    if not await bot.music_player.join_voice_channel(ctx):
        return
    
    search_msg = await ctx.send("🔍 Ищу плейлист...")
    
    try:
        import random
        # 1) Если пришла ссылка на альбом — воспроизводим альбом
        if isinstance(query, str) and "music.yandex.ru/album/" in query:
            try:
                album_id = query.split("music.yandex.ru/album/")[-1].split('?')[0].split('/')[0]
                album_tracks = await bot.playlist_manager.get_album_tracks(album_id, limit=50)
                if not album_tracks:
                    await search_msg.edit(content="❌ Не удалось получить треки альбома!")
                    return
                tracks = random.sample(album_tracks, min(10, len(album_tracks)))
            except Exception as album_err:
                logger.error(f"Ошибка парсинга/загрузки альбома: {album_err}")
                await search_msg.edit(content="❌ Ошибка обработки ссылки альбома!")
                return
        else:
            # 2) Иначе ищем пользовательский плейлист (или URL плейлиста)
            playlists = await bot.playlist_manager.search_playlists(query, limit=5)
            if not playlists:
                await search_msg.edit(content="❌ Плейлист не найден!")
                return
            playlist = playlists[0]
            tracks_list = await bot.playlist_manager.get_playlist_tracks(playlist['id'], limit=50)
            if not tracks_list:
                await search_msg.edit(content="❌ Плейлист пуст!")
                return
            tracks = random.sample(tracks_list, min(10, len(tracks_list)))
        
        if not tracks:
            await search_msg.edit(content="❌ Плейлист пуст!")
            return
        
        # Добавляем треки в очередь
        added_count = 0
        for track in tracks:
            track_url = await bot.yandex_client.get_track_url(track['id'])
            if track_url and await bot.music_player.add_to_queue(ctx, track, track_url):
                added_count += 1
        
        if added_count > 0:
            await search_msg.edit(content=f"✅ Добавлено {added_count} треков в очередь!")
            
            # Если ничего не играет, начинаем воспроизведение
            voice_client = bot.music_player.get_voice_client(ctx.guild.id)
            if not voice_client.is_playing():
                await bot.music_player.play_next(ctx)
        else:
            await search_msg.edit(content="❌ Не удалось добавить треки в очередь!")
    
    except Exception as e:
        logger.error(f"Ошибка в команде playlist: {e}")
        await search_msg.edit(content="❌ Произошла ошибка при загрузке плейлиста!")

@bot.hybrid_command(name='liked', aliases=['l'], description='Воспроизведение лайкнутых треков')
async def play_liked_tracks(ctx):
    """Воспроизведение лайкнутых треков"""
    if not await bot.music_player.join_voice_channel(ctx):
        return
    
    search_msg = await ctx.send("❤️ Загружаю лайкнутые треки...")
    
    try:
        # Получаем лайкнутые треки
        tracks = await bot.playlist_manager.get_liked_tracks(limit=10)
        
        if not tracks:
            await search_msg.edit(content="❌ У вас нет лайкнутых треков!")
            return
        
        # Добавляем треки в очередь
        added_count = 0
        for track in tracks:
            track_url = await bot.yandex_client.get_track_url(track['id'])
            if track_url and await bot.music_player.add_to_queue(ctx, track, track_url):
                added_count += 1
        
        if added_count > 0:
            await search_msg.edit(content=f"✅ Добавлено {added_count} лайкнутых треков в очередь!")
            
            # Если ничего не играет, начинаем воспроизведение
            voice_client = bot.music_player.get_voice_client(ctx.guild.id)
            if not voice_client.is_playing():
                await bot.music_player.play_next(ctx)
        else:
            await search_msg.edit(content="❌ Не удалось добавить треки в очередь!")
    
    except Exception as e:
        logger.error(f"Ошибка в команде liked: {e}")
        await search_msg.edit(content="❌ Произошла ошибка при загрузке лайкнутых треков!")

@bot.command(name='testliked')
async def test_liked_command(ctx):
    """Тестирование получения лайкнутых треков напрямую"""
    try:
        await ctx.send("🔍 Тестирую получение лайкнутых треков...")
        
        # Получаем лайкнутые треки напрямую
        liked_tracks = await asyncio.get_event_loop().run_in_executor(
            None,
            bot.yandex_client.client.users_likes_tracks
        )
        
        logger.info("Получены лайкнутые треки (объект получен)")
        if hasattr(liked_tracks, 'tracks'):
            logger.info(f"Количество треков: {len(liked_tracks.tracks) if liked_tracks.tracks else 0}")
        
        if liked_tracks and hasattr(liked_tracks, 'tracks') and liked_tracks.tracks:
            # Получаем ID треков
            track_ids = []
            for i, track_short in enumerate(liked_tracks.tracks[:5]):
                try:
                    # Пробуем разные способы получения ID
                    if hasattr(track_short, 'id'):
                        track_ids.append(track_short.id)
                    elif isinstance(track_short, dict) and 'id' in track_short:
                        track_ids.append(track_short['id'])
                    else:
                        logger.warning(f"Не удалось получить ID для трека {i}: {track_short}")
                except Exception as e:
                    logger.warning(f"Ошибка получения ID трека {i}: {e}")
            
            logger.info(f"Загружаю {len(track_ids)} трек(а/ов)")
            
            if track_ids:
                # Загружаем полную информацию о треках
                try:
                    # Используем tracks API напрямую
                    full_tracks = await asyncio.get_event_loop().run_in_executor(
                        None,
                        bot.yandex_client.client.tracks,
                        track_ids
                    )
                    
                    logger.info(f"Загружено {len(full_tracks) if full_tracks else 0} треков")
                    
                    tracks = []
                    if full_tracks:
                        for i, track in enumerate(full_tracks[:5]):  # Показываем первые 5
                            if track:
                                track_info = {
                                    'id': track.id,
                                    'title': track.title,
                                    'artist': ', '.join([artist.name for artist in track.artists]),
                                    'duration': track.duration_ms // 1000
                                }
                                tracks.append(track_info)
                except Exception as fetch_error:
                    logger.error(f"Ошибка загрузки треков: {fetch_error}")
                    tracks = []
            else:
                tracks = []
            
            if tracks:
                embed = discord.Embed(
                    title="❤️ Лайкнутые треки (тест)",
                    description=f"Найдено {len(tracks)} треков",
                    color=0x00ff00
                )
                
                for i, track in enumerate(tracks, 1):
                    embed.add_field(
                        name=f"{i}. {track['title']}",
                        value=f"👤 {track['artist']}\n⏱️ {track['duration']}с\n🆔 ID: {track['id']}",
                        inline=False
                    )
                
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Не удалось получить треки из liked_tracks")
        else:
            await ctx.send("❌ liked_tracks пуст или не содержит tracks")
        
    except Exception as e:
        logger.error(f"Ошибка команды testliked: {e}")
        await ctx.send(f"❌ Ошибка тестирования лайкнутых треков: {e}")

@bot.command(name='myplaylists')
async def my_playlists_command(ctx):
    """Показ всех плейлистов пользователя"""
    try:
        await ctx.send("🔍 Загружаю ваши плейлисты...")
        
        # Получаем плейлисты пользователя
        playlists = await bot.yandex_client.get_user_playlists()
        
        if not playlists:
            await ctx.send("❌ У вас нет плейлистов или не удалось их загрузить!")
            return
        
        embed = discord.Embed(
            title="📋 Ваши плейлисты",
            description=f"Найдено {len(playlists)} плейлистов",
            color=0x00ff00
        )
        
        for i, playlist in enumerate(playlists[:10], 1):  # Показываем первые 10
            embed.add_field(
                name=f"{i}. {playlist['title']}",
                value=f"🎵 {playlist['track_count']} треков\n🆔 ID: {playlist['id']}",
                inline=False
            )
        
        if len(playlists) > 10:
            embed.add_field(
                name="...",
                value=f"И еще {len(playlists) - 10} плейлистов",
                inline=False
            )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Ошибка команды myplaylists: {e}")
        await ctx.send(f"❌ Ошибка загрузки плейлистов: {e}")

@bot.command(name='test')
async def test_search(ctx, *, query=None):
    """Тестовая команда для проверки поиска"""
    if not query:
        await ctx.send("❌ Укажите запрос для тестирования! Пример: `!test песня`")
        return
    
    try:
        tracks = await bot.yandex_client.search_tracks(query, limit=3)
        if tracks:
            embed = discord.Embed(title="🔍 Результаты поиска", color=0x00ff00)
            for i, track in enumerate(tracks, 1):
                embed.add_field(
                    name=f"{i}. {track['title']}",
                    value=f"Исполнитель: {track['artist']}\nДлительность: {track['duration']}с",
                    inline=False
                )
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Треки не найдены!")
    except Exception as e:
        logger.error(f"Ошибка тестового поиска: {e}")
        await ctx.send(f"❌ Ошибка поиска: {e}")

@bot.command(name='debug')
async def debug_api(ctx, *, query="тест"):
    """Отладочная команда для проверки API"""
    try:
        # Тест поиска
        tracks = await bot.yandex_client.search_tracks(query, limit=3)
        
        embed = discord.Embed(title="🔧 Отладка API", color=0xff9900)
        embed.add_field(name="Запрос", value=query, inline=False)
        embed.add_field(name="Найдено треков", value=len(tracks), inline=True)
        embed.add_field(name="Авторизован", value="✅" if bot.yandex_client.is_authenticated else "❌", inline=True)
        
        if tracks:
            for i, track in enumerate(tracks, 1):
                embed.add_field(
                    name=f"Трек {i}",
                    value=f"**{track['title']}**\nИсполнитель: {track['artist']}\nID: {track['id']}",
                    inline=False
                )
        else:
            embed.add_field(name="Результат", value="❌ Треки не найдены", inline=False)
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Ошибка отладки: {e}")
        await ctx.send(f"❌ Ошибка отладки: {e}")

@bot.command(name='url')
async def test_track_url(ctx, *, track_id):
    """Тестирование получения URL трека по ID"""
    try:
        # Получаем информацию о треке
        track_info = await bot.yandex_client.get_track_info_by_id(track_id)
        
        if not track_info:
            await ctx.send("❌ Трек не найден!")
            return
        
        # Получаем URL
        track_url = await bot.yandex_client.get_track_url(track_id)
        
        embed = discord.Embed(title="🔗 Тест URL трека", color=0x0099ff)
        embed.add_field(name="ID трека", value=track_id, inline=False)
        embed.add_field(name="Название", value=track_info['title'], inline=False)
        embed.add_field(name="Исполнитель", value=track_info['artist'], inline=False)
        
        if track_url:
            embed.add_field(name="URL", value=f"✅ Получен (длина: {len(track_url)} символов)", inline=False)
            # Показываем только первые 100 символов URL для безопасности
            embed.add_field(name="URL (первые 100 символов)", value=track_url[:100] + "...", inline=False)
        else:
            embed.add_field(name="URL", value="❌ Не удалось получить", inline=False)
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Ошибка тестирования URL: {e}")
        await ctx.send(f"❌ Ошибка тестирования URL: {e}")

@bot.command(name='urltest')
async def detailed_url_test(ctx, *, track_id):
    """Детальное тестирование всех методов получения URL"""
    try:
        embed = discord.Embed(title="🔧 Детальный тест URL", color=0xff6600)
        embed.add_field(name="ID трека", value=track_id, inline=False)
        
        # Тест 1: Получение информации о треке
        track_info = await bot.yandex_client.get_track_info_by_id(track_id)
        if track_info:
            embed.add_field(name="Информация о треке", value=f"✅ {track_info['title']} - {track_info['artist']}", inline=False)
        else:
            embed.add_field(name="Информация о треке", value="❌ Не получена", inline=False)
            await ctx.send(embed=embed)
            return
        
        # Тест 2: Основной метод получения URL
        track_url = await bot.yandex_client.get_track_url(track_id)
        if track_url:
            embed.add_field(name="URL (основной метод)", value=f"✅ Получен", inline=True)
            embed.add_field(name="Длина URL", value=f"{len(track_url)} символов", inline=True)
        else:
            embed.add_field(name="URL (основной метод)", value="❌ Не получен", inline=True)
        
        # Тест 3: Альтернативный метод
        alt_url = await bot.yandex_client._get_track_url_alternative(track_id)
        if alt_url:
            embed.add_field(name="URL (альтернативный)", value=f"✅ Получен", inline=True)
        else:
            embed.add_field(name="URL (альтернативный)", value="❌ Не получен", inline=True)
        
        # Тест 4: yt-dlp метод
        ytdlp_url = await bot.yandex_client.get_track_url_ytdlp(track_id)
        if ytdlp_url:
            embed.add_field(name="URL (yt-dlp)", value=f"✅ Получен", inline=True)
        else:
            embed.add_field(name="URL (yt-dlp)", value="❌ Не получен", inline=True)
        
        # Показываем первые 200 символов URL для диагностики
        if track_url:
            embed.add_field(name="URL (первые 200 символов)", value=track_url[:200] + "..." if len(track_url) > 200 else track_url, inline=False)
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Ошибка детального тестирования URL: {e}")
        await ctx.send(f"❌ Ошибка детального тестирования: {e}")

@bot.hybrid_command(name='status', description='Проверка статуса бота')
async def bot_status(ctx):
    """Проверка статуса бота и авторизации"""
    embed = discord.Embed(title="🤖 Статус бота", color=0x00ff00)
    
    # Статус Discord
    embed.add_field(name="Discord", value="✅ Подключен", inline=True)
    
    # Статус Яндекс.Музыки
    if bot.yandex_client.is_authenticated:
        embed.add_field(name="Яндекс.Музыка", value="✅ Авторизован", inline=True)
    else:
        embed.add_field(name="Яндекс.Музыка", value="❌ Не авторизован", inline=True)
    
    # Статус голосового канала
    voice_client = bot.music_player.get_voice_client(ctx.guild.id)
    if voice_client and voice_client.is_connected():
        embed.add_field(name="Голосовой канал", value=f"✅ Подключен к {voice_client.channel.name}", inline=True)
    else:
        embed.add_field(name="Голосовой канал", value="❌ Не подключен", inline=True)
    
    # Размер очереди
    queue = bot.music_player.get_queue(ctx.guild.id)
    embed.add_field(name="Очередь", value=f"📋 {len(queue)} треков", inline=True)
    
    # Текущий трек
    current = bot.music_player.current_song.get(ctx.guild.id)
    if current:
        embed.add_field(name="Сейчас играет", value=f"🎵 {current['title']} - {current['artist']}", inline=False)
    else:
        embed.add_field(name="Сейчас играет", value="🔇 Ничего", inline=False)
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name='help', description='Показ справки по командам')
async def help_command(ctx):
    """Показ справки по командам"""
    embed = discord.Embed(
        title="🎵 Команды Яндекс.Музыка Бота",
        description="Список доступных команд:",
        color=0x00ff00
    )
    
    commands_list = [
        ("`!play <запрос>` / `/play`", "Поиск и воспроизведение трека"),
        ("`!mywave` / `/mywave`", "Воспроизведение 'Моя волна'"),
        ("`!mywavetest`", "Тестирование 'Моя волна'"),
        ("`!radiodebug`", "Отладка радиостанций"),
        ("`!radiotest <ID>`", "Тестирование конкретной радиостанции"),
        ("`!mywavedirect`", "Прямое тестирование user:onyourwave"),
        ("`!mywaveoff` / `/mywaveoff`", "Отключение режима 'Моя волна'"),
        ("`!played` / `/played`", "Статистика проигранных треков"),
        ("`!playlist <запрос>` / `/playlist`", "Поиск и воспроизведение плейлиста"),
        ("`!liked` / `/liked`", "Воспроизведение лайкнутых треков"),
        ("`!myplaylists`", "Показ всех ваших плейлистов"),
        ("`!test <запрос>`", "Тестирование поиска треков"),
        ("`!debug <запрос>`", "Отладка API Яндекс.Музыки"),
        ("`!url <ID_трека>`", "Тестирование получения URL трека"),
        ("`!urltest <ID_трека>`", "Детальное тестирование URL"),
        ("`!status` / `/status`", "Проверка статуса бота"),
        ("`!skip` / `/skip`", "Пропуск текущего трека"),
        ("`!pause` / `/pause`", "Пауза воспроизведения"),
        ("`!resume` / `/resume`", "Возобновление воспроизведения"),
        ("`!stop` / `/stop`", "Остановка и очистка очереди"),
        ("`!queue` / `/queue`", "Показ текущей очереди"),
        ("`!disconnect` / `/disconnect`", "Отключение от голосового канала"),
        ("`!help` / `/help`", "Показ этой справки")
    ]
    
    for command, description in commands_list:
        embed.add_field(name=command, value=description, inline=False)
    
    embed.set_footer(text="Бот для воспроизведения музыки через Яндекс.Музыку • Версия 1.0")
    
    await ctx.send(embed=embed)

# Команда release удалена по пожеланию пользователя

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN не найден в переменных окружения!")
        exit(1)
    
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")

