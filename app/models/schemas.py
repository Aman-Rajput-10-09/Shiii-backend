from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, 
    Boolean, Float, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base

class UserRole(str, enum.Enum):
    MASTER = "master"
    MISTRESS = "mistress"

class ConcernStatus(str, enum.Enum):
    PENDING = "pending"          # Mistress expressed concern, waiting for Master briefing
    BRIEFED = "briefed"          # Master was briefed
    RESOLVED = "resolved"        # Master responded and Shiii conveyed diplomatic resolution

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False)
    display_name = Column(String(100), nullable=True)
    couple_id = Column(Integer, ForeignKey("couples.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    messages = relationship("ChatMessage", back_populates="user")
    couple = relationship("Couple", foreign_keys=[couple_id], post_update=True)

class Couple(Base):
    """
    Represents the paired bond between a Master and a Mistress.
    """
    __tablename__ = "couples"
    
    id = Column(Integer, primary_key=True, index=True)
    pair_code = Column(String(20), unique=True, index=True, nullable=False)
    master_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    mistress_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    master = relationship("User", foreign_keys=[master_id])
    mistress = relationship("User", foreign_keys=[mistress_id])
    concerns = relationship("CoupleConcern", back_populates="couple", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sender_role = Column(String(20), nullable=False) # "master", "mistress", or "shiii"
    content = Column(Text, nullable=False)
    english_content = Column(Text, nullable=True)
    audio_path = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="messages")

class CoupleGroupMessage(Base):
    """
    Shared 3-Way Group Lounge: Master + Mistress + Shiii as the diplomatic mediator.
    """
    __tablename__ = "couple_group_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    couple_id = Column(Integer, ForeignKey("couples.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sender_role = Column(String(20), nullable=False) # "master", "mistress", or "shiii"
    sender_name = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    english_content = Column(Text, nullable=True)
    audio_path = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

class CoupleDirectMessage(Base):
    """
    Personal 1-on-1 direct chat between Master and Mistress only (no Shiii).
    Includes real-time delivery and read receipt status (is_read, read_at).
    """
    __tablename__ = "couple_direct_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    couple_id = Column(Integer, ForeignKey("couples.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

class CoupleConcern(Base):
    """
    Tracks concerns raised by Mistress or Master, diplomatic mediation state,
    and Shiii's briefing to the partner.
    """
    __tablename__ = "couple_concerns"
    
    id = Column(Integer, primary_key=True, index=True)
    couple_id = Column(Integer, ForeignKey("couples.id", ondelete="CASCADE"), nullable=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    author_role = Column(SQLEnum(UserRole), default=UserRole.MISTRESS)
    original_mistress_text = Column(Text, nullable=False)
    emotional_sentiment = Column(String(50), default="upset") # sad, lonely, anxious, annoyed
    urgency_score = Column(Float, default=1.0) # Used for relationship ranking
    
    # Diplomatic briefing prepared by Shiii for Master
    master_briefing = Column(Text, nullable=True)
    audio_path = Column(String(500), nullable=True)
    
    # Master's response & Shiii's sweet translation back to Mistress
    master_response = Column(Text, nullable=True)
    diplomatic_resolution_to_mistress = Column(Text, nullable=True)
    
    status = Column(SQLEnum(ConcernStatus), default=ConcernStatus.PENDING)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    couple = relationship("Couple", back_populates="concerns")

class RelationshipMemory(Base):
    """
    Long-term couple memory for RAG:
    e.g. 'Mistress loves matcha and warm hugs', 'Master works late on Tuesdays'
    """
    __tablename__ = "relationship_memories"
    
    id = Column(Integer, primary_key=True, index=True)
    couple_id = Column(Integer, ForeignKey("couples.id", ondelete="CASCADE"), nullable=True)
    subject = Column(String(50), nullable=False) # mistress, master, couple
    category = Column(String(50), nullable=False) # preference, habit, past_conflict, milestone
    memory_text = Column(Text, nullable=False)
    emotional_weight = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

