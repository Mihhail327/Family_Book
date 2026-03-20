import os
from PIL import Image, ImageOps
from typing import Optional, Union, BinaryIO
from app.logger import log_error

def process_and_save_image(
    source_file: Union[BinaryIO, str], 
    target_path: str, 
    max_size=(2560, 1440), 
    quality=85 
) -> Optional[str]:
    """
    Профессиональная обработка: EXIF, сохранение альфа-канала, сжатие в WebP.
    """
    try:
        with Image.open(source_file) as img:
            # 1. Исправляем ориентацию (чтобы фото с телефонов не лежали на боку)
            img = ImageOps.exif_transpose(img)
            
            # 2. Умная конвертация (WebP поддерживает прозрачность!)
            # Если картинка с прозрачностью, переводим в чистый RGBA.
            # Всю экзотику (CMYK, LAB) конвертируем в стандартный RGB.
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                img = img.convert("RGBA")
            elif img.mode != "RGB":
                img = img.convert("RGB")
            
            # 3. Уменьшение размера с сохранением деталей (Lanczos)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # 4. Формируем путь
            target_path_webp = os.path.splitext(target_path)[0] + ".webp"
            
            # 5. Сохранение
            # method=4 — золотой стандарт для серверов (быстро и компактно)
            img.save(
                target_path_webp, 
                "WEBP", 
                quality=quality, 
                optimize=True, 
                method=4 
            )
            
            return target_path_webp
            
    except Exception as e:
        log_error("IMAGE_PROCESSING_ERROR", f"Файл {target_path}: {str(e)}")
        return None