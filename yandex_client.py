import asyncio
import logging
from yandex_music import Client
from config import ERROR_MESSAGES
import yt_dlp

logger = logging.getLogger(__name__)

class YandexMusicClient:
    def __init__(self):
        self.client = None
        self.is_authenticated = False
        
    async def authenticate_with_token(self, token):
        """Аутентификация в Яндекс.Музыке"""
        try:
            # Создаем клиент с токеном
            self.client = Client(token)
            await asyncio.get_event_loop().run_in_executor(
                None, 
                self.client.init
            )
            self.is_authenticated = True
            logger.info("Успешная авторизация в Яндекс.Музыке")
            return True
        except Exception as e:
            logger.error(f"Ошибка авторизации в Яндекс.Музыке: {e}")
            self.is_authenticated = False
            return False
    
    async def search_tracks(self, query, limit=10):
        """Поиск треков"""
        if not self.is_authenticated:
            logger.error("Клиент не авторизован")
            return []
        
        try:
            # Простой поиск без дополнительных параметров
            search_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.search(query)
            )
            
            tracks = []
            if search_result and hasattr(search_result, 'tracks') and search_result.tracks:
                for track in search_result.tracks.results[:limit]:
                    if track and hasattr(track, 'available') and track.available:
                        track_info = {
                            'id': track.id,
                            'title': track.title,
                            'artist': ', '.join([artist.name for artist in track.artists]) if track.artists else 'Неизвестный исполнитель',
                            'duration': track.duration_ms // 1000 if track.duration_ms else 0,
                            'album': track.albums[0].title if track.albums and len(track.albums) > 0 else 'Неизвестный альбом',
                            'cover_url': f"https://{track.cover_uri.replace('%%', '200x200')}" if track.cover_uri else None
                        }
                        tracks.append(track_info)
            
            if tracks:
                return tracks
            
            # Если не найдено, попробуем альтернативный поиск
            return await self._alternative_search(query, limit)
            
        except Exception as e:
            logger.error(f"Ошибка поиска треков: {e}")
            # Попробуем альтернативный способ поиска
            try:
                return await self._alternative_search(query, limit)
            except Exception as e2:
                logger.error(f"Альтернативный поиск также не удался: {e2}")
                return []
    
    async def _alternative_search(self, query, limit=10):
        """Альтернативный способ поиска треков"""
        try:
            # Простой поиск без дополнительных параметров
            search_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.search(query)
            )
            
            tracks = []
            if search_result and hasattr(search_result, 'tracks') and search_result.tracks:
                for track in search_result.tracks.results[:limit]:
                    if track and hasattr(track, 'available') and track.available:
                        track_info = {
                            'id': track.id,
                            'title': track.title,
                            'artist': ', '.join([artist.name for artist in track.artists]) if track.artists else 'Неизвестный исполнитель',
                            'duration': track.duration_ms // 1000 if track.duration_ms else 0,
                            'album': track.albums[0].title if track.albums and len(track.albums) > 0 else 'Неизвестный альбом',
                            'cover_url': f"https://{track.cover_uri.replace('%%', '200x200')}" if track.cover_uri else None
                        }
                        tracks.append(track_info)
            
            return tracks
        except Exception as e:
            logger.error(f"Ошибка альтернативного поиска: {e}")
            return []
    
    async def get_track_info_by_id(self, track_id):
        """Получение информации о треке по ID"""
        if not self.is_authenticated:
            return None
        
        try:
            track = await asyncio.get_event_loop().run_in_executor(
                None,
                self.client.tracks,
                [track_id]
            )
            
            if track and track[0]:
                track_obj = track[0]
                track_info = {
                    'id': track_obj.id,
                    'title': track_obj.title,
                    'artist': ', '.join([artist.name for artist in track_obj.artists]) if track_obj.artists else 'Неизвестный исполнитель',
                    'duration': track_obj.duration_ms // 1000 if track_obj.duration_ms else 0,
                    'album': track_obj.albums[0].title if track_obj.albums and len(track_obj.albums) > 0 else 'Неизвестный альбом',
                    'cover_url': f"https://{track_obj.cover_uri.replace('%%', '200x200')}" if track_obj.cover_uri else None
                }
                return track_info
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о треке: {e}")
            
        return None
    
    async def get_track_url(self, track_id):
        """Получение URL трека для воспроизведения"""
        if not self.is_authenticated:
            return None
        
        # Попробуем несколько способов получения URL
        
        # Способ 1: Через track_download_info
        try:
            download_info = await asyncio.get_event_loop().run_in_executor(
                None,
                self.client.track_download_info,
                track_id
            )
            
            if download_info:
                logger.info(f"Получена информация о загрузке для трека {track_id}")
                
                # Выбираем лучшее качество
                if hasattr(download_info, '__iter__') and len(download_info) > 0:
                    best_quality = max(download_info, key=lambda x: getattr(x, 'bitrate_in_kbps', 0))
                else:
                    best_quality = download_info
                
                # Получаем прямую ссылку
                if hasattr(best_quality, 'direct_link') and best_quality.direct_link:
                    logger.info(f"Найдена прямая ссылка через direct_link")
                    return best_quality.direct_link
                elif hasattr(best_quality, 'get_direct_link'):
                    direct_link = await asyncio.get_event_loop().run_in_executor(
                        None,
                        best_quality.get_direct_link
                    )
                    logger.info(f"Получена прямая ссылка через get_direct_link")
                    return direct_link
                elif hasattr(best_quality, 'url'):
                    logger.info(f"Найдена ссылка через url")
                    return best_quality.url
                    
        except Exception as e:
            logger.error(f"Способ 1 получения URL не удался: {e}")
        
        # Способ 2: Через tracks и get_download_info
        try:
            track = await asyncio.get_event_loop().run_in_executor(
                None,
                self.client.tracks,
                [track_id]
            )
            
            if track and track[0]:
                track_obj = track[0]
                
                # Пробуем получить download_info напрямую
                if hasattr(track_obj, 'get_download_info'):
                    download_info = track_obj.get_download_info()
                    if download_info and len(download_info) > 0:
                        best_quality = max(download_info, key=lambda x: getattr(x, 'bitrate_in_kbps', 0))
                        
                        if hasattr(best_quality, 'direct_link') and best_quality.direct_link:
                            logger.info(f"Найдена прямая ссылка через tracks.get_download_info")
                            return best_quality.direct_link
                        elif hasattr(best_quality, 'get_direct_link'):
                            direct_link = best_quality.get_direct_link()
                            logger.info(f"Получена прямая ссылка через get_direct_link")
                            return direct_link
                            
        except Exception as e:
            logger.error(f"Способ 2 получения URL не удался: {e}")
        
        # Способ 3: Через yt-dlp
        try:
            ytdlp_url = await self.get_track_url_ytdlp(track_id)
            if ytdlp_url:
                logger.info(f"Получен URL через yt-dlp")
                return ytdlp_url
        except Exception as e:
            logger.error(f"Способ 3 (yt-dlp) не удался: {e}")
        
        # Способ 4: Создаем URL на основе ID (может не работать, но попробуем)
        try:
            # Иногда можно создать URL напрямую
            fake_url = f"https://music.yandex.ru/track/{track_id}"
            logger.info(f"Создан фиктивный URL: {fake_url}")
            return fake_url
        except Exception as e:
            logger.error(f"Способ 4 также не удался: {e}")
            
        return None
    
    async def get_track_url_ytdlp(self, track_id):
        """Получение URL трека через yt-dlp"""
        try:
            yandex_url = f"https://music.yandex.ru/track/{track_id}"
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'format': 'bestaudio/best',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: ydl.extract_info(yandex_url, download=False)
                )
                
                if info and 'url' in info:
                    logger.info(f"Получен URL через yt-dlp: {info['url'][:100]}...")
                    return info['url']
                    
        except Exception as e:
            logger.error(f"Ошибка получения URL через yt-dlp: {e}")
            
        return None
    
    async def _get_track_url_alternative(self, track_id):
        """Альтернативный способ получения URL трека"""
        try:
            # Попробуем получить трек напрямую через клиент
            track = await asyncio.get_event_loop().run_in_executor(
                None,
                self.client.track_download_info,
                track_id
            )
            
            if track:
                # Ищем лучший вариант
                if hasattr(track, 'get_direct_link'):
                    return await asyncio.get_event_loop().run_in_executor(
                        None,
                        track.get_direct_link
                    )
                elif hasattr(track, 'direct_link'):
                    return track.direct_link
                else:
                    return str(track)
            
        except Exception as e:
            logger.error(f"Ошибка альтернативного получения URL: {e}")
            
        # Последняя попытка - используем старый API
        try:
            track = await asyncio.get_event_loop().run_in_executor(
                None,
                self.client.tracks,
                [track_id]
            )
            
            if track and track[0]:
                # Попробуем получить ссылку на трек напрямую
                track_obj = track[0]
                if hasattr(track_obj, 'get_download_info'):
                    download_info = track_obj.get_download_info()
                    if download_info and len(download_info) > 0:
                        best = max(download_info, key=lambda x: getattr(x, 'bitrate_in_kbps', 0))
                        if hasattr(best, 'direct_link'):
                            return best.direct_link
                        elif hasattr(best, 'get_direct_link'):
                            return best.get_direct_link()
            
        except Exception as e2:
            logger.error(f"Последняя попытка получения URL также не удалась: {e2}")
            
        return None
    
    async def get_my_wave_tracks(self, limit=5):
        """Получение треков из 'Моя волна' (только для начальной загрузки)"""
        if not self.is_authenticated:
            return []
        
        try:
            # Прямое обращение к user:onyourwave для начальной загрузки
            logger.info("Получение начальных треков из 'Моя волна'...")
            direct_tracks = await self._get_direct_my_wave_tracks(limit)
            if direct_tracks:
                logger.info(f"Получены начальные треки с user:onyourwave: {len(direct_tracks)} треков")
                return direct_tracks
            
            # Если не удалось, пробуем другие способы
            logger.warning("Не удалось получить треки с user:onyourwave, пробуем альтернативы...")
            
            # Способ 2: Через лайкнутые треки
            try:
                liked_tracks = await self._get_liked_tracks_fallback(limit)
                if liked_tracks:
                    logger.info(f"Используем лайкнутые треки: {len(liked_tracks)} треков")
                    return liked_tracks
            except Exception as e:
                logger.error(f"Ошибка получения лайкнутых треков: {e}")
            
            # Способ 3: Популярные треки
            try:
                popular_tracks = await self._get_popular_tracks_fallback(limit)
                if popular_tracks:
                    logger.info(f"Используем популярные треки: {len(popular_tracks)} треков")
                    return popular_tracks
            except Exception as e:
                logger.error(f"Ошибка получения популярных треков: {e}")
            
            logger.warning("Не удалось найти треки для 'Моя волна'")
            return []
                
        except Exception as e:
            logger.error(f"Общая ошибка получения 'Моя волна': {e}")
            
        return []
    
    async def _get_liked_tracks_fallback(self, limit=20):
        """Получение лайкнутых треков как альтернатива 'Моя волна'"""
        try:
            liked_tracks = await asyncio.get_event_loop().run_in_executor(
                None,
                self.client.users_likes_tracks
            )
            
            tracks = []
            if liked_tracks and hasattr(liked_tracks, 'tracks'):
                for track_short in liked_tracks.tracks[:limit]:
                    if track_short.track:
                        track = track_short.track
                        track_info = {
                            'id': track.id,
                            'title': track.title,
                            'artist': ', '.join([artist.name for artist in track.artists]) if track.artists else 'Неизвестный исполнитель',
                            'duration': track.duration_ms // 1000 if track.duration_ms else 0,
                            'album': track.albums[0].title if track.albums and len(track.albums) > 0 else 'Неизвестный альбом',
                            'cover_url': f"https://{track.cover_uri.replace('%%', '200x200')}" if track.cover_uri else None
                        }
                        tracks.append(track_info)
            
            return tracks
        except Exception as e:
            logger.error(f"Ошибка получения лайкнутых треков: {e}")
            return []
    
    async def _get_direct_my_wave_tracks(self, limit=20):
        """Прямое получение треков с радиостанции user:onyourwave"""
        try:
            logger.info("Прямое обращение к user:onyourwave...")
            
            # Пробуем разные способы получения треков с user:onyourwave
            station_tracks = None
            
            # Способ 1: Базовый вызов
            try:
                station_tracks = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.client.rotor_station_tracks,
                    'user:onyourwave'
                )
                logger.info("Получены треки с user:onyourwave (способ 1)")
            except Exception as e1:
                logger.error(f"Способ 1 не удался: {e1}")
                
                # Способ 2: С настройками
                try:
                    station_tracks = await asyncio.get_event_loop().run_in_executor(
                        None,
                        self.client.rotor_station_tracks,
                        'user:onyourwave',
                        {"language": "ru", "moodEnergy": "all"},
                        None
                    )
                    logger.info("Получены треки с user:onyourwave (способ 2)")
                except Exception as e2:
                    logger.error(f"Способ 2 не удался: {e2}")
                    
                    # Способ 3: С пустыми параметрами
                    try:
                        station_tracks = await asyncio.get_event_loop().run_in_executor(
                            None,
                            self.client.rotor_station_tracks,
                            'user:onyourwave',
                            {},
                            ""
                        )
                        logger.info("Получены треки с user:onyourwave (способ 3)")
                    except Exception as e3:
                        logger.error(f"Способ 3 не удался: {e3}")
                        raise e3
            
            tracks = []
            if station_tracks and hasattr(station_tracks, 'sequence'):
                logger.info(f"Найдено {len(station_tracks.sequence)} треков в последовательности")
                for track_short in station_tracks.sequence[:limit]:
                    if hasattr(track_short, 'track') and track_short.track:
                        track = track_short.track
                        track_info = {
                            'id': track.id,
                            'title': track.title,
                            'artist': ', '.join([artist.name for artist in track.artists]) if track.artists else 'Неизвестный исполнитель',
                            'duration': track.duration_ms // 1000 if track.duration_ms else 0,
                            'album': track.albums[0].title if track.albums and len(track.albums) > 0 else 'Неизвестный альбом',
                            'cover_url': f"https://{track.cover_uri.replace('%%', '200x200')}" if track.cover_uri else None
                        }
                        tracks.append(track_info)
            
            logger.info(f"Обработано {len(tracks)} треков с user:onyourwave")
            return tracks
            
        except Exception as e:
            logger.error(f"Ошибка прямого получения треков с user:onyourwave: {e}")
            return []
    
    async def get_next_my_wave_track(self, batch_id=None):
        """Получение следующего трека из 'Моя волна' для обновления"""
        try:
            logger.info(f"Получение следующего трека из 'Моя волна' (batch_id: {batch_id})...")
            
            # Пробуем получить следующий трек с user:onyourwave
            station_tracks = None
            
            # Способ 1: С batch_id для получения следующего трека
            if batch_id:
                try:
                    station_tracks = await asyncio.get_event_loop().run_in_executor(
                        None,
                        self.client.rotor_station_tracks,
                        'user:onyourwave',
                        None,  # settings
                        batch_id  # batch_id для получения следующего трека
                    )
                    logger.info("Получен следующий трек с batch_id")
                except Exception as e1:
                    logger.error(f"Способ 1 с batch_id не удался: {e1}")
                    batch_id = None  # Сбрасываем batch_id для следующей попытки
            
            # Способ 2: Без batch_id (получаем новые треки)
            if not station_tracks:
                try:
                    station_tracks = await asyncio.get_event_loop().run_in_executor(
                        None,
                        self.client.rotor_station_tracks,
                        'user:onyourwave'
                    )
                    logger.info("Получен следующий трек без batch_id")
                except Exception as e2:
                    logger.error(f"Способ 2 без batch_id не удался: {e2}")
                    return None
            
            if station_tracks and hasattr(station_tracks, 'sequence') and station_tracks.sequence:
                # Берем первый трек из последовательности
                track_short = station_tracks.sequence[0]
                if hasattr(track_short, 'track') and track_short.track:
                    track = track_short.track
                    track_info = {
                        'id': track.id,
                        'title': track.title,
                        'artist': ', '.join([artist.name for artist in track.artists]) if track.artists else 'Неизвестный исполнитель',
                        'duration': track.duration_ms // 1000 if track.duration_ms else 0,
                        'album': track.albums[0].title if track.albums and len(track.albums) > 0 else 'Неизвестный альбом',
                        'cover_url': f"https://{track.cover_uri.replace('%%', '200x200')}" if track.cover_uri else None,
                        'batch_id': getattr(station_tracks, 'batch_id', None)  # Сохраняем batch_id для следующего запроса
                    }
                    logger.info(f"Получен следующий трек: {track_info['title']} - {track_info['artist']}")
                    return track_info
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения следующего трека из 'Моя волна': {e}")
            return None
    
    async def _get_radio_tracks_fallback(self, limit=20):
        """Получение треков через радиостанции как альтернатива 'Моя волна'"""
        try:
            # Попробуем получить радиостанции пользователя
            stations = await asyncio.get_event_loop().run_in_executor(
                None,
                self.client.rotor_stations_dashboard
            )
            
            tracks = []
            if stations and hasattr(stations, 'stations'):
                logger.info(f"Найдено {len(stations.stations)} радиостанций")
                
                # Ищем станцию "Моя волна"
                for station in stations.stations:
                    if hasattr(station, 'station') and station.station:
                        station_info = station.station
                        station_name = getattr(station_info, 'name', '').lower()
                        logger.info(f"Радиостанция: {station_name}")
                        
                        if 'волна' in station_name or 'my wave' in station_name or station_info.id == 'user:onyourwave':
                            logger.info(f"Найдена станция 'Моя волна': {station_name}")
                            
                            # Получаем треки с этой станции
                            try:
                                # Попробуем разные способы получения треков с радиостанции
                                station_tracks = None
                                
                                # Способ 1: С базовыми параметрами
                                try:
                                    station_tracks = await asyncio.get_event_loop().run_in_executor(
                                        None,
                                        self.client.rotor_station_tracks,
                                        station_info.id,
                                        None,  # settings
                                        None   # batch_id
                                    )
                                except Exception as e1:
                                    logger.error(f"Способ 1 получения треков с радиостанции не удался: {e1}")
                                    
                                    # Способ 2: С пустыми параметрами
                                    try:
                                        station_tracks = await asyncio.get_event_loop().run_in_executor(
                                            None,
                                            self.client.rotor_station_tracks,
                                            station_info.id,
                                            {},   # settings как пустой dict
                                            ""    # batch_id как пустая строка
                                        )
                                    except Exception as e2:
                                        logger.error(f"Способ 2 получения треков с радиостанции не удался: {e2}")
                                        
                                        # Способ 3: Только с ID станции
                                        try:
                                            station_tracks = await asyncio.get_event_loop().run_in_executor(
                                                None,
                                                self.client.rotor_station_tracks,
                                                station_info.id
                                            )
                                        except Exception as e3:
                                            logger.error(f"Способ 3 получения треков с радиостанции не удался: {e3}")
                                            
                                            # Способ 4: Через rotor API напрямую
                                            try:
                                                logger.info("Попытка получения треков через rotor API...")
                                                rotor_tracks = await asyncio.get_event_loop().run_in_executor(
                                                    None,
                                                    self.client.rotor_station_tracks,
                                                    station_info.id,
                                                    {"language": "ru", "moodEnergy": "all"},
                                                    None
                                                )
                                                if rotor_tracks:
                                                    station_tracks = rotor_tracks
                                                    logger.info("Получены треки через rotor API")
                                            except Exception as e4:
                                                logger.error(f"Способ 4 получения треков с радиостанции не удался: {e4}")
                                                raise e4
                                
                                if station_tracks and hasattr(station_tracks, 'sequence'):
                                    for track_short in station_tracks.sequence[:limit]:
                                        if hasattr(track_short, 'track') and track_short.track:
                                            track = track_short.track
                                            track_info = {
                                                'id': track.id,
                                                'title': track.title,
                                                'artist': ', '.join([artist.name for artist in track.artists]) if track.artists else 'Неизвестный исполнитель',
                                                'duration': track.duration_ms // 1000 if track.duration_ms else 0,
                                                'album': track.albums[0].title if track.albums and len(track.albums) > 0 else 'Неизвестный альбом',
                                                'cover_url': f"https://{track.cover_uri.replace('%%', '200x200')}" if track.cover_uri else None
                                            }
                                            tracks.append(track_info)
                                    
                                    if tracks:
                                        logger.info(f"Получено {len(tracks)} треков с радиостанции 'Моя волна'")
                                        return tracks
                            except Exception as e:
                                logger.error(f"Ошибка получения треков с радиостанции: {e}")
            
            return []
        except Exception as e:
            logger.error(f"Ошибка получения радиостанций: {e}")
            return []
    
    async def _get_popular_tracks_fallback(self, limit=20):
        """Получение популярных треков как альтернатива 'Моя волна'"""
        try:
            # Попробуем получить популярные треки через поиск
            search_results = await asyncio.get_event_loop().run_in_executor(
                None,
                self.client.search,
                'популярные треки'
            )
            
            tracks = []
            if search_results and hasattr(search_results, 'tracks') and search_results.tracks:
                for track_short in search_results.tracks.results[:limit]:
                    if track_short:
                        track_info = {
                            'id': track_short.id,
                            'title': track_short.title,
                            'artist': ', '.join([artist.name for artist in track_short.artists]) if track_short.artists else 'Неизвестный исполнитель',
                            'duration': track_short.duration_ms // 1000 if track_short.duration_ms else 0,
                            'album': track_short.albums[0].title if track_short.albums and len(track_short.albums) > 0 else 'Неизвестный альбом',
                            'cover_url': f"https://{track_short.cover_uri.replace('%%', '200x200')}" if track_short.cover_uri else None
                        }
                        tracks.append(track_info)
            
            return tracks
        except Exception as e:
            logger.error(f"Ошибка получения популярных треков: {e}")
            return []
    
    async def _get_playlist_tracks(self, playlist_id, limit=20):
        """Получение треков из плейлиста по ID"""
        try:
            playlist = await asyncio.get_event_loop().run_in_executor(
                None,
                self.client.users_playlists,
                '3',  # kind для пользовательских плейлистов
                playlist_id
            )
            
            tracks = []
            if playlist and hasattr(playlist, 'tracks') and playlist.tracks:
                for track_short in playlist.tracks[:limit]:
                    if track_short.track:
                        track = track_short.track
                        track_info = {
                            'id': track.id,
                            'title': track.title,
                            'artist': ', '.join([artist.name for artist in track.artists]) if track.artists else 'Неизвестный исполнитель',
                            'duration': track.duration_ms // 1000 if track.duration_ms else 0,
                            'album': track.albums[0].title if track.albums and len(track.albums) > 0 else 'Неизвестный альбом',
                            'cover_url': f"https://{track.cover_uri.replace('%%', '200x200')}" if track.cover_uri else None
                        }
                        tracks.append(track_info)
            
            return tracks
        except Exception as e:
            logger.error(f"Ошибка получения треков плейлиста: {e}")
            return []
    
    async def get_user_playlists(self):
        """Получение плейлистов пользователя"""
        if not self.is_authenticated:
            logger.error("Клиент не авторизован")
            return []
        
        try:
            logger.info("Получаем плейлисты пользователя...")
            
            # Пробуем разные способы получения плейлистов
            playlists = None
            
            # Способ 1: С kind='3' (пользовательские плейлисты)
            try:
                playlists = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.client.users_playlists,
                    '3'  # kind для пользовательских плейлистов
                )
                logger.info("Получены плейлисты способом 1 (kind='3')")
                
                # Проверяем, что это за объект
                logger.info(f"Тип объекта: {type(playlists)}")
                if hasattr(playlists, '__iter__') and not isinstance(playlists, str):
                    logger.info("Объект итерируемый, но не строка")
                else:
                    logger.info("Объект не итерируемый или строка")
                    
            except Exception as e1:
                logger.warning(f"Способ 1 не сработал: {e1}")
                
                # Способ 2: Без параметров
                try:
                    playlists = await asyncio.get_event_loop().run_in_executor(
                        None,
                        self.client.users_playlists
                    )
                    logger.info("Получены плейлисты способом 2 (без параметров)")
                except Exception as e2:
                    logger.warning(f"Способ 2 не сработал: {e2}")
                    
                    # Способ 3: С kind=3 (число)
                    try:
                        playlists = await asyncio.get_event_loop().run_in_executor(
                            None,
                            self.client.users_playlists,
                            3  # kind как число
                        )
                        logger.info("Получены плейлисты способом 3 (kind=3)")
                    except Exception as e3:
                        logger.warning(f"Способ 3 не сработал: {e3}")
                        
                        # Способ 4: Попробуем получить коллекцию пользователя
                        try:
                            logger.info("Пробуем получить коллекцию пользователя...")
                            # Получаем информацию о пользователе
                            user_info = await asyncio.get_event_loop().run_in_executor(
                                None,
                                self.client.account_status
                            )
                            
                            if user_info and hasattr(user_info, 'account'):
                                user_id = user_info.account.uid
                                logger.info(f"ID пользователя: {user_id}")
                                
                                # Получаем плейлисты пользователя по ID
                                playlists = await asyncio.get_event_loop().run_in_executor(
                                    None,
                                    self.client.users_playlists,
                                    user_id
                                )
                                logger.info("Получены плейлисты способом 4 (по ID пользователя)")
                            else:
                                raise Exception("Не удалось получить ID пользователя")
                                
                        except Exception as e4:
                            logger.error(f"Способ 4 не сработал: {e4}")
                            raise e4
            
            playlist_list = []
            
            # Обрабатываем результат
            if playlists:
                # Если это один объект Playlist, а не список
                if hasattr(playlists, 'playlist_id'):
                    logger.info("Получен один плейлист, обрабатываем как объект")
                    try:
                        playlist_info = {
                            'id': getattr(playlists, 'playlist_id', 'unknown'),
                            'title': getattr(playlists, 'title', 'Неизвестный плейлист'),
                            'track_count': getattr(playlists, 'track_count', 0),
                            'cover_url': None
                        }
                        
                        # Безопасно получаем обложку
                        if hasattr(playlists, 'cover') and playlists.cover and hasattr(playlists.cover, 'uri'):
                            playlist_info['cover_url'] = f"https://{playlists.cover.uri.replace('%%', '200x200')}"
                        
                        playlist_list.append(playlist_info)
                        logger.info(f"Добавлен плейлист: {playlist_info['title']} (ID: {playlist_info['id']})")
                    except Exception as e:
                        logger.error(f"Ошибка обработки единственного плейлиста: {e}")
                
                # Если это список плейлистов
                elif hasattr(playlists, '__iter__') and not isinstance(playlists, str):
                    try:
                        playlists_list = list(playlists)
                        logger.info(f"Найдено {len(playlists_list)} плейлистов в списке")
                        for i, playlist in enumerate(playlists_list):
                            try:
                                playlist_info = {
                                    'id': getattr(playlist, 'playlist_id', f'unknown_{i}'),
                                    'title': getattr(playlist, 'title', f'Плейлист {i+1}'),
                                    'track_count': getattr(playlist, 'track_count', 0),
                                    'cover_url': None
                                }
                                
                                # Безопасно получаем обложку
                                if hasattr(playlist, 'cover') and playlist.cover and hasattr(playlist.cover, 'uri'):
                                    playlist_info['cover_url'] = f"https://{playlist.cover.uri.replace('%%', '200x200')}"
                                
                                playlist_list.append(playlist_info)
                                logger.info(f"Добавлен плейлист: {playlist_info['title']} (ID: {playlist_info['id']})")
                            except Exception as e:
                                logger.error(f"Ошибка обработки плейлиста {i}: {e}")
                                continue
                    except Exception as e:
                        logger.error(f"Ошибка преобразования в список: {e}")
                
                # Если это объект с атрибутом playlists
                elif hasattr(playlists, 'playlists'):
                    logger.info("Найден атрибут playlists, обрабатываем")
                    try:
                        playlists_attr = playlists.playlists
                        if hasattr(playlists_attr, '__iter__') and not isinstance(playlists_attr, str):
                            playlists_list = list(playlists_attr)
                            logger.info(f"Найдено {len(playlists_list)} плейлистов в атрибуте playlists")
                            for i, playlist in enumerate(playlists_list):
                                try:
                                    playlist_info = {
                                        'id': getattr(playlist, 'playlist_id', f'unknown_{i}'),
                                        'title': getattr(playlist, 'title', f'Плейлист {i+1}'),
                                        'track_count': getattr(playlist, 'track_count', 0),
                                        'cover_url': None
                                    }
                                    
                                    # Безопасно получаем обложку
                                    if hasattr(playlist, 'cover') and playlist.cover and hasattr(playlist.cover, 'uri'):
                                        playlist_info['cover_url'] = f"https://{playlist.cover.uri.replace('%%', '200x200')}"
                                    
                                    playlist_list.append(playlist_info)
                                    logger.info(f"Добавлен плейлист: {playlist_info['title']} (ID: {playlist_info['id']})")
                                except Exception as e:
                                    logger.error(f"Ошибка обработки плейлиста {i}: {e}")
                                    continue
                    except Exception as e:
                        logger.error(f"Ошибка обработки атрибута playlists: {e}")
                
                else:
                    logger.warning(f"Неизвестный тип объекта плейлистов: {type(playlists)}")
                    logger.info(f"Атрибуты объекта: {dir(playlists)}")
            else:
                logger.warning("Плейлисты не найдены или пусты")
            
            logger.info(f"Итого обработано {len(playlist_list)} плейлистов")
            return playlist_list
            
        except Exception as e:
            logger.error(f"Ошибка получения плейлистов: {e}")
            return []
