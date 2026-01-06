import { useState, useEffect, useCallback } from 'react';
import { api, ConvertConfig, JobStatus, Voice, Mode } from './api';

const CATEGORIES = [
  { id: 'research_paper', name: '논문/기술문서', emoji: '📄' },
  { id: 'career', name: '커리어/직업', emoji: '💼' },
  { id: 'language_learning', name: '어학/학습', emoji: '📚' },
  { id: 'philosophy', name: '철학', emoji: '🧠' },
  { id: 'tech_news', name: '기술 뉴스', emoji: '📰' },
];

const LANGUAGES = [
  { id: 'ko', name: '한국어' },
  { id: 'en', name: 'English' },
];

const DEFAULT_VOICES: Voice[] = [
  { id: 'Achernar', name: 'Achernar', gender: 'female' },
  { id: 'Aoede', name: 'Aoede', gender: 'female' },
  { id: 'Autonoe', name: 'Autonoe', gender: 'female' },
  { id: 'Callirrhoe', name: 'Callirrhoe', gender: 'female' },
  { id: 'Despina', name: 'Despina', gender: 'female' },
  { id: 'Erinome', name: 'Erinome', gender: 'female' },
  { id: 'Gacrux', name: 'Gacrux', gender: 'female' },
  { id: 'Kore', name: 'Kore', gender: 'female' },
  { id: 'Laomedeia', name: 'Laomedeia', gender: 'female' },
  { id: 'Leda', name: 'Leda', gender: 'female' },
  { id: 'Sulafat', name: 'Sulafat', gender: 'female' },
  { id: 'Vindemiatrix', name: 'Vindemiatrix', gender: 'female' },
  { id: 'Zephyr', name: 'Zephyr', gender: 'female' },
  { id: 'Achird', name: 'Achird', gender: 'male' },
  { id: 'Algenib', name: 'Algenib', gender: 'male' },
  { id: 'Algieba', name: 'Algieba', gender: 'male' },
  { id: 'Alnilam', name: 'Alnilam', gender: 'male' },
  { id: 'Charon', name: 'Charon', gender: 'male' },
  { id: 'Enceladus', name: 'Enceladus', gender: 'male' },
  { id: 'Fenrir', name: 'Fenrir', gender: 'male' },
  { id: 'Iapetus', name: 'Iapetus', gender: 'male' },
  { id: 'Orus', name: 'Orus', gender: 'male' },
  { id: 'Puck', name: 'Puck', gender: 'male' },
  { id: 'Pulcherrima', name: 'Pulcherrima', gender: 'male' },
  { id: 'Rasalgethi', name: 'Rasalgethi', gender: 'male' },
  { id: 'Sadachbia', name: 'Sadachbia', gender: 'male' },
  { id: 'Sadaltager', name: 'Sadaltager', gender: 'male' },
  { id: 'Schedar', name: 'Schedar', gender: 'male' },
  { id: 'Umbriel', name: 'Umbriel', gender: 'male' },
];

const DEFAULT_MODES: Mode[] = [
  { id: 'mentor', name: '멘토/코치', description: '따뜻하고 격려적인 톤으로 설명' },
  { id: 'lover', name: '이성친구', description: '부드럽고 친밀한 대화 스타일' },
  { id: 'friend', name: '친구', description: '편안하고 캐주얼한 대화' },
  { id: 'radio_show', name: '라디오쇼', description: '2인 진행자의 대화 형식' },
];

type Step = 'input' | 'processing' | 'complete';

