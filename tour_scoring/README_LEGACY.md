# Tour Navigator 현재 점수 산정과 테마 추천 코드

2026-09-27 확인한 GitHub main 커밋 `96db458ed63b3e34a1c3d63a8ad444ea67ab6b77` 및 제공된 APP.zip의 홈 추천을 설명하고 재현하는 패키지입니다. 앱 전체 또는 개선판이 아닙니다. 실제 저장소와 APP.zip을 수정하지 않았습니다.

## 실행

Node.js 18 이상. npm 패키지 설치, API 키, 인터넷 연결이 필요 없습니다. ZIP을 풀고 이 README와 package.json이 있는 폴더에서 실행합니다.

```bash
node src/cli.cjs examples/domestic.json
node src/cli.cjs examples/foreign.json
node src/cli.cjs examples/app_zip_domestic.json
node src/cli.cjs examples/app_zip_foreign_error.json
node tests/parity.cjs
```

마지막 외래객 예제는 원본 ZIP의 `fr` 누락 때문에 TypeError를 출력하고 종료 코드 1을 반환하는 것이 예상 동작입니다. 코드가 오류를 임의로 보정하지 않습니다. 앱 화면 전체의 정상 동작을 보장하는 테스트는 아닙니다.

## 입력과 출력

- `version`: `github` 또는 `app_zip`. 기본 github.
- `browserLanguage`: 원본 `navigator.language`에 대응. 앱 화면 선택 언어와 다릅니다.
- `answers`: 키 0~13은 Q1~Q14, 값은 보기의 0 기반 인덱스. Q4와 Q14만 배열입니다. 생략한 키는 미응답입니다.
- 예: `"5":0`은 국내 거주, `"5":1`은 해외 방문. `"3":[2,3]`은 역사와 자연 관심입니다.
- `result`: 원본 finish()가 저장하는 결과와 동일. p/s2는 군집의 0 기반 인덱스, pr/pr2는 반올림한 상대 점수 백분율입니다.
- `trace`: 설명을 위해 추가한 기여 점수, 군집 순위, 반올림 전 상대 비중, 모든 테마의 fit/bonus/reg/score.
- app_zip 정상 결과에는 280개 시티투어 중 지역 중복을 제거한 최대 5개 추천의 분해 점수도 출력합니다.
- 입력 형식 검증은 설명용 모듈에 추가한 기능입니다. 원본 화면은 UI 입력을 전제로 합니다.

## 핵심 순서

1. Q1~Q9 점수표 합산. Q6은 직접 점수표가 없고 후보 제한·외래객 가산을 제어.
2. 해외 방문이면 C7~C10에 각 2점, 브라우저 언어에 따른 추가 가산.
3. 국내 거주는 C1~C6만 후보. 해외 방문 및 미응답은 C1~C10 전체 후보.
4. 2^(총점/2)을 후보 전체에서 정규화. 1위 비중이 0.5 미만이면 1·2위를 혼합.
5. 테마 구성비와 군집 가중치 내적에 관심사 가산점과 지역 보정을 더함.
6. 5개 테마를 원점수 내림차순으로 정렬해 상위 3개 반환.
7. Q10~Q14는 filters 문자열로 저장. 테마 점수와 순위를 직접 바꾸지 않음.
8. APP.zip 시티투어는 별도 키워드 분류, 군집 적합도, 관심사, 경유지 수 가산을 계산하고 지역별 1개씩 최대 5개 선택.

## 파일 구성

| 경로 | 역할 |
|---|---|
| src/scoring.cjs | 현재 테마 추천의 순수 함수와 trace |
| src/citytour.cjs | ZIP 시티투어 프로필과 지역별 추천 |
| src/cli.cjs | JSON 입력 실행기 |
| data/github.json | 원본 QS·CL·TH 점수표 전체 |
| data/app_zip.json | ZIP의 QS·CL·TH 전체, fr 누락 유지 |
| data/citytour_app_zip.json | ZIP 홈에 내장된 시티투어 280건 |
| reference/*recommendation.js | 원본 클래스 중 state~finish 발췌; 단독 앱 실행용 아님 |
| reference/app_zip_citytour.js | 원본 KW·prof·추천 선택 구간 발췌 |
| reference/upstream | 산출 근거 검토용 원본 Python 4종 |
| reference/derived | 저장소의 산출 JSON 4종 |
| examples | 국내·외래객·ZIP 예제와 정상 출력 |
| tests/parity.cjs | 원본 발췌와 설명용 엔진의 결정적 대조 검사 |
| tests/verification_result.json | 이번 검증 결과 |
| PROVENANCE.json | 기준 커밋, ZIP SHA-256, 자료 범위 |

## 재현 범위와 제한

원본 Python은 분석 근거 참고용입니다. 외래객 원자료와 df.pkl, labels.pkl 등 중간파일, 일부 장소 분류 입력은 제공되지 않아 이 패키지만으로 조사 분석 전체를 재학습할 수 없습니다. 현재 실행 점수의 권위 있는 값은 data/github.json 및 data/app_zip.json입니다. Python의 가상 테마와 대표 사용자 실험은 앱의 현재 5개 테마 추천과 구분합니다.

군집 상대 비중은 검증된 예측확률이 아니며 테마 점수도 0~1 정규화 점수가 아닙니다. 군집 가중치의 일부 합계는 반올림 때문에 0.99 또는 1.01입니다. 재현 모듈은 임의로 재정규화하지 않습니다. API 키 및 원본 앱 전체는 포함하지 않습니다.

원본 저장소: https://github.com/TourLabOrganization/Tour-Navigator-App
