import asyncio
import discord
from discord.ext import commands
from discord.ui import View, Button
import yt_dlp
import logging
from collections import deque
from config import MAX_QUEUE_SIZE, MAX_SONG_LENGTH, ERROR_MESSAGES
import os

# Добавляем путь к FFmpeg в PATH
ffmpeg_path = r"D:\PROJECT\VSC\YANDEX.MUSIC\ffmpeg\bin"
if ffmpeg_path not in os.environ.get("PATH", ""):
    os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ.get("PATH", "")

logger = logging.getLogger(__name__)

class MusicControlView(View):
    """Класс для кнопок управления музыкой"""
    
    def __init__(self, music_player, guild_id):
        super().__init__(timeout=300)  # 5 минут timeout
        self.music_player = music_player
        self.guild_id = guild_id
        
        # Кнопка паузы/возобновления
        self.pause_button = Button(
            style=discord.ButtonStyle.secondary,  # Желтый цвет
            emoji="⏸️",
            label="Пауза",
            custom_id="pause"
        )
        self.pause_button.callback = self.pause_callback
        self.add_item(self.pause_button)
        
        # Кнопка остановки
        self.stop_button = Button(
            style=discord.ButtonStyle.danger,  # Красный цвет
            emoji="⏹️",
            label="Стоп",
            custom_id="stop"
        )
        self.stop_button.callback = self.stop_callback
        self.add_item(self.stop_button)
        
        # Кнопка пропуска
        self.skip_button = Button(
            style=discord.ButtonStyle.primary,  # Синий цвет
            emoji="⏭️",
            label="Пропустить",
            custom_id="skip"
        )
        self.skip_button.callback = self.skip_callback
        self.add_item(self.skip_button)
        
        # Кнопка очереди
        self.queue_button = Button(
            style=discord.ButtonStyle.secondary,
            emoji="📋",
            label="Очередь",
            custom_id="queue"
        )
        self.queue_button.callback = self.queue_callback
        self.add_item(self.queue_button)

        # Кнопка помощи
        self.help_button = Button(
            style=discord.ButtonStyle.secondary,
            emoji="❓",
            label="Help",
            custom_id="help"
        )
        self.help_button.callback = self.help_callback
        self.add_item(self.help_button)
    
    async def pause_callback(self, interaction):
        """Обработка кнопки паузы/возобновления"""
        try:
            voice_client = self.music_player.get_voice_client(self.guild_id)
            
            if not voice_client or not voice_client.is_connected():
                await interaction.response.send_message("❌ Бот не подключен к голосовому каналу!", ephemeral=True)
                return
            
            if voice_client.is_paused():
                voice_client.resume()
                self.pause_button.emoji = "⏸️"
                self.pause_button.label = "Пауза"
                self.pause_button.style = discord.ButtonStyle.secondary  # Желтый цвет для паузы
                await interaction.response.edit_message(content="▶️ Воспроизведение возобновлено!", view=self)
            elif voice_client.is_playing():
                voice_client.pause()
                self.pause_button.emoji = "▶️"
                self.pause_button.label = "Продолжить"
                self.pause_button.style = discord.ButtonStyle.success  # Зеленый цвет для продолжения
                await interaction.response.edit_message(content="⏸️ Воспроизведение приостановлено!", view=self)
            else:
                await interaction.response.send_message("❌ Сейчас ничего не играет!", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Ошибка в pause_callback: {e}")
            await interaction.response.send_message("❌ Произошла ошибка!", ephemeral=True)
    
    async def stop_callback(self, interaction):
        """Обработка кнопки остановки"""
        try:
            voice_client = self.music_player.get_voice_client(self.guild_id)
            
            if not voice_client or not voice_client.is_connected():
                await interaction.response.send_message("❌ Бот не подключен к голосовому каналу!", ephemeral=True)
                return
            
            # Останавливаем, чистим очередь и отключаемся от голосового канала
            voice_client.stop()
            queue = self.music_player.get_queue(self.guild_id)
            queue.clear()
            self.music_player.current_song[self.guild_id] = None
            # Сбрасываем режим "Моя волна" и связанные данные
            self.music_player.my_wave_mode[self.guild_id] = False
            if self.guild_id in self.music_player.my_wave_batch_id:
                del self.music_player.my_wave_batch_id[self.guild_id]
            if self.guild_id in self.music_player.played_tracks:
                del self.music_player.played_tracks[self.guild_id]
            
            await voice_client.disconnect()
            if self.guild_id in self.music_player.voice_clients:
                del self.music_player.voice_clients[self.guild_id]
            
            await interaction.response.edit_message(content="⏹️ Остановлено и отключился от голосового канала!", view=None)
            
        except Exception as e:
            logger.error(f"Ошибка в stop_callback: {e}")
            await interaction.response.send_message("❌ Произошла ошибка!", ephemeral=True)
    
    async def skip_callback(self, interaction):
        """Обработка кнопки пропуска"""
        try:
            voice_client = self.music_player.get_voice_client(self.guild_id)
            
            if not voice_client or not voice_client.is_connected():
                await interaction.response.send_message("❌ Бот не подключен к голосовому каналу!", ephemeral=True)
                return
            
            if not voice_client.is_playing():
                await interaction.response.send_message("❌ Сейчас ничего не играет!", ephemeral=True)
                return
            
            # Если включен режим "Моя волна", добавляем новый трек
            if self.music_player.my_wave_mode.get(self.guild_id, False):
                logger.info("Режим 'Моя волна' активен, добавляем новый трек...")
                # Создаем фиктивный контекст для добавления трека
                class FakeContext:
                    def __init__(self, guild_id):
                        self.guild = type('Guild', (), {'id': guild_id})()
                
                fake_ctx = FakeContext(self.guild_id)
                await self.music_player._add_next_my_wave_track(fake_ctx)
            
            voice_client.stop()
            await interaction.response.edit_message(content="⏭️ Трек пропущен!", view=self)
            
        except Exception as e:
            logger.error(f"Ошибка в skip_callback: {e}")
            await interaction.response.send_message("❌ Произошла ошибка!", ephemeral=True)
    
    async def queue_callback(self, interaction):
        """Обработка кнопки очереди"""
        try:
            queue = self.music_player.get_queue(self.guild_id)
            current_song = self.music_player.current_song.get(self.guild_id)
            
            if not queue and not current_song:
                await interaction.response.send_message("📋 Очередь пуста!", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="📋 Очередь воспроизведения",
                color=0x00ff00
            )
            
            if current_song:
                embed.add_field(
                    name="🎵 Сейчас играет",
                    value=f"**{current_song['title']}**\n{current_song['artist']}",
                    inline=False
                )
            
            if queue:
                queue_text = ""
                for i, song in enumerate(list(queue)[:10], 1):  # Показываем только первые 10
                    queue_text += f"{i}. **{song['title']}** - {song['artist']}\n"
                
                if len(queue) > 10:
                    queue_text += f"... и еще {len(queue) - 10} треков"
                
                embed.add_field(
                    name=f"📋 В очереди ({len(queue)} треков)",
                    value=queue_text,
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Ошибка в queue_callback: {e}")
            await interaction.response.send_message("❌ Произошла ошибка!", ephemeral=True)

    async def help_callback(self, interaction):
        """Обработка кнопки помощи"""
        try:
            embed = discord.Embed(
                title="🎵 Команды бота",
                description="Доступны prefix `!` и slash `/` команды",
                color=0x00ff00
            )
            embed.add_field(name="Воспроизведение", value="`!play`, `/play`, `!playlist`, `/playlist`, `!liked`, `/liked`", inline=False)
            embed.add_field(name="Моя волна", value="`!mywave`, `/mywave`, `!mywaveoff`, `/mywaveoff`", inline=False)
            embed.add_field(name="Управление", value="`!skip`, `!pause`, `!resume`, `!stop`, `!queue`, `!disconnect` (есть и slash)", inline=False)
            embed.set_footer(text="Для списка всех команд используйте `!help` или `/help`")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Ошибка в help_callback: {e}")
            await interaction.response.send_message("❌ Произошла ошибка!", ephemeral=True)

class MusicPlayer:
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}  # Словарь очередей для каждого сервера
        self.current_song = {}  # Текущий трек для каждого сервера
        self.voice_clients = {}  # Голосовые соединения
        self.my_wave_mode = {}  # Флаг режима "Моя волна" для каждого сервера
        self.my_wave_batch_id = {}  # Batch ID для "Моя волна" для каждого сервера
        self.played_tracks = {}  # Список уже проигранных треков для каждого сервера
        
    def get_queue(self, guild_id):
        """Получение очереди для сервера"""
        if guild_id not in self.queues:
            self.queues[guild_id] = deque()
        return self.queues[guild_id]
    
    def get_voice_client(self, guild_id):
        """Получение голосового клиента для сервера"""
        return self.voice_clients.get(guild_id)
    
    def get_played_tracks(self, guild_id):
        """Получение списка проигранных треков для сервера"""
        if guild_id not in self.played_tracks:
            self.played_tracks[guild_id] = set()
        return self.played_tracks[guild_id]
    
    async def join_voice_channel(self, ctx):
        """Подключение к голосовому каналу"""
        if not ctx.author.voice:
            await ctx.send(ERROR_MESSAGES['no_voice_channel'])
            return False
        
        voice_channel = ctx.author.voice.channel
        # Пытаемся взять уже существующий клиент и синхронизировать кэш
        voice_client = self.get_voice_client(ctx.guild.id)
        if not voice_client:
            existing_vc = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
            if existing_vc:
                self.voice_clients[ctx.guild.id] = existing_vc
                voice_client = existing_vc
        
        # Если уже подключены
        if voice_client and voice_client.is_connected():
            if voice_client.channel != voice_channel:
                try:
                    await voice_client.move_to(voice_channel)
                except Exception as e:
                    logger.error(f"Ошибка перемещения в голосовой канал: {e}")
                    await ctx.send("Ошибка перемещения в голосовой канал!")
                    return False
            return True
        
        # Иначе пробуем подключиться
        try:
            voice_client = await voice_channel.connect(timeout=10.0, reconnect=True)
            self.voice_clients[ctx.guild.id] = voice_client
            return True
        except discord.ClientException as e:
            # Частый кейс: Already connected — пробуем взять существующий клиент
            logger.warning(f"Исключение при подключении (вероятно, уже подключен): {e}")
            existing_vc = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
            if existing_vc:
                self.voice_clients[ctx.guild.id] = existing_vc
                if existing_vc.channel != voice_channel:
                    try:
                        await existing_vc.move_to(voice_channel)
                    except Exception as move_err:
                        logger.error(f"Ошибка перемещения после Already connected: {move_err}")
                        await ctx.send("Ошибка перемещения в голосовой канал!")
                        return False
                return True
            await ctx.send("Ошибка подключения к голосовому каналу!")
            return False
        except Exception as e:
            logger.error(f"Ошибка подключения к голосовому каналу: {e}")
            # Повторная попытка один раз (в т.ч. для 'list index out of range')
            try:
                await asyncio.sleep(0.5)
                existing_vc = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
                if existing_vc:
                    self.voice_clients[ctx.guild.id] = existing_vc
                    if existing_vc.channel != voice_channel:
                        await existing_vc.move_to(voice_channel)
                    return True
                voice_client = await voice_channel.connect(timeout=10.0, reconnect=True)
                self.voice_clients[ctx.guild.id] = voice_client
                return True
            except Exception as e2:
                logger.error(f"Повторная ошибка подключения к голосовому каналу: {e2}")
                await ctx.send("Ошибка подключения к голосовому каналу!")
                return False
    
    async def play_next(self, ctx):
        """Воспроизведение следующего трека в очереди"""
        queue = self.get_queue(ctx.guild.id)
        voice_client = self.get_voice_client(ctx.guild.id)
        
        if not voice_client or not voice_client.is_connected():
            return
        
        if not queue:
            # Если очередь пуста и включен режим "Моя волна", добавляем новый трек
            if self.my_wave_mode.get(ctx.guild.id, False):
                logger.info("Очередь пуста, но режим 'Моя волна' активен, добавляем новый трек...")
                if await self._add_next_my_wave_track(ctx):
                    # Рекурсивно вызываем play_next для воспроизведения добавленного трека
                    await self.play_next(ctx)
                    return
                else:
                    logger.warning("Не удалось добавить трек из 'Моя волна'")
            
            # Если очередь пуста, останавливаем воспроизведение
            self.current_song[ctx.guild.id] = None
            return
        
        # Получаем следующий трек из очереди
        song = queue.popleft()
        self.current_song[ctx.guild.id] = song
        
        # Добавляем трек в список проигранных (если есть ID)
        if 'id' in song and song['id']:
            played_tracks = self.get_played_tracks(ctx.guild.id)
            played_tracks.add(song['id'])
        
        try:
            # Проверяем доступность FFmpeg
            import shutil
            if not shutil.which('ffmpeg'):
                logger.error("FFmpeg не найден в PATH!")
                await ctx.send("❌ FFmpeg не найден! Проверьте установку.")
                return
            
            # Создаем FFmpeg источник для воспроизведения
            source = discord.FFmpegPCMAudio(
                song['url'],
                before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
            )
            
            # Воспроизводим трек
            voice_client.play(
                source,
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self.play_next(ctx), 
                    self.bot.loop
                ) if e is None else logger.error(f"Ошибка воспроизведения: {e}")
            )
            
            # Отправляем информацию о текущем треке
            embed = discord.Embed(
                title="🎵 Сейчас играет",
                description=f"**{song['title']}**\n"
                           f"Исполнитель: {song['artist']}\n"
                           f"Длительность: {self.format_duration(song['duration'])}",
                color=0x00ff00
            )
            
            if song.get('cover_url'):
                embed.set_thumbnail(url=song['cover_url'])
            
            # Создаем кнопки управления
            view = MusicControlView(self, ctx.guild.id)
            
            await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"Ошибка воспроизведения трека: {e}")
            await ctx.send(ERROR_MESSAGES['playback_error'])
            # Пытаемся воспроизвести следующий трек
            await self.play_next(ctx)
    
    def format_duration(self, seconds):
        """Форматирование длительности трека"""
        minutes, seconds = divmod(seconds, 60)
        return f"{minutes}:{seconds:02d}"
    
    async def _add_next_my_wave_track(self, ctx):
        """Добавление следующего трека из 'Моя волна'"""
        try:
            # Получаем список уже проигранных треков
            played_tracks = self.get_played_tracks(ctx.guild.id)
            
            # Пробуем получить новый трек до 10 раз, чтобы избежать повторений
            max_attempts = 10
            for attempt in range(max_attempts):
                # Получаем batch_id для этого сервера
                batch_id = self.my_wave_batch_id.get(ctx.guild.id)
                
                # Получаем следующий трек из "Моя волна"
                track = await self.bot.yandex_client.get_next_my_wave_track(batch_id)
                
                if not track:
                    logger.warning("Не удалось получить следующий трек из 'Моя волна'")
                    return False
                
                # Проверяем, что у трека есть ID
                if 'id' not in track or not track['id']:
                    logger.warning(f"У трека отсутствует ID (попытка {attempt + 1}): {track.get('title', 'Unknown')}")
                    # Сохраняем batch_id для следующего запроса
                    if 'batch_id' in track and track['batch_id']:
                        self.my_wave_batch_id[ctx.guild.id] = track['batch_id']
                    continue
                
                # Проверяем, не был ли трек уже проигран
                if track['id'] not in played_tracks:
                    logger.info(f"Найден новый трек (попытка {attempt + 1}): {track['title']} - {track['artist']}")
                    break
                else:
                    logger.info(f"Трек уже проигран (попытка {attempt + 1}): {track['title']} - {track['artist']}")
                    # Сохраняем batch_id для следующего запроса
                    if 'batch_id' in track and track['batch_id']:
                        self.my_wave_batch_id[ctx.guild.id] = track['batch_id']
                    continue
            else:
                logger.warning("Не удалось найти новый трек после 10 попыток")
                return False
            
            # Сохраняем batch_id для следующего запроса
            if 'batch_id' in track and track['batch_id']:
                self.my_wave_batch_id[ctx.guild.id] = track['batch_id']
                logger.info(f"Сохранен batch_id: {track['batch_id']}")
            
            # Получаем URL трека
            track_url = await self.bot.yandex_client.get_track_url(track['id'])
            
            if not track_url:
                logger.warning(f"Не удалось получить URL для трека {track['id']}")
                return False
            
            # Добавляем трек в очередь
            song = {
                'title': track['title'],
                'artist': track['artist'],
                'duration': track['duration'],
                'url': track_url,
                'id': track['id']
            }
            
            queue = self.get_queue(ctx.guild.id)
            queue.append(song)
            
            logger.info(f"Добавлен следующий трек из 'Моя волна': {track['title']} - {track['artist']}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка добавления следующего трека из 'Моя волна': {e}")
            return False
    
    async def add_to_queue(self, ctx, song_info, url):
        """Добавление трека в очередь"""
        queue = self.get_queue(ctx.guild.id)
        
        if len(queue) >= MAX_QUEUE_SIZE:
            await ctx.send(ERROR_MESSAGES['queue_full'])
            return False
        
        if song_info['duration'] > MAX_SONG_LENGTH:
            await ctx.send(ERROR_MESSAGES['song_too_long'])
            return False
        
        song = {
            'title': song_info['title'],
            'artist': song_info['artist'],
            'duration': song_info['duration'],
            'url': url,
            'cover_url': song_info.get('cover_url'),
            'requester': ctx.author
        }
        
        queue.append(song)
        return True
    
    async def skip_song(self, ctx):
        """Пропуск текущего трека"""
        voice_client = self.get_voice_client(ctx.guild.id)
        
        if not voice_client or not voice_client.is_playing():
            await ctx.send("Сейчас ничего не играет!", ephemeral=True)
            return
        
        # Если включен режим "Моя волна", добавляем новый трек перед пропуском
        if self.my_wave_mode.get(ctx.guild.id, False):
            logger.info("Режим 'Моя волна' активен, добавляем новый трек...")
            await self._add_next_my_wave_track(ctx)
        
        voice_client.stop()
        await ctx.send("⏭️ Трек пропущен!")
    
    async def pause_song(self, ctx):
        """Пауза воспроизведения"""
        voice_client = self.get_voice_client(ctx.guild.id)
        
        if not voice_client or not voice_client.is_playing():
            await ctx.send("Сейчас ничего не играет!", ephemeral=True)
            return
        
        voice_client.pause()
        await ctx.send("⏸️ Воспроизведение приостановлено!")
    
    async def resume_song(self, ctx):
        """Возобновление воспроизведения"""
        voice_client = self.get_voice_client(ctx.guild.id)
        
        if not voice_client or voice_client.is_playing():
            await ctx.send("Сейчас ничего не приостановлено!", ephemeral=True)
            return
        
        voice_client.resume()
        await ctx.send("▶️ Воспроизведение возобновлено!")
    
    async def stop_playback(self, ctx):
        """Остановка воспроизведения и очистка очереди"""
        voice_client = self.get_voice_client(ctx.guild.id)
        queue = self.get_queue(ctx.guild.id)
        
        if voice_client:
            voice_client.stop()
        
        queue.clear()
        self.current_song[ctx.guild.id] = None
        # Сбрасываем режим "Моя волна" и связанные данные
        self.my_wave_mode[ctx.guild.id] = False
        if ctx.guild.id in self.my_wave_batch_id:
            del self.my_wave_batch_id[ctx.guild.id]
        if ctx.guild.id in self.played_tracks:
            del self.played_tracks[ctx.guild.id]
        
        # Отключаемся от голосового канала
        if voice_client:
            await voice_client.disconnect()
            if ctx.guild.id in self.voice_clients:
                del self.voice_clients[ctx.guild.id]
        
        await ctx.send("⏹️ Остановлено и отключился от голосового канала!")
    
    async def show_queue(self, ctx):
        """Показ текущей очереди"""
        queue = self.get_queue(ctx.guild.id)
        current = self.current_song.get(ctx.guild.id)
        
        if not queue and not current:
            await ctx.send("Очередь пуста!", ephemeral=True)
            return
        
        embed = discord.Embed(title="🎵 Очередь воспроизведения", color=0x00ff00)
        
        if current:
            embed.add_field(
                name="Сейчас играет",
                value=f"**{current['title']}**\n{current['artist']}",
                inline=False
            )
        
        if queue:
            queue_text = ""
            for i, song in enumerate(list(queue)[:10], 1):  # Показываем первые 10 треков
                queue_text += f"{i}. **{song['title']}** - {song['artist']}\n"
            
            if len(queue) > 10:
                queue_text += f"... и еще {len(queue) - 10} треков"
            
            embed.add_field(name="Очередь", value=queue_text, inline=False)
        
        await ctx.send(embed=embed)
    
    async def disconnect(self, ctx):
        """Отключение от голосового канала"""
        voice_client = self.get_voice_client(ctx.guild.id)
        
        if voice_client:
            await voice_client.disconnect()
            del self.voice_clients[ctx.guild.id]
            self.queues[ctx.guild.id].clear()
            self.current_song[ctx.guild.id] = None
            await ctx.send("👋 Отключился от голосового канала!")
        else:
            await ctx.send("Бот не подключен к голосовому каналу!", ephemeral=True)
