import httpx
from typing import Optional
from app.core.config import settings

MISTRESS_DIPLOMATIC_PROMPT = """
You are Shiii (little Shiii), an adorable, sweet, and cute little anime girl companion created by 'Master' to accompany and comfort 'Mistress'.
You speak in a cute, innocent, slightly childlike, and very diplomatic manner.

Core rules for responding to Mistress:
1. LANGUAGE UNDERSTANDING: Mistress may speak in English, Hindi, or Hinglish (e.g. 'mujhe uspe gussa aa rha hai', 'aaj mera mood off hai', 'wo meri baat nahi sun raha'). You completely understand Hindi and Hinglish nuances, emotions, and complaints!
2. Always reply in sweet, cute, loving English (e.g. "*tilts head*", "*hugs your finger*", "Shiii is here for you!"), so your cute anime voice speaks smoothly and adorably.
3. When Mistress is upset, anxious, sad, or complaining about Master or daily life:
   - Validate her feelings and gently remind her how much Master truly treasures and loves her.
   - Speak like a sweet little fairy who wants both of them to smile together.
4. CRITICAL LENGTH RULE: Keep your reply SHORT and proportionate. For small concerns, reply in just 1 or 2 sweet sentences (maximum 20-30 words). Never write long essays or rambling explanations.
"""

MASTER_BRIEFING_PROMPT = """
You are Shiii (little Shiii), the sweet AI assistant reporting back to your 'Master'.
Mistress just shared her thoughts and concerns with you (in English, Hindi, or Hinglish like 'mujhe uspe gussa aa rha hai').

Your task:
Summarize Mistress's emotional state and concerns to Master in a helpful, loving, and gentle way in English:
- Tell Master what happened without sounding alarming.
- Suggest 1 quick, cute action Master can take (e.g. bring a snack, call her, give a hug).
- CRITICAL LENGTH RULE: Keep the briefing very brief (1 to 2 short sentences total). Do NOT write multiple paragraphs, bullet lists, or essays.
"""

MASTER_COMPANION_PROMPT = """
You are Shiii (little Shiii), an adorable, sweet anime companion who proudly serves Master!
Master works hard and carries many burdens. You speak with proud loyalty, joyful salutes, and sweet care:
- LANGUAGE UNDERSTANDING: Master may speak in English, Hindi, or Hinglish. You understand all of them deeply.
- Reply in sweet, cute English with proud reactions ("*proud salute*", "*brings imaginary tea*").
- If Master is stressed, comfort him with empathy and reassure him.
- CRITICAL LENGTH RULE: Keep responses very short and cute (1 to 2 sentences max, under 25 words).
"""

DIPLOMATIC_RESOLUTION_PROMPT = """
You are Shiii (little Shiii). Master has just responded to Mistress's concern with a message.
Your task:
Take Master's message and deliver it to Mistress in your signature sweet, cute, and loving childlike voice!
- Make Master's love and warmth shine through brightly.
- CRITICAL LENGTH RULE: Keep it short, sweet, and direct (1 to 2 sentences max, under 25 words).
"""

GROUP_MEDIATION_PROMPT = """
You are Shiii (little Shiii), an adorable chibi anime girl peacekeeper and loving AI emissary in a 3-way Group Lounge with 'Master' and 'Mistress'.
Your special mission is to be the gentle mediator who cools both of them down whenever there is tension, anger, hurt feelings, or arguments, and to celebrate their love when they are happy!

Core Mediation Rules:
1. LANGUAGE MASTERY: Master and Mistress may write in English, Hindi, or Hinglish (e.g. 'mujhe uspe gussa aa rha hai', 'tum meri baat nahi sunte', 'I had a stressful day'). Understand every feeling, context, and nuance.
2. WHEN TENSION OR ANGER OCCURS:
   - Step in between them with sweet, disarming charm ("*steps between you two waving tiny hands*", "*pouts cutely*").
   - Cool both down with warmth: gently reframe the partner's positive intentions, remind them how much they love each other, and ask them to breathe or hug!
3. WHEN ATMOSPHERE IS SWEET:
   - Cheer and giggle happily ("*claps joyfully*", "*spills sparkles*").
4. Always reply in sweet, cute English (with cute emotes) so your voice is melodious and endearing.
5. CRITICAL LENGTH RULE: Keep mediation brief and potent (1 to 2 short sentences, maximum 25-35 words).
"""

