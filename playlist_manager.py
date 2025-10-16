import asyncio
import random
import logging
from yandex_client import YandexMusicClient

logger = logging.getLogger(__name__)

class PlaylistManager:
    def __init__(self, yandex_client: YandexMusicClient):
        self.yandex_client = yandex_client
    
    async def get_playlist_tracks(self, playlist_id, limit=20):
        """Получение треков из плейлиста"""
        if not self.yandex_client.is_authenticated:
            logger.error("Клиент не авторизован")
            return []
        
        try:
            logger.info(f"Получаем треки из плейлиста {playlist_id}...")
            
            # Пробуем разные способы получения треков из плейлиста
            tracks = []
            
            # Способ 0: Для плейлиста "Мне нравится" сначала пробуем users_likes_tracks
            logger.info(f"Проверяем условие для способа 0: playlist_id='{playlist_id}'")
            should_use_likes = ('нравится' in playlist_id.lower() or 'liked' in playlist_id.lower() or 
                               '131840276:3' in playlist_id or 'Мне нравится' in playlist_id)
            logger.info(f"Условие для users_likes_tracks: {should_use_likes}")
            
            if should_use_likes:
                try:
                    logger.info("Пробуем получить лайкнутые треки (приоритетный способ)...")
                    liked_tracks = await asyncio.get_event_loop().run_in_executor(
                        None,
                        self.yandex_client.client.users_likes_tracks
                    )
                    
                    if liked_tracks and hasattr(liked_tracks, 'tracks') and liked_tracks.tracks:
                        total = len(liked_tracks.tracks)
                        logger.info(f"Найдено лайкнутых треков: {total}")

                        # Собираем все ID, затем выбираем случайные
                        all_ids = []
                        for track_short in liked_tracks.tracks:
                            if hasattr(track_short, 'id') and track_short.id:
                                all_ids.append(track_short.id)
                            elif isinstance(track_short, dict) and track_short.get('id'):
                                all_ids.append(track_short['id'])

                        if all_ids:
                            sample_size = min(limit, len(all_ids))
                            track_ids = random.sample(all_ids, sample_size)
                            logger.info(f"Случайно выбрано {len(track_ids)} треков для загрузки")
                            
                            # Загружаем полную информацию о треках
                            logger.info("Загружаем полную информацию о выбранных треках...")
                            try:
                                # Используем tracks API напрямую
                                full_tracks = await asyncio.get_event_loop().run_in_executor(
                                    None,
                                    self.yandex_client.client.tracks,
                                    track_ids
                                )
                                
                                logger.info(f"Загружено треков: {len(full_tracks) if full_tracks else 0}")
                                
                                if full_tracks:
                                    for track in full_tracks:
                                        if track:
                                            track_info = {
                                                'id': track.id,
                                                'title': track.title,
                                                'artist': ', '.join([artist.name for artist in track.artists]),
                                                'duration': track.duration_ms // 1000,
                                                'album': track.albums[0].title if track.albums else 'Неизвестный альбом',
                                                'cover_url': f"https://{track.cover_uri.replace('%%', '200x200')}" if track.cover_uri else None
                                            }
                                            tracks.append(track_info)
                                    
                                    if tracks:
                                        logger.info(f"Готово треков: {len(tracks)} (liked random)")
                                        return tracks
                                    else:
                                        logger.warning("Не удалось обработать загруженные треки")
                                else:
                                    logger.warning("Не удалось загрузить полную информацию о треках")
                                    
                            except Exception as fetch_error:
                                logger.error(f"Ошибка загрузки треков: {fetch_error}")
                        else:
                            logger.warning("Не найдены ID лайкнутых треков")
                    else:
                        logger.warning("liked_tracks пуст или не содержит tracks")
                            
                except Exception as e0:
                    logger.error(f"Способ 0 (users_likes_tracks приоритетный) не сработал: {e0}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
            else:
                logger.info("Условие для users_likes_tracks не выполнено, пропускаем способ 0")
            
            # Способ 1: Через users_playlists с kind='3'
            try:
                playlist = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.yandex_client.client.users_playlists,
                    '3',  # kind для пользовательских плейлистов
                    playlist_id
                )
                logger.info("Получен плейлист способом 1 (kind='3')")
                
                if playlist and hasattr(playlist, 'tracks') and playlist.tracks:
                    for track_short in playlist.tracks[:limit]:
                        if track_short.track:
                            track = track_short.track
                            track_info = {
                                'id': track.id,
                                'title': track.title,
                                'artist': ', '.join([artist.name for artist in track.artists]),
                                'duration': track.duration_ms // 1000,
                                'album': track.albums[0].title if track.albums else 'Неизвестный альбом',
                                'cover_url': f"https://{track.cover_uri.replace('%%', '200x200')}" if track.cover_uri else None
                            }
                            tracks.append(track_info)
                    
                    if tracks:
                        logger.info(f"Получено {len(tracks)} треков способом 1")
                        return tracks
                        
            except Exception as e1:
                logger.warning(f"Способ 1 не сработал: {e1}")
            
            # Способ 2: Для плейлиста "Мне нравится" используем users_likes_tracks
            # Проверяем по ID или названию плейлиста
            if ('нравится' in playlist_id.lower() or 'liked' in playlist_id.lower() or 
                '131840276:3' in playlist_id or 'Мне нравится' in playlist_id):
                try:
                    logger.info("Пробуем получить треки через users_likes_tracks...")
                    liked_tracks = await asyncio.get_event_loop().run_in_executor(
                        None,
                        self.yandex_client.client.users_likes_tracks
                    )
                    
                    if liked_tracks and hasattr(liked_tracks, 'tracks') and liked_tracks.tracks:
                        for track_short in liked_tracks.tracks[:limit]:
                            if track_short.track:
                                track = track_short.track
                                track_info = {
                                    'id': track.id,
                                    'title': track.title,
                                    'artist': ', '.join([artist.name for artist in track.artists]),
                                    'duration': track.duration_ms // 1000,
                                    'album': track.albums[0].title if track.albums else 'Неизвестный альбом',
                                    'cover_url': f"https://{track.cover_uri.replace('%%', '200x200')}" if track.cover_uri else None
                                }
                                tracks.append(track_info)
                        
                        if tracks:
                            logger.info(f"Получено {len(tracks)} треков через users_likes_tracks")
                            return tracks
                            
                except Exception as e2:
                    logger.warning(f"Способ 2 (users_likes_tracks) не сработал: {e2}")
            
            # Способ 3: Пробуем получить плейлист без kind
            try:
                logger.info("Пробуем получить плейлист без kind...")
                playlist = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.yandex_client.client.users_playlists,
                    playlist_id
                )
                
                if playlist and hasattr(playlist, 'tracks') and playlist.tracks:
                    for track_short in playlist.tracks[:limit]:
                        if track_short.track:
                            track = track_short.track
                            track_info = {
                                'id': track.id,
                                'title': track.title,
                                'artist': ', '.join([artist.name for artist in track.artists]),
                                'duration': track.duration_ms // 1000,
                                'album': track.albums[0].title if track.albums else 'Неизвестный альбом',
                                'cover_url': f"https://{track.cover_uri.replace('%%', '200x200')}" if track.cover_uri else None
                            }
                            tracks.append(track_info)
                    
                    if tracks:
                        logger.info(f"Получено {len(tracks)} треков способом 3")
                        return tracks
                        
            except Exception as e3:
                logger.warning(f"Способ 3 не сработал: {e3}")
            
            # Способ 4: Пробуем получить плейлист с kind=3 (число)
            try:
                logger.info("Пробуем получить плейлист с kind=3...")
                playlist = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.yandex_client.client.users_playlists,
                    3,  # kind как число
                    playlist_id
                )
                
                if playlist and hasattr(playlist, 'tracks') and playlist.tracks:
                    for track_short in playlist.tracks[:limit]:
                        if track_short.track:
                            track = track_short.track
                            track_info = {
                                'id': track.id,
                                'title': track.title,
                                'artist': ', '.join([artist.name for artist in track.artists]),
                                'duration': track.duration_ms // 1000,
                                'album': track.albums[0].title if track.albums else 'Неизвестный альбом',
                                'cover_url': f"https://{track.cover_uri.replace('%%', '200x200')}" if track.cover_uri else None
                            }
                            tracks.append(track_info)
                    
                    if tracks:
                        logger.info(f"Получено {len(tracks)} треков способом 4")
                        return tracks
                        
            except Exception as e4:
                logger.warning(f"Способ 4 не сработал: {e4}")
            
            # Способ 5: Попробуем получить плейлист через tracks API
            try:
                logger.info("Пробуем получить треки через tracks API...")
                # Парсим ID плейлиста
                if ':' in playlist_id:
                    user_id, playlist_kind = playlist_id.split(':')
                    logger.info(f"Парсинг ID: user_id={user_id}, kind={playlist_kind}")
                    
                    # Пробуем получить треки через tracks API
                    track_ids = await asyncio.get_event_loop().run_in_executor(
                        None,
                        self.yandex_client.client.users_playlists,
                        user_id,
                        playlist_id
                    )
                    
                    if track_ids and hasattr(track_ids, 'tracks') and track_ids.tracks:
                        # Получаем информацию о треках
                        track_id_list = [track_short.track.id for track_short in track_ids.tracks[:limit] if track_short.track]
                        if track_id_list:
                            tracks_info = await asyncio.get_event_loop().run_in_executor(
                                None,
                                self.yandex_client.client.tracks,
                                track_id_list
                            )
                            
                            if tracks_info:
                                for track in tracks_info[:limit]:
                                    if track:
                                        track_info = {
                                            'id': track.id,
                                            'title': track.title,
                                            'artist': ', '.join([artist.name for artist in track.artists]),
                                            'duration': track.duration_ms // 1000,
                                            'album': track.albums[0].title if track.albums else 'Неизвестный альбом',
                                            'cover_url': f"https://{track.cover_uri.replace('%%', '200x200')}" if track.cover_uri else None
                                        }
                                        tracks.append(track_info)
                                
                                if tracks:
                                    logger.info(f"Получено {len(tracks)} треков способом 5")
                                    return tracks
                                    
            except Exception as e5:
                logger.warning(f"Способ 5 не сработал: {e5}")
            
            logger.warning("Все способы получения треков из плейлиста не сработали")
            return []
                
        except Exception as e:
            logger.error(f"Общая ошибка получения плейлиста: {e}")
            
        return []
    
    async def search_playlists(self, query, limit=10):
        """Поиск плейлистов"""
        if not self.yandex_client.is_authenticated:
            logger.error("Клиент не авторизован")
            return []
        
        try:
            # Если пришла ссылка на плейлист пользователя, пробуем распарсить
            if isinstance(query, str) and "music.yandex.ru/users/" in query and "/playlists/" in query:
                try:
                    parts = query.split("music.yandex.ru/users/")[-1]
                    uid = parts.split("/playlists/")[0].split("?")[0].split("/")[0]
                    kind = parts.split("/playlists/")[-1].split("?")[0].split("/")[0]
                    playlist_id = f"{uid}:{kind}"
                    logger.info(f"Распознан плейлист по URL: {playlist_id}")
                    # Возвращаем псевдо-список с одним плейлистом
                    return [{
                        'id': playlist_id,
                        'title': f'Плейлист {uid}:{kind}',
                        'track_count': 0,
                        'cover_url': None,
                        'owner': uid
                    }]
                except Exception as parse_err:
                    logger.warning(f"Не удалось распарсить URL плейлиста: {parse_err}")
                    # продолжим обычным поиском как fallback
            
            search_result = await asyncio.get_event_loop().run_in_executor(
                None,
                self.yandex_client.client.search,
                query,
                'playlist',
                limit
            )
            
            playlists = []
            if search_result and search_result.playlists:
                for playlist in search_result.playlists.results:
                    if playlist:
                        playlist_info = {
                            'id': playlist.playlist_id,
                            'title': playlist.title,
                            'track_count': playlist.track_count,
                            'cover_url': f"https://{playlist.cover.uri.replace('%%', '200x200')}" if playlist.cover else None,
                            'owner': playlist.owner.name if playlist.owner else 'Неизвестно'
                        }
                        playlists.append(playlist_info)
            
            return playlists
        except Exception as e:
            logger.error(f"Ошибка поиска плейлистов: {e}")
            return []

    async def get_album_tracks(self, album_id, limit=50):
        """Получение треков из альбома по ID"""
        if not self.yandex_client.is_authenticated:
            logger.error("Клиент не авторизован")
            return []
        try:
            logger.info(f"Получаем треки из альбома {album_id}...")
            # Приводим ID к числу, если возможно
            parsed_id = None
            try:
                parsed_id = int(str(album_id).strip())
            except Exception:
                parsed_id = album_id

            # Основная попытка: одиночный ID
            try:
                albums_res = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.yandex_client.client.albums_with_tracks,
                    parsed_id
                )
            except Exception as primary_err:
                logger.warning(f"albums_with_tracks с одиночным ID не сработал: {primary_err}")
                # Резерв: список ID
                albums_res = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.yandex_client.client.albums_with_tracks,
                    [parsed_id]
                )

            if not albums_res:
                return []

            # Нормализуем ответ: может быть одним объектом Album или списком
            if hasattr(albums_res, 'volumes'):
                album = albums_res
            elif hasattr(albums_res, '__iter__') and not isinstance(albums_res, (str, bytes)):
                album = list(albums_res)[0]
            else:
                album = albums_res

            # album.volumes — список дисков (каждый — список треков)
            volumes = getattr(album, 'volumes', []) or []
            tracks = []
            for disk in volumes:
                for track in disk:
                    if len(tracks) >= limit:
                        break
                    if not track:
                        continue
                    track_info = {
                        'id': track.id,
                        'title': track.title,
                        'artist': ', '.join([a.name for a in (getattr(track, 'artists', None) or [])]) if getattr(track, 'artists', None) else 'Неизвестный исполнитель',
                        'duration': (getattr(track, 'duration_ms', 0) or 0) // 1000,
                        'album': getattr(album, 'title', 'Альбом'),
                        'cover_url': (
                            f"https://{getattr(getattr(album, 'cover', None), 'uri', '').replace('%%', '200x200')}"
                            if getattr(getattr(album, 'cover', None), 'uri', None)
                            else None
                        )
                    }
                    tracks.append(track_info)
                if len(tracks) >= limit:
                    break
            logger.info(f"Получено {len(tracks)} треков из альбома")
            return tracks
        except Exception as e:
            logger.error(f"Ошибка получения альбома: {e}")
            return []
    
    async def get_liked_tracks(self, limit=20):
        """Получение лайкнутых треков из плейлиста 'Мне нравится'"""
        if not self.yandex_client.is_authenticated:
            logger.error("Клиент не авторизован")
            return []
        
        try:
            # Сначала пробуем получить треки через API лайков
            try:
                liked_tracks = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.yandex_client.client.users_likes_tracks
                )
                
                tracks = []
                if liked_tracks and hasattr(liked_tracks, 'tracks') and liked_tracks.tracks:
                    for track_short in liked_tracks.tracks[:limit]:
                        if track_short.track:
                            track = track_short.track
                            track_info = {
                                'id': track.id,
                                'title': track.title,
                                'artist': ', '.join([artist.name for artist in track.artists]),
                                'duration': track.duration_ms // 1000,
                                'album': track.albums[0].title if track.albums else 'Неизвестный альбом',
                                'cover_url': f"https://{track.cover_uri.replace('%%', '200x200')}" if track.cover_uri else None
                            }
                            tracks.append(track_info)
                
                if tracks:
                    logger.info(f"Получено {len(tracks)} треков через API лайков")
                    return tracks
            except Exception as e:
                logger.warning(f"API лайков не сработал: {e}")
            
            # Если API лайков не сработал, ищем плейлист "Мне нравится"
            logger.info("Ищем плейлист 'Мне нравится'...")
            
            # Получаем все плейлисты пользователя
            playlists = await self.yandex_client.get_user_playlists()
            
            liked_playlist_id = None
            if playlists:
                for playlist in playlists:
                    playlist_title = playlist.get('title', '').lower()
                    if 'нравится' in playlist_title or 'liked' in playlist_title or 'favorites' in playlist_title:
                        liked_playlist_id = playlist.get('id')
                        logger.info(f"Найден плейлист 'Мне нравится': {playlist.get('title')} (ID: {liked_playlist_id})")
                        break
            
            if liked_playlist_id:
                # Получаем треки из плейлиста "Мне нравится"
                tracks = await self.get_playlist_tracks(liked_playlist_id, limit)
                if tracks:
                    logger.info(f"Получено {len(tracks)} треков из плейлиста 'Мне нравится'")
                    return tracks
            
            # Если не нашли плейлист "Мне нравится", пробуем другие варианты
            logger.warning("Плейлист 'Мне нравится' не найден, пробуем альтернативы...")
            
            # Ищем плейлисты с похожими названиями
            if playlists:
                for playlist in playlists:
                    playlist_title = playlist.get('title', '').lower()
                    if any(keyword in playlist_title for keyword in ['избранное', 'favorite', 'like', 'любимое']):
                        liked_playlist_id = playlist.get('id')
                        logger.info(f"Найден альтернативный плейлист: {playlist.get('title')} (ID: {liked_playlist_id})")
                        tracks = await self.get_playlist_tracks(liked_playlist_id, limit)
                        if tracks:
                            logger.info(f"Получено {len(tracks)} треков из альтернативного плейлиста")
                            return tracks
            
            logger.warning("Не удалось найти плейлист с лайкнутыми треками")
            return []
                
        except Exception as e:
            logger.error(f"Ошибка получения лайкнутых треков: {e}")
            
        return []
