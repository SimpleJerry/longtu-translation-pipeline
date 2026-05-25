# LongtuKorea Translation Model

[한국어](README.md) | [English](README.en.md) | [中文](README.zh-CN.md)

LongtuKorea의 게임 현지화 번역 모델 실험 저장소입니다. 현재 저장소는 중국어 간체(`zh-CN`)에서 한국어(`ko`)로 번역하는 NLLB 기반 파인튜닝 흐름을 중심으로, 용어집 매칭, 번역 결과 생성, BLEU 및 용어 보존 평가를 함께 다룹니다.

이 문서는 현재 저장소의 실제 상태를 정리하기 위한 문서입니다. 아직 패키지화된 제품 코드라기보다 데이터 처리 스크립트와 연구용 notebook이 함께 있는 실험 저장소에 가깝습니다.

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
│   ├── evaluate_translation.py
│   ├── segments_cleaning_pipeline.py
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
| `scripts/evaluate_translation.py` | BLEU와 glossary preservation을 계산하는 번역 결과 평가 CLI이며 모델을 로드하지 않습니다. |
| `scripts/segments_cleaning_pipeline.py` | 로컬 segments semantic 정제 pipeline이며 기본적으로 dry-run review를 생성합니다. |
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
| `requirements-training.txt` | RF-006 학습 smoke test 및 이후 학습 chain 의존성입니다. |

## 실행 환경

권장 환경은 Windows 또는 Linux의 Python 가상환경입니다. `requirements.txt`에는 실제로 사용 중인 로컬 semantic cleaning 의존성과 CUDA 13.2 계열 PyTorch가 기록되어 있습니다. 기본 CLI, dry-run, 테스트, RF-007 evaluation은 대부분 표준 라이브러리만 사용하므로 모든 workflow가 전체 의존성을 필요로 한다는 뜻은 아닙니다. `requirements-training.txt`에는 RF-006 학습 smoke test 및 이후 학습 chain 의존성을 기록하며, 현재는 `transformers`, `tokenizers`, `accelerate`, `sentencepiece`와 직접 실행 의존성을 포함합니다. `datasets`는 아직 현재 최소 chain에 포함하지 않습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
jupyter lab
```

RF-006-P2 이후 학습/inference chain을 실행하려면 학습 chain 의존성도 설치합니다.

```powershell
python -m pip install -r requirements-training.txt
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

본문 말뭉치 정제를 확인하거나 반복하려면 먼저 dry-run을 실행합니다.

```powershell
venv\Scripts\python.exe scripts\segments_cleaning_pipeline.py --dry-run
```

이 pipeline은 먼저 `<c=...>` 같은 표현용 스타일 태그를 제거하고 대칭 외부 wrapper를 푼 뒤, Stanza, jieba, kiwipiepy, `BAAI/bge-m3`로 term/entity-like segment를 점수화합니다. Placeholder 행은 기본적으로 보존하고 mismatch만 감사합니다. 이 명령은 `data/segments.csv`를 다시 쓰지 않고 로컬 `data/review/segments/` 아래에 감사 CSV만 생성합니다. 수동 확인 후에만 `--apply`를 사용합니다.

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

학습/추론 engineering entry point는 현재 RF-006 smoke-test/pilot/formal-run hardening 단계입니다. dry-run은 설정 읽기, 데이터 검증, 결정적인 train/validation/test 계획만 수행합니다. RF-006-P7은 ignored `fine-tuned-models/.../runs/run-*` 아래에 고정 split artifact와 `run_manifest.json`을 작성합니다. RF-006-P10은 formal experiment split을 seed `42`의 8:1:1로 수정합니다. validation은 학습 중 eval/checkpoint 관찰에만 쓰고, 최종 성능 보고는 held-out test split만 사용합니다. RF-006-P8은 고정 validation split에서 translation CSV를 만들고, `--generate-test`는 고정 test split에서 최종 평가 CSV를 만듭니다. P4/P5/P6/P7/P8/P2는 full training을 명시적으로 시작하기 전까지 engineering chain 검증입니다.

```powershell
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --dry-run
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --smoke-test
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --nllb-smoke-test --smoke-rows 2
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --real-model-smoke-test --smoke-rows 2
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --pilot-train --pilot-rows 64 --max-steps 4 --save-steps 2
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --train --limit-rows 128 --max-steps 4 --save-steps 2 --save-total-limit 2 --logging-steps 1
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --train --run-dir fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-name --resume-from-checkpoint latest --max-steps 6 --save-steps 2 --save-total-limit 2 --logging-steps 1
venv\Scripts\python.exe scripts\train_model.py --config configs\training\full_10k.json --train --run-name run-full-10k-corrected-v1
venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --dry-run
venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --generate --model-path fine-tuned-models\nllb-200-distilled-600M\zh2ko\pilot\run-20260525-093832\checkpoint-4 --sample-rows 8
venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --generate-validation --run-dir fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-name
venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --generate-test --run-dir fine-tuned-models\nllb-200-distilled-600M\zh2ko\runs\run-full-10k-corrected-v1
```

기존 번역 결과 CSV를 평가하려면 RF-007 평가 entry point를 사용합니다. 입력은 notebook의 기존 출력 컬럼인 `source`, `references`, `candidates`를 사용합니다. BLEU는 기본적으로 한국어 공백 단위 토큰화를 사용하며, glossary preservation은 후보 번역에서 `<start>...<end>` marker를 제거한 뒤 한국어 용어가 포함되었는지 검사합니다. 모델이 빈 `candidates`를 생성한 경우 report를 중단하지 않고 `empty_candidate_rows`로 기록합니다.

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

## 아키텍처와 리팩터링 문서

장기 리팩터링 TODO는 README에서 관리하지 않습니다. 다음 문서를 참고하세요.

- [리팩터링 backlog](docs/refactor/backlog.md)
- [리팩터링 결정 기록](docs/refactor/decisions.md)
- [Notebook inventory](docs/notebooks/inventory.md)
- [AI/Codex 작업 규칙](AGENTS.md)
