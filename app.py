import asyncio
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Depends
from schemas import PostResponse, UserRead, UserCreate, UserUpdate
from db import Post, create_db_and_tables, get_async_session, User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from contextlib import asynccontextmanager
from sqlalchemy import select
from images import imagekit
import shutil
import os
import uuid
import tempfile
from users import auth_backend, current_active_user, fastapi_users


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fastapi_users.get_auth_router(auth_backend), prefix='/auth/jwt', tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_reset_password_router(), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_verify_router(UserRead), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"])

@app.post("/upload", response_model=PostResponse)
async def upload_file(
        file: UploadFile = File(...),
        caption: str = Form(""),
        user: User = Depends(current_active_user),
        session: AsyncSession = Depends(get_async_session)
        ):
    temp_file_path = None
    try:
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)

        def upload_to_imagekit_sync():
            with open(temp_file_path, "rb") as f:
                return imagekit.files.upload(
                    file=f,
                    file_name=file.filename,
                    use_unique_file_name=True,
                    tags=["backend-upload"]
                )

        upload_result = await asyncio.to_thread(upload_to_imagekit_sync)

        post = Post(
            user_id=str(user.id),
            caption=caption,
            url=upload_result.url,
            file_type="video" if file.content_type.startswith("video/") else "image",
            file_name=upload_result.name
        )

        session.add(post)
        await session.commit()
        await session.refresh(post)

        return PostResponse(
            id=str(post.id),
            user_id=str(post.user_id),
            caption=post.caption,
            url=post.url,
            file_type=post.file_type,
            file_name=post.file_name,
            created_at=post.created_at.isoformat(),
            is_owner=True,
            email=user.email
        )

    except Exception as e:
        print(f"Error during upload: {e}") # Helpful for debugging
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)



@app.get("/feed")
async def get_feed(
        session: AsyncSession = Depends(get_async_session),
        user: User = Depends(current_active_user),
        ):
    stmt = select(Post).options(joinedload(Post.user)).order_by(Post.created_at.desc())
    result = await session.execute(stmt)
    posts = result.scalars().all()

    posts_data = []
    for post in posts:
        posts_data.append({
            "id": post.id,
            "user_id": post.user_id,
            "caption": post.caption,
            "url": post.url,
            "file_type": post.file_type,
            "file_name": post.file_name,
            "created_at": post.created_at.isoformat(),
            "is_owner": post.user_id == str(user.id),
            "email": post.user.email  
        })

    return {"posts": posts_data}


@app.delete("/posts/{post_id}")
async def delete_post(post_id: str, session: AsyncSession = Depends(get_async_session), user: User = Depends(current_active_user)):
    try:
        try:
            uuid_obj = uuid.UUID(post_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid post ID")

        result = await session.execute(select(Post).where(Post.id == post_id))
        post = result.scalars().first()

        if not post:
            raise HTTPException(status_code=404, detail="Post not found")

        if post.user_id != str(user.id):
            raise HTTPException(status_code=403, detail="You don't have permission to delete this post")

        await session.delete(post)
        await session.commit()

        return {"success": True, "message": "Post deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))