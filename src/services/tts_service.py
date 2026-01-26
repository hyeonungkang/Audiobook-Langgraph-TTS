"""
TTS Service for text-to-speech synthesis
TTS 관련 함수들을 클래스로 통합
"""
import re
from typing import Dict, Any, Optional, Tuple, List
from ..core.rate_limiter import RateLimiter, get_default_rate_limiter
from ..core.constants import TTS_MAX_BYTES, TTS_SAFETY_MARGIN


class TTSService:
    """
    TTS 관련 기능을 통합한 서비스 클래스
    """
    
    def __init__(self, rate_limiter: Optional[RateLimiter] = None):
        """
        Args:
            rate_limiter: RateLimiter 인스턴스 (None이면 기본 인스턴스 사용)
        """
        self.rate_limiter = rate_limiter or get_default_rate_limiter()
    
    def remove_ssml_tags(self, text: str) -> str:
        """
        SSML 태그를 제거하되, Gemini-TTS markup tag는 보존합니다.
        
        Gemini-TTS markup tag 형식: [tag_name] (예: [sigh], [short pause], [whispering])
        SSML 태그 형식: <tag>content</tag> (예: <speak>...</speak>)
        """
        if not text:
            return ""
        
        # SSML 태그만 제거 (꺾쇠괄호로 둘러싸인 태그)
        # Gemini-TTS markup tag는 대괄호로 둘러싸여 있으므로 보존됨
        text = re.sub(r'<[^>]+>', '', text)
        return text.strip()
    
    def chunk_text_for_tts(
        self,
        text: str,
        language: str = "ko",
        max_chunk_length: Optional[int] = None
    ) -> List[str]:
        """
        텍스트를 TTS API 제한에 맞게 청크로 분할합니다.
        
        Args:
            text: 분할할 텍스트
            language: 언어 코드
            max_chunk_length: 최대 청크 길이 (None이면 기본값 사용)
        
        Returns:
            텍스트 청크 리스트
        """
        if not text:
            return []
        
        # SSML 태그 제거
        text = self.remove_ssml_tags(text)
        
        # text의 최대 길이 = TTS_MAX_BYTES - TTS_SAFETY_MARGIN
        # max_chunk_length가 지정되지 않았으면 자동 계산
        if max_chunk_length is None:
            max_chunk_length = TTS_MAX_BYTES - TTS_SAFETY_MARGIN
            if max_chunk_length < 500:  # 최소 500 bytes는 보장
                max_chunk_length = 500
        else:
            # 지정된 max_chunk_length도 TTS_MAX_BYTES 제한 내에서 조정
            max_chunk_length = min(max_chunk_length, TTS_MAX_BYTES - TTS_SAFETY_MARGIN)
            if max_chunk_length < 500:
                max_chunk_length = 500
        
        # 문장 단위로 분할 (구분자 보존)
        if language == "ko":
            sentence_endings = r'[.!?。！？]'
        else:
            sentence_endings = r'[.!?]'
        
        # 구분자를 포함한 문장 추출 (re.finditer 사용)
        sentences_with_endings = []
        pattern = re.compile(f'(.+?)({sentence_endings})(\\s*)', re.DOTALL)
        
        last_end = 0
        for match in pattern.finditer(text):
            sentence_text = match.group(1).strip()
            ending = match.group(2)  # 구분자 (. ! ? 등)
            trailing_space = match.group(3)  # 구분자 뒤 공백
            
            if sentence_text:
                # 구분자와 함께 문장 저장
                full_sentence = sentence_text + ending + trailing_space
                sentences_with_endings.append(full_sentence)
            last_end = match.end()
        
        # 마지막 부분 처리 (구분자가 없는 나머지 텍스트)
        if last_end < len(text):
            remaining = text[last_end:].strip()
            if remaining:
                sentences_with_endings.append(remaining)
        
        # 구분자가 없는 문장이 있으면 원본 텍스트를 그대로 사용
        if not sentences_with_endings:
            sentences_with_endings = [text]
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences_with_endings:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # 현재 청크에 문장 추가 시도
            # 문장들은 이미 구분자와 공백을 포함하고 있으므로 자연스럽게 연결
            if current_chunk:
                # current_chunk 끝이 공백이 아니면 공백 하나 추가
                if not current_chunk.rstrip().endswith(('.', '!', '?', '。', '！', '？')):
                    # 구분자로 끝나지 않으면 공백 추가
                    test_chunk = current_chunk.rstrip() + " " + sentence
                else:
                    # 구분자로 끝나면 이미 공백이 포함되어 있을 수 있으므로 확인
                    if current_chunk.endswith(" "):
                        test_chunk = current_chunk + sentence
                    else:
                        test_chunk = current_chunk + " " + sentence
            else:
                test_chunk = sentence
            
            test_chunk_bytes = len(test_chunk.encode('utf-8'))
            if test_chunk_bytes <= max_chunk_length:
                current_chunk = test_chunk
            else:
                # 현재 청크를 저장
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # 문장 자체가 max_chunk_length를 초과하면 강제로 자름
                sentence_bytes = len(sentence.encode('utf-8'))
                if sentence_bytes > max_chunk_length:
                    # 문장을 단어 단위로 자름
                    words = sentence.split()
                    temp_chunk = ""
                    for word in words:
                        test_word_chunk = temp_chunk + " " + word if temp_chunk else word
                        if len(test_word_chunk.encode('utf-8')) <= max_chunk_length:
                            temp_chunk = test_word_chunk
                        else:
                            if temp_chunk:
                                chunks.append(temp_chunk.strip())
                            temp_chunk = word
                    current_chunk = temp_chunk
                else:
                    current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [text]
    
    def synthesize_with_retry(
        self,
        chunk: str,
        profile: dict,
        lang: str,
        max_retries: int = 5,
        chunk_index: Optional[int] = None,
        total_chunks: Optional[int] = None,
        narrative_mode: str = "mentor",
        tts_backend: str = "cloud",
        tts_model_name: str = "gemini-2.5-pro-tts",
        genai_tts_model_id: str = "gemini-2.5-flash-preview-tts",
    ) -> Tuple[bytes, int]:
        """
        지수 백오프를 적용한 단일 TTS 요청 함수.
        
        Args:
            chunk: 합성할 텍스트 청크
            profile: 음성 프로필
            lang: 언어 코드
            max_retries: 최대 재시도 횟수
            chunk_index: 청크 인덱스
            total_chunks: 전체 청크 수
            narrative_mode: 서사 모드
            tts_backend: TTS 백엔드
            tts_model_name: TTS 모델 이름
            genai_tts_model_id: GenAI TTS 모델 ID
        
        Returns:
            (오디오 바이트, 재시도 횟수)
        """
        # TODO: utils.py의 synthesize_with_retry 함수를 여기로 이동
        from ..utils import synthesize_with_retry
        return synthesize_with_retry(
            chunk, profile, lang, max_retries, chunk_index, total_chunks,
            narrative_mode, tts_backend, tts_model_name, genai_tts_model_id
        )
    
    def wait_for_rate_limit(self) -> None:
        """
        Rate limit을 확인하고 필요시 대기합니다.
        """
        self.rate_limiter.wait_if_needed()
