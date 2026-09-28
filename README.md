# Tour Navigator Data Analytics

세션에서 작성한 **PCA·코사인 군집화, 설문·유형 점수, 테마·지역 시티투어 추천, 체류 산정, 입력 CSV, 실행 코드·노트북, Word·Markdown 명세서와 결과 그림**을 모았습니다.

현재 추천 기준은 **통합 명세서 6.2 / 분기 설문 6.1**입니다. 주 분석 엔진은 지출업종 분류를 제거한 integrated-5.0을 유지합니다. 데이터·결과는 세션에서 검증한 스냅숏이며, 입력을 교체하면 재학습해야 합니다.

## 바로 보기

| 자료 | 위치 |
|---|---|
| 전체 상세명세서 — 설문, 산식, PCA 축, 코사인, 지역 배정, 여행장소, 체류 | [Markdown](docs/Tour_Navigator_Integrated_Specification.md) · [Word](docs/Tour_Navigator_Cosine_Specification.docx) |
| 최신 설문과 선택지별 가산점 | [설문 MD](survey/Tour_Navigator_Branching_Questionnaire.md) · [점수 사전 CSV](survey/implementation/question_score_map.csv) |
| 응답자용 설문지 | [Word](survey/Tour_Navigator_Survey_Form.docx) · [PNG 6장](survey/survey_png/) |
| CSV → PCA·코사인 군집·표·그림 | [Jupyter Notebook](analysis/Tour_Navigator_Integrated.ipynb) · [동일 분석 Python](analysis/run_analysis.py) |
| 신규 설문 → 유형 → 테마·지역 시티투어 | [추천 코드](reference_calc/recommend_reference.py) · [설문 엔진](reference_calc/score_survey.py) |
| 주 분석 PNG 41개·결과 CSV 92개 | [결과 폴더](analysis/outputs_cosine/run_20260928_062724_468322/) |
| 입력 데이터의 위치·행 수·해시 | [입력 목록](docs/INPUT_DATA_INDEX.md) · [전체 파일 SHA256](verification/release_manifest.csv) |
| 기존 앱·확장 산식 비교와 체류 코드 | [Node.js 코드집](tour_scoring/) · [원본 추적 정보](tour_scoring/PROVENANCE.json) |

## 1. 최신 설문 점수와 추천 실행

Python 3.10 이상 표준 라이브러리만 필요합니다. 저장소 최상위에서 실행하세요.

```bash
python reference_calc/score_survey.py reference_calc/demo_answers.json
python reference_calc/recommend_reference.py reference_calc/demo_answers.json
python reference_calc/verify_reference.py
```

입력은 S1~S6와 S4에 해당하는 B 문항 하나입니다. F1이 필요한 경우에만 후보 C 코드 또는 `BALANCED`를 입력합니다. B1~B7의 **D = 없음**은 모든 유형에 0점을 더하고 기존 점수를 유지합니다. 예제 응답은 가상 데이터입니다.

- 유형: 선택지별 C1~C10 가산점 합계, 최고점과 2점 이내인 유형을 최종 후보로 유지.
- 선호 벡터: 후보의 기존 5범주 프로필을 점수 차이에 따른 가중치로 합성. `q_source=type_profile_prior`이며 개인 선호 실측값이 아님.
- 테마: `100 × (프로필 적합도 + 0.5 × 주요 관심사 항) / 1.5`로 정렬.
- 시티투어: `100 × cosine(선호 벡터, 코스 범주 비중) × 분류 커버리지`로 정렬하고 지역명별 첫 코스를 최대 5개 선택.
- 테마 점수와 코스 점수는 합산하지 않으며, 군집 번호를 추천의 강제 필터로 사용하지 않음.
- 신규 기본 흐름의 지역·한류·연령·성별 별도 가산은 0. 관련 분석 데이터를 자동 가산으로 해석하지 않음.

`reference_calc/eligible_courses.csv`는 적격 179코스 스냅숏입니다. 새 CSV를 학습해도 이 파일은 자동 교체되지 않습니다. 최신 분석 결과와 출처를 검토한 후 갱신해야 합니다.

## 2. CSV부터 분석 재실행

