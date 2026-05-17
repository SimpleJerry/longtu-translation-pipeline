# LongtuKorea Translation Model

[한국어](README.md) | [English](README.en.md) | [中文](README.zh-CN.md)

LongtuKorea의 게임 현지화 번역 모델 실험 저장소입니다. 현재 저장소는 중국어 간체(`zh-CN`)에서 한국어(`ko`)로 번역하는 NLLB 기반 파인튜닝 흐름을 중심으로, 용어집 매칭, 코드/태그 보호, 번역 결과 생성, BLEU 및 용어 보존 평가를 함께 다룹니다.

이 문서는 현재 저장소의 실제 상태를 정리하기 위한 문서입니다. 아직 패키지화된 제품 코드라기보다 데이터 처리 스크립트와 연구용 notebook이 함께 있는 실험 저장소에 가깝습니다.

## 현재 범위

- 다국어 Excel 원본 데이터를 정리하고 언어 쌍별 CSV로 병합합니다.
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
├── glossary_all.xlsx
├── data/
│   ├── data-cleaning-and-merging.py
│   └── input/
│       ├── 盾勇/
│       └── 스크립트(열강,검마,WOG)/
├── tests/
│   └── BLEU-score-calculating.ipynb
├── nllb-fine-tune_all.ipynb
├── T&N method.ipynb
├── T&N method_modified.ipynb
├── T&N+R preprocess.ipynb
├── T&N+R method.ipynb
├── model-generation.ipynb
├── model-generation-manual.ipynb
├── special_token_test.ipynb
├── return code tokens.ipynb
├── tag.ipynb
└── train_eval_loss_picture.ipynb
```

## 주요 파일

| 파일 | 역할 |
| --- | --- |
| `data/data-cleaning-and-merging.py` | 여러 Excel 파일과 시트를 읽어 표준 언어 컬럼으로 정리하고, 전체 병합 파일과 언어 쌍별 CSV를 생성합니다. |
| `data/input/` | 원본 게임 스크립트와 용어집 Excel 파일입니다. |
| `glossary_all.xlsx` | 중국어-한국어 용어집 실험에 쓰이는 통합 용어 데이터입니다. |
| `nllb-fine-tune_all.ipynb` | NLLB 모델 파인튜닝 기본 흐름입니다. |
| `T&N method.ipynb` | Terminology and Notation 방식의 용어 특수 토큰 실험입니다. |
| `T&N+R preprocess.ipynb` | 용어 및 코드 보호를 포함한 전처리 실험입니다. |
| `T&N+R method.ipynb` | Terminology, Notation and Return-code 보호를 함께 적용한 학습 실험입니다. |
| `model-generation.ipynb` | 파인튜닝 모델로 번역 결과를 생성합니다. |
| `model-generation-manual.ipynb` | 특수 토큰을 보존한 수동 디코딩 방식의 번역 결과 생성 실험입니다. |
| `tests/BLEU-score-calculating.ipynb` | 생성 결과와 reference 번역의 BLEU 점수를 계산합니다. |
| `train_eval_loss_picture.ipynb` | 학습 로그에서 train/eval loss 그래프를 생성합니다. |

## 실행 환경

권장 환경은 Windows 또는 Linux의 Python 가상환경입니다. GPU 학습을 기준으로 `requirements.txt`에는 CUDA 11.8 계열 PyTorch가 고정되어 있습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
jupyter lab
```

참고:

- `torch==2.0.1+cu118` 설치가 실패하면 PyTorch CUDA 11.8 wheel 인덱스를 따로 지정해야 할 수 있습니다.
- BLEU notebook은 `nltk.translate.bleu_score`를 사용합니다. 환경에 `nltk`가 없으면 별도로 설치해야 합니다.
- 큰 모델, 학습 결과, 번역 결과, 전처리 출력은 `.gitignore`에 의해 제외됩니다.

## 기본 워크플로

1. 원본 Excel 파일을 `data/input/` 아래에 배치합니다.
2. 데이터 병합 스크립트를 `data/` 디렉터리에서 실행합니다.

```powershell
cd data
python data-cleaning-and-merging.py
```

3. 생성되는 주요 산출물을 확인합니다.

```text
data/output/
data/all_files_merged.xlsx
data/all_files_merged.csv
data/output/all_files_merged_zh-CN_ko.csv
```

4. 학습 notebook에서 언어 컬럼을 NLLB 코드로 변환합니다.

```text
zh-CN -> zho_Hans
zh-TW -> zho_Hant
en    -> eng_Latn
ja    -> jpn_Jpan
ko    -> kor_Hang
```

5. `T&N method.ipynb` 또는 `T&N+R method.ipynb`에서 용어/코드 보존 전처리와 파인튜닝을 실행합니다.
6. `model-generation.ipynb` 또는 `model-generation-manual.ipynb`로 번역 결과를 생성합니다.
7. BLEU, 용어 보존율, 코드 보존율 notebook으로 품질을 확인합니다.

## 아키텍처와 리팩터링 문서

장기 리팩터링 TODO는 README에서 관리하지 않습니다. 다음 문서를 참고하세요.

- [리팩터링 backlog](docs/refactor/backlog.md)
- [리팩터링 결정 기록](docs/refactor/decisions.md)
- [AI/Codex 작업 규칙](AGENTS.md)
