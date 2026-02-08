import os
from PIL import Image, ImageOps
from typing import Optional, Union, BinaryIO
from app.logger import log_error # Используем твой логгер для солидности

def process_and_save_image(
    source_file: Union[BinaryIO, str], 
    target_path: str, 
    # Увеличим max_size до 2560 (QHD), так как при 20МБ исходнике 
    # 1920 может показаться маловато для больших экранов
    max_size=(2560, 1440), 
    quality=85 # 85 — золотая середина для WebP
) -> Optional[str]:
    """
    Профессиональная обработка: EXIF, RGB-конвертация, сжатие в WebP.
    """
    try:
        with Image.open(source_file) as img:
            # 1. Исправляем ориентацию (чтобы фото не лежали на боку)
            img = ImageOps.exif_transpose(img)
            
            # 2. Обработка прозрачности (RGBA -> RGB)
            # Если оставить как есть, при конвертации в RGB прозрачный фон станет черным.
            # Мы сделаем его белым — это выглядит аккуратнее.
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                background = Image.new("RGB", img.size, (255, 255, 255))
                # Накладываем изображение на белый фон, используя альфа-канал как маску
                background.paste(img, mask=img.convert("RGBA").split()[3]) 
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
            
            # 3. Уменьшение размера с сохранением деталей
            # LANCZOS идеален для уменьшения тяжелых файлов.
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # 4. Формируем путь (всегда .webp)
            target_path_webp = os.path.splitext(target_path)[0] + ".webp"
            
            # 5. Сохранение
            # method=6 — это максимальное сжатие WebP (дольше обрабатывает, но файл меньше)
            img.save(
                target_path_webp, 
                "WEBP", 
                quality=quality, 
                optimize=True, 
                method=6 
            )
            
            return target_path_webp
            
    except Exception as e:
        log_error("IMAGE_PROCESSING_ERROR", f"Файл {target_path}: {str(e)}")
        return None