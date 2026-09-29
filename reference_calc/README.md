# 신규 설문 추천 참조 계산 — integrated 6.3

Python 3.10 이상 표준 라이브러리만 사용합니다. 저장소 최상위에서:

```bash
python reference_calc/score_survey.py reference_calc/demo_answers.json
python reference_calc/recommend_reference.py reference_calc/demo_answers.json
python reference_calc/verify_reference.py
```

설문 6.2의 S1~S6, 해당 B 하나, 필요한 경우 F1을 입력합니다. B1~B7의 D 없음은 0점이며 기존 점수를 유지합니다. 미완료 입력은 다음 문항을 반환합니다.

`survey_config.json`은 문항과 선택지별 점수, `recommendation_config.json`은 유형별 5범주 프로필과 테마 정보를 담습니다. `recommendation_config.json`의 `course_score`에는 코스 가산 설정이 있습니다. `eligible_courses.csv`는 주 분석에서 가져온 적격 179코스 스냅숏이며, 6.3에서 방문 후보 수와 야경 표식 열을 추가했습니다. `input_provenance.json`에 출처가 있습니다. 예제 응답·결과는 가상 검증 자료입니다.

추천 벡터는 `q_source=type_profile_prior`인 간접 선호입니다. 직접 코사인 평점 5문항은 신규 설문에 포함되지 않습니다. 코스 점수는 범주 적합(코사인 × 분류 커버리지)에 S4 관심사(0.5)·S6 저녁·밤 야경(0.1)·S3 여행 속도(0.1) 가산을 더하고, 적용된 항의 가중치 합으로 나눠 0~100으로 만듭니다. 결과의 `category_fit_score`는 가산 전 점수, `bonus_points`는 항별 가산 점수입니다. 테마 점수와 코스 점수는 합산하지 않습니다. 기본 흐름의 지역·한류·연령·성별 추가 가산은 0입니다. 체류·일정 검증은 이 참조 코드에 통합하지 않았습니다.

전체 [명세서](../docs/Tour_Navigator_Integrated_Specification.md)와 [설문지](../survey/Tour_Navigator_Branching_Questionnaire.md)를 참고하세요. 원자료 전처리·PCA·군집 재학습은 [analysis](../analysis/)에서 수행합니다. 재학습 후 이 폴더의 코스 스냅숏이 자동 교체되는 것은 아닙니다.
