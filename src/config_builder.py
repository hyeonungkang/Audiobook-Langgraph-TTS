"""
Configuration Builder
프론트엔드에서 받은 단순 설정값을 CLI와 동일한 형태의 풍부한 설정 객체로 변환합니다.
"""
from typing import Dict, Any, Optional
from .utils import CONTENT_CATEGORIES, NARRATIVE_MODES, VOICE_BANKS, DEFAULT_NARRATIVE_MODE

def build_config(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    프론트엔드에서 받은 설정을 기반으로 전체 설정 객체를 생성합니다.
    
    Args:
        raw_config: 프론트엔드에서 전송한 설정 딕셔너리
            - language: "ko" | "en"
            - category: "research_paper" | "career" | ...
            - narrative_mode: "mentor" | "friend" | ...
            - voice: "Achernar" (단일 화자 모드 시)
            - host1_voice: "Achernar" (라디오쇼 모드 시)
            - host2_voice: "Achird" (라디오쇼 모드 시)
            - listener_name: "청취자 이름"
            - model_name: "gemini-2.5-pro" (선택적)
            
    Returns:
        AgentState에서 사용할 수 있는 완전한 config 객체
    """
    # 1. 기본 설정 복사
    config = raw_config.copy()
    
    # 2. 언어 코드 정규화 (Korean -> ko, English -> en)
    if config.get("language") == "Korean":
        config["language"] = "ko"
    elif config.get("language") == "English":
        config["language"] = "en"
    
    language = config.get("language", "ko")
    
    # 3. 카테고리 검증
    category = config.get("category", "research_paper")
    if category not in CONTENT_CATEGORIES:
        category = "research_paper"
    config["content_category"] = category  # CLI에서는 content_category 키 사용
    
    # 4. 서사 모드 검증
    mode = config.get("narrative_mode", DEFAULT_NARRATIVE_MODE)
    if mode not in NARRATIVE_MODES:
        mode = DEFAULT_NARRATIVE_MODE
    config["narrative_mode"] = mode
    
    # 4-1. 라디오쇼 멀티스피커 단일요청 옵션 (기본 True: Vertex 스타일 단일 요청)
    config["radio_show_single_request"] = bool(config.get("radio_show_single_request", True))
    
    # 5. 음성 프로필 구성 (가장 중요)
    voice_profile = {}
    
    if mode == "radio_show":
        # 라디오쇼 모드: 두 명의 화자 필요
        host1_name = config.get("host1_voice")
        host2_name = config.get("host2_voice")
        
        # 만약 host1/host2가 없는데 voice만 있다면 (잘못된 요청), voice를 host1으로 사용
        if not host1_name and config.get("voice"):
            host1_name = config.get("voice")
            
        # 기본값 처리
        if not host1_name:
            host1_name = VOICE_BANKS["female"]["default"]
        if not host2_name:
            host2_name = VOICE_BANKS["male"]["default"]
            
        host1_profile = _find_voice_profile(host1_name, 1)
        host2_profile = _find_voice_profile(host2_name, 2)
        
        voice_profile = {
            "host1": host1_profile,
            "host2": host2_profile,
            "mode": "radio_show"
        }
    else:
        # 단일 화자 모드
        voice_name = config.get("voice")
        if not voice_name:
            # 기본값: 여성 음성
            voice_name = VOICE_BANKS["female"]["default"]
            
        voice_profile = _find_voice_profile(voice_name)
        
    config["voice_profile"] = voice_profile
    
    # 6. 모델 이름 매핑 (gemini_model / tts_model_name)
    # 프론트엔드에서 model_name 또는 gemini_model 모두 지원
    if "model_name" in config:
        config["gemini_model"] = config["model_name"]
    elif "gemini_model" in config:
        # 이미 gemini_model로 온 경우 그대로 사용
        pass
    else:
        config["gemini_model"] = "gemini-2.5-flash-lite"
    
    # TTS 모델 기본값: flash-tts (멀티스피커 지원)
    if "tts_model_name" not in config:
        config["tts_model_name"] = "gemini-2.5-flash-tts"
        
    return config


def _find_voice_profile(voice_name: str, host_number: Optional[int] = None) -> Dict[str, Any]:
    """
    음성 이름으로 전체 프로필 정보를 찾습니다.
    """
    # 모든 음성 뱅크 검색
    for group_key, bank in VOICE_BANKS.items():
        for voice in bank["voices"]:
            if voice["name"] == voice_name:
                profile = {
                    "name": voice["name"],
                    "display": voice.get("display", voice["name"]),
                    "gender": voice.get("gender", "FEMALE"),
                    "group": group_key
                }
                if host_number:
                    profile["host_number"] = host_number
                return profile
                
    # 찾지 못한 경우 기본값 반환 (여성 기본)
    default_voice = VOICE_BANKS["female"]["voices"][0]
    profile = {
        "name": default_voice["name"],
        "display": default_voice.get("display", default_voice["name"]),
        "gender": default_voice.get("gender", "FEMALE"),
        "group": "female"
    }
    if host_number:
        profile["host_number"] = host_number
    return profile
