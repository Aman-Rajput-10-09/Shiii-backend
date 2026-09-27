from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.auth import verify_password, get_password_hash, create_access_token
from app.models.schemas import User, UserRole, Couple
from app.schemas.dto import UserCreate, UserLogin, Token, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserOut)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == user_in.username))
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    user = User(
        username=user_in.username,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
        display_name=user_in.display_name or user_in.username
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == credentials.username))
    user = result.scalars().first()
    
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    is_paired = False
    pair_code = None
    partner_name = None
    if user.couple_id:
        c_res = await db.execute(
            select(Couple)
            .where(Couple.id == user.couple_id)
            .options(selectinload(Couple.master), selectinload(Couple.mistress))
        )
        couple = c_res.scalars().first()
        if couple:
            pair_code = couple.pair_code
            partner = couple.mistress if user.role == UserRole.MASTER else couple.master
            if partner:
                is_paired = True
                partner_name = partner.display_name

    token = create_access_token(data={"sub": user.username, "role": user.role.value})
    return Token(
        access_token=token,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
        display_name=user.display_name,
        couple_id=user.couple_id,
        is_paired=is_paired,
        pair_code=pair_code,
        partner_name=partner_name
    )