export default function App() {
  const [step, setStep] = useState<Step>('input');
  const [text, setText] = useState('');
  const [config, setConfig] = useState<ConvertConfig>({
    language: 'ko',
    category: 'research_paper',
    narrative_mode: 'mentor',
    voice: 'Achernar',
    listener_name: '',
    use_flash_lite: false,
  });

  const [voices, setVoices] = useState<Voice[]>(DEFAULT_VOICES);
  const [modes, setModes] = useState<Mode[]>(DEFAULT_MODES);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [serverOnline, setServerOnline] = useState<boolean | null>(null);

  // 서버 상태 체크
  useEffect(() => {
    const checkServer = async () => {
      try {
        await api.healthCheck();
        setServerOnline(true);
        // 음성 및 모드 목록 가져오기
        try {
          const [voicesRes, modesRes] = await Promise.all([
            api.getVoices(),
            api.getModes(),
          ]);
          if (voicesRes.voices?.length) setVoices(voicesRes.voices);
          if (modesRes.modes?.length) setModes(modesRes.modes);
        } catch {
          // 기본값 사용
        }
      } catch {
        setServerOnline(false);
      }
    };
    checkServer();
    const interval = setInterval(checkServer, 30000);
    return () => clearInterval(interval);
  }, []);

  // 작업 상태 폴링
  useEffect(() => {
    if (!jobId || step !== 'processing') return;

    const pollStatus = async () => {
      try {
        const status = await api.getJobStatus(jobId);
        setJobStatus(status);

        if (status.status === 'completed') {
          setStep('complete');
        } else if (status.status === 'failed') {
          setError(status.error || '변환에 실패했습니다.');
          setStep('input');
        }
      } catch (e) {
        console.error('Status poll failed:', e);
      }
    };

    pollStatus();
    const interval = setInterval(pollStatus, 2000);
    return () => clearInterval(interval);
  }, [jobId, step]);

  const handleSubmit = async () => {
    if (!text.trim()) {
      setError('텍스트를 입력해주세요.');
      return;
    }

    setError(null);
    setStep('processing');

    try {
      const result = await api.startConvert({ text, config });
      setJobId(result.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : '변환 시작에 실패했습니다.');
      setStep('input');
    }
  };

  const handleReset = useCallback(() => {
    setStep('input');
    setText('');
    setJobId(null);
    setJobStatus(null);
    setError(null);
  }, []);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      setText(event.target?.result as string || '');
    };
    reader.readAsText(file);
  };

  const femaleVoices = voices.filter(v => v.gender === 'female');
  const maleVoices = voices.filter(v => v.gender === 'male');

  return (
    <div className="app">
      <header className="header">
        <h1>Audiobook TTS Generator</h1>
        <p className="subtitle">AI 기반 오디오북 생성기</p>
        <div className={`server-status ${serverOnline ? 'online' : 'offline'}`}>
          {serverOnline === null ? '서버 확인 중...' : serverOnline ? '서버 연결됨' : '서버 오프라인'}
        </div>
      </header>

      <main className="main">
        {error && (
          <div className="error-banner">
            {error}
            <button onClick={() => setError(null)}>×</button>
          </div>
        )}

        {step === 'input' && (
          <div className="input-step">
            <section className="section">
              <h2>1. 텍스트 입력</h2>
              <div className="text-input-area">
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="오디오북으로 변환할 텍스트를 입력하세요...&#10;&#10;논문, 기술 문서, 기사 등 어떤 텍스트든 가능합니다."
                  rows={10}
                />
                <div className="file-upload">
                  <label>
                    <span>또는 파일 업로드</span>
                    <input type="file" accept=".txt,.md" onChange={handleFileUpload} />
                  </label>
                </div>
                <div className="char-count">
                  {text.length.toLocaleString()} 자
                </div>
              </div>
            </section>

            <section className="section">
              <h2>2. 설정</h2>
              <div className="config-grid">
                <div className="config-item">
                  <label>언어</label>
                  <div className="radio-group">
                    {LANGUAGES.map(lang => (
                      <label key={lang.id} className="radio-label">
                        <input
                          type="radio"
                          name="language"
                          value={lang.id}
                          checked={config.language === lang.id}
                          onChange={(e) => setConfig({ ...config, language: e.target.value })}
                        />
                        <span>{lang.name}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <div className="config-item">
                  <label>카테고리</label>
                  <select
                    value={config.category}
                    onChange={(e) => setConfig({ ...config, category: e.target.value })}
                  >
                    {CATEGORIES.map(cat => (
                      <option key={cat.id} value={cat.id}>
                        {cat.emoji} {cat.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="config-item">
                  <label>서사 모드</label>
                  <select
                    value={config.narrative_mode}
                    onChange={(e) => setConfig({ ...config, narrative_mode: e.target.value })}
                  >
                    {modes.map(mode => (
                      <option key={mode.id} value={mode.id}>
                        {mode.name} - {mode.description}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="config-item">
                  <label>음성 선택</label>
                  <select
                    value={config.voice}
                    onChange={(e) => setConfig({ ...config, voice: e.target.value })}
                  >
                    <optgroup label="여성 음성">
                      {femaleVoices.map(voice => (
                        <option key={voice.id} value={voice.id}>{voice.name}</option>
                      ))}
                    </optgroup>
                    <optgroup label="남성 음성">
                      {maleVoices.map(voice => (
                        <option key={voice.id} value={voice.id}>{voice.name}</option>
                      ))}
                    </optgroup>
                  </select>
                </div>

                <div className="config-item">
                  <label>청자 이름 (선택)</label>
                  <input
                    type="text"
                    value={config.listener_name}
                    onChange={(e) => setConfig({ ...config, listener_name: e.target.value })}
                    placeholder="예: 현웅"
                  />
                </div>

                <div className="config-item">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={config.use_flash_lite || false}
                      onChange={(e) => setConfig({ ...config, use_flash_lite: e.target.checked })}
                    />
                    <span>Flash Lite 모드 (빠른 처리)</span>
                  </label>
                </div>
              </div>
            </section>

            <button
              className="submit-btn"
              onClick={handleSubmit}
              disabled={!text.trim() || !serverOnline}
            >
              오디오북 생성 시작
            </button>
          </div>
        )}

        {step === 'processing' && (
          <div className="processing-step">
            <div className="spinner"></div>
            <h2>오디오북 생성 중...</h2>
            {jobStatus && (
              <div className="status-info">
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{ width: `${jobStatus.progress || 0}%` }}
                  ></div>
                </div>
                <p className="current-step">{jobStatus.current_step || '처리 중...'}</p>
                <p className="progress-text">{jobStatus.progress || 0}% 완료</p>
              </div>
            )}
            <p className="processing-note">
              텍스트 분석, 스크립트 생성, 음성 합성 과정을 거칩니다.<br/>
              텍스트 길이에 따라 몇 분에서 수십 분이 소요될 수 있습니다.
            </p>
          </div>
        )}

        {step === 'complete' && jobStatus?.result && (
          <div className="complete-step">
            <div className="success-icon">✓</div>
            <h2>오디오북 생성 완료!</h2>

            {jobStatus.result.audio_title && (
              <p className="audio-title">{jobStatus.result.audio_title}</p>
            )}

            {jobStatus.result.download_url && (
              <a
                href={jobStatus.result.download_url}
                className="download-btn"
                download
              >
                오디오 파일 다운로드
              </a>
            )}

            <button className="reset-btn" onClick={handleReset}>
              새로운 오디오북 생성
            </button>
          </div>
        )}
      </main>

      <footer className="footer">
        <p>Powered by LangGraph + Gemini TTS</p>
      </footer>
    </div>
  );
}