```bash
python -m pip install -r analysis/requirements.txt
python analysis/run_analysis.py
```

Jupyter에서는 `analysis` 폴더에서 [Tour_Navigator_Integrated.ipynb](analysis/Tour_Navigator_Integrated.ipynb)를 열고 **Restart Kernel → Run All** 하세요. Jupyter는 별도 설치합니다. 결과는 `analysis/outputs_cosine/run_실행시각/`의 `tables`, `plots`, `models`에 저장됩니다. 기존 스냅숏을 덮어쓰지 않습니다.

| 입력 | 위치 | 용도 |
|---|---|---|
| 전국 여행장소 | `analysis/tour-places.csv` | 범주·체류·유네스코 표식, G/GC 군집 |
| 지역 시티투어 | `analysis/citytour.csv` | 코스 정제·장소 연결·범주 비중, T/TC 군집 |
| 지역별 내국인 지출 비율 | `analysis/spending_csv/spend_region.csv` | 지역 관광공급과 지출의 설명 회귀 |
| 전국 해양관광 | `analysis/marine_csv/` | 전국 히트맵, 월별 추이, Top5, 검색순위 |
| 연령별 인기관광지 | `age_upgrade/data/raw/` | 연령 지표와 A 군집 |
| 지역 성별·연령별 방문자 구성비 | `demographic_upgrade/data/raw/` | 주변비율 지표와 R 군집 |
| 2026 해외한류실태조사 집계치 | `hallyu_preprocessed_csv/` | 전처리 CSV 8개, 통계값·설계계수·적용조건 |

지출 **업종 분류 S/SC 및 업종·월별 지출 입력은 제거**했습니다. 지역 지출 회귀는 유지합니다. 해양 월별 방문자는 지출 월별 입력과 다른 자료입니다.

주 노트북의 직접 5범주 평점 CSV는 코사인 계산을 검증하는 별도 선택 입력이며 최신 분기 설문에 포함되지 않습니다. 파일이 없으면 `SYNTHETIC_DEMONSTRATION`으로 표시한 가상 응답 4개로 계산을 시연합니다.

분석 스냅숏: 장소 3,118행 중 숙박 569행 제외 후 2,549행, 코스 280행 중 적격 179행, G/GC 10군집·T/TC 2군집. PCA 축은 학습된 성분이며 설문 유형과 다릅니다. 식·실루엣·ARI 해석은 통합 명세서를 참조하세요.

## 3. 연령·성연령 및 기존 산식 비교

```bash
python age_upgrade/run_age_clustering.py
python demographic_upgrade/analyze_demographics.py
npm test --prefix tour_scoring
python run_session.py examples/full_session.json
```

마지막 두 명령과 `tour_scoring`, `survey_legacy`, `session_results`는 **기존 v1~v4 비교용**입니다. 최신 설문은 `reference_calc`를 사용합니다. 성별·연령 구성비는 교차분포가 아닌 주변비율입니다. 한류 자료는 개인 응답 원자료가 아닌 집계 통계입니다.

체류·일정 코드는 `tour_scoring/src/scoring-v2.cjs`, `citytour.cjs`, `session.cjs`와 명세서에 있습니다. 신규 설문의 체류 연결은 명세에 포함되어 있으나 `reference_calc`에 일정 검증을 통합한 것은 아닙니다.

## 버전·검증 범위

- [이관 기록](docs/RELEASE_NOTES.md): 패키지와 최신·비교용 코드 구분.
- [현재 검증 결과](verification/release_validation.json): 이 브랜치에서 실제 실행한 검사.
- 각 모듈의 검증 JSON·로그에는 이전 세션 검사도 보존했습니다.
- 규칙 검증과 재현 검사는 실제 이용자 만족도·추천 정확도 검증을 뜻하지 않습니다.
- 운영 앱 배포, 실시간 운행 확인, 예약 확정과 장소 동일성 검증은 완료된 범위가 아닙니다.

원천 자료의 출처·범위는 각 모듈 README와 메타데이터에 있습니다. 이 저장소에 포함됐다는 사실만으로 원천 자료의 재이용 조건을 새로 부여하지 않습니다.
