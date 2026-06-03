# ㈜룽투코리아 게임 현지화 번역 파이프라인

[한국어](README.md) | [English](README.en.md) | [中文](README.zh-CN.md)

이 저장소는 저자가 ㈜룽투코리아(LONGTU KOREA Inc., 현 ㈜스타코링크 / STACO LINK Co., Ltd.) 시스템 엔지니어로 재직할 당시 수행한 게임 현지화 번역 파이프라인의 재현물입니다. 원래 형태는 일련의 Jupyter Notebook 파일이었으며, 대부분 실험의 중간 과정 파일이었습니다. 이후 Claude Code와 Codex를 활용해 점진적으로 재구성하여 현재와 같은 재현 가능한 파이프라인으로 정리했습니다.

프로젝트의 배경은 다음과 같습니다. ㈜룽투코리아(현 ㈜스타코링크)는 자사 게임을 한국 시장에 서비스하면서 대량의 중국어 텍스트를 한국어로 현지화해야 하는 수요가 있었으며, 매년 수천만 원에 달하는 번역 외주 비용이 발생하고 있었습니다. 이에 회사가 보유한 게임 말뭉치를 기반으로 NLLB 모델을 파인튜닝하고, 소량의 인간 검수를 보조로 삼아 번역 자동화를 구축하는 것을 목표로 했습니다.

현재 저장소는 중국어 간체(`zh-CN`)에서 한국어(`ko`)로 번역하는 NLLB 기반 파인튜닝 흐름을 중심으로, 용어집 매칭, 번역 결과 생성, BLEU 및 용어 보존 평가를 함께 다룹니다.

## 프로젝트 현황 및 결과

이 저장소는 재현 가능한 zh-CN → ko 파인튜닝 파이프라인과 학습·평가가 완료된 모델을 모두 포함합니다.

- **데이터 정제** — 중국어 간체-한국어 병렬 말뭉치와 게임 용어집을 체계적으로 정제했습니다. 로컬 semantic pipeline(Stanza / jieba / kiwipiepy / wordfreq / `BAAI/bge-m3`)을 이용한 glossary 정제, markup/wrapper 정규화·target 언어 오염 제거를 포함한 segment 정제, glossary-segment 교차 일관성 검사까지 수행했습니다. 최종적으로 전량 cloud LLM(OpenAI Batch API)을 통해 corpus 품질을 추가 검증했습니다.
- **파인튜닝 및 학습** — `facebook/nllb-200-distilled-600M`을 기반으로 게임 번역 corpus를 파인튜닝했습니다. 결정적 8:1:1 split(seed 42)과 early-stopping으로 복합 품질 지표 기준 최선 checkpoint를 자동 선택합니다.
- **평가** — held-out test split에서 BLEU + chrF + glossary preservation(exact & no-space)을 측정했습니다.
- **추론** — 학습된 checkpoint를 사용하여 새로운 중국어 텍스트를 한국어로 번역하고 결과를 CSV로 내보내는 추론 CLI를 구축했습니다.

**현재 모델.** early-stopping run의 `checkpoint-48000`, beam search(`num_beams=4`) 디코딩. held-out test split(seed 42, 학습 및 checkpoint 선택에서 미사용):

| 지표 | 점수 |
| --- | --- |
| BLEU (공백 단위) | 0.325 |
| chrF (max_n=6, β=2) | 0.590 |
| Glossary preservation (no-space) | 0.954 |
| Glossary preservation (exact) | 0.950 |

**능력 단계표** (동일한 test split, 전 단계 beam=4):

| 단계 | BLEU | chrF | Preservation (no-space) |
| --- | --- | --- | --- |
| Base NLLB-600M *(파인튜닝 전 기준선 — marker 없음)* | 0.009 | 0.226 | 0.323 |
| Fine-tuned `checkpoint-48000`, beam=4 **(현재 모델)** | **0.325** | **0.590** | **0.954** |

![Base vs. Fine-tuned NLLB-200 성능 비교](docs/figures/capability_comparison.png)

파인튜닝 + 데이터 정제의 순 효과: 동일한 beam=4 디코딩 기준 **+0.316 BLEU (~34×)**; glossary preservation이 ~32%에서 ~95%로 상승했습니다. Base 모델은 유창하게 들리는 한국어를 생성하지만 게임 특유 용어와 캐릭터 이름을 완전히 놓칩니다. 파인튜닝과 데이터 정제가 합쳐서 전체 차이를 설명합니다.

