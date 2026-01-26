"""
Content category definitions
"""
CONTENT_CATEGORIES = {
    "research_paper": {
        "label": "논문/기술 문서 (Research Paper)",
        "description": "학술 논문, 기술 보고서, 연구 자료",
        "icon": "📄",
        "recommended_modes": ["mentor"],  # 멘토 모드 추천
    },
    "career": {
        "label": "커리어/자기계발 (Career & Self-Growth)",
        "description": "커리어 조언, 자기계발, 동기부여 콘텐츠",
        "icon": "💼",
        "recommended_modes": ["mentor", "friend"],  # 멘토, 친구 모드 추천
    },
    "language_learning": {
        "label": "어학 학습 (Language Learning)",
        "description": "영어 회화 팁, 표현 익히기, 쉐도잉",
        "icon": "🗣️",
        "recommended_modes": ["mentor", "friend"],  # 멘토, 친구 모드 추천
    },
    "philosophy": {
        "label": "인문학/에세이 (Philosophy & Essay)",
        "description": "인생 철학, 수필, 사색적인 글",
        "icon": "🤔",
        "recommended_modes": ["mentor", "friend", "lover"],  # 다양한 모드 추천
    },
    "tech_news": {
        "label": "기술 뉴스/트렌드 (Tech & Trends)",
        "description": "뉴스, 트렌드 리포트, 기술 동향",
        "icon": "📰",
        "recommended_modes": ["radio_show", "mentor"],  # 라디오쇼, 멘토 모드 추천
    },
}
