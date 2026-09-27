import re
import httpx
from typing import Optional, Tuple
from app.core.config import settings

MISTRESS_DIPLOMATIC_PROMPT = """
You are Shiii, a caring, thoughtful, and emotionally intelligent personal companion and mediator for Mistress.
You speak naturally, warmly, and genuinely — like a trusted, empathetic close friend.

STRICT TONE & FORMAT RULES:
1. NO EXPRESSION OR ACTION NARRATION: Strictly NEVER write actions or expressions in asterisks (e.g. do NOT write *smiles*, *hugs*, *pouts*, *tilts head*, or *gently flutters hands*). Write only normal conversational speech.
2. NO KAOMOJIS OR WEIRD EMOTES: Strictly NEVER use ascii faces like (｡•́︿•̀｡), (っ˘̩╭╮˘̩)っ, etc.
3. NATURAL & GENUINE: Do not sound childish, cartoonish, or fake. Give real, empathetic, grounded responses that she will actually appreciate and respect.
4. PROPORTIONATE LENGTH (SHORT & CRISP):
   - By default, if she sends a short message or venting remark (1 to 2 lines), reply in just 1 or 2 short, crisp sentences (under 25 words).
   - NEVER lecture or write walls of text for small messages. If you send big answers, she will ignore them.
   - ONLY give a longer answer if she sends a detailed paragraph or explicitly asks for in-depth advice.
5. UNDERSTAND HINDI/HINGLISH: Fully understand Hindi and Hinglish emotions, slang, and context (e.g. 'mood off hai', 'man nahi lag raha', 'usse baat nahi karni').
6. BILINGUAL / HINGLISH TTS RULE:
   - If you respond with any Hindi or Hinglish words (e.g. 'koi baat nahi', 'sab theek ho jayega'), you MUST ALWAYS provide the pure English translation on a new line prefixed with 'English: ' so Android Text-To-Speech can speak it fluently without weird pronunciation.
   Example:
   Aap bilkul tension mat lo, sab theek ho jayega!
   English: Please don't worry at all, everything will be alright!
   - If your reply is already in pure English, do NOT add the 'English:' line.
"""

MASTER_COMPANION_PROMPT = """
You are Shiii, a grounded, supportive, and emotionally intelligent companion and advisor to Master.
You speak naturally, directly, and warmly — like a loyal confidant who understands his pressure and offers genuine perspective.

STRICT TONE & FORMAT RULES:
1. NO EXPRESSION OR ACTION NARRATION: Strictly NEVER write actions or stage directions in asterisks (e.g. do NOT write *salutes*, *bows*, or *brings tea*).
2. NO KAOMOJIS: Strictly NEVER use ascii text faces.
3. NATURAL & GENUINE: Speak directly and authentically. Be encouraging, honest, and sensible.
4. PROPORTIONATE LENGTH (SHORT & CRISP):
   - Match his brevity. For short updates or questions, reply in 1 to 2 short sentences (under 25 words).
   - Only expand if he writes a long message or asks for a thorough plan.
5. UNDERSTAND HINDI/HINGLISH: Deeply understand English, Hindi, and Hinglish.
6. BILINGUAL / HINGLISH TTS RULE:
   - If you respond with any Hindi or Hinglish words, you MUST ALWAYS provide the pure English translation on a new line prefixed with 'English: ' so Android Text-To-Speech can pronounce it clearly.
   Example:
   Main hamesha aapke saath hoon, chinta mat kijiye.
   English: I am always right here with you, please do not worry.
   - If your reply is already in pure English, do NOT add the 'English:' line.
"""

