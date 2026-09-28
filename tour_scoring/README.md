# Tour Navigator 성별 연령별 지역지표 확장 v4.0.0

기존 v3 장소 연령 인기도에 **지역별 성별·연령별 주변구성비**를 추가했습니다. 운영 앱에는 배포하지 않은 로컬 실행용입니다. 기존 설명은 README_V3.md와 README_V2.md에 보존했습니다.

## 실행

Node.js18 이상, npm 의존성 설치 없이 `npm start`로 http://127.0.0.1:8787 접속. `npm run demo:v4`, `npm test` 지원.

```js
const V=require('./src/scoring-v4.cjs');
const input=require('./examples/v4_domestic30female.json');
const result=V.recommendV4(input);
// input.demographics={sex:'female',enabled:true};
```

D1은 선택형 성별 질문입니다. male/female/unspecified/null 허용, 기본미선택. 기존 Q1~Q14 보기 인덱스를 변경하지 않습니다. 지역 적용 기본true; `demographics.enabled=false`이면 D만0으로 v3와 일치합니다. `ageOptions.strictVerified=true`이면 잠정 장소·지역 연결 모두 제외됩니다. 해외 모드에서는 D=0입니다.

## 산식과 범위

원자료 정상90지역의 성별비율/연령비율을 별도로 사용합니다. p=각 분류의 원비율/지역별 분류합, b=제공된90지역의 중앙값, z=clip(log2(p/b),0,1), D=0.02×0.5×(.75z_age+.25z_sex). 성별 미응답이면 성별항0이며 가중치를 넘기지 않습니다. 비율0은z=0. 70대 자료의 상한 미확인으로 Q1=70대 이상은 새 지역 연령항을 보류합니다. 기존 장소 Top30의60대 이상 항과 성별항은 유지합니다.

지역 최대0.01, 장소/시티투어는 기존 연령 가산과 합쳐0.02 상한, 테마는 기존 지역 보정과 합쳐±0.05 상한입니다. 전체 후보 계산과 정렬 후 지역별1개·최대5코스를 뽑습니다. 계수는 시범 설계값이며 방문 로그로 추정하지 않았습니다.

90지역은 남성 구성비 상위 목록에 선택된 자료입니다. 전국 평균으로 표시하지 않습니다. 54개 앱 지역·952장소·127코스의 지역 연결이 가능하며 모두 이름 기반 잠정값입니다. 상세표 없는 지역, 데이터가 충돌한4지역, 광역도시 집계 및 중복지명은 제외합니다. 코스 지역이 실제 여러 경유지역을 대표한다는 근사입니다.

## API와 출력

- `regionalBonus(appRegion,answers,demographics,ageOptions)`: 해당 지역의 D, agePart, sexPart, 기준값, 이유.
- `applyDemographicsToPlace({placeId,score},...)`: **A와 D를 더하기 전 기본 점수**를 입력. 기존 v3 보정이 더해진 점수를 재입력하면 중복 가산됩니다.
- `recommendV4(input)`: v3 출력에 demographicPolicy 및 후보 regionalDemographics 추가. effectiveBonus가 실제 변화량입니다.
- agePlaceRanking은 기존 장소연령 보정만 보여주는 진단 목록입니다. v4 전체 장소 순위가 아닙니다.
- 체류와 일정은 v2 estimateStay/validateTimeline을 사용하며 성별로 체류·속도를 변경하지 않습니다.

테마 프로필은 기준 커밋의 페이지 비숙박 장소 고정 스냅샷입니다. 테마·코스를 바꾸면 data/age-candidate-profiles.json 및 data/region-demographics.json을 함께 갱신하세요. 지역 세분 코드 없는 코스를 자동으로 구 단위에 배정하지 않습니다.

## 검증

기존 테마610회·시티투어186회 대조 유지. v2 39개, v3 22개, v4 30개 테스트 통과. 로컬 HTTP 국내·해외·검증모드·오류 응답 및 UI 스크립트 구문 확인. 브라우저 시각 자동검사는 미실행. 통계적 추천 성능향상을 입증한 검증은 아닙니다.

원자료 품질검사·PCA/R군집·전후 점수CSV·상세명세서는 별도 v4 업그레이드 묶음을 참조하세요. 군집번호는 추천점수로 쓰지 않습니다.
