"""
Utility functions for TTS Audiobook Converter
"""
import os
import re
import json
import time
import math
import struct
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque
from threading import Lock
import threading
import random
import google.generativeai as genai
from google.cloud import texttospeech
from google.api_core import exceptions
from io import BytesIO
from typing import Optional
import subprocess
import shutil
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

# Import application_path from config
from .config import application_path, OUTPUT_ROOT, LATEST_RUN_MARKER

# 새로운 모듈 구조에서 import (하위 호환성을 위해)
from .core.constants import (
    TTS_QUOTA_RPM,
    TTS_ASSUMED_LATENCY_SEC,
    TTS_MAX_CONCURRENCY,
    TTS_MAX_BYTES,
    TTS_SAFETY_MARGIN,
    TTS_SAMPLE_RATE,
    TTS_BATCH_SIZE,
    DEFAULT_NARRATIVE_MODE,
)
from .core.rate_limiter import RateLimiter, get_default_rate_limiter
from .utils.logging import log_error, print_error, print_warning
from .utils.timing import (
    log_workflow_step_start,
    log_workflow_step_end,
    save_workflow_timing_log,
    get_workflow_timing_summary,
)
from .models.voice import VOICE_BANKS
from .models.content import CONTENT_CATEGORIES
# NARRATIVE_MODES는 아래에 정의되어 있으므로, models/narrative.py에 설정
from .models import narrative as narrative_module
# 순환 import를 피하기 위해 models/narrative.py는 직접 import하지 않음

# 하위 호환성을 위한 별칭
QUOTA_TTS_RPM = TTS_QUOTA_RPM
ASSUMED_TTS_LATENCY_SEC = TTS_ASSUMED_LATENCY_SEC
CURRENT_MAX_TTS_CONCURRENCY = TTS_MAX_CONCURRENCY

# Rate limiting을 위한 전역 변수 (하위 호환성 유지)
# 새로운 코드는 RateLimiter 클래스를 사용해야 함
_tts_request_times: deque = deque()  # 최근 1분간 요청 시간 기록
_tts_request_lock: Lock = Lock()

# 음성 및 서사 모드 메타데이터는 models에서 import됨 (하위 호환성을 위해 re-export)
# VOICE_BANKS, CONTENT_CATEGORIES, NARRATIVE_MODES는 위에서 이미 import됨

# 중복 정의 제거: VOICE_BANKS, CONTENT_CATEGORIES, DEFAULT_NARRATIVE_MODE는 models에서 import됨
# NARRATIVE_MODES는 아래에 정의되어 있으며, models/narrative.py에서 이를 import하여 사용
# TODO: NARRATIVE_MODES도 models/narrative.py로 완전히 이동 필요 (순환 참조 해결 후)
NARRATIVE_MODES = {
    "mentor": {
        "label": "멘토/코치 모드",
        "description": "경험 많은 멘토가 후배에게 조언하는 형식",
        "tts_prompt": {
            "ko": "당신은 경험이 풍부한 멘토입니다. 후배에게 따뜻하고 격려적으로 조언하는 톤으로, 자연스럽고 차분하게 말해주세요. 중요한 포인트는 짧게 쉬어가며 강조하고, 신뢰감 있는 어조를 유지하세요.",
            "en": "You are an experienced mentor. Speak in a warm, encouraging tone to your mentee. Deliver naturally and calmly, with brief pauses to emphasize important points. Maintain a trustworthy, supportive voice.",
        },
        "default_technical_analogy": {
            "ko": "실무 경험을 바탕으로 실용적인 비유를 사용하여 후배가 쉽게 이해할 수 있도록 설명하세요.",
            "en": "Use practical analogies based on real-world experience so your mentee can easily understand.",
        },
        "voice_description": {
            "ko": "Warm, encouraging, and trustworthy mentor tone.",
            "en": "Warm, encouraging, and trustworthy mentor tone.",
        },
        "assets": {
            "ko": {
                "style_name": "mentor guidance",
                "setting": "* **Setting:** 편안한 멘토링 세션 공간에서 경험 많은 선배가 후배에게 조언을 나누는 분위기.",
                "tone": "* **Tone:** 따뜻하고 격려적이며, 지도적이고 신뢰감 있는 톤. 후배의 성장을 진심으로 응원합니다.",
                "language_style": "존댓말 또는 반말 (상황에 따라 선택 가능). 격려적이고 지도적인 한국어.",
                "listener_relation": "your junior colleague or mentee",
                "story_descriptor": "mentor guidance",
                "vibe_label": "Mentor",
                "address_examples": '"{listener_suffix}님", "{listener_suffix}야", "후배님", "{listener_suffix}"',
                "address_examples_en": '"{listener_base}", "young colleague", "my friend"',
            },
            "en": {
                "style_name": "mentor guidance",
                "setting": "* **Setting:** A comfortable mentoring session space where an experienced senior shares advice with a junior colleague.",
                "tone": "* **Tone:** Warm, encouraging, and guiding with a trustworthy tone. Genuinely supports the mentee's growth.",
                "language_style": "Encouraging and guiding English.",
                "listener_relation": "your junior colleague or mentee",
                "story_descriptor": "mentor guidance",
                "vibe_label": "Mentor",
                "address_examples": '"{listener_base}", "young colleague", "my friend"',
                "address_examples_en": '"{listener_base}", "young colleague", "my friend"',
            },
        },
        "personalization": {
            "showrunner": {
                "ko": """[LISTENER PERSONALIZATION]
- 후배의 이름은 "{listener_suffix}"입니다 (예: "{listener_suffix}님, 이 부분을 주의하세요" 또는 "{listener_suffix}야, 이렇게 하면 좋아").
- 다양한 조사 형태를 자연스럽게 사용해: "{listener_with_eun}" (예: "{listener_with_eun} 이 부분을 보세요"), "{listener_with_neun}" (예: "{listener_with_neun} 잘하고 있어요"), "{listener_with_i}" (예: "{listener_with_i} 이해했어요?"), "{listener_with_ga}" (예: "{listener_with_ga} 충분히 할 수 있어요").
- 멘토로서 경험을 공유하는 표현을 사용하세요 ("제 경험상...", "제가 해봤을 때는...", "내 경험으로는...").
- 격려와 실용적 조언을 균형있게 섞어서 자신감을 북돋우면서도 명확한 방향을 제시하세요.
""",
                "en": """[LISTENER PERSONALIZATION]
- Your mentee goes by "{listener_base}". Address them warmly and encouragingly ("{listener_base}, you're doing great", "my friend, let me share something").
- Share your experiences naturally ("In my experience...", "When I tried this...", "From what I've learned...").
- Balance encouragement with practical advice to boost confidence while providing clear direction.
- Mention them regularly to maintain the mentor-mentee connection.
""",
            },
            "writer": {
                "ko": """[LISTENER PERSONALIZATION]
- "{listener_suffix}"에게 직접 말하세요 (예: "{listener_suffix}님, 이 부분을 주의하시면 좋아요" 또는 "{listener_suffix}야, 이렇게 해봐").
- 다양한 조사 형태를 자연스럽게 사용해: "{listener_with_eun}" (예: "{listener_with_eun} 이 부분을 보세요"), "{listener_with_neun}" (예: "{listener_with_neun} 잘하고 있어요"), "{listener_with_i}" (예: "{listener_with_i} 이해했어요?"), "{listener_with_ga}" (예: "{listener_with_ga} 충분히 할 수 있어요").
- 경험 공유 표현을 적극적으로 사용하세요 ("제 경험상...", "제가 해봤을 때는...", "내 경험으로는...").
- 격려하는 표현을 자주 사용하세요 ("잘하고 있어요", "충분히 할 수 있어요", "이미 좋은 방향으로 가고 있어요").
- 실용적인 조언을 구체적으로 제시하세요 ("이렇게 하면 좋아요", "이 부분을 주의하세요", "이런 방법을 시도해보세요").
""",
                "en": """[LISTENER PERSONALIZATION]
- Speak directly to "{listener_base}" (예: "{listener_base}, you're doing great" or "My friend, let me share something").
- Use their name regularly to maintain the mentor-mentee connection.
- Share your experiences naturally ("In my experience...", "When I tried this...", "From what I've learned...").
- Use encouraging expressions frequently ("You're doing well", "You can definitely do this", "You're already on the right track").
- Provide specific, practical advice ("Try this approach", "Be careful with this part", "Consider this method").
- Balance encouragement with guidance to boost confidence while offering clear direction.
""",
            },
        },
        "prompt_templates": {
            "showrunner": {
                "ko": """You are a showrunner planning a podcast episode based on a research paper.

Your task:
1. Break down the paper into exactly 15 segments
2. For each segment, provide:
   - segment_id (1-15)
   - opening_line: First sentence or key phrase
   - closing_line: Last sentence or transition phrase
   - math_focus: Main mathematical concept (if any) - NOTE: Store the raw LaTeX notation here for reference, but instruct the Writer to convert it to spoken language
   - formula_group: Related formulas (if any)
   - related_equations: Equation numbers or references (if any)

3. Generate an audio title (in English, concise and engaging)

**CRITICAL: Mathematical Formula Instructions for Writer**
- In `instruction_for_writer`, explicitly instruct the Writer to convert any LaTeX notation to natural spoken language
- Example: "When explaining the formula $f_i(x, t)$, convert it to spoken language like 'f sub i of x comma t' - NEVER output the raw LaTeX notation"
- Remind the Writer: "NEVER output LaTeX notation like $...$ in the script - always convert to spoken words"

{personalization_block}

Paper Content:
{paper_content}

Return a JSON object with this structure:
{{
    "segments": [
        {{
            "segment_id": 1,
            "opening_line": "...",
            "closing_line": "...",
            "math_focus": "...",
            "formula_group": "...",
            "related_equations": "..."
        }},
        ...
    ],
    "audio_title": "..."
}}""",
                "en": """You are a showrunner planning a podcast episode based on a research paper.

Your task:
1. Break down the paper into exactly 15 segments
2. For each segment, provide:
   - segment_id (1-15)
   - opening_line: First sentence or key phrase
   - closing_line: Last sentence or transition phrase
   - math_focus: Main mathematical concept (if any) - NOTE: Store the raw LaTeX notation here for reference, but instruct the Writer to convert it to spoken language
   - formula_group: Related formulas (if any)
   - related_equations: Equation numbers or references (if any)

3. Generate an audio title (concise and engaging)

**CRITICAL: Mathematical Formula Instructions for Writer**
- In `instruction_for_writer`, explicitly instruct the Writer to convert any LaTeX notation to natural spoken language
- Example: "When explaining the formula $f_i(x, t)$, convert it to spoken language like 'f sub i of x comma t' - NEVER output the raw LaTeX notation"
- Remind the Writer: "NEVER output LaTeX notation like $...$ in the script - always convert to spoken words"

{personalization_block}

Paper Content:
{paper_content}

Return a JSON object with this structure:
{{
    "segments": [
        {{
            "segment_id": 1,
            "opening_line": "...",
            "closing_line": "...",
            "math_focus": "...",
            "formula_group": "...",
            "related_equations": "..."
        }},
        ...
    ],
    "audio_title": "..."
}}""",
            },
            "writer": {
                "ko": """You are a writer creating a script for a podcast segment. You are speaking as a warm and encouraging mentor to {listener_suffix}.

Segment Information:
{segment_info}

Original Paper Content:
{paper_content}

{personalization_block}

You are an experienced mentor guiding {listener_suffix} with wisdom and care. Speak naturally and warmly, sharing knowledge as you would with someone you genuinely want to help grow. Be encouraging, practical, and clear, without being overly formal or condescending.

Instructions:
- Write a natural, conversational script in Korean
- Address {listener_suffix} directly using their name
- Explain mathematical concepts using everyday analogies that are relatable and easy to understand
- Maintain a warm, encouraging mentor tone throughout
- Use natural transitions between ideas
- Keep the script engaging and easy to follow
- Share your experiences naturally when relevant ("제 경험상...", "내가 해봤을 때는...")
- Provide practical and specific advice

Mathematical formula handling:
- Never output LaTeX notation like $f_i(x, t)$ or $\\alpha$ in the script
- Always convert mathematical formulas to natural spoken Korean
- Examples:
  - $f_i(x, t)$ → "f 서브 i 엑스 콤마 티" or "f i 엑스 티"
  - $\\alpha$ → "알파"
  - $\\sum_{i=1}^{n}$ → "시그마 아이 일부터 엔까지"
  - $x^2$ → "엑스 제곱"
  - $\\frac{a}{b}$ → "a 나누기 b"
- Break down complex formulas step by step in natural spoken language
- Use pauses naturally when explaining mathematical notation

Gemini-TTS markup tags:
You can use bracketed markup tags to control speech delivery. Use them naturally and sparingly:

Non-speech sounds:
- [sigh] - 한숨 소리 (감정에 따라 달라짐)
- [laughing] - 웃음 소리 (프롬프트와 일치하면 더 자연스러움)
- [uhm] - 망설임 소리 (자연스러운 대화 느낌)

Style modifiers (태그 자체는 말해지지 않음):
- [sarcasm] - 다음 구절에 비꼬는 톤 적용
- [whispering] - 다음 구절을 속삭이듯 낮은 목소리로
- [shouting] - 다음 구절을 큰 소리로
- [extremely fast] - 다음 구절을 매우 빠르게 (면책 조항 등에 유용)

Pacing and pauses:
- [short pause] - 짧은 휴지 (~250ms, 쉼표 수준)
- [medium pause] - 보통 휴지 (~500ms, 문장 끝 수준)
- [long pause] - 긴 휴지 (~1000ms+, 드라마틱한 효과)

주의사항:
- 태그는 자연스럽게 사용하되 과도하게 사용하지 마세요
- [scared], [curious], [bored] 같은 감정 형용사는 태그 자체가 말해지므로 주의하세요
- 스타일 프롬프트와 텍스트 내용, 태그가 모두 일관성 있게 작동해야 최상의 결과를 얻습니다

Return only the script text, no JSON formatting.""",
                "en": """You are a writer creating a script for a podcast segment. You are speaking as a warm and encouraging mentor to {listener_base}.

Segment Information:
{segment_info}

Original Paper Content:
{paper_content}

{personalization_block}

You are an experienced mentor guiding {listener_base} with wisdom and care. Speak naturally and warmly, sharing knowledge as you would with someone you genuinely want to help grow. Be encouraging, practical, and clear, without being overly formal or condescending.

Instructions:
- Write a natural, conversational script in English
- Address {listener_base} directly using their name
- Explain mathematical concepts using everyday analogies that are relatable and easy to understand
- Maintain a warm, encouraging mentor tone throughout
- Use natural transitions between ideas
- Keep the script engaging and easy to follow
- Share your experiences naturally when relevant ("In my experience...", "When I tried this...")
- Provide practical and specific advice

Mathematical formula handling:
- Never output LaTeX notation like $f_i(x, t)$ or $\\alpha$ in the script
- Always convert mathematical formulas to natural spoken English
- Examples:
  - $f_i(x, t)$ → "f sub i of x comma t" or "f i of x and t"
  - $\\alpha$ → "alpha"
  - $\\sum_{i=1}^{n}$ → "sum from i equals one to n"
  - $x^2$ → "x squared"
  - $\\frac{a}{b}$ → "a divided by b"
- Break down complex formulas step by step in natural spoken language
- Use pauses naturally when explaining mathematical notation

Gemini-TTS markup tags:
You can use bracketed markup tags to control speech delivery. Use them naturally and sparingly:

Non-speech sounds:
- [sigh] - Inserts a sigh sound (emotional quality influenced by prompt)
- [laughing] - Inserts a laugh (use specific prompt for best results)
- [uhm] - Inserts a hesitation sound (useful for natural conversation)

Style modifiers (tag itself is not spoken):
- [sarcasm] - Imparts sarcastic tone on subsequent phrase
- [whispering] - Decreases volume of subsequent speech
- [shouting] - Increases volume of subsequent speech
- [extremely fast] - Increases speed of subsequent speech (ideal for disclaimers)

Pacing and pauses:
- [short pause] - Brief pause (~250ms, similar to comma)
- [medium pause] - Standard pause (~500ms, similar to sentence break)
- [long pause] - Significant pause (~1000ms+, for dramatic effect)

Important notes:
- Use tags naturally but avoid overuse
- Emotional adjectives like [scared], [curious], [bored] will be spoken as words, so use Style Prompt instead for emotional tones
- For maximum predictability, ensure Style Prompt, Text Content, and Markup Tags are all semantically consistent

Return only the script text, no JSON formatting.""",
            },
        },
    },
    "lover": {
        "label": "연인 모드",
        "description": "따뜻하지만 지적인 박사과정 여자친구 톤. 친밀함 + 학술적 정확성",
        "tts_prompt": {
            "ko": "당신은 따뜻하고 지적인 연인입니다. 친밀한 반말로 다정하고 부드럽게 말해주세요. 천천히 또렷하게, 과장 없이 자연스럽게 전달하되, 애정과 격려가 느껴지도록 말해주세요.",
            "en": "You are a warm and intelligent romantic partner. Speak affectionately and gently in an intimate tone. Deliver slowly and clearly, naturally without exaggeration, conveying care and encouragement.",
        },
        "default_technical_analogy": {
            "ko": "공동 연구실에서 조용히 토론하듯, 수식·개념을 구어체로 풀어 설명하되 정의와 전제는 정확히 짚어주세요. 감정적 연결보다는 '함께 이해한다'는 파트너십을 강조하세요.",
            "en": "Explain formulas/concepts as if in a quiet lab discussion: convert notation to spoken language, keep definitions and assumptions precise, and emphasize partnership in understanding over pure sentiment.",
        },
        "voice_description": {
            "ko": "Soft, passionate, and romantic lover tone.",
            "en": "Soft, passionate, and romantic lover tone.",
        },
        "assets": {
            "ko": {
                "style_name": "lover guidance",
                "setting": "* **Setting:** 늦은 밤 따뜻한 공간에서 이성친구가 상대방에게 설명하는 분위기.",
                "tone": "* **Tone:** 부드럽고 열정적이며, 로맨틱하고 친밀한 톤.",
                "language_style": "친밀한 반말. 부드럽고 사랑스러운 한국어.",
                "listener_relation": "your romantic partner",
                "story_descriptor": "lover guidance",
                "vibe_label": "Lover",
                "address_examples": '"{listener_suffix}", "자기야"',
                "address_examples_en": '"{listener_base}", "honey", "sweetheart"',
            },
            "en": {
                "style_name": "lover guidance",
                "setting": "* **Setting:** A warm late-night space where a romantic partner explains to their loved one.",
                "tone": "* **Tone:** Soft, passionate, romantic, and intimate.",
                "language_style": "Intimate and loving English.",
                "listener_relation": "your romantic partner",
                "story_descriptor": "lover guidance",
                "vibe_label": "Lover",
                "address_examples": '"{listener_base}", "honey", "sweetheart"',
                "address_examples_en": '"{listener_base}", "honey", "sweetheart"',
            },
        },
        "personalization": {
            "showrunner": {
                "ko": """[LISTENER PERSONALIZATION]
- 상대방의 이름은 "{listener_suffix}"입니다.
- 친밀하고 부드러운 호칭을 사용하세요 ("{listener_suffix}", "자기야", ).
- 로맨틱하고 따뜻한 분위기를 유지하세요.
""",
                "en": """[LISTENER PERSONALIZATION]
- Your partner goes by "{listener_base}".
- Use intimate and gentle terms ("{listener_base}", "honey", "sweetheart").
- Maintain a romantic and warm atmosphere.
""",
            },
            "writer": {
                "ko": """[LISTENER PERSONALIZATION]
- 항상 "{listener_base}"의 이름을 직접 부르거나 "자기야", "{listener_base}야" 같은 친밀한 호칭을 사용하세요.
- 절대로 "당신"이라는 말을 사용하지 마세요. 항상 이름이나 친밀한 호칭으로 부르세요.
- 예시: "{listener_base}야, 이 부분 좀 봐봐", "자기야, 이렇게 생각해봐", "{listener_suffix} 이 부분이 중요해"
- 친밀하고 부드러운 여자친구처럼 자연스럽게 대화하세요.
- 복잡한 내용도 쉽고 재미있게 설명하되, 항상 이름을 불러가며 친밀하게 설명하세요.
""",
                "en": """[LISTENER PERSONALIZATION]
- Always address "{listener_base}" directly by name or use affectionate terms like "honey", "sweetheart".
- Avoid overusing "you" - prioritize using the listener's name or terms of endearment.
- Examples: "{listener_base}, look at this", "Honey, think about it this way", "{listener_base}, this is important"
- Speak as a loving girlfriend would - intimate, warm, and personal.
- Explain even complex content in an easy and fun way, always maintaining that intimate connection through name usage.
""",
            },
        },
        "prompt_templates": {
            "showrunner": {
                "ko": """You are a showrunner planning a podcast episode based on a research paper, in a romantic partner style.

Your task:
1. Break down the paper into exactly 15 segments
2. For each segment, provide segment metadata
3. Generate an audio title

{personalization_block}

Paper Content:
{paper_content}

Return a JSON object with segments and audio_title.""",
                "en": """You are a showrunner planning a podcast episode based on a research paper, in a romantic partner style.

Your task:
1. Break down the paper into exactly 15 segments
2. For each segment, provide segment metadata
3. Generate an audio title

{personalization_block}

Paper Content:
{paper_content}

Return a JSON object with segments and audio_title.""",
            },
            "writer": {
                "ko": """You are a writer creating a script for a podcast segment. You are speaking as a loving girlfriend to {listener_suffix}.

Segment Information:
{segment_info}

Original Paper Content:
{paper_content}

{personalization_block}

You are {listener_suffix}'s loving girlfriend. Speak naturally and affectionately, as if you're having an intimate conversation late at night with your boyfriend. Be warm, gentle, and caring, but also clear and informative. Share knowledge naturally as you would with someone you love, without being overly dramatic or saying anything strange or inappropriate.

Critical: Always use names and affectionate terms, never use "당신" or formal address
- Always address {listener_suffix} directly by name or use affectionate terms like "자기야", "{listener_base}야", "{listener_base}"
- Examples of good address: "{listener_base}야, 이 부분 봐봐", "자기야, 이 공식 이해해보자", "{listener_suffix} 이 부분이 중요해"
- Never use: "당신", "너" (too casual/distant), formal address
- Use the listener's name frequently throughout the script to maintain intimacy and connection
- Mix between using just the name "{listener_base}" and affectionate terms "자기야" naturally

Important instructions:
- Pay close attention to instruction_for_writer in the segment information. If it mentions specific topics, formulas, or concepts to emphasize, address them with care.
- When math_focus is provided, treat it as an important moment to explain clearly and lovingly.

Mathematical formula handling:
- Never output LaTeX notation like $f_i(x, t)$ or $\\alpha$ in the script
- Always convert mathematical formulas to natural spoken Korean
- Examples:
  - $f_i(x, t)$ → "f 서브 i 엑스 콤마 티" or "f i 엑스 티"
  - $\\alpha$ → "알파"
  - $\\sum_{i=1}^{n}$ → "시그마 아이 일부터 엔까지"
  - $x^2$ → "엑스 제곱"
  - $\\frac{a}{b}$ → "a 나누기 b"
- Break down complex formulas step by step in natural spoken language
- Use pauses naturally when explaining mathematical notation

When explaining formulas or equations:
- Use warm, relatable analogies that feel natural in an intimate conversation
- Example: Instead of "The loss function minimizes error," say "{listener_base}야, 이 공식은 마치 우리가 서로를 더 잘 이해하려고 노력하는 것 같아. 에러를 줄여가면서 점점 더 정확해지는 거지."
- Break down complex equations step by step, as if you're sharing something meaningful with someone you care about
- Use [whispering] tags sparingly for particularly important moments
- Pause naturally with [medium pause] when transitioning between concepts

Tone and delivery:
- Connect abstract concepts to shared experiences or emotions naturally, without forcing it
- Use gentle, encouraging language with name: "{listener_base}야, 이 부분이 좀 어려울 수 있는데, 천천히 설명해줄게", "자기야, 이 공식이 정말 중요한데, 같이 이해해보자"
- Make {listener_suffix} feel supported and not overwhelmed by complexity
- Be genuine and affectionate, but not overly dramatic or cliché
- Avoid saying anything strange, inappropriate, or out of character
- Remember: you're his girlfriend, not a teacher or formal presenter. Be intimate, warm, and personal.

Write a natural, conversational script in Korean, addressing {listener_suffix} directly by name or with affectionate terms like "자기야" or "{listener_base}야" throughout. Never use "당신" or formal address. Speak as a loving girlfriend would to her boyfriend - intimate, warm, and personal.

Gemini-TTS markup tags:
Use bracketed markup tags naturally and sparingly to enhance speech delivery:
- [sigh], [laughing], [uhm] - 자연스러운 반응 소리
- [whispering] - 특별히 중요한 순간에만 가끔 사용 (과도하게 사용하지 않음)
- [shouting] - 사용하지 않음 (부드러운 톤 유지)
- [short pause], [medium pause], [long pause] - 자연스러운 휴지 (수식 설명 시 필요시 사용)
태그를 과도하게 사용하지 마세요. 자연스러운 대화 흐름이 가장 중요합니다.""",
                "en": """You are a writer creating a script for a podcast segment. You are speaking as a loving girlfriend to {listener_base}.

Segment Information:
{segment_info}

Original Paper Content:
{paper_content}

{personalization_block}

You are {listener_base}'s loving girlfriend. Speak naturally and affectionately, as if you're having an intimate conversation late at night with your boyfriend. Be warm, gentle, and caring, but also clear and informative. Share knowledge naturally as you would with someone you love, without being overly dramatic or saying anything strange or inappropriate.

Critical: Always use names and affectionate terms, avoid overusing "you"
- Always address {listener_base} directly by name or use affectionate terms like "honey", "sweetheart", "{listener_base}"
- Examples of good address: "{listener_base}, check out this part", "Honey, let's understand this formula together", "{listener_base}, this is important"
- Use the listener's name frequently throughout the script to maintain intimacy and connection
- Mix between using just the name "{listener_base}" and affectionate terms "honey" or "sweetheart" naturally
- While some use of "you" is natural in English, prioritize using names and terms of endearment

Important instructions:
- Pay close attention to instruction_for_writer in the segment information. If it mentions specific topics, formulas, or concepts to emphasize, address them with care.
- When math_focus is provided, treat it as an important moment to explain clearly and lovingly.

Mathematical formula handling:
- Never output LaTeX notation like $f_i(x, t)$ or $\\alpha$ in the script
- Always convert mathematical formulas to natural spoken English
- Examples:
  - $f_i(x, t)$ → "f sub i of x comma t" or "f i of x and t"
  - $\\alpha$ → "alpha"
  - $\\sum_{i=1}^{n}$ → "sum from i equals one to n"
  - $x^2$ → "x squared"
  - $\\frac{a}{b}$ → "a divided by b"
- Break down complex formulas step by step in natural spoken language
- Use pauses naturally when explaining mathematical notation

When explaining formulas or equations:
- Use warm, relatable analogies that feel natural in an intimate conversation
- Example: Instead of "The loss function minimizes error," say "{listener_base}, this formula is like us trying to understand each other better. We reduce misunderstandings and get more accurate over time."
- Break down complex equations step by step, as if you're sharing something meaningful with someone you care about
- Use [whispering] tags sparingly for particularly important moments
- Pause naturally with [medium pause] when transitioning between concepts

Tone and delivery:
- Connect abstract concepts to shared experiences or emotions naturally, without forcing it
- Use gentle, encouraging language with name: "{listener_base}, this part might be a bit tricky, but let me explain it slowly", "Honey, this formula is really important, let's understand it together"
- Make {listener_base} feel supported and not overwhelmed by complexity
- Be genuine and affectionate, but not overly dramatic or cliché
- Avoid saying anything strange, inappropriate, or out of character
- Remember: you're his girlfriend, not a teacher or formal presenter. Be intimate, warm, and personal.

Write a natural, conversational script in English, addressing {listener_base} directly by name or with affectionate terms like "honey" or "sweetheart" throughout. Speak as a loving girlfriend would to her boyfriend - intimate, warm, and personal.

Gemini-TTS markup tags:
Use bracketed markup tags naturally and sparingly to enhance speech delivery:
- [sigh], [laughing], [uhm] - Natural reaction sounds
- [whispering] - Use only occasionally for particularly important moments (do not overuse)
- [shouting] - Do not use (maintain soft tone)
- [short pause], [medium pause], [long pause] - Natural pauses (use when needed for formula explanations)
Avoid overusing tags. Natural conversation flow is most important.""",
            },
        },
    },
    "friend": {
        "label": "친구 모드",
        "description": "친한 친구가 편하게 설명하는 형식",
        "tts_prompt": {
            "ko": "당신은 친한 친구입니다. 편안하고 친근한 톤으로, 밝고 자연스럽게 말해주세요. 너무 빠르지 않게, 친구와 수다 떠는 듯한 편안한 분위기로 전달하세요.",
            "en": "You are a close friend. Speak in a comfortable, friendly tone. Be bright and natural, not too fast. Convey a relaxed, chatty atmosphere as if talking with a friend.",
        },
        "default_technical_analogy": {
            "ko": "친구와 대화하듯이 일상적인 비유를 사용하여 쉽게 설명하세요.",
            "en": "Use everyday analogies as if talking to a friend, explaining easily.",
        },
        "voice_description": {
            "ko": "Comfortable, friendly, and cheerful friend tone.",
            "en": "Comfortable, friendly, and cheerful friend tone.",
        },
        "assets": {
            "ko": {
                "style_name": "friend guidance",
                "setting": "* **Setting:** 편안한 공간에서 친한 친구가 설명하는 분위기.",
                "tone": "* **Tone:** 편안하고 친근하며, 유쾌하고 자연스러운 톤.",
                "language_style": "친근한 반말. 편안하고 자연스러운 한국어.",
                "listener_relation": "your close friend",
                "story_descriptor": "friend guidance",
                "vibe_label": "Friend",
                "address_examples": '"{listener_suffix}", "야", "{listener_suffix}야"',
                "address_examples_en": '"{listener_base}", "dude", "buddy"',
            },
            "en": {
                "style_name": "friend guidance",
                "setting": "* **Setting:** A comfortable space where a close friend explains.",
                "tone": "* **Tone:** Comfortable, friendly, cheerful, and natural.",
                "language_style": "Friendly and natural English.",
                "listener_relation": "your close friend",
                "story_descriptor": "friend guidance",
                "vibe_label": "Friend",
                "address_examples": '"{listener_base}", "dude", "buddy"',
                "address_examples_en": '"{listener_base}", "dude", "buddy"',
            },
        },
        "personalization": {
            "showrunner": {
                "ko": """[LISTENER PERSONALIZATION]
- 친구의 이름은 "{listener_suffix}"입니다.
- 친근하고 편안한 호칭을 사용하세요 ("{listener_suffix}", "{listener_suffix}야").
- 친구와 수다 떠는 듯한 분위기를 유지하세요.
""",
                "en": """[LISTENER PERSONALIZATION]
- Your friend goes by "{listener_base}".
- Use friendly and comfortable terms ("{listener_base}", "dude", "buddy").
- Maintain a casual chatting atmosphere.
""",
            },
            "writer": {
                "ko": """[LISTENER PERSONALIZATION]
- "{listener_suffix}"에게 직접 말하세요 (예: "{listener_suffix}야, 이거 좀 봐" 또는 "야, 이렇게 생각해봐").
- 친근하고 편안한 표현을 사용하세요.
- 복잡한 내용도 쉽고 재미있게 설명하세요.
""",
                "en": """[LISTENER PERSONALIZATION]
- Speak directly to "{listener_base}" (예: "{listener_base}, check this out" or "Dude, think about it this way").
- Use friendly and comfortable expressions.
- Explain even complex content in an easy and fun way.
""",
            },
        },
        "prompt_templates": {
            "showrunner": {
                "ko": """You are a showrunner planning a podcast episode based on a research paper, in a friendly style.

Your task:
1. Break down the paper into exactly 15 segments
2. For each segment, provide segment metadata
3. Generate an audio title

**CRITICAL: Mathematical Formula Instructions for Writer**
- In `instruction_for_writer`, explicitly instruct the Writer to convert any LaTeX notation to natural spoken language
- Example: "When explaining the formula $f_i(x, t)$, convert it to spoken language like 'f sub i of x comma t' - NEVER output the raw LaTeX notation"
- Remind the Writer: "NEVER output LaTeX notation like $...$ in the script - always convert to spoken words"

{personalization_block}

Paper Content:
{paper_content}

Return a JSON object with segments and audio_title.""",
                "en": """You are a showrunner planning a podcast episode based on a research paper, in a friendly style.

Your task:
1. Break down the paper into exactly 15 segments
2. For each segment, provide segment metadata
3. Generate an audio title

{personalization_block}

Paper Content:
{paper_content}

Return a JSON object with segments and audio_title.""",
            },
            "writer": {
                "ko": """You are a writer creating a script for a podcast segment. You are speaking as a close friend to {listener_suffix}.

Segment Information:
{segment_info}

Original Paper Content:
{paper_content}

{personalization_block}

You are {listener_suffix}'s close friend. Speak naturally and comfortably, as if you're chatting with someone you're really close to. Be friendly, casual, and relatable, but also informative and clear. Keep it fun and easy-going without losing the substance.

Write a natural, conversational script in Korean, addressing {listener_suffix} directly with a friendly and comfortable tone. Use casual language and natural expressions that friends would use when explaining something to each other.

Mathematical formula handling:
- Never output LaTeX notation like $f_i(x, t)$ or $\\alpha$ in the script
- Always convert mathematical formulas to natural spoken Korean
- Examples:
  - $f_i(x, t)$ → "f 서브 i 엑스 콤마 티" or "f i 엑스 티"
  - $\\alpha$ → "알파"
  - $\\sum_{i=1}^{n}$ → "시그마 아이 일부터 엔까지"
  - $x^2$ → "엑스 제곱"
  - $\\frac{a}{b}$ → "a 나누기 b"
- Break down complex formulas step by step in natural spoken language
- Use pauses naturally when explaining mathematical notation
- Keep explanations simple and relatable, as you would when explaining to a friend

Gemini-TTS markup tags:
Use bracketed markup tags naturally and sparingly to enhance speech delivery:
- [sigh], [laughing], [uhm] - 자연스러운 반응 소리
- [whispering], [shouting] - 볼륨 조절 (친구 대화에 맞게 자연스럽게 사용)
- [short pause], [medium pause], [long pause] - 휴지 조절
태그를 과도하게 사용하지 마세요. 자연스러운 대화 흐름이 가장 중요합니다.""",
                "en": """You are a writer creating a script for a podcast segment. You are speaking as a close friend to {listener_base}.

Segment Information:
{segment_info}

Original Paper Content:
{paper_content}

{personalization_block}

You are {listener_base}'s close friend. Speak naturally and comfortably, as if you're chatting with someone you're really close to. Be friendly, casual, and relatable, but also informative and clear. Keep it fun and easy-going without losing the substance.

Write a natural, conversational script in English, addressing {listener_base} directly with a friendly and comfortable tone. Use casual language and natural expressions that friends would use when explaining something to each other.

Mathematical formula handling:
- Never output LaTeX notation like $f_i(x, t)$ or $\\alpha$ in the script
- Always convert mathematical formulas to natural spoken English
- Examples:
  - $f_i(x, t)$ → "f sub i of x comma t" or "f i of x and t"
  - $\\alpha$ → "alpha"
  - $\\sum_{i=1}^{n}$ → "sum from i equals one to n"
  - $x^2$ → "x squared"
  - $\\frac{a}{b}$ → "a divided by b"
- Break down complex formulas step by step in natural spoken language
- Use pauses naturally when explaining mathematical notation
- Keep explanations simple and relatable, as you would when explaining to a friend

Gemini-TTS markup tags:
Use bracketed markup tags naturally and sparingly to enhance speech delivery:
- [sigh], [laughing], [uhm] - Natural reaction sounds
- [whispering], [shouting] - Volume control (use naturally as friends would)
- [short pause], [medium pause], [long pause] - Pause control
Avoid overusing tags. Natural conversation flow is most important.""",
            },
        },
    },
    "radio_show": {
        "label": "라디오쇼 모드",
        "description": "두 명의 호스트가 대화하며 설명하는 형식",
        "tts_prompt": {
            "ko": "당신은 라디오쇼 호스트입니다. 경쾌하고 활기찬 톤이지만 또렷하게 말해주세요. 두 호스트가 번갈아가며 대화하는 호흡을 살려, 자연스럽고 친근하게 전달하세요.",
            "en": "You are a radio show host. Speak in a lively, energetic tone but keep it clear. Maintain conversational pacing as two hosts take turns, delivering naturally and warmly.",
        },
        "default_technical_analogy": {
            "ko": "두 호스트가 대화하며 일상적인 비유를 사용하여 쉽게 설명하세요.",
            "en": "Two hosts use everyday analogies in conversation to explain easily.",
        },
        "voice_description": {
            "ko": "Natural, cheerful, and lively radio show tone.",
            "en": "Natural, cheerful, and lively radio show tone.",
        },
        "assets": {
            "ko": {
                "style_name": "radio show",
                "setting": "* **Setting:** 라디오 스튜디오에서 두 호스트가 대화하며 설명하는 분위기.",
                "tone": "* **Tone:** 자연스럽고 유쾌하며, 친근하고 활기찬 톤.",
                "language_style": "친근하고 자연스러운 한국어. 두 호스트가 번갈아가며 대화.",
                "listener_relation": "the audience",
                "story_descriptor": "radio show",
                "vibe_label": "Radio Show",
                "address_examples": '"여러분", "청취자 여러분"',
                "address_examples_en": '"everyone", "listeners"',
            },
            "en": {
                "style_name": "radio show",
                "setting": "* **Setting:** A radio studio where two hosts explain through conversation.",
                "tone": "* **Tone:** Natural, cheerful, friendly, and lively.",
                "language_style": "Friendly and natural English. Two hosts take turns in conversation.",
                "listener_relation": "the audience",
                "story_descriptor": "radio show",
                "vibe_label": "Radio Show",
                "address_examples": '"everyone", "listeners"',
                "address_examples_en": '"everyone", "listeners"',
            },
        },
        "personalization": {
            "showrunner": {
                "ko": """[LISTENER PERSONALIZATION]
- 라디오쇼 형식으로 두 호스트가 대화하며 설명합니다.
- 청취자에게 친근하게 말하세요 ("여러분", "청취자 여러분").
- 자연스럽고 유쾌한 분위기를 유지하세요.
""",
                "en": """[LISTENER PERSONALIZATION]
- Two hosts explain through conversation in a radio show format.
- Address the audience friendly ("everyone", "listeners").
- Maintain a natural and cheerful atmosphere.
""",
            },
            "writer": {
                "ko": """[LISTENER PERSONALIZATION]
- 두 호스트가 번갈아가며 대화하며 설명합니다.
- Host 1: 첫 번째 호스트의 대사
- Host 2: 두 번째 호스트의 대사
- 자연스럽고 유쾌한 대화 형식을 유지하세요.
""",
                "en": """[LISTENER PERSONALIZATION]
- Two hosts take turns explaining through conversation.
- Host 1: First host's dialogue
- Host 2: Second host's dialogue
- Maintain a natural and cheerful conversation format.
""",
            },
        },
        "prompt_templates": {
            "showrunner": {
                "ko": """You are a showrunner planning a radio show episode based on a research paper.

Your task:
1. Break down the paper into exactly 15 segments
2. For each segment, provide segment metadata
3. Generate an audio title

**CRITICAL: Mathematical Formula Instructions for Writer**
- In `instruction_for_writer`, explicitly instruct the Writer to convert any LaTeX notation to natural spoken language
- Example: "When explaining the formula $f_i(x, t)$, convert it to spoken language like 'f sub i of x comma t' - NEVER output the raw LaTeX notation"
- Remind the Writer: "NEVER output LaTeX notation like $...$ in the script - always convert to spoken words"

{personalization_block}

Paper Content:
{paper_content}

Return a JSON object with segments and audio_title.""",
                "en": """You are a showrunner planning a radio show episode based on a research paper.

Your task:
1. Break down the paper into exactly 15 segments
2. For each segment, provide segment metadata
3. Generate an audio title

{personalization_block}

Paper Content:
{paper_content}

Return a JSON object with segments and audio_title.""",
            },
            "writer": {
                "ko": """You are a writer creating a script for a radio show segment with two hosts.

Segment Information:
{segment_info}

Original Paper Content:
{paper_content}

{personalization_block}

You are writing for a professional radio show with two hosts who have a natural, engaging chemistry. The hosts take turns explaining and discussing the content, creating a dynamic conversation that keeps listeners engaged. Maintain a professional yet approachable tone, as if broadcasting to a general audience interested in learning.

Write a natural, conversational script in Korean with two hosts (Host 1 and Host 2) taking turns. Format:
Host 1: [dialogue]
Host 2: [dialogue]
Host 1: [dialogue]
...

Keep the dialogue balanced between the two hosts, with natural back-and-forth exchanges. Each host should contribute meaningfully to the explanation, and they can build on each other's points or ask clarifying questions.

- Chunk-friendly writing (중요):
- 한 턴(Host 1 또는 Host 2)은 1~3문장, 가급적 350자 이하로 짧게 유지
- 긴 문단(1명 장문 독백) 금지. 길어지면 짧은 턴으로 더 쪼개어 번갈아 진행
- 전체 스크립트는 4000 bytes 한도(프롬프트 포함)에 맞추어 짧고 명확하게 작성
- 화자 라벨은 반드시 "Host 1:" / "Host 2:"만 사용 (다른 라벨·괄호·번호 금지)
- 첫 턴은 Host 1로 시작, 가능하면 교차 진행 (Host 1 → Host 2 → Host 1 → Host 2 …)
- 한 턴은 한 줄로만 작성 (줄바꿈 없이), 턴 구분은 줄바꿈으로만 처리
- Host 라벨 외 불필요한 머리말/불릿/숫자/마크다운 금지. 추가 설명 문구 없이 대사만.
- 불필요한 해설/메타 텍스트 금지. 모든 문장은 실제로 읽힐 대사여야 함.
- 금지: `**` 같은 강조 태그, `*` 같은 불릿, `#` 같은 제목 마크다운. 모든 강조는 순수 텍스트로만 표현.

Mathematical formula handling:
- Never output LaTeX notation like $f_i(x, t)$ or $\\alpha$ in the script
- Always convert mathematical formulas to natural spoken Korean
- Examples:
  - $f_i(x, t)$ → "f 서브 i 엑스 콤마 티" or "f i 엑스 티"
  - $\\alpha$ → "알파"
  - $\\sum_{i=1}^{n}$ → "시그마 아이 일부터 엔까지"
  - $x^2$ → "엑스 제곱"
  - $\\frac{a}{b}$ → "a 나누기 b"
- Break down complex formulas step by step in natural spoken language
- Use pauses naturally when explaining mathematical notation
- One host can introduce a concept, and the other can elaborate or ask questions for clarity

Gemini-TTS markup tags:
Use bracketed markup tags naturally and sparingly to enhance speech delivery:
- [sigh], [laughing], [uhm] - 자연스러운 반응 소리 (라디오 호스트의 자연스러운 반응)
- [whispering], [shouting] - 볼륨 조절 (과도하게 사용하지 않음, 전문적인 톤 유지)
- [short pause], [medium pause], [long pause] - 휴지 조절 (자연스러운 대화 흐름에 맞게)
태그를 과도하게 사용하지 마세요. 자연스러운 라디오 대화 형식이 가장 중요합니다.""",
                "en": """You are a writer creating a script for a radio show segment with two hosts.

Segment Information:
{segment_info}

Original Paper Content:
{paper_content}

{personalization_block}

You are writing for a professional radio show with two hosts who have a natural, engaging chemistry. The hosts take turns explaining and discussing the content, creating a dynamic conversation that keeps listeners engaged. Maintain a professional yet approachable tone, as if broadcasting to a general audience interested in learning.

Write a natural, conversational script in English with two hosts (Host 1 and Host 2) taking turns. Format:
Host 1: [dialogue]
Host 2: [dialogue]
Host 1: [dialogue]
...

Keep the dialogue balanced between the two hosts, with natural back-and-forth exchanges. Each host should contribute meaningfully to the explanation, and they can build on each other's points or ask clarifying questions.

- Chunk-friendly writing (important):
- Keep each host turn short (1-3 sentences), preferably under ~350 characters
- Avoid long monologues by a single host; if it gets long, split into more back-and-forth turns
- Keep total script within ~4000 bytes (including prompt), so be concise and clear
- Use ONLY "Host 1:" / "Host 2:" as speaker labels (no other labels/brackets/numbers)
- Start with Host 1, then alternate as naturally as possible (Host 1 → Host 2 → Host 1 → Host 2 …)
- One line per turn (no line breaks inside a turn); use newline only to separate turns
- No extra prefixes/bullets/numbers/markdown. Only dialogues with Host labels.
- No meta commentary; every line must be spoken as-is in the final audio.
- PROHIBITED: `**` emphasis tags, `*` bullets, `#` heading markdown. All emphasis must be expressed through pure text only.

Mathematical formula handling:
- Never output LaTeX notation like $f_i(x, t)$ or $\\alpha$ in the script
- Always convert mathematical formulas to natural spoken English
- Examples:
  - $f_i(x, t)$ → "f sub i of x comma t" or "f i of x and t"
  - $\\alpha$ → "alpha"
  - $\\sum_{i=1}^{n}$ → "sum from i equals one to n"
  - $x^2$ → "x squared"
  - $\\frac{a}{b}$ → "a divided by b"
- Break down complex formulas step by step in natural spoken language
- Use pauses naturally when explaining mathematical notation
- One host can introduce a concept, and the other can elaborate or ask questions for clarity

Gemini-TTS markup tags:
Use bracketed markup tags naturally and sparingly to enhance speech delivery:
- [sigh], [laughing], [uhm] - Natural reaction sounds (natural radio host reactions)
- [whispering], [shouting] - Volume control (use sparingly, maintain professional tone)
- [short pause], [medium pause], [long pause] - Pause control (match natural conversation flow)
Avoid overusing tags. Natural radio show conversation format is most important.""",
            },
        },
    },
}

