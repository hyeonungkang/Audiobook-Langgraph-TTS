"""
Command-line interface functions for user interaction
"""
from .utils import NARRATIVE_MODES, DEFAULT_NARRATIVE_MODE, VOICE_BANKS, CONTENT_CATEGORIES
from .config import application_path


def select_content_category():
    """
    사용자로부터 콘텐츠 카테고리를 선택받습니다.
    
    Returns:
        선택된 카테고리 키 (str) - "research_paper", "career", "language_learning", "philosophy", "tech_news"
    """
    category_keys = list(CONTENT_CATEGORIES.keys())
    
    print("\n📌 어떤 종류의 텍스트인가요?", flush=True)
    print("\nAvailable Categories:", flush=True)
    print("-" * 70, flush=True)
    for idx, key in enumerate(category_keys, 1):
        category = CONTENT_CATEGORIES[key]
        print(f"  {category['icon']} {idx:>2}. {category['label']}", flush=True)
        print(f"     └─ {category['description']}", flush=True)
    print("-" * 70, flush=True)
    print("="*70, flush=True)
    
    while True:
        try:
            choice = input(f"\n👉 콘텐츠 카테고리를 선택하세요 (1-{len(category_keys)}): ").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(category_keys):
                    selected_key = category_keys[idx]
                    selected_category = CONTENT_CATEGORIES[selected_key]
                    print(f"  ✓ 선택됨: {selected_category['label']}", flush=True)
                    
                    # 추천 모드 표시
                    recommended_modes = selected_category.get("recommended_modes", [])
                    if recommended_modes:
                        mode_labels = [NARRATIVE_MODES[mode]["label"] for mode in recommended_modes if mode in NARRATIVE_MODES]
                        if mode_labels:
                            print(f"  💡 추천 서사 모드: {', '.join(mode_labels)}", flush=True)
                    
                    return selected_key
            print(f"  ✗ 잘못된 입력입니다. 1부터 {len(category_keys)} 사이의 숫자를 입력하세요.", flush=True)
        except (KeyboardInterrupt, EOFError):
            # 기본값으로 research_paper 선택
            print(f"\n  ✓ 기본값 선택: {CONTENT_CATEGORIES['research_paper']['label']}", flush=True)
            return "research_paper"


def select_language():
    """
    사용자로부터 언어를 선택받습니다.
    
    Returns:
        선택된 언어 코드 (str) - "ko" 또는 "en"
    """
    print("\n📌 출력 오디오의 언어를 선택하세요.", flush=True)
    print("\nAvailable Languages:", flush=True)
    print("-" * 70, flush=True)
    print("  1. Korean (한국어) - 한국어 대본으로 생성", flush=True)
    print("  2. English (영어) - 영어 대본으로 생성 (더 큰 맥락 활용 가능)", flush=True)
    print("-" * 70, flush=True)
    print("  💡 팁: Enter 키를 누르면 기본값(한국어)이 선택됩니다.", flush=True)
    print("="*70, flush=True)
    
    while True:
        try:
            choice = input("\n👉 언어를 선택하세요 (1-2, 또는 Enter): ").strip()
            
            if not choice:
                print("  ✓ 기본값 선택: Korean (한국어)", flush=True)
                return "ko"
            
            if choice == "1":
                print("  ✓ 선택됨: Korean (한국어)", flush=True)
                return "ko"
            elif choice == "2":
                print("  ✓ 선택됨: English (영어)", flush=True)
                return "en"
            else:
                print("  ✗ 잘못된 입력입니다. 1 또는 2를 입력하세요.", flush=True)
        except (KeyboardInterrupt, EOFError):
            print("\n  ✓ 기본값 선택: Korean (한국어)", flush=True)
            return "ko"


