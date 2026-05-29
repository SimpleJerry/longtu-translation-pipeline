# LongtuKorea Translation Model

[한국어](README.md) | [English](README.en.md) | [中文](README.zh-CN.md)

LongtuKorea의 게임 현지화 번역 모델 실험 저장소입니다. 현재 저장소는 중국어 간체(`zh-CN`)에서 한국어(`ko`)로 번역하는 NLLB 기반 파인튜닝 흐름을 중심으로, 용어집 매칭, 번역 결과 생성, BLEU 및 용어 보존 평가를 함께 다룹니다.

이 문서는 현재 저장소의 실제 상태를 정리하기 위한 문서입니다. 아직 패키지화된 제품 코드라기보다 데이터 처리 스크립트와 연구용 notebook이 함께 있는 실험 저장소에 가깝습니다.

## 프로젝트 현황 및 결과

이 저장소는 이제 재현 가능한 zh-CN → ko 파인튜닝 파이프라인과 학습·평가가 끝난 모델을 모두 포함합니다. 작업은 긴 점진적 리팩터링(RF-001 ~ RF-029)이었습니다.

- **데이터 거버넌스** (RF-001/002/004/009/010) — IDE/Excel 아티팩트를 Git에서 제거, raw 스프레드시트를 검토 가능한 CSV로 변환, 2023 notebook 아카이브, 다국어 말뭉치를 커밋되는 두 개의 이중언어 파일로 축소.
- **Glossary 정제** (RF-010/011/012/014) — 로컬 semantic pipeline(Stanza / jieba / kiwipiepy / wordfreq / `BAAI/bge-m3`), strict 1:1 강제, glossary↔segment 교차 일관성, 선택적 cloud LLM delete-only pass.
- **Segment 정제** (RF-005/011/013/015/029) — markup/wrapper 정규화, 구조 분리, target 언어 오염 제거, 단일 `<start>...<end>` 용어 marker 표준, strict glossary 일관성 학습 게이트, 전체 말뭉치 cloud LLM pass(OpenAI Batch API).
- **학습 및 평가** (RF-006/007) — 결정적 8:1:1 split(seed 42)을 쓰는 config 기반 NLLB 학습/추론/평가 CLI; BLEU + glossary preservation(exact & no-space) + chrF 보고; composite 품질 지표로 best checkpoint를 자동 선택하는 early-stopping 루프.
- **엔지니어링 하드닝 및 테스트** (RF-016–022) — 공용 LLM client 모듈, 의존성 정리, 공개 API 축소, notebook 아카이브, 정제 pipeline 단위 테스트 보강.

**현재 모델.** early-stopping run의 `checkpoint-48000`, beam search(`num_beams=4`) 디코딩. held-out test split(seed 42, 학습 및 checkpoint 선택에서 미사용):

| 지표 | 점수 |
| --- | --- |
| BLEU (공백 단위) | 0.325 |
| chrF (max_n=6, β=2) | 0.590 |
| Glossary preservation (no-space) | 0.954 |
| Glossary preservation (exact) | 0.950 |

**능력 단계표** (동일한 test split, 전 단계 beam=4 — 각 단계는 해당 최선 설정으로 실행):

| 단계 | BLEU | chrF | Preservation (no-space) |
| --- | --- | --- | --- |
| Zero-shot NLLB-600M *(진짜 기준선 — raw 중국어 입력, marker 없음)* | 0.009 | 0.226 | 0.323 |
| Fine-tuned `checkpoint-48000`, beam=4 **(이 모델, marker 활성화)** | **0.325** | **0.590** | **0.954** |

*(중간 진단: 10k under-fit fine-tuned run, BLEU ≈ 0.198 — 과소적합 방향 확인용이며 기준선이 아닙니다.)*