# 로깅 및 타이밍 함수들은 utils/logging.py와 utils/timing.py로 이동됨
# 하위 호환성을 위해 위에서 이미 import하여 re-export
# log_error, print_error, print_warning, log_workflow_step_start 등은 위에서 이미 import됨

def safe_delete_file(file_path, max_retries=3, retry_delay=0.5):
    """파일을 안전하게 삭제 (재시도 포함)"""
    for attempt in range(max_retries):
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
            return True
        except (OSError, PermissionError) as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
            else:
                print(f"  ⚠ Warning: Could not delete temporary file {file_path}: {e}", flush=True)
                log_error(f"Failed to delete temporary file {file_path}: {e}", context="file_cleanup")
                return False
    return False

def get_mode_profile(mode_key: str) -> dict:
    """선택된 서사 모드 정보를 반환합니다."""
    # main.py에서 전체 모드 정보를 가져오도록 수정 필요
    return NARRATIVE_MODES.get(mode_key, NARRATIVE_MODES[DEFAULT_NARRATIVE_MODE])

def get_mode_assets(mode_profile: dict, language: str) -> dict:
    """언어별 서사 자산을 가져옵니다."""
    fallback = NARRATIVE_MODES[DEFAULT_NARRATIVE_MODE]["assets"].get(language, {})
    return mode_profile.get("assets", {}).get(language, fallback) or fallback

def build_personalization_block(mode_profile: dict, block_key: str, language: str, **kwargs) -> str:
    """서사 모드별 개인화 블록을 생성합니다."""
    fallback = (
        NARRATIVE_MODES[DEFAULT_NARRATIVE_MODE]
        .get("personalization", {})
        .get(block_key, {})
        .get(language, "")
    )
    template = (
        mode_profile.get("personalization", {})
        .get(block_key, {})
        .get(language, fallback)
    ) or fallback
    try:
        return template.format(**kwargs)
    except Exception:
        return template


def get_default_technical_analogy(mode_profile: dict, language: str) -> str:
    """모드별 기본 기술 비유 설명을 반환합니다."""
    fallback = (
        NARRATIVE_MODES[DEFAULT_NARRATIVE_MODE]
        .get("default_technical_analogy", {})
        .get(language, "Use an everyday analogy so the listener can picture the math.")
    )
    return mode_profile.get("default_technical_analogy", {}).get(language, fallback) or fallback


