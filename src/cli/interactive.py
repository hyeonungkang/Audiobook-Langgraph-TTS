"""
Rich-based interactive CLI functions for user interaction
"""
from typing import Optional, Tuple, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import IntPrompt, Prompt, Confirm
from rich.text import Text
from rich import box
from ..models import DEFAULT_NARRATIVE_MODE, VOICE_BANKS, CONTENT_CATEGORIES
# NARRATIVE_MODES는 lazy import로 처리
NARRATIVE_MODES = None

console = Console()


def select_content_category() -> str:
    """
    사용자로부터 콘텐츠 카테고리를 선택받습니다 (Rich UI).
    
    Returns:
        선택된 카테고리 키 (str) - "research_paper", "career", "language_learning", "philosophy", "tech_news"
    """
    if not CONTENT_CATEGORIES:
        console.print("[red]✗ Error: CONTENT_CATEGORIES가 비어 있습니다.[/red]")
        raise ValueError("CONTENT_CATEGORIES가 비어 있습니다.")
    category_keys = list(CONTENT_CATEGORIES.keys())
    
    # Rich 테이블로 카테고리 표시
    table = Table(title="📌 어떤 종류의 텍스트인가요?", box=box.ROUNDED, show_header=True, header_style="bold magenta")
    table.add_column("번호", justify="center", style="cyan", width=6)
    table.add_column("카테고리", style="green", width=30)
    table.add_column("설명", style="yellow", width=40)
    
    for idx, key in enumerate(category_keys, 1):
        category = CONTENT_CATEGORIES[key]
        table.add_row(
            str(idx),
            f"{category['icon']} {category['label']}",
            category['description']
        )
    
    console.print()
    console.print(table)
    console.print()
    
    while True:
        try:
            choice = IntPrompt.ask(
                f"[cyan]👉[/cyan] 콘텐츠 카테고리를 선택하세요",
                default=1,
                show_default=True
            )
            
            if 1 <= choice <= len(category_keys):
                selected_key = category_keys[choice - 1]
                selected_category = CONTENT_CATEGORIES[selected_key]
                
                # 성공 메시지
                console.print(f"[green]✓[/green] 선택됨: [bold]{selected_category['label']}[/bold]")
                
                # 추천 모드 표시
                recommended_modes = selected_category.get("recommended_modes", [])
                if recommended_modes:
                    # NARRATIVE_MODES가 None이면 lazy load 시도
                    global NARRATIVE_MODES
                    if NARRATIVE_MODES is None:
                        try:
                            import sys
                            if "src.utils_module" in sys.modules:
                                utils_module = sys.modules["src.utils_module"]
                                NARRATIVE_MODES = utils_module.NARRATIVE_MODES
                        except Exception:
                            pass
                    
                    # NARRATIVE_MODES가 여전히 None이면 추천 모드 표시 건너뛰기
                    if NARRATIVE_MODES is not None:
                        try:
                            mode_labels = [NARRATIVE_MODES[mode]["label"] for mode in recommended_modes if mode in NARRATIVE_MODES]
                            if mode_labels:
                                console.print(f"[blue]💡[/blue] 추천 서사 모드: [yellow]{', '.join(mode_labels)}[/yellow]")
                        except Exception:
                            # 오류가 발생해도 계속 진행 (추천 모드 표시는 선택사항)
                            pass
                
                return selected_key
            else:
                console.print(f"[red]✗[/red] 잘못된 입력입니다. 1부터 {len(category_keys)} 사이의 숫자를 입력하세요.")
        except (KeyboardInterrupt, EOFError):
            # 기본값으로 research_paper 선택
            console.print(f"\n[green]✓[/green] 기본값 선택: [bold]{CONTENT_CATEGORIES['research_paper']['label']}[/bold]")
            return "research_paper"
        except Exception as e:
            console.print(f"[red]✗[/red] 오류가 발생했습니다: {e}")