파인튜닝 + 데이터 정제의 순 효과: 동일한 beam=4 디코딩 기준 **+0.316 BLEU (~34×)**; glossary preservation이 ~32%에서 ~95%로 상승했습니다. Zero-shot 기반 모델은 유창하게 들리는 한국어를 생성하지만 게임 특유 용어와 캐릭터 이름을 완전히 놓칩니다. 파인튜닝과 데이터 정제가 합쳐서 전체 차이를 설명합니다. 정확한 말뭉치 행 수와 SHA256은 매 정제 pass마다 바뀌므로 여기서 중복하지 않고 [docs/refactor/backlog.md](docs/refactor/backlog.md)에 기록합니다.

## 현재 범위

- 저장소에는 최종 학습 말뭉치와 용어집만 보관하며, 민감한 raw Excel/CSV 입력은 커밋하지 않습니다.
- 로컬 semantic pipeline으로 중국어-한국어 게임 용어집을 정제합니다.
- `facebook/nllb-200-*` 계열 모델을 기반으로 게임 번역 데이터를 파인튜닝합니다.
- 번역 중 용어집 항목을 표시하기 위해 단일 `<start>...<end>` 특수 토큰 형태를 사용합니다.
- T&N+R 및 code-id code/tag 보호는 역사적 실험으로만 보관하며 현재 주 흐름에서는 사용하지 않습니다.
- 번역 결과를 Excel/CSV로 내보내고 BLEU와 용어 보존율을 평가합니다.

## 저장소 구조

```text
.
├── README.md
├── README.en.md
├── README.zh-CN.md
├── requirements.txt
├── requirements-training.txt
├── data/
│   ├── glossary.csv
│   ├── segments.csv
│   └── review/                # 로컬 생성, Git 제외
├── configs/
│   ├── cross_cleaning/
│   ├── glossary/
│   ├── evaluation/
│   ├── inference/
│   ├── segments/
│   └── training/
├── scripts/
│   ├── glossary_semantic_pipeline.py
│   ├── glossary_llm_cleanup_pipeline.py
│   ├── evaluate_translation.py
│   ├── segments_cleaning_pipeline.py
│   ├── segments_llm_cleanup_pipeline.py
│   ├── segments_glossary_cross_cleaning_pipeline.py
│   ├── run_inference.py
│   └── train_model.py
├── src/
│   └── longtu_translation_pipeline/
├── notebooks/
│   ├── main/
│   ├── analysis/
│   └── archive/2023-legacy/
└── docs/
    ├── data-cleaning.md
    ├── notebooks/inventory.md
    └── refactor/
```

## 주요 파일

