"""
Typer-based CLI application entry point
"""
import typer
from rich.console import Console
from rich.panel import Panel
from typing import Optional

app = typer.Typer(
    name="audiobook",
    help="🎙️ LangGraph TTS - 오디오북 변환기",
    add_completion=False,
    rich_markup_mode="rich"
)
console = Console()


@app.command()
def convert(
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", "-i/-n", help="대화형 모드 사용 여부")
):
    """
    오디오북 변환을 시작합니다 (대화형 모드).
    """
    # 실제 변환 로직은 src/main.py의 main() 함수를 호출
    from ..main import main as run_conversion
    
    if interactive:
        console.print(Panel.fit(
            "[bold cyan]🎙️ LangGraph TTS - 오디오북 변환기[/bold cyan]",
            border_style="cyan"
        ))
        console.print()
    
    # 기존 main() 함수 실행
    run_conversion()


@app.command()
def list_voices():
    """
    사용 가능한 음성 목록을 표시합니다.
    """
    from ..utils import VOICE_BANKS
    
    console.print(Panel.fit(
        "[bold cyan]🎤 사용 가능한 음성 목록[/bold cyan]",
        border_style="cyan"
    ))
    console.print()
    
    from rich.table import Table
    from rich import box
    
    for group_key, bank in VOICE_BANKS.items():
        table = Table(
            title=f"{bank['label']} - {bank.get('description', '')}",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )
        table.add_column("번호", justify="center", style="cyan", width=6)
        table.add_column("음성 이름", style="green", width=25)
        table.add_column("기본값", justify="center", style="yellow", width=10)
        
        default_voice = bank.get("default", "")
        for idx, voice in enumerate(bank["voices"], 1):
            is_default = "✓" if voice["name"] == default_voice else ""
            table.add_row(str(idx), voice["display"], is_default)
        
        console.print(table)
        console.print()


@app.command()
def list_modes():
    """
    사용 가능한 서사 모드 목록을 표시합니다.
    """
    from ..utils import NARRATIVE_MODES
    
    console.print(Panel.fit(
        "[bold cyan]🎭 사용 가능한 서사 모드[/bold cyan]",
        border_style="cyan"
    ))
    console.print()
    
    from rich.table import Table
    from rich import box
    
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta"
    )
    table.add_column("모드 키", style="cyan", width=20)
    table.add_column("모드 이름", style="green", width=25)
    table.add_column("설명", style="yellow", width=50)
    
    for key, mode in NARRATIVE_MODES.items():
        mode_icon = "👨‍🏫" if key == "mentor" else "💕" if key == "lover" else "👥" if key == "friend" else "📻"
        table.add_row(key, f"{mode_icon} {mode['label']}", mode['description'])
    
    console.print(table)
    console.print()


@app.command()
def config(
    show: bool = typer.Option(False, "--show", "-s", help="현재 설정 표시"),
    set_key: Optional[str] = typer.Option(None, "--set", help="설정 키 설정 (예: --set GOOGLE_API_KEY=xxx)")
):
    """
    설정을 관리합니다.
    """
    if show:
        from ..config import CONFIG_PATH
        from pathlib import Path
        import json
        
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            console.print(Panel.fit(
                f"[bold cyan]현재 설정[/bold cyan]\n\n{json.dumps(config_data, indent=2, ensure_ascii=False)}",
                border_style="cyan"
            ))
        else:
            console.print("[yellow]⚠[/yellow] 설정 파일이 없습니다.")
    elif set_key:
        # 설정 키 설정 로직 (구현 필요)
        console.print(f"[yellow]⚠[/yellow] 설정 키 설정 기능은 아직 구현되지 않았습니다.")
    else:
        console.print("[yellow]ℹ[/yellow] 사용법: [cyan]audiobook config --show[/cyan] 또는 [cyan]audiobook config --set KEY=value[/cyan]")


if __name__ == "__main__":
    app()
