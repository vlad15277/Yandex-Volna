# Установка FFmpeg

FFmpeg необходим для воспроизведения аудио в Discord боте.

## Windows

### Способ 1: Скачивание с официального сайта

1. Перейдите на [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
2. Нажмите на "Windows" в разделе "Get packages & executable files"
3. Выберите "Windows builds by BtbN"
4. Скачайте последнюю версию (например, `ffmpeg-master-latest-win64-gpl.zip`)
5. Распакуйте архив в папку (например, `C:\ffmpeg`)
6. Добавьте `C:\ffmpeg\bin` в переменную PATH:
   - Откройте "Параметры системы" → "Дополнительные параметры системы"
   - Нажмите "Переменные среды"
   - В разделе "Системные переменные" найдите "Path" и нажмите "Изменить"
   - Нажмите "Создать" и добавьте `C:\ffmpeg\bin`
   - Нажмите "ОК" во всех окнах

### Способ 2: Через Chocolatey

```powershell
# Установите Chocolatey (если не установлен)
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Установите FFmpeg
choco install ffmpeg
```

### Способ 3: Через Scoop

```powershell
# Установите Scoop (если не установлен)
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
irm get.scoop.sh | iex

# Установите FFmpeg
scoop install ffmpeg
```

## Linux

### Ubuntu/Debian

```bash
sudo apt update
sudo apt install ffmpeg
```

### CentOS/RHEL/Fedora

```bash
# CentOS/RHEL
sudo yum install ffmpeg

# Fedora
sudo dnf install ffmpeg
```

### Arch Linux

```bash
sudo pacman -S ffmpeg
```

## macOS

### Через Homebrew

```bash
# Установите Homebrew (если не установлен)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Установите FFmpeg
brew install ffmpeg
```

### Через MacPorts

```bash
sudo port install ffmpeg
```

## Проверка установки

После установки FFmpeg проверьте, что он работает:

```bash
ffmpeg -version
```

Вы должны увидеть информацию о версии FFmpeg.

## Устранение проблем

### Windows: "ffmpeg не является внутренней или внешней командой"

Это означает, что FFmpeg не добавлен в PATH. Убедитесь, что:
1. FFmpeg установлен в правильную папку
2. Путь к папке `bin` добавлен в переменную PATH
3. Перезапустите командную строку после изменения PATH

### Linux/macOS: "command not found"

Убедитесь, что FFmpeg установлен правильно:

```bash
which ffmpeg
```

Если команда не найдена, переустановите FFmpeg согласно инструкциям выше.

## Альтернативные варианты

Если у вас проблемы с установкой FFmpeg, вы можете:

1. Использовать Docker с предустановленным FFmpeg
2. Скачать статическую сборку FFmpeg
3. Использовать онлайн-сервисы для конвертации аудио

## Поддержка

Если у вас возникли проблемы с установкой FFmpeg, обратитесь к:
- [Официальной документации FFmpeg](https://ffmpeg.org/documentation.html)
- [Вики FFmpeg](https://trac.ffmpeg.org/wiki)
- Форумам сообщества FFmpeg