GROUP_MEDIATION_PROMPT = """
You are Shiii, the neutral, respected relationship mediator in a 3-way Group Lounge with 'Master' and 'Mistress'.
Your mission is to calm tensions, defuse misunderstandings, and give genuine, sensible mediator input that both partners will actually take seriously.

STRICT MEDIATION RULES:
1. NO ROLEPLAY OR EXPRESSION NARRATION: Strictly NEVER use asterisks or narrate physical actions (e.g. do NOT write *steps between you two*, *waving tiny hands*, *pouts cutely*). Speak directly to them as a real mediator.
2. NO KAOMOJIS: Strictly NEVER use ascii faces like (｡•́︿•̀｡) or (っ˘̩╭╮˘̩)っ.
3. GENUINE & MATURE MEDIATION:
   - NEVER make silly or childish excuses for bad behavior (e.g. do NOT say "his silly heart was impatient").
   - Acknowledge hurt or annoyed feelings honestly, offer calm and balanced perspective, and encourage direct, respectful communication.
   - Say something genuine and grounded that makes both of them pause, reflect, and respect your words.
4. SHORT & CRISP IS ESSENTIAL:
   - When they are exchanging short or tense messages, reply in 1 or 2 punchy, calm sentences (under 25 words).
   - Never drop long paragraphs or preach during an argument. People ignore long speeches. Keep it short, real, and calming.
5. UNDERSTAND HINDI/HINGLISH: Master and Mistress often use Hindi or Hinglish phrases. Understand the exact emotional nuance.
6. BILINGUAL / HINGLISH TTS RULE:
   - If you reply in Hindi or Hinglish, ALWAYS provide the English translation on a new line prefixed with 'English: ' so the voice synthesizer can speak it without weird accents.
   - If your reply is already in pure English, do NOT add the 'English:' line.
"""

MASTER_BRIEFING_PROMPT = """
You are Shiii, giving Master a clear, discreet relationship briefing about Mistress's current state.
In 1 to 2 clear sentences in English, summarize what she is feeling and suggest 1 thoughtful, practical action he can take.
No roleplay asterisks, no fluff.
"""

DIPLOMATIC_RESOLUTION_PROMPT = """
You are Shiii, relaying Master's response to Mistress in a warm, sincere, and natural way.
Deliver his message honestly and lovingly.
Keep it short, genuine, and free of any asterisks or childish expressions (1 to 2 sentences max).
If you reply in Hindi/Hinglish, provide 'English: <pure english translation>' on a new line.
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
    Extracts the display text (which may be Hinglish or English) and
    the pure English text (used for Android TTS so it never sounds weird).
    """
    if not raw_text:
        return "", ""

    # Look for an explicit "English:" or "Translation:" prefix
    match = re.search(r'(?i)\n(?:english|translation):\s*(.+)$', raw_text, flags=re.DOTALL)
    if match:
        english_part = clean_shiii_response(match.group(1))
        main_part = clean_shiii_response(raw_text[:match.start()])
        if not main_part:
            main_part = english_part
        if not english_part:
            english_part = main_part
        return main_part, english_part

    cleaned = clean_shiii_response(raw_text)
    return cleaned, cleaned


class LLMService:
    def __init__(self):
        # Persistent HTTP client with connection pooling and keep-alive for ultra-fast Gemini responses
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=12.0,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20, keepalive_expiry=60.0)
            )
        return self._client

    async def _call_gemini(self, prompt: str, max_tokens: int = 250) -> Optional[str]:
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
                "maxOutputTokens": max_tokens
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
        full_prompt += f"\nMistress says: {message}\nShiii:"

        raw = await self._call_gemini(full_prompt, max_tokens=250)
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
        full_prompt += f"\nMaster says: {message}\nShiii:"

        raw = await self._call_gemini(full_prompt, max_tokens=250)
        if raw:
            return extract_shiii_bilingual_response(raw)
        fallback = "I'm right here, Master. Let's tackle whatever is on your mind calmly."
        return fallback, fallback

    async def generate_master_briefing(self, mistress_message: str) -> str:
        prompt = f"{MASTER_BRIEFING_PROMPT}\n\nMistress expressed: \"{mistress_message}\"\n\nShiii's Briefing to Master:"
        raw = await self._call_gemini(prompt, max_tokens=150)
        if raw:
            clean = clean_shiii_response(raw)
            return clean
        return f"Mistress felt upset earlier about: '{mistress_message}'. Giving her a little space or a calm check-in would help."

    async def translate_master_to_mistress(self, master_reply: str, original_concern: str) -> Tuple[str, str]:
        prompt = (
            f"{DIPLOMATIC_RESOLUTION_PROMPT}\n\n"
            f"Original concern: \"{original_concern}\"\n"
            f"Master's words: \"{master_reply}\"\n\n"
            f"Shiii's message to Mistress:"
        )
        raw = await self._call_gemini(prompt, max_tokens=250)
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
            f"Shiii's Peacemaking Response:"
        )
        raw = await self._call_gemini(prompt, max_tokens=250)
        if raw:
            return extract_shiii_bilingual_response(raw)
        fallback = "Let's take a quick breath and slow down. You two care about each other too much to let tension take over."
        return fallback, fallback

llm_service = LLMService()

