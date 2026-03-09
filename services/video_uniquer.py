import asyncio
import logging
import os
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional
import ffmpeg
from core.config import settings

logger = logging.getLogger(__name__)


class VideoUniquer:
    """Сервис для уникализации видео с помощью FFmpeg."""

    def __init__(self):
        self.input_path = settings.input_path
        self.output_path = settings.output_path
        self.ffmpeg_path = settings.FFMPEG_PATH

    def _generate_output_filename(self, input_filename: str) -> str:
        """Генерация уникального имени выходного файла."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        name, ext = os.path.splitext(input_filename)
        return f"{name}_unique_{timestamp}_{unique_id}{ext}"

    def _apply_video_filters(self, input_file: Path, output_file: Path) -> bool:
        """
        Применение фильтров для уникализации видео.
        """
        try:
            # Генерация случайных параметров для уникализации
            brightness = 0.02
            contrast = 1.02
            saturation = 1.05
            noise_strength = 20
            speed = 1.0

            # Построение цепочки фильтров (правильный синтаксис для ffmpeg-python)
            video_filters = (
                f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation},"
                f"noise=alls={noise_strength}:allf=t+u"
            )

            # Запуск FFmpeg через subprocess (прямой вызов)
            import subprocess
            
            # Полный filter_complex включает все видео фильтры
            filter_complex = (
                f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation},"
                f"noise=alls={noise_strength}:allf=t+u,"
                f"setpts={1/speed}*PTS"
            )
            
            cmd = [
                self.ffmpeg_path,
                "-i", str(input_file),
                "-filter_complex", filter_complex,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                "-y",  # overwrite output
                str(output_file)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                return False

            logger.info(f"Видео успешно обработано: {output_file}")
            return True

        except Exception as e:
            logger.exception(f"Неожиданная ошибка при обработке видео: {e}")
            return False

    def _apply_audio_filters(self, input_file: Path, output_file: Path) -> bool:
        """
        Применение фильтров для уникализации аудио.

        Фильтры:
        - Небольшое изменение высоты тона
        - Небольшое изменение темпа
        """
        try:
            # Параметры для аудио
            pitch = 1.02  # Изменение высоты тона
            tempo = 1.0   # Темп (оставляем без изменений для синхронизации)

            (
                ffmpeg
                .input(str(input_file))
                .audio
                .filter_("asetrate", 44100 * pitch)
                .filter_("atempo", 1/pitch * tempo)
                .output(
                    str(output_file),
                    **{"c:a": "aac", "b:a": "128k"}
                )
                .overwrite_output()
                .run(
                    cmd=self.ffmpeg_path,
                    capture_stdout=True,
                    capture_stderr=True,
                )
            )

            return True

        except ffmpeg.Error as e:
            logger.error(f"Ошибка FFmpeg при обработке аудио: {e.stderr.decode() if e.stderr else e}")
            return False
        except Exception as e:
            logger.exception(f"Неожиданная ошибка при обработке аудио: {e}")
            return False

    async def process(
        self,
        input_file_path: Path,
        output_filename: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Обработка видео для уникализации.

        Args:
            input_file_path: Путь к входному файлу.
            output_filename: Имя выходного файла (опционально).

        Returns:
            Путь к обработанному файлу или None при ошибке.
        """
        input_file = Path(input_file_path)

        if not input_file.exists():
            logger.error(f"Входной файл не найден: {input_file}")
            return None

        # Генерация имени выходного файла
        if output_filename is None:
            output_filename = self._generate_output_filename(input_file.name)

        output_file = self.output_path / output_filename

        # Создаём выходную директорию если не существует
        self.output_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Начало обработки: {input_file} -> {output_file}")

        # Запуск обработки в отдельном потоке (FFmpeg блокирующий)
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(
            None,
            self._apply_video_filters,
            input_file,
            output_file,
        )

        if success and output_file.exists():
            logger.info(f"Обработка завершена: {output_file}")
            return output_file
        else:
            logger.error(f"Обработка не удалась: {input_file}")
            return None

    def cleanup_input_file(self, file_path: Path):
        """Удаление входного файла после обработки."""
        try:
            if file_path and file_path.exists():
                file_path.unlink()
                logger.info(f"Входной файл удалён: {file_path}")
        except Exception as e:
            logger.error(f"Ошибка при удалении файла {file_path}: {e}")


# Глобальный экземпляр
video_uniquer = VideoUniquer()
