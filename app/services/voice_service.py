from typing import List, Tuple, Optional
from app.schemas.dto import VisemeCue

class VoiceService:
    @classmethod
    async def synthesize(cls, text: str) -> Tuple[Optional[str], List[VisemeCue]]:
        """
        Edge-TTS removed. Voice synthesis is handled natively on-device via Android TTS.
        """
        return None, []

voice_service = VoiceService()
