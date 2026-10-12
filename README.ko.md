<div align="center">

# ai-criteria

**AI가 같은 실수를 또 한다. 매번 고치지 말고, 고친 것을 쌓아서 기준으로 만든다.**

[Claude Code](https://claude.com/claude-code)용 로컬 우선 플러그인. AI를 고쳐 준 순간을 기록하고,
**반복되는 근본 원인**만 골라 답하기 전에 통과해야 하는 기준으로 바꾼다.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)
![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen)

[English](README.md) · 한국어

</div>

---

## 문제

AI를 고쳐 주면 사과하고, 다음 주에 다른 파일에서 같은 실수를 한다.
"메모리" 노트는 **결론과 다짐**("스펙을 더 조심해서 읽겠다")만 담아서 검증할 수 없고, 쌓이기만 하며, 틀린 규칙은 지워지지 않는다.

## 아이디어

```
AI를 고쳐 줌 ──▶ /ai-log       냈다 / 실제 / 왜(WHY) 3칸 (훅이 상기시킴)
                    │ 주 1회
                    ▼
              /ai-rollup      인박스 → 주차 사례집
                    ▼
              /ai-criteria    같은 `왜` 2건 이상 → 승격 · 반례 → 폐기
                    ▼
      다음 세션 시작 때 현행 기준이 컨텍스트에 이미 들어와 있음
                    ▼
              /ai-check       되돌리기 어려운 결론 직전 게이트
```

1. **결과가 아니라 틀어진 전제를 적는다.** `왜: 기획서 문장 = 확정 요구사항으로 전제` (✗ "문서를 잘 못 읽음")
2. **독립적으로 반복돼야 승격한다.** 같은 `왜` 가 **서로 다른 2일 이상 2건** → 잠정, **3일 이상 3건** → 정식. 같은 날 3번 지적은 관찰 1번이다. 태그가 같아도 `왜` 가 다르면 다른 기준.
3. **기준은 반증 가능해야 한다.** 모든 기준에 **적용 조건**과 **무효 조건**이 있다.
4. **기준도 죽는다.** 반례가 나오면 폐기. 목록이 늘기만 하면 잘못 돌고 있는 것.

## 증거 단계

| 단계 | 같은 `왜` | 처리 |
|---|---|---|
| 대기 | 1건, 또는 하루에 여러 건 | `## Pending` 에 건수와 함께 보관 |
| 잠정 | 2건 이상, 2일 이상 | `[provisional]` 표시로 주입, 무효 조건 엄격히 |
| 정식 | 3건 이상, 3일 이상 | 일반 기준으로 주입 |
| 전역 | 2개 이상 프로젝트에서 같은 `왜` | 그 전엔 `@프로젝트` 한정 |
| 폐기 | 반례 2건 (1건이면 강등) | `## Retired` 로 이동 |

틀린 기준의 비용은 낮고(무효 조건이 거른다) 늦은 기준의 비용은 크다(실수가 계속 난다). 그래서 잠정은 낮게, 정식은 엄격하게 잡는다.
승격 뒤 진짜 증거는 **재발**이다: `ailog.py search "<문구>" --since <승격일>`. 문턱은 `~/.ai-criteria/config.json` 에서 조정한다.

## 설치

```
/plugin marketplace add phantomMillie/ai-criteria
/plugin install ai-criteria@ai-criteria
```

새 세션부터 동작한다. 설정·API 키·패키지 설치 없음(Python 3.8+ 표준 라이브러리). 확인: `python3 scripts/ailog.py doctor`

## 사용

### Claude Code · Codex · Gemini CLI 공용 설치

Claude Code 플러그인을 설치한 뒤, 이 저장소에서 실행한다:

```bash
python3 scripts/install_shared.py
```

세 도구 모두 기존 `~/.ai-criteria/`를 사용한다(`AI_CRITERIA_HOME`도 동일하게 설정해야 한다).
Codex와 Gemini CLI는 공용 `~/.agents/skills/ai-*` 스킬 5개를 발견한다.
설치기는 Claude 전용 스킬 경로를 독립적인 `~/.local/share/ai-criteria` 경로로 바꾸고,
`~/.codex/AGENTS.md`와 `~/.gemini/GEMINI.md`에 관리 블록을 추가한다.
기존 지침은 보존하고 변경 전 파일은 `~/.local/share/ai-criteria-backups/`에 백업한다.
재실행해도 블록은 중복되지 않는다. 기존 동명 사용자 스킬은 덮어쓰지 않는다.

새 세션부터 적용한다. 세 도구 모두 세션 시작 시 현행 기준을 자동 주입한다.
Claude·Codex의 `UserPromptSubmit`, Gemini의 `BeforeAgent`가 같은 정정 감지 로직을 실행한다.
Codex는 `~/.codex/hooks.json`, Gemini는 `~/.gemini/settings.json`에 훅을 병합하며 기존 설정을 보존한다.
Codex에서는 새 훅을 `/hooks`에서 검토·신뢰해야 실행된다. 설치기는 신뢰 승인을 자동으로 처리하지 않는다.
훅 실행이 불가능하면 전역 지침의 수동 읽기로 보완한다. 이미 주입된 기준을 중복으로 읽지 않는다.
정정 감지는 기록을 상기시키는 신호이며, 실제 오류 여부와 기록 내용은 모델이 판단한다.
훅 자체는 사례를 자동 생성하지 않는다. JSON 어댑터 오류는 세션이나 입력을 막지 않는다.
Gemini의 스킬 활성화 동의 등 호스트의 승인 정책은 그대로 따른다.
Claude는 기존 플러그인 훅을 계속 사용하므로 중복 설치할 필요가 없다.
설치기는 기록·태그·기준 데이터를 변경하거나 자동 승격하지 않는다.

| 하는 일 | 일어나는 일 |
|---|---|
| AI에게 "그거 틀렸어, 두 번째 파일 빠뜨렸잖아" | 훅이 지적을 감지 → AI가 같은 턴에 한 건 적립 |
| `/ai-rollup` (주 1회) | 인박스 → `cases/2026-W42.jsonl` (+ 읽기용 `.md`), 이어서 `/ai-criteria` |
| `/ai-criteria` | `왜` 를 묶어 승격·폐기, 나머지는 *Pending* |
| 새 세션 | **현재 프로젝트** 기준만 주입. 정리 안 된 사례 5건 이상이면 정리 제안 |
| `/ai-check` | 대조·집계·"확정" 같은 결론 직전: 입력 부족 먼저, 그다음 판정 기준의 무효 조건 |
| `/ai-recall` | 과거 사례 검색·통계·점검·export/import |

## 내 데이터

홈 디렉터리의 **숨김 폴더**(권한 700)에만 쌓인다.

```
~/.ai-criteria/
├── inbox.jsonl · cases/2026-W42.{jsonl,md} · criteria.md · tags.json · meta.json
```

- **어디로도 전송하지 않는다.** 네트워크 호출·텔레메트리·계정 없음. 표준 라이브러리만 쓰는 파일 하나.
- OS 사용자마다 따로 쌓인다. 위치는 `AI_CRITERIA_HOME` 으로 변경.
- 키·토큰·비밀번호 형태는 저장 전에 가리지만 보장은 아니다 — 사례에 비밀을 적지 않는다.
- 컴퓨터 옮기기: `ailog.py export --out x.json` → 새 컴퓨터에서 `ailog.py import x.json`.
- 팀 공유는 사례가 아니라 `criteria.md` 만 나눈다.

## 개발

```bash
python3 -m unittest discover -s tests -v
```

이슈·PR 환영. MIT. 변경 이력은 [CHANGELOG](CHANGELOG.md).
