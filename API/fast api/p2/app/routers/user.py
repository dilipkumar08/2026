from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import user
from app.schemas.user import UserCreate, UserResponse


router=APIRouter(prefix="/users",tags=["Users"])

@router.post("/",response_model=UserResponse,status_code=status.HTTP_201_CREATED)
def create_user(user:UserCreate,db:Session=Depends(get_db)):
    