## 현재 범위

- 저장소에는 최종 학습 말뭉치와 용어집만 보관하며, 민감한 raw Excel/CSV 입력은 커밋하지 않습니다.
- 로컬 semantic pipeline으로 중국어-한국어 게임 용어집을 정제합니다.
- `facebook/nllb-200-*` 계열 모델을 기반으로 게임 번역 데이터를 파인튜닝합니다.
- 번역 중 용어집 항목을 표시하기 위해 단일 `<start>...<end>` 특수 토큰 형태를 사용합니다.
- T&N+R 및 code-id code/tag 보호는 역사적 실험으로만 보관하며 현재 주 흐름에서는 사용하지 않습니다.
- 번역 결과를 Excel/CSV로 내보내고 BLEU와 용어 보존율을 평가합니다.

## 기술 배경

**용어 marker (`<start>...<end>`) 방법론.** 번역 시 게임 용어를 보존하기 위해 source 측 용어 주입(source-side terminology injection) 방식을 사용합니다. Dinu et al. (ACL 2019) *"Training Neural Machine Translation to Apply Terminology Constraints"*에 기반하며, source 중국어 텍스트에서 glossary와 매칭되는 부분을 `<start>...<end>` 특수 토큰 쌍으로 감싼 뒤 해당 형태로 학습시킵니다. 이를 통해 모델은 target 한국어에 해당 용어를 자연스럽게 재현하는 soft constraint를 학습합니다. decode 시점에 토큰을 강제 삽입하는 hard constrained decoding과 달리 번역 유창성을 유지하며, 단일 marker 형태를 채택해 tokenizer 확장을 최소화합니다.