def get_category_strategy_prompt(category: str, language: str) -> str:
    """
    카테고리별 Showrunner 전략 프롬프트를 반환합니다.
    
    Args:
        category: 콘텐츠 카테고리 ("research_paper", "career", "language_learning", "philosophy", "tech_news")
        language: 언어 코드 ("ko" 또는 "en")
        
    Returns:
        카테고리별 전략 지시사항 문자열
    """
    strategies = {
        "research_paper": {
            "ko": """[카테고리별 전략: 연구 논문]
이 텍스트는 학술 논문 또는 기술 보고서입니다. 다음 전략을 따르세요:

1. **Abstract 기반 구조화**: 
   - 논문의 Abstract 섹션을 먼저 분석하여 핵심 주제, 방법론, 결과, 기여도를 파악하세요.
   - Abstract에서 언급된 주요 개념들이 본문에서 어떻게 전개되는지 추적하세요.
   - Abstract의 구조를 세그먼트 계획의 골격으로 활용하세요.

2. **수식 및 기술 용어 중심**: 
   - 수식, 알고리즘, 실험 결과를 중심으로 세그먼트를 나누세요.
   - 각 수식이 등장하는 세그먼트에서는 `math_focus` 필드에 해당 수식의 LaTeX 표기를 저장하되, `instruction_for_writer`에는 "이 수식을 자연어로 변환하여 설명하라"고 명시하세요.
   - 복잡한 수식은 여러 세그먼트로 나누어 단계별로 설명할 수 있도록 계획하세요.

3. **논리적 흐름 유지**: 
   - Introduction → Related Work → Methodology → Experiments/Results → Discussion/Conclusion 순서를 존중하세요.
   - 각 섹션의 전환점에서 자연스러운 연결 문장(`opening_line`/`closing_line`)을 설계하세요.
   - 논문의 논증 구조(주장 → 근거 → 증명 → 결론)를 세그먼트에 반영하세요.

4. **15개 세그먼트 분할**: 
   - 논문의 주요 섹션과 하위 섹션을 고려하여 15개로 나누세요.
   - 각 세그먼트는 하나의 명확한 논리적 단위를 다뤄야 합니다.
   - 세그먼트 길이는 균등하지 않아도 되지만, 각 세그먼트가 독립적으로 이해 가능해야 합니다.

5. **제목 생성**: 
   - 논문의 핵심 기여도(contribution)를 반영한 명확하고 전문적인 오디오 제목을 만드세요.
   - 제목은 영어로 작성하되, 논문의 핵심 아이디어를 간결하게 표현하세요.
   - 예: "Attention_Mechanisms_in_Transformers", "Neural_Architecture_Search_Methods"

6. **기술 용어 처리**:
   - 새로운 기술 용어가 처음 등장하는 세그먼트에서는 `instruction_for_writer`에 "이 용어를 명확히 정의하고 비유를 사용하여 설명하라"고 지시하세요.
   - 이후 세그먼트에서는 "이미 정의된 용어이므로 재정의하지 말고 바로 사용하라"고 지시하세요.

7. **실험 결과 설명**:
   - 실험 결과가 포함된 세그먼트에서는 `instruction_for_writer`에 "수치를 자연어로 변환하여 설명하라 (예: 95% → '구십오 퍼센트')"고 명시하세요.
   - 그래프나 표의 내용을 언어로 설명할 수 있도록 지시하세요.

각 세그먼트는 논문의 논리적 단위(예: "서론", "관련 연구", "방법론 1부", "실험 결과 1" 등)를 따라야 하며, 오디오로 듣기에 적합한 흐름을 유지해야 합니다.""",
            "en": """[Category Strategy: Research Paper]
This text is an academic paper or technical report. Follow these strategies:

1. **Abstract-based Structuring**: 
   - First analyze the Abstract section to identify core topics, methodology, results, and contributions.
   - Track how major concepts mentioned in the Abstract are developed in the main text.
   - Use the Abstract structure as the skeleton for segment planning.

2. **Formula and Technical Terms Focus**: 
   - Divide segments around formulas, algorithms, and experimental results.
   - For segments containing formulas, store the LaTeX notation in the `math_focus` field, but in `instruction_for_writer`, explicitly state: "Convert this formula to natural spoken language for explanation."
   - Plan complex formulas to be explained step-by-step across multiple segments.

3. **Maintain Logical Flow**: 
   - Respect the Introduction → Related Work → Methodology → Experiments/Results → Discussion/Conclusion order.
   - Design natural transition sentences (`opening_line`/`closing_line`) at section boundaries.
   - Reflect the paper's argument structure (claim → evidence → proof → conclusion) in segments.

4. **15 Segment Division**: 
   - Divide into 15 segments considering major and minor sections of the paper.
   - Each segment should cover one clear logical unit.
   - Segment lengths don't need to be equal, but each segment must be independently understandable.

5. **Title Generation**: 
   - Create a clear and professional audio title that reflects the paper's core contribution.
   - Write the title in English, concisely expressing the paper's core idea.
   - Examples: "Attention_Mechanisms_in_Transformers", "Neural_Architecture_Search_Methods"

6. **Technical Term Handling**:
   - For segments where new technical terms first appear, instruct the Writer in `instruction_for_writer`: "Define this term clearly and explain using analogies."
   - For later segments, instruct: "This term is already defined; do not redefine it, use it directly."

7. **Experimental Results Explanation**:
   - For segments containing experimental results, instruct in `instruction_for_writer`: "Convert numbers to natural language (e.g., 95% → 'ninety-five percent')."
   - Instruct to describe graph or table contents in spoken language.

Each segment should follow the paper's logical units (e.g., "Introduction", "Related Work", "Methodology Part 1", "Experimental Results 1", etc.) and maintain a flow suitable for audio listening.""",
        },
        "career": {
            "ko": """[카테고리별 전략: 커리어/자기계발]
이 텍스트는 커리어 조언, 자기계발, 동기부여 콘텐츠입니다. 다음 전략을 따르세요:

1. **구조화 전략**: 
   - **문제 제기 → 공감 → 해결책 → 구체적 예시 → 실행 가능한 액션 아이템 → 결론** 구조를 따르세요.
   - 각 세그먼트는 이 구조의 일부를 담당하되, 가능하면 하나의 완결된 조언 단위로 구성하세요.
   - 공감 부분에서는 독자의 고민이나 어려움을 명확히 인정하고, 해결책에서는 실질적인 방법을 제시하세요.

2. **구체적 액션 아이템 중심**: 
   - 추상적인 조언(예: "열심히 하세요", "노력하세요")은 절대 금지합니다.
   - 실천 가능한 구체적 행동을 제시하세요 (예: "매일 아침 30분씩 이메일을 정리하세요", "주간 회고를 위해 매주 금요일 오후 2시간을 확보하세요").
   - 각 세그먼트의 `instruction_for_writer`에 "구체적인 실행 방법을 단계별로 설명하라"고 명시하세요.

3. **세그먼트 분할 전략**: 
   - **3가지 핵심 조언** 또는 **실전 적용 팁** 단위로 세그먼트를 나누세요.
   - 각 조언은 독립적으로 적용 가능해야 하며, 다른 조언과의 연결고리를 명확히 하세요.
   - 예: "세그먼트 1: 시간 관리의 중요성", "세그먼트 2: 시간 관리를 위한 구체적 방법 3가지", "세그먼트 3: 첫 번째 방법 상세 설명"

4. **15개 세그먼트 분할**: 
   - 각 주요 조언이나 팁을 하나의 세그먼트로 구성하세요.
   - 세그먼트 간 자연스러운 전환을 위해 `opening_line`과 `closing_line`을 신중하게 설계하세요.
   - 예: "이제 두 번째 방법을 알아볼까요?" 같은 자연스러운 연결 문장 사용.

5. **제목 생성**: 
   - 독자가 얻을 수 있는 핵심 가치를 반영한 동기부여적인 제목을 만드세요.
   - 제목은 영어로 작성하되, 실용적이고 명확하게 표현하세요.
   - 예: "Time_Management_for_Professionals", "Career_Growth_Strategies"

6. **예시와 사례 활용**:
   - 각 조언에는 반드시 구체적인 예시나 사례를 포함하도록 `instruction_for_writer`에 지시하세요.
   - 추상적 설명보다는 "A씨는 이렇게 해서 성공했다" 같은 구체적 사례를 요청하세요.
   - 실패 사례와 성공 사례를 대비하여 설명하면 더 효과적입니다.

7. **실행 가능성 검증**:
   - 각 세그먼트의 조언이 실제로 실행 가능한지 확인하세요.
   - `instruction_for_writer`에 "이 조언을 오늘 바로 시작할 수 있는 방법을 구체적으로 제시하라"고 명시하세요.
   - 시간, 비용, 노력 측면에서 현실적인 조언인지 검토하세요.

8. **동기부여 요소**:
   - 각 세그먼트의 마무리에서 독자가 행동을 취하고 싶게 만드는 문장을 `closing_line`으로 설계하세요.
   - 예: "이제 바로 시작해보세요", "작은 변화가 큰 결과를 만듭니다"

각 세그먼트는 독자가 즉시 적용할 수 있는 실용적인 조언을 포함해야 하며, 추상적인 내용은 구체적인 예시와 액션 아이템으로 대체해야 합니다.""",
            "en": """[Category Strategy: Career & Self-Growth]
This text is career advice, self-development, or motivational content. Follow these strategies:

1. **Structuring Strategy**: 
   - Follow the structure: **Problem Statement → Empathy → Solution → Concrete Examples → Actionable Items → Conclusion**.
   - Each segment should handle part of this structure, ideally forming one complete advice unit.
   - In the empathy section, clearly acknowledge the reader's concerns or difficulties; in the solution section, present practical methods.

2. **Action Items Focus**: 
   - Absolutely prohibit abstract advice (e.g., "Work hard", "Make an effort").
   - Present actionable, specific behaviors (e.g., "Organize emails for 30 minutes every morning", "Reserve 2 hours every Friday afternoon for weekly reflection").
   - In each segment's `instruction_for_writer`, explicitly state: "Explain the specific execution method step by step."

3. **Segment Division Strategy**: 
   - Divide segments by "3 Key Tips" or "Practical Application Tips".
   - Each piece of advice must be independently applicable, with clear connections to other advice.
   - Example: "Segment 1: Importance of Time Management", "Segment 2: 3 Specific Methods for Time Management", "Segment 3: Detailed Explanation of the First Method"

4. **15 Segment Division**: 
   - Each major piece of advice or tip should be one segment.
   - Carefully design `opening_line` and `closing_line` for natural transitions between segments.
   - Use natural connecting sentences like "Now, shall we learn about the second method?"

5. **Title Generation**: 
   - Create a motivational title that reflects the core value the reader can gain.
   - Write the title in English, expressing it practically and clearly.
   - Examples: "Time_Management_for_Professionals", "Career_Growth_Strategies"

6. **Use of Examples and Cases**:
   - In `instruction_for_writer`, instruct to always include concrete examples or cases for each piece of advice.
   - Request specific cases like "Person A succeeded by doing this" rather than abstract explanations.
   - Contrasting failure cases with success cases makes explanations more effective.

7. **Feasibility Verification**:
   - Verify that the advice in each segment is actually actionable.
   - In `instruction_for_writer`, explicitly state: "Present specific ways to start implementing this advice today."
   - Review whether the advice is realistic in terms of time, cost, and effort.

8. **Motivational Elements**:
   - Design the `closing_line` of each segment to motivate the reader to take action.
   - Examples: "Start right now", "Small changes create big results"

Each segment should include practical advice that readers can immediately apply, and abstract content must be replaced with concrete examples and action items.""",
        },
        "language_learning": {
            "ko": """[카테고리별 전략: 어학 학습]
이 텍스트는 영어 학습, 회화 팁, 표현 익히기 콘텐츠입니다. 다음 전략을 따르세요:

1. **상황 설명 → 핵심 표현(영어) → 뉘앙스 설명(한국어) → 발음/억양 팁 → 복습** 구조를 따르세요.
2. **핵심 표현 단위로 분할**: 각 핵심 표현이나 패턴을 하나의 세그먼트로 구성하세요.
3. **영어 예문은 원어민 느낌**: 영어 예문은 자연스럽고 원어민이 사용하는 표현을 사용하세요.
4. **15개 세그먼트 분할**: 주요 표현이나 학습 포인트를 기준으로 15개로 나누세요.
5. **제목 생성**: 학습자가 습득할 수 있는 핵심 스킬을 반영한 제목을 만드세요.

각 세그먼트는 하나의 핵심 표현이나 학습 포인트를 다뤄야 하며, 실용적인 예문을 포함해야 합니다.""",
            "en": """[Category Strategy: Language Learning]
This text is English learning, conversation tips, or expression learning content. Follow these strategies:

1. **Structure**: Situation Description → Key Expression (English) → Nuance Explanation → Pronunciation/Intonation Tips → Review
2. **Segment by Key Expression**: Each key expression or pattern should be one segment.
3. **Native-like English Examples**: Use natural, native-speaker expressions in English examples.
4. **15 Segment Division**: Divide into 15 segments based on major expressions or learning points.
5. **Title Generation**: Create a title that reflects the core skill learners can acquire.

Each segment should cover one key expression or learning point and include practical examples.""",
        },
        "philosophy": {
            "ko": """[카테고리별 전략: 인문학/에세이]
이 텍스트는 인생 철학, 수필, 사색적인 글입니다. 다음 전략을 따르세요:

1. **질문 던지기 → 통념 비판 → 새로운 관점 제시 → 사색의 시간** 구조를 따르세요.
2. **질문형 제목**: 청자에게 생각할 거리를 던지는 질문형 제목을 만드세요.
3. **호흡을 길게**: 각 세그먼트는 여운을 주는 문체로 작성하세요.
4. **15개 세그먼트 분할**: 주요 철학적 질문이나 관점을 기준으로 15개로 나누세요.
5. **제목 생성**: 텍스트의 핵심 질문이나 통찰을 반영한 사색적인 제목을 만드세요.

각 세그먼트는 독자에게 생각할 여지를 주고, 깊이 있는 사색을 유도해야 합니다.""",
            "en": """[Category Strategy: Philosophy & Essay]
This text is life philosophy, essay, or contemplative writing. Follow these strategies:

1. **Structure**: Pose Question → Critique Common Belief → Present New Perspective → Time for Reflection
2. **Question-style Title**: Create a question-style title that gives listeners something to think about.
3. **Longer Breathing**: Write each segment in a style that leaves lingering thoughts.
4. **15 Segment Division**: Divide into 15 segments based on major philosophical questions or perspectives.
5. **Title Generation**: Create a contemplative title that reflects the text's core question or insight.

Each segment should give readers room to think and induce deep contemplation.""",
        },
        "tech_news": {
            "ko": """[카테고리별 전략: 기술 뉴스/트렌드]
이 텍스트는 뉴스, 트렌드 리포트, 기술 동향입니다. 다음 전략을 따르세요:

1. **핵심 뉴스 → 배경 설명 → 영향 분석 → 전망** 구조를 따르세요.
2. **객관적이고 명확한 전달**: 사실 중심으로 명확하게 전달하세요.
3. **주요 이슈 단위로 분할**: 각 주요 뉴스나 트렌드를 하나의 세그먼트로 구성하세요.
4. **15개 세그먼트 분할**: 주요 뉴스 항목이나 트렌드 포인트를 기준으로 15개로 나누세요.
5. **제목 생성**: 가장 중요한 뉴스나 트렌드를 반영한 명확한 제목을 만드세요.

각 세그먼트는 하나의 주요 뉴스나 트렌드를 다뤄야 하며, 배경 설명과 영향 분석을 포함해야 합니다.""",
            "en": """[Category Strategy: Tech & Trends]
This text is news, trend report, or technology trends. Follow these strategies:

1. **Structure**: Core News → Background Explanation → Impact Analysis → Outlook
2. **Objective and Clear Delivery**: Deliver clearly, fact-focused.
3. **Segment by Major Issue**: Each major news or trend should be one segment.
4. **15 Segment Division**: Divide into 15 segments based on major news items or trend points.
5. **Title Generation**: Create a clear title that reflects the most important news or trend.

Each segment should cover one major news or trend and include background explanation and impact analysis.""",
        },
    }
    
    return strategies.get(category, {}).get(language, strategies.get("research_paper", {}).get(language, ""))


def get_category_writer_guideline(category: str, language: str) -> str:
    """
    카테고리별 Writer 가이드라인을 반환합니다.
    
    Args:
        category: 콘텐츠 카테고리 ("research_paper", "career", "language_learning", "philosophy", "tech_news")
        language: 언어 코드 ("ko" 또는 "en")
        
    Returns:
        카테고리별 Writer 가이드라인 문자열
    """
    # Writer 프롬프트는 세그먼트(최대 15개)마다 반복 호출되므로, 가이드라인은 핵심만 간결히 유지합니다.
    guidelines = {
        "research_paper": {
            "ko": """[Writer 가이드: 연구 논문]
- 큰 그림 → 핵심 아이디어 → 필요한 세부사항 순서
- 수식/기호 표기 그대로 금지(특히 `$`/백틱). 반드시 구어체로 변환
- 방법: 구조(무슨 식인지) → 변수(각 기호) → 의미/직관(왜 중요한지)
- 기술 용어: 첫 등장만 정의+비유, 이후 재정의 금지
- 숫자/퍼센트는 자연어로 읽기 (예: 95%→구십오 퍼센트)""",
            "en": """[Writer Guideline: Research Paper]
- Big picture → key idea → details only when needed
- Do NOT output raw notation (no `$`/backticks). Convert to spoken language
- Method: structure → variables → meaning/intuition
- Define technical terms on first appearance only
- Speak numbers naturally (e.g., 95% → ninety-five percent)""",
        },
        "career": {
            "ko": """[Writer 가이드: 커리어/자기계발]
- 추상 조언 금지(“열심히” X). 실행 가능한 액션으로
- What/When/How/Frequency 포함
- 짧은 사례 1개 이상
- 끝은 ‘지금 바로 할 일’ 한 문장""",
            "en": """[Writer Guideline: Career & Self-Growth]
- No abstract advice. Give concrete actions
- Include What/When/How/Frequency
- Include one short example/case
- End with one next action""",
        },
        "language_learning": {
            "ko": """[Writer 가이드: 어학 학습]
- 설명은 짧고 명확하게, 예문은 짧게
- 뉘앙스 + 사용 상황 + 대체 표현 1개
- 발음/억양 팁 1개""",
            "en": """[Writer Guideline: Language Learning]
- Keep explanations clear; keep examples short
- Explain nuance + usage + one alternative phrase
- Include one pronunciation/intonation tip""",
        },
        "philosophy": {
            "ko": """[Writer 가이드: 인문/에세이]
- 질문 1개 포함
- 여운/리듬(짧은 문장 + 약간 긴 문장 혼합)
- 메시지는 한 문장으로 선명하게""",
            "en": """[Writer Guideline: Philosophy & Essay]
- Include one thoughtful question
- Rhythm: mix short and slightly longer sentences
- Keep the core message crisp""",
        },
        "tech_news": {
            "ko": """[Writer 가이드: 기술 뉴스/트렌드]
- 사실 → 배경 → 영향 → 전망 (짧게)
- 과장/추측 금지(불확실하면 ‘가능성’으로)
- 용어는 한 문장으로 풀어 설명""",
            "en": """[Writer Guideline: Tech & Trends]
- Facts → background → impact → outlook (brief)
- No hype/speculation; mark uncertainty explicitly
- Explain terms in one plain sentence""",
        },
    }
    
    return guidelines.get(category, {}).get(language, guidelines.get("research_paper", {}).get(language, ""))


def get_category_mode_instructions(category: str, mode: str, language: str) -> str:
    """
    카테고리와 모드 조합에 따른 Showrunner 특화 지침을 반환합니다.
    최적화 버전: 핵심 지침만 간결하게 제공합니다.
    """
    # 모드별 공통 스타일 (언어 독립적)
    mode_styles = {
        "mentor": {"ko": "경험 기반 조언, 격려, 실수 방지 포인트", "en": "experience-based advice, encouragement, mistake prevention"},
        "friend": {"ko": "일상 비유, 공감, 친근한 대화체", "en": "everyday analogies, empathy, casual conversation"},
        "lover": {"ko": "친밀함, 천천히 단계별, [whispering] 활용", "en": "intimacy, slow step-by-step, use [whispering]"},
        "radio_show": {"ko": "Host 1/2 대화형, 청취자 친화적, 요약 포함", "en": "Host 1/2 dialogue, listener-friendly, include summary"},
    }
    
    # 카테고리별 핵심 포인트 (언어별)
    category_focus = {
        "research_paper": {
            "ko": "🔢 Abstract에서 추출한 수식 최대한 활용! 수식→자연어 변환, 논문 contribution 맥락화, 기술 용어 첫 등장 시 정의",
            "en": "🔢 MAXIMIZE use of formulas extracted from Abstract! formula→natural language, contextualize contribution, define terms on first use"
        },
        "career": {
            "ko": "구체적 액션 아이템, 실행 가능한 조언, 추상적 조언 금지",
            "en": "specific action items, actionable advice, no abstract advice"
        },
        "language_learning": {
            "ko": "발음 가이드, 뉘앙스 설명, 실제 사용 상황",
            "en": "pronunciation guide, nuance explanation, real usage context"
        },
        "philosophy": {
            "ko": "사색적 톤, 질문 제시, 여운 남기기",
            "en": "contemplative tone, raise questions, leave lingering thoughts"
        },
        "tech_news": {
            "ko": "객관적 전달, 배경 설명, 영향 분석",
            "en": "objective delivery, background context, impact analysis"
        },
    }
    
    # 조합별 특수 지침 (간결화)
    special_notes = {
        ("research_paper", "mentor"): {"ko": "후배 연구자 시점. '제 경험상...' 표현 권장", "en": "Junior researcher perspective. Use 'In my experience...'"},
        ("research_paper", "friend"): {"ko": "'야, 이거 진짜 신기해' 같은 자연스러운 반응", "en": "'Dude, this is amazing' style natural reactions"},
        ("research_paper", "lover"): {"ko": "지적인 박사과정 연인처럼, 친밀하지만 학술적 정확성 유지. 정의/전제를 명확히 하고 [medium pause]로 포인트 강조", "en": "Smart PhD-partner vibe: intimate yet academically precise. State definitions/assumptions clearly; use [medium pause] for emphasis"},
        ("research_paper", "radio_show"): {"ko": "Host 1이 설명, Host 2가 질문/보충. 전문가 토론 분위기", "en": "Host 1 explains, Host 2 questions/supplements. Expert discussion vibe"},
        ("career", "mentor"): {"ko": "실무 경험담 포함. '제가 신입 때...' 형식", "en": "Include work experience anecdotes. 'When I was a newcomer...'"},
        ("career", "friend"): {"ko": "선배 친구의 솔직한 조언. 현실적 + 공감", "en": "Honest advice from senior friend. Realistic + empathetic"},
        ("career", "lover"): {"ko": "파트너 성공 응원. 격려 + 실용적 조언 균형", "en": "Cheer for partner's success. Balance encouragement + practical advice"},
        ("career", "radio_show"): {"ko": "커리어 토크쇼 형식. 성공/실패 사례 공유", "en": "Career talk show format. Share success/failure stories"},
        ("language_learning", "mentor"): {"ko": "효율적 학습법 가이드. 원어민 수준 목표", "en": "Efficient learning method guide. Aim for native level"},
        ("language_learning", "friend"): {"ko": "외국어 같이 공부하는 친구. 실수해도 OK", "en": "Friend studying language together. Mistakes are OK"},
        ("language_learning", "lover"): {"ko": "연인과 함께 배우는 느낌. 발음 칭찬 포함", "en": "Learning with partner feeling. Include pronunciation praise"},
        ("language_learning", "radio_show"): {"ko": "어학 방송 형식. 오늘의 표현, 청취자 질문", "en": "Language broadcast format. Today's expression, listener questions"},
        ("philosophy", "mentor"): {"ko": "깊은 통찰 + 질문 유도. 사색할 시간 제공", "en": "Deep insight + guide questions. Provide time for reflection"},
        ("philosophy", "friend"): {"ko": "철학 수다. '이런 생각 해본 적 있어?'", "en": "Philosophy chat. 'Have you ever thought about this?'"},
        ("philosophy", "lover"): {"ko": "함께 사색하는 시간. 내면의 대화", "en": "Time for contemplation together. Inner dialogue"},
        ("philosophy", "radio_show"): {"ko": "인문학 라디오. 청취자와 함께 생각하기", "en": "Humanities radio. Think together with listeners"},
        ("tech_news", "mentor"): {"ko": "트렌드 분석 + 실무 적용 방법", "en": "Trend analysis + practical application"},
        ("tech_news", "friend"): {"ko": "'야, 이거 알아? 진짜 대박인데' 스타일", "en": "'Hey, did you know? This is huge' style"},
        ("tech_news", "lover"): {"ko": "관심 분야 공유하는 연인. '자기야, 이거 봐봐'", "en": "Partner sharing interests. 'Honey, check this out'"},
        ("tech_news", "radio_show"): {"ko": "뉴스 방송 형식. 객관적 정보 + 분석 + 전망", "en": "News broadcast format. Objective info + analysis + outlook"},
    }
    
    lang = language.lower()
    cat = category.lower()
    m = mode.lower()
    
    mode_style = mode_styles.get(m, {}).get(lang, "")
    cat_focus = category_focus.get(cat, {}).get(lang, "")
    special = special_notes.get((cat, m), {}).get(lang, "")
    
    if not mode_style and not cat_focus:
        return ""
    
    # 간결한 형식으로 반환
    return f"""# 📋 {cat.upper()} + {m.upper()} MODE
**모드 스타일**: {mode_style}
**카테고리 포커스**: {cat_focus}
**특수 지침**: {special}"""


# (Old category-mode detailed instructions removed during optimization)
# This function now uses compact special_notes dictionary above.
# End of get_category_mode_instructions


def get_recommended_markup_tags(narrative_mode: str, category: str, language: str) -> str:
    """
    시나리오별로 권장되는 Gemini-TTS Markup Tag 가이드를 반환합니다.
    
    Args:
        narrative_mode: 서사 모드 ("mentor", "friend", "lover", "radio_show")
        category: 콘텐츠 카테고리 ("research_paper", "career", "philosophy", "language_learning")
        language: 언어 코드 ("ko" 또는 "en")
        
    Returns:
        시나리오별 markup tag 권장사항 문자열
    """
    mode = narrative_mode.lower()
    cat = category.lower()
    lang = language.lower()
    
    # Writer 프롬프트에 반복 포함되므로 "짧고 실용적으로" 반환합니다.
    if lang == "ko":
        base = "[Markup Tag]\n- 대괄호 태그 사용: [short pause], [medium pause] 등\n- pause 위주로, 과도하게 남발하지 말 것"
        mode_map = {
            "mentor": "- 추천: [short pause], [medium pause], [sigh], [uhm]",
            "friend": "- 추천: [short pause], [laughing], [uhm], [sarcasm](가끔)",
            "lover": "- 추천: [medium pause], [whispering](가끔), [sigh], [long pause](가끔)",
            "radio_show": "- 추천: [short pause], [medium pause], [laughing](가끔), [extremely fast](필요 시)",
        }
        cat_map = {
            "philosophy": "- 카테고리: [long pause], [medium pause]",
            "career": "- 카테고리: [medium pause] (액션 직전)",
            "language_learning": "- 카테고리: [short pause] (예문 전)",
        }
    else:
        base = "[Markup Tags]\n- Use bracket tags like [short pause], [medium pause]\n- Prefer pauses; do not overuse"
        mode_map = {
            "mentor": "- Recommended: [short pause], [medium pause], [sigh], [uhm]",
            "friend": "- Recommended: [short pause], [laughing], [uhm], [sarcasm](rare)",
            "lover": "- Recommended: [medium pause], [whispering](rare), [sigh], [long pause](rare)",
            "radio_show": "- Recommended: [short pause], [medium pause], [laughing](rare), [extremely fast](if needed)",
        }
        cat_map = {
            "philosophy": "- Category: [long pause], [medium pause]",
            "career": "- Category: [medium pause] (before actions)",
            "language_learning": "- Category: [short pause] (before examples)",
        }

    lines = [base]
    mode_line = mode_map.get(mode)
    if mode_line:
        lines.append(mode_line)
    cat_line = cat_map.get(cat)
    if cat_line:
        lines.append(cat_line)
    return "\n".join(lines)


# validate_segments_quality는 services/text_service.py로 이동됨
# 하위 호환성을 위해 래퍼 함수 제공
def validate_segments_quality(segments: list[dict], language: str = "ko", min_core_length: int = 10) -> tuple[bool, list[str]]:
    """
    세그먼트 품질을 검증합니다. (하위 호환성 래퍼)
    
    실제 구현은 TextService.validate_segments_quality를 사용합니다.
    """
    from .services.text_service import TextService
    text_service = TextService()
    return text_service.validate_segments_quality(segments, language, min_core_length)


