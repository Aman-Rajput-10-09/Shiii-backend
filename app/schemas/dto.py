from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from app.models.schemas import UserRole, ConcernStatus

# Auth
class Token(BaseModel):
    access_token: str
    token_type: str
    role: UserRole
    user_id: Optional[int] = None
    display_name: Optional[str] = None
    couple_id: Optional[int] = None
    is_paired: bool = False
    pair_code: Optional[str] = None
    partner_name: Optional[str] = None

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole
    display_name: Optional[str] = None

class UserOut(BaseModel):
    id: int
    username: str
    role: UserRole
    display_name: Optional[str] = None
    couple_id: Optional[int] = None
    
    class Config:
        from_attributes = True

# Couple Pairing
class CoupleStatusOut(BaseModel):
    is_paired: bool
    pair_code: str
    partner_name: Optional[str] = None
    partner_role: Optional[str] = None
    couple_id: Optional[int] = None

class PairRequest(BaseModel):
    pair_code: str

class PairResponse(BaseModel):
    success: bool
    message: str
    partner_name: str
    couple_id: int

# Chat & Dialogue
class ChatRequest(BaseModel):
    message: str

class VisemeCue(BaseModel):
    time_ms: int
    mouth: str  # "closed", "A", "I", "U", "E", "O"

class ChatResponse(BaseModel):
    id: Optional[int] = None
    reply_text: str
    english_text: Optional[str] = None
    audio_url: Optional[str] = None
    visemes: List[VisemeCue] = []
    sender_role: str = "shiii"
    created_at: datetime


class ChatMessageOut(BaseModel):
    id: int
    sender_role: str
    content: str
    english_text: Optional[str] = None
    audio_url: Optional[str] = None
    visemes: List[VisemeCue] = []
    created_at: datetime

    class Config:
        from_attributes = True


# Concern & Briefing
class ConcernBriefingOut(BaseModel):
    id: int
    original_mistress_text: str
    emotional_sentiment: str
    urgency_score: float
    master_briefing: Optional[str] = None
    audio_path: Optional[str] = None
    audio_url: Optional[str] = None
    status: ConcernStatus
    created_at: datetime
    
    class Config:
        from_attributes = True

class MasterResolutionRequest(BaseModel):
    concern_id: int
    master_reply: str

class MasterResolutionResponse(BaseModel):
    success: bool
    diplomatic_message_for_mistress: str
    audio_url: Optional[str] = None

class TTSRequest(BaseModel):
    text: str

class TTSResponse(BaseModel):
    audio_url: Optional[str] = None
    visemes: List[VisemeCue] = []

# 3-Way Group Chat (Master, Mistress, and Shiii)
class GroupChatRequest(BaseModel):
    message: str

class GroupMessageOut(BaseModel):
    id: int
    couple_id: int
    sender_id: Optional[int] = None
    sender_role: str
    sender_name: str
    content: str
    english_text: Optional[str] = None
    audio_url: Optional[str] = None
    visemes: List[VisemeCue] = []
    created_at: datetime

    class Config:
        from_attributes = True

# Personal Direct Couple Chat (Master & Mistress 1-on-1 with Read Receipts)
class DirectMessageRequest(BaseModel):
    content: str

class DirectMessageOut(BaseModel):
    id: int
    couple_id: int
    sender_id: int
    receiver_id: int
    sender_role: str = "" # "master" or "mistress"
    content: str
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

class MarkReadResponse(BaseModel):
    status: str
    marked_count: int
