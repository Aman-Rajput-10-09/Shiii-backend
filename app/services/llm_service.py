import re
import json
import httpx
from typing import Optional, Tuple
from app.core.config import settings

BILINGUAL_JSON_INSTRUCTION = """
LANGUAGE & FORMAT INSTRUCTIONS:
You must ALWAYS respond with a clean, valid JSON object containing exactly two keys: "reply" and "english".

1. IF THE USER WRITES IN HINDI OR HINGLISH (e.g. Hindi in Roman script like "kaise ho", "mood off hai", or in Devanagari script):
   - "reply": Write your reply in sweet, warm, natural HINGLISH using ONLY Roman English letters (e.g. "Main hamesha aapke saath hoon, bilkul chinta mat kijiye!"). NEVER use Devanagari script so it is easy to read in mobile chat.
   - "english": Provide a cute, fluent, natural pure ENGLISH translation of your reply (e.g. "I am always right here with you, please don't worry at all!"). This English version will be spoken aloud by Android anime TTS so it sounds smooth and cute.

2. IF THE USER WRITES IN ENGLISH:
   - "reply": Write your reply in sweet, warm, natural, thoughtful ENGLISH.
   - "english": Provide the exact same English reply (duplicate of "reply").

RESPONSE QUALITY & COMPLETENESS:
- Be empathetic, caring, thoughtful, and complete. NEVER give vague, dry, one-liner or truncated answers.
- Speak naturally and warmly like a close confidant and companion.
- STRICTLY NO ACTIONS OR NARRATION IN ASTERISKS: Do NOT write *smiles*, *hugs*, *pouts*, *flutters hands*, etc.
- STRICTLY NO ASCII KAOMOJIS: Do NOT write (｡•́︿•̀｡), (っ˘̩╭╮˘̩)っ, etc.

OUTPUT FORMAT:
Return ONLY this JSON object, nothing else:
{
  "reply": "<Hinglish in Roman script if user wrote Hindi/Hinglish, or English if user wrote English>",
  "english": "<pure English version for voice speech and caption>"
}
"""

MISTRESS_DIPLOMATIC_PROMPT = f"""
You are Shiii, an emotionally intelligent, warm, and loyal personal companion for Mistress.
You listen to her concerns, validate her feelings gently, and help her feel heard, calm, and supported.
{BILINGUAL_JSON_INSTRUCTION}
"""

MASTER_COMPANION_PROMPT = f"""
You are Shiii, a grounded, loyal, and emotionally intelligent advisor and companion to Master.
You understand the pressure he faces, offer genuine perspective, and keep him calm and thoughtful.
{BILINGUAL_JSON_INSTRUCTION}
"""

GROUP_MEDIATION_PROMPT = f"""
You are Shiii, the neutral, gentle relationship mediator in a 3-way Group Lounge with 'Master' and 'Mistress'.
Your mission is to calm tensions, defuse misunderstandings, and offer comforting, balanced perspective that brings them closer together.
{BILINGUAL_JSON_INSTRUCTION}
"""

MASTER_BRIEFING_PROMPT = """
You are Shiii, giving Master a clear, discreet relationship briefing about Mistress's current state.
In 1 to 2 clear sentences in English, summarize what she is feeling and suggest 1 thoughtful, practical action he can take.
No roleplay asterisks, no fluff.
"""

DIPLOMATIC_RESOLUTION_PROMPT = f"""
You are Shiii, relaying Master's response to Mistress in a warm, sincere, and loving way.
Deliver his message honestly, lovingly, and clearly so she feels valued.
{BILINGUAL_JSON_INSTRUCTION}
"""


