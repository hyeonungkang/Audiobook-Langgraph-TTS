# 🔒 보안 확인 체크리스트

GitHub에 push하기 전에 API 키가 포함되지 않았는지 확인하세요.

## ✅ .gitignore에 포함된 항목 (안전)

다음 파일들은 `.gitignore`에 의해 자동으로 제외됩니다:

- ✅ `.env` - API 키 파일
- ✅ `config.json` - API 키 포함 설정 파일
- ✅ `loyal-operation-*.json` - 서비스 계정 키
- ✅ `*-e610e3f55565.json` - 서비스 계정 키
- ✅ `*service-account*.json` - 서비스 계정 키
- ✅ `*credentials*.json` - 인증 정보

## 🔍 최종 확인 방법

### 1. Git 저장소 초기화 (아직 안 했다면)
```bash
git init
```

### 2. 추가될 파일 확인
```bash
git status
```

### 3. 민감한 파일이 포함되지 않았는지 확인
```bash
# 다음 명령어로 확인 (아무것도 나오지 않아야 함)
git status | grep -E "\.env|config\.json|loyal-operation"
```

### 4. 실제로 추가될 파일 목록 확인
```bash
git add -n .
```

### 5. 만약 이미 추가된 파일이 있다면 제거
```bash
# 이미 추가된 민감한 파일 제거
git rm --cached config.json
git rm --cached loyal-operation-*.json
git rm --cached .env

# .gitignore에 추가되어 있으면 다시 추가되지 않음
```

## ⚠️ 주의사항

1. **소스 코드에 하드코딩된 API 키 확인**
   - `src/config.py`에 예시로만 `AIzaSy...`가 있음 (실제 키 아님) ✅
   - 다른 파일에 실제 API 키가 하드코딩되어 있지 않은지 확인하세요

2. **Git 히스토리 확인**
   - 이전에 API 키를 커밋했다면 히스토리에서 제거해야 합니다
   ```bash
   # Git 히스토리에서 민감한 파일 제거 (주의: 히스토리 재작성)
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch config.json loyal-operation-*.json" \
     --prune-empty --tag-name-filter cat -- --all
   ```

3. **원격 저장소 확인**
   - 이미 push했다면 즉시 키를 재발급하세요
   - GitHub의 "Secret scanning" 기능이 자동으로 감지할 수 있습니다

## ✅ 현재 상태

- `.gitignore` 설정: ✅ 올바름
- 소스 코드 하드코딩: ✅ 없음 (예시만 있음)
- 민감한 파일 존재: `config.json`, `loyal-operation-*.json` (하지만 .gitignore에 포함됨)

**결론**: `.gitignore` 설정이 올바르므로, `git add` 시 민감한 파일은 자동으로 제외됩니다.

