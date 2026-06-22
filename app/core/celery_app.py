import os
from celery import Celery
from app.config import settings
from app.utils.images import process_and_save_image

# Инициализируем инстанс Celery
celery_instance = Celery(
    "family_book",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

# Поддержка eager режима для тестов
if settings.ENV == "testing":
    celery_instance.conf.update(
        task_always_eager=True,
        task_eager_propagates=True
    )

@celery_instance.task(name="process_image_task")
def process_image_task(temp_file_path: str, target_file_path: str):
    """
    Фоновое сжатие картинки.
    Берет картинку из temp_file_path, пережимает в target_file_path через process_and_save_image,
    после чего удаляет исходный временный файл.
    """
    try:
        if not os.path.exists(temp_file_path):
            from app.logger import log_error
            log_error("CELERY_IMAGE_TASK_ERR", f"Временный файл не найден: {temp_file_path}")
            return
        
        # Сжимаем и сохраняем картинку
        success = process_and_save_image(temp_file_path, target_file_path)
        if not success:
            from app.logger import log_error
            log_error("CELERY_IMAGE_TASK_ERR", f"Не удалось обработать изображение: {temp_file_path}")
            
    except Exception as e:
        from app.logger import log_error
        log_error("CELERY_IMAGE_TASK_ERR", f"Ошибка обработки: {str(e)}")
    finally:
        # Всегда удаляем временный файл, чтобы не засорять диск
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                from app.logger import log_error
                log_error("CELERY_TEMP_DEL_ERR", f"Не удалось удалить временный файл {temp_file_path}: {e}")