**평가 지표.** BLEU(Papineni et al., 2002)는 n-gram 정밀도 기반 표준 MT 지표입니다. Google Cloud Translate의 [BLEU 해석 기준](https://cloud.google.com/translate/docs/advanced/bleu-scores)에 따르면 0.30~0.40 범위는 "이해 가능~양호한 번역(Understandable to good translations)"에 해당하며, 본 모델의 0.325는 이 구간에 속합니다. 단, 형태소가 풍부한 한국어에서는 공백 단위 토큰화가 번역 품질을 과소평가할 수 있으므로 chrF(character n-gram F-score, Popović 2015)를 함께 보고합니다. chrF는 어미·접사 변화가 많은 한국어에서 인간 판단과 더 높은 상관관계를 보입니다. 도메인 특유 지표인 glossary preservation은 용어집 항목의 출현 여부를 직접 측정하며, exact match와 no-space match를 함께 보고해 띄어쓰기 불일치를 실제 용어 누락으로 오판하는 것을 방지합니다.

**과적합 방지.**

1. **Early stopping** — validation split에서 BLEU + chrF + glossary preservation 복합 점수를 관찰하며 개선이 없으면 학습을 조기 종료하고 최선 checkpoint를 자동 선택합니다.
2. **결정적 8:1:1 데이터 분할** — seed 42로 고정해 train/validation/test를 나누며, test split은 최종 보고에만 한 번 사용합니다. checkpoint 선택에 test split을 쓰지 않아 정보 누출을 차단합니다.
3. **데이터 정제 품질 게이트** — 오염 row·불일치 용어가 많으면 노이즈가 과적합 신호로 작용하므로, strict gate를 통과한 corpus만 학습에 사용합니다.

## 저장소 구조

```text
.
├── README.md
├── README.en.md
├── README.zh-CN.md
├── CLAUDE.md
├── .env.example
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
│   ├── cleanup_common.py
│   ├── llm_common.py
│   ├── glossary_semantic_pipeline.py
│   ├── glossary_llm_cleanup_pipeline.py
│   ├── evaluate_translation.py
│   ├── segments_cleaning_pipeline.py
│   ├── segments_llm_cleanup_pipeline.py
│   ├── segments_glossary_cross_cleaning_pipeline.py
│   ├── sweep_inference_params.py
│   ├── run_inference.py
│   ├── train_model.py
│   └── plot_training_loss.py
├── src/
│   └── longtu_translation_pipeline/
├── tests/
└── docs/
    ├── architecture/data-cleaning-pipeline.md
    └── notebooks/inventory.md
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
| `configs/training/default.json` | smoke/dry-run용 기본 학습 설정. 데이터 경로, 언어 코드, 모델명, 출력 디렉터리, 기본 파라미터를 선언합니다. |
| `configs/training/step10k.json` | 10k step full-data 학습 profile. step, checkpoint, eval, optimizer 설정을 명시합니다. |
| `configs/training/earlystop.json` | Early-stopping 학습 profile. 현재 최종 모델(`checkpoint-48000`)을 생성한 설정입니다. |
| `configs/inference/default.json` | 추론 설정. 모델 경로, 입력/출력 경로, 언어 코드, 생성 파라미터를 선언합니다. |
| `configs/evaluation/default.json` | 평가 설정. 번역 결과 CSV, glossary, BLEU 설정, 로컬 보고서 출력 위치를 선언합니다. |
| `scripts/cleanup_common.py` | segment/glossary 정제 pipeline이 공유하는 공통 유틸리티 함수입니다. |
| `scripts/llm_common.py` | OpenAI-compatible Chat Completions API 호출 공통 client 모듈입니다. |
| `scripts/sweep_inference_params.py` | beam width 등 추론 파라미터를 sweep해 최선 설정을 탐색하는 CLI입니다. |
| `scripts/glossary_semantic_pipeline.py` | Stanza, jieba, kiwipiepy, wordfreq, `BAAI/bge-m3`를 사용하는 로컬 glossary semantic 정제 pipeline입니다. |
| `scripts/glossary_llm_cleanup_pipeline.py` | Cloud OpenAI-compatible glossary aggressive cleanup entry point입니다. 용어 삭제만 허용하고 로컬 ignored review를 작성합니다. |
| `scripts/evaluate_translation.py` | BLEU와 glossary preservation을 계산하는 번역 결과 평가 CLI이며 모델을 로드하지 않습니다. |
| `scripts/segments_cleaning_pipeline.py` | 로컬 segments semantic 정제 pipeline이며 기본적으로 dry-run review를 생성합니다. |
| `scripts/segments_llm_cleanup_pipeline.py` | Cloud OpenAI-compatible segments 전체 정제 entry point입니다. 한국어 rewrite는 로컬 검증을 통과한 경우에만 적용합니다. |
| `scripts/segments_glossary_cross_cleaning_pipeline.py` | glossary/segments 교차 정제 CLI이며 고신뢰 용어 충돌 행을 제거하고 로컬 review를 생성합니다. |
| `scripts/train_model.py` | 설정 dry-run, 로컬 tiny tokenizer smoke, 실제 tokenizer + tiny Trainer smoke, 실제 NLLB model 1-step smoke, pilot training, formal run-directory training을 지원하는 학습 CLI입니다. |
| `scripts/run_inference.py` | 추론 CLI입니다. 설정 dry-run과 실제 checkpoint 기반 sample generation을 지원합니다. |
| `scripts/plot_training_loss.py` | `trainer_state.json`으로부터 훈련/평가 손실 곡선을 그리는 CLI입니다. `--output`으로 파일 저장 가능합니다. |
| `src/longtu_translation_pipeline/text_protection.py` | 테스트 가능한 용어 marker 보호 pure-function 모듈입니다. |
| `src/longtu_translation_pipeline/training_metrics.py` | 학습 중 복합 품질 지표 계산 및 best checkpoint 선택 로직입니다. |
| `src/longtu_translation_pipeline/config.py` | 학습/추론 JSON 설정을 dataclass로 파싱하고 검증합니다. |
| `src/longtu_translation_pipeline/training.py` | import 가능한 학습 데이터 준비 및 Trainer 연결 API입니다. |
| `src/longtu_translation_pipeline/inference.py` | import 가능한 추론 입력 계획 dry-run API입니다. |
| `src/longtu_translation_pipeline/evaluation.py` | import 가능한 BLEU와 glossary preservation 평가 API입니다. |
| `docs/notebooks/inventory.md` | 2023년 실험 Notebook의 시간순 흐름, 목적 및 퇴역 기록입니다. 원본 Notebook 파일은 git 태그 `notebooks-retire`로 조회할 수 있습니다. |
| `docs/architecture/data-cleaning-pipeline.md` | 스타일 태그, 구조화 문자열, 짧은 조각, target 오염, strict gate 예시를 포함한 데이터 정제 규칙 설명입니다. |
| `requirements-training.txt` | 학습 chain 의존성. transformers, accelerate, sentencepiece, CUDA PyTorch를 포함합니다. |

## 실행 환경

Python 가상환경(Windows 또는 Linux)을 권장합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt           # 데이터 정제·평가
pip install -r requirements-training.txt  # 학습·추론 시 추가 설치 (CUDA 13.2 PyTorch 포함)
```

Stanza 언어 모델, Hugging Face 캐시, 학습 결과물, raw 데이터는 `.gitignore`에 의해 Git에서 제외됩니다.

## 기본 워크플로

학습 데이터 진입점은 두 개의 최종 CSV입니다. raw Excel/CSV 파일은 커밋하지 않습니다.

- `data/segments.csv` — 중국어-한국어 병렬 말뭉치
- `data/glossary.csv` — 게임 용어집

**Glossary 정제** — 먼저 Stanza 모델을 내려받은 뒤 로컬 pipeline을 실행합니다.

```powershell
$env:STANZA_RESOURCES_DIR="D:\longtu-translation-pipeline\venv\stanza_resources"
venv\Scripts\python.exe -c "import stanza; stanza.download('zh', model_dir=r'D:\longtu-translation-pipeline\venv\stanza_resources'); stanza.download('ko', model_dir=r'D:\longtu-translation-pipeline\venv\stanza_resources')"
$env:HF_HOME="D:\longtu-translation-pipeline\venv\hf_cache"
venv\Scripts\python.exe scripts\glossary_semantic_pipeline.py
```

로컬 규칙만으로 부족할 때는 cloud LLM delete-only cleanup을 추가로 실행합니다.

```powershell
$env:OPENAI_API_KEY="<your-key>"; $env:LLM_MODEL="<your-model>"
venv\Scripts\python.exe scripts\glossary_llm_cleanup_pipeline.py --apply
```

**Segment 정제** — dry-run으로 확인 후 apply합니다. 학습 전에는 반드시 strict-check를 통과해야 합니다.

```powershell
venv\Scripts\python.exe scripts\segments_cleaning_pipeline.py --dry-run
venv\Scripts\python.exe scripts\segments_cleaning_pipeline.py --apply
venv\Scripts\python.exe scripts\segments_glossary_cross_cleaning_pipeline.py --strict-check
```

LLM 전체 검수가 필요한 경우:

```powershell
$env:OPENAI_API_KEY="<your-key>"; $env:LLM_MODEL="<your-model>"
venv\Scripts\python.exe scripts\segments_llm_cleanup_pipeline.py --dry-run
# 확인 후: venv\Scripts\python.exe scripts\segments_llm_cleanup_pipeline.py --apply
```

각 정제 유형의 상세 예시와 규칙은 [docs/architecture/data-cleaning-pipeline.md](docs/architecture/data-cleaning-pipeline.md)를 참고하세요.

**학습** — `earlystop.json`을 사용합니다(결정적 8:1:1 split, seed 42, early-stopping).

```powershell
venv\Scripts\python.exe scripts\train_model.py --config configs\training\earlystop.json --train --run-name <run-name>
```

빠른 검증용 smoke/dry-run:

```powershell
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --dry-run
venv\Scripts\python.exe scripts\train_model.py --config configs\training\default.json --nllb-smoke-test --smoke-rows 2
```

**추론** — 학습된 run 디렉터리를 지정합니다.

```powershell
venv\Scripts\python.exe scripts\run_inference.py --config configs\inference\default.json --generate-test --run-dir <run-dir>
```

**평가** — 생성된 CSV를 입력합니다. BLEU, chrF, glossary preservation을 한 번에 보고합니다.

```powershell
venv\Scripts\python.exe scripts\evaluate_translation.py --config configs\evaluation\generation_report.json --input <generated-csv>
```

**모델 가져오기 및 배포** — 학습된 모델은 공개 Hugging Face Hub 저장소로 배포됩니다(ADR-0037). 토큰 없이 다운로드 가능합니다.

```python
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

repo = "SimpleJerry/longtu-nllb-zh2ko"
tag  = "earlystop-v1-ckpt48000"  # revision을 고정하여 가져오기

tokenizer = AutoTokenizer.from_pretrained(repo, revision=tag)
model     = AutoModelForSeq2SeqLM.from_pretrained(repo, revision=tag)
```

라이선스: cc-by-nc-4.0 (비상업적 사용만 허용). Docker 배포 방법은 [ADR-0035](docs/decisions/adr/ADR-0035-docker-jenkins-deployment-contract.md) 참고.

**서빙(serving)** — 발행된 체크포인트를 동기 HTTP/JSON 서비스로 제공합니다. 계약은 [ADR-0034](docs/decisions/adr/ADR-0034-serving-contract-synchronous-http-api.md) 참고. 엔드포인트: `POST /translate`, `GET /health`, `GET /info`.

```powershell
venv\Scripts\python.exe scripts\serve.py --dry-run   # 설정만 검증, 모델 미로딩
venv\Scripts\python.exe scripts\serve.py             # 체크포인트 로딩, 127.0.0.1:8000 serve
```

**Docker 배포** — 서비스를 컨테이너화하고 Jenkins CI/CD로 자동 배포합니다. 계약은 [ADR-0035](docs/decisions/adr/ADR-0035-docker-jenkins-deployment-contract.md) 참고. 모델 가중치는 이미지에 포함되지 않으며, 시작 시 공개 HF Hub에서 자동 다운로드됩니다（ADR-0038）. Docker Desktop + WSL2 + NVIDIA CUDA on WSL이 필요합니다.

```bash
# 이미지 빌드
docker build -t longtu-translation-service:latest .

# 토큰 불필요 — 시작 시 공개 HF Hub에서 ~2.3 GB 모델 자동 다운로드 (첫 실행 수 분 소요, 이후 캐시 사용)
docker run -d \
    --gpus all \
    -p 8000:8000 \
    -v longtu_hf_cache:/home/appuser/.cache/huggingface \
    longtu-translation-service:latest
```

로컬 볼륨 마운트 변형（개발/오프라인）은 `configs/serving/docker-localmount.json` 참고.

## 더 큰 모델 (1.3B / 3.3B)

NLLB-200에는 더 큰 베이스(`nllb-200-1.3B`, `nllb-200-3.3B`)도 있습니다. 더 큰 dense MT 모델은 일반적으로 품질이 좋아지지만(체감 수익은 점차 감소) **보장되지는 않으며**, 본 프로젝트의 파인튜닝된 zh-CN → ko 작업에서 1.3B/3.3B를 **벤치마크하지 않았으므로** 예상 품질 향상 수치는 제시하지 않습니다. 다만 비용은 예측 가능합니다.

| | 600M (현재) | 1.3B | 3.3B |
| --- | --- | --- | --- |
| 파라미터 | ~0.6B | ~1.3B (~2.1×) | ~3.3B (~5.4×) |
| 추론 지연 (dense, 파라미터에 비례) | 1× | ~2.1× | ~5.4× |
| 전체 파인튜닝 VRAM (AdamW, mixed precision) | 16 GB에 적합 (본 프로젝트는 RTX 4070 Ti SUPER에서 ~14.9 GB 사용) | ~21 GB — 16 GB 초과 | ~53 GB — 단일 16 GB GPU를 크게 초과 |

여기서 사용한 16 GB GPU에서는 메모리 절약 기법(gradient checkpointing, 8-bit optimizer, LoRA, offload) 없이는 **1.3B 전체 파인튜닝이 들어가지 않으며**, **3.3B는 더 큰 GPU 또는 다중 GPU가 필요합니다**. 현재 `num_beams=4` 기본값(이미 greedy의 ~4×)과 합치면 3.3B 추론은 원래 600M greedy 비용의 약 ~21× 수준이 됩니다.

출처: 파라미터 수와 ~17.6 GB 디스크 3.3B checkpoint 크기는 Hugging Face 모델 카드([600M](https://huggingface.co/facebook/nllb-200-distilled-600M), [1.3B](https://huggingface.co/facebook/nllb-200-distilled-1.3B), [3.3B](https://huggingface.co/facebook/nllb-200-3.3B))에서 가져왔고, VRAM 수치는 본 프로젝트의 600M 실측(`run_manifest.json`)과 표준 AdamW 메모리 산정(가중치 + 그래디언트 + optimizer state 기준 ~16 bytes/파라미터)에 근거합니다.

## 참고 문서

- [아키텍처 결정 기록 (ADR)](docs/decisions/adr/README.md)
- [Notebook inventory](docs/notebooks/inventory.md)
- [에이전트 헌법 (CLAUDE.md)](CLAUDE.md)
