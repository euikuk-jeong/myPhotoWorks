# 세션 요약: release-github 스킬 CHANGELOG 업데이트 단계 추가

- **날짜/시간**: 2026-04-10 21:10

---

## 작업 목록

- `release-github` 스킬에 커밋 전 CHANGELOG.md 자동 업데이트 단계(Step 2) 추가
- 기존 Step 번호 전체 재정렬 (Step 2~9 → Step 3~11)
- 완료 요약 출력에 CHANGELOG 업데이트 항목 추가

---

## 변경된 스킬 흐름

| 단계 | 내용 |
|------|------|
| Step 1 | 현재 상태 확인 |
| Step 2 | **CHANGELOG.md 업데이트** (신규) |
| Step 3 | 커밋 (CHANGELOG.md 포함) |
| Step 4 | Push |
| Step 5 | main으로 PR 생성 |
| Step 6 | PR Merge |
| Step 7 | 버전 결정 |
| Step 8 | 태그 생성 및 GitHub Release |
| Step 9 | 작업 브랜치로 복귀 |
| Step 10 | 완료 요약 출력 |

---

## CHANGELOG.md 업데이트 동작 상세

- 파일 없으면 자동 생성
- `git diff --stat` + `git log main..HEAD` 기반으로 Added / Changed / Fixed 항목 자동 분류
- 버전 미확정 시 `[Unreleased]`로 작성, Step 7(버전 확정) 후 버전 채움
- 작성 내용을 사용자에게 보여주고 확인 후 저장
- 이후 Step 3 커밋에 CHANGELOG.md 자동 포함

---

## 스킬 파일 위치

```
C:\Users\EK Jeong\.claude\plugins\local\release-github\skills\release-github\SKILL.md
```
