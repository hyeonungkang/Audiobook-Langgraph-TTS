# Audiobook TTS Frontend

React 기반의 오디오북 TTS 생성기 프론트엔드입니다.

## 기능

- 텍스트 입력 또는 파일 업로드
- 언어 선택 (한국어/영어)
- 카테고리 선택 (논문, 커리어, 어학, 철학, 기술뉴스)
- 서사 모드 선택 (멘토, 이성친구, 친구, 라디오쇼)
- 29개 음성 선택 (여성 13개, 남성 16개)
- 실시간 진행 상황 표시
- 생성된 오디오 파일 다운로드

## 설치 및 실행

### 개발 모드

```bash
# 의존성 설치
npm install

# 개발 서버 실행 (http://localhost:5173)
npm run dev
```

### 프로덕션 빌드

```bash
npm run build
```

## 백엔드 연동

프론트엔드는 백엔드 API 서버 (`http://localhost:8000`)와 연동됩니다.

### 백엔드 실행 방법

```bash
# 프로젝트 루트에서
cd src
python server.py
```

### API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/v1/convert` | POST | TTS 변환 시작 |
| `/api/v1/convert/{job_id}/status` | GET | 작업 상태 조회 |
| `/api/v1/outputs/{filename}` | GET | 파일 다운로드 |
| `/api/v1/voices` | GET | 음성 목록 |
| `/api/v1/modes` | GET | 서사 모드 목록 |

## 기술 스택

- React 18
- TypeScript
- Vite
- CSS (커스텀 스타일링)
