# 세션 요약: release-github 개인 스킬 생성

- **날짜/시간**: 2026-04-10 20:59

---

## 작업 목록

- Claude Code에서 사용할 개인 커스텀 스킬 `release-github` 생성
- 플러그인 구조(`plugin.json`, `installed_plugins.json`, 디렉토리 패턴) 탐색 및 분석
- 공식 마켓플레이스(`claude-plugins-official`)에 잘못 배치된 스킬을 로컬 경로로 이전
- 스킬 이름 `release` → `release-github` 변경

---

## 스킬 동작 흐름

| 단계 | 내용 |
|------|------|
| Step 1 | 브랜치·변경사항·미push 커밋 확인 |
| Step 2 | 변경사항 커밋 (메시지 입력 또는 자동 생성) |
| Step 3 | `git push -u origin <branch>` |
| Step 4 | `gh pr create` — 커밋 내역 기반 PR 자동 생성 |
| Step 5 | `gh pr merge --merge --delete-branch` → main 체크아웃 |
| Step 6 | 버전 결정 (미지정 시 마지막 태그 minor +1) |
| Step 7 | `git tag -a` + `gh release create` |
| Step 8 | 원래 작업 브랜치로 복귀 |
| Step 9 | 완료 요약 출력 |

---

## 주요 결정 사항

- 개인 커스텀 스킬은 `~/.claude/plugins/local/` 아래에 배치 (`@local` 네임스페이스)
- 공식 마켓플레이스 디렉토리(`marketplaces/claude-plugins-official/plugins/`)에는 배치하지 않음
- `installed_plugins.json`에 `release-github@local`로 등록

---

## 스킬 파일 위치

```
C:\Users\EK Jeong\.claude\plugins\local\release-github\
├── .claude-plugin\plugin.json
└── skills\release-github\SKILL.md   ← 수정 시 이 파일
```

등록 파일: `C:\Users\EK Jeong\.claude\plugins\installed_plugins.json`

---

## 다음 단계

- 실제 프로젝트에서 `/release-github` 스킬 사용 테스트
- 필요 시 SKILL.md 내용 보완 후 `/reload-plugins` 적용
