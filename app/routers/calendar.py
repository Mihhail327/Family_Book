from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select, extract, desc  # Добавь desc сюда
from app.database import get_session  
from app.models import Post
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")
router = APIRouter()

@router.get("/calendar/day-posts")
async def get_posts_by_day(
    day: int, month: int, year: int, 
    request: Request, 
    session: Session = Depends(get_session)
):
    # Теперь линтер будет доволен, так как мы вызываем функцию desc()
    statement = (
        select(Post)
        .where(
            extract('day', Post.created_at) == day,
            extract('month', Post.created_at) == month,
            extract('year', Post.created_at) == year
        )
        .order_by(desc(Post.created_at)) # Используем desc(Post.created_at)
    )
    
    posts = session.exec(statement).all()
    
    return templates.TemplateResponse(
        "includes/_calendar_posts.html", 
        {"request": request, "posts": posts, "selected_date": f"{day}.{month}.{year}"}
    )