def select_language() -> str:
    """
    사용자로부터 언어를 선택받습니다 (Rich UI).
    
    Returns:
        선택된 언어 코드 (str) - "ko" 또는 "en"
    """
    # Rich 테이블로 언어 옵션 표시
    table = Table(title="📌 출력 오디오의 언어를 선택하세요", box=box.ROUNDED, show_header=True, header_style="bold magenta")
    table.add_column("번호", justify="center", style="cyan", width=6)
    table.add_column("언어", style="green", width=20)
    table.add_column("설명", style="yellow", width=50)
    
    table.add_row("1", "Korean (한국어)", "한국어 대본으로 생성")
    table.add_row("2", "English (영어)", "영어 대본으로 생성 (더 큰 맥락 활용 가능)")
    
    console.print()
    console.print(table)
    console.print("[blue]💡[/blue] 팁: Enter 키를 누르면 기본값(한국어)이 선택됩니다.")
    console.print()
    
    while True:
        try:
            choice = IntPrompt.ask(
                "[cyan]👉[/cyan] 언어를 선택하세요",
                default=1,
                show_default=True
            )
            
            if choice == 1:
                console.print("[green]✓[/green] 선택됨: [bold]Korean (한국어)[/bold]")
                return "ko"
            elif choice == 2:
                console.print("[green]✓[/green] 선택됨: [bold]English (영어)[/bold]")
                return "en"
            else:
                console.print("[red]✗[/red] 잘못된 입력입니다. 1 또는 2를 입력하세요.")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[green]✓[/green] 기본값 선택: [bold]Korean (한국어)[/bold]")
            return "ko"
        except Exception as e:
            console.print(f"[red]✗[/red] 오류가 발생했습니다: {e}")


