<div align="center">

# 🎙️ LangGraph TTS - 오디오북 변환기

**AI 논문이나 긴 텍스트를 자연스러운 한국어/영어 팟캐스트로 변환하는 CLI 도구**

[![LangGraph TTS](https://img.shields.io/badge/LangGraph%20TTS-Audiobook%20Converter-9333EA?style=for-the-badge&logo=python&logoColor=white)](https://github.com/YOUR_USERNAME/langraph_tts)
[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.0+-orange.svg)](https://langchain-ai.github.io/langgraph/)

*Gemini API를 사용해 텍스트를 분석하고, 다양한 서사 모드로 오디오북을 생성합니다*

[설치](#-설치-방법) • [사용법](#️-사용-방법-cli) • [API 키 설정](#-api-키-설정) • [문제 해결](#-문제-해결)

</div>

---

## ✨ 주요 특징

<div align="center">

| 🎯 기능 | 📝 설명 |
|---------|--------|
| 🤖 **AI Agent 기반** | 논문을 15개 세그먼트로 자동 분해 및 기획 |
| 🎭 **4가지 서사 모드** | 멘토/코치, 이성친구, 친구, 라디오쇼 모드 |
| � **M4B 오디오북** | 챕터 마커, 메타데이터, 커버 아트 완벽 지원 |
| 🎨 **Generative Art** | 콘텐츠에 어울리는 커버 아트 자동 생성 (Voronoi) |
| �🌐 **다국어 지원** | 한국어/영어 스크립트 자동 생성 |
| 👤 **개인화** | 청자 이름 개인화 (기본값: "용사") |
| ⚡ **병렬 처리** | 15개 세그먼트 동시 생성으로 빠른 처리 |
| 🎵 **고품질 음성** | Gemini 2.5 Pro TTS (여성 13개, 남성 16개 음성) |
| 💰 **비용 최적화** | 토큰 소모 60-80% 감소, TTS API 호출 최소화 |
| 📄 **유연한 입력** | `input.txt`에 아무 텍스트나 넣어도 자동 처리 |

</div>


---

## 📅 2026.01.05 최신 업데이트 (v2.2)

**TTS 청킹 최적화 및 API 소모 최소화 업데이트입니다!**

### 1️⃣ TTS 청킹 최적화 ⚡
- **전체 텍스트 통합 청킹**: 모든 스크립트를 합쳐서 한 번에 청킹하여 TTS API 호출 횟수를 최소화
- **API 제한 준수**: Cloud Text-to-Speech API 제한(4000 bytes)에 정확히 맞춰 청킹 로직 개선
- **효율적인 청크 분할**: 문장 단위로 자연스럽게 분할하여 최적의 청크 크기 유지

### 2️⃣ 코드 품질 개선 🔧
- **중복 코드 제거**: 구버전 TTS 함수 제거 및 REST API 버전 통합
- **린트 오류 해결**: 모든 코드 린트 오류 수정 완료

---

## 📅 2026.01.04 업데이트 (v2.1)

**TTS 성능 최적화 및 오디오 품질 개선 업데이트입니다!**

### 1️⃣ TTS 병렬 처리 최적화 ⚡
- **전체 청크 동시 전송**: 15개 청크를 슬라이딩 윈도우 없이 모든 요청을 한 번에 병렬 전송하여 처리 속도 대폭 향상
- **ThreadPoolExecutor 최적화**: API 제한을 고려하여 `max_workers`를 10개로 설정
- **처리 시간 단축**: Rate limit 대기 없이 모든 요청을 즉시 제출하여 전체 변환 시간 단축

### 2️⃣ 임시 파일 자동 정리 🗑️
- **자동 정리 기능**: 변환이 성공적으로 완료되면 `temp_output` 디렉토리의 임시 파일들이 자동으로 삭제됩니다
- **세션별 정리**: 해당 세션의 파일들만 정확하게 식별하여 삭제 (다른 세션 파일 보호)
- **디스크 공간 절약**: 더 이상 수동으로 temp 파일을 정리할 필요가 없습니다

### 3️⃣ 오디오 품질 향상 🎵
- **향상된 노이즈 제거**: 더 공격적인 노이즈 제거 설정 (prop_decrease=0.95, stationary=True)

---

## 📅 2026.01.04 대규모 업데이트 (v2.0)

**오디오북 품질과 안정성을 획기적으로 개선한 메이저 업데이트입니다!**

### 1️⃣ 메타데이터터
- **풍부한 메타데이터**: 제목, 아티스트, 앨범명, 장르, 연도 등 ID3 태그가 완벽하게 내장됩니다.
- **FFmpeg 엔진 도입**: 기존의 불안정한 라이브러리를 제거하고, 산업 표준인 **FFmpeg**를 도입하여 인코딩 속도와 안정성을 대폭 강화했습니다.

### 2️⃣ Generative Art 커버 자동 생성 🎨
- **"이미지가 없어도 괜찮습니다"**: 커버 이미지를 따로 준비하지 않아도, 수학적 알고리즘(Voronoi Diagram)이 **매번 세상에 하나뿐인 기하학적 커버 아트**를 생성합니다.
- **세련된 디자인**: 전문가가 큐레이션한 컬러 팔레트를 무작위로 조합하여, 소장하고 싶은 앨범 아트를 만들어줍니다.

### 3️⃣ 라디오쇼 모드 엔진 리팩토링 📻
- **멀티 스피커 아키텍처**: `Radio Show` 모드의 핵심 로직을 완전히 재설계했습니다. 이제 **Host 1**과 **Host 2**가 프롬프트 누수 없이 완벽하게 분리된 목소리로 대화를 나눕니다.
- **스마트 쿼터 관리**: Google Cloud TTS의 API 제한(RPM)을 자동으로 감지하고 조절하는 **Rate Limiter**와 **재시도(Retry)** 로직을 탑재하여, 대량 변환 중에도 멈추지 않습니다.

---

## 📋 필요한 API 키

### 1️⃣ Google Gemini API 키 (필수)

**📌 발급 방법:**

1. [Google AI Studio](https://aistudio.google.com/app/apikey) 접속
2. Google 계정으로 로그인
3. **"Create API Key"** 버튼 클릭
4. API 키가 생성되면 복사 (예: `AIzaSy...` 형식, 약 39자)
5. 안전한 곳에 저장

**🔧 용도**: 
- 텍스트 분석 및 스크립트 생성 (Showrunner, Writer Agent)
- TTS 음성 합성

**⚠️ 보안 주의**: 
- API 키는 절대 공개하지 마세요
- GitHub에 커밋하지 마세요 (`.gitignore`에 포함됨)
- 유출 시 즉시 재발급하세요

### 2️⃣ Google Cloud 서비스 계정 키 (TTS용, 선택사항)

**📌 발급 방법:**

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 프로젝트 생성 또는 선택
3. **API 및 서비스** > **라이브러리** 메뉴로 이동
4. **"Text-to-Speech API"** 검색 후 **활성화** 클릭
5. **IAM 및 관리자** > **서비스 계정** 메뉴로 이동
6. **서비스 계정 만들기** 클릭
7. 서비스 계정 이름 입력 (예: "tts-service") 후 **만들기**
8. **역할** 선택: **"Text-to-Speech API 사용자"** 또는 **"Editor"**
9. **완료** 클릭
10. 생성된 서비스 계정 클릭 > **키** 탭 이동
11. **키 추가** > **JSON 만들기** 클릭
12. 다운로드된 JSON 파일을 안전한 위치에 저장

**🔧 용도**: 음성 합성 (TTS)

**⚠️ 보안 주의**: 
- 서비스 계정 키 파일(JSON)은 절대 GitHub에 커밋하지 마세요
- `.gitignore`에 이미 포함되어 있습니다
- 유출 시 즉시 키를 삭제하고 재생성하세요

---

## 🚀 설치 방법

### 1️⃣ 저장소 클론

```bash
git clone <repository-url>
cd langraph_tts
```

### 2️⃣ 가상환경 생성 및 활성화

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
# 가상환경 생성
py -3 -m venv .venv

# 가상환경 활성화
.\.venv\Scripts\Activate.ps1
```

</details>

<details>
<summary><b>Windows (CMD)</b></summary>

```cmd
# 가상환경 생성
py -3 -m venv .venv

# 가상환경 활성화
.venv\Scripts\activate.bat
```

</details>

<details>
<summary><b>Linux/Mac</b></summary>

```bash
# 가상환경 생성
python3 -m venv .venv

# 가상환경 활성화
source .venv/bin/activate
```

</details>

**✅ 활성화 확인**: 프롬프트 앞에 `(.venv)`가 표시되면 성공입니다.

### 3️⃣ 패키지 설치

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4️⃣ 설치 확인

```bash
python -c "import langgraph; print('✅ LangGraph OK')"
python -c "import google.generativeai; print('✅ Google GenerativeAI OK')"
```

---

## 🖥️ 사용 방법 (CLI)

### 1️⃣ API 키 설정

#### 방법 1: .env 파일 사용 (권장, 표준 방식) ⭐

프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 다음 내용을 입력하세요:

```bash
GOOGLE_API_KEY=your-api-key-here
GOOGLE_APPLICATION_CREDENTIALS=C:/path/to/service-account-key.json
```

**⚠️ 중요**: 
- `.env` 파일에는 **주석을 넣지 마세요** (한국어 주석은 인코딩 문제를 일으킬 수 있습니다)
- 값만 입력하세요: `KEY=value` 형식으로만 작성

**📝 파일 생성 방법:**

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
# PowerShell에서
New-Item -Path .env -ItemType File
# 그 다음 텍스트 에디터로 열어서 위 내용 입력
```

</details>

<details>
<summary><b>Linux/Mac</b></summary>

```bash
# .env 파일 생성
cat > .env << EOF
GOOGLE_API_KEY=your-api-key-here
EOF

# 또는 텍스트 에디터로 직접 생성
nano .env
```

</details>

**🔒 보안**: 
- `.env` 파일은 `.gitignore`에 포함되어 있어 GitHub에 올라가지 않습니다
- 실제 API 키를 입력한 `.env` 파일은 절대 공개하지 마세요

#### 방법 2: 환경 변수로 설정

```bash
# Windows (PowerShell)
$env:GOOGLE_API_KEY="your-api-key-here"

# Windows (CMD)
set GOOGLE_API_KEY=your-api-key-here

# Linux/Mac
export GOOGLE_API_KEY="your-api-key-here"
```

#### 방법 3: 대화형 입력

프로그램을 처음 실행하면 API 키를 입력하라는 프롬프트가 나타납니다:

```
🔑 API Key Initialization
======================================================================
✗ No API key found in any configuration
💡 Starting interactive API key setup...

🔐 Google Gemini API Key를 입력하세요: [여기에 API 키 입력]
```

입력한 API 키는 `.env` 파일에 자동 저장됩니다.

**📊 우선순위:**
1. `.env` 파일 (프로젝트 루트) ⭐
2. 시스템 환경 변수
3. config.json (백업용, 하위 호환성)
4. 대화형 입력

### 2️⃣ input.txt 파일 준비

프로젝트 루트 디렉토리에 `input.txt` 파일을 생성하고 변환할 텍스트를 넣습니다:

```
예시:
- AI 논문 (PDF에서 복사한 텍스트)
- 기술 문서
- 뉴스 기사
- 블로그 포스트
- 등등...
```

### 3️⃣ 프로그램 실행

```bash
python main.py
```

**💡 참고**: 가상환경이 활성화되지 않아도 `main.py`가 자동으로 가상환경을 감지하고 사용합니다.

### 4️⃣ 설정 단계

프로그램 실행 후 다음 단계를 진행합니다:

#### 1️⃣ Gemini 모델 선택
- **Pro**: 고품질 생성 (권장, Showrunner에 사용)
- **Flash**: 빠른 생성 (Writer에 사용)

#### 2️⃣ 콘텐츠 카테고리 선택
- 논문/기술 문서 (research_paper)
- 커리어 (career)
- 어학 (language_learning)
- 철학 (philosophy)
- 뉴스 (tech_news)

#### 3️⃣ 언어 선택
- 한국어 (ko)
- 영어 (en)

#### 4️⃣ 서사 모드 선택

<details>
<summary><b>멘토/코치 모드 (mentor) 🎓</b></summary>

- 따뜻하고 격려적인 톤
- 경험 공유, 실용적 조언
- 학습 콘텐츠에 적합

</details>

<details>
<summary><b>이성친구 모드 (lover) 💕</b></summary>

- 부드럽고 열정적인 톤
- 똑똑한 박사과정 여자친구처럼 대사 생성
- 연구 목적에도 적합

</details>

<details>
<summary><b>친구 모드 (friend) 👥</b></summary>

- 편안하고 장난스러운 톤
- 절친과의 대화 형식

</details>

<details>
<summary><b>라디오쇼 모드 (radio_show) 📻</b></summary>

- 2인 대화 형식
- 첫 번째 화자와 두 번째 화자의 음성을 각각 선택 (성별 제한 없음)

</details>

#### 5️⃣ 음성 선택

**여성 음성 (13개):**
- Achernar (기본값), Aoede, Autonoe, Callirrhoe, Despina, Erinome, Gacrux, Kore, Laomedeia, Leda, Sulafat, Vindemiatrix, Zephyr

**남성 음성 (16개):**
- Achird (기본값), Algenib, Algieba, Alnilam, Charon, Enceladus, Fenrir, Iapetus, Orus, Puck, Pulcherrima, Rasalgethi, Sadachbia, Sadaltager, Schedar, Umbriel, Zubenelgenubi

#### 6️⃣ 청취자 이름 입력
- 기본값: **용사**
- Enter 키를 누르면 기본값 사용
- 한국어 대본에서는 자동으로 적절한 조사(은/는, 이/가)가 붙습니다

### 5️⃣ 결과 확인

처리가 완료되면 다음 위치에 결과가 저장됩니다:

```
outputs/{오디오제목}_{모드}_{음성}_{언어코드}/
├── {오디오제목}_{모드}_{음성}_{언어코드}.mp3  # 최종 오디오 파일
├── refined_text.txt                          # 생성된 스크립트
├── audio_title.txt                           # 오디오 제목
├── showrunner_segments.json                  # 15개 세그먼트 기획안
└── input.txt                                 # 원본 입력 파일 복사본
```

**📁 추가 저장 위치:**
- `C:/audiiobook/{오디오제목}_{모드}_{음성}_{언어코드}/` (동일한 파일)

---

## 🏗️ 작동 원리

<div align="center">

```mermaid
graph TD
    A[input.txt] --> B[Showrunner Agent]
    B --> C[15개 세그먼트 기획]
    C --> D[Writer Agent 병렬 처리]
    D --> E[스크립트 생성]
    E --> F[TTS 음성 합성]
    F --> G[오디오 파일 저장]
```

</div>

### 1단계: Showrunner Agent (기획자) 🎬
- 원본 텍스트를 분석하여 15개 세그먼트로 분해
- 각 세그먼트의 제목, 핵심 내용, 경계 문장 생성
- Reasoning 절차를 거쳐 고품질 세그먼트 생성

### 2단계: Writer Agent (작가) - 병렬 처리 ✍️
- 각 세그먼트를 선택한 언어 및 서사 모드에 맞게 작성
- 원본 텍스트의 관련 섹션만 참고하여 효율적 처리
- 15개 세그먼트를 동시에 병렬 처리

### 3단계: TTS (Text-to-Speech) 🎵
- Gemini 2.5 Pro TTS로 음성 합성
- 선택한 음성으로 자연스러운 오디오 생성

### 4단계: 오디오 후처리 🎚️
- 오디오 파일을 최종 위치로 저장
- `outputs/` 및 `C:/audiiobook/`에 저장

---

## 🔧 문제 해결

<details>
<summary><b>가상환경이 자동으로 활성화되지 않는 경우</b></summary>

프로그램이 자동으로 가상환경을 감지하지만, 수동으로 활성화하려면:

**Windows:**
```powershell
.\.venv\Scripts\Activate.ps1
python main.py
```

**Linux/Mac:**
```bash
source .venv/bin/activate
python main.py
```

</details>

<details>
<summary><b>API 키 오류</b></summary>

- `.env` 파일을 확인하세요
- API 키가 유효한지 확인하세요
- [Google AI Studio](https://aistudio.google.com/app/apikey)에서 키를 재발급하세요

</details>

<details>
<summary><b>패키지 설치 오류</b></summary>

```bash
# pip 업그레이드
python -m pip install --upgrade pip

# 패키지 재설치
pip install -r requirements.txt --force-reinstall
```

</details>

<details>
<summary><b>Showrunner 세그먼트 생성 실패</b></summary>

- 프로그램이 자동으로 최대 3회 재시도합니다
- 실패 시 `temp_output/showrunner_error_*.txt` 파일을 확인하세요
- `input.txt` 파일이 비어있지 않은지 확인하세요

</details>

---

## 📁 프로젝트 구조

```
langraph_tts/
├── main.py                 # 진입점 (가상환경 자동 감지)
├── src/
│   ├── main.py            # 메인 로직
│   ├── cli.py              # CLI 인터페이스
│   ├── config.py           # 설정 관리 (.env 파일 지원)
│   ├── graph.py            # LangGraph 워크플로우
│   ├── nodes/              # Agent 노드들
│   │   ├── showrunner.py   # Showrunner Agent
│   │   ├── writer.py       # Writer Agent
│   │   ├── tts.py          # TTS 생성
│   │   └── audio_postprocess.py  # 오디오 후처리
│   └── utils.py            # 유틸리티 함수
├── input.txt               # 입력 텍스트 파일
├── requirements.txt        # Python 패키지 목록
├── .gitignore             # Git 무시 파일
├── LICENSE                # MIT 라이선스
└── README.md              # 이 파일
```

---

## ⚙️ 설정 파일

### .env 파일 (표준 방식, 권장) ⭐

프로젝트 루트 디렉토리에 `.env` 파일을 생성하여 API 키를 관리합니다:

```bash
GOOGLE_API_KEY=your-api-key-here
GOOGLE_APPLICATION_CREDENTIALS=C:/path/to/service-account-key.json
```

**📝 참고:**
- `.env.example` 파일을 참고하여 `.env` 파일을 생성하세요
- `.env.example`은 Git에 포함되지만, 실제 API 키가 들어간 `.env` 파일은 `.gitignore`에 의해 제외됩니다

**📍 위치:**
- 프로젝트 루트 디렉토리: `langraph_tts/.env`

### config.json (백업용, 하위 호환성)

기존 `config.json` 파일도 지원하지만, 새로운 설정은 `.env` 파일 사용을 권장합니다.

**📍 위치:**
- 개발 모드: 프로젝트 루트/`config.json`
- 프로덕션: 사용자 데이터 폴더/`config.json`

---

## 📚 기술 스택

<div align="center">

| 카테고리 | 기술 |
|---------|------|
| **언어** | Python 3.9+ |
| **AI 프레임워크** | LangGraph |
| **LLM** | Google Gemini 2.5 Pro/Flash |
| **TTS** | Google Cloud Text-to-Speech |
| **환경 관리** | python-dotenv |

</div>

---

## 📄 라이선스

이 프로젝트는 [MIT License](LICENSE) 하에 배포됩니다.

```
MIT License

Copyright (c) 2024 LangGraph TTS Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

<div align="center">

**Made with ❤️ using LangGraph and Gemini**

**Happy Building! 🎉**

[⬆ Back to Top](#-langgraph-tts---오디오북-변환기)

</div>