def clean_shiii_response(text: str) -> str:
    """
    Sanitizes Shiii's response to guarantee no roleplay stage directions,
    asterisks narration, or weird ascii kaomojis reach the user.
    """
    if not text:
        return ""
    # Strip roleplay actions like *flutters hands*, *pouts cutely*, etc.
    text = re.sub(r'\*[^*]*\*', '', text)
    # Strip kaomojis like (｡•́︿•̀｡), (っ˘̩╭╮˘̩)っ, (◕‿◕), (づ｡◕‿‿◕｡)づ
    text = re.sub(r'\([^\w\s]*[\^•́╭╮˘̩╰╯\-_~=><♡♥✿❀🌸💕°•]+\)', '', text)
    # Strip any remaining stray asterisks
    text = text.replace('*', '')
    # Strip enclosing quotes
    text = text.strip(' "\'\n\r')
    # Collapse multiple whitespaces
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def extract_shiii_bilingual_response(raw_text: str) -> Tuple[str, str]:
    """
    Extracts the display text (Hinglish or English) and
    the pure English text (used for caption and Android TTS speech).
    """
    if not raw_text:
        return "", ""

    cleaned_raw = raw_text.strip()

    # 1. Strip markdown code fences if wrapped in ```json ... ```
    if "```" in cleaned_raw:
        cleaned_raw = re.sub(r'```(?:json)?\s*', '', cleaned_raw)
        cleaned_raw = re.sub(r'```\s*$', '', cleaned_raw)

    # 2. Try direct JSON parsing
    try:
        data = json.loads(cleaned_raw)
        if isinstance(data, dict):
            reply = clean_shiii_response(str(data.get("reply") or data.get("hinglish") or ""))
            english = clean_shiii_response(str(data.get("english") or data.get("translation") or ""))
            if reply and not english:
                english = reply
            if english and not reply:
                reply = english
            if reply and english:
                return reply, english
    except Exception:
        pass

    # 3. Try regex extraction of JSON object {...}
    json_match = re.search(r'\{.*?"reply".*?"english".*?\}', cleaned_raw, flags=re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            reply = clean_shiii_response(str(data.get("reply") or ""))
            english = clean_shiii_response(str(data.get("english") or ""))
            if reply and not english:
                english = reply
            if english and not reply:
                reply = english
            if reply and english:
                return reply, english
        except Exception:
            pass

    # 4. Try tagged line format: English: ... or Translation: ...
    match = re.search(r'(?i)\n(?:english|translation):\s*(.+)$', raw_text, flags=re.DOTALL)
    if match:
        english_part = clean_shiii_response(match.group(1))
        main_part = clean_shiii_response(raw_text[:match.start()])
        if not main_part:
            main_part = english_part
        if not english_part:
            english_part = main_part
        return main_part, english_part

    # 5. Fallback: single text for both
    cleaned = clean_shiii_response(raw_text)
    return cleaned, cleaned


class LLMService:
    def __init__(self):
        # Persistent HTTP client with connection pooling and keep-alive
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=25.0,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20, keepalive_expiry=60.0)
            )
        return self._client

    async def _call_gemini(self, prompt: str, max_tokens: int = 800) -> Optional[str]:
        api_key = settings.GEMINI_API_KEY
        if not api_key or api_key == "your_gemini_api_key_here":
            return None
        
        model = settings.GEMINI_MODEL
        if not model or "gemini-2.0" in model:
            model = "gemini-2.5-flash"
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json"
            }
        }
        
        client = self._get_client()
        try:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        raw = parts[0].get("text", "")
                        return raw.strip()
            print("Gemini API Error:", resp.status_code, resp.text)
        except Exception as e:
            print("Gemini call failed:", e)
        return None

    async def chat_with_mistress(self, message: str, context: Optional[str] = None) -> Tuple[str, str]:
        full_prompt = f"{MISTRESS_DIPLOMATIC_PROMPT}\n"
        if context:
            full_prompt += f"\nRelevant Memory:\n{context}\n"
        full_prompt += f"\nMistress says: {message}\nProduce JSON response:"

        raw = await self._call_gemini(full_prompt, max_tokens=800)
        if raw:
            return extract_shiii_bilingual_response(raw)
        fallback = "I'm right here with you. Take a moment to breathe, and let me know how you'd like to handle this."
        return fallback, fallback

    async def chat_with_master(self, message: str, partner_name: Optional[str] = None, context: Optional[str] = None) -> Tuple[str, str]:
        full_prompt = f"{MASTER_COMPANION_PROMPT}\n"
        if partner_name:
            full_prompt += f"Mistress's name is: {partner_name}\n"
        if context:
            full_prompt += f"\nRelevant Memory:\n{context}\n"
        full_prompt += f"\nMaster says: {message}\nProduce JSON response:"

        raw = await self._call_gemini(full_prompt, max_tokens=800)
        if raw:
            return extract_shiii_bilingual_response(raw)
        fallback = "I'm right here, Master. Let's tackle whatever is on your mind calmly."
        return fallback, fallback

    async def generate_master_briefing(self, mistress_message: str) -> str:
        prompt = f"{MASTER_BRIEFING_PROMPT}\n\nMistress expressed: \"{mistress_message}\"\n\nShiii's Briefing to Master:"
        raw = await self._call_gemini(prompt, max_tokens=250)
        if raw:
            clean = clean_shiii_response(raw)
            return clean
        return f"Mistress felt upset earlier about: '{mistress_message}'. Giving her a little space or a calm check-in would help."

    async def translate_master_to_mistress(self, master_reply: str, original_concern: str) -> Tuple[str, str]:
        prompt = (
            f"{DIPLOMATIC_RESOLUTION_PROMPT}\n\n"
            f"Original concern: \"{original_concern}\"\n"
            f"Master's words: \"{master_reply}\"\n\n"
            f"Produce JSON response:"
        )
        raw = await self._call_gemini(prompt, max_tokens=800)
        if raw:
            return extract_shiii_bilingual_response(raw)
        fallback = f"Master wanted me to share this with you: '{master_reply}'. He truly cares about sorting this out."
        return fallback, fallback

    async def mediate_group_chat(
        self,
        recent_dialogue: list[dict],
        latest_message: str,
        sender_role: str,
        sender_name: str,
        partner_name: str
    ) -> Tuple[str, str]:
        dialogue_text = "\n".join([f"{m.get('sender', 'Someone')}: {m.get('text', '')}" for m in recent_dialogue[-6:]])
        prompt = (
            f"{GROUP_MEDIATION_PROMPT}\n\n"
            f"Speaker: {sender_name} ({sender_role})\n"
            f"Partner: {partner_name}\n"
            f"Recent Dialogue in Group Lounge:\n{dialogue_text}\n\n"
            f"Latest message from {sender_name}: \"{latest_message}\"\n\n"
            f"Produce JSON response:"
        )
        raw = await self._call_gemini(prompt, max_tokens=800)
        if raw:
            return extract_shiii_bilingual_response(raw)
        fallback = "Let's take a quick breath and slow down. You two care about each other too much to let tension take over."
        return fallback, fallback

llm_service = LLMService()