def select_narrative_mode(category: str = None):
    """
    사용자로부터 서사 모드를 선택받습니다.
    
    Args:
        category: 선택된 콘텐츠 카테고리 (선택적, 추천 모드 표시용)
    """
    mode_keys = list(NARRATIVE_MODES.keys())
    default_index = mode_keys.index(DEFAULT_NARRATIVE_MODE) if DEFAULT_NARRATIVE_MODE in mode_keys else 0
    
    # 카테고리별 추천 모드 가져오기
    recommended_modes = []
    if category and category in CONTENT_CATEGORIES:
        recommended_modes = CONTENT_CATEGORIES[category].get("recommended_modes", [])
    
    print("\n📌 이야기의 톤과 스타일을 선택하세요.", flush=True)
    if recommended_modes:
        recommended_labels = [NARRATIVE_MODES[mode]["label"] for mode in recommended_modes if mode in NARRATIVE_MODES]
        if recommended_labels:
            print(f"  💡 추천 모드: {', '.join(recommended_labels)}", flush=True)
    print("\nAvailable Modes:", flush=True)
    print("-" * 70, flush=True)
    for idx, key in enumerate(mode_keys, 1):
        profile = NARRATIVE_MODES[key]
        mode_icon = "👨‍🏫" if key == "mentor" else "💕" if key == "lover" else "👥" if key == "friend" else "📻"
        is_recommended = "⭐" if key in recommended_modes else " "
        print(f"  {mode_icon} {is_recommended} {idx:>2}. {profile['label']}", flush=True)
        print(f"     └─ {profile['description']}", flush=True)
    print("-" * 70, flush=True)
    default_mode = NARRATIVE_MODES[mode_keys[default_index]]
    print(f"  💡 팁: Enter 키를 누르면 기본값({default_mode['label']})이 선택됩니다.", flush=True)
    print("="*70, flush=True)
    
    while True:
        try:
            choice = input(f"\n👉 서사 모드를 선택하세요 (1-{len(mode_keys)}, 또는 Enter): ").strip()
            if not choice:
                selected_key = mode_keys[default_index]
                print(f"  ✓ 기본값 선택: {NARRATIVE_MODES[selected_key]['label']}", flush=True)
                return selected_key
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(mode_keys):
                    selected_key = mode_keys[idx]
                    selected_profile = NARRATIVE_MODES[selected_key]
                    print(f"  ✓ 선택됨: {selected_profile['label']}", flush=True)
                    if selected_key == "radio_show":
                        print("  ℹ︎ 라디오쇼 모드는 다음 단계에서 두 개의 화자 음성을 선택합니다.", flush=True)
                    return selected_key
            print(f"  ✗ 잘못된 입력입니다. 1부터 {len(mode_keys)} 사이의 숫자를 입력하세요.", flush=True)
        except (KeyboardInterrupt, EOFError):
            selected_key = mode_keys[default_index]
            print(f"\n  ✓ 기본값 선택: {NARRATIVE_MODES[selected_key]['label']}", flush=True)
            return selected_key


def select_voice(language: str = "ko"):
    """
    사용자로부터 음성 그룹과 개별 음성을 선택받습니다.
    
    Args:
        language: 선택된 언어 코드 ("ko" 또는 "en")
    
    Returns:
        선택된 음성 프로필 (dict)
    """
    group_keys = list(VOICE_BANKS.keys())
    default_group_index = 0
    
    print("\n📌 음성 그룹을 선택하세요.", flush=True)
    print("\nAvailable Voice Groups:", flush=True)
    print("-" * 70, flush=True)
    for idx, key in enumerate(group_keys, 1):
        bank = VOICE_BANKS[key]
        desc = bank.get("description", "")
        gender_icon = "👩" if key == "female" else "👨"
        print(f"  {gender_icon} {idx:>2}. {bank['label']} - {desc}", flush=True)
    print("-" * 70, flush=True)
    print(f"  💡 팁: Enter 키를 누르면 기본값({VOICE_BANKS[group_keys[default_group_index]]['label']})이 선택됩니다.", flush=True)
    print("="*70, flush=True)
    
    # 그룹 선택
    while True:
        try:
            group_choice = input(f"\n👉 음성 그룹을 선택하세요 (1-{len(group_keys)}, 또는 Enter): ").strip()
            if not group_choice:
                selected_group = group_keys[default_group_index]
                print(f"  ✓ 기본값 선택: {VOICE_BANKS[selected_group]['label']}", flush=True)
                break
            if group_choice.isdigit():
                idx = int(group_choice) - 1
                if 0 <= idx < len(group_keys):
                    selected_group = group_keys[idx]
                    print(f"  ✓ 선택됨: {VOICE_BANKS[selected_group]['label']}", flush=True)
                    break
            print(f"  ✗ 잘못된 입력입니다. 1부터 {len(group_keys)} 사이의 숫자를 입력하세요.", flush=True)
        except (KeyboardInterrupt, EOFError):
            selected_group = group_keys[default_group_index]
            print(f"\n  ✓ 기본값 선택: {VOICE_BANKS[selected_group]['label']}", flush=True)
            break
    
    voice_bank = VOICE_BANKS[selected_group]
    voices = voice_bank["voices"]
    default_voice_name = voice_bank.get("default", voices[0]["name"])
    
    print("\n" + "="*70, flush=True)
    print(f"📌 {voice_bank['label']} 중에서 음성을 선택하세요.", flush=True)
    print("="*70, flush=True)
    print("\nAvailable Voices:", flush=True)
    print("-" * 70, flush=True)
    for idx, voice in enumerate(voices, 1):
        print(f"  {idx:>2}. {voice['display']}", flush=True)
    print("-" * 70, flush=True)
    default_display = next((v["display"] for v in voices if v["name"] == default_voice_name), voices[0]["display"])
    print(f"  💡 팁: Enter 키를 누르면 기본값({default_display})이 선택됩니다.", flush=True)
    print("="*70, flush=True)
    
    while True:
        try:
            choice = input(f"\n👉 음성을 선택하세요 (1-{len(voices)}, 또는 Enter): ").strip()
            if not choice:
                selected_voice = next((v for v in voices if v["name"] == default_voice_name), voices[0])
                print(f"  ✓ 기본값 선택: {selected_voice['display']}", flush=True)
                break
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(voices):
                    selected_voice = voices[idx]
                    print(f"  ✓ 선택됨: {selected_voice['display']}", flush=True)
                    break
            print(f"  ✗ 잘못된 입력입니다. 1부터 {len(voices)} 사이의 숫자를 입력하세요.", flush=True)
        except (EOFError, KeyboardInterrupt):
            selected_voice = next((v for v in voices if v["name"] == default_voice_name), voices[0])
            print(f"\n  ✓ 기본값 선택: {selected_voice['display']}", flush=True)
            break
    
    profile = {
        "name": selected_voice["name"],
        "display": selected_voice.get("display", selected_voice["name"]),
        "gender": selected_voice.get("gender", "FEMALE"),
        "group": selected_group,
    }
    print(f"  ✓ Selected voice: {profile['display']} ({voice_bank['label']})", flush=True)
    return profile


