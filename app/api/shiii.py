import asyncio
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.schemas import User, UserRole, Couple, ChatMessage, CoupleConcern, ConcernStatus, CoupleGroupMessage, CoupleDirectMessage
from app.schemas.dto import (
    ChatRequest, ChatResponse, ChatMessageOut, ConcernBriefingOut, 
    MasterResolutionRequest, MasterResolutionResponse,
    TTSRequest, TTSResponse,
    GroupMessageOut, GroupChatRequest,
    DirectMessageRequest, DirectMessageOut, MarkReadResponse
)
from app.services.llm_service import llm_service
from app.services.voice_service import voice_service
from app.services.ranking_service import ranking_service

router = APIRouter(prefix="/shiii", tags=["shiii"])

@router.post("/tts", response_model=TTSResponse)
async def synthesize_voice(
    req: TTSRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Synthesize any text into Shiii's signature cute anime voice (en-US-AnaNeural)
    ensuring 100% voice frequency parity between Master and Mistress.
    """
    audio_url, visemes = await voice_service.synthesize(req.text)
    return TTSResponse(audio_url=audio_url, visemes=visemes)

@router.post("/chat", response_model=ChatResponse)
async def chat_with_shiii(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Main dialogue endpoint:
    - If user is Mistress: Shiii responds diplomatically, comforts her, records concern for Master briefing.
    - If user is Master: Shiii provides loyal encouragement, companionship, and relationship updates.
    Optimized for ultra-low latency with parallel LLM execution and bilingual Hinglish/English support.
    """
    user_msg = ChatMessage(
        user_id=current_user.id,
        sender_role=current_user.role.value,
        content=req.message
    )
    db.add(user_msg)
    await db.commit()

    # Find partner if paired
    partner_name: str | None = None
    if current_user.couple_id:
        c_res = await db.execute(
            select(Couple)
            .where(Couple.id == current_user.couple_id)
            .options(selectinload(Couple.master), selectinload(Couple.mistress))
        )
        couple = c_res.scalars().first()
        if couple:
            if current_user.role == UserRole.MASTER and couple.mistress:
                partner_name = couple.mistress.display_name
            elif current_user.role == UserRole.MISTRESS and couple.master:
                partner_name = couple.master.display_name

    context = await ranking_service.get_ranked_context(db, req.message, current_user.couple_id)

    if current_user.role == UserRole.MISTRESS:
        if current_user.couple_id:
            # Parallel execution of companion chat and master briefing cuts latency in half!
            (reply_text, english_text), briefing_text = await asyncio.gather(
                llm_service.chat_with_mistress(req.message, context),
                llm_service.generate_master_briefing(req.message)
            )
            concern = CoupleConcern(
                couple_id=current_user.couple_id,
                author_id=current_user.id,
                author_role=UserRole.MISTRESS,
                original_mistress_text=req.message,
                master_briefing=briefing_text,
                audio_path=None,
                status=ConcernStatus.PENDING,
                urgency_score=1.5
            )
            db.add(concern)
            await db.commit()
        else:
            reply_text, english_text = await llm_service.chat_with_mistress(req.message, context)
    else:
        # Master chatting with Shiii
        concerns = await ranking_service.get_unresolved_concerns(db, current_user.couple_id)
        reply_text, english_text = await llm_service.chat_with_master(req.message, partner_name=partner_name, context=context)
        if concerns and ("mistress" in req.message.lower() or "how is" in req.message.lower()):
            top_concern = concerns[0]
            extra = f"\n\nMaster! Also, Mistress felt a little concerned recently: '{top_concern.master_briefing}'."
            reply_text += extra
            english_text += extra

    # Synthesize cute girl voice & lip-sync visemes
    audio_url, visemes = await voice_service.synthesize(english_text or reply_text)

    # Save Shiii response to history
    shiii_msg = ChatMessage(
        user_id=current_user.id,
        sender_role="shiii",
        content=reply_text,
        english_content=english_text,
        audio_path=audio_url
    )
    db.add(shiii_msg)
    await db.commit()
    await db.refresh(shiii_msg)

    return ChatResponse(
        id=shiii_msg.id,
        reply_text=reply_text,
        english_text=english_text,
        audio_url=audio_url,
        visemes=visemes,
        sender_role="shiii",
        created_at=datetime.now(timezone.utc)
    )

@router.get("/master/briefings", response_model=List[ConcernBriefingOut])
async def get_master_briefings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetched by Master to view active concerns from his Mistress.
    """
    if current_user.role != UserRole.MASTER:
        raise HTTPException(status_code=403, detail="Only Master can access briefings")
        
    concerns = await ranking_service.get_unresolved_concerns(db, current_user.couple_id)
    out_list = []
    updated = False
    for c in concerns:
        audio_url = c.audio_path
        if not audio_url and c.master_briefing:
            audio_url, _ = await voice_service.synthesize(c.master_briefing)
            c.audio_path = audio_url
            updated = True
        out_list.append(ConcernBriefingOut(
            id=c.id,
            original_mistress_text=c.original_mistress_text,
            emotional_sentiment=c.emotional_sentiment,
            urgency_score=c.urgency_score,
            master_briefing=c.master_briefing,
            audio_path=audio_url,
            audio_url=audio_url,
            status=c.status,
            created_at=c.created_at
        ))
    if updated:
        await db.commit()
    return out_list

@router.post("/master/resolve", response_model=MasterResolutionResponse)
async def resolve_concern_by_master(
    req: MasterResolutionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Master sends a reply to resolve Mistress's concern.
    Shiii translates it diplomatically with voice and queues it for Mistress.
    """
    if current_user.role != UserRole.MASTER:
        raise HTTPException(status_code=403, detail="Only Master can resolve briefings")
        
    result = await db.execute(select(CoupleConcern).where(CoupleConcern.id == req.concern_id))
    concern = result.scalars().first()
    if not concern:
        raise HTTPException(status_code=404, detail="Concern not found")

    # Scoping check
    if current_user.couple_id and concern.couple_id and concern.couple_id != current_user.couple_id:
        raise HTTPException(status_code=403, detail="You do not have permission to resolve this concern")
        
    # Translate Master's response into Shiii's sweet words
    sweet_message, sweet_english = await llm_service.translate_master_to_mistress(
        master_reply=req.master_reply,
        original_concern=concern.original_mistress_text
    )
    
    # Synthesize voice for Mistress
    audio_url, _ = await voice_service.synthesize(sweet_english or sweet_message)
    
    concern.master_response = req.master_reply
    concern.diplomatic_resolution_to_mistress = sweet_message
    concern.status = ConcernStatus.RESOLVED
    concern.resolved_at = datetime.now(timezone.utc)

    # Determine author / mistress ID to deliver resolution to
    target_mistress_id = concern.author_id
    if not target_mistress_id and concern.couple_id:
        c_res = await db.execute(select(Couple).where(Couple.id == concern.couple_id))
        couple = c_res.scalars().first()
        if couple and couple.mistress_id:
            target_mistress_id = couple.mistress_id
    elif not target_mistress_id and current_user.couple_id:
        c_res = await db.execute(select(Couple).where(Couple.id == current_user.couple_id))
        couple = c_res.scalars().first()
        if couple and couple.mistress_id:
            target_mistress_id = couple.mistress_id

    # If mistress is found, add resolution to mistress message history as Shiii message
    if target_mistress_id:
        resolution_chat = ChatMessage(
            user_id=target_mistress_id,
            sender_role="shiii",
            content=f"💕 Sweet update from Master! {sweet_message}",
            english_content=f"Sweet update from Master! {sweet_english}",
            audio_path=audio_url
        )
        db.add(resolution_chat)

    await db.commit()
    
    return MasterResolutionResponse(
        success=True,
        diplomatic_message_for_mistress=sweet_message,
        audio_url=audio_url
    )

@router.get("/messages", response_model=List[ChatMessageOut])
async def get_chat_messages(
    after_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Real-time polling endpoint:
    Returns chat messages for current user (Mistress or Master).
    If after_id is provided, returns only messages newer than after_id.
    """
    query = select(ChatMessage).where(ChatMessage.user_id == current_user.id)
    if after_id is not None and after_id > 0:
        query = query.where(ChatMessage.id > after_id).order_by(ChatMessage.id.asc())
    else:
        query = query.order_by(ChatMessage.id.desc()).limit(100)

    result = await db.execute(query)
    messages = list(result.scalars().all())
    if after_id is None or after_id <= 0:
        messages.reverse()

    out: List[ChatMessageOut] = []
    for msg in messages:
        visemes = []
        if msg.audio_path:
            word_count = len(msg.content.split())
            estimated_duration = max(1.0, (word_count / 140.0) * 60.0)
            visemes = voice_service._estimate_visemes(msg.content, estimated_duration)

        out.append(ChatMessageOut(
            id=msg.id,
            sender_role=msg.sender_role,
            content=msg.content,
            english_text=msg.english_content or msg.content,
            audio_url=msg.audio_path,
            visemes=visemes,
            created_at=msg.created_at
        ))
    return out

@router.get("/group/messages", response_model=List[GroupMessageOut])
async def get_group_messages(
    after_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Real-time polling endpoint for 3-Way Group Lounge (Master + Mistress + Shiii).
    """
    if not current_user.couple_id:
        return []
    
    query = select(CoupleGroupMessage).where(CoupleGroupMessage.couple_id == current_user.couple_id)
    if after_id is not None and after_id > 0:
        query = query.where(CoupleGroupMessage.id > after_id).order_by(CoupleGroupMessage.id.asc())
    else:
        query = query.order_by(CoupleGroupMessage.id.desc()).limit(100)
    
    result = await db.execute(query)
    messages = list(result.scalars().all())
    if after_id is None or after_id <= 0:
        messages.reverse()
        
    out: List[GroupMessageOut] = []
    for m in messages:
        visemes = []
        if m.audio_path:
            word_count = len(m.content.split())
            estimated_duration = max(1.0, (word_count / 140.0) * 60.0)
            visemes = voice_service._estimate_visemes(m.content, estimated_duration)
        out.append(GroupMessageOut(
            id=m.id,
            couple_id=m.couple_id,
            sender_id=m.sender_id,
            sender_role=m.sender_role,
            sender_name=m.sender_name,
            content=m.content,
            english_text=m.english_content or m.content,
            audio_url=m.audio_path,
            visemes=visemes,
            created_at=m.created_at
        ))
    return out

@router.post("/group/messages", response_model=List[GroupMessageOut])
async def send_group_message(
    req: GroupChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message to 3-Way Group Lounge.
    Shiii reads the context (understanding Hindi/Hinglish/English) and responds with cute calming mediation.
    """
    if not current_user.couple_id:
        raise HTTPException(status_code=400, detail="You must be paired with your partner to enter Group Lounge")
        
    sender_name = current_user.display_name or current_user.username
    user_msg = CoupleGroupMessage(
        couple_id=current_user.couple_id,
        sender_id=current_user.id,
        sender_role=current_user.role.value,
        sender_name=sender_name,
        content=req.message
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    # Fetch partner info
    c_res = await db.execute(
        select(Couple)
        .where(Couple.id == current_user.couple_id)
        .options(selectinload(Couple.master), selectinload(Couple.mistress))
    )
    couple = c_res.scalars().first()
    master_name = couple.master.display_name if couple and couple.master else "Master"
    mistress_name = couple.mistress.display_name if couple and couple.mistress else "Mistress"
    partner_name = mistress_name if current_user.role == UserRole.MASTER else master_name

    # Fetch recent conversation for context
    history_res = await db.execute(
        select(CoupleGroupMessage)
        .where(CoupleGroupMessage.couple_id == current_user.couple_id)
        .order_by(CoupleGroupMessage.id.desc())
        .limit(8)
    )
    recent_records = list(history_res.scalars().all())
    recent_records.reverse()
    recent_dialogue = [{"sender": r.sender_name, "text": r.content} for r in recent_records]

    # Generate Shiii's mediation to soothe tension and bring peace
    mediation_text, mediation_english = await llm_service.mediate_group_chat(
        recent_dialogue=recent_dialogue,
        latest_message=req.message,
        sender_role=current_user.role.value,
        sender_name=sender_name,
        partner_name=partner_name
    )

    # Synthesize cute voice for Shiii
    shiii_audio_url, shiii_visemes = await voice_service.synthesize(mediation_english or mediation_text)

    shiii_msg = CoupleGroupMessage(
        couple_id=current_user.couple_id,
        sender_id=None,
        sender_role="shiii",
        sender_name="Shiii 🌸",
        content=mediation_text,
        english_content=mediation_english,
        audio_path=shiii_audio_url
    )
    db.add(shiii_msg)
    await db.commit()
    await db.refresh(shiii_msg)

    return [
        GroupMessageOut(
            id=user_msg.id,
            couple_id=user_msg.couple_id,
            sender_id=user_msg.sender_id,
            sender_role=user_msg.sender_role,
            sender_name=user_msg.sender_name,
            content=user_msg.content,
            english_text=user_msg.content,
            audio_url=user_msg.audio_path,
            visemes=[],
            created_at=user_msg.created_at
        ),
        GroupMessageOut(
            id=shiii_msg.id,
            couple_id=shiii_msg.couple_id,
            sender_id=shiii_msg.sender_id,
            sender_role=shiii_msg.sender_role,
            sender_name=shiii_msg.sender_name,
            content=shiii_msg.content,
            english_text=shiii_msg.english_content,
            audio_url=shiii_msg.audio_path,
            visemes=shiii_visemes,
            created_at=shiii_msg.created_at
        )
    ]


# -------------------------------------------------------------
# Personal Direct 1-on-1 Chat (Master & Mistress Only, No Shiii)
# Real-Time, Ultra-Low Latency, and Read Receipts
# -------------------------------------------------------------

@router.get("/direct/messages", response_model=List[DirectMessageOut])
async def get_direct_messages(
    after_id: Optional[int] = None,
    mark_read: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get 1-on-1 personal couple messages between Master and Mistress.
    If mark_read is True, automatically marks partner's unread messages as read!
    """
    if not current_user.couple_id:
        return []

    # If mark_read is requested, mark incoming messages sent by partner as read
    if mark_read:
        partner_query = (
            select(CoupleDirectMessage)
            .where(
                CoupleDirectMessage.couple_id == current_user.couple_id,
                CoupleDirectMessage.receiver_id == current_user.id,
                CoupleDirectMessage.is_read == False
            )
        )
        unread_res = await db.execute(partner_query)
        unreads = unread_res.scalars().all()
        if unreads:
            now = datetime.now(timezone.utc)
            for m in unreads:
                m.is_read = True
                m.read_at = now
            await db.commit()

    query = select(CoupleDirectMessage).where(CoupleDirectMessage.couple_id == current_user.couple_id)
    if after_id is not None:
        query = query.where(CoupleDirectMessage.id > after_id).order_by(CoupleDirectMessage.id.asc())
    else:
        query = query.order_by(CoupleDirectMessage.id.desc()).limit(100)

    c_res = await db.execute(
        select(Couple).where(Couple.id == current_user.couple_id)
    )
    couple = c_res.scalars().first()
    master_id = couple.master_id if couple else None

    result = await db.execute(query)
    messages = list(result.scalars().all())
    if after_id is None:
        messages.reverse()

    return [
        DirectMessageOut(
            id=m.id,
            couple_id=m.couple_id,
            sender_id=m.sender_id,
            receiver_id=m.receiver_id,
            sender_role="master" if m.sender_id == master_id else "mistress",
            content=m.content,
            is_read=m.is_read,
            read_at=m.read_at,
            created_at=m.created_at
        )
        for m in messages
    ]

@router.post("/direct/messages", response_model=DirectMessageOut)
async def send_direct_message(
    req: DirectMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Send an ultra-low latency direct message to your partner (Master <-> Mistress).
    No Shiii AI messages are inserted here.
    """
    if not current_user.couple_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not paired with a partner yet."
        )

    # Find the partner's user ID
    c_res = await db.execute(
        select(Couple)
        .options(selectinload(Couple.master), selectinload(Couple.mistress))
        .where(Couple.id == current_user.couple_id)
    )
    couple = c_res.scalars().first()
    if not couple or not couple.master_id or not couple.mistress_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Couple pairing incomplete."
        )

    receiver_id = couple.mistress_id if current_user.id == couple.master_id else couple.master_id

    direct_msg = CoupleDirectMessage(
        couple_id=current_user.couple_id,
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=req.content.strip(),
        is_read=False,
        read_at=None
    )
    db.add(direct_msg)
    await db.commit()
    await db.refresh(direct_msg)

    return DirectMessageOut(
        id=direct_msg.id,
        couple_id=direct_msg.couple_id,
        sender_id=direct_msg.sender_id,
        receiver_id=direct_msg.receiver_id,
        sender_role=current_user.role.value,
        content=direct_msg.content,
        is_read=direct_msg.is_read,
        read_at=direct_msg.read_at,
        created_at=direct_msg.created_at
    )

@router.post("/direct/messages/read", response_model=MarkReadResponse)
async def mark_direct_messages_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Explicitly mark all incoming direct messages from partner as read.
    """
    if not current_user.couple_id:
        return MarkReadResponse(status="ok", marked_count=0)

    partner_query = (
        select(CoupleDirectMessage)
        .where(
            CoupleDirectMessage.couple_id == current_user.couple_id,
            CoupleDirectMessage.receiver_id == current_user.id,
            CoupleDirectMessage.is_read == False
        )
    )
    unread_res = await db.execute(partner_query)
    unreads = unread_res.scalars().all()
    count = len(unreads)
    if count > 0:
        now = datetime.now(timezone.utc)
        for m in unreads:
            m.is_read = True
            m.read_at = now
        await db.commit()

    return MarkReadResponse(status="ok", marked_count=count)


@router.delete("/messages/clear")
async def clear_messages(
    scope: str = "all",  # "shiii", "direct", "group", "all"
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete chat messages sent by the current user:
    - scope = 'shiii': clears private chat with Shiii
    - scope = 'direct': clears messages sent by current user in 1-on-1 direct chat
    - scope = 'group': clears messages sent by current user in 3-way lounge
    - scope = 'all': clears all of the above
    """
    from sqlalchemy import delete

    deleted_counts = {}

    if scope in ("shiii", "all"):
        res = await db.execute(
            delete(ChatMessage).where(ChatMessage.user_id == current_user.id)
        )
        deleted_counts["shiii"] = res.rowcount

    if scope in ("direct", "all") and current_user.couple_id:
        res = await db.execute(
            delete(CoupleDirectMessage).where(
                CoupleDirectMessage.couple_id == current_user.couple_id,
                CoupleDirectMessage.sender_id == current_user.id
            )
        )
        deleted_counts["direct"] = res.rowcount

    if scope in ("group", "all") and current_user.couple_id:
        res = await db.execute(
            delete(CoupleGroupMessage).where(
                CoupleGroupMessage.couple_id == current_user.couple_id,
                CoupleGroupMessage.sender_id == current_user.id
            )
        )
        deleted_counts["group"] = res.rowcount

    await db.commit()

    return {
        "status": "ok",
        "scope": scope,
        "deleted_counts": deleted_counts,
        "message": f"Successfully deleted messages for scope '{scope}'"
    }