| 파일 | 역할 |
| --- | --- |
| `data/segments.csv` | `segment_id`, `zh-CN`, `ko` 컬럼만 가진 최종 문장/구간 학습 말뭉치입니다. |
| `data/glossary.csv` | `term_id`, `zh-CN`, `ko` 컬럼만 가진 최종 중국어-한국어 게임 용어집입니다. |
| `data/review/` | 로컬 데이터 정제 감사 CSV와 검토용 산출물이며 기본적으로 커밋하지 않습니다. |
| `configs/glossary/` | glossary 정제에 쓰는 seed, 어휘 목록, 규칙 설정입니다. |
| `configs/segments/` | segment 정제를 위한 구조화 문자열 분리, term/entity seed, semantic 임계값 설정입니다. |
| `configs/cross_cleaning/` | glossary/segments 교차 일관성 정제 임계값 설정입니다. |
| `configs/training/default.json` | RF-006 1단계 학습 설정이며 데이터 경로, 언어 코드, 모델명, 출력 디렉터리, 기본 학습 파라미터를 선언합니다. |
| `configs/training/full_10k.json` | 첫 full-data 10k training profile이며 step, checkpoint, eval, optimizer 설정을 명시합니다. |
| `configs/inference/default.json` | RF-006 1단계 추론 설정이며 모델 경로, 입력/출력 경로, 언어 코드, 생성 파라미터를 선언합니다. |
| `configs/evaluation/default.json` | RF-007 평가 설정이며 번역 결과 CSV, glossary, BLEU 설정, 로컬 보고서 출력 위치를 선언합니다. |
| `scripts/glossary_semantic_pipeline.py` | Stanza, jieba, kiwipiepy, wordfreq, `BAAI/bge-m3`를 사용하는 로컬 glossary semantic 정제 pipeline입니다. |
| `scripts/glossary_llm_cleanup_pipeline.py` | Cloud OpenAI-compatible glossary aggressive cleanup entry point입니다. 용어 삭제만 허용하고 로컬 ignored review를 작성합니다. |
| `scripts/evaluate_translation.py` | BLEU와 glossary preservation을 계산하는 번역 결과 평가 CLI이며 모델을 로드하지 않습니다. |
| `scripts/segments_cleaning_pipeline.py` | 로컬 segments semantic 정제 pipeline이며 기본적으로 dry-run review를 생성합니다. |
| `scripts/segments_llm_cleanup_pipeline.py` | Cloud OpenAI-compatible segments 전체 정제 entry point입니다. 한국어 rewrite는 로컬 검증을 통과한 경우에만 적용합니다. |
| `scripts/segments_glossary_cross_cleaning_pipeline.py` | glossary/segments 교차 정제 CLI이며 고신뢰 용어 충돌 행을 제거하고 로컬 review를 생성합니다. |
| `scripts/train_model.py` | 설정 dry-run, 로컬 tiny tokenizer smoke, 실제 tokenizer + tiny Trainer smoke, 실제 NLLB model 1-step smoke, pilot training, formal run-directory training을 지원하는 학습 CLI입니다. |
| `scripts/run_inference.py` | 추론 CLI입니다. 설정 dry-run과 실제 checkpoint 기반 sample generation을 지원합니다. |
| `src/longtu_translation_pipeline/text_protection.py` | 테스트 가능한 용어 marker 보호 pure-function 모듈입니다. |
| `src/longtu_translation_pipeline/config.py` | 학습/추론 JSON 설정을 dataclass로 파싱하고 검증합니다. |
| `src/longtu_translation_pipeline/training.py` | import 가능한 학습 데이터 준비 및 Trainer 연결 API입니다. |
| `src/longtu_translation_pipeline/inference.py` | import 가능한 추론 입력 계획 dry-run API입니다. |
| `src/longtu_translation_pipeline/evaluation.py` | import 가능한 BLEU와 glossary preservation 평가 API입니다. |
| `notebooks/main/` | 주요 학습, 전처리, 생성, 평가 실험 notebook입니다. |
| `notebooks/analysis/` | train/eval loss 시각화 같은 보조 분석 notebook입니다. |
| `notebooks/archive/2023-legacy/` | 2023년 legacy 실험 archive이며 첫 번째 정리 단계에서는 삭제하지 않습니다. |
| `docs/notebooks/inventory.md` | Notebook의 시간순 흐름, 목적, 의존성 상태, 보존/archive/삭제 제안입니다. |
| `docs/data-cleaning.md` | 스타일 태그, 구조화 문자열, 짧은 조각, target 오염, strict gate 예시를 포함한 데이터 정제 규칙 설명입니다. |
| `requirements-training.txt` | RF-006 학습 smoke test 및 이후 학습 chain 의존성입니다. |

## 실행 환경

