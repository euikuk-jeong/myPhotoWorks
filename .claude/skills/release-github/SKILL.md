---
name: release
description: GitHub 릴리즈 워크플로우 스킬. 현재 브랜치의 변경사항을 commit/push하고 main으로 PR을 생성·merge한 뒤 버전 태그를 생성합니다. 사용자가 "릴리즈", "배포", "release", "/release", "PR 만들고 merge", "태그 만들어", "버전 올려", "main에 올려", "ship", "publish" 등을 언급하거나, commit→push→PR→merge→tag를 한 번에 처리하고 싶을 때 반드시 이 스킬을 사용하세요.
---

# GitHub Release Workflow

현재 작업 브랜치를 커밋·푸시하고 main에 PR을 생성·merge한 뒤 지정 버전으로 태그를 만드는 전체 릴리즈 흐름을 안내합니다.

사용법: `/release [version]`  
예시: `/release v1.2.0` 또는 `/release` (자동 버전 증가)

---

## Step 1: 현재 상태 확인

아래를 병렬로 실행해 상태를 파악한다:

```bash
git status --short
git branch --show-current
git log main..HEAD --oneline
git remote get-url origin
```

- **main 브랜치인 경우**: 어떤 브랜치에서 작업할지 사용자에게 묻고 중단한다.
- **remote가 없는 경우**: 에러를 안내하고 중단한다.

---

## Step 2: 버전 결정

커밋/PR 전에 버전을 확정한다. `pyproject.toml` 업데이트가 릴리즈 커밋에 포함되어야 하므로 이 단계를 먼저 수행한다.

**버전이 인수로 주어진 경우** (예: `/release v1.2.0`): 그대로 사용한다.

**버전이 없는 경우**:

1. 최신 태그 조회 (리모트 포함):
   ```bash
   git fetch --tags
   git tag --sort=-v:refname | head -1
   ```
2. 태그가 있으면 **minor 버전 +1** 한다:
   - `v1.2.3` → `v1.3.0`
   - `1.2.3` → `1.3.0`
   - 접미사(`-beta`, `-rc1` 등)는 제거한다
3. 태그가 없으면 `v0.1.0`을 기본값으로 제안한다
4. 사용자에게 확인한다:
   > "버전 태그를 **vX.Y.Z** 로 생성합니다. 다른 버전을 원하시면 입력해주세요 (Enter로 확인):"

---

## Step 3: pyproject.toml 버전 업데이트

확정된 버전(예: `v1.2.0` → `1.2.0`, `v` 접두사 제거)으로 `pyproject.toml`의 `version` 필드를 업데이트한다.

```toml
# pyproject.toml
version = "X.Y.Z"   ← 이 줄을 새 버전으로 교체
```

Edit 도구로 직접 수정한다. 수정 후 사용자에게 변경 내용을 보여준다:
> "`pyproject.toml` 버전을 `0.9.3` → `1.2.0` 으로 업데이트했습니다."

---

## Step 4: 커밋 (변경사항이 있을 때만)

`git status`에 수정/추가된 파일이 있으면:

1. `git diff --stat`으로 변경 요약을 보여준다 (pyproject.toml 포함 여부 확인)
2. 사용자에게 커밋 메시지를 묻는다:
   > "커밋 메시지를 입력해주세요 (비우면 자동 생성):"
3. 입력이 없으면 변경 내역을 기반으로 conventional commit 형식으로 자동 생성한다
   - 예: `feat: add image rotation`, `fix: resolve EXIF double-rotation`, `chore: update dependencies`
4. `pyproject.toml`을 포함해 스테이징 후 커밋:
   ```bash
   git add -A
   git commit -m "<message>"
   ```

변경사항이 pyproject.toml 업데이트만 있는 경우에도 커밋한다:
```bash
git add pyproject.toml
git commit -m "chore: bump version to <version>"
```

---

## Step 5: Push

```bash
git push -u origin <current-branch>
```

- 리모트 브랜치가 없으면 `--set-upstream`을 자동으로 사용한다.
- push 실패 시 (히스토리 충돌 등) **절대 force push하지 않는다**. 오류를 보여주고 사용자에게 해결 방법을 묻는다.

---

## Step 6: main으로 PR 생성

`gh` CLI로 PR을 생성한다:

```bash
gh pr create \
  --base main \
  --title "<title>" \
  --body "<body>"
```

**PR 제목**: 커밋이 하나면 커밋 메시지를, 여럿이면 변경 사항을 한 줄로 요약한다.

**PR 본문 템플릿**:
```
## Changes
- <commit 1>
- <commit 2>

## Summary
<이번 릴리즈에 포함된 내용 1~2문장 요약>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

이미 해당 브랜치의 PR이 존재하면 (`gh pr list --head <branch>`) 새로 만들지 않고 기존 PR을 재사용한다.

PR URL을 사용자에게 보여준다.

---

## Step 7: PR Merge

```bash
gh pr merge <PR-number> --merge
```

- 기본은 `--merge` (squash/rebase는 사용자 요청 시에만 사용).
- merge 충돌이 발생하면 **자동 해결하지 않는다**. 사용자에게 알리고 수동 해결을 안내한다.

merge 완료 후 main으로 전환하고 최신화한다:

```bash
git checkout main
git pull
```

---

## Step 8: 태그 생성 및 GitHub Release

main 브랜치에서 태그를 만들고 push한다:

```bash
git tag -a <version> -m "Release <version>"
git push origin <version>
```

GitHub Release를 생성한다:

```bash
gh release create <version> \
  --title "Release <version>" \
  --notes "<PR 본문의 Changes + Summary 내용 재사용>"
```

---

## Step 9: 작업 브랜치로 복귀

릴리즈가 완료되면 원래 작업 브랜치로 돌아온다:

```bash
git checkout <original-branch>
```

---

## Step 10: 완료 요약

아래 형식으로 결과를 출력한다:

```
✅ Release <version> 완료!

브랜치: <branch> → main (merged)
태그:   <version>
PR:     <PR URL>
Release: <GitHub release URL>
현재 브랜치: <original-branch> (복귀 완료)
```

---

## 에러 처리

| 상황 | 대응 |
|------|------|
| 이미 존재하는 태그 | 경고 후 다른 버전 입력 요청 |
| PR merge 충돌 | 자동 해결하지 않음. 사용자에게 수동 해결 안내 |
| gh auth 오류 | `gh auth status` 실행 안내 |
| main 브랜치가 아닌 다른 기본 브랜치 | `gh repo view --json defaultBranchRef`로 자동 감지 |
| force push 요청 | 명시적 확인 없이는 절대 실행하지 않음 |
