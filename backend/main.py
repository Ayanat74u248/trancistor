from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import yt_dlp
import whisper
import os
import tempfile
from pathlib import Path
import re

# Попробуем импортировать youtube-transcript-api
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    TRANSCRIPT_API_AVAILABLE = True
except ImportError:
    TRANSCRIPT_API_AVAILABLE = False

app = FastAPI()

# Добавляем CORS для работы с frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Абсолютный путь к frontend
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# Обслуживаем статические файлы из frontend по маршруту /static
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")

class TranscribeRequest(BaseModel):
    url: str

# Загружаем модель один раз при запуске
try:
    model = whisper.load_model("base")
except Exception as e:
    print(f"Ошибка загрузки модели: {e}")
    model = None

def extract_video_id(url: str):
    """Извлекает video_id из YouTube ссылки"""
    patterns = [
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
        r'youtu\.be/([a-zA-Z0-9_-]+)',
        r'youtube\.com/embed/([a-zA-Z0-9_-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_transcript_from_api(video_id: str):
    """Пытается получить текст стенограммы из встроенных субтитров YouTube"""
    if not TRANSCRIPT_API_AVAILABLE:
        return None
    
    try:
        print(f"[DEBUG] Пытаюсь получить субтитры YouTube для видео: {video_id}")
        
        # Создаём API объект
        api = YouTubeTranscriptApi()
        
        # Получаем субтитры (по умолчанию на доступном языке)
        try:
            # Пробуем список доступных языков
            transcripts_list = api.list(video_id)
            print(f"[DEBUG] Доступные языки субтитров: {list(transcripts_list.keys())}")
            
            # Приоритет языков
            languages_priority = ['ru', 'en', 'es', 'fr', 'de']
            
            selected_lang = None
            for lang in languages_priority:
                if lang in transcripts_list:
                    selected_lang = lang
                    break
            
            if not selected_lang:
                # Берём первый доступный язык
                selected_lang = list(transcripts_list.keys())[0]
            
            print(f"[DEBUG] Используем язык: {selected_lang}")
            transcript_data = transcripts_list[selected_lang]
            
            # Получаем текст из объектов (используя атрибут .text)
            full_text = " ".join([item.text for item in transcript_data])
            print(f"[DEBUG] Получено {len(full_text)} символов текста из YouTube субтитров")
            return full_text
            
        except:
            # Если list не работает, пробуем fetch
            print(f"[DEBUG] Используем fetch для получения субтитров...")
            transcript_data = api.fetch(video_id)
            
            # Получаем текст из объектов (используя атрибут .text)
            full_text = " ".join([item.text for item in transcript_data])
            print(f"[DEBUG] Получено {len(full_text)} символов текста из YouTube субтитров")
            return full_text
        
    except Exception as e:
        print(f"[DEBUG] Не удалось получить субтитры YouTube: {str(e)}")
        return None

def download_audio(url: str, download_dir: str):
    """Скачивает звук с YouTube видео"""
    try:
        # Проверяем наличие FFmpeg
        import subprocess
        ffmpeg_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",  # Наш установленный FFmpeg
            "ffmpeg.exe",  # В PATH
            "ffmpeg"  # В PATH
        ]
        
        ffmpeg_available = False
        ffmpeg_path = None
        
        for path in ffmpeg_paths:
            try:
                subprocess.run([path, '-version'], capture_output=True, check=True)
                ffmpeg_available = True
                ffmpeg_path = path
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        if not ffmpeg_available:
            raise Exception("FFmpeg не найден. Установите FFmpeg и добавьте в PATH, или поместите ffmpeg.exe в C:\\ffmpeg\\bin")

        # Более агрессивные настройки для YouTube
        ydl_opts = {
            'format': 'm4a/bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best',
            'outtmpl': os.path.join(download_dir, 'audio.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'socket_timeout': 30,
            'skip_unavailable_fragments': True,
            'noplaylist': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            'check_certificates': False,
            'extract_flat': False,
            'allow_multiple_video_resolutions': True,
        }
        
        print(f"[DEBUG] Скачиваем видео: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("[DEBUG] Извлекаем информацию о видео...")
            info = ydl.extract_info(url, download=True)
            print(f"[DEBUG] Видео скачано: {info.get('title', 'Unknown')}")

        files = os.listdir(download_dir)

        priority_formats = ['.m4a', '.mp3', '.wav', '.webm', '.ogg', '.opus', '.aac', '.flac']

        for ext in priority_formats:
            for file in files:
                if file.startswith("audio") and file.endswith(ext):
                    audio_path = os.path.join(download_dir, file)
                    file_size = os.path.getsize(audio_path)
                    print(f"[DEBUG] Найден аудиофайл: {audio_path} ({file_size} bytes)")
                    return audio_path

        # Если не найдены приоритетные форматы, берём первый подходящий
        for file in files:
            if file.startswith("audio"):
                audio_path = os.path.join(download_dir, file)
                file_size = os.path.getsize(audio_path)
                print(f"[DEBUG] Используем файл: {audio_path} ({file_size} bytes)")
                return audio_path

        raise Exception("Не удалось найти скачанный аудиофайл. Файлы: " + str(files))
    except Exception as e:
        error_msg = f"Ошибка скачивания: {str(e)}"
        print(f"[ERROR] {error_msg}")
        raise Exception(error_msg)

@app.get("/")
def read_root():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.post("/transcribe")
def transcribe(req: TranscribeRequest):
    """Транскрибирует видео с YouTube"""
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="URL не может быть пустой")
    
    if "youtube.com" not in req.url and "youtu.be" not in req.url:
        raise HTTPException(status_code=400, detail="Это не YouTube ссылка")
    
    # Извлекаем video_id
    video_id = extract_video_id(req.url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Не удалось извлечь ID видео из ссылки")
    
    # Сначала пробуем получить встроенные субтитры YouTube
    print(f"\n[INFO] === Начинаем обработку видео: {req.url} ===")
    text = get_transcript_from_api(video_id)
    language = "youtube_subtitle"
    
    # Если встроенных субтитров нет, используем Whisper
    if text is None:
        if model is None:
            raise HTTPException(status_code=500, detail="Модель не загружена и нет встроенных субтитров")
        
        # Создаём временную директорию для каждого запроса
        temp_dir = tempfile.mkdtemp()
        audio_file = None
        
        try:
            # Скачиваем аудио
            audio_file = download_audio(req.url, temp_dir)
            if not audio_file:
                raise Exception("Не удалось скачать аудио")
            
            # Транскрибируем
            print("[DEBUG] Начинаем транскрипцию Whisper...")
            result = model.transcribe(audio_file)
            text = result.get("text", "").strip()
            language = result.get("language", "unknown")
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")
        
        finally:
            # Очищаем временные файлы
            try:
                for file in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                os.rmdir(temp_dir)
            except:
                pass
    
    if not text:
        raise HTTPException(status_code=500, detail="Не удалось получить текст из видео")
    
    print(f"[INFO] === Обработка завершена. Получено {len(text)} символов ===\n")
    
    return {
        "status": "success",
        "text": text,
        "language": language
    }