def select_radio_show_hosts(language: str = "ko"):
    """
    라디오쇼 모드용: 첫 번째 화자와 두 번째 화자의 음성을 각각 선택받습니다.
    성별 제한 없이 자유롭게 선택 가능합니다.
    
    Args:
        language: 선택된 언어 코드 ("ko" 또는 "en")
    
    Returns:
        (host1_profile, host2_profile) 튜플
    """
    group_keys = list(VOICE_BANKS.keys())
    
    def select_host_voice(host_number: int, host_label: str, default_group: str = None):
        """개별 화자 음성 선택 헬퍼 함수
        
        Args:
            host_number: 호스트 번호 (1 또는 2)
            host_label: 호스트 레이블
            default_group: 기본 그룹 키 (None이면 host_number에 따라 자동 설정)
        """
        # 기본 그룹 설정: host1은 female, host2는 male
        if default_group is None:
            default_group = "female" if host_number == 1 else "male"
        
        # 그룹 목록을 기본 그룹이 첫 번째가 되도록 재정렬
        display_groups = [default_group] + [k for k in group_keys if k != default_group]
        
        host_icon = "1️⃣" if host_number == 1 else "2️⃣"
        print(f"\n{host_icon} {host_label} 음성 선택", flush=True)
        print("=" * 70, flush=True)
        print("\n📌 음성 그룹을 선택하세요.", flush=True)
        print("\nAvailable Voice Groups:", flush=True)
        print("-" * 70, flush=True)
        for idx, key in enumerate(display_groups, 1):
            bank = VOICE_BANKS[key]
            desc = bank.get("description", "")
            gender_icon = "👩" if key == "female" else "👨"
            default_marker = " (기본값)" if key == default_group else ""
            print(f"  {gender_icon} {idx:>2}. {bank['label']} - {desc}{default_marker}", flush=True)
        print("-" * 70, flush=True)
        print(f"  💡 팁: Enter 키를 누르면 기본값({VOICE_BANKS[default_group]['label']})이 선택됩니다.", flush=True)
        print("=" * 70, flush=True)

        # 그룹 선택
        while True:
            try:
                group_choice = input(
                    f"\n👉 {host_label}의 음성 그룹을 선택하세요 (1-{len(display_groups)}, 또는 Enter): "
                ).strip()
                if not group_choice:
                    selected_group = default_group
                    print(f"  ✓ 기본값 선택: {VOICE_BANKS[selected_group]['label']}", flush=True)
                    break
                if group_choice.isdigit():
                    idx = int(group_choice) - 1
                    if 0 <= idx < len(display_groups):
                        selected_group = display_groups[idx]
                        print(f"  ✓ 선택됨: {VOICE_BANKS[selected_group]['label']}", flush=True)
                        break
                print(f"  ✗ 잘못된 입력입니다. 1부터 {len(display_groups)} 사이의 숫자를 입력하세요.", flush=True)
            except (KeyboardInterrupt, EOFError):
                selected_group = default_group
                print(f"\n  ✓ 기본값 선택: {VOICE_BANKS[selected_group]['label']}", flush=True)
                break

        voice_bank = VOICE_BANKS[selected_group]
        voices = voice_bank["voices"]
        default_voice_name = voice_bank.get("default", voices[0]["name"])

        print("\n" + "=" * 70, flush=True)
        print(f"📌 {voice_bank['label']} 중에서 {host_label}의 음성을 선택하세요.", flush=True)
        print("=" * 70, flush=True)
        print("\nAvailable Voices:", flush=True)
        print("-" * 70, flush=True)
        for idx, voice in enumerate(voices, 1):
            print(f"  {idx:>2}. {voice['display']}", flush=True)
        print("-" * 70, flush=True)
        default_display = next(
            (v["display"] for v in voices if v["name"] == default_voice_name),
            voices[0]["display"],
        )
        print(f"  💡 팁: Enter 키를 누르면 기본값({default_display})이 선택됩니다.", flush=True)
        print("=" * 70, flush=True)

        while True:
            try:
                choice = input(
                    f"\n👉 {host_label}의 음성을 선택하세요 (1-{len(voices)}, 또는 Enter): "
                ).strip()
                if not choice:
                    selected_voice = next(
                        (v for v in voices if v["name"] == default_voice_name),
                        voices[0],
                    )
                    print(f"  ✓ 기본값 선택: {selected_voice['display']}", flush=True)
                    break
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(voices):
                        selected_voice = voices[idx]
                        print(f"  ✓ 선택됨: {selected_voice['display']}", flush=True)
                        break
                print(f"  ✗ 잘못된 입력입니다. 1부터 {len(voices)} 사이의 숫자를 입력하세요.", flush=True)
            except (EOFError, KeyboardInterrupt):
                selected_voice = next(
                    (v for v in voices if v["name"] == default_voice_name),
                    voices[0],
                )
                print(f"\n  ✓ 기본값 선택: {selected_voice['display']}", flush=True)
                break

        profile = {
            "name": selected_voice["name"],
            "display": selected_voice.get("display", selected_voice["name"]),
            "gender": selected_voice.get("gender", "FEMALE"),
            "group": selected_group,
            "host_number": host_number,
        }
        print(
            f"  ✓ Selected {host_label} voice: {profile['display']} ({voice_bank['label']})",
            flush=True,
        )
        return profile
    
    # 첫 번째 화자 선택 (기본값: 여성)
    host1_profile = select_host_voice(1, "First Host (첫 번째 화자)", default_group="female")
    
    # 두 번째 화자 선택 (기본값: 남성)
    host2_profile = select_host_voice(2, "Second Host (두 번째 화자)", default_group="male")
    
    return (host1_profile, host2_profile)


