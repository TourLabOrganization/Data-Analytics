# 세션 산출물 이관 기록

Tour Navigator 분석 세션의 최종 유효 산출물을 Git에서 찾아보고 실행할 수 있도록 펼쳐 담은 첫 이관본입니다. 분석을 새로 학습하거나 운영 앱을 배포한 릴리스가 아닙니다.

| 기존 패키지 | 반영 위치 | 기준 |
|---|---|---|
| Tour_Navigator_Integrated_Codebook.zip | analysis, age_upgrade, demographic_upgrade, hallyu_preprocessed_csv, tour_scoring, examples, session_results, verification | integrated-5.0 분석·원자료·결과·비교 코드 |
| Tour_Navigator_Integrated_Specification_Package.zip | docs, reference_calc | integrated-6.2 최신 명세·추천 참조 계산 |
| Tour_Navigator_Branching_Questionnaire_Package.zip | survey | survey-6.1, B1~B7 D 없음 |

중복 파일은 최신 명세·설문을 우선했습니다. 임시 캐시·문서 렌더링 중간본·전송용 복사본은 제외했습니다. 모듈의 상대경로를 유지해 실행 의존성을 보존했습니다.

## 기존 버전과의 관계

- `archive/README_integrated_5_0.md`는 이전 안내입니다. 최신 실행은 최상위 README를 따릅니다.
- `survey_legacy`는 구 설문·비교 사전입니다. 신규 문항은 `survey/implementation`과 `reference_calc`에 있습니다.
- `run_session.py`와 Node.js v1~v4는 기존 방식의 재현·비교용입니다. 당시 예제와의 호환성을 위해 이름을 유지했습니다.
- 주 노트북의 첫 안내문만 최신 설문 진입점을 알려주도록 정리했습니다. 코드 셀·학습 결과는 세션 스냅숏을 보존했습니다.
- 이전 별도 `Tour_Navigator_CSV_to_PCA.ipynb`와 `Tour_Navigator_Cosine_Results.zip`에는 삭제 전 업종 분류가 남아 있습니다. 이후 수정된 `analysis/Tour_Navigator_Integrated.ipynb`를 기준 노트북으로 사용합니다.
- 따라서 삭제 전 51개 그래프·102개 CSV 대신 **주 분석 그래프 41개·결과 CSV 92개**가 기준입니다. 연령·성연령, 설문 그림과 예제 출력은 별도입니다.

CSV 입력, 처리 결과, 학습 모델, 노트북 출력, PNG, 설정 JSON, Word·MD, 원본 비교 코드를 포함합니다. `verification/release_manifest.csv`는 자기 자신을 제외한 파일의 크기와 SHA256을 기록합니다.

재현 검사는 코드·입력·문서 연결 확인이며 규칙 기반 점수의 실증적 타당성을 추가로 증명하지 않습니다. 가상 설문은 실제 이용자 데이터로 표현하지 않습니다.

## 2026-09-29 T 특징 묶음별 분산 균형 개정

- 문제: T 특징의 설계 가중치는 범주 비중 0.75, 방문 후보 수 0.15, 야경 0.10이었으나 실제 분산 기여는 0.25, 0.72, 0.03이었다. 두 T 군집은 범주 구성이 거의 같고 코스 길이로만 갈렸다.
- 수정: `analysis/run_analysis.py`와 노트북에서 세 묶음을 각각 총표준편차로 나눈 뒤 √가중치를 곱한다. 묶음별 표준편차는 모델 파일 전처리 정보에 저장한다.
- 재학습: 결과 폴더를 `analysis/outputs_cosine/run_20260929_000435_315309/`로 교체했다. T는 k=6(실루엣 0.222), TC는 k=7(코사인 실루엣 0.410)이다. G·GC·지출·해양 결과는 이전 실행과 바이트 단위로 같다.
- 연쇄 갱신: 명세서 MD·Word·spec_structure.json의 18·22·25·40·41장과 비교 그림, `reference_calc/eligible_courses.csv`의 T 라벨과 예제 출력, `session_results`의 TC 라벨.
- 추천 점수와 순위는 T 번호를 쓰지 않으므로 바뀌지 않는다.

## 2026-09-29 설문 6.2 · 추천 6.3 개정 (설문-모델 정합성)

전수 경로 점검에서 설문 응답이 코스 추천에 제대로 전달되지 않는 문제를 확인하고 세 가지를 고쳤다.

- 바다 관심사: S4 바다(E) 점수를 C2 +2 · C3 +2 · C9 +2에서 C2 +1 · C3 +1 · C9 +4로 바꾸고(총점 6점 유지), C9 프로필을 바다 0.50·자연 0.30·음식 0.11로 조정했다. 바다를 고른 경로에서 C9 포함 비율 18.8%→40.1%, 1위 코스가 바다 중심인 비율 0%→37.5%.
- 관심사 코스 가산: 테마와 같은 0.5 가중치로 S4 관심사 범주 비중(야경이면 코스 야경 표식)을 코스 점수에 더한다. 1위 코스가 관심사 범주 중심인 비율은 역사 68%→81%, 자연 49%→69%, 체험 33%→62%, 음식 54%→60%.
- 야경·여행 속도 활용: S6 저녁·밤까지는 야경 코스, S3 빡빡하게·천천히는 방문지가 많은·적은 코스에 0.1 가산한다. `eligible_courses.csv`에 방문 후보 수와 야경 표식 열을 추가했다.
- 점수식: `100 × (fit + Σ w·b) / (1 + Σ w)`. 적용되는 항만 분모에 넣어 0~100을 유지하고, 가산이 없으면 이전과 같은 `100 × fit`이 된다. 테마 점수는 바뀌지 않았다.
- 설문 완료 경로 141,833개→141,897개(F1 조합 변경). 명세서 MD·Word·spec_structure.json, 설문 문항지 MD·Word, README와 예제 출력을 갱신했다. 응답자용 설문지는 점수를 표시하지 않아 바뀌지 않았다.
- 수치는 모든 선택지가 같은 빈도라고 가정한 구조 점검이며 실제 이용자 분포나 만족도 검증이 아니다.
