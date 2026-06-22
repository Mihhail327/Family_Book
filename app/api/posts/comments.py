from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Form, Request, HTTPException, Response
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlmodel import Session

from app.database import get_session
from app.models import Comment, Post, User
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
    user_id: Optional[int] = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    post = session.get(Post, post_id)
    if not post:
        return HTMLResponse("<div class='p-4 text-slate-500 text-sm'>Пост не найден</div>")
    
    user = session.get(User, user_id) if user_id else None
    
    # 🟢 HTMX всегда просит фрагмент. 
    # Если зайти просто браузером, мы тоже отдадим этот фрагмент (это ок для отладки)
    return templates.TemplateResponse(
        request=request,
        name="includes/_comments_list.html",
        context={"post": post, "user": user}
    )

@router.post("/posts/{post_id}/comment")
async def create_comment(
    post_id: int,
    request: Request,
    content: str = Form(...),
    parent_id: Optional[int] = Form(None),
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

        # Валидируем parent_id, если он указан
        if parent_id:
            parent_comment = session.get(Comment, parent_id)
            if not parent_comment or parent_comment.post_id != post_id:
                raise HTTPException(status_code=400, detail="Некорректный родительский комментарий")

        new_comment = Comment(
            content=safe_content,
            post_id=post_id,
            author_id=user_id,
            parent_id=parent_id,
            created_at=datetime.now(timezone.utc)
        )
        session.add(new_comment)
        session.commit()
        
        # 🟢 МАГИЯ HTMX: Если запрос пришел от HTMX, не редиректим!
        if request.headers.get("HX-Request"):
            session.refresh(new_comment) 
            post = session.get(Post, post_id)
            user = session.get(User, user_id) if user_id else None
            return templates.TemplateResponse(
                request=request,
                name="includes/_comments_list.html", 
                context={"post": post, "user": user}
            )
            
        flash(response, "Комментарий добавлен", "success")
        
    except HTTPException as he:
        flash(response, he.detail, "error")
    except Exception as e:
        log_error("COMMENT_ERR", str(e))
        flash(response, "Ошибка при добавлении комментария", "error")

    return response

@router.delete("/posts/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    user_id: int = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if not user_id:
        raise HTTPException(status_code=401, detail="Необходимо авторизоваться")
    
    comment = session.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Комментарий не найден")
    
    from app.models import User
    user = session.get(User, user_id)
    post = session.get(Post, comment.post_id)
    
    is_admin = getattr(user, "role", "") == "admin"
    is_comment_author = comment.author_id == user_id
    is_post_author = post and post.author_id == user_id
    
    if not (is_comment_author or is_post_author or is_admin):
        raise HTTPException(status_code=403, detail="У вас нет прав для удаления этого комментария")
    
    session.delete(comment)
    session.commit()
    return Response(status_code=200)