def select_narrative_mode(category: Optional[str] = None) -> str:
    """
    사용자로부터 서사 모드를 선택받습니다 (Rich UI).
    
    Args:
        category: 선택된 콘텐츠 카테고리 (선택적, 추천 모드 표시용)
    
    Returns:
        선택된 서사 모드 키 (str)
    """
    global NARRATIVE_MODES
    
    # NARRATIVE_MODES가 비어있을 수 있으므로, 직접 utils.py에서 로드
    # src.main.py에서 이미 utils.py를 로드했으므로, sys.modules에서 찾기
    try:
        import sys
        # src.main.py에서 로드한 utils_module 찾기
        if "src.utils_module" in sys.modules:
            utils_module = sys.modules["src.utils_module"]
            _actual_modes = utils_module.NARRATIVE_MODES
            # NARRATIVE_MODES 프록시를 실제 딕셔너리로 교체
            NARRATIVE_MODES = _actual_modes
        elif NARRATIVE_MODES is None or (hasattr(NARRATIVE_MODES, '__len__') and len(NARRATIVE_MODES) == 0):
            # utils.py를 직접 로드
            import importlib.util
            from pathlib import Path
            
            utils_py_path = Path(__file__).parent.parent / "utils.py"
            if utils_py_path.exists():
                # 이미 로드된 모듈들을 sys.modules에 등록
                if "src" not in sys.modules:
                    import types
                    sys.modules["src"] = types.ModuleType("src")
                if "src.config" not in sys.modules:
                    from .. import config
                    sys.modules["src.config"] = config
                if "src.core" not in sys.modules:
                    from .. import core
                    sys.modules["src.core"] = core
                if "src.models" not in sys.modules:
                    from .. import models
                    sys.modules["src.models"] = models
                if "src.utils" not in sys.modules:
                    import types
                    sys.modules["src.utils"] = types.ModuleType("src.utils")
                if "src.utils.logging" not in sys.modules:
                    from ..utils import logging
                    sys.modules["src.utils.logging"] = logging
                if "src.utils.timing" not in sys.modules:
                    from ..utils import timing
                    sys.modules["src.utils.timing"] = timing
                
                spec = importlib.util.spec_from_file_location("_temp_utils", utils_py_path)
                temp_utils = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(temp_utils)
                _actual_modes = temp_utils.NARRATIVE_MODES
                # NARRATIVE_MODES 프록시를 실제 딕셔너리로 교체
                NARRATIVE_MODES = _actual_modes
    except Exception as e:
        # 실패해도 계속 진행
        console.print(f"[yellow]⚠ Warning: NARRATIVE_MODES 로드 실패: {e}[/yellow]")
    
    mode_keys = list(NARRATIVE_MODES.keys()) if NARRATIVE_MODES else []
    if not mode_keys:
        console.print("[red]✗ Error: NARRATIVE_MODES가 비어 있습니다.[/red]")
        raise ValueError("NARRATIVE_MODES가 비어 있습니다.")
    default_index = mode_keys.index(DEFAULT_NARRATIVE_MODE) if DEFAULT_NARRATIVE_MODE in mode_keys else 0
    
    # 카테고리별 추천 모드 가져오기
    recommended_modes = []
    if category and CONTENT_CATEGORIES and category in CONTENT_CATEGORIES:
        recommended_modes = CONTENT_CATEGORIES[category].get("recommended_modes", [])
    
    # Rich 테이블로 서사 모드 표시
    table = Table(title="📌 이야기의 톤과 스타일을 선택하세요", box=box.ROUNDED, show_header=True, header_style="bold magenta")
    table.add_column("번호", justify="center", style="cyan", width=6)
    table.add_column("모드", style="green", width=25)
    table.add_column("설명", style="yellow", width=40)
    table.add_column("추천", justify="center", style="yellow", width=8)
    
    for idx, key in enumerate(mode_keys, 1):
        profile = NARRATIVE_MODES[key]
        mode_icon = "👨‍🏫" if key == "mentor" else "💕" if key == "lover" else "👥" if key == "friend" else "📻"
        is_recommended = "⭐" if key in recommended_modes else ""
        
        table.add_row(
            str(idx),
            f"{mode_icon} {profile['label']}",
            profile['description'],
            is_recommended
        )
    
    console.print()
    if recommended_modes:
        recommended_labels = [NARRATIVE_MODES[mode]["label"] for mode in recommended_modes if mode in NARRATIVE_MODES]
        if recommended_labels:
            console.print(f"[blue]💡[/blue] 추천 모드: [yellow]{', '.join(recommended_labels)}[/yellow]")
    console.print()
    console.print(table)
    
    default_mode = NARRATIVE_MODES[mode_keys[default_index]]
    console.print(f"[blue]💡[/blue] 팁: Enter 키를 누르면 기본값([bold]{default_mode['label']}[/bold])이 선택됩니다.")
    console.print()
    
    while True:
        try:
            choice = IntPrompt.ask(
                "[cyan]👉[/cyan] 서사 모드를 선택하세요",
                default=default_index + 1,
                show_default=True
            )
            
            if 1 <= choice <= len(mode_keys):
                selected_key = mode_keys[choice - 1]
                selected_profile = NARRATIVE_MODES[selected_key]
                console.print(f"[green]✓[/green] 선택됨: [bold]{selected_profile['label']}[/bold]")
                
                if selected_key == "radio_show":
                    console.print("[blue]ℹ︎[/blue] 라디오쇼 모드는 다음 단계에서 두 개의 화자 음성을 선택합니다.")
                
                return selected_key
            else:
                console.print(f"[red]✗[/red] 잘못된 입력입니다. 1부터 {len(mode_keys)} 사이의 숫자를 입력하세요.")
        except (KeyboardInterrupt, EOFError):
            selected_key = mode_keys[default_index]
            console.print(f"\n[green]✓[/green] 기본값 선택: [bold]{NARRATIVE_MODES[selected_key]['label']}[/bold]")
            return selected_key
        except Exception as e:
            console.print(f"[red]✗[/red] 오류가 발생했습니다: {e}")


