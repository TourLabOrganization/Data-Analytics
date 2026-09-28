# Tour Navigator 통합 코드집

버전 **integrated 5.0**. 설문 문항 → C 유형 → 테마·지역 시티투어 점수 → 체류·일정 검증과 CSV 기반 PCA·코사인 분석을 함께 제공합니다. 지출업종 분류 S/SC는 제거했고 지역별 지출 설명 모델 M은 유지했습니다.

## 먼저 실행

Python 3.10+와 Node.js 18+가 필요합니다. 검증 환경은 Python 3.12.14입니다. 분석 패키지만 설치하려면:

```bash
python -m pip install -r analysis/requirements.txt
python analysis/run_analysis.py
python run_session.py examples/full_session.json
npm test --prefix tour_scoring
```

포함된 분석 결과를 그대로 사용하면 두 번째 명령을 건너뛰고 세션 예제부터 실행할 수 있습니다. 다른 위치의 분석 결과를 쓰려면 `python run_session.py example.json --run-dir /path/to/run_...`로 지정하세요. 노트북은 `analysis` 폴더에서 `Tour_Navigator_Integrated.ipynb`를 열고 **Run All** 합니다. Jupyter 실행 프로그램은 사용하는 환경에 별도로 설치해야 합니다. `execute_notebook.py`는 Jupyter 커널 없이 모든 코드 셀을 순차 실행해 출력이 담긴 ipynb로 저장하는 보조 도구입니다.

## 코드 구성

| 폴더 또는 파일 | 역할 |
|---|---|
| docs | 40쪽 Word 및 같은 내용의 Markdown, 그림 리소스 |
| survey/question_score_dictionary.csv | 모든 Q 선택지와 C1~C10 점수의 기계 판독 사전 |
| survey/survey_form.md | Q1~Q14와 신규 H·D·코사인 설문, 저장값 안내 |
| tour_scoring/src | 원본 추출과 v2·v3·v4의 Node.js 실행 엔진 |
| tour_scoring/reference | 지정 GitHub 커밋과 APP.zip의 보관 원본 |
| analysis | CSV 입력, PCA·구면 코사인, 지역 지출 설명 회귀, 전국 해양 분석 |
| run_session.py | v4와 독립 코사인 점수의 통합 실행 진입점 |
| examples/full_session.json | 실제 응답자가 아닌 가상 검증 예제 |
| session_results | v4·체류 JSON, 코사인 179후보와 지역대표 5개, 요약 |
| age_upgrade | 연령 Top30 원자료·전처리·A 군집과 가산 근거 |
| demographic_upgrade | 성별·연령 주변비율 원자료·전처리·R 군집 |
| hallyu_preprocessed_csv | 한류 요약본의 8개 전처리 CSV와 출처 메타데이터 |
| verification | 실행 검사와 코드·문서 대조 결과 |

## 입력 교체

1. `analysis/tour-places.csv`와 `citytour.csv`는 포함한 열 이름 또는 명시된 별칭을 유지합니다. 첫 설정 셀의 경로도 수정할 수 있습니다.
2. 지역 지출은 `spending_csv/spend_region.csv`의 **지역별 비율 4열**만 읽습니다. 업종·월별 지출 CSV는 입력에 넣지 않습니다.
3. 해양 CSV는 `marine_csv`에 둡니다. 새 파일에서는 `source_registry.json`의 이전 해시·범위 선언을 그대로 사용하지 않습니다.
4. 실제 코사인 설문은 `survey_responses_template.csv` 열을 유지해 `analysis/survey_responses.csv`로 저장합니다. 파일이 없으면 **가상 응답 4개**임을 표시한 결과를 만듭니다.
5. 기존 C·H·D 설문과 체류는 `examples/full_session.json` 형태의 JSON을 별도로 입력합니다. Q 번호와 선택값은 0 기반입니다. 성별은 `male`, `female`, `unspecified` 또는 null입니다.

CSV 교체는 해당 분석을 재학습합니다. 기존 v4의 테마 구성비·연령 연결 JSON까지 자동 갱신하는 배포 파이프라인은 아닙니다. 원자료를 바꿀 때에는 해당 prepare 스크립트와 연결 검토 과정을 거쳐야 합니다.

## 두 추천 점수의 의미

- 기존 경로: C 유형과 범주 적합도, Q4, 지역·한류·연령 근거를 더한 원본 척도입니다. 원본 시티투어 파서는 중복 분류가 가능하여 1보다 큰 점수가 나옵니다.
- 코사인 경로: 별도 5문항 0~5 정수 벡터와 신규 파서의 코스 비중을 비교한 **100 × cosine × coverage**입니다.
- `score_fusion=false`이며 두 척도를 임의 합산하지 않습니다. 군집 번호는 순위나 개인 성격이 아닙니다.
- 검증되지 않은 장소 연결은 잠정으로 표시합니다. 실제 280코스 콘텐츠 관련성은 미매핑으로 H=0입니다. 운영 가능성은 `false`이며 예약 확정이 아닙니다.

## 보조 분석 재실행

```bash
python age_upgrade/run_age_clustering.py
python demographic_upgrade/analyze_demographics.py
```

위 명령은 동봉한 전처리 결과에서 A와 R을 재생성합니다. 원자료부터는 각 폴더의 `prepare_age_data.py`, `prepare_demographics.py`를 사용하되 원래 스냅숏 입력에 맞춘 행 수 검사와 매핑 규칙을 확인해야 합니다. 한글 PNG에는 맑은 고딕·Noto Sans CJK KR·Droid Sans Fallback 중 사용 가능한 폰트를 씁니다.

## 검증한 범위

주 분석 폴더 1개에서 **PNG 41개, 결과 CSV 92개**를 생성했습니다. 원자료와 A·R·세션 결과는 이 수에 포함되지 않습니다. 노트북 코드 셀 19개를 새 Python 프로세스에서 실행했습니다. 실제 Jupyter 소켓 커널 환경까지 시험한 것은 아닙니다. 원본 테마 비교 610건(정상 491, 원본 예상 오류 119), 코스 비교 186건, 확장 기능 검사 39+22+30개가 통과했습니다.

전체 명세서는 `docs/Tour_Navigator_Integrated_Specification.md`를 보세요. 하위 폴더의 기존 README는 모듈별 작성 당시 설명이며 현재 통합 구성·개수·정책은 이 README와 통합 명세서를 기준으로 합니다. 운영 앱은 변경·배포하지 않았습니다.