권장 환경은 Windows 또는 Linux의 Python 가상환경입니다. `requirements.txt`에는 실제로 사용 중인 로컬 semantic cleaning 의존성과 CUDA 13.2 계열 PyTorch가 기록되어 있습니다. 기본 CLI, dry-run, 테스트, RF-007 evaluation은 대부분 표준 라이브러리만 사용하므로 모든 workflow가 전체 의존성을 필요로 한다는 뜻은 아닙니다. `requirements-training.txt`에는 RF-006 학습 smoke test 및 이후 학습 chain 의존성을 기록하며, 현재는 `transformers`, `tokenizers`, `accelerate`, `sentencepiece`와 직접 실행 의존성을 포함합니다. `datasets`는 아직 현재 최소 chain에 포함하지 않습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
jupyter lab
```

RF-006-P2 이후 학습/inference chain을 실행하려면 학습 chain 의존성도 설치합니다. 먼저 `requirements.txt`를 설치한 후 `requirements-training.txt`를 설치합니다.

```powershell
python -m pip install -r requirements-training.txt   # 학습이 필요한 경우에만
```

참고:

- Stanza 중국어/한국어 모델과 Hugging Face embedding cache는 로컬 가상환경 아래에 두며 Git에 커밋하지 않습니다.
- Legacy BLEU notebook은 `nltk.translate.bleu_score`를 사용했지만, 현재 RF-007 evaluation CLI는 pure-Python 구현이므로 `nltk`가 필요하지 않습니다.
- 큰 모델, 학습 결과, 번역 결과, raw 데이터, 로컬 모델 cache는 `.gitignore`에 의해 제외됩니다.

## 기본 워크플로

이 저장소에 커밋되는 학습 데이터 진입점은 최종 CSV입니다.

- `data/segments.csv`
- `data/glossary.csv`

민감한 raw Excel/CSV 파일은 커밋하지 않습니다. `data/glossary.csv`는 로컬 semantic pipeline으로 반복 정제되며, 감사 CSV는 로컬 `data/review/` 아래에 생성되지만 Git에는 커밋하지 않습니다.
`data/segments.csv`는 glossary 정제에 현재 제품 말뭉치 근거를 제공하지만, 용어 보존의 유일한 기준이거나 충분조건은 아닙니다.
pipeline은 로컬 단어 빈도, 품사 형태, embedding, 게임 도메인 신호도 함께 사용해 일반 단어와 게임 용어를 구분합니다.
최종 커밋 CSV는 중국어-한국어 이중언어 말뭉치이며, 중국어/한국어가 아닌 학습 컬럼은 최종 corpus에 보관하지 않습니다.

glossary 정제를 다시 실행하려면 먼저 Stanza 모델을 내려받습니다.

```powershell
$env:STANZA_RESOURCES_DIR="D:\longtu-translation-pipeline\venv\stanza_resources"
venv\Scripts\python.exe -c "import stanza; stanza.download('zh', model_dir=r'D:\longtu-translation-pipeline\venv\stanza_resources'); stanza.download('ko', model_dir=r'D:\longtu-translation-pipeline\venv\stanza_resources')"
```

그다음 로컬 pipeline을 실행합니다.

```powershell
$env:HF_HOME="D:\longtu-translation-pipeline\venv\hf_cache"
$env:STANZA_RESOURCES_DIR="D:\longtu-translation-pipeline\venv\stanza_resources"
venv\Scripts\python.exe scripts\glossary_semantic_pipeline.py
```

기본 규칙 디렉터리는 `configs/glossary/`이며 seed 파일, 어휘 목록, `rules.json`을 포함합니다. `--config-dir`, `--game-seeds`, `--common-noun-seeds`로 다른 파일을 지정할 수 있습니다.

로컬 규칙만으로 일반 단어와 회사 게임 용어를 더 이상 충분히 구분하기 어렵다면 cloud LLM delete-only cleanup을 사용할 수 있습니다. 이 단계는 현재 `data/glossary.csv`의 용어쌍을 OpenAI-compatible Chat Completions API로 보내며, 모델은 keep/delete만 판단합니다. 한국어 번역을 고치거나, 새 용어를 추가하거나, 용어를 병합하지 않습니다. 감사 산출물은 로컬 `data/review/llm_glossary_cleanup/` 아래에 기록되며 Git에 커밋하지 않습니다.

```powershell
$env:OPENAI_API_KEY="<your-key>"
$env:LLM_MODEL="<your-model>"
# 선택: $env:OPENAI_BASE_URL="https://api.openai.com/v1"
venv\Scripts\python.exe scripts\glossary_llm_cleanup_pipeline.py --apply
```

LLM cleanup 뒤에는 학습을 시작하기 전에 strict gate와 training dry-run을 다시 실행해야 합니다.

본문 말뭉치 정제를 확인하거나 반복하려면 먼저 dry-run을 실행합니다.

```powershell
venv\Scripts\python.exe scripts\segments_cleaning_pipeline.py --dry-run
```

이 pipeline은 먼저 `<c=...>` 같은 표현용 스타일 태그를 제거하고 대칭 외부 wrapper를 푼 뒤, 고신뢰 non-segment fragment와 한국어 target-language contamination을 삭제합니다. 그 다음 Stanza, jieba, kiwipiepy, `BAAI/bge-m3`로 term/entity-like segment를 점수화합니다. Placeholder 행은 기본적으로 보존하고 mismatch만 감사하지만, target 쪽이 강한 오염 규칙에 걸리면 삭제됩니다. 이 명령은 `data/segments.csv`를 다시 쓰지 않고 로컬 `data/review/segments/` 아래에 감사 CSV만 생성합니다. 수동 확인 후에만 `--apply`를 사용합니다. 각 정제 유형의 예시는 `docs/data-cleaning.md`를 참고하세요.

`segments.csv` 전체를 LLM으로 다시 검사하려면 cloud segment cleanup entry point를 사용합니다. LLM에는 원문 중한 텍스트, placeholder, 매칭된 glossary term만 전달하고 target contamination, structured-string, 길이 비율 같은 로컬 선판단 신호는 응답 이후 검증과 감사에만 사용합니다. LLM은 행 삭제 또는 한국어 rewrite를 제안할 수 있지만, 로컬 검증을 통과한 한국어 rewrite만 corpus에 적용합니다. 검증은 비어 있지 않은 Hangul 출력, 중국어 오염 없음, placeholder 보존, exact/no-space glossary 보존, 길이 비율, 반복 출력 패턴을 확인합니다. 감사 파일은 로컬 `data/review/llm_segments_cleanup/` 아래에 기록되며 Git에 커밋하지 않습니다.

```powershell
$env:OPENAI_API_KEY="<your-key>"
$env:LLM_MODEL="<your-model>"
venv\Scripts\python.exe scripts\segments_llm_cleanup_pipeline.py --dry-run
```

로컬 review를 확인한 뒤에만 `--apply`를 사용합니다. 전체 LLM segment cleanup 이후에는 기존 training run, split, report가 모두 무효가 되므로 strict-check와 training dry-run을 다시 실행해야 합니다.

glossary와 segments의 용어 일관성을 확인하려면 먼저 dry-run을 실행하고 검토 후 apply합니다.

```powershell
venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --dry-run
venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --apply
```

교차 정제는 고신뢰 glossary noise 또는 강한 용어집 항목과 충돌하는 segment 행만 자동 삭제합니다. 한국어 번역문을 자동 치환하지 않으며, 삭제 내용은 로컬 `data/review/segments_glossary_cross/` 아래에 기록합니다.
기본 흐름은 다음과 같습니다. `segments.csv`를 longest-first, non-overlap 중국어 용어 매칭으로 스캔하고, 한국어 쪽이 glossary 번역을 exact 및 no-space exact로 보존하는지 확인합니다. 그 다음 `configs/cross_cleaning/rules.json`의 임계값으로 term별 preserved/missing 근거를 집계해 glossary noise, strong glossary term, review 항목으로 분류합니다. 마지막으로 고신뢰 glossary noise와 strong term을 누락한 segment 행만 삭제합니다.
학습 전에는 더 엄격한 gate를 사용할 수 있습니다. 이 모드는 남은 glossary 용어가 모든 matching segment 안에서 반드시 보존되어야 한다고 검사합니다.

```powershell
venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --strict-dry-run
venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --strict-check
```

Strict mode는 먼저 실제 `segments.csv` 번역을 기준으로 enforceable glossary를 고릅니다. 누락이 없는 term은 보존하고, 강한 게임 도메인 term은 충분한 preserved evidence와 제한된 missing rate가 필요하며, 경험적으로 안정적인 term은 높은 preserved count/rate가 필요합니다. 이 조건을 만족하지 못하고 mismatch가 있는 term은 glossary에서 제거합니다. 그 다음 enforceable glossary term을 포함하지만 한국어가 해당 번역을 보존하지 않는 segment 행만 삭제합니다. `--strict-check`는 현재 데이터를 검사만 하며 누락 용어가 있으면 실패합니다. 로컬 strict review를 확인한 뒤에만 `--strict-apply`를 사용합니다.
Full training 또는 최종 test report 전에 `--strict-check`는 반드시 통과해야 합니다.

학습/추론/평가 entry point는 config 기반이며, 최종 모델까지 end-to-end로 실행되었습니다(위 "프로젝트 현황 및 결과" 참고). dry-run은 설정 읽기, 데이터 검증, 결정적인 train/validation/test 계획만 수행합니다. RF-006-P7은 ignored `fine-tuned-models/.../runs/run-*` 아래에 고정 split artifact와 `run_manifest.json`을 작성합니다. RF-006-P10은 formal experiment split을 seed `42`의 8:1:1로 수정합니다. validation은 학습 중 eval/checkpoint 관찰에만 쓰고, 최종 성능 보고는 held-out test split만 사용합니다. RF-006-P8은 고정 validation split에서 translation CSV를 만들고, `--generate-test`는 고정 test split에서 최종 평가 CSV를 만듭니다. 아래 smoke/pilot 명령은 빠른 engineering chain 검증용으로 계속 사용할 수 있습니다. 현재 모델 run은 `run-full-earlystop-v1`입니다.

```powershell
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --dry-run
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --smoke-test
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --nllb-smoke-test --smoke-rows 2
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --real-model-smoke-test --smoke-rows 2
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --pilot-train --pilot-rows 64 --max-steps 4 --save-steps 2
venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_10k.json --train --limit-rows 128 --max-steps 4 --save-steps 2 --save-total-limit 2 --logging-steps 1
venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_10k.json --train --run-dir fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-name --resume-from-checkpoint latest --max-steps 6 --save-steps 2 --save-total-limit 2 --logging-steps 1
venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_10k.json --train --run-name run-full-10k-corrected-v1
venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --dry-run
venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --generate --model-path fine-tuned-models\nllb-200-distilled-600M\zh2ko\pilot\run-20260525-093832\checkpoint-4 --sample-rows 8
venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --generate-validation --run-dir fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-name
venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --generate-test --run-dir fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-full-10k-corrected-v1
```

기존 번역 결과 CSV를 평가하려면 RF-007 평가 entry point를 사용합니다. 입력은 notebook의 기존 출력 컬럼인 `source`, `references`, `candidates`를 사용합니다. BLEU는 기본적으로 한국어 공백 단위 토큰화를 사용하며, glossary preservation은 후보 번역에서 `<start>...<end>` marker를 제거한 뒤 한국어 용어가 포함되었는지 검사합니다. RF-024부터 chrF(문자 n-gram F-score, max_n=6, beta=2)도 함께 보고하며, BLEU보다 한국어처럼 형태소가 풍부한 언어에서 인간 판단과 더 높은 상관관계를 가집니다. 모델이 빈 `candidates`를 생성한 경우 report를 중단하지 않고 `empty_candidate_rows`로 기록합니다.
Inference entry point는 이제 tokenization 전에 `data/glossary.csv` 기준으로 source에 학습과 동일한 `<start>...<end>` 용어 marker를 적용합니다. 단, 생성 CSV에는 review를 위해 원본 source를 그대로 씁니다. RF-007은 exact와 no-space glossary preservation을 함께 보고합니다. exact는 형식 일관성을 보고, no-space는 한국어 띄어쓰기 차이를 실제 용어 누락으로 오판하지 않기 위한 지표입니다.

```powershell
venv\Scripts\python.exe scripts\evaluate_translation.py --config configs\evaluation\default.json --input translation_result.csv
venv\Scripts\python.exe scripts\evaluate_translation.py --config configs\evaluation\generation_report.json --checkpoint fine-tuned-models\nllb-200-distilled-600M\zh2ko\pilot\run-20260525-093832\checkpoint-4
venv\Scripts\python.exe scripts\evaluate_translation.py --config configs\evaluation\generation_report.json --input data\review\inference\test\run-full-10k-corrected-v1\test_generated.csv --report-dir data\review\evaluation\test_report\run-full-10k-corrected-v1 --checkpoint fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-full-10k-corrected-v1\checkpoint-10000
```

학습 notebook에서는 언어 컬럼을 NLLB 코드로 변환합니다.

```text
zh-CN -> zho_Hans
zh-TW -> zho_Hant
en    -> eng_Latn
ja    -> jpn_Jpan
ko    -> kor_Hang
```

Notebook은 실험 기록으로 보존합니다. T&N+R 관련 notebook은 deprecated historical experiments로 취급합니다. 각 notebook의 목적, 순서, 의존성 상태는 `docs/notebooks/inventory.md`를 참고하세요.

현재 용어 보호 로직은 `src/longtu_translation_pipeline/text_protection.py`로 분리했습니다. 이 모듈은 단일 `<start>...<end>` marker만 사용하며, 기존 이중 용어 marker와 code-id 보호는 현재 engineering mainline에서 폐기되었습니다. 이번 단계에서는 notebook이 이 모듈을 import하도록 다시 쓰지 않고, 실험 기록으로 유지합니다.

## 더 큰 모델 (1.3B / 3.3B)

NLLB-200에는 더 큰 베이스(`nllb-200-1.3B`, `nllb-200-3.3B`)도 있습니다. 더 큰 dense MT 모델은 일반적으로 품질이 좋아지지만(체감 수익은 점차 감소) **보장되지는 않으며**, 본 프로젝트의 파인튜닝된 zh-CN → ko 작업에서 1.3B/3.3B를 **벤치마크하지 않았으므로** 예상 품질 향상 수치는 제시하지 않습니다. 다만 비용은 예측 가능합니다.

| | 600M (현재) | 1.3B | 3.3B |
| --- | --- | --- | --- |
| 파라미터 | ~0.6B | ~1.3B (~2.1×) | ~3.3B (~5.4×) |
| 추론 지연 (dense, 파라미터에 비례) | 1× | ~2.1× | ~5.4× |
| 전체 파인튜닝 VRAM (AdamW, mixed precision) | 16 GB에 적합 (본 프로젝트는 RTX 4070 Ti SUPER에서 ~14.9 GB 사용) | ~21 GB — 16 GB 초과 | ~53 GB — 단일 16 GB GPU를 크게 초과 |

여기서 사용한 16 GB GPU에서는 메모리 절약 기법(gradient checkpointing, 8-bit optimizer, LoRA, offload) 없이는 **1.3B 전체 파인튜닝이 들어가지 않으며**, **3.3B는 더 큰 GPU 또는 다중 GPU가 필요합니다**. 현재 `num_beams=4` 기본값(이미 greedy의 ~4×)과 합치면 3.3B 추론은 원래 600M greedy 비용의 약 ~21× 수준이 됩니다.

출처: 파라미터 수와 ~17.6 GB 디스크 3.3B checkpoint 크기는 Hugging Face 모델 카드([600M](https://huggingface.co/facebook/nllb-200-distilled-600M), [1.3B](https://huggingface.co/facebook/nllb-200-distilled-1.3B), [3.3B](https://huggingface.co/facebook/nllb-200-3.3B))에서 가져왔고, VRAM 수치는 본 프로젝트의 600M 실측(`run_manifest.json`)과 표준 AdamW 메모리 산정(가중치 + 그래디언트 + optimizer state 기준 ~16 bytes/파라미터)에 근거합니다.

## 아키텍처와 리팩터링 문서

장기 리팩터링 TODO는 README에서 관리하지 않습니다. 다음 문서를 참고하세요.

- [리팩터링 backlog](docs/refactor/backlog.md)
- [후속 작업 (병렬 트랙 맵)](docs/refactor/follow-up-tasks.md)
- [리팩터링 결정 기록](docs/refactor/decisions.md)
- [Notebook inventory](docs/notebooks/inventory.md)
- [AI/Codex 작업 규칙](AGENTS.md)