def select_gemini_model():
    """
    사용자로부터 Gemini 모델을 선택받습니다.
    
    Returns:
        선택된 모델 이름 (str) - "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro"
    """
    models = [
        {
            "key": "gemini-2.5-flash-lite",
            "name": "Gemini 2.5 Flash Lite",
            "description": "기본 모델 (빠르고 효율적, 최적화된 성능)",
            "icon": "🚀"
        },
        {
            "key": "gemini-2.5-pro",
            "name": "Gemini 2.5 Pro",
            "description": "고품질 생성 (더 정확하고 상세한 출력, 느림)",
            "icon": "🎯"
        },
        {
            "key": "gemini-2.5-flash",
            "name": "Gemini 2.5 Flash",
            "description": "빠른 생성 (빠른 응답, 상대적으로 간결한 출력)",
            "icon": "⚡"
        }
    ]
    
    print("\n📌 Gemini 모델을 선택하세요.", flush=True)
    print("\nAvailable Models:", flush=True)
    print("-" * 70, flush=True)
    for idx, model in enumerate(models, 1):
        print(f"  {model['icon']} {idx:>2}. {model['name']}", flush=True)
        print(f"     └─ {model['description']}", flush=True)
    print("-" * 70, flush=True)
    print(f"  💡 팁: Enter 키를 누르면 기본값({models[0]['name']})이 선택됩니다.", flush=True)
    print("="*70, flush=True)
    
    while True:
        try:
            choice = input(f"\n👉 모델을 선택하세요 (1-{len(models)}, 또는 Enter): ").strip()
            if not choice:
                selected_model = models[0]
                print(f"  ✓ 기본값 선택: {selected_model['name']}", flush=True)
                return selected_model["key"]
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(models):
                    selected_model = models[idx]
                    print(f"  ✓ 선택됨: {selected_model['name']}", flush=True)
                    return selected_model["key"]
            print(f"  ✗ 잘못된 입력입니다. 1부터 {len(models)} 사이의 숫자를 입력하세요.", flush=True)
        except (KeyboardInterrupt, EOFError):
            selected_model = models[0]
            print(f"\n  ✓ 기본값 선택: {selected_model['name']}", flush=True)
            return selected_model["key"]
