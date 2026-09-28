# Tour Navigator 설문·추천·체류 산정 v2.0.0

기존 추천 로직과 비교하면서 H1~H4, 콘텐츠 선호 점수, 지역별 대표 선정, 개인별 체류 및 일정 검증을 실행하는 패키지입니다. 운영 앱 전체를 대체하거나 배포한 상태는 아닙니다.

## 실행

Node.js 18 이상. 의존성 설치 없이 이 폴더에서 실행합니다.

```bash
npm start
# 브라우저에서 http://127.0.0.1:8787
npm run demo:v2
npm test
```

설문 화면에서 Q1·Q2·Q3·Q6은 필수, H4는 선택입니다. 국내·해외 모두 H4에 답할 수 있습니다. H1~H3는 해외 방문자에게, H2는 10대에게만 표시합니다. Q7 보기는 Q6에 따라 바뀝니다. 건너뛰기와 보통은 다른 값입니다. /calculate는 서버가 입력을 검증하고 점수 분해를 반환합니다. 응답은 디스크에 저장하지 않습니다.

## 신규 산식

- 직접 답변: e = 0 / 0.25 / 0.5 / 0.75 / 1, z=e.
- 미응답: 대상이면 z=0.5+0.2(r−0.5), 대상 밖이면 z=0.5.
- H = 0.1 × Σ M(k) × (z(k)−0.5). 기존 추천점수 + H로 전체 후보를 정렬합니다.
- 시티투어는 정렬 후 지역별 하나씩 최대 5개. H 적용 전에 지역을 고르지 않습니다.
- I = Σ M(k)z(k) + (1−ΣM)I0.
- 체류 원값 = B × [1+0.2(I−0.5)] × P + 추가활동분.
- 권장분 = 5분 올림 후 [L,U] 제한. 고정 시간 > 수동 시간 > 권장 시간 순으로 적용합니다.

계수는 시범 설계값입니다. 통계는 첨부 2026 해외한류실태조사 요약본의 2025년 콘텐츠 추천의향이며 관광지 체류 실측값이 아닙니다. data/hallyu_2026.json에 출처와 활성·비활성 분야를 구분했습니다.

## 실제 데이터와 가상 시연의 구분

280개 실제 코스의 콘텐츠 태그는 아직 구축하지 않아 기본 실행 시 H=0과 MEDIA_NOT_MAPPED를 기록합니다. 콘텐츠 가산을 적용하려면 검증된 themeProfiles / tourProfiles를 입력합니다. 지역명만으로 촬영지 태그를 자동 생성하지 않습니다. UI의 B=60분 드라마 장소는 산식 시연용 가상 장소입니다. 실제 추천 코스 점수를 변경하지 않습니다.

프로필 형식: `{verified:true, source:"검증 근거", media:{drama:0.5}}`. verified는 공급자 선언이며 출처 사실성을 엔진이 검증하는 기능은 아닙니다. 태그 비중 합은 1 이하입니다. themeProfiles의 키는 테마 k, tourProfiles의 키는 동봉 citytour_app_zip.json의 행 인덱스입니다. 후보 순서가 변경되면 프로필을 재매핑해야 합니다.

## 함수 연결

```js
const v2 = require('./src/scoring-v2.cjs');
const input = require('./examples/v2_domestic.json');
const result = v2.recommendV2(input);
const stay = v2.estimateStay({
  answers: input.answers, preference: result.preference,
  place: {baseMinutes:60,minMinutes:30,maxMinutes:120,categories:[0]}
});
```

- answers: 기존 Q 번호에서 1을 뺀 키. 선택지 0 기반 인덱스. Q4·Q14는 배열.
- hallyu.contentPreference: `drama/film/variety/music`별 `{rating:1,answered:true}` 또는 `{rating:null,answered:false}`.
- hallyu.residenceArea: ISO 2자리, age15to19·experienced: boolean. 언어나 국적을 거주지역으로 추정하지 않습니다.
- buildCourseMedia(stops,totalUniqueStops): 고유 경유지 id와 contentProfile로 프로필 구성. 미매핑 경유지도 분모에 포함.
- estimateStay: 추가활동분(extraMinutes), 수동분(manualMinutes), 고정분(fixedMinutes)을 선택 공급. 누락 기본분은 오류이며 기본분 0은 제외 처리. 범주별 잠정 기본분은 별도 데이터 준비 단계에서 출처를 붙여 공급.
- validateTimeline({answers,days,longWalkingMinutes}): 일정 검증. examples/v2_schedule.json을 참고하고 Q11의 일수와 일치하는 연속 날짜를 제공.

## 일정 데이터 계약

시각은 현지 자정 이후 분으로 공급합니다. 하루 start/end, 실제 date와 origin, 이동 확인 여부 transportVerified가 필요합니다. Q12의 이동수단에 맞는 경로·버스시간표는 외부에서 공급해야 합니다. 이 패키지는 실제 경로 API나 운행시간표를 조회하지 않습니다.

각 경유지의 moveMinutes는 전체 이동분이고 walkMinutes는 그중 보행분입니다. 별도 정류장 보행 stopWalkMinutes는 다음 경유지 이동에 중복 포함하지 마세요. 운영시간 누락은 HOURS_UNKNOWN으로 기록하고 24시간 영업을 가정하지 않습니다. 식사·휴식은 별도 이벤트로 공급하고 장소 체류분과 중복 계산하지 않습니다.

고정 시티투어: redepartMinute, boardingBufferMinutes, minVisitMinutes. 순환버스: loopDepartures, stopWalkMinutes, boardingBufferMinutes. 귀환: returnDeadline, returnDeadlineKind(arrival_home 또는 departure_hub), returnMoveMinutes, returnWalkMinutes, returnBufferMinutes. 반려동물·무장애는 features.pets/accessible, 실내는 features.indoor입니다. 결과 상태는 feasible / needs_data / conflict이며 입력된 데이터 기준입니다.

## 검증과 기존 코드 비교

- 기존 테마 결과·오류 610회 대조: 정상 491, 원본 오류 119 재현.
- 기존 시티투어 186회 대조.
- 신규 함수 39개 테스트 통과. 직접 선호, 통계 대상 제외, 지역 대표 변경, 체류·폐장·보행·막차·귀환 검증 포함.
- 로컬 HTTP의 질문 제공·국내/해외 계산·잘못된 입력 반환을 확인했습니다. 브라우저 렌더링 자동검사는 실행 환경에 브라우저가 없어 수행하지 못했습니다.

신규 엔진은 fr가 있는 GitHub 테마 자료를 사용합니다. 원본 APP.zip의 fr 누락 오류는 legacy 비교용 모듈에서 유지합니다. 기존 설명과 실행법은 README_LEGACY.md, 원문 추적은 PROVENANCE.json, 상세 질문별 점수는 동봉 제공 Word 명세서 참조.
