# Research Assistance Liner

Liner로 논문을 수집하고, 출처 기록을 보존하며, 로컬 Markdown 위키를 큐레이션하기 위한 데이터 없는(evidence-first) 템플릿입니다. 이 저장소에는 합성 예시만 들어 있으며 실제 연구 코퍼스, 자격 증명, 실행 상태, 개인 편집기 설정은 포함하지 않습니다.

## 이 템플릿이 하는 일

- Liner API 클라이언트로 학술 문헌을 검색하고 구조화 추출을 요청합니다.
- 추출된 라벨마다 페이지를 만들지 않고 **토픽 허브**(정의, 논문, 테마, 인접 분야)에 모읍니다.
- 라벨 페이지는 raw 출처 2편부터 만들고, 이미 있는 논문은 추출을 생략하며, 갭 후보는 Scholar로 재확인합니다.
- 캡처한 근거는 `raw/`에 보관합니다. 캡처 뒤 raw 본문은 불변이며 SHA-256 체크섬을 가집니다.
- 근거가 있는 지식은 `entities/`, `concepts/`, `comparisons/`, `queries/`의 canonical 페이지로 큐레이션합니다.
- 누락된 연결 가능성을 Scholar 확인 뒤에 research-gap 후보로 표시합니다. 후보일 뿐 검증된 지식이 아니므로, 승격하거나 공유하기 전에 사람이 인용 근거를 확인해야 합니다.

근거나 canonical 페이지를 추가하기 전에 [SCHEMA.md](SCHEMA.md)를 읽으세요. 운영 모델은 [docs/architecture.md](docs/architecture.md), [docs/workflow.md](docs/workflow.md)에 있습니다.

## 빠른 시작

필요 사항: Git, Python 3.11 이상.

```bash
git clone git@github.com:DrawingProcess/research-assistance-liner.git
cd research-assistance-liner
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
cp .env.example .env
python -m pytest
```

로컬 인터프리터 이름이 `python3.11`이 아니라면 Python 3.11+를 선택하는 명령(예: `python3`)을 사용하세요. Windows PowerShell에서는 `.venv\\Scripts\\Activate.ps1`로 활성화하고 `Copy-Item .env.example .env`로 환경 파일을 복사합니다.

`.env.example`에는 필요한 유일한 서비스 설정이 있습니다.

```dotenv
LINER_API_KEY=<replace-with-your-liner-api-key>
```

`LINER_API_KEY`에는 자신의 Liner 계정에 발급된 API 키를 넣으세요. 라이브 Liner 호출에만 필요하며 테스트와 합성 드라이 런은 Liner에 연결하지 않습니다. 실제 값은 로컬 `.env`에만 보관하세요. `.env`를 커밋하지 마세요. API 응답, Discord 식별자, 로그, 생성된 실행 출력도 커밋하지 마세요.

POSIX 셸에서 라이브 명령을 실행하기 전에는 로컬 환경 파일을 불러옵니다.

```bash
set -a
. ./.env
set +a
```

## 첫 주제: 합성 드라이 런과 수동 조사

키 없이 시작하려면 `examples/`의 의도적으로 가공된 기록을 살펴보고 프로젝트 검사를 실행하세요.

```bash
python -m pytest
python scripts/validate_public_template.py --repo .
```

첫 실제 주제는 버전 관리 밖의 로컬 backlog에 추가한 뒤 Liner를 수동으로 조회합니다. 아래의 주제 문구를 자신의 주제로 바꾸세요.

```bash
python -c 'from pathlib import Path; from src.backlog import add_curiosity_topics, load_backlog, save_backlog; p = Path("research-gap/backlog.json"); b = load_backlog(p); add_curiosity_topics(b, ["your research topic"], "2026-09-09"); save_backlog(p, b)'
python -c 'import json; from src.liner_client import search_scholar, raise_for_status; r = search_scholar("your research topic"); raise_for_status(r, "scholar search"); print(json.dumps(r["response"], ensure_ascii=False, indent=2))'
python src/daily_pipeline.py
```

`python src/daily_pipeline.py`는 선택적인 v2 배치입니다(pending 최대 3개, 허브 컴파일, 목·일 Scholar 갭 검증, 월요일 커버리지 정찰). 직접 실행하기 전에는 돌아가지 않으며, 이 템플릿에는 활성화된 스케줄러가 없습니다. stdout을 직접 검토하세요. Liner 검색 결과, 추출, taxonomy, gap 결과를 결론으로 취급하지 마세요.

반환된 논문은 라이브러리 함수와 복사 가능한 [templates](templates/)로 한 편씩 캡처할 수도 있습니다. raw 기록의 체크섬은 frontmatter 뒤의 정확한 본문 바이트로 계산하고, raw 본문을 보존하며, canonical 지식을 만들거나 수정할 때는 `index.md`를 갱신하고 `log.md`에 추가합니다.

Liner 검색 결과, 추출, taxonomy, gap 결과를 결론으로 취급하지 마세요. 서지 정보와 출처 지원을 검증하고 관련 raw 기록을 비교한 뒤에만 canonical 페이지를 만들거나 수정합니다. 특히 자동 gap은 후보일 뿐 검증된 지식이 아닙니다.

## 데이터 구조

| 위치 | 목적 | Git 정책 |
| --- | --- | --- |
| `inbox/` | 캡처 전 임시 입력 | 로컬 내용 무시 |
| `raw/` | 불변 원문 근거 | 로컬 내용 무시, placeholder만 추적 |
| `entities/`, `concepts/`, `comparisons/`, `queries/` | 큐레이션한 canonical 위키 | 로컬 내용 무시, placeholder만 추적 |
| `research-gap/` | 로컬 backlog와 watcher 상태 | 무시 |
| `examples/` | 가공된 형식 예시 | 추적 |
| `templates/` | 복사해서 쓰는 Markdown 템플릿 | 추적 |

깨끗한 clone 상태에는 canonical 페이지가 0개인 것이 정상입니다. 실제 canonical 페이지에는 유효한 frontmatter, 해결되는 raw 출처, 필요한 경우 claim 수준 marker, `index.md`/`log.md` 동기화, 다른 활성 canonical 페이지 두 개 이상으로 향하는 서로 다른 링크가 필요합니다. 전체 규칙은 [SCHEMA.md](SCHEMA.md)를 참고하세요.

## 보안과 공개 전 검사

저장소는 자격 증명, 근거, canonical 데이터, 실행 상태, 출력, 보고서, 로그, 개인 편집기 상태를 무시합니다. 변경을 공유하기 전에 확인하세요.

```bash
git status --ignored --short
python scripts/validate_public_template.py --repo .
```

검증기는 안전망일 뿐 사람의 검토를 대신하지 않습니다. 커밋 전에는 `git diff --cached`를 확인하고, Git에 들어가기 전 개인 정보를 제거하세요.

## 로컬 기여

변경 뒤 전체 테스트를 실행하세요.

```bash
python -m pytest
```

이 템플릿은 로컬 수동 실행을 기본값으로 합니다. 자동화나 외부 연동은 자격 증명, 근거 보관, 검토, 접근 제어 방식을 결정한 뒤에만 추가하세요.
