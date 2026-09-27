import secrets
import string
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.schemas import User, UserRole, Couple
from app.schemas.dto import CoupleStatusOut, PairRequest, PairResponse

router = APIRouter(prefix="/couple", tags=["couple"])

def _generate_pair_code() -> str:
    alphabet = string.ascii_uppercase + "23456789" # avoid confusing 0/O, 1/I
    suffix = "".join(secrets.choice(alphabet) for _ in range(4))
    return f"SHIII-{suffix}"

@router.get("/status", response_model=CoupleStatusOut)
async def get_couple_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user's pairing status.
    If no couple exists yet, generates a unique pending couple with pair_code.
    """
    couple: Couple | None = None
    
    if current_user.couple_id:
        result = await db.execute(
            select(Couple)
            .where(Couple.id == current_user.couple_id)
            .options(selectinload(Couple.master), selectinload(Couple.mistress))
        )
        couple = result.scalars().first()

    if not couple:
        # Check if an existing couple has this user as master or mistress
        if current_user.role == UserRole.MASTER:
            res = await db.execute(select(Couple).where(Couple.master_id == current_user.id))
        else:
            res = await db.execute(select(Couple).where(Couple.mistress_id == current_user.id))
        couple = res.scalars().first()

    if not couple:
        # Auto-create a pending couple code for this user
        new_code = _generate_pair_code()
        # Ensure code uniqueness
        while True:
            existing = await db.execute(select(Couple).where(Couple.pair_code == new_code))
            if not existing.scalars().first():
                break
            new_code = _generate_pair_code()

        couple = Couple(
            pair_code=new_code,
            master_id=current_user.id if current_user.role == UserRole.MASTER else None,
            mistress_id=current_user.id if current_user.role == UserRole.MISTRESS else None
        )
        db.add(couple)
        await db.flush()
        current_user.couple_id = couple.id
        await db.commit()

    # Re-fetch with relationships loaded
    result = await db.execute(
        select(Couple)
        .where(Couple.id == couple.id)
        .options(selectinload(Couple.master), selectinload(Couple.mistress))
    )
    couple = result.scalars().first()

    # Determine partner
    partner: User | None = None
    if current_user.role == UserRole.MASTER:
        partner = couple.mistress if couple else None
    else:
        partner = couple.master if couple else None

    is_paired = partner is not None

    return CoupleStatusOut(
        is_paired=is_paired,
        pair_code=couple.pair_code if couple else "",
        partner_name=partner.display_name if partner else None,
        partner_role=partner.role.value if partner else None,
        couple_id=couple.id if couple else None
    )

@router.post("/pair", response_model=PairResponse)
async def pair_with_partner(
    req: PairRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Connect with a partner using their invite code.
    Requires one partner to be MASTER and one to be MISTRESS.
    """
    code = req.pair_code.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Please enter a valid pair code")

    result = await db.execute(
        select(Couple)
        .where(Couple.pair_code == code)
        .options(selectinload(Couple.master), selectinload(Couple.mistress))
    )
    target_couple = result.scalars().first()
    if not target_couple:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pair code not found. Please check with your partner!"
        )

    # Check if this is user's own code
    if (current_user.role == UserRole.MASTER and target_couple.master_id == current_user.id) or \
       (current_user.role == UserRole.MISTRESS and target_couple.mistress_id == current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This is your own code! Share it with your partner so they can join you."
        )

    partner: User | None = None

    if current_user.role == UserRole.MASTER:
        # User is Master, so the code creator must be Mistress
        if target_couple.master_id is not None and target_couple.master_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This couple already has a Master paired."
            )
        if target_couple.mistress_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The code creator is also registered as Master. A couple needs one Master and one Mistress!"
            )
        target_couple.master_id = current_user.id
        partner = target_couple.mistress
    else:
        # User is Mistress, so the code creator must be Master
        if target_couple.mistress_id is not None and target_couple.mistress_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This couple already has a Mistress paired."
            )
        if target_couple.master_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The code creator is also registered as Mistress. A couple needs one Master and one Mistress!"
            )
        target_couple.mistress_id = current_user.id
        partner = target_couple.master

    # Clean up any empty previous couple that belonged solely to current_user
    old_couple_id = current_user.couple_id
    current_user.couple_id = target_couple.id

    if old_couple_id and old_couple_id != target_couple.id:
        old_res = await db.execute(select(Couple).where(Couple.id == old_couple_id))
        old_couple = old_res.scalars().first()
        if old_couple:
            # If old couple has no other members, remove it
            if (old_couple.master_id == current_user.id and old_couple.mistress_id is None) or \
               (old_couple.mistress_id == current_user.id and old_couple.master_id is None):
                await db.delete(old_couple)

    await db.commit()

    partner_name = partner.display_name if partner else "Partner"
    return PairResponse(
        success=True,
        message=f"You and {partner_name} are now linked in love through Shiii! 💕",
        partner_name=partner_name,
        couple_id=target_couple.id
    )
