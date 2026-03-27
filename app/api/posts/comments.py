from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlmodel import Session

from app.database import get_session
from app.models import Comment, Post
from app.security import get_current_user, validate_security_input
from app.logger import log_error
from app.utils.flash import flash
# Убедись, что импортировал templates
from app.core.templates import templates 

router = APIRouter()

# 🟢 НОВЫЙ РОУТ: Отдает только HTML комментариев для HTMX (выезжающая панель)
@router.get("/posts/{post_id}/comments", response_class=HTMLResponse)
async def load_comments(
    post_id: int, 
    request: Request, 
    session: Session = Depends(get_session)
):
    post = session.get(Post, post_id)
    if not post:
        return HTMLResponse("<div class='p-4 text-slate-500 text-sm'>Пост не найден</div>")
    
    # 🟢 HTMX всегда просит фрагмент. 
    # Если зайти просто браузером, мы тоже отдадим этот фрагмент (это ок для отладки)
    return templates.TemplateResponse(
        request=request,
        name="includes/_comments_list.html",
        context={"post": post}
    )

@router.post("/posts/{post_id}/comment")
async def create_comment(
    post_id: int,
    request: Request,
    content: str = Form(...),
    user_id: int = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if not user_id:
        raise HTTPException(status_code=401, detail="Необходимо авторизоваться")

    clean_content = content.strip()
    
    # Подготавливаем базовый редирект для обычных браузеров
    response = RedirectResponse(url=f"/posts/{post_id}", status_code=303)

    if not clean_content:
        flash(response, "Нельзя оставить пустой комментарий", "info")
        return response

    try:
        safe_content = validate_security_input(clean_content)

        new_comment = Comment(
            content=safe_content,
            post_id=post_id,
            author_id=user_id,
            created_at=datetime.now(timezone.utc)
        )
        session.add(new_comment)
        session.commit()
        
        # 🟢 МАГИЯ HTMX: Если запрос пришел от HTMX, не редиректим!
        if request.headers.get("HX-Request"):
            session.refresh(new_comment) 
            post = session.get(Post, post_id)
            return templates.TemplateResponse(
                request=request,
                name="includes/_comments_list.html", 
                context={"post": post}
            )
            
        flash(response, "Комментарий добавлен", "success")
        
    except HTTPException as he:
        flash(response, he.detail, "error")
    except Exception as e:
        log_error("COMMENT_ERR", str(e))
        flash(response, "Ошибка при добавлении комментария", "error")

    return response