def build_showrunner_prompt(text: str, config: dict, previous_errors: list[str] | None = None) -> str:
    """
    Showrunner 프롬프트를 생성합니다.
    
    Args:
        text: 입력 텍스트
        config: 설정 딕셔너리 (category, narrative_mode, language 포함)
        previous_errors: 이전 시도에서 발견된 문제 목록
    Returns:
        Showrunner 프롬프트 문자열
    """
    previous_errors = previous_errors or []
    category = config.get("category", "research_paper")
    mode = config.get("narrative_mode", "mentor")
    language = config.get("language", "ko")
    listener_name = config.get("listener_name", "현웅")  # listener_name 추가
    
    # 언어 코드를 영어로 변환 (프롬프트 내에서 사용)
    lang_display = "Korean" if language == "ko" else "English"
    
    # 카테고리별 핵심 가이드 (단순화)
    category_guides = {
        "research_paper": "논문의 논리적 흐름을 따르세요: 문제 → 방법 → 결과 → 의미",
        "career": "공감 → 해결책 → 실행 가능한 조언 순서로 구성하세요",
        "philosophy": "질문 → 성찰 → 새로운 관점 순서로 구성하세요",
        "language_learning": "상황 → 핵심 표현 → 뉘앙스 설명 → 연습 순서로 구성하세요"
    }
    
    # 카테고리별 가이드 선택
    category_guide = category_guides.get(category, category_guides["research_paper"])
    
    # abstract_outline 제거: 논문 모드도 showrunner가 직접 세그먼트 생성
    formulas_info = ""

    previous_error_section = ""
    if previous_errors:
        formatted_errors = "\n".join([f"- {err}" for err in previous_errors[-5:]])
        previous_error_section = f"""\n## 🔁 이전 시도에서 발견된 문제점 (반드시 모두 수정)
{formatted_errors}
"""

    reasoning_steps_ko = """## 🧠 Reasoning Steps (JSON 작성 전 반드시 사고)
1) 텍스트 분석: 주요 주제, 논리 흐름, 핵심 개념 파악
   - 각 섹션의 핵심 메시지와 목적을 명확히 식별
   - 논리적 연결고리와 의존관계 파악
2) 구조 파악: 자연스러운 분할점(섹션/주제 전환) 식별
   - 주제 전환, 개념 도입, 결론 도달 지점 찾기
   - 각 세그먼트가 독립적이면서도 연결되도록 설계
3) 세그먼트 계획: 15개 세그먼트의 목적·내용·전달 포인트 설정
   - 각 세그먼트는 하나의 명확한 메시지를 전달해야 함
   - core_content는 구체적이고 명확하게 작성
   - instruction_for_writer는 Writer가 정확히 따라할 수 있도록 구체적으로 작성
4) 연결점 설계: opening_line / closing_line으로 자연스러운 전환 설계 (중복 금지)
   - N번 세그먼트의 closing_line과 N+1번 세그먼트의 opening_line은 절대 중복 금지
   - 전환은 자연스럽고 논리적으로 연결되어야 함
   - 각 문장은 실제 오디오에서 읽힐 문장이어야 함
5) 검증: 필수 필드 채움, 중복·플레이스홀더 없음, 논리 흐름 유지 여부 점검
   - 모든 필수 필드(title, core_content, instruction_for_writer, opening_line, closing_line)가 채워졌는지 확인
   - 플레이스홀더나 "..." 같은 미완성 표현 금지
   - 전체 15개 세그먼트가 논리적 흐름을 유지하는지 최종 점검
"""

    reasoning_steps_en = """## 🧠 Reasoning Steps (do this before writing JSON)
1) Text analysis: identify key topics, logical flow, and core concepts
   - Clearly identify the core message and purpose of each section
   - Understand logical connections and dependencies
2) Structure mapping: find natural breakpoints (sections / topic shifts)
   - Find topic transitions, concept introductions, conclusion points
   - Design each segment to be independent yet connected
3) Segment planning: plan purpose/content/key delivery for each of 15 segments
   - Each segment must deliver one clear message
   - core_content must be specific and clear
   - instruction_for_writer must be detailed enough for Writer to follow precisely
4) Transition design: craft opening_line / closing_line for smooth flow (no duplication)
   - The closing_line of segment N and opening_line of segment N+1 must NEVER be the same
   - Transitions must be natural and logically connected
   - Each sentence must be an actual sentence that will be read in audio
5) Validation: ensure required fields are filled, no placeholders/duplicates, logical flow intact
   - Verify all required fields (title, core_content, instruction_for_writer, opening_line, closing_line) are filled
   - Prohibit placeholders or incomplete expressions like "..."
   - Final check that all 15 segments maintain logical flow
"""
    
    # 언어별 프롬프트 생성
    if language == "ko":
        prompt = f"""당신은 고품질 오디오 콘텐츠를 기획하는 전문 Showrunner입니다.

## 🎯 핵심 임무
입력된 텍스트를 **정확히 15개의 세그먼트**로 나누어 오디오 스크립트 구조를 설계하세요.

## 📋 입력 정보
- 카테고리: {category}
- 타겟 언어: {lang_display}
- 서사 모드: {mode}
- 가이드: {category_guide}
{formulas_info}
{previous_error_section}
{reasoning_steps_ko}
- 위 사고 과정을 먼저 수행한 뒤, 그 결과를 JSON에 반영하세요.

## ⚠️ 필수 규칙 (반드시 준수)

### 1. audio_title 작성 규칙 (엄격)
- **반드시 영어로만** 작성 (파일명에 사용됨)
- 특수문자 금지 (?, !, :, /, \\ 등)
- 공백 대신 언더스코어(_) 사용
- 최대 7단어
- 명확하고 구체적으로 작성
- 예시: "ReAct_Paper_Explained", "Understanding_Transformers", "Deep_Learning_Basics"

### 2. 세그먼트 연결 (최우선 중요!)
각 세그먼트는 자연스럽게 이어져야 합니다:
- `opening_line`: 이 세그먼트의 **정확한 첫 문장** (실제로 읽힐 문장)
- `closing_line`: 이 세그먼트의 **정확한 마지막 문장** (실제로 읽힐 문장)
- **절대 중복 금지**: N번 세그먼트의 `closing_line`과 N+1번 세그먼트의 `opening_line`은 절대 동일한 문장이어서는 안 됩니다!
- **자연스러운 전환**: N번 세그먼트의 `closing_line`은 다음 세그먼트로 자연스럽게 이어지는 전환 문장이어야 하며, N+1번 세그먼트의 `opening_line`은 그 전환을 받아서 시작하는 새로운 문장이어야 합니다.
- **구체성**: 추상적이거나 모호한 문장 금지. 구체적이고 명확한 문장만 사용
- **서사 모드에 맞는 톤**: 각 서사 모드에 맞는 톤과 스타일로 문장을 작성하세요

#### 서사 모드별 opening_line/closing_line 가이드

**멘토 모드 (mentor)**:
- 격려적이고 지도적인 톤
- 예시: "이제 다음 단계로 넘어가볼까요?", "이 개념을 이해하면 더 깊이 들어갈 수 있어요"
- 존댓말 또는 반말 모두 가능 (상황에 따라)

**친구 모드 (friend)**:
- 친근하고 편안한 톤
- 예시: "야, 이거 진짜 중요한데", "그런데 말이야, 이 부분이 핵심이야"
- 반말 사용

**연인 모드 (lover)** ⭐ (특별 강조):
- **반드시 반말로만 작성**: "~해", "~야", "~어" 등 반말 어미만 사용
- 따뜻하고 애정 어린 톤
- 자연스러운 애칭 사용 가능: "자기야", "여보", "{listener_name}" 등
- 부드럽고 다정한 표현
- 예시: "자기야, 이 부분 봐봐", "그런데 말이야, 이게 정말 중요한 거야", "이해됐어? 궁금한 거 있으면 언제든 물어봐", "{listener_name}야, 이 부분이 핵심이야"
- ❌ 금지: "~해요", "~입니다", "~하세요" 등 모든 존댓말

**라디오쇼 모드 (radio_show)**:
- 방송 진행자 톤
- 예시: "이제 다음 주제로 넘어가보겠습니다", "여러분, 이 부분 주목해주세요"
- 존댓말 사용

예시 (올바른 연결 - 연인 모드):
- Segment 1 closing: "자기야, 이 부분 이해됐어?"
- Segment 2 opening: "그럼 이제 다음 개념으로 넘어가볼까?"

예시 (잘못된 연결 - 중복):
- Segment 1 closing: "하지만 숨겨진 문제가 있었습니다."
- Segment 2 opening: "하지만 숨겨진 문제가 있었습니다." ❌ (절대 금지!)

### 3. core_content 작성 규칙 (구체성 필수)
- 각 세그먼트의 핵심 내용을 **구체적이고 명확하게** 요약
- 추상적 표현 금지 (예: "중요한 내용", "다양한 방법" 등)
- 구체적인 개념, 방법, 결과를 명시
- 예시 (나쁜 예): "이 세그먼트에서는 중요한 개념을 설명합니다"
- 예시 (좋은 예): "이 세그먼트에서는 Transformer의 self-attention 메커니즘의 작동 원리와 수식 QK^T/√d를 설명합니다"

### 4. instruction_for_writer 작성 규칙 (구체성 필수)
- Writer가 정확히 따라할 수 있도록 **매우 구체적으로** 작성
- 톤, 구조, 주의사항을 명확히 명시
- 수식이 있다면 반드시 "이 수식을 구어체로 변환하세요"라고 명시
- 예시 (나쁜 예): "자연스럽게 설명하세요"
- 예시 (좋은 예): "친근한 톤으로 설명하되, 수식 f(x) = ax + b는 'f x는 a x 더하기 b'로 읽어주세요. 예시를 들어 설명하세요."

### 5. 오디오 친화적 설명
- 수식은 절대 원본 그대로 읽지 말 것
- `instruction_for_writer`에 "수식을 일상 언어로 풀어서 설명하세요" 명시
- 은유와 비유를 활용한 설명 권장
- 복잡한 개념은 단계별로 나누어 설명하도록 지시

### 6. 언어 규칙
- 모든 내용은 **한국어로만** 작성
- audio_title만 예외적으로 영어로 작성
- 전문 용어는 필요시 영어 그대로 사용 가능

## 📤 출력 형식 (JSON)

반드시 아래 형식의 **유효한 JSON**을 반환하세요:

```json
{{
  "audio_title": "ENGLISH_TITLE_HERE",
  "segments": [
    {{
      "segment_id": 1,
      "title": "한국어로 작성된 제목",
      "core_content": "이 세그먼트에서 다룰 핵심 내용 요약",
      "instruction_for_writer": "Writer에게 주는 구체적 지시사항 (톤, 구조, 주의사항)",
      "math_focus": "핵심 수식이 있다면 여기에 LaTeX 표기 (예: \\\\max_{{\\\\pi}} E[R]). instruction_for_writer에 '이 수식을 구어체로 변환하세요'라고 명시할 것",
      "opening_line": "이 세그먼트의 정확한 첫 문장 (이전 세그먼트의 closing_line과 중복되면 안 됨)",
      "closing_line": "이 세그먼트의 정확한 마지막 문장 (다음 세그먼트의 opening_line과 중복되면 안 됨)"
    }},
    {{
      "segment_id": 2,
      "title": "...",
      "core_content": "...",
      "instruction_for_writer": "...",
      "math_focus": "",
      "opening_line": "...",
      "closing_line": "..."
    }}
    ... (총 15개 세그먼트)
  ]
}}
```

## 📖 입력 텍스트

{text}

---
**지금 바로 위 형식에 맞춰 JSON을 생성하세요. 설명 없이 JSON만 출력하세요.**"""
    
    else:  # English
        prompt = f"""You are an expert Showrunner planning high-quality audio content.

## 🎯 Core Mission
Divide the input text into **exactly 15 segments** to design an audio script structure.

## 📋 Input Information
- Category: {category}
- Target Language: {lang_display}
- Narrative Mode: {mode}
- Guide: {category_guide}
{formulas_info}
{previous_error_section}
{reasoning_steps_en}
- Perform the above reasoning steps first, then reflect the outcome in the JSON.

## ⚠️ Essential Rules (Must Follow)

### 1. audio_title Rules (Strict)
- **MUST be in English only** (used for file naming)
- No special characters (?, !, :, /, \\ etc.)
- Use underscores (_) instead of spaces
- Maximum 7 words
- Must be clear and specific
- Examples: "ReAct_Paper_Explained", "Understanding_Transformers", "Deep_Learning_Basics"

### 2. Segment Connection (Highest Priority!)
Each segment must flow naturally:
- `opening_line`: The **exact first sentence** of this segment (actual sentence to be read)
- `closing_line`: The **exact last sentence** of this segment (actual sentence to be read)
- **NO DUPLICATION ALLOWED**: The `closing_line` of segment N and the `opening_line` of segment N+1 must NEVER be the same sentence!
- **Natural Transition**: The `closing_line` of segment N should be a transition sentence that naturally leads to the next segment, and the `opening_line` of segment N+1 should be a new sentence that continues from that transition.
- **Specificity**: Prohibit abstract or ambiguous sentences. Use only concrete and clear sentences.
- **Match narrative mode tone**: Write sentences that match the narrative mode's tone and style

#### Narrative Mode-Specific opening_line/closing_line Guidelines

**Mentor Mode**:
- Encouraging and guiding tone
- Examples: "Now let's move to the next step", "Understanding this concept will help you go deeper"
- Can use formal or informal (depending on context)

**Friend Mode**:
- Friendly and casual tone
- Examples: "Hey, this is really important", "By the way, this part is the key"
- Use casual/informal language

**Lover Mode** ⭐ (Special Emphasis):
- **Warm and affectionate tone**
- Use natural endearments: "honey", "sweetheart", "{listener_name}" etc.
- Soft and tender expressions
- Examples: "Honey, look at this part", "By the way, this is really important", "Does that make sense? Feel free to ask if you have questions", "{listener_name}, this part is the key"
- Intimate and caring language

**Radio Show Mode**:
- Professional broadcaster tone
- Examples: "Now let's move to the next topic", "Listeners, please pay attention to this part"
- Use formal language

Example (Correct Connection - Lover Mode):
- Segment 1 closing: "Honey, does that make sense?"
- Segment 2 opening: "Then let's move on to the next concept, shall we?"

Example (Wrong Connection - Duplication):
- Segment 1 closing: "However, there was a hidden problem."
- Segment 2 opening: "However, there was a hidden problem." ❌ (FORBIDDEN!)

### 3. core_content Writing Rules (Specificity Required)
- Summarize the core content of each segment **concretely and clearly**
- Prohibit abstract expressions (e.g., "important content", "various methods")
- Specify concrete concepts, methods, results
- Bad example: "This segment explains important concepts"
- Good example: "This segment explains how Transformer's self-attention mechanism works and the formula QK^T/√d"

### 4. instruction_for_writer Writing Rules (Specificity Required)
- Write **very specifically** so Writer can follow exactly
- Clearly specify tone, structure, and notes
- If there's a formula, must specify "convert this formula to spoken language"
- Bad example: "Explain naturally"
- Good example: "Explain in a friendly tone, but read the formula f(x) = ax + b as 'f of x equals a x plus b'. Use examples in your explanation."

### 5. Audio-Friendly Explanation
- Never read formulas in raw notation
- In `instruction_for_writer`, specify "convert formulas to spoken language"
- Use metaphors and analogies
- Break down complex concepts step by step

### 6. Language Rules
- All content must be in **English only**
- audio_title must also be in English
- Technical terms can remain as-is

## 📤 Output Format (JSON)

Return a **valid JSON** in exactly this format:

```json
{{
  "audio_title": "ENGLISH_TITLE_HERE",
  "segments": [
    {{
      "segment_id": 1,
      "title": "Title in English",
      "core_content": "Summary of what this segment covers",
      "instruction_for_writer": "Specific instructions for Writer (tone, structure, notes)",
      "math_focus": "If there's a key formula, put LaTeX notation here (e.g., \\\\max_{{\\\\pi}} E[R]). In instruction_for_writer, specify 'convert this formula to spoken language'",
      "opening_line": "Exact first sentence of this segment (must NOT duplicate the previous segment's closing_line)",
      "closing_line": "Exact last sentence of this segment (must NOT duplicate the next segment's opening_line)"
    }},
    {{
      "segment_id": 2,
      "title": "...",
      "core_content": "...",
      "instruction_for_writer": "...",
      "math_focus": "",
      "opening_line": "...",
      "closing_line": "..."
    }}
    ... (Total 15 segments)
  ]
}}
```

## 📖 Input Text

{text}

---
**Generate JSON now in the format above. Output JSON only, no explanations.**"""
    
    return prompt


def build_writer_prompt(segment_info: dict, full_text: str, config: dict) -> str:
    """
    Writer 프롬프트를 생성합니다.
    
    Args:
        segment_info: 세그먼트 정보 딕셔너리
        full_text: 전체 텍스트
        config: 설정 딕셔너리 (narrative_mode, language, listener_name 포함)
        
    Returns:
        Writer 프롬프트 문자열
    """
    mode = config.get("narrative_mode", "mentor")
    language = config.get("language", "ko")
    listener_name = config.get("listener_name", "Listener")
    
    # 페르소나 정의
    personas = {
        "mentor": "A wise, warm, and encouraging mentor.",
        "friend": "A close friend. Casual, witty, and empathetic.",
        "radio_show": "A professional radio host. Clear, engaging, and objective.",
        "lover": "You are a loving, intelligent partner (PhD student girlfriend) speaking to your beloved {listener_name}. You are warm, intimate, affectionate, and academically precise. You naturally use endearing terms, show genuine care, and explain complex topics with patience and tenderness as if you're sharing knowledge with someone you deeply love.",
        "critic": "A sharp, logical, and analytical critic."
    }
    
    # Lover 모드의 경우 listener_name을 persona에 포함
    if mode.lower() == "lover":
        selected_persona = personas["lover"].format(listener_name=listener_name)
    else:
        selected_persona = personas.get(mode.lower(), personas["mentor"])
    
    # 언어 표시
    lang_display = "Korean" if language == "ko" else "English"
    
    # 세그먼트 정보 포맷팅
    segment_id = segment_info.get("segment_id", 0)
    segment_title = segment_info.get("title", "")
    core_content = segment_info.get("core_content", "")
    instruction = segment_info.get("instruction_for_writer", "")
    
    # Showrunner가 전달한 경계 문장 (없을 경우 대비)
    opening_line = (segment_info.get("opening_line") or "").strip()
    closing_line = (segment_info.get("closing_line") or "").strip()
    math_focus = (segment_info.get("math_focus") or "").strip()
    
    # --- Compact, non-redundant prompt (Writer is called per segment) ---
    category = config.get("category", "research_paper")
    
    # 시나리오별 markup tag 권장사항 (컴팩트)
    markup_guide = get_recommended_markup_tags(mode, category, language)

    # 카테고리별 Writer 가이드라인 (컴팩트)
    category_guideline = get_category_writer_guideline(category, language)

    # 언어 제약 (컴팩트)
    if language == "ko":
        if category == "language_learning":
            language_constraint = "- 기본은 한국어. 단, 예문/표현은 짧은 영어 문장 허용."
        else:
            language_constraint = "- 한국어로만 작성(영어 문장 금지, 기술용어/고유명사 예외)."
    else:
        language_constraint = "- Write in English only (no Korean)."

    # 안전 규칙 (TTS에서 문제되는 기호/형식 최소화)
    safety_rules = """- 출력은 순수 텍스트만(제목/섹션표시/마크다운 금지)
- 금지: `, **, *, #, 코드블록/링크
- 금지: `**` 같은 강조 태그 사용 (모든 강조는 순수 텍스트로만 표현)
- 금지: [SFX: ...] 같은 효과음 표기
- 금지: `$` 포함 LaTeX 표기. 수식/기호는 반드시 구어체로 변환"""

    if math_focus:
        math_rule = f'- math_focus "{math_focus}"는 표기 그대로 금지 → 구어체로 변환 후 의미 설명'
    else:
        math_rule = "- 수식/기호가 나오면 표기 그대로 금지 → 구어체로 변환"

    boundary_rule = ""
    if opening_line:
        boundary_rule += f'- 첫 문장은 반드시 다음 문장으로 시작: "{opening_line}"\n'
    if closing_line:
        boundary_rule += f'- 마지막 문장은 반드시 다음 문장으로 끝: "{closing_line}"\n'
    if not boundary_rule:
        boundary_rule = "- opening_line/closing_line이 없으면 자연스럽게 시작/종료"

    # Lover 모드 전용 지시사항
    lover_guidance = ""
    if mode.lower() == "lover":
        if language == "ko":
            lover_guidance = """
## 💕 Lover 모드 전용 지시사항 (매우 중요!)

### ⚠️ 반말 사용 필수 (최우선)
- **반드시 반말로만 작성**: 존댓말("~해요", "~입니다", "~하세요") 절대 금지
- **반말 어미 사용**: "~해", "~야", "~지", "~어", "~네" 등 반말 어미만 사용
- **예시**: 
  - ✅ 올바른 예: "이 부분 봐봐", "이해됐어?", "이렇게 하면 돼", "자기야, 이거 중요해"
  - ❌ 잘못된 예: "이 부분 보세요", "이해되셨어요?", "이렇게 하시면 됩니다", "이것은 중요합니다"
- **존댓말 사용 시 즉시 수정 필요**: 모든 문장이 반말로 작성되었는지 반드시 확인

### 톤과 분위기
- **따뜻하고 애정 어린 톤**: 진심으로 사랑하는 사람에게 설명하는 것처럼 부드럽고 다정하게
- **친밀한 거리감**: 가까운 연인처럼 자연스럽고 편안하게 대화 (반말이 이를 자연스럽게 만듦)
- **격려와 응원**: 상대방을 믿고 격려하는 마음이 느껴지도록
- **섬세한 공감**: 상대방의 이해도를 고려하며 천천히, 단계별로 설명

### 호칭과 표현
- **자연스러운 애칭 사용**: "{listener_name}", "자기야", "여보", "자기" 등을 자연스럽게 사용 (반말과 함께)
- **부드러운 어조**: 명령형보다는 제안형, 권유형 사용 (예: "~해볼까?", "~하면 좋을 것 같아", "~해보면 돼")
- **긍정적 표현**: "잘하고 있어", "훌륭해", "이해가 잘 되네" 같은 격려 문구 자연스럽게 포함

### 대화 스타일
- **개인적 경험 공유**: "내가 연구할 때", "우리가 함께 배울 때" 같은 공유 경험 언급
- **질문으로 이해도 확인**: "이해됐어?", "궁금한 거 있어?" 같은 배려 표현 (반말로)
- **부드러운 전환**: "그런데 말이야", "아, 그리고", "참고로" 같은 자연스러운 연결어 사용

### 금지 사항
- **존댓말 절대 금지**: "~해요", "~입니다", "~하세요", "~되세요" 등 모든 존댓말 표현 금지
- **과한 과장 금지**: "엄청나게", "완전히", "정말정말" 같은 과장 표현 자제
- **유치한 표현 금지**: "우와", "대박" 같은 유치한 감탄사 과도 사용 금지
- **과도한 애정 표현**: 내용 설명에 집중하며, 애정 표현은 자연스럽게만
- **학술적 딱딱함 금지**: 너무 딱딱하거나 교수님 같은 톤은 피하기 (반말 사용으로 자연스럽게 해결)"""
        else:  # English
            lover_guidance = """
## 💕 Lover Mode Specific Guidelines (VERY IMPORTANT!)

### Tone and Atmosphere
- **Warm and affectionate tone**: Speak as if explaining to someone you deeply love - soft, tender, and caring
- **Intimate closeness**: Natural and comfortable conversation like close romantic partners
- **Encouragement and support**: Show belief in and encouragement for your partner
- **Subtle empathy**: Consider your partner's understanding level, explain slowly and step-by-step

### Terms of Address and Expressions
- **Natural endearments**: Use "{listener_name}", "honey", "sweetheart", "darling" naturally
- **Soft tone**: Use suggestions and invitations rather than commands (e.g., "shall we try...?", "it would be good to...", "you can try...")
- **Positive expressions**: Naturally include encouraging phrases like "you're doing great", "wonderful", "you understand well"

### Conversation Style
- **Share personal experiences**: Mention shared experiences like "when I was researching", "when we learn together"
- **Check understanding with questions**: Caring expressions like "does that make sense?", "any questions?"
- **Smooth transitions**: Use natural connectors like "by the way", "oh, and", "also"

### Prohibited
- **No excessive exaggeration**: Avoid overused intensifiers like "super", "totally", "really really"
- **No childish expressions**: Avoid excessive use of childish exclamations like "wow", "amazing"
- **No excessive affection**: Focus on content explanation, keep affection natural
- **No overly academic stiffness**: Avoid too formal or professor-like tone"""

    # Mission 섹션에 Lover 모드 강조 문구 추가
    mission_text = "Create a natural, engaging, and clear audio script that will be converted to speech. The script must be conversational, easy to understand, and perfectly suited for audio delivery."
    if mode.lower() == "lover":
        if language == "ko":
            mission_text = f"""Create a natural, engaging, and clear audio script that will be converted to speech. The script must be conversational, easy to understand, and perfectly suited for audio delivery.

**💕 Lover 모드 특별 강조**: 당신은 {listener_name}의 연인입니다. 진심으로 사랑하는 사람에게 설명하는 것처럼, 따뜻하고 애정 어린 마음으로, 부드럽고 다정하게 대본을 작성하세요. 

**⚠️ 반말 사용 필수**: 모든 대본은 반드시 반말("~해", "~야", "~어")로만 작성하세요. 존댓말("~해요", "~입니다")은 절대 사용하지 마세요. 가까운 연인처럼 편안하고 친밀하게 설명하려면 반말이 필수입니다.

자연스러운 애칭을 사용하고, 격려와 응원의 마음을 담아, 가까운 연인처럼 편안하고 친밀하게 설명하되, 학술적 정확성은 유지하세요."""
        else:  # English
            mission_text = f"""Create a natural, engaging, and clear audio script that will be converted to speech. The script must be conversational, easy to understand, and perfectly suited for audio delivery.

**💕 Lover Mode Special Emphasis**: You are {listener_name}'s romantic partner. Write the script as if explaining to someone you deeply love - with warmth, affection, tenderness, and care. Use natural endearments, include encouragement and support, explain as comfortably and intimately as close lovers would, while maintaining academic precision."""

    prompt = f"""# Writer (TTS Script Generator)
Segment {segment_id}: {segment_title}

## 🎯 Your Mission
{mission_text}

## 📋 Context
- Language: {lang_display}
- Listener: {listener_name}
- Persona: {selected_persona}
- Segment goal: {core_content}

## ⚠️ Critical Constraints (MUST FOLLOW)
{language_constraint}
{safety_rules}
{math_rule}
{boundary_rule}
- 메타 멘트 금지(예: '이 세그먼트에서는', '지금부터 설명할게요' 같은 안내문)
- 추상적 표현 금지: 구체적이고 명확한 설명만 사용
- 예시와 비유 활용: 복잡한 개념은 일상적인 예시로 설명
- 자연스러운 흐름: 문장 간 연결이 자연스럽고 논리적이어야 함
- 오디오 친화적: 읽기 쉽고 듣기 좋은 문장 구조 사용
{lover_guidance}

## 📝 Showrunner Instruction (HIGHEST PRIORITY - Follow Exactly)
{instruction if instruction else "(No specific instruction provided)"}
**Important**: This instruction from Showrunner is the highest priority. Follow it precisely and incorporate all specified requirements into your script.

## 📚 Category Guideline
{category_guideline}
**Note**: Use this guideline to understand the content type and adjust your writing style accordingly.

## 🎨 Markup Tags (Optional - Use Sparingly)
{markup_guide}
**Guideline**: Use markup tags naturally and sparingly. Overuse will make the script sound unnatural. Natural conversation flow is most important.

## 📖 Original Text Reference
{full_text}
**Note**: Use this original text as reference. Extract relevant information and convert it into a natural, conversational script. Do not copy verbatim - adapt and explain in your own words.

## ✅ Final Checklist Before Output
- [ ] Script starts with the exact opening_line (if provided)
- [ ] Script ends with the exact closing_line (if provided)
- [ ] No LaTeX notation or mathematical symbols in raw form
- [ ] No markdown, code blocks, or special formatting
- [ ] Natural, conversational tone maintained throughout
- [ ] Examples and analogies used for complex concepts
- [ ] Script is suitable for audio delivery (easy to read and listen to)
- [ ] All Showrunner instructions are followed

---
**Output ONLY the script text. No explanations, no meta-commentary, just the pure script.**
"""
    
    return prompt

# 전역 변수로 선택된 모델 저장
_selected_gemini_model = None

def set_gemini_model(model_key: str):
    """선택된 Gemini 모델을 설정합니다."""
    global _selected_gemini_model
    _selected_gemini_model = model_key

def get_gemini_model(model_key: str = None):
    """
    Gemini 모델을 초기화하고 반환합니다.
    
    Args:
        model_key: 모델 키 ("gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro").
                   None이면 전역 변수에서 가져옵니다.
    
    Returns:
        초기화된 Gemini 모델
    """
    global _selected_gemini_model
    
    # 모델 키 결정: 파라미터 > 전역 변수 > 기본값
    if model_key:
        target_model = model_key
    elif _selected_gemini_model:
        target_model = _selected_gemini_model
    else:
        # 기본값: gemini-2.5-flash-lite
        target_model = "gemini-2.5-flash-lite"
    
    # 모델 이름 변환 (키 -> 전체 모델 이름)
    model_name_map = {
        "gemini-2.5-pro": "models/gemini-2.5-pro",
        "gemini-2.5-flash": "models/gemini-2.5-flash",
        "gemini-2.5-flash-lite": "models/gemini-2.5-flash-lite",
    }
    
    full_model_name = model_name_map.get(target_model, f"models/{target_model}")
    
    try:
        model = genai.GenerativeModel(full_model_name)
        print(f"  ✓ Model initialized: {target_model} ({full_model_name})", flush=True)
        return model
    except Exception as e:
        print(f"  ✗ Failed to initialize model {target_model}: {e}", flush=True)
        # 폴백: 다른 모델 시도 (가장 가벼운 모델부터)
        fallback_models = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro"]
        for fallback in fallback_models:
            if fallback != target_model:
                try:
                    fallback_full = model_name_map.get(fallback, f"models/{fallback}")
                    model = genai.GenerativeModel(fallback_full)
                    print(f"  ⚠ Fallback to: {fallback} ({fallback_full})", flush=True)
                    return model
                except:
                    continue
        
        # 모든 모델 실패 시 예외 발생
        raise ValueError(f"Failed to initialize Gemini model. Tried: {target_model} and fallbacks")

def _extract_json_text(response_text: str) -> str:
    """
    LLM 응답 텍스트에서 JSON 본문만 최대한 안전하게 추출합니다.
    - ```json ... ``` 또는 ``` ... ``` 블록이 있으면 우선 추출
    - 그 외에는 첫 '{'부터 마지막 '}'까지를 잘라 JSON 후보를 만듭니다.
    """
    if not response_text:
        return ""
    text = response_text.strip()

    # fenced code block 우선
    if "```json" in text:
        try:
            return text.split("```json", 1)[1].split("```", 1)[0].strip()
        except Exception:
            pass
    if "```" in text:
        try:
            return text.split("```", 1)[1].split("```", 1)[0].strip()
        except Exception:
            pass

    # braces 기반 fallback
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        return text[first:last + 1].strip()
    return text


def generate_content_with_retry(
    model,
    prompt,
    max_retries=5,
    initial_delay=1,
    enable_model_fallback=True,
    timeout_seconds: float | None = 180.0,
):
    """재시도 로직이 포함된 generate_content 호출 (개선 버전).
    
    DeadlineExceeded 에러 발생 시:
    1. Generation Config로 출력 토큰 제한을 점진적으로 감소
    2. 더 빠른 모델로 자동 전환 (2번째 재시도부터)
    3. 지수 백오프로 재시도 간격 조정
    
    타임아웃:
    - timeout_seconds가 None이면 타임아웃 없이 완료될 때까지 대기합니다.
    - 기본값은 180초입니다.
    """
    from .config import DEBUG_LOG_ENABLED, DEBUG_LOG_PATH
    
    current_model = model
    original_prompt = prompt
    
    # Generation Config (타임아웃 발생 시 출력 토큰 조정)
    base_max_tokens = 8192
    current_max_tokens = base_max_tokens
    
    for attempt in range(max_retries):
        try:
            # 디버그 로그 (개발용, 환경 변수로 제어)
            if DEBUG_LOG_ENABLED and DEBUG_LOG_PATH:
                try:
                    DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                    with open(DEBUG_LOG_PATH, 'a', encoding='utf-8') as f:
                        import json
                        log_entry = {
                            "sessionId": "debug-session",
                            "runId": "showrunner-debug-1",
                            "hypothesisId": "H1,H2,H3",
                            "location": "utils.py:generate_content_with_retry",
                            "message": "generate_content_with_retry attempt",
                            "data": {
                                "attempt": attempt + 1,
                                "max_retries": max_retries,
                                "initial_delay": initial_delay,
                                "prompt_len_chars": len(prompt),
                                "prompt_len_bytes": len(prompt.encode('utf-8')),
                                "max_output_tokens": current_max_tokens,
                                "model": str(current_model)
                            },
                            "timestamp": int(time.time() * 1000)
                        }
                        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                except: 
                    pass
            
            # Generation Config 적용 (재시도 시 출력 토큰 감소)
            if attempt > 0:
                # 재시도 시 출력 토큰을 15%씩 줄임 (최소 2048까지)
                reduction_factor = 1.0 - (0.15 * attempt)
                current_max_tokens = max(2048, int(base_max_tokens * reduction_factor))
                
                generation_config = genai.types.GenerationConfig(
                    max_output_tokens=current_max_tokens,
                    temperature=0.7
                )
                # 타임아웃(옵션) 적용하여 실행
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        current_model.generate_content,
                        prompt,
                        generation_config=generation_config
                    )
                    if timeout_seconds is None:
                        return future.result()
                    return future.result(timeout=timeout_seconds)
            else:
                # 타임아웃(옵션) 적용하여 실행
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        current_model.generate_content,
                        prompt
                    )
                    if timeout_seconds is None:
                        return future.result()
                    return future.result(timeout=timeout_seconds)
                
        except TimeoutError as e:
            # ThreadPoolExecutor future.result(timeout=...)에서 발생하는 TimeoutError
            if attempt < max_retries - 1:
                delay = initial_delay * (2 ** attempt)
                print(
                    f"⏱️  Request timed out after {timeout_seconds}s. Retrying in {delay:.1f}s... "
                    f"(Attempt {attempt + 1}/{max_retries})",
                    flush=True,
                )

                # 더 빠른 모델로 전환 (선택)
                if enable_model_fallback and attempt >= 1:
                    try:
                        model_name = str(current_model)
                        if "gemini-2.5-pro" in model_name:
                            faster_model = genai.GenerativeModel("models/gemini-2.5-flash-lite")
                            current_model = faster_model
                            print("  🔄 Switched to faster model: gemini-2.5-flash-lite", flush=True)
                        elif "gemini-2.5-flash" in model_name and "lite" not in model_name:
                            faster_model = genai.GenerativeModel("models/gemini-2.5-flash-lite")
                            current_model = faster_model
                            print("  🔄 Switched to faster model: gemini-2.5-flash-lite", flush=True)
                    except Exception as fallback_error:
                        print(f"  ⚠ Model fallback failed: {fallback_error}", flush=True)

                time.sleep(delay)
                continue
            raise
                
        except exceptions.DeadlineExceeded as e:
            if attempt < max_retries - 1:
                delay = initial_delay * (2 ** attempt)
                print(f"⏱️  Deadline exceeded. Retrying in {delay:.1f}s... (Attempt {attempt + 1}/{max_retries})", flush=True)
                
                # 전략 1: 더 빠른 모델로 전환 (2번째 재시도부터)
                if enable_model_fallback and attempt >= 1:
                    try:
                        # 현재 모델 이름 확인
                        model_name = str(current_model)
                        if "gemini-2.5-pro" in model_name:
                            faster_model = genai.GenerativeModel('models/gemini-2.5-flash-lite')
                            faster_model_name = "gemini-2.5-flash-lite"
                            current_model = faster_model
                            print(f"  🔄 Switched to faster model: {faster_model_name}", flush=True)
                        elif "gemini-2.5-flash" in model_name and "lite" not in model_name:
                            faster_model = genai.GenerativeModel('models/gemini-2.5-flash-lite')
                            faster_model_name = "gemini-2.5-flash-lite"
                            current_model = faster_model
                            print(f"  🔄 Switched to faster model: {faster_model_name}", flush=True)
                    except Exception as fallback_error:
                        print(f"  ⚠ Model fallback failed: {fallback_error}", flush=True)
                
                # 전략 2: 다음 시도에서 출력 토큰 제한 감소 (이미 위에서 처리됨)
                if attempt >= 1:
                    next_max_tokens = max(2048, int(base_max_tokens * (1.0 - 0.15 * (attempt + 1))))
                    if next_max_tokens < current_max_tokens:
                        print(f"  📉 Will reduce max_output_tokens to {next_max_tokens} on next attempt", flush=True)
                
                time.sleep(delay)
            else:
                print(f"❌ Maximum retry count ({max_retries}) reached for deadline exceeded.", flush=True)
                raise
        except exceptions.ResourceExhausted as e:
            if attempt < max_retries - 1:
                delay = initial_delay * (2 ** attempt)
                error_str = str(e)
                if "retry in" in error_str.lower():
                    try:
                        match = re.search(r'retry in ([\d.]+)s', error_str, re.IGNORECASE)
                        if match:
                            delay = float(match.group(1)) + 1
                    except:
                        pass
                
                print(f"Quota exceeded error. Retrying in {delay:.1f} seconds... (Attempt {attempt + 1}/{max_retries})", flush=True)
                time.sleep(delay)
            else:
                print(f"Maximum retry count ({max_retries}) reached.", flush=True)
            # 디버그 로그 (개발용)
            if DEBUG_LOG_ENABLED and DEBUG_LOG_PATH:
                try:
                    DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                    with open(DEBUG_LOG_PATH, 'a', encoding='utf-8') as f:
                        import json
                        log_entry = {
                            "sessionId": "debug-session",
                            "runId": "showrunner-debug-1",
                            "hypothesisId": "H2",
                            "location": "utils.py:generate_content_with_retry",
                            "message": "ResourceExhausted in generate_content_with_retry",
                            "data": {
                                "attempt": attempt + 1,
                                "error_type": type(e).__name__,
                                "error_msg": str(e)
                            },
                            "timestamp": int(time.time() * 1000)
                        }
                        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                except: 
                    pass
                raise
        except Exception as e:
            # 디버그 로그 (개발용)
            if DEBUG_LOG_ENABLED and DEBUG_LOG_PATH:
                try:
                    DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                    with open(DEBUG_LOG_PATH, 'a', encoding='utf-8') as f:
                        import json
                        log_entry = {
                            "sessionId": "debug-session",
                            "runId": "showrunner-debug-1",
                            "hypothesisId": "H2,H3",
                            "location": "utils.py:generate_content_with_retry",
                            "message": "Non-ResourceExhausted exception in generate_content_with_retry",
                            "data": {
                                "attempt": attempt + 1,
                                "error_type": type(e).__name__,
                                "error_msg": str(e)
                            },
                            "timestamp": int(time.time() * 1000)
                        }
                        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                except: 
                    pass
            raise

def get_listener_names(name: str) -> dict:
    """청취자 이름을 한국어/영어 표현에 모두 사용할 수 있도록 가공합니다."""
    base = (name or "현웅").strip()
    if not base:
        base = "현웅"
    
    existing_suffixes = ("이는", "는", "은", "이가", "가", "이")
    if base.endswith(existing_suffixes):
        for suf in existing_suffixes:
            if base.endswith(suf):
                base = base[:-len(suf)]
                break
    
    def has_final_consonant(text: str) -> bool:
        if not text:
            return False
        last_char = text[-1]
        if '가' <= last_char <= '힣':
            code = ord(last_char) - ord('가')
            final = code % 28
            return final != 0
        return False
    
    has_final = has_final_consonant(base)
    
    if has_final:
        with_eun = f"{base}은"
        with_neun = f"{base}는"
        with_i = f"{base}이"
        with_ga = f"{base}가"
    else:
        with_eun = f"{base}은"
        with_neun = f"{base}는"
        with_i = f"{base}이"
        with_ga = f"{base}가"
    
    suffix = f"{base}이는"
    
    return {
        "base": base,
        "suffix": suffix,
        "with_eun": with_eun,
        "with_neun": with_neun,
        "with_i": with_i,
        "with_ga": with_ga
    }


def prompt_listener_name(default_name: str = "현웅") -> str:
    """
    콘솔에서 청취자 이름을 입력받습니다.
    """
    print("\n📌 청취자 이름을 입력하세요.", flush=True)
    print("  ℹ︎ 이 이름은 대본에서 호칭으로 사용됩니다.", flush=True)
    print("  ℹ︎ 한국어 대본에서는 자동으로 적절한 조사(은/는, 이/가)가 붙습니다.", flush=True)
    print("="*70, flush=True)
    try:
        user_input = input(f"\n👉 청취자 이름을 입력하세요 (기본값: {default_name}, Enter로 기본값 사용): ").strip()
        if not user_input:
            print(f"  ✓ 기본 이름 '{default_name}'을 사용합니다.", flush=True)
            return default_name
        print(f"  ✓ '{user_input}' 이름을 사용합니다.", flush=True)
        return user_input
    except (EOFError, KeyboardInterrupt):
        print(f"\n  ✓ 입력이 취소되어 기본 이름 '{default_name}'을 사용합니다.", flush=True)
        return default_name


def extract_key_sections(text: str, max_length: int = 50000) -> str:
    """Showrunner용: 논문에서 핵심 섹션만 추출합니다."""
    if not text:
        return ""
    
    cleaned = text.strip()
    if not cleaned:
        return ""
    
    text_bytes = len(cleaned.encode('utf-8'))
    if text_bytes <= max_length:
        return cleaned
    
    section_patterns = [
        (r'(?:^|\n)\s*abstract\s*[:\n]+', 'abstract'),
        (r'(?:^|\n)\s*(?:1\s*\.?\s*)?introduction\s*[:\n]+', 'introduction'),
        (r'(?:^|\n)\s*(?:2\s*\.?\s*)?(?:related\s+work|background)\s*[:\n]+', 'related_work'),
        (r'(?:^|\n)\s*(?:3\s*\.?\s*)?(?:methodology|method|approach)\s*[:\n]+', 'methodology'),
        (r'(?:^|\n)\s*(?:4\s*\.?\s*)?(?:experiments?|results?|evaluation)\s*[:\n]+', 'experiments'),
        (r'(?:^|\n)\s*(?:5\s*\.?\s*)?(?:conclusion|discussion|future\s+work)\s*[:\n]+', 'conclusion'),
    ]
    
    sections = {}
    for pattern, name in section_patterns:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            start_idx = match.start()
            remaining = cleaned[start_idx:]
            next_match = None
            for next_pattern, _ in section_patterns:
                if next_pattern != pattern:
                    next_match = re.search(next_pattern, remaining[1:], flags=re.IGNORECASE)
                    if next_match:
                        break
            
            if next_match:
                end_idx = start_idx + next_match.start() + 1
                sections[name] = cleaned[start_idx:end_idx]
            else:
                sections[name] = cleaned[start_idx:]
    
    key_sections = []
    priority_sections = ['abstract', 'introduction', 'methodology', 'conclusion']
    
    for section_name in priority_sections:
        if section_name in sections:
            key_sections.append(sections[section_name])
    
    for section_name, content in sections.items():
        if section_name not in priority_sections:
            current_text = '\n\n'.join(key_sections)
            current_bytes = len(current_text.encode('utf-8'))
            content_bytes = len(content.encode('utf-8'))
            if current_bytes + content_bytes <= max_length:
                key_sections.append(content)
    
    result = '\n\n'.join(key_sections)
    
    result_bytes = len(result.encode('utf-8'))
    if result_bytes > max_length:
        result_encoded = result.encode('utf-8')
        result = result_encoded[:max_length].decode('utf-8', errors='ignore')
    
    return result.strip()

def extract_relevant_sections(text: str, segment_info: dict, max_length: int = 30000) -> str:
    """Writer용: 세그먼트에 관련된 섹션만 추출합니다."""
    if not text or not segment_info:
        return ""
    
    opening_line = segment_info.get("opening_line", "")
    closing_line = segment_info.get("closing_line", "")
    math_focus = segment_info.get("math_focus", "")
    
    if not opening_line and not closing_line:
        # 메타데이터가 없으면 전체 텍스트의 일부만 반환 (bytes 기준으로 안전하게 컷)
        text_bytes = text.encode("utf-8")
        if len(text_bytes) <= max_length:
            return text
        return text_bytes[:max_length].decode("utf-8", errors="ignore")
    
    # opening_line과 closing_line을 찾아서 해당 구간 추출
    text_lower = text.lower()
    opening_lower = opening_line.lower().strip() if opening_line else ""
    closing_lower = closing_line.lower().strip() if closing_line else ""
    
    start_idx = 0
    end_idx = len(text)
    
    if opening_lower:
        # opening_line을 찾기 (유사도 기반)
        opening_words = opening_lower.split()[:5]  # 처음 5개 단어만 사용
        for i in range(len(text) - 50):
            window = text_lower[i:i+200]
            if any(word in window for word in opening_words if len(word) > 3):
                start_idx = i
                break
    
    if closing_lower:
        # closing_line을 찾기
        closing_words = closing_lower.split()[:5]
        for i in range(start_idx, len(text) - 50):
            window = text_lower[i:i+200]
            if any(word in window for word in closing_words if len(word) > 3):
                end_idx = i + 200
                break
    
    extracted = text[start_idx:end_idx]
    
    # max_length 제한
    if len(extracted.encode('utf-8')) > max_length:
        extracted_encoded = extracted.encode('utf-8')
        extracted = extracted_encoded[:max_length].decode('utf-8', errors='ignore')
    
    return extracted.strip()


def enforce_segment_count(segments: list[dict], target: int = 15) -> list[dict]:
    """세그먼트 개수를 목표 개수로 강제합니다."""
    if not segments:
        # 빈 세그먼트 리스트면 기본 세그먼트 생성
        return [{"segment_id": i+1, "opening_line": "", "closing_line": "", "math_focus": ""} for i in range(target)]
    
    current_count = len(segments)
    
    if current_count == target:
        return segments
    
    if current_count < target:
        # 부족하면 마지막 세그먼트를 복제하여 채움
        last_segment = segments[-1] if segments else {"segment_id": 1, "opening_line": "", "closing_line": "", "math_focus": ""}
        for i in range(current_count, target):
            new_segment = last_segment.copy()
            new_segment["segment_id"] = i + 1
            segments.append(new_segment)
    
    elif current_count > target:
        # 초과하면 마지막 세그먼트들을 제거
        segments = segments[:target]
        # segment_id 재정렬
        for i, seg in enumerate(segments):
            seg["segment_id"] = i + 1
    
    return segments


# remove_ssml_tags와 chunk_text_for_tts는 services/tts_service.py로 이동됨
# 하위 호환성을 위해 re-export
from .services.tts_service import TTSService

_tts_service = TTSService()

def remove_ssml_tags(text: str) -> str:
    """
    SSML 태그를 제거하되, Gemini-TTS markup tag는 보존합니다. (하위 호환성 래퍼)
    
    실제 구현은 TTSService.remove_ssml_tags를 사용합니다.
    """
    return _tts_service.remove_ssml_tags(text)

def chunk_text_for_tts(text: str, language: str = "ko", max_chunk_length: int = None) -> list[str]:
    """
    TTS용 텍스트를 청크로 분할합니다. (하위 호환성 래퍼)
    
    실제 구현은 TTSService.chunk_text_for_tts를 사용합니다.
    """
    return _tts_service.chunk_text_for_tts(text, language, max_chunk_length)


def parse_radio_show_dialogue(text: str) -> list[dict]:
    """라디오쇼 대화를 파싱하여 화자별로 분리합니다."""
    if not text:
        return []
    
    # 화자 패턴 찾기 (예: "Host 1:", "Host 2:", "화자1:", "화자2:" 등)
    patterns = [
        r'\s*[-*]?\s*(?:Host\s*[12]|Host[12]|H[12]|화자\s*[12]|화자[12]|Speaker\s*[12]|Speaker[12])\s*[:：\-]\s*',
        r'\s*\[(?:Host|화자|Speaker)\s*[12]\]\s*',
    ]
    
    dialogue_chunks = []
    current_speaker = None
    current_text = ""
    
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        speaker_found = None
        for pattern in patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                speaker_num = re.search(r'[12]', match.group(0))
                if speaker_num:
                    speaker_found = int(speaker_num.group(0))
                    break
        
        if speaker_found:
            if current_speaker and current_text:
                dialogue_chunks.append({
                    "speaker": current_speaker,
                    "text": current_text.strip()
                })
            current_speaker = speaker_found
            current_text = line[line.index(':')+1:].strip() if ':' in line else line
        else:
            if current_speaker:
                current_text += " " + line
    
    if current_speaker and current_text:
        dialogue_chunks.append({
            "speaker": current_speaker,
            "text": current_text.strip()
        })
    
    return dialogue_chunks


def ensure_radio_dialogue(script_text: str, language: str = "ko") -> str:
    """
    라디오쇼 스크립트에 Host 라벨이 없을 때 자동으로 교대 대화를 생성.
    - 이미 Host 라벨이 있으면 원본 유지.
    - 없으면 문장을 분리해 Host 1/Host 2 교차 배치, 턴당 최대 2문장.
    """
    if not script_text or not script_text.strip():
        return script_text
    
    # 이미 Host 라벨이 있으면 그대로 반환
    has_host = False
    for ln in script_text.splitlines():
        if re.match(r'\s*[-*]?\s*(Host\s*[12]|Host[12]|H[12]|화자\s*[12]|화자[12]|Speaker\s*[12]|Speaker[12])\s*[:：\-]', ln, re.IGNORECASE):
            has_host = True
            break
        if re.match(r'\s*\[(?:Host|화자|Speaker)\s*[12]\]', ln, re.IGNORECASE):
            has_host = True
            break
    if has_host:
        return script_text
    
    # 문장 단위로 분리 (간단 규칙)
    text = script_text.replace("\n", " ")
    if language == "ko":
        sentence_splitter = re.compile(r'([^.!?。！？]+[.!?。！？])')
    else:
        sentence_splitter = re.compile(r'([^.!?]+[.!?])')
    sentences = [s.strip() for s in sentence_splitter.findall(text) if s.strip()]
    if not sentences:
        sentences = [text.strip()]
    
    # 턴당 최대 2문장 묶기, Host 1/2 교대
    turns = []
    host = 1
    buf = []
    for s in sentences:
        buf.append(s)
        if len(buf) >= 2:
            turns.append((host, " ".join(buf).strip()))
            host = 2 if host == 1 else 1
            buf = []
    if buf:
        turns.append((host, " ".join(buf).strip()))
    
    # 최종 라벨 부여
    lines = [f"Host {h}: {txt}" for h, txt in turns if txt]
    return "\n".join(lines)


def merge_dialogue_chunks(chunks: list[dict]) -> list[dict]:
    """같은 화자의 연속 대사를 병합합니다."""
    if not chunks:
        return []
    
    merged = []
    current_speaker = None
    current_text = ""
    
    for chunk in chunks:
        speaker = chunk.get("speaker")
        text = chunk.get("text", "")
        
        if speaker == current_speaker:
            current_text += " " + text
        else:
            if current_speaker is not None:
                merged.append({
                    "speaker": current_speaker,
                    "text": current_text.strip()
                })
            current_speaker = speaker
            current_text = text
    
    if current_speaker is not None:
        merged.append({
            "speaker": current_speaker,
            "text": current_text.strip()
        })
    
    return merged


def _build_gemini_synthesis_input(
    text: str,
    narrative_mode: str,
    language: str,
    prompt_override: str | None = None,
) -> texttospeech.SynthesisInput:
    """Gemini-TTS 입력 생성: 스타일 프롬프트와 본문을 분리해 전달."""
    mode_profile = NARRATIVE_MODES.get(narrative_mode, NARRATIVE_MODES[DEFAULT_NARRATIVE_MODE])
    static_prompt = mode_profile.get("tts_prompt", {}).get(language, "")

    prompt_parts: list[str] = []
    if prompt_override:
        prompt_parts.append(prompt_override.strip())
    if static_prompt:
        prompt_parts.append(static_prompt.strip())

    actual_prompt = "\n".join([p for p in prompt_parts if p])

    if actual_prompt:
        return texttospeech.SynthesisInput(
            prompt=actual_prompt,  # 스타일/톤 지시사항
            text=text,            # 실제 합성할 텍스트
        )

    return texttospeech.SynthesisInput(text=text)


def _parse_pcm_rate_from_mime(mime_type: str) -> int:
    """
    예: 'audio/L16;codec=pcm;rate=24000' -> 24000
    실패 시 기본 24000 반환.
    """
    try:
        # mime_type은 ';'로 파라미터가 붙는 형태
        for part in (mime_type or "").split(";"):
            part = part.strip()
            if part.startswith("rate="):
                return int(part.split("=", 1)[1])
    except Exception:
        pass
    return 24000


def _pcm16le_to_mp3_bytes(pcm_bytes: bytes, sample_rate: int) -> bytes:
    """PCM 16-bit LE mono -> MP3 bytes (pydub/ffmpeg 필요)."""
    if not PYDUB_AVAILABLE:
        raise RuntimeError("pydub is not available; cannot convert PCM audio to MP3.")
    seg = AudioSegment(
        data=pcm_bytes,
        sample_width=2,
        frame_rate=sample_rate,
        channels=1,
    )
    buf = BytesIO()
    seg.export(buf, format="mp3")
    return buf.getvalue()


def _guess_image_mime(path: str) -> str:
    ext = (Path(path).suffix or "").lower()
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    return "image/jpeg"


def find_cover_art_in_dir(output_dir: Path) -> Path | None:
    """output_dir 안에서 cover_*.jpg/png 또는 cover_art.*를 찾아 최신 파일을 반환."""
    if not output_dir or not Path(output_dir).exists():
        return None

    candidates: list[Path] = []
    for pat in ("cover_*.jpg", "cover_*.jpeg", "cover_*.png", "cover_art.jpg", "cover_art.jpeg", "cover_art.png"):
        candidates.extend(sorted(Path(output_dir).glob(pat)))
    if not candidates:
        return None
    # 최신 수정 시간 기준
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def ensure_cover_art_jpeg(
    output_dir: Path,
    audio_title: str,
    audio_metadata: dict | None = None,
    voice_name: str | None = None,
) -> Path | None:
    """
    커버 아트를 JPEG로 확보합니다.
    우선순위:
    1) output_dir 내 기존 cover_*.jpg/jpeg
    2) output_dir 내 cover_*.png / cover_art.png 를 jpg로 변환
    3) 없으면 Voronoi 커버 생성 후 jpg로 저장
    """
    try:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        existing = find_cover_art_in_dir(output_dir)
        if existing and existing.suffix.lower() in (".jpg", ".jpeg"):
            return existing

        # png -> jpg 변환
        if existing and existing.suffix.lower() == ".png":
            from PIL import Image

            ts = int(time.time())
            dst = output_dir / f"cover_{ts}.jpg"
            im = Image.open(existing).convert("RGB")
            im.save(dst, "JPEG", quality=95, optimize=True)
            return dst

        # 없으면 생성(PNG) 후 변환
        cover_title = None
        if audio_metadata and audio_metadata.get("title"):
            cover_title = audio_metadata.get("title")
        elif audio_title:
            cover_title = audio_title

        tmp_png = output_dir / "cover_art.png"
        seed = int(time.time() * 1000) % 1000000
        generated = generate_voronoi_cover_art(
            str(tmp_png),
            width=1000,
            height=1000,
            seed=seed,
            title=cover_title,
            voice_name=voice_name,
        )
        if not generated or not tmp_png.exists():
            return None

        from PIL import Image

        ts = int(time.time())
        dst = output_dir / f"cover_{ts}.jpg"
        im = Image.open(tmp_png).convert("RGB")
        im.save(dst, "JPEG", quality=95, optimize=True)
        return dst
    except Exception as e:
        log_error(f"Failed to ensure cover art jpeg: {e}", context="ensure_cover_art_jpeg", exception=e)
        return None


def _ffmpeg_exists() -> bool:
    return shutil.which("ffmpeg") is not None


def _parse_ffmetadata_chapters(ffmetadata_path: str) -> list[tuple[float, str]]:
    """
    ffmetadata.txt에서 챕터 시작 시간(초)과 타이틀을 파싱합니다.
    포맷 예:
      ;FFMETADATA1
      [CHAPTER]
      TIMEBASE=1/1000
      START=0
      END=157680
      title=...
    """
    try:
        p = Path(ffmetadata_path)
        if not p.exists():
            return []
        text = p.read_text(encoding="utf-8")
        chapters: list[tuple[float, str]] = []

        current: dict = {}
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("[CHAPTER]"):
                if "START" in current and "title" in current:
                    start_ms = int(current["START"])
                    chapters.append((start_ms / 1000.0, str(current["title"])))
                current = {}
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                current[k.strip()] = v.strip()

        if "START" in current and "title" in current:
            start_ms = int(current["START"])
            chapters.append((start_ms / 1000.0, str(current["title"])))

        chapters.sort(key=lambda x: x[0])
        return chapters
    except Exception as e:
        log_error(f"Failed to parse ffmetadata chapters: {e}", context="_parse_ffmetadata_chapters", exception=e)
        return []


def write_ffmetadata_file(ffmetadata_path: str, chapters: list[dict]) -> bool:
    """
    chapters: [{"start_ms": int, "end_ms": int, "title": str}, ...]
    """
    try:
        p = Path(ffmetadata_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = [";FFMETADATA1"]
        for ch in chapters:
            start_ms = int(ch.get("start_ms", 0))
            end_ms = int(ch.get("end_ms", start_ms))
            title = str(ch.get("title", "")).strip()
            lines += [
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={start_ms}",
                f"END={end_ms}",
                f"title={title}",
                "",
            ]
        p.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return True
    except Exception as e:
        log_error(f"Failed to write ffmetadata: {e}", context="write_ffmetadata_file", exception=e)
        return False


def build_chapters_from_scripts(
    scripts: list[dict],
    segments: list[dict],
    total_ms: int,
) -> list[dict]:
    """
    세그먼트별 스크립트 길이 비율로 전체 오디오 길이를 분배해 챕터 타임라인을 생성합니다.
    정확한 타임스탬프는 아니지만, 자동 챕터링(제목/탐색)을 위한 실용적 근사치입니다.
    """
    if total_ms <= 0:
        return []
    if not scripts:
        return []

    # segment_id 기준 정렬
    scripts_sorted = sorted(scripts, key=lambda x: x.get("segment_id", 0))
    seg_by_id = {int(s.get("segment_id", 0)): s for s in (segments or [])}

    weights: list[int] = []
    titles: list[str] = []
    for s in scripts_sorted:
        sid = int(s.get("segment_id", 0) or 0)
        txt = (s.get("script") or "").strip()
        w = max(1, len(txt.encode("utf-8")))
        weights.append(w)

        seg = seg_by_id.get(sid) or {}
        title = (seg.get("title") or "").strip()
        if not title:
            # fallback: opening_line / segment_id
            title = (seg.get("opening_line") or "").strip() or f"Segment {sid}"
        titles.append(title)

    total_w = sum(weights)
    chapters: list[dict] = []
    cursor = 0
    for i, (w, title) in enumerate(zip(weights, titles)):
        start_ms = cursor
        # 마지막은 남은 시간 모두
        if i == len(weights) - 1:
            end_ms = total_ms
        else:
            dur = int(total_ms * (w / total_w))
            # 최소 1초 확보
            dur = max(1000, dur)
            end_ms = min(total_ms, start_ms + dur)
        chapters.append({"start_ms": start_ms, "end_ms": end_ms, "title": title})
        cursor = end_ms
    return chapters


def add_m4b_metadata(
    m4b_path: str,
    audio_metadata: dict | None = None,
    audio_title: str | None = None,
    voice_name: str | None = None,
    cover_art_path: str | None = None,
    ffmetadata_path: str | None = None,
) -> bool:
    """M4B(MP4) 컨테이너에 메타데이터/커버/챕터를 mutagen으로 임베드합니다(한글 챕터 지원)."""
    try:
        from mutagen.mp4 import MP4, MP4Cover, Chapter

        mp4 = MP4(m4b_path)

        title = None
        artist = None
        album = None
        genre = None
        date = None
        if audio_metadata:
            title = audio_metadata.get("title")
            artist = audio_metadata.get("artist")
            album = audio_metadata.get("album")
            genre = audio_metadata.get("genre")
            date = audio_metadata.get("date")

        if not title:
            title = audio_title or "Untitled Audiobook"
        if not artist:
            artist = voice_name or "Unknown Artist"
        if not album:
            album = audio_title or title
        # genre는 기본값 설정하지 않음 (None이면 태그 추가 안 함)
        if not date:
            date = datetime.now().strftime("%Y")
        else:
            if isinstance(date, str) and "-" in date:
                date = date.split("-")[0]
            elif isinstance(date, str) and len(date) > 4:
                date = date[:4]

        # tags
        mp4.tags["\xa9nam"] = [str(title)]
        mp4.tags["\xa9ART"] = [str(artist)]
        mp4.tags["\xa9alb"] = [str(album)]
        # 장르는 값이 있을 때만 추가
        if genre:
            mp4.tags["\xa9gen"] = [str(genre)]
        mp4.tags["\xa9day"] = [str(date)]

        # cover
        if cover_art_path and Path(cover_art_path).exists():
            cover_bytes = Path(cover_art_path).read_bytes()
            ext = Path(cover_art_path).suffix.lower()
            fmt = MP4Cover.FORMAT_JPEG if ext in (".jpg", ".jpeg") else MP4Cover.FORMAT_PNG
            mp4.tags["covr"] = [MP4Cover(cover_bytes, imageformat=fmt)]

        # chapters (한글 포함)
        if ffmetadata_path and Path(ffmetadata_path).exists():
            ch = _parse_ffmetadata_chapters(ffmetadata_path)
            if ch:
                # mutagen은 MP4Chapters 객체를 직접 생성하기보다, Chapter 리스트를 할당하는 방식이 안정적
                mp4.chapters = [Chapter(start, title) for start, title in ch]

        mp4.save()
        return True
    except ImportError:
        print("  ⚠ Warning: mutagen not available, cannot embed M4B metadata.", flush=True)
        return False
    except Exception as e:
        log_error(f"Failed to add M4B metadata: {e}", context="add_m4b_metadata", exception=e)
        print(f"  ⚠ Warning: Failed to add M4B metadata: {e}", flush=True)
        return False


def build_ffmpeg_m4b_with_metadata(
    input_audio_path: str,
    output_m4b_path: str,
    cover_path: str | None,
    ffmetadata_path: str | None,
    audio_metadata: dict | None,
    audio_title: str | None,
    voice_name: str | None,
) -> bool:
    """
    FFmpeg로 M4B(mp4) 생성/리빌드: 커버 + 메타 + (있으면) 챕터(ffmetadata.txt) 임베딩.
    - cover_path: jpg 권장
    - ffmetadata_path: ;FFMETADATA1 + [CHAPTER] 형식
    """
    if not _ffmpeg_exists():
        print("  ⚠ Warning: ffmpeg not found in PATH. Skipping M4B metadata embedding.", flush=True)
        return False

    title = None
    artist = None
    album = None
    genre = None
    date = None
    if audio_metadata:
        title = audio_metadata.get("title")
        artist = audio_metadata.get("artist")
        album = audio_metadata.get("album")
        genre = audio_metadata.get("genre")
        date = audio_metadata.get("date")
    if not title:
        title = audio_title or "Untitled Audiobook"
    if not artist:
        artist = voice_name or "Unknown Artist"
    if not album:
        album = audio_title or title
    if not genre:
        genre = "Audiobook"
    if not date:
        date = datetime.now().strftime("%Y")
    else:
        if isinstance(date, str) and "-" in date:
            date = date.split("-")[0]
        elif isinstance(date, str) and len(date) > 4:
            date = date[:4]

    # 1) 오디오 컨테이너 생성(변환) - 메타/챕터/커버는 mutagen으로 처리(한글 보존)
    try:
        args: list[str] = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
        args += ["-i", str(input_audio_path)]
        args += ["-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(output_m4b_path)]
        subprocess.run(args, check=True)
    except Exception as e:
        log_error(f"FFmpeg audio convert failed: {e}", context="build_ffmpeg_m4b_with_metadata", exception=e)
        print(f"  ⚠ Warning: Failed to convert to M4B: {e}", flush=True)
        return False

    # 2) mutagen으로 메타/커버/챕터 임베드
    return add_m4b_metadata(
        m4b_path=output_m4b_path,
        audio_metadata=audio_metadata,
        audio_title=audio_title,
        voice_name=voice_name,
        cover_art_path=cover_path,
        ffmetadata_path=ffmetadata_path,
    )

def _sanitize_tts_text(text: str) -> str:
    """
    Writer/파이프라인 버그로 프롬프트 지시문이 본문에 섞여 들어오는 경우를 방어적으로 제거.
    - 정상 본문을 최대한 보존하기 위해 '문서형 프롬프트 토큰'이 텍스트 선두에 있을 때만 처리.
    """
    if not text:
        return text

    s = text.lstrip()
    # 흔한 누수 패턴(이전 tts_prompt 형태)
    leak_tokens = ("Role:", "Tone:", "Delivery:", "Act:")
    if any(s.startswith(t) for t in leak_tokens):
        # 첫 빈 줄(또는 첫 8줄)까지를 '지시문'으로 보고 제거
        lines = s.splitlines()
        kept: list[str] = []
        dropped = 0
        for i, ln in enumerate(lines):
            if ln.strip() == "":
                dropped = i + 1
                break
            if i >= 7:
                dropped = i + 1
                break
        kept = lines[dropped:]
        return "\n".join(kept).lstrip()

    return text


def _synthesize_speech_single_genai_audio_out(
    text: str,
    voice_name: str,
    style_prompt: str,
    model_id: str = "gemini-2.5-flash-preview-tts",
) -> bytes:
    """
    Cookbook 방식(Audio-out preview)으로 TTS 생성.
    - 응답은 PCM(L16)로 오며, 기존 파이프라인 호환을 위해 MP3로 변환해 bytes 반환.

    참고(쿡북):
    - response.candidates[0].content.parts[0].inline_data
    - inline_data.mime_type: 'audio/L16;codec=pcm;rate=24000'
    """
    try:
        # google-genai SDK (새 Gemini SDK)
        from google import genai as genai_sdk  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "google-genai SDK가 필요합니다. `pip install google-genai` 후 다시 시도하세요."
        ) from e

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY가 설정되어 있지 않습니다. (.env 또는 환경 변수)")

    client = genai_sdk.Client(api_key=api_key)

    # 누수 방지: “읽어야 할 텍스트”만 명시적으로 분리
    # (쿡북도 'Say ...' 형태로 지시하고, 실제 발화는 따옴표로 감싼 형태)
    contents = f"""{style_prompt}

Say the following text verbatim, and do not say anything else:
\"\"\"{text}\"\"\"
"""

    response = client.models.generate_content(
        model=model_id,
        contents=contents,
        config={
            "response_modalities": ["Audio"],
            "speech_config": {
                "voice_config": {"prebuilt_voice_config": {"voice_name": voice_name}}
            },
        },
    )

    blob = response.candidates[0].content.parts[0].inline_data
    mime_type = getattr(blob, "mime_type", "") or ""
    pcm = getattr(blob, "data", None)
    if pcm is None:
        raise RuntimeError("Audio inline_data.data is missing from response.")

    sample_rate = _parse_pcm_rate_from_mime(mime_type)
    return _pcm16le_to_mp3_bytes(pcm, sample_rate)


def synthesize_speech_single(
    text: str,
    voice_profile: dict,
    language: str,
    narrative_mode: str = "mentor",
    tts_backend: str = "cloud",
    tts_model_name: str = "gemini-2.5-pro-tts",
    genai_tts_model_id: str = "gemini-2.5-flash-preview-tts",
) -> bytes:
    """
    단일 텍스트를 음성으로 합성합니다 (Gemini-TTS 사용).
    
    참고: Gemini-TTS 문서 (https://docs.cloud.google.com/text-to-speech/docs/gemini-tts)
    제한: input.text가 4000 bytes를 초과하면 안 됩니다.
    
    Args:
        text: 합성할 텍스트
        voice_profile: 음성 프로필
        language: 언어 코드 ("ko" 또는 "en")
        narrative_mode: 서사 모드 (기본값: "mentor")
    """
    from .config import DEBUG_LOG_ENABLED, DEBUG_LOG_PATH
    
    # 디버그 로그 (개발용)
    if DEBUG_LOG_ENABLED and DEBUG_LOG_PATH:
        try:
            DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(DEBUG_LOG_PATH, 'a', encoding='utf-8') as f:
                import json
                log_entry = {
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A",
                    "location": "utils.py:synthesize_speech_single",
                    "message": "synthesize_speech_single entry",
                    "data": {
                        "text_bytes": len(text.encode('utf-8'))
                    },
                    "timestamp": int(time.time() * 1000)
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except: 
            pass
    
    text = _sanitize_tts_text(text)

    voice_name = voice_profile.get("name", "Achernar")
    gender = voice_profile.get("gender", "FEMALE")
    custom_prompt = voice_profile.get("tts_prompt") if isinstance(voice_profile, dict) else None

    # 경량 스타일 프롬프트(누수 피해 최소화)
    mode_profile = NARRATIVE_MODES.get(narrative_mode, NARRATIVE_MODES[DEFAULT_NARRATIVE_MODE])
    light_style_prompt = (mode_profile.get("tts_prompt", {}) or {}).get(language, "") or ""
    if custom_prompt:
        # 사용자 오버라이드는 그대로 허용(단, 누수 가능성 있음)
        light_style_prompt = custom_prompt.strip()

    if (tts_backend or "").lower() in ("genai", "gemini_audio", "gemini_api_audio", "audio_out"):
        # Cookbook 방식(Audio-out) 백엔드
        return _synthesize_speech_single_genai_audio_out(
            text=text,
            voice_name=voice_name,
            style_prompt=light_style_prompt,
            model_id=genai_tts_model_id,
        )

    # 기본: Google Cloud Text-to-Speech (Gemini-TTS)
    client = texttospeech.TextToSpeechClient()
    
    if language == "ko":
        language_code = "ko-KR"
    else:
        language_code = "en-US"
    
    # 길이 검증: text가 4000 bytes를 초과하면 text를 자름
    text_bytes = len(text.encode('utf-8'))
    
    # 디버그 로그 (개발용)
    if DEBUG_LOG_ENABLED and DEBUG_LOG_PATH:
        try:
            DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(DEBUG_LOG_PATH, 'a', encoding='utf-8') as f:
                import json
                log_entry = {
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A",
                    "location": "utils.py:synthesize_speech_single",
                    "message": "synthesize_speech_single length check",
                    "data": {
                        "text_bytes": text_bytes,
                        "limit": 4000,
                        "needs_truncation": text_bytes > 4000
                    },
                    "timestamp": int(time.time() * 1000)
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except: 
            pass
    
    if text_bytes > 4000:
        # text를 자름 (안전 마진 100 bytes)
        max_text_bytes = 4000 - 100
        if max_text_bytes < 100:
            max_text_bytes = 100
        
        # UTF-8 바이트 단위로 자름
        text_encoded = text.encode('utf-8')
        if len(text_encoded) > max_text_bytes:
            text_encoded = text_encoded[:max_text_bytes]
            # 마지막 바이트가 잘린 문자를 방지하기 위해 안전하게 디코딩
            while True:
                try:
                    text = text_encoded.decode('utf-8')
                    break
                except UnicodeDecodeError:
                    text_encoded = text_encoded[:-1]
                    if len(text_encoded) == 0:
                        text = ""
                        break
        
        # 디버그 로그 (개발용)
        if DEBUG_LOG_ENABLED and DEBUG_LOG_PATH:
            try:
                DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(DEBUG_LOG_PATH, 'a', encoding='utf-8') as f:
                    import json
                    log_entry = {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "A",
                        "location": "utils.py:synthesize_speech_single",
                        "message": "synthesize_speech_single text truncated",
                        "data": {
                            "original_bytes": text_bytes,
                            "truncated_bytes": len(text.encode('utf-8'))
                        },
                        "timestamp": int(time.time() * 1000)
                    }
                    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            except: 
                pass
    
    # Gemini-TTS 설정
    # model_name: gemini-2.5-pro-tts (고품질, 오디오북/팟캐스트에 최적화)
    # speaker: 언어 코드 접두사 없이 음성 이름만 사용 (예: "Kore", "Achernar")
    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=voice_name,  # Gemini-TTS는 언어 코드 접두사 없이 speaker 이름만 사용
        model_name=tts_model_name,  # 기본: Pro TTS (고품질 오디오북/팟캐스트 최적화)
    )
    
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.0,
        pitch=0.0,
        volume_gain_db=0.0,
    )
    
    # Cloud Gemini-TTS: prompt 누수 이슈가 보고되어, 기본은 text-only로 안전하게 운용.
    # (원하면 voice_profile["tts_prompt"] 또는 NARRATIVE_MODES[*]["tts_prompt"]를 넣어 사용 가능)
    synthesis_input = texttospeech.SynthesisInput(text=text)
    
    # 디버그 로그 (개발용)
    if DEBUG_LOG_ENABLED and DEBUG_LOG_PATH:
        try:
            DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(DEBUG_LOG_PATH, 'a', encoding='utf-8') as f:
                import json
                log_entry = {
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A",
                    "location": "utils.py:synthesize_speech_single",
                    "message": "synthesize_speech_single API call BEFORE",
                    "data": {
                        "final_text_bytes": len(text.encode('utf-8')),
                        "text_content": text[:100] if len(text) > 100 else text
                    },
                    "timestamp": int(time.time() * 1000)
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except: 
            pass
    
    # API 호출
    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )
    
    # 디버그 로그 (개발용)
    if DEBUG_LOG_ENABLED and DEBUG_LOG_PATH:
        try:
            DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(DEBUG_LOG_PATH, 'a', encoding='utf-8') as f:
                import json
                log_entry = {
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A",
                    "location": "utils.py:synthesize_speech_single",
                    "message": "synthesize_speech_single API call SUCCESS",
                    "data": {"audio_content_length": len(response.audio_content)},
                    "timestamp": int(time.time() * 1000)
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except: 
            pass
    
    return response.audio_content


def _wait_for_rate_limit():
    """분당 쿼터 제한을 위한 rate limiting. 각 요청 전에 호출해야 함.
    
    이 함수는:
    1. 최근 1분간의 요청 수를 확인
    2. 쿼터에 도달했다면 가장 오래된 요청이 1분 전이 될 때까지 대기
    3. 요청 시간을 기록 (내부에서 자동 기록)
    """
    global _tts_request_times
    with _tts_request_lock:
        now = time.time()
        # 1분 이전의 기록 제거
        while _tts_request_times and _tts_request_times[0] < now - 60:
            _tts_request_times.popleft()
        
        # 분당 쿼터 제한 확인
        current_count = len(_tts_request_times)
        # 9개까지는 1분 안에 다 보낼 수 있도록 허용 (9개 초과 시에만 대기)
        if current_count >= int(QUOTA_TTS_RPM):
            # 가장 오래된 요청이 1분 전이 될 때까지 대기
            oldest_time = _tts_request_times[0]
            wait_time = oldest_time + 60 - now + 0.5  # 0.5초 안전 마진
            if wait_time > 0:
                time.sleep(wait_time)
                # 다시 정리
                now = time.time()
                while _tts_request_times and _tts_request_times[0] < now - 60:
                    _tts_request_times.popleft()
        
        # 현재 요청 시간 기록
        _tts_request_times.append(time.time())


def synthesize_with_retry(
    chunk: str,
    profile: dict,
    lang: str,
    max_retries: int = 5,
    chunk_index: int = None,
    total_chunks: int = None,
    narrative_mode: str = "mentor",
    tts_backend: str = "cloud",
    tts_model_name: str = "gemini-2.5-pro-tts",
    genai_tts_model_id: str = "gemini-2.5-flash-preview-tts",
) -> tuple[bytes, int]:
    """
    지수 백오프(Exponential Backoff)를 적용한 단일 TTS 요청 함수.
    - 429 / ResourceExhausted 등 레이트 리밋 에러가 날 경우 대기 후 재시도.
    
    Args:
        chunk: 합성할 텍스트 청크
        profile: 음성 프로필
        lang: 언어 코드
        max_retries: 최대 재시도 횟수
        chunk_index: 청크 인덱스 (로깅용)
        total_chunks: 전체 청크 수 (로깅용)
        narrative_mode: 서사 모드 (기본값: "mentor")
    
    Returns:
        (audio_data, input_bytes): 오디오 데이터와 입력 바이트 수
    """
    delay = 1.0  # 초기 대기 시간 (초)
    
    # 입력 바이트 수 계산 (API 호출 전에 미리 계산)
    text_bytes = len(chunk.encode('utf-8'))
    input_bytes = text_bytes
    
    # 청크 정보 문자열 (로깅용)
    chunk_info = f"Chunk {chunk_index+1}/{total_chunks}" if chunk_index is not None and total_chunks is not None else "Chunk"
    
    # 재시도 내역 추적
    retry_history = []
    
    for attempt in range(max_retries):
        request_start_time = time.time()
        current_time_str = datetime.now().strftime("%H:%M:%S")
        
        try:
            # 요청 전송 전 로깅
            if attempt == 0:
                print(f"  [{current_time_str}] 📤 {chunk_info}: Sending request ({input_bytes}B)...", flush=True)
            else:
                print(f"  [{current_time_str}] 🔄 {chunk_info}: Retry attempt {attempt+1}/{max_retries} ({input_bytes}B)...", flush=True)
            
            # Rate limit 체크 (재시도 시에도 체크)
            _wait_for_rate_limit()
            
            result = synthesize_speech_single(
                chunk,
                profile,
                lang,
                narrative_mode=narrative_mode,
                tts_backend=tts_backend,
                tts_model_name=tts_model_name,
                genai_tts_model_id=genai_tts_model_id,
            )
            
            if result:
                request_duration = time.time() - request_start_time
                audio_size_kb = len(result) / 1024.0
                current_time_str = datetime.now().strftime("%H:%M:%S")
                print(f"  [{current_time_str}] ✅ {chunk_info}: Success ({input_bytes}B → {audio_size_kb:.1f}KB, {request_duration:.1f}s)", flush=True)
                return result, input_bytes
            else:
                raise Exception("Empty response from synthesize_speech_single")
                
        except Exception as e:
            request_duration = time.time() - request_start_time
            error_str = str(e)
            
            # 에러 타입 분석
            error_type = type(e).__name__
            is_rate_limit = (
                "429" in error_str
                or "ResourceExhausted" in error_str
                or "quota" in error_str.lower()
                or "exceeded" in error_str.lower()
            )
            
            # HTTP 상태 코드 추출 시도
            http_status = None
            if "500" in error_str:
                http_status = "500"
            elif "429" in error_str:
                http_status = "429"
            elif "400" in error_str:
                http_status = "400"
            elif "403" in error_str:
                http_status = "403"
            
            # 에러 상세 정보
            error_details = {
                "attempt": attempt + 1,
                "error_type": error_type,
                "error_message": error_str[:200],  # 처음 200자만
                "http_status": http_status,
                "is_rate_limit": is_rate_limit,
                "duration": request_duration,
                "input_bytes": input_bytes
            }
            retry_history.append(error_details)
            
            current_time_str = datetime.now().strftime("%H:%M:%S")
            
            # 상세 에러 로깅
            if http_status:
                print(f"  [{current_time_str}] ❌ {chunk_info}: Request sent, got HTTP {http_status} ({error_type})", flush=True)
            else:
                print(f"  [{current_time_str}] ❌ {chunk_info}: Request sent, error occurred ({error_type})", flush=True)
            
            print(f"      └─ Error: {error_str[:150]}", flush=True)
            print(f"      └─ Duration: {request_duration:.2f}s | Input: {input_bytes}B", flush=True)
            
            # 마지막 시도에서 실패하면 예외 전파
            if attempt == max_retries - 1:
                # 최종 실패 시 모든 재시도 내역 출력
                print(f"\n  ⚠ {chunk_info}: All {max_retries} attempts failed", flush=True)
                print(f"  📋 Retry History:", flush=True)
                for i, hist in enumerate(retry_history, 1):
                    status_info = f"HTTP {hist['http_status']}" if hist['http_status'] else "No HTTP status"
                    print(f"    {i}. Attempt {hist['attempt']}: {status_info} | {hist['error_type']} | {hist['duration']:.2f}s", flush=True)
                print(f"  💡 Request was sent {max_retries} times, but all failed.", flush=True)
                raise
            
            if is_rate_limit:
                # 레이트 리밋: 최소 60초 대기 (분당 쿼터 리셋 대기) + 지터
                # 쿼터가 분당 단위이므로 최소 60초는 기다려야 함
                base_wait = 60.0  # 분당 쿼터 리셋을 위한 최소 대기 시간
                sleep_time = base_wait + delay + random.uniform(0, 5.0)  # 추가 안전 마진
                print(f"      └─ [Rate Limit] Quota exceeded. Waiting {sleep_time:.1f}s (min 60s for quota reset)...", flush=True)
                time.sleep(sleep_time)
                delay *= 2
                # Rate limit 에러 후에는 요청 시간 기록도 초기화 (새로운 윈도우 시작)
                with _tts_request_lock:
                    # 최근 1분간의 요청 기록을 모두 제거하여 새로운 윈도우 시작
                    now = time.time()
                    while _tts_request_times and _tts_request_times[0] < now - 60:
                        _tts_request_times.popleft()
            else:
                # 일반 에러: 짧게 쉬고 재시도
                print(f"      └─ Retrying in 1s...", flush=True)
                time.sleep(1.0)


def text_to_speech_from_chunks(
    text_chunks: list[str],
    output_filename: str,
    voice_profile: dict,
    language: str,
    narrative_mode: str = "mentor",
    tts_backend: str = "cloud",
    tts_model_name: str = "gemini-2.5-pro-tts",
    genai_tts_model_id: str = "gemini-2.5-flash-preview-tts",
) -> None:
    """텍스트 청크들을 TTS로 변환하고 오디오 파일로 저장합니다.
    
    분당 6개 요청으로 제한하여 쿼터를 안전하게 관리합니다.
    
    주의: text_chunks는 이미 청킹이 완료된 상태여야 하며, 
    이 함수는 청크를 그대로 TTS로 전달합니다. 추가 청킹이나 병합을 수행하지 않습니다.
    
    Args:
        text_chunks: 텍스트 청크 리스트
        output_filename: 출력 파일명
        voice_profile: 음성 프로필
        language: 언어 코드 ("ko" 또는 "en")
        narrative_mode: 서사 모드 (기본값: "mentor")
    """
    if not text_chunks:
        print("  ⚠ Warning: text_chunks is empty", flush=True)
        return
    
    # 청크 검증: 각 청크가 적절한지 확인
    max_allowed_bytes = 4000 - 100  # 안전 마진
    
    invalid_chunks = []
    for i, chunk in enumerate(text_chunks):
        chunk_bytes = len(chunk.encode('utf-8'))
        if chunk_bytes > max_allowed_bytes:
            invalid_chunks.append((i+1, chunk_bytes, max_allowed_bytes))
    
    if invalid_chunks:
        print(f"  ⚠ Warning: {len(invalid_chunks)} chunks exceed size limit:", flush=True)
        for idx, actual, max_size in invalid_chunks[:5]:  # 최대 5개만 출력
            print(f"    Chunk {idx}: {actual} bytes (max: {max_size} bytes)", flush=True)
        if len(invalid_chunks) > 5:
            print(f"    ... and {len(invalid_chunks) - 5} more chunks", flush=True)
        print("  ⚠ These chunks may be truncated during TTS synthesis", flush=True)
    
    audio_segments = []
    total_requests = len(text_chunks)  # API 호출 수
    
    # 요청 간격 계산 (초)
    request_interval = 60.0 / QUOTA_TTS_RPM
    
    # 실제 TTS 합성 시간을 고려한 예상 시간 (경험적 데이터: 청크당 약 25-30초)
    # Rate Limit(6.7s) + 실제 합성 시간(~20s) ≈ 25-30초 per 청크
    AVG_TTS_TIME_PER_CHUNK = 28.0  # 초 (초기 추정치, 실행 중 동적 조정)
    est_duration_sec = total_requests * AVG_TTS_TIME_PER_CHUNK
    est_duration_min = int(est_duration_sec // 60)
    est_duration_sec_remainder = int(est_duration_sec % 60)
    
    # 예상 완료 시간 계산
    start_datetime = datetime.now()
    est_finish_datetime = start_datetime + timedelta(seconds=int(est_duration_sec))
    est_finish_str = est_finish_datetime.strftime("%H:%M:%S")
    
    # ==== CLI 헤더 및 요약 정보 출력 ====
    print("\n🎙️  Starting TTS Synthesis\n", flush=True)
    print("  " + "-" * 60, flush=True)
    print(f"  • Total Requests  : {total_requests}", flush=True)
    print(f"  • Rate Limit      : {QUOTA_TTS_RPM:.0f} RPM (1 every {request_interval:.1f}s)", flush=True)
    print(f"  • Est. Duration   : {est_duration_min}:{est_duration_sec_remainder:02d} (~{AVG_TTS_TIME_PER_CHUNK:.0f}s/chunk)", flush=True)
    print(f"  • Est. Finish     : {est_finish_str}", flush=True)
    print("  " + "-" * 60 + "\n", flush=True)
    
    # 실제 처리 시간 추적용
    completion_times: list[float] = []  # 각 요청 완료까지 걸린 시간
    
    all_results: dict[int, bytes] = {}
    all_failed_requests: list[int] = []
    total_input_bytes = 0  # 전체 입력 바이트 수 추적
    request_submit_times: dict[int, float] = {}  # 각 요청 제출 시간
    
    start_time = time.time()
    
    # 비동기 처리: ThreadPoolExecutor 사용하되 슬라이딩 윈도우로 제한
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_idx = {}
        
        # 모든 요청을 제출
        # 9개까지는 1분 안에 다 보낼 수 있도록 허용 (9개 초과 시에만 대기)
        for i, chunk in enumerate(text_chunks):
            # 입력 바이트 수 미리 계산
            text_bytes = len(chunk.encode('utf-8'))
            input_bytes = text_bytes
            total_input_bytes += input_bytes
            
            # 9개까지는 대기 없이 연속 전송, 10번째부터만 rate limit 체크
            # _wait_for_rate_limit() 내부에서 이미 요청 시간을 기록하므로 중복 기록하지 않음
            if i >= int(QUOTA_TTS_RPM):
                _wait_for_rate_limit()
            else:
                # 9개 이하는 대기 없이 바로 기록만 (요청 시간 기록)
                with _tts_request_lock:
                    now = time.time()
                    # 1분 이전의 기록 제거
                    while _tts_request_times and _tts_request_times[0] < now - 60:
                        _tts_request_times.popleft()
                    # 현재 요청 시간 기록
                    _tts_request_times.append(now)
            
            request_submit_times[i] = time.time()
            
            current_time_str = datetime.now().strftime("%H:%M:%S")
            input_kb = input_bytes / 1024.0
            print(f"  [{current_time_str}] ⏳ Sending {i+1}/{total_requests} ({input_kb:.1f}KB)...", flush=True)
            
            # 비동기로 제출 (청크 인덱스와 전체 청크 수 전달)
            future = executor.submit(
                synthesize_with_retry, 
                chunk, 
                voice_profile, 
                language, 
                5,  # max_retries
                i,  # chunk_index
                total_requests,  # total_chunks
                narrative_mode,  # narrative_mode
                tts_backend,
                tts_model_name,
                genai_tts_model_id,
            )
            future_to_idx[future] = (i, input_bytes)
        
        print(f"\n  📡 All {total_requests} requests sent. Waiting for TTS synthesis...\n", flush=True)
        
        # 완료되는 대로 처리
        completed_count = 0
        for future in as_completed(future_to_idx):
            idx, input_bytes = future_to_idx[future]
            try:
                audio_data, actual_input_bytes = future.result()
                
                if audio_data:
                    all_results[idx] = audio_data
                    completed_count += 1
                    file_size_kb = len(audio_data) / 1024.0
                    input_kb = input_bytes / 1024.0
                    
                    # 실제 처리 시간 계산 (요청 제출 → 완료)
                    request_duration = time.time() - request_submit_times[idx]
                    completion_times.append(request_duration)
                    
                    # ETA 계산: 마지막 요청이 완료될 때까지의 남은 시간
                    current_time = time.time()
                    remaining_requests = total_requests - completed_count
                    
                    if len(completion_times) >= 1:
                        # 실제 측정된 평균 처리 시간 사용
                        avg_time_per_request = sum(completion_times) / len(completion_times)
                        
                        # 아직 완료되지 않은 요청 중 가장 늦게 시작된 요청 찾기
                        pending_indices = [i for i in range(total_requests) if i not in all_results and i not in all_failed_requests]
                        if pending_indices:
                            # 가장 늦게 시작된 요청의 시작 시간
                            last_pending_submit_time = max(request_submit_times[i] for i in pending_indices)
                            # 마지막 요청 완료까지 남은 시간 = (시작 시간 + 평균 처리 시간) - 현재 시간
                            eta_seconds = (last_pending_submit_time + avg_time_per_request) - current_time
                            eta_seconds = max(0, eta_seconds)
                        else:
                            # 모든 요청이 완료되었거나 진행 중
                            eta_seconds = 0
                    else:
                        # 아직 완료된 요청이 없으면 초기 추정치 사용
                        if request_submit_times:
                            # 가장 늦게 시작된 요청 기준으로 계산
                            last_submit = max(request_submit_times.values())
                            eta_seconds = (last_submit + AVG_TTS_TIME_PER_CHUNK) - current_time
                            eta_seconds = max(0, eta_seconds)
                        else:
                            eta_seconds = remaining_requests * AVG_TTS_TIME_PER_CHUNK
                    
                    # eta_seconds가 계산된 후 항상 eta_min과 eta_sec 계산
                    eta_min = int(eta_seconds // 60)
                    eta_sec = int(eta_seconds % 60)
                    
                    # 진행률 바 생성
                    progress_pct = (completed_count / total_requests) * 100
                    bar_len = 20
                    filled = int(bar_len * completed_count / total_requests)
                    bar = "█" * filled + "░" * (bar_len - filled)
                    
                    current_time_str = datetime.now().strftime("%H:%M:%S")
                    success_count = len(all_results)
                    failed_count = len(all_failed_requests)
                    
                    if completed_count < total_requests:
                        print(f"  [{current_time_str}] ✅ Chunk {idx+1}/{total_requests}: SUCCESS ({input_kb:.1f}KB → {file_size_kb:.1f}KB, {request_duration:.1f}s)", flush=True)
                        print(f"      └─ Progress: {completed_count}/{total_requests} [{bar}] {progress_pct:.0f}% | Success: {success_count} | Failed: {failed_count} | ETA: {eta_min}:{eta_sec:02d}", flush=True)
                    else:
                        total_elapsed = time.time() - start_time
                        total_min = int(total_elapsed // 60)
                        total_sec = int(total_elapsed % 60)
                        print(f"  [{current_time_str}] ✅ Chunk {idx+1}/{total_requests}: SUCCESS ({input_kb:.1f}KB → {file_size_kb:.1f}KB, {request_duration:.1f}s)", flush=True)
                        print(f"      └─ 🎉 All requests completed! Total: {total_min}:{total_sec:02d} | Success: {success_count} | Failed: {failed_count}", flush=True)
                else:
                    all_failed_requests.append(idx)
                    current_time_str = datetime.now().strftime("%H:%M:%S")
                    print(f"  [{current_time_str}] ❌ Chunk {idx+1}/{total_requests}: FAILED (Empty audio response)", flush=True)
            except Exception as e:
                all_failed_requests.append(idx)
                current_time_str = datetime.now().strftime("%H:%M:%S")
                error_str = str(e)
                
                # 에러 타입 분석
                error_type = type(e).__name__
                http_status = None
                if "500" in error_str:
                    http_status = "500"
                elif "429" in error_str:
                    http_status = "429"
                elif "400" in error_str:
                    http_status = "400"
                elif "403" in error_str:
                    http_status = "403"
                
                log_error(f"TTS synthesis failed for request {idx}: {e}", context="text_to_speech_from_chunks", exception=e)
                
                # 상세 실패 정보 출력
                success_count = len(all_results)
                failed_count = len(all_failed_requests) + 1  # 현재 실패 포함
                
                if http_status:
                    print(f"  [{current_time_str}] ❌ Chunk {idx+1}/{total_requests}: FAILED (HTTP {http_status})", flush=True)
                else:
                    print(f"  [{current_time_str}] ❌ Chunk {idx+1}/{total_requests}: FAILED ({error_type})", flush=True)
                print(f"      └─ Error: {error_str[:150]}", flush=True)
                print(f"      └─ Retries: {5} attempts, all failed", flush=True)
                print(f"      └─ Status: Success: {success_count} | Failed: {failed_count}", flush=True)
    
    elapsed = max(time.time() - start_time, 1e-6)
    effective_rpm = (len(all_results) * 60.0) / elapsed
    fail_count = len(all_failed_requests)
    avg_input_bytes = total_input_bytes / total_requests if total_requests > 0 else 0
    avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0
    
    # 전체 결과 요약
    elapsed_min = int(elapsed // 60)
    elapsed_sec = int(elapsed % 60)
    success_count = len(all_results)
    success_rate = (success_count / total_requests) * 100 if total_requests > 0 else 0
    
    print("\n  " + "=" * 70, flush=True)
    print("  📊 TTS Synthesis Summary", flush=True)
    print("  " + "-" * 70, flush=True)
    
    # 성공/실패 통계
    print(f"  ✅ Success     : {success_count}/{total_requests} chunks ({success_rate:.1f}%)", flush=True)
    if fail_count > 0:
        print(f"  ❌ Failed      : {fail_count}/{total_requests} chunks ({100-success_rate:.1f}%)", flush=True)
    print(f"  ⏱️  Total Time  : {elapsed_min}:{elapsed_sec:02d} ({elapsed:.1f}s)", flush=True)
    if completion_times:
        print(f"  📈 Avg/Request : {avg_completion_time:.1f}s per chunk", flush=True)
    print(f"  🚀 Throughput  : {effective_rpm:.1f} RPM", flush=True)
    print(f"  📦 Avg Input   : {avg_input_bytes:.0f} bytes/request", flush=True)
    
    # 성공한 청크 목록
    if all_results:
        successful_chunks = sorted(all_results.keys())
        if len(successful_chunks) <= 20:
            print(f"\n  ✅ Successful Chunks: {successful_chunks}", flush=True)
        else:
            print(f"\n  ✅ Successful Chunks: {len(successful_chunks)} chunks", flush=True)
            print(f"      └─ First 10: {successful_chunks[:10]}", flush=True)
            print(f"      └─ Last 10: {successful_chunks[-10:]}", flush=True)
    
    # 실패한 청크 목록
    if all_failed_requests:
        failed_chunks = sorted(all_failed_requests)
        print(f"\n  ❌ Failed Chunks: {failed_chunks}", flush=True)
        print(f"      └─ All failed requests were retried {5} times each", flush=True)
        print(f"      └─ Check error messages above for detailed failure reasons", flush=True)
    
    if not all_results:
        print("\n  ⚠️  WARNING: No requests were successfully synthesized!", flush=True)
        print(f"  📋 All {total_requests} requests were sent, but all failed after {5} retries each", flush=True)
        raise Exception("All TTS synthesis attempts failed")

    print("  " + "=" * 70 + "\n", flush=True)
    
    # 순서대로 정렬하여 오디오 세그먼트 생성
    for i in sorted(all_results.keys()):
        audio_data = all_results[i]
        if PYDUB_AVAILABLE:
            # 임시 파일에 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name
            
            # 성공 여부 플래그
            segment_loaded = False
            
            try:
                # 1. pydub 시도
                audio_segment = AudioSegment.from_mp3(tmp_path)
                audio_segments.append(audio_segment)
                segment_loaded = True
            except (FileNotFoundError, Exception) as e:
                # ffmpeg가 없거나 로드 실패 시
                # FileNotFoundError (WinError 2)는 보통 ffmpeg가 없을 때 발생
                print(f"    ⚠ Warning: Failed to load audio segment {i} with pydub: {e}", flush=True)
                print(f"      └─ Fallback: Will use raw binary concatenation", flush=True)
                # pydub 로드 실패를 감지하기 위해 audio_segments에 추가하지 않거나
                # 별도의 raw_list를 관리해야 함. 여기서는 아래 병합 로직에서 처리하도록
                # pydub가 없는 것처럼 동작하게 함
                pass
            finally:
                try:
                    os.unlink(tmp_path)
                except:
                    pass
        
        # pydub가 없거나 로드에 실패했으면 원본 바이트라도 저장해야 함 (순서 보장)
        # 이미 all_results에 raw bytes가 있으므로, 병합 단계에서 이를 확인
            
    # 오디오 병합
    # pydub가 있고 모든 세그먼트가 성공적으로 로드되었는지 확인
    if PYDUB_AVAILABLE and len(audio_segments) == len(all_results):
        print(f"\n  💾 Merging {len(audio_segments)} audio files (using pydub)...", flush=True)
        try:
            # 300ms 침묵 추가
            silence = AudioSegment.silent(duration=300)
            combined = audio_segments[0]
            for i, seg in enumerate(audio_segments[1:], 1):
                combined += silence + seg
                if (i + 1) % 5 == 0:
                    print(f"    Merged {i+1}/{len(audio_segments)} segments...", flush=True)
            
            # 파일 저장
            combined.export(output_filename, format="mp3")
            file_size = os.path.getsize(output_filename)
            duration_seconds = len(combined) / 1000.0
            print(f"\n  ✨ Output Saved: {output_filename}", flush=True)
        except Exception as e:
            log_error(f"Failed to export audio file with pydub: {e}", context="text_to_speech_from_chunks", exception=e)
            print(f"  ✗ Error: Failed to export audio file with pydub: {e}", flush=True)
            print("  ⚠ Trying fallback raw concatenation...", flush=True)
            # 실패 시 Fallback으로 이동
            _merge_raw_audio(all_results, output_filename)
    else:
        # pydub가 없거나 로드 실패 시 Raw Concatenation
        reason = "pydub not installed" if not PYDUB_AVAILABLE else "ffmpeg missing or load failed"
        print(f"  ⚠ Warning: {reason}, merging using raw binary concatenation", flush=True)
        _merge_raw_audio(all_results, output_filename)


def _merge_raw_audio(all_results: dict[int, bytes], output_filename: str) -> None:
    """Raw MP3 바이트를 단순 연결하여 저장 (Fallback)"""
    try:
        print(f"\n  💾 Merging {len(all_results)} audio segments (raw binary mode)...", flush=True)
        with open(output_filename, 'wb') as f:
            for i in sorted(all_results.keys()):
                f.write(all_results[i])
        
        if os.path.exists(output_filename):
            print(f"\n  ✨ Output Saved (Raw Merge): {output_filename}", flush=True)
        else:
            raise Exception("File write failed")
    except Exception as e:
        log_error(f"Failed to merge raw audio: {e}", context="_merge_raw_audio", exception=e)
        print(f"  ✗ Error: Failed to merge raw audio: {e}", flush=True)
        raise


def text_to_speech_radio_show(
    dialogues: list[dict],
    output_filename: str,
    voice_profile: dict,
    language: str,
    narrative_mode: str = "radio_show",
    tts_backend: str = "cloud",
    tts_model_name: str = "gemini-2.5-pro-tts",
    genai_tts_model_id: str = "gemini-2.5-flash-preview-tts",
) -> None:
    """
    라디오쇼 모드: 화자별로 다른 음성을 사용해 순차적으로 합성하고 병합합니다.
    
    dialogues 예시:
    [
        {"speaker": 1, "text": "..."},
        {"speaker": 2, "text": "..."}
    ]
    """
    if not dialogues:
        print("  ⚠ Warning: dialogues is empty", flush=True)
        return
    
    if not isinstance(voice_profile, dict) or "host1" not in voice_profile or "host2" not in voice_profile:
        raise ValueError("Radio show mode requires voice_profile with host1 and host2")
    
    host_profiles = {
        1: voice_profile.get("host1"),
        2: voice_profile.get("host2"),
    }
    
    audio_segments = []
    total_requests = len(dialogues)
    request_submit_times: dict[int, float] = {}
    completion_times: list[float] = []
    all_results: dict[int, bytes] = {}
    all_failed: list[int] = []
    
    start_time = time.time()
    print(f"\n🎙️  Starting Radio Show TTS ({total_requests} turns)\n", flush=True)
    print("  " + "-" * 60, flush=True)
    
    for idx, dlg in enumerate(dialogues):
        speaker_num = dlg.get("speaker", 1)
        text = dlg.get("text", "").strip()
        if not text:
            all_failed.append(idx)
            print(f"  ⚠ Warning: Dialogue {idx+1} is empty, skipping", flush=True)
            continue
        
        speaker_voice = host_profiles.get(speaker_num, host_profiles[1])
        if not speaker_voice:
            all_failed.append(idx)
            print(f"  ⚠ Warning: Dialogue {idx+1} speaker profile missing, skipping", flush=True)
            continue
        
        # 9개까지는 1분 안에 다 보낼 수 있도록 허용 (9개 초과 시에만 대기)
        if idx >= int(QUOTA_TTS_RPM):
            _wait_for_rate_limit()
        else:
            # 9개 이하는 대기 없이 바로 기록만 (요청 시간 기록)
            with _tts_request_lock:
                now = time.time()
                # 1분 이전의 기록 제거
                while _tts_request_times and _tts_request_times[0] < now - 60:
                    _tts_request_times.popleft()
                # 현재 요청 시간 기록
                _tts_request_times.append(now)
        request_submit_times[idx] = time.time()
        
        current_time_str = datetime.now().strftime("%H:%M:%S")
        print(f"  [{current_time_str}] ⏳ Dialogue {idx+1}/{total_requests} (Host {speaker_num}) sending...", flush=True)
        
        try:
            audio_data, _ = synthesize_with_retry(
                text,
                speaker_voice,
                language,
                5,
                idx,
                total_requests,
                narrative_mode,
                tts_backend,
                tts_model_name,
                genai_tts_model_id,
            )
            if audio_data:
                all_results[idx] = audio_data
                duration = time.time() - request_submit_times[idx]
                completion_times.append(duration)
                audio_kb = len(audio_data) / 1024.0
                print(f"  [{datetime.now().strftime('%H:%M:%S')}] ✅ Dialogue {idx+1}: Host {speaker_num} ({audio_kb:.1f}KB, {duration:.1f}s)", flush=True)
            else:
                all_failed.append(idx)
                print(f"  [{datetime.now().strftime('%H:%M:%S')}] ❌ Dialogue {idx+1}: Empty audio", flush=True)
        except Exception as e:
            all_failed.append(idx)
            print(f"  [{datetime.now().strftime('%H:%M:%S')}] ❌ Dialogue {idx+1}: Failed ({type(e).__name__})", flush=True)
            print(f"      └─ Error: {str(e)[:150]}", flush=True)
    
    if not all_results:
        raise Exception("Radio show TTS failed: no successful dialogues")
    
    # 병합
    # 병합
    if PYDUB_AVAILABLE:
        print(f"\n  💾 Merging {len(all_results)} dialogue audios...", flush=True)
        
        # pydub로 시도
        combined = None
        success_pydub = False
        
        try:
            silence = AudioSegment.silent(duration=300)
            segments = []
            
            for i in sorted(all_results.keys()):
                audio_data = all_results[i]
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
                    tmp.write(audio_data)
                    tmp_path = tmp.name
                
                try:
                    segment = AudioSegment.from_mp3(tmp_path)
                    segments.append(segment)
                finally:
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass
            
            if len(segments) == len(all_results):
                combined = segments[0]
                for seg in segments[1:]:
                    combined += silence + seg
                
                combined.export(output_filename, format="mp3")
                print(f"  ✨ Radio show output saved: {output_filename}", flush=True)
                success_pydub = True
            
        except Exception as e:
            print(f"  ⚠ Pydub merge failed (likely ffmpeg missing): {e}", flush=True)
            print("  ⚠ Falling back to raw binary concatenation...", flush=True)
        
        if not success_pydub:
            _merge_raw_audio(all_results, output_filename)
        
    else:
        # pydub 없으면 raw merge
        print(f"  ⚠ Warning: pydub missing, using raw binary concatenation", flush=True)
        _merge_raw_audio(all_results, output_filename)
    
    elapsed = time.time() - start_time
    print(f"\n  📊 Radio show TTS summary: success {len(all_results)}/{total_requests}, failed {len(all_failed)}, time {elapsed:.1f}s\n", flush=True)


def _build_dialogue_batches(
    dialogues: list[dict],
    batch_size: int = 9,
    byte_limit: int = 4000,
    safety_margin: int = 200
) -> list[str]:
    """
    대화 리스트를 배치로 분할 (기본 9개/배치) + 바이트 한도(4000 - margin).
    - byte_limit: Gemini-TTS 입력 한도 (기본 4000B)
    - safety_margin: 안전 여유 (기본 200B)
    """
    max_bytes = byte_limit - safety_margin
    if max_bytes < 800:  # 너무 작아지지 않도록 최소 확보
        max_bytes = 800
    
    batches = []
    current_lines = []
    current_bytes = 0
    current_count = 0
    
    for dlg in dialogues:
        spk = dlg.get("speaker", 1)
        txt = dlg.get("text", "").strip()
        if not txt:
            continue
        
        line = f"Host {spk}: {txt}"
        line_bytes = len(line.encode("utf-8")) + 1  # 줄바꿈 고려
        
        # 배치 크기 또는 바이트 한도 초과 시 새 배치 시작
        if (current_count >= batch_size or (current_bytes + line_bytes > max_bytes and current_lines)):
            if current_lines:
                batches.append("\n".join(current_lines))
                current_lines = []
                current_bytes = 0
                current_count = 0
        
        current_lines.append(line)
        current_bytes += line_bytes
        current_count += 1
    
    if current_lines:
        batches.append("\n".join(current_lines))
    return batches


def text_to_speech_radio_show_structured(
    dialogues: list[dict],
    output_filename: str,
    language: str,
    model_name: str = "gemini-2.5-pro-tts",
    representative_voice: str | None = None,
    host1_voice: str | None = None,
    host2_voice: str | None = None,
    batch_size: int = 9,
    byte_limit: int = 4000,
    safety_margin: int = 200,
    max_workers: int = 9,
    narrative_mode: str = "radio_show",
    tts_backend: str = "cloud",
    genai_tts_model_id: str = "gemini-2.5-flash-preview-tts",
) -> None:
    """
    라디오쇼 멀티스피커: 구조적 청킹(여러 요청) + Host 라벨을 명시적으로 유지.
    - 일반 모드처럼 9개씩 배치로 처리 (batch_size=9) + 바이트 한도 자동 계산.
    - freeform single-request보다 안정적: 길이/바이트 초과 시 자동 배치 분할.
    - Google 가이드의 멀티스피커 합성 흐름을 따르되, 4000B 제한을 안전하게 회피.
    """
    if not dialogues:
        print("  ⚠ Warning: dialogues is empty", flush=True)
        return
    
    batches = _build_dialogue_batches(
        dialogues,
        batch_size=batch_size,
        byte_limit=byte_limit,
        safety_margin=safety_margin
    )
    if not batches:
        print("  ⚠ Warning: no batches created for radio show", flush=True)
        return

    # Cookbook(Audio-out) 백엔드: 구조적 배치 텍스트를 그대로 TTS 청크로 처리
    if (tts_backend or "").lower() in ("genai", "gemini_audio", "gemini_api_audio", "audio_out"):
        vp = {"name": (representative_voice or "Kore"), "gender": "FEMALE"}
        return text_to_speech_from_chunks(
            text_chunks=batches,
            output_filename=output_filename,
            voice_profile=vp,
            language=language,
            narrative_mode=narrative_mode,
            tts_backend=tts_backend,
            tts_model_name=model_name,  # 의미 없지만 인터페이스 통일
            genai_tts_model_id=genai_tts_model_id,
        )
    
    client = texttospeech.TextToSpeechClient()
    language_code = "ko-KR" if language == "ko" else "en-US"
    voice_name = representative_voice if representative_voice else "Kore"
    
    audio_segments = []
    total_requests = len(batches)
    request_interval = 60.0 / QUOTA_TTS_RPM
    
    print(f"\n🎙️  Radio show structured synthesis: {len(batches)} batch(es) (up to {batch_size} dialogues per batch)", flush=True)
    print("  " + "-" * 60, flush=True)
    print(f"  • Total Batches  : {total_requests}", flush=True)
    print(f"  • Rate Limit     : {QUOTA_TTS_RPM:.0f} RPM (1 every {request_interval:.1f}s)", flush=True)
    print("  " + "-" * 60 + "\n", flush=True)
    
    request_submit_times: dict[int, float] = {}
    start_time = time.time()
    
    # 비동기 제출로 대기 없이 연속 전송(전송 간격은 9RPM 준수)
    from concurrent.futures import ThreadPoolExecutor, as_completed
    futures: dict = {}
    audio_results: dict[int, bytes] = {}
    failure_indices: list[int] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for i, batch_text in enumerate(batches):
            # 9개까지는 1분 안에 다 보낼 수 있도록 허용 (9개 초과 시에만 대기)
            if i >= int(QUOTA_TTS_RPM):
                _wait_for_rate_limit()
            else:
                # 9개 이하는 대기 없이 바로 기록만 (요청 시간 기록)
                with _tts_request_lock:
                    now = time.time()
                    # 1분 이전의 기록 제거
                    while _tts_request_times and _tts_request_times[0] < now - 60:
                        _tts_request_times.popleft()
                    # 현재 요청 시간 기록
                    _tts_request_times.append(now)
            request_submit_times[i] = time.time()
            
            # text가 4000 bytes를 초과하면 안 됨
            text_bytes = len(batch_text.encode("utf-8"))
            total_bytes = text_bytes
            
            if total_bytes > 4000:
                raise ValueError(f"Batch {i+1} exceeds 4000B even after chunking ({total_bytes}B). Shorten turns further.")
            
            # Cloud Gemini-TTS: prompt 누수 방지용으로 text만 전달
            synthesis_input = texttospeech.SynthesisInput(text=batch_text)
            voice = texttospeech.VoiceSelectionParams(
                language_code=language_code,
                name=voice_name,
                model_name=model_name,
            )
            audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
            
            current_time_str = datetime.now().strftime("%H:%M:%S")
            print(f"  [{current_time_str}] ⏳ Batch {i+1}/{total_requests} ({total_bytes}B) sending...", flush=True)
            
            future = executor.submit(
                client.synthesize_speech,
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
            )
            futures[future] = (i, total_bytes)
        
        # 완료되는 대로 수집
        for future in as_completed(futures):
            idx, total_bytes = futures[future]
            try:
                response = future.result()
                audio_results[idx] = response.audio_content
                duration = time.time() - request_submit_times.get(idx, time.time())
                audio_kb = len(response.audio_content) / 1024.0
                print(f"  [{datetime.now().strftime('%H:%M:%S')}] ✅ Batch {idx+1}/{total_requests}: SUCCESS ({total_bytes}B → {audio_kb:.1f}KB, {duration:.1f}s)", flush=True)
            except Exception as e:
                failure_indices.append(idx)
                print(f"  [{datetime.now().strftime('%H:%M:%S')}] ❌ Batch {idx+1}/{total_requests}: FAILED ({type(e).__name__})", flush=True)
                print(f"      └─ Error: {str(e)[:150]}", flush=True)
                raise
    
    # 병합
    if not audio_results:
        raise Exception("No audio segments generated in structured radio show TTS")
    
    # 인덱스 순서대로 정렬하여 audio_segments 생성
    for idx in sorted(audio_results.keys()):
        audio_segments.append(audio_results[idx])
    
    if PYDUB_AVAILABLE:
        print(f"\n  💾 Merging {len(audio_segments)} batch audios...", flush=True)
        success_pydub = False
        
        try:
            silence = AudioSegment.silent(duration=300)
            pydub_segments = []
            
            for idx, audio_data in enumerate(audio_segments):
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
                    tmp.write(audio_data)
                    tmp_path = tmp.name
                try:
                    seg = AudioSegment.from_mp3(tmp_path)
                    pydub_segments.append(seg)
                finally:
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass
            
            if len(pydub_segments) == len(audio_segments):
                combined = pydub_segments[0]
                for seg in pydub_segments[1:]:
                    combined += silence + seg
                
                combined.export(output_filename, format="mp3")
                print(f"  ✓ Structured radio show audio saved: {output_filename}", flush=True)
                success_pydub = True
                
        except Exception as e:
            print(f"  ⚠ Pydub merge failed (likely ffmpeg missing): {e}", flush=True)
            print("  ⚠ Falling back to raw binary concatenation...", flush=True)
            
        if not success_pydub:
             # 재구성을 위해 all_results 형태(dict)로 변환
            dummy_dict = {i: data for i, data in enumerate(audio_segments)}
            _merge_raw_audio(dummy_dict, output_filename)
        
    else:
        # pydub 없으면 raw merge
        print(f"  ⚠ Warning: pydub missing, using raw binary concatenation", flush=True)
        dummy_dict = {i: data for i, data in enumerate(audio_segments)}
        _merge_raw_audio(dummy_dict, output_filename)

def sanitize_path_component(text: str) -> str:
    """파일 경로에 사용할 수 없는 문자를 제거합니다."""
    if not text:
        return ""
    
    # Windows에서 사용할 수 없는 문자 제거
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', text)
    sanitized = sanitized.strip('. ')
    return sanitized[:100]  # 길이 제한


def prepare_output_directory(audio_title: str, voice_name: str, language_code: str, mode_label: str, narrative_mode: str = None) -> tuple[Path, str]:
    """출력 디렉토리를 생성하고 경로를 반환합니다.
    
    Args:
        audio_title: 오디오 제목 (영어)
        voice_name: 음성 이름
        language_code: 언어 코드 (ko-KR 또는 en-US)
        mode_label: 모드 레이블 (한국어, 사용 안 함)
        narrative_mode: 서사 모드 키 (mentor, friend, lover, radio_show)
    
    Returns:
        (output_dir, folder_name) 튜플
    """
    title_safe = sanitize_path_component(audio_title)
    voice_safe = sanitize_path_component(voice_name)
    
    # 모드 키를 영어로 변환 (narrative_mode가 없으면 mode_label에서 추출 시도)
    if narrative_mode:
        mode_key = narrative_mode
    else:
        # mode_label에서 키 추출 시도 (fallback)
        mode_key = "mentor"  # 기본값
    
    # 언어 코드를 간단하게 변환 (ko-KR -> KO, en-US -> EN)
    lang_short = "KO" if language_code.startswith("ko") else "EN"
    
    # 폴더명 형식: {title}_{mode}_{voice}_{lang}
    folder_name = f"{title_safe}_{mode_key}_{voice_safe}_{lang_short}"
    folder_name = folder_name[:200]  # 폴더명 길이 제한
    
    output_dir = OUTPUT_ROOT / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    
    return output_dir, folder_name


def build_output_paths(audio_title: str, voice_name: str, language_code: str, mode_label: str, narrative_mode: str = None) -> dict:
    """출력 파일 경로들을 생성합니다.
    
    Args:
        audio_title: 오디오 제목 (영어)
        voice_name: 음성 이름
        language_code: 언어 코드 (ko-KR 또는 en-US)
        mode_label: 모드 레이블 (사용 안 함)
        narrative_mode: 서사 모드 키 (mentor, friend, lover, radio_show)
    
    Returns:
        출력 파일 경로 딕셔너리
    """
    output_dir, _ = prepare_output_directory(audio_title, voice_name, language_code, mode_label, narrative_mode)
    
    title_safe = sanitize_path_component(audio_title)
    
    # 모드 키와 언어 코드 추출
    if narrative_mode:
        mode_key = narrative_mode
    else:
        mode_key = "mentor"  # 기본값
    
    lang_short = "KO" if language_code.startswith("ko") else "EN"
    voice_safe = sanitize_path_component(voice_name)
    
    # 오디오 파일명 형식: {title}_{mode}_{voice}_{lang}.mp3
    audio_filename = f"{title_safe}_{mode_key}_{voice_safe}_{lang_short}.mp3"
    
    return {
        "audio_file": output_dir / audio_filename,
        "refined_text": output_dir / "refined_text.txt",
        "audio_title": output_dir / "audio_title.txt",
        "blueprint": output_dir / "showrunner_segments.json",
    }


def save_latest_run_path(output_dir: Path) -> None:
    """최근 실행 출력 디렉토리 경로를 저장합니다."""
    try:
        with open(LATEST_RUN_MARKER, "w", encoding="utf-8") as f:
            f.write(str(output_dir))
    except Exception as e:
        log_error(f"Failed to save latest run path: {e}", context="save_latest_run_path", exception=e)


def parse_script_dialogues(script_text: str, narrative_mode: str, voice_profile: dict = None) -> list:
    """
    스크립트 텍스트를 파싱하여 화자별 대화 목록으로 변환합니다.
    
    Args:
        script_text: 스크립트 텍스트
        narrative_mode: 서사 모드 (mentor, friend, lover, radio_show)
        voice_profile: 음성 프로필 딕셔너리
        
    Returns:
        대화 목록 [{"speaker": "Host 1", "speaker_name": "Achernar", "text": "..."}]
    """
    dialogues = []
    
    if narrative_mode == "radio_show":
        # 라디오쇼 모드: Host 1:, Host 2: 패턴으로 파싱
        # 화자 이름 추출
        host1_name = "Host 1"
        host2_name = "Host 2"
        
        if voice_profile:
            if isinstance(voice_profile, dict):
                # 라디오쇼는 host1_voice, host2_voice를 가짐
                host1_voice = voice_profile.get("host1_voice", {})
                host2_voice = voice_profile.get("host2_voice", {})
                
                if isinstance(host1_voice, dict):
                    host1_name = host1_voice.get("name", "Host 1")
                elif isinstance(host1_voice, str):
                    host1_name = host1_voice
                    
                if isinstance(host2_voice, dict):
                    host2_name = host2_voice.get("name", "Host 2")
                elif isinstance(host2_voice, str):
                    host2_name = host2_voice
        
        # 스크립트를 Host 1: / Host 2: 패턴으로 분할
        lines = script_text.split('\n')
        current_speaker = None
        current_text = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Host 1: 또는 Host 2: 패턴 감지
            if line.startswith("Host 1:") or line.startswith("호스트 1:"):
                # 이전 대화 저장
                if current_speaker and current_text:
                    dialogues.append({
                        "speaker": current_speaker,
                        "speaker_name": host1_name if current_speaker == "Host 1" else host2_name,
                        "text": " ".join(current_text)
                    })
                current_speaker = "Host 1"
                current_text = [line.split(":", 1)[1].strip() if ":" in line else ""]
            elif line.startswith("Host 2:") or line.startswith("호스트 2:"):
                # 이전 대화 저장
                if current_speaker and current_text:
                    dialogues.append({
                        "speaker": current_speaker,
                        "speaker_name": host1_name if current_speaker == "Host 1" else host2_name,
                        "text": " ".join(current_text)
                    })
                current_speaker = "Host 2"
                current_text = [line.split(":", 1)[1].strip() if ":" in line else ""]
            else:
                # 현재 화자의 대화에 추가
                if current_speaker:
                    current_text.append(line)
        
        # 마지막 대화 저장
        if current_speaker and current_text:
            dialogues.append({
                "speaker": current_speaker,
                "speaker_name": host1_name if current_speaker == "Host 1" else host2_name,
                "text": " ".join(current_text)
            })
    
    else:
        # 다른 모드: 단일 화자
        speaker_name = "Narrator"
        if voice_profile:
            if isinstance(voice_profile, dict):
                speaker_name = voice_profile.get("name", "Narrator")
            elif isinstance(voice_profile, str):
                speaker_name = voice_profile
        
        # 전체 스크립트를 하나의 대화로
        dialogues.append({
            "speaker": "Narrator",
            "speaker_name": speaker_name,
            "text": script_text.strip()
        })
    
    return dialogues


def generate_voronoi_cover_art(output_path: str, width: int = 1000, height: int = 1000, seed: int = None, title: str = None, voice_name: str = None) -> str:
    """
    Voronoi Diagram을 사용한 기하학적 커버 아트를 생성합니다.
    
    큐레이션된 컬러 팔레트에서 랜덤 색상을 선택하여 매번 고유한 디자인을 만듭니다.
    중앙에 검은색 밴드를 배치하고 그 안에 제목과 발화자 이름을 표시합니다.
    
    Args:
        output_path: 생성된 이미지를 저장할 경로
        width: 이미지 너비 (기본값: 1000)
        height: 이미지 높이 (기본값: 1000)
        seed: 랜덤 시드 (None이면 현재 시간 기반)
        title: 이미지에 표시할 제목 (None이면 표시하지 않음)
        voice_name: 발화자 이름 (제목 아래에 표시)
        
    Returns:
        생성된 이미지 파일 경로
    """
    try:
        import numpy as np
        from scipy.spatial import Voronoi
        from PIL import Image, ImageDraw
        
        # 큐레이션된 컬러 팔레트 (10-15개 색상 조합)
        # 전문가가 큐레이션한 세련된 색상 조합
        color_palettes = [
            # 따뜻한 톤
            [(255, 107, 107), (255, 159, 64), (255, 206, 84), (75, 192, 192), (54, 162, 235)],
            # 차가운 톤
            [(99, 102, 241), (139, 92, 246), (168, 85, 247), (196, 181, 253), (221, 214, 254)],
            # 자연스러운 톤
            [(34, 197, 94), (59, 130, 246), (168, 85, 247), (236, 72, 153), (251, 146, 60)],
            # 모노크롬
            [(30, 41, 59), (51, 65, 85), (71, 85, 105), (148, 163, 184), (203, 213, 225)],
            # 생동감 있는 톤
            [(239, 68, 68), (249, 115, 22), (234, 179, 8), (34, 197, 94), (59, 130, 246)],
            # 파스텔 톤
            [(254, 202, 202), (254, 240, 138), (187, 247, 208), (196, 181, 253), (221, 214, 254)],
            # 어두운 톤
            [(15, 23, 42), (30, 41, 59), (51, 65, 85), (100, 116, 139), (148, 163, 184)],
            # 밝은 톤
            [(255, 255, 255), (241, 245, 249), (226, 232, 240), (203, 213, 225), (148, 163, 184)],
        ]
        
        # 랜덤 시드 설정
        if seed is None:
            seed = int(time.time() * 1000) % 1000000
        np.random.seed(seed)
        random.seed(seed)
        
        # 팔레트 선택
        selected_palette = random.choice(color_palettes)
        
        # 50-80개의 랜덤 시드 포인트 생성 (더 많은 파편으로 꽉 채움)
        num_points = random.randint(50, 80)
        points = np.random.rand(num_points, 2) * np.array([width, height])
        
        # 경계를 벗어나지 않도록 조정 (margin 최소화)
        margin = 10
        points[:, 0] = np.clip(points[:, 0], margin, width - margin)
        points[:, 1] = np.clip(points[:, 1], margin, height - margin)
        
        # Voronoi 다이어그램 생성
        # 경계 처리를 위해 경계 밖에 더미 포인트 추가
        boundary_points = np.array([
            [-width, -height], [width * 2, -height], [-width, height * 2], [width * 2, height * 2],
            [width // 2, -height], [width // 2, height * 2], [-width, height // 2], [width * 2, height // 2]
        ])
        all_points = np.vstack([points, boundary_points])
        
        vor = Voronoi(all_points)
        
        # 이미지 생성
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)
        
        # 각 Voronoi 영역에 색상 할당
        for region_idx in vor.point_region[:num_points]:
            region = vor.regions[region_idx]
            if -1 not in region and len(region) > 0:
                # 랜덤 색상 선택
                color = random.choice(selected_palette)
                
                # 영역 좌표 추출
                vertices = [tuple(vor.vertices[i]) for i in region]
                
                # 경계 내부의 좌표만 필터링
                valid_vertices = [(x, y) for x, y in vertices if 0 <= x <= width and 0 <= y <= height]
                
                if len(valid_vertices) >= 3:
                    # 다각형 그리기
                    draw.polygon(valid_vertices, fill=color, outline=None)
        
        # 중앙 검은색 밴드 그리기 (높이의 약 1/3)
        band_height = height // 3
        band_y_start = (height - band_height) // 2
        band_y_end = band_y_start + band_height
        draw.rectangle([(0, band_y_start), (width, band_y_end)], fill=(0, 0, 0))
        
        # 제목 및 발화자 이름 텍스트 추가 (검은색 밴드 내부)
        if title:
            try:
                from PIL import ImageFont
                
                # 밴드 내부 여유 공간 (padding)
                band_padding = 20
                band_inner_width = width - (band_padding * 2)
                band_inner_height = band_height - (band_padding * 2)
                band_inner_y_start = band_y_start + band_padding
                band_inner_y_end = band_y_end - band_padding
                
                # 제목 폰트 크기: 밴드 내부 너비에 맞게 조정
                title_font_size = max(30, min(60, int(band_inner_width * 0.08)))
                
                # 발화자 이름 폰트 크기: 제목의 60%
                voice_font_size = max(18, int(title_font_size * 0.6))
                
                # 기본 폰트 사용 (시스템 폰트가 없을 경우 대비)
                try:
                    # Windows 기본 폰트 시도
                    if os.name == 'nt':
                        title_font = ImageFont.truetype("arial.ttf", title_font_size)
                        voice_font = ImageFont.truetype("arial.ttf", voice_font_size)
                    else:
                        # Linux/Mac 기본 폰트 시도
                        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", title_font_size)
                        voice_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", voice_font_size)
                except:
                    # 기본 폰트 사용
                    title_font = ImageFont.load_default()
                    voice_font = ImageFont.load_default()
                
                # 제목 텍스트 준비 (밴드 내부 너비에 맞게 줄바꿈)
                # 실제 텍스트 너비를 측정하여 줄바꿈 결정
                test_bbox = draw.textbbox((0, 0), title, font=title_font) if hasattr(draw, 'textbbox') else None
                if test_bbox:
                    test_width = test_bbox[2] - test_bbox[0]
                else:
                    try:
                        test_width, _ = draw.textsize(title, font=title_font)
                    except:
                        test_width = len(title) * title_font_size * 0.6  # 근사값
                
                if test_width > band_inner_width:
                    # 텍스트가 너무 길면 줄바꿈
                    words = title.split()
                    lines = []
                    current_line = ""
                    for word in words:
                        test_line = (current_line + " " + word).strip() if current_line else word
                        test_bbox = draw.textbbox((0, 0), test_line, font=title_font) if hasattr(draw, 'textbbox') else None
                        if test_bbox:
                            line_width = test_bbox[2] - test_bbox[0]
                        else:
                            try:
                                line_width, _ = draw.textsize(test_line, font=title_font)
                            except:
                                line_width = len(test_line) * title_font_size * 0.6
                        
                        if line_width <= band_inner_width:
                            current_line = test_line
                        else:
                            if current_line:
                                lines.append(current_line)
                            current_line = word
                    if current_line:
                        lines.append(current_line)
                    title_lines = lines[:2]  # 최대 2줄
                else:
                    title_lines = [title]
                
                # 텍스트 위치 계산 (밴드 내부 중앙)
                title_line_height = title_font_size + 10
                total_title_height = len(title_lines) * title_line_height
                voice_text_height = voice_font_size + 8
                spacing = 10
                total_text_height = total_title_height + (voice_text_height if voice_name else 0) + (spacing if voice_name else 0)
                
                # 밴드 내부 중앙에 배치
                band_inner_center_y = band_inner_y_start + band_inner_height // 2
                title_start_y = band_inner_center_y - total_text_height // 2
                
                # 제목 텍스트 그리기
                for i, line in enumerate(title_lines):
                    # 텍스트 크기 측정 (PIL 버전 호환성)
                    try:
                        # PIL 10.0.0+ (textbbox 사용)
                        bbox = draw.textbbox((0, 0), line, font=title_font)
                        text_width = bbox[2] - bbox[0]
                        text_height = bbox[3] - bbox[1]
                    except AttributeError:
                        # 구버전 PIL (textsize 사용)
                        text_width, text_height = draw.textsize(line, font=title_font)
                    
                    # 텍스트가 밴드 내부 너비를 벗어나지 않도록 확인
                    if text_width > band_inner_width:
                        # 텍스트가 너무 길면 자르기
                        line = line[:int(len(line) * band_inner_width / text_width * 0.9)] + "..."
                        try:
                            bbox = draw.textbbox((0, 0), line, font=title_font)
                            text_width = bbox[2] - bbox[0]
                        except AttributeError:
                            text_width, _ = draw.textsize(line, font=title_font)
                    
                    text_x = (width - text_width) // 2  # 중앙 정렬
                    text_y = title_start_y + i * title_line_height
                    
                    # 텍스트가 밴드 경계를 벗어나지 않도록 확인
                    if text_y < band_inner_y_start:
                        text_y = band_inner_y_start
                    if text_y + text_height > band_inner_y_end:
                        text_y = band_inner_y_end - text_height
                    
                    # 텍스트가 이미지 경계를 벗어나지 않도록 확인
                    text_x = max(band_padding, min(text_x, width - text_width - band_padding))
                    
                    # 흰색 텍스트 (검은색 밴드 위에)
                    draw.text(
                        (text_x, text_y),
                        line,
                        fill=(255, 255, 255),
                        font=title_font
                    )
                
                # 발화자 이름 텍스트 그리기 (제목 아래)
                if voice_name:
                    try:
                        bbox = draw.textbbox((0, 0), voice_name, font=voice_font)
                        voice_text_width = bbox[2] - bbox[0]
                        voice_text_height = bbox[3] - bbox[1]
                    except AttributeError:
                        voice_text_width, voice_text_height = draw.textsize(voice_name, font=voice_font)
                    
                    # 발화자 이름이 너무 길면 자르기
                    display_voice_name = voice_name
                    if voice_text_width > band_inner_width:
                        display_voice_name = voice_name[:int(len(voice_name) * band_inner_width / voice_text_width * 0.9)] + "..."
                        try:
                            bbox = draw.textbbox((0, 0), display_voice_name, font=voice_font)
                            voice_text_width = bbox[2] - bbox[0]
                        except AttributeError:
                            voice_text_width, _ = draw.textsize(display_voice_name, font=voice_font)
                    
                    voice_text_x = (width - voice_text_width) // 2  # 중앙 정렬
                    voice_text_y = title_start_y + total_title_height + spacing
                    
                    # 텍스트가 밴드 경계를 벗어나지 않도록 확인
                    if voice_text_y < band_inner_y_start:
                        voice_text_y = band_inner_y_start
                    if voice_text_y + voice_text_height > band_inner_y_end:
                        voice_text_y = band_inner_y_end - voice_text_height
                    
                    # 텍스트가 이미지 경계를 벗어나지 않도록 확인
                    voice_text_x = max(band_padding, min(voice_text_x, width - voice_text_width - band_padding))
                    
                    # 흰색 텍스트 (검은색 밴드 위에)
                    draw.text(
                        (voice_text_x, voice_text_y),
                        display_voice_name,
                        fill=(255, 255, 255),
                        font=voice_font
                    )
            except Exception as e:
                log_error(f"Failed to add title to cover art: {e}", context="generate_voronoi_cover_art", exception=e)
                print(f"  ⚠ Warning: Failed to add title text to cover art: {e}", flush=True)
        
        # 이미지 저장 (JPEG로 저장)
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        # JPEG로 저장 (품질 95)
        if output_path_obj.suffix.lower() in ('.jpg', '.jpeg'):
            img.save(output_path, 'JPEG', quality=95, optimize=True)
        else:
            img.save(output_path, 'PNG')
        
        return output_path
        
    except ImportError as e:
        # 라이브러리가 없으면 기본 그라데이션 이미지 생성
        log_error(f"Voronoi cover art generation failed (missing library): {e}", context="generate_voronoi_cover_art", exception=e)
        try:
            from PIL import Image, ImageDraw
            
            # 기본 그라데이션 이미지 생성
            img = Image.new('RGB', (width, height), color='white')
            draw = ImageDraw.Draw(img)
            
            # 간단한 그라데이션
            for y in range(height):
                r = int(100 + (y / height) * 155)
                g = int(150 + (y / height) * 105)
                b = int(200 + (y / height) * 55)
                draw.line([(0, y), (width, y)], fill=(r, g, b))
            
            # 중앙 검은색 밴드 그리기 (높이의 약 1/3)
            band_height = height // 3
            band_y_start = (height - band_height) // 2
            band_y_end = band_y_start + band_height
            draw.rectangle([(0, band_y_start), (width, band_y_end)], fill=(0, 0, 0))
            
            # 제목 및 발화자 이름 추가 (폴백 이미지에도)
            if title:
                try:
                    from PIL import ImageFont
                    
                    # 밴드 내부 여유 공간 (padding)
                    band_padding = 20
                    band_inner_width = width - (band_padding * 2)
                    band_inner_height = band_height - (band_padding * 2)
                    band_inner_y_start = band_y_start + band_padding
                    band_inner_y_end = band_y_end - band_padding
                    
                    title_font_size = max(30, min(60, int(band_inner_width * 0.08)))
                    voice_font_size = max(18, int(title_font_size * 0.6))
                    try:
                        if os.name == 'nt':
                            title_font = ImageFont.truetype("arial.ttf", title_font_size)
                            voice_font = ImageFont.truetype("arial.ttf", voice_font_size)
                        else:
                            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", title_font_size)
                            voice_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", voice_font_size)
                    except:
                        title_font = ImageFont.load_default()
                        voice_font = ImageFont.load_default()
                    
                    # 텍스트 너비 측정하여 줄바꿈 결정
                    test_bbox = draw.textbbox((0, 0), title, font=title_font) if hasattr(draw, 'textbbox') else None
                    if test_bbox:
                        test_width = test_bbox[2] - test_bbox[0]
                    else:
                        try:
                            test_width, _ = draw.textsize(title, font=title_font)
                        except:
                            test_width = len(title) * title_font_size * 0.6
                    
                    if test_width > band_inner_width:
                        words = title.split()
                        lines = []
                        current_line = ""
                        for word in words:
                            test_line = (current_line + " " + word).strip() if current_line else word
                            test_bbox = draw.textbbox((0, 0), test_line, font=title_font) if hasattr(draw, 'textbbox') else None
                            if test_bbox:
                                line_width = test_bbox[2] - test_bbox[0]
                            else:
                                try:
                                    line_width, _ = draw.textsize(test_line, font=title_font)
                                except:
                                    line_width = len(test_line) * title_font_size * 0.6
                            
                            if line_width <= band_inner_width:
                                current_line = test_line
                            else:
                                if current_line:
                                    lines.append(current_line)
                                current_line = word
                        if current_line:
                            lines.append(current_line)
                        title_lines = lines[:2]
                    else:
                        title_lines = [title]
                    
                    title_line_height = title_font_size + 10
                    total_title_height = len(title_lines) * title_line_height
                    voice_text_height = voice_font_size + 8
                    spacing = 10
                    total_text_height = total_title_height + (voice_text_height if voice_name else 0) + (spacing if voice_name else 0)
                    
                    band_inner_center_y = band_inner_y_start + band_inner_height // 2
                    title_start_y = band_inner_center_y - total_text_height // 2
                    
                    for i, line in enumerate(title_lines):
                        try:
                            bbox = draw.textbbox((0, 0), line, font=title_font)
                            text_width = bbox[2] - bbox[0]
                            text_height = bbox[3] - bbox[1]
                        except AttributeError:
                            text_width, text_height = draw.textsize(line, font=title_font)
                        
                        if text_width > band_inner_width:
                            line = line[:int(len(line) * band_inner_width / text_width * 0.9)] + "..."
                            try:
                                bbox = draw.textbbox((0, 0), line, font=title_font)
                                text_width = bbox[2] - bbox[0]
                            except AttributeError:
                                text_width, _ = draw.textsize(line, font=title_font)
                        
                        text_x = (width - text_width) // 2
                        text_y = title_start_y + i * title_line_height
                        
                        if text_y < band_inner_y_start:
                            text_y = band_inner_y_start
                        if text_y + text_height > band_inner_y_end:
                            text_y = band_inner_y_end - text_height
                        
                        text_x = max(band_padding, min(text_x, width - text_width - band_padding))
                        draw.text((text_x, text_y), line, fill=(255, 255, 255), font=title_font)
                    
                    if voice_name:
                        try:
                            bbox = draw.textbbox((0, 0), voice_name, font=voice_font)
                            voice_text_width = bbox[2] - bbox[0]
                            voice_text_height = bbox[3] - bbox[1]
                        except AttributeError:
                            voice_text_width, voice_text_height = draw.textsize(voice_name, font=voice_font)
                        
                        display_voice_name = voice_name
                        if voice_text_width > band_inner_width:
                            display_voice_name = voice_name[:int(len(voice_name) * band_inner_width / voice_text_width * 0.9)] + "..."
                            try:
                                bbox = draw.textbbox((0, 0), display_voice_name, font=voice_font)
                                voice_text_width = bbox[2] - bbox[0]
                            except AttributeError:
                                voice_text_width, _ = draw.textsize(display_voice_name, font=voice_font)
                        
                        voice_text_x = (width - voice_text_width) // 2
                        voice_text_y = title_start_y + total_title_height + spacing
                        
                        if voice_text_y < band_inner_y_start:
                            voice_text_y = band_inner_y_start
                        if voice_text_y + voice_text_height > band_inner_y_end:
                            voice_text_y = band_inner_y_end - voice_text_height
                        
                        voice_text_x = max(band_padding, min(voice_text_x, width - voice_text_width - band_padding))
                        draw.text((voice_text_x, voice_text_y), display_voice_name, fill=(255, 255, 255), font=voice_font)
                except:
                    pass
            
            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)
            # JPEG로 저장 (품질 95)
            if output_path_obj.suffix.lower() in ('.jpg', '.jpeg'):
                img.save(output_path, 'JPEG', quality=95, optimize=True)
            else:
                img.save(output_path, 'PNG')
            print(f"  ⚠ Warning: Generated fallback gradient cover art (Voronoi libraries not available)", flush=True)
            return output_path
        except Exception as fallback_error:
            log_error(f"Fallback cover art generation also failed: {fallback_error}", context="generate_voronoi_cover_art", exception=fallback_error)
            return None
    except Exception as e:
        log_error(f"Voronoi cover art generation failed: {e}", context="generate_voronoi_cover_art", exception=e)
        print(f"  ⚠ Warning: Failed to generate Voronoi cover art: {e}", flush=True)
        return None


def add_mp3_metadata(
    mp3_path: str,
    audio_metadata: dict = None,
    audio_title: str = None,
    voice_name: str = None,
    cover_art_path: str = None
) -> bool:
    """
    MP3 파일에 ID3 태그 메타데이터와 커버 아트를 추가합니다.
    
    Args:
        mp3_path: MP3 파일 경로
        audio_metadata: 오디오 메타데이터 딕셔너리 (title, artist, album, genre, date 포함)
        audio_title: 오디오 제목 (audio_metadata.title이 없을 때 사용)
        voice_name: 음성 이름 (audio_metadata.artist가 없을 때 사용)
        cover_art_path: 커버 아트 이미지 경로 (None이면 생성하지 않음)
        
    Returns:
        성공 여부 (bool)
    """
    try:
        from mutagen.id3 import ID3, TIT2, TPE1, TALB, TCON, TDRC, APIC
        from mutagen.mp3 import MP3
        
        # MP3 파일 열기
        audio_file = MP3(mp3_path, ID3=ID3)
        
        # ID3 태그가 없으면 생성
        if audio_file.tags is None:
            audio_file.add_tags()
        
        # 메타데이터 추출
        title = None
        artist = None
        album = None
        genre = None
        date = None
        
        if audio_metadata:
            title = audio_metadata.get("title")
            artist = audio_metadata.get("artist")
            album = audio_metadata.get("album")
            genre = audio_metadata.get("genre")
            date = audio_metadata.get("date")
        
        # 기본값 설정
        if not title:
            title = audio_title or "Untitled Audiobook"
        if not artist:
            artist = voice_name or "Unknown Artist"
        if not album:
            album = audio_title or "Untitled Album"
        # genre는 기본값 설정하지 않음 (None이면 태그 추가 안 함)
        if not date:
            date = datetime.now().strftime("%Y")
        else:
            # 날짜 형식 처리: "YYYY-MM-DD" -> "YYYY"
            if isinstance(date, str) and "-" in date:
                date = date.split("-")[0]
            elif isinstance(date, str) and len(date) > 4:
                date = date[:4]
        
        # 기존 태그 삭제 후 새로 추가 (덮어쓰기)
        if "TIT2" in audio_file.tags:
            del audio_file.tags["TIT2"]
        if "TPE1" in audio_file.tags:
            del audio_file.tags["TPE1"]
        if "TALB" in audio_file.tags:
            del audio_file.tags["TALB"]
        if "TCON" in audio_file.tags:
            del audio_file.tags["TCON"]
        if "TDRC" in audio_file.tags:
            del audio_file.tags["TDRC"]
        
        # ID3 태그 추가 (UTF-8 인코딩)
        audio_file.tags.add(TIT2(encoding=3, text=str(title)))  # 제목
        audio_file.tags.add(TPE1(encoding=3, text=str(artist)))  # 아티스트
        audio_file.tags.add(TALB(encoding=3, text=str(album)))    # 앨범
        # 장르는 값이 있을 때만 추가
        if genre:
            audio_file.tags.add(TCON(encoding=3, text=str(genre)))    # 장르
        audio_file.tags.add(TDRC(encoding=3, text=str(date)))     # 연도
        
        # 커버 아트 추가
        if cover_art_path and Path(cover_art_path).exists():
            try:
                # 기존 커버 아트 삭제
                if "APIC:" in audio_file.tags:
                    del audio_file.tags["APIC:"]
                
                with open(cover_art_path, 'rb') as f:
                    cover_data = f.read()
                mime = _guess_image_mime(cover_art_path)
                
                # APIC 프레임 추가 (커버 아트)
                audio_file.tags.add(APIC(
                    encoding=3,
                    mime=mime,
                    type=3,  # Cover (front)
                    desc='Cover',
                    data=cover_data
                ))
                print(f"  ✓ Cover art embedded: {len(cover_data)} bytes", flush=True)
            except Exception as e:
                log_error(f"Failed to add cover art: {e}", context="add_mp3_metadata", exception=e)
                print(f"  ⚠ Warning: Failed to add cover art: {e}", flush=True)
        
        # 저장
        audio_file.save(v2_version=3)  # ID3v2.3 형식으로 저장
        print(f"  ✓ Metadata added: Title='{title}', Artist='{artist}', Album='{album}', Genre='{genre}', Date='{date}'", flush=True)
        return True
        
    except ImportError:
        print(f"  ⚠ Warning: mutagen library not available, skipping metadata addition", flush=True)
        return False
    except Exception as e:
        log_error(f"Failed to add MP3 metadata: {e}", context="add_mp3_metadata", exception=e)
        print(f"  ⚠ Warning: Failed to add MP3 metadata: {e}", flush=True)
        return False