def select_voice(language: str = "ko") -> Dict[str, Any]:
    """
    사용자로부터 음성 그룹과 개별 음성을 선택받습니다 (Rich UI).
    
    Args:
        language: 선택된 언어 코드 ("ko" 또는 "en")
    
    Returns:
        선택된 음성 프로필 (dict)
    """
    group_keys = list(VOICE_BANKS.keys())
    default_group_index = 0
    
    # 음성 그룹 선택 테이블
    table = Table(title="📌 음성 그룹을 선택하세요", box=box.ROUNDED, show_header=True, header_style="bold magenta")
    table.add_column("번호", justify="center", style="cyan", width=6)
    table.add_column("그룹", style="green", width=20)
    table.add_column("설명", style="yellow", width=45)
    
    for idx, key in enumerate(group_keys, 1):
        bank = VOICE_BANKS[key]
        desc = bank.get("description", "")
        gender_icon = "👩" if key == "female" else "👨"
        table.add_row(str(idx), f"{gender_icon} {bank['label']}", desc)
    
    console.print()
    console.print(table)
    console.print(f"[blue]💡[/blue] 팁: Enter 키를 누르면 기본값([bold]{VOICE_BANKS[group_keys[default_group_index]]['label']}[/bold])이 선택됩니다.")
    console.print()
    
    # 그룹 선택
    while True:
        try:
            group_choice = IntPrompt.ask(
                "[cyan]👉[/cyan] 음성 그룹을 선택하세요",
                default=default_group_index + 1,
                show_default=True
            )
            
            if 1 <= group_choice <= len(group_keys):
                selected_group = group_keys[group_choice - 1]
                console.print(f"[green]✓[/green] 선택됨: [bold]{VOICE_BANKS[selected_group]['label']}[/bold]")
                break
            else:
                console.print(f"[red]✗[/red] 잘못된 입력입니다. 1부터 {len(group_keys)} 사이의 숫자를 입력하세요.")
        except (KeyboardInterrupt, EOFError):
            selected_group = group_keys[default_group_index]
            console.print(f"\n[green]✓[/green] 기본값 선택: [bold]{VOICE_BANKS[selected_group]['label']}[/bold]")
            break
        except Exception as e:
            console.print(f"[red]✗[/red] 오류가 발생했습니다: {e}")
    
    voice_bank = VOICE_BANKS[selected_group]
    voices = voice_bank["voices"]
    default_voice_name = voice_bank.get("default", voices[0]["name"])
    
    # 개별 음성 선택 테이블
    console.print()
    voice_table = Table(
        title=f"📌 {voice_bank['label']} 중에서 음성을 선택하세요",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta"
    )
    voice_table.add_column("번호", justify="center", style="cyan", width=6)
    voice_table.add_column("음성 이름", style="green", width=25)
    
    for idx, voice in enumerate(voices, 1):
        is_default = " (기본값)" if voice["name"] == default_voice_name else ""
        voice_table.add_row(str(idx), f"{voice['display']}{is_default}")
    
    console.print(voice_table)
    default_display = next((v["display"] for v in voices if v["name"] == default_voice_name), voices[0]["display"])
    console.print(f"[blue]💡[/blue] 팁: Enter 키를 누르면 기본값([bold]{default_display}[/bold])이 선택됩니다.")
    console.print()
    
    # 기본값 인덱스 찾기
    default_voice_index = next((i for i, v in enumerate(voices) if v["name"] == default_voice_name), 0)
    
    while True:
        try:
            choice = IntPrompt.ask(
                "[cyan]👉[/cyan] 음성을 선택하세요",
                default=default_voice_index + 1,
                show_default=True
            )
            
            if 1 <= choice <= len(voices):
                selected_voice = voices[choice - 1]
                console.print(f"[green]✓[/green] 선택됨: [bold]{selected_voice['display']}[/bold]")
                break
            else:
                console.print(f"[red]✗[/red] 잘못된 입력입니다. 1부터 {len(voices)} 사이의 숫자를 입력하세요.")
        except (KeyboardInterrupt, EOFError):
            selected_voice = next((v for v in voices if v["name"] == default_voice_name), voices[0])
            console.print(f"\n[green]✓[/green] 기본값 선택: [bold]{selected_voice['display']}[/bold]")
            break
        except Exception as e:
            console.print(f"[red]✗[/red] 오류가 발생했습니다: {e}")
    
    profile = {
        "name": selected_voice["name"],
        "display": selected_voice.get("display", selected_voice["name"]),
        "gender": selected_voice.get("gender", "FEMALE"),
        "group": selected_group,
    }
    console.print(f"[green]✓[/green] Selected voice: [bold]{profile['display']}[/bold] ([cyan]{voice_bank['label']}[/cyan])")
    return profile


