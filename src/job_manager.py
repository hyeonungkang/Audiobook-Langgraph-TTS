"""
Job Manager for TTS Audiobook Converter
작업 큐 및 상태 관리
"""
import uuid
import threading
import time
from typing import Dict, Optional, Any
from pathlib import Path
from .graph import compile_graph
from .state import AgentState
from .utils.logging import log_error


class JobStatus:
    """작업 상태 클래스"""
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.status = "pending"  # pending, processing, completed, failed
        self.current_step = None  # showrunner, writer, tts, postprocess
        self.progress = {
            "showrunner": "pending",
            "writer": "pending",
            "tts": "pending",
            "postprocess": "pending"
        }
        self.segments_completed = 0
        self.segments_total = 0
        self.result = None
        self.error_message = None
        self.created_at = time.time()
        self.updated_at = time.time()
        
    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        data = {
            "job_id": self.job_id,
            "status": self.status,
            "current_step": self.current_step,
            "progress": self.progress,
            "segments_completed": self.segments_completed,
            "segments_total": self.segments_total,
        }
        if self.result:
            data["result"] = self.result
        if self.error_message:
            data["error_message"] = self.error_message
        return data


class JobManager:
    """작업 관리자 싱글톤"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self.jobs: Dict[str, JobStatus] = {}
        self.jobs_lock = threading.Lock()
        self._initialized = True
    
    def create_job(self, text: str, config: dict) -> str:
        """새 작업 생성"""
        job_id = str(uuid.uuid4())
        job_status = JobStatus(job_id)
        job_status.status = "processing"
        
        with self.jobs_lock:
            self.jobs[job_id] = job_status
        
        # 백그라운드 스레드에서 실행
        thread = threading.Thread(
            target=self._run_conversion,
            args=(job_id, text, config),
            daemon=True
        )
        thread.start()
        
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[dict]:
        """작업 상태 조회"""
        with self.jobs_lock:
            job = self.jobs.get(job_id)
            if job:
                return job.to_dict()
        return None
    
    def _update_job_status(
        self,
        job_id: str,
        status: Optional[str] = None,
        current_step: Optional[str] = None,
        progress_update: Optional[dict] = None,
        segments_completed: Optional[int] = None,
        segments_total: Optional[int] = None,
        result: Optional[dict] = None,
        error_message: Optional[str] = None
    ):
        """작업 상태 업데이트"""
        with self.jobs_lock:
            job = self.jobs.get(job_id)
            if not job:
                return
            
            if status:
                job.status = status
            if current_step:
                job.current_step = current_step
            if progress_update:
                job.progress.update(progress_update)
            if segments_completed is not None:
                job.segments_completed = segments_completed
            if segments_total is not None:
                job.segments_total = segments_total
            if result:
                job.result = result
            if error_message:
                job.error_message = error_message
            
            job.updated_at = time.time()
    
    def _run_conversion(self, job_id: str, text: str, config: dict):
        """변환 작업 실행 (백그라운드 스레드)"""
        try:
            # 초기 State 생성
            initial_state: AgentState = {
                "original_text": text,
                "config": config,
                "segments": [],
                "scripts": [],
                "audio_chunks": [],
                "audio_paths": [],
                "final_audio_path": None,
                "audio_title": None,
                "output_dir": None,
                "errors": []
            }
            
            # 그래프 컴파일
            app = compile_graph()
            
            # Showrunner 시작
            self._update_job_status(
                job_id,
                current_step="showrunner",
                progress_update={"showrunner": "in_progress"}
            )
            
            # 커스텀 실행으로 각 노드 완료 시 상태 업데이트
            final_state = self._run_graph_with_updates(app, initial_state, job_id)
            
            # 결과 처리
            if final_state.get("final_audio_path"):
                result = self._build_result(final_state)
                self._update_job_status(
                    job_id,
                    status="completed",
                    result=result
                )
            else:
                errors = final_state.get("errors", [])
                error_msg = "; ".join([e.get("error_message", "") for e in errors]) if errors else "Unknown error"
                self._update_job_status(
                    job_id,
                    status="failed",
                    error_message=error_msg
                )
        
        except Exception as e:
            log_error(f"Job {job_id} failed: {e}", context="job_manager")
            self._update_job_status(
                job_id,
                status="failed",
                error_message=str(e)
            )
    
    def _run_graph_with_updates(self, app, initial_state: AgentState, job_id: str) -> AgentState:
        """그래프를 실행하면서 중간 상태 업데이트 (Real-time Streaming)"""
        
        final_state = initial_state
        
        # app.stream을 사용하여 각 노드 실행 완료 시점 포착
        # LangGraph의 stream 모드는 각 단계의 출력을 yield합니다.
        for output in app.stream(initial_state):
            # output은 {node_name: state_update} 형태
            for node_name, state_update in output.items():
                print(f"Job {job_id} - Node completed: {node_name}")
                
                # 상태 병합 (간단한 버전)
                if isinstance(state_update, dict):
                    final_state.update(state_update)
                
                # 노드별 상태 업데이트 로직
                if node_name == "showrunner":
                    segments = state_update.get("segments", [])
                    self._update_job_status(
                        job_id,
                        current_step="writer",
                        progress_update={"showrunner": "completed", "writer": "in_progress"},
                        segments_total=len(segments)
                    )
                
                elif node_name == "writer":
                    scripts = state_update.get("scripts", [])
                    self._update_job_status(
                        job_id,
                        current_step="tts",
                        progress_update={"writer": "completed", "tts": "in_progress"},
                        segments_completed=len(scripts)
                    )
                
                elif node_name == "tts":
                    # TTS는 보통 여러 청크로 나뉘어 실행되지만, 
                    # 여기서는 tts 노드가 완료된 시점을 잡습니다.
                    self._update_job_status(
                        job_id,
                        current_step="postprocess",
                        progress_update={"tts": "completed", "postprocess": "in_progress"}
                    )
                
                elif node_name == "postprocess":
                    self._update_job_status(
                        job_id,
                        progress_update={"postprocess": "completed"}
                    )

        return final_state
    
    def _build_result(self, final_state: AgentState) -> dict:
        """최종 결과 빌드"""
        from .utils import parse_script_dialogues
        
        final_audio_path = final_state.get("final_audio_path")
        audio_title = final_state.get("audio_title", "output")
        output_dir = final_state.get("output_dir")
        segments = final_state.get("segments", [])
        scripts = final_state.get("scripts", [])
        errors = final_state.get("errors", [])
        config = final_state.get("config", {})
        
        # 오디오 파일 정보
        audio_duration = 0
        audio_size = 0
        if final_audio_path and Path(final_audio_path).exists():
            audio_size = Path(final_audio_path).stat().st_size
            # 오디오 길이는 pydub로 계산 (간단히 추정)
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_mp3(final_audio_path)
                audio_duration = len(audio) / 1000  # 초 단위
            except:
                audio_duration = 0
        
        # 전체 스크립트 결합
        full_script = "\n\n".join([
            f"=== Segment {s.get('segment_id', i+1)} ===\n{s.get('script', '')}"
            for i, s in enumerate(scripts)
        ])
        
        # 상세 스크립트 파싱 (화자 정보 포함)
        narrative_mode = config.get("narrative_mode", "mentor")
        voice_profile = config.get("voice_profile", {})
        
        detailed_scripts = []
        for script_obj in scripts:
            segment_id = script_obj.get("segment_id", 0)
            script_text = script_obj.get("script", "")
            
            dialogues = parse_script_dialogues(
                script_text,
                narrative_mode,
                voice_profile
            )
            
            detailed_scripts.append({
                "segment_id": segment_id,
                "dialogues": dialogues
            })
        
        # API URL 생성
        audio_filename = Path(final_audio_path).name if final_audio_path else ""
        audio_url = f"/api/v1/outputs/{audio_filename}" if audio_filename else ""
        
        return {
            "audio_url": audio_url,
            "audio_duration": int(audio_duration),
            "audio_size": audio_size,
            "audio_title": audio_title,
            "output_folder": str(output_dir) if output_dir else "",
            "full_script": full_script,
            "segments": segments,
            "detailed_scripts": detailed_scripts,
            "errors": [e.get("error_message", "") for e in errors]
        }


# 싱글톤 인스턴스
job_manager = JobManager()

