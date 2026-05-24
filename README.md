# LongtuKorea Translation Model

[한국어](README.md) | [English](README.en.md) | [中文](README.zh-CN.md)

LongtuKorea의 게임 현지화 번역 모델 실험 저장소입니다. 현재 저장소는 중국어 간체(`zh-CN`)에서 한국어(`ko`)로 번역하는 NLLB 기반 파인튜닝 흐름을 중심으로, 용어집 매칭, 코드/태그 보호, 번역 결과 생성, BLEU 및 용어 보존 평가를 함께 다룹니다.

이 문서는 현재 저장소의 실제 상태를 정리하기 위한 문서입니다. 아직 패키지화된 제품 코드라기보다 데이터 처리 스크립트와 연구용 notebook이 함께 있는 실험 저장소에 가깝습니다.

## 현재 범위

- 저장소에는 최종 학습 말뭉치와 용어집만 보관하며, 민감한 raw Excel/CSV 입력은 커밋하지 않습니다.
- 로컬 semantic pipeline으로 중국어-한국어 게임 용어집을 정제합니다.
- `facebook/nllb-200-*` 계열 모델을 기반으로 게임 번역 데이터를 파인튜닝합니다.
- 번역 중 용어집 항목을 보존하기 위해 `<start>`, `<middle>`, `<end>` 특수 토큰을 사용합니다.
- 코드, 플레이스홀더, 게임 UI 태그를 보호하기 위해 `<code_id=*>` 형태의 토큰을 실험합니다.
- 번역 결과를 Excel/CSV로 내보내고 BLEU, 용어 보존율, 코드 보존율을 평가합니다.

## 저장소 구조

```text
.
├── README.md
├── README.en.md
├── README.zh-CN.md
├── requirements.txt
├── data/
│   ├── glossary.csv
│   ├── segments.csv
│   └── review/                # 로컬 생성, Git 제외
├── configs/
│   ├── glossary/
│   └── segments/
├── scripts/
│   ├── glossary_semantic_pipeline.py
│   └── segments_cleaning_pipeline.py
├── nllb-fine-tune_all.ipynb
├── T&N method.ipynb
├── T&N method_modified.ipynb
├── T&N+R preprocess.ipynb
├── T&N+R method.ipynb
├── model-generation.ipynb
├── special_token_test.ipynb
├── return code tokens.ipynb
└── train_eval_loss_picture.ipynb
```

## 주요 파일

| 파일 | 역할 |
| --- | --- |
| `data/segments.csv` | `segment_id`, `zh-CN`, `ko` 컬럼만 가진 최종 문장/구간 학습 말뭉치입니다. |
| `data/glossary.csv` | `term_id`, `zh-CN`, `ko` 컬럼만 가진 최종 중국어-한국어 게임 용어집입니다. |
| `data/review/` | 로컬 데이터 정제 감사 CSV와 검토용 산출물이며 기본적으로 커밋하지 않습니다. |
| `configs/glossary/` | glossary 정제에 쓰는 seed, 어휘 목록, 규칙 설정입니다. |
| `configs/segments/` | segment 정제를 위한 구조화 문자열 분리, term/entity seed, semantic 임계값 설정입니다. |
| `scripts/glossary_semantic_pipeline.py` | Stanza, jieba, kiwipiepy, wordfreq, `BAAI/bge-m3`를 사용하는 로컬 glossary semantic 정제 pipeline입니다. |
| `scripts/segments_cleaning_pipeline.py` | 로컬 segments semantic 정제 pipeline이며 기본적으로 dry-run review를 생성합니다. |
| `nllb-fine-tune_all.ipynb` | NLLB 모델 파인튜닝 기본 흐름입니다. |
| `T&N method.ipynb` | Terminology and Notation 방식의 용어 특수 토큰 실험입니다. |
| `T&N+R preprocess.ipynb` | 용어 및 코드 보호를 포함한 전처리 실험입니다. |
| `T&N+R method.ipynb` | Terminology, Notation and Return-code 보호를 함께 적용한 학습 실험입니다. |
| `model-generation.ipynb` | 파인튜닝 모델로 번역 결과를 생성합니다. |
| `train_eval_loss_picture.ipynb` | 학습 로그에서 train/eval loss 그래프를 생성합니다. |

## 실행 환경

권장 환경은 Windows 또는 Linux의 Python 가상환경입니다. `requirements.txt`에는 CUDA 13.2 계열 PyTorch와 로컬 용어집 정제 의존성이 기록되어 있습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
jupyter lab
```

참고:

- Stanza 중국어/한국어 모델과 Hugging Face embedding cache는 로컬 가상환경 아래에 두며 Git에 커밋하지 않습니다.
- BLEU notebook은 `nltk.translate.bleu_score`를 사용합니다. 환경에 `nltk`가 없으면 별도로 설치해야 합니다.
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

학습 notebook에서는 언어 컬럼을 NLLB 코드로 변환합니다.

```text
zh-CN -> zho_Hans
zh-TW -> zho_Hant
en    -> eng_Latn
ja    -> jpn_Jpan
ko    -> kor_Hang
```

`T&N method.ipynb` 또는 `T&N+R method.ipynb`에서 용어/코드 보존 전처리와 파인튜닝을 실행하고, 생성 및 평가 notebook으로 BLEU, 용어 보존율, 코드 보존율을 확인합니다.

## 아키텍처와 리팩터링 문서

장기 리팩터링 TODO는 README에서 관리하지 않습니다. 다음 문서를 참고하세요.

- [리팩터링 backlog](docs/refactor/backlog.md)
- [리팩터링 결정 기록](docs/refactor/decisions.md)
- [AI/Codex 작업 규칙](AGENTS.md)