def select_radio_show_hosts(language: str = "ko") -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    라디오쇼 모드용: 첫 번째 화자와 두 번째 화자의 음성을 각각 선택받습니다 (Rich UI).
    성별 제한 없이 자유롭게 선택 가능합니다.
    
    Args:
        language: 선택된 언어 코드 ("ko" 또는 "en")
    
    Returns:
        (host1_profile, host2_profile) 튜플
    """
    group_keys = list(VOICE_BANKS.keys())
    
    def select_host_voice(host_number: int, host_label: str, default_group: Optional[str] = None) -> Dict[str, Any]:
        """개별 화자 음성 선택 헬퍼 함수"""
        # 기본 그룹 설정: host1은 female, host2는 male
        if default_group is None:
            default_group = "female" if host_number == 1 else "male"
        
        # 그룹 목록을 기본 그룹이 첫 번째가 되도록 재정렬
        display_groups = [default_group] + [k for k in group_keys if k != default_group]
        
        host_icon = "1️⃣" if host_number == 1 else "2️⃣"
        
        # 그룹 선택 테이블
        table = Table(
            title=f"{host_icon} {host_label} 음성 선택 - 음성 그룹",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )
        table.add_column("번호", justify="center", style="cyan", width=6)
        table.add_column("그룹", style="green", width=20)
        table.add_column("설명", style="yellow", width=45)
        
        for idx, key in enumerate(display_groups, 1):
            bank = VOICE_BANKS[key]
            desc = bank.get("description", "")
            gender_icon = "👩" if key == "female" else "👨"
            default_marker = " (기본값)" if key == default_group else ""
            table.add_row(str(idx), f"{gender_icon} {bank['label']}{default_marker}", desc)
        
        console.print()
        console.print(table)
        console.print(f"[blue]💡[/blue] 팁: Enter 키를 누르면 기본값([bold]{VOICE_BANKS[default_group]['label']}[/bold])이 선택됩니다.")
        console.print()
        
        # 그룹 선택
        default_group_index = 0  # 기본 그룹이 첫 번째
        while True:
            try:
                group_choice = IntPrompt.ask(
                    f"[cyan]👉[/cyan] {host_label}의 음성 그룹을 선택하세요",
                    default=default_group_index + 1,
                    show_default=True
                )
                
                if 1 <= group_choice <= len(display_groups):
                    selected_group = display_groups[group_choice - 1]
                    console.print(f"[green]✓[/green] 선택됨: [bold]{VOICE_BANKS[selected_group]['label']}[/bold]")
                    break
                else:
                    console.print(f"[red]✗[/red] 잘못된 입력입니다. 1부터 {len(display_groups)} 사이의 숫자를 입력하세요.")
            except (KeyboardInterrupt, EOFError):
                selected_group = default_group
                console.print(f"\n[green]✓[/green] 기본값 선택: [bold]{VOICE_BANKS[selected_group]['label']}[/bold]")
                break
            except Exception as e:
                console.print(f"[red]✗[/red] 오류가 발생했습니다: {e}")
        
        voice_bank = VOICE_BANKS[selected_group]
        voices = voice_bank["voices"]
        default_voice_name = voice_bank.get("default", voices[0]["name"])
        
        # 개별 음성 선택 테이블
        console.print()
        voice_table = Table(
            title=f"📌 {voice_bank['label']} 중에서 {host_label}의 음성을 선택하세요",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )
        voice_table.add_column("번호", justify="center", style="cyan", width=6)
        voice_table.add_column("음성 이름", style="green", width=25)
        
        default_voice_index = 0
        for idx, voice in enumerate(voices, 1):
            is_default = " (기본값)" if voice["name"] == default_voice_name else ""
            if voice["name"] == default_voice_name:
                default_voice_index = idx - 1
            voice_table.add_row(str(idx), f"{voice['display']}{is_default}")
        
        console.print(voice_table)
        default_display = next((v["display"] for v in voices if v["name"] == default_voice_name), voices[0]["display"])
        console.print(f"[blue]💡[/blue] 팁: Enter 키를 누르면 기본값([bold]{default_display}[/bold])이 선택됩니다.")
        console.print()
        
        while True:
            try:
                choice = IntPrompt.ask(
                    f"[cyan]👉[/cyan] {host_label}의 음성을 선택하세요",
                    default=default_voice_index + 1,
                    show_default=True
                )
                
                if 1 <= choice <= len(voices):
                    selected_voice = voices[choice - 1]
                    console.print(f"[green]✓[/green] 선택됨: [bold]{selected_voice['display']}[/bold]")
                    break
                else:
                    console.print(f"[red]✗[/red] 잘못된 입력입니다. 1부터 {len(voices)} 사이의 숫자를 입력하세요.")
            except (KeyboardInterrupt, EOFError):
                selected_voice = next((v for v in voices if v["name"] == default_voice_name), voices[0])
                console.print(f"\n[green]✓[/green] 기본값 선택: [bold]{selected_voice['display']}[/bold]")
                break
            except Exception as e:
                console.print(f"[red]✗[/red] 오류가 발생했습니다: {e}")
        
        profile = {
            "name": selected_voice["name"],
            "display": selected_voice.get("display", selected_voice["name"]),
            "gender": selected_voice.get("gender", "FEMALE"),
            "group": selected_group,
            "host_number": host_number,
        }
        console.print(f"[green]✓[/green] Selected {host_label} voice: [bold]{profile['display']}[/bold] ([cyan]{voice_bank['label']}[/cyan])")
        return profile
    
    # 첫 번째 화자 선택 (기본값: 여성)
    host1_profile = select_host_voice(1, "First Host (첫 번째 화자)", default_group="female")
    
    # 두 번째 화자 선택 (기본값: 남성)
    host2_profile = select_host_voice(2, "Second Host (두 번째 화자)", default_group="male")
    
    return (host1_profile, host2_profile)


def select_gemini_model() -> str:
    """
    사용자로부터 Gemini 모델을 선택받습니다 (Rich UI).
    
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
    
    # Rich 테이블로 모델 표시
    table = Table(title="📌 Gemini 모델을 선택하세요", box=box.ROUNDED, show_header=True, header_style="bold magenta")
    table.add_column("번호", justify="center", style="cyan", width=6)
    table.add_column("모델", style="green", width=30)
    table.add_column("설명", style="yellow", width=45)
    
    for idx, model in enumerate(models, 1):
        table.add_row(str(idx), f"{model['icon']} {model['name']}", model['description'])
    
    console.print()
    console.print(table)
    console.print(f"[blue]💡[/blue] 팁: Enter 키를 누르면 기본값([bold]{models[0]['name']}[/bold])이 선택됩니다.")
    console.print()
    
    while True:
        try:
            choice = IntPrompt.ask(
                "[cyan]👉[/cyan] 모델을 선택하세요",
                default=1,
                show_default=True
            )
            
            if 1 <= choice <= len(models):
                selected_model = models[choice - 1]
                console.print(f"[green]✓[/green] 선택됨: [bold]{selected_model['name']}[/bold]")
                return selected_model["key"]
            else:
                console.print(f"[red]✗[/red] 잘못된 입력입니다. 1부터 {len(models)} 사이의 숫자를 입력하세요.")
        except (KeyboardInterrupt, EOFError):
            selected_model = models[0]
            console.print(f"\n[green]✓[/green] 기본값 선택: [bold]{selected_model['name']}[/bold]")
            return selected_model["key"]
        except Exception as e:
            console.print(f"[red]✗[/red] 오류가 발생했습니다: {e}")