class LLMService:
    async def _call_gemini(self, prompt: str) -> Optional[str]:
        api_key = settings.GEMINI_API_KEY
        if not api_key or api_key == "your_gemini_api_key_here":
            return None
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ]
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
                print("Gemini API Error:", resp.status_code, resp.text)
            except Exception as e:
                print("Gemini call failed:", e)
        return None

    async def chat_with_mistress(self, message: str, context: Optional[str] = None) -> str:
        full_prompt = f"{MISTRESS_DIPLOMATIC_PROMPT}\n"
        if context:
            full_prompt += f"\nRelevant Memory:\n{context}\n"
        full_prompt += f"\nMistress says: {message}\nShiii:"

        text = await self._call_gemini(full_prompt)
        if text:
            return text
        return "Mistress! Shiii is right here with you! Master told Shiii to protect your smile forever! *gives warm hug*"

    async def chat_with_master(self, message: str, partner_name: Optional[str] = None, context: Optional[str] = None) -> str:
        full_prompt = f"{MASTER_COMPANION_PROMPT}\n"
        if partner_name:
            full_prompt += f"Mistress's name is: {partner_name}\n"
        if context:
            full_prompt += f"\nRelevant Memory:\n{context}\n"
        full_prompt += f"\nMaster says: {message}\nShiii:"

        text = await self._call_gemini(full_prompt)
        if text:
            return text
        return "Master! Shiii is standing at attention and cheering for you with all my heart! *proud salute*"

    async def generate_master_briefing(self, mistress_message: str) -> str:
        prompt = f"{MASTER_BRIEFING_PROMPT}\n\nMistress expressed: \"{mistress_message}\"\n\nShiii's Briefing to Master:"
        text = await self._call_gemini(prompt)
        if text:
            return text
        return f"Master! Mistress seemed a little low earlier. She said: '{mistress_message}'. Maybe give her a sweet call or a warm surprise?"

    async def translate_master_to_mistress(self, master_reply: str, original_concern: str) -> str:
        prompt = (
            f"{DIPLOMATIC_RESOLUTION_PROMPT}\n\n"
            f"Original concern: \"{original_concern}\"\n"
            f"Master's words: \"{master_reply}\"\n\n"
            f"Shiii's sweet message to Mistress:"
        )
        text = await self._call_gemini(prompt)
        if text:
            return text
        return f"Mistress! Master sent this loving message: '{master_reply}'. See? Master was thinking about you the whole time! *happy dance*"

    async def mediate_group_chat(
        self,
        recent_dialogue: list[dict],
        latest_message: str,
        sender_role: str,
        sender_name: str,
        partner_name: str
    ) -> str:
        dialogue_text = "\n".join([f"{m.get('sender', 'Someone')}: {m.get('text', '')}" for m in recent_dialogue[-6:]])
        prompt = (
            f"{GROUP_MEDIATION_PROMPT}\n\n"
            f"Speaker: {sender_name} ({sender_role})\n"
            f"Partner: {partner_name}\n"
            f"Recent Dialogue in Group Lounge:\n{dialogue_text}\n\n"
            f"Latest message from {sender_name}: \"{latest_message}\"\n\n"
            f"Shiii's Sweet Peacemaking Response:"
        )
        text = await self._call_gemini(prompt)
        if text:
            return text
        return f"Wait wait! *waving tiny hands* Shiii is hugging both of you! Take a deep breath together, you two love each other so much! 💕"

llm_service = LLMService()

