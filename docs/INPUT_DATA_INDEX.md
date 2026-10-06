# 입력 데이터 목록

CSV 행 수는 헤더를 제외한 실제 레코드 수입니다. 원자료, 집계치 전처리, 추천용 처리 결과를 구분합니다.

2026-09-29: 앱 장소 원본(Tour-Navigator-App)에서 맥도날드 드라이브스루 9곳(`ro466` · `ro467` · `ro524` · `ro532` · `ro536` · `ro540` · `ro684` · `ro780` · `ro857`, 모두 `food`)을 삭제한 데 맞춰
`analysis/tour-places.csv`와 `age_upgrade/data/source/nationwide_places_all_3118.csv`(파일 이름은 스크립트 경로 때문에 그대로)에서도 뺐습니다(3,118 → 3,109행).
분석 결과(`analysis/outputs_cosine/run_20260929_234547_706228/` · `age_upgrade/results/` · `demographic_upgrade/results/` · `tour_scoring/data/region-demographics.json` 등)는
3,109행으로 다시 계산했습니다. 관광지 군집은 G 10 → 8군집, GC 10 → 7군집으로 바뀌었고, 9곳은 시티투어 경유지가 아니라 T·TC 군집 · 적격 234코스 · 시티투어 점수 · 테마 추천 결과는 그대로입니다(자세한 내용은 [이관 기록](RELEASE_NOTES.md)).

| 파일 | 행 수 | 열 수 | SHA256 |
|---|---:|---:|---|
| [analysis/tour-places.csv](../analysis/tour-places.csv) | 4,841 | 17 | `022fe69ca785a47d83bc3de5d8a1fe303e464e061131b7fe84e391bd78da639d` |
| [analysis/citytour_manual_places.csv](../analysis/citytour_manual_places.csv) | 124 | 13 | `26951dc66690823d300413eb04cd7b1edb5d2b1c6e6ce2e12e2ccfd962664b4b` |
| [analysis/popular_manual_places.csv](../analysis/popular_manual_places.csv) | 100 | 4 | `edf5921644302b646fd3d6ff043f26817846ffaa9a6293fd4d9b7ad07a43b010` |
| [analysis/related_manual_places.csv](../analysis/related_manual_places.csv) | 67 | 14 | `e02fba63c491dee30bd09543d16984cdeff15aa72ac58309fd3c6872ab9007f3` |
| [analysis/crowd_manual_places.csv](../analysis/crowd_manual_places.csv) | 7 | 14 | `e4b0f9d62ce97e177d56c184d3e7dcf229d15fb663e1e1e4c586070e943dbfca` |
| [analysis/same_places.csv](../analysis/same_places.csv) | 90 | 3 | `147f40121214ed96ac20422c045d9e5827db055b88168895cf6157175401fd55` |
| [analysis/place_aliases.csv](../analysis/place_aliases.csv) | 90 | 3 | `da6d1c3343c559fc26cb4fecc19d9e80d6a83a4d091b1377b84a0f3282387aeb` |
| [analysis/user_manual_places.csv](../analysis/user_manual_places.csv) | 3 | 14 | `69b734d7dd0f1313e5a50c70a0e0a0f30475abdeae476cd548432a6194c5b7d7` |
| [analysis/popular_match.csv](../analysis/popular_match.csv) | 4 | 4 | `00391b88a0526e0cbb04e0ab5f1688950564884d2139e5085a3156e8f0247463` |
| [analysis/national_treasure_places.csv](../analysis/national_treasure_places.csv) | 29 | 15 | `6fb223b1e3f02001b7bbcf56f61192cf3614fcfbbd3f8d55f5f028d7988bb01c` |
| [analysis/national_treasure_places_2.csv](../analysis/national_treasure_places_2.csv) | 34 | 14 | `2520e708dea7959fa59dedefcb505848b76411178ec75b2a319f2fca66b71b0f` |
| [analysis/treasure_sites.csv](../analysis/treasure_sites.csv) | 577 | 8 | `ef3e90098af8f6a9757ec0fa5100839bff31a690ec83db31c0d9f9db90ded2a6` |
| [analysis/treasure_places.csv](../analysis/treasure_places.csv) | 532 | 15 | `5fe35404ff46f136228b5900152c47edf7bc90675dddffb0b5873aaf4217cc1b` |
| [analysis/k100_list.csv](../analysis/k100_list.csv) | 100 | 9 | `c92d79b7c544daeb73fe27b783e7cccd0f55458dce3418c91d76b5c2ac71f12c` |
| [analysis/open_tourism_list.csv](../analysis/open_tourism_list.csv) | 211 | 7 | `c6a65f9a885602ac0e752adf6e1de73ad10cbc857ef5796dce4c08a38b1a956c` |
| [analysis/open_tourism_places.csv](../analysis/open_tourism_places.csv) | 32 | 15 | `0d1de70ffbd52870c34771868a8685d2ae99d9fa3cdb21e4a4ec481b6cbf48f0` |
| [analysis/uiryeong_places.csv](../analysis/uiryeong_places.csv) | 17 | 15 | `500b9e3405bb5df1124acf8d7653ef4aebe3483efd0f1fe26aa20ced72dbb472` |
| [analysis/leisure_places.csv](../analysis/leisure_places.csv) | 34 | 15 | `9905c65dd65b67dbc79beb6f2b621adaed642c8cb3a21a349b79126085b75346` |
| [analysis/beach_valley_places.csv](../analysis/beach_valley_places.csv) | 202 | 15 | `843a2a24d94d4075a329e9af95f7fccce67ed11788fcf469a2d6a715a2e57ad0` |
| [analysis/art_literature_places.csv](../analysis/art_literature_places.csv) | 146 | 15 | `ddd42975074c6571e9a855e808826bb2c581186988f9f97b8ef7e450cec91627` |
| [analysis/market_places.csv](../analysis/market_places.csv) | 82 | 15 | `28e639bcac060ea4d34782d78721ad44af222a67c39549c9442dfc4c1e22c080` |
| [analysis/place_fixes.csv](../analysis/place_fixes.csv) | 290 | 10 | `54e468939ee47b4fa6dec345dc3345a4bc44de602507d7f6f4794860286a7354` |
| [analysis/unesco_list.csv](../analysis/unesco_list.csv) | 17 | 4 | `ea964c658c2f7bd380d6a0941410b0116abaa5b638fc061c1b7358d3f51445bb` |
| [analysis/unesco_places.csv](../analysis/unesco_places.csv) | 13 | 15 | `58b3d129eb34da3c88dcebf706eaf70013ae52a87c9eb5191fb150ae60bab003` |
| [analysis/aquarium_places.csv](../analysis/aquarium_places.csv) | 9 | 15 | `3069f4c43e32053daa236811053db00bd82f4420b8eee4725979d80076a16877` |
| [analysis/sokcho_places.csv](../analysis/sokcho_places.csv) | 70 | 15 | `31f33793e4d5377d892518cf058e21e0b91b625c9d52e8b031949d18f17d8709` |
| [analysis/gangneung_places.csv](../analysis/gangneung_places.csv) | 71 | 15 | `2c9dcbf9955660fd6a8a4b6acbeb65013002b4783fe8bb616275ccaa1826c1eb` |
| [analysis/jeonju_places.csv](../analysis/jeonju_places.csv) | 69 | 15 | `bd1fc2c01b337b6bb889aeb84f11ded06804437230856a1d2234021e10662070` |
| [analysis/island_places.csv](../analysis/island_places.csv) | 37 | 15 | `fd66b37de8ef5e799a719758c371701006db04f7e9cfee4e11bc7a2b207d0619` |
| [analysis/resort_places.csv](../analysis/resort_places.csv) | 127 | 15 | `d9386cef46adda75c2c6d65115b47da81905f25e286ecaf23a26d4bc16e225cd` |
| [analysis/food_list_places.csv](../analysis/food_list_places.csv) | 105 | 15 | `a99b739cd193f3ae56d762a574da628e8e3ad15443cc0035c4610246c1d18c76` |
| [analysis/place_notes.csv](../analysis/place_notes.csv) | 11 | 4 | `e1270bdd01aa6d84cafade579c6c6c848f0dba8f23c3f54e9099a53fc665b9ba` |
| [analysis/bakery_places.csv](../analysis/bakery_places.csv) | 90 | 15 | `e46e5473ffff7efba20fdf9ed10b0e893f0f60d8a5f7b3885852ac9404724469` |
| [analysis/related_added/related_mentioned_missing_2026-10-03.csv](../analysis/related_added/related_mentioned_missing_2026-10-03.csv) | 842 | 4 | `c0920fb295ed1f7b4266d7f22b223393a74ddfc2eefcd3978003c5d7e620fea2` |
| [analysis/place_signgu.json](../analysis/place_signgu.json) | 4,841 | 2 (id, 코드) | `feee819dddf1508aa051471fe823a26f242bbf0f7ddb396e08362084dc17d80b` |
| [analysis/citytour.csv](../analysis/citytour.csv) | 280 | 13 | `cea012bccbeb03bc8abc841e1be6b6e5310df547dcd8d6ade9c51c638d865324` |
| [analysis/stop_category_review.csv](../analysis/stop_category_review.csv) | 30 | 4 | `3cd2219d4290dcac5204adb865a4677f030182ae05e020778dbe4785f45dc70b` |
| [analysis/spending_csv/spend_region.csv](../analysis/spending_csv/spend_region.csv) | 233 | 4 | `b57eaea72fa6b060347393748e00676c160326921375b048af2486e6d632a31c` |
| [analysis/marine_csv/marine_heatmap.csv](../analysis/marine_csv/marine_heatmap.csv) | 3,564 | 3 | `b98acc36b7d8b59d9daf6c79adf5a22129eabc9f8f49f9eb5aba3d63e8884ff3` |
| [analysis/marine_csv/marine_monthly.csv](../analysis/marine_csv/marine_monthly.csv) | 60 | 4 | `d418cdaf056050fed1268cd7805d7a362227c8adee4592337b2ef6f4493afa44` |
| [analysis/marine_csv/marine_search_rank.csv](../analysis/marine_csv/marine_search_rank.csv) | 100 | 5 | `bdcc97daefa6cbd4083617999a6299dd356cba3a7c66d8bf1595f0a5da6dc3d6` |
| [analysis/marine_csv/marine_top5.csv](../analysis/marine_csv/marine_top5.csv) | 5 | 5 | `b82e6ad2155897014d6a275ba6f82042e3c0ea3bf79f5395ffebc6da0f13d197` |
| [age_upgrade/data/raw/20260927150125_세대별 인기관광지(20대).csv](../age_upgrade/data/raw/20260927150125_세대별%20인기관광지(20대).csv) | 30 | 6 | `0960628ff41b6039434d48c11686f92316899f49d22133cff99fba1dadbe94a2` |
| [age_upgrade/data/raw/20260927150125_세대별 인기관광지(30대).csv](../age_upgrade/data/raw/20260927150125_세대별%20인기관광지(30대).csv) | 30 | 6 | `66d7eb0551730e822e577a3ff1aba5c653f0b4c5acb5c5cfa360743e740d5f59` |
| [age_upgrade/data/raw/20260927150125_세대별 인기관광지(40대).csv](../age_upgrade/data/raw/20260927150125_세대별%20인기관광지(40대).csv) | 30 | 6 | `0f1eba2318cd4131d9bb3c429434fb4623e8527553e7c911de9b6e13925768a5` |
| [age_upgrade/data/raw/20260927150125_세대별 인기관광지(50대).csv](../age_upgrade/data/raw/20260927150125_세대별%20인기관광지(50대).csv) | 30 | 6 | `5adb09c67bffa21aa80714557b0f8d1c7400d0843746837c69abd36d3a48b34d` |
| [age_upgrade/data/raw/20260927150125_세대별 인기관광지(60대이상).csv](../age_upgrade/data/raw/20260927150125_세대별%20인기관광지(60대이상).csv) | 30 | 6 | `f788d71ead92adc050cc6eb17f330893acf0a064d20520fc9d4df122a1d7ce9e` |
| [age_upgrade/data/raw/20260927150125_세대별 인기관광지(전체).csv](../age_upgrade/data/raw/20260927150125_세대별%20인기관광지(전체).csv) | 30 | 6 | `5bd1770ad0810f005d6a46272544b05a2e2fe909217d023c7cc763bc560be5ff` |
| [demographic_upgrade/data/raw/20260927163120_구성비 순위.csv](../demographic_upgrade/data/raw/20260927163120_구성비%20순위.csv) | 100 | 6 | `ee573530a473cc381e9c76802775b64ec945c694d9e31815f82efa171dca2a56` |
| [demographic_upgrade/data/raw/20260927163120_구성비 히트맵.csv](../demographic_upgrade/data/raw/20260927163120_구성비%20히트맵.csv) | 242 | 6 | `23bb54059adc4f1e3b1ea0a18c53d3e1e8bd632113688c73b64ad6ad2de18349` |
| [demographic_upgrade/data/raw/20260927163120_성별 방문자 구성비.csv](../demographic_upgrade/data/raw/20260927163120_성별%20방문자%20구성비.csv) | 220 | 6 | `a7ae50185f0dadc85e43e4d3b2a559e6f7a99047c09e8210f317672298a0d02b` |
| [demographic_upgrade/data/raw/20260927163120_연령별 방문자 구성비.csv](../demographic_upgrade/data/raw/20260927163120_연령별%20방문자%20구성비.csv) | 880 | 6 | `999b3d408130434d92357e9222db7519727a7a7418b10c9b0fff3e38d193b9d3` |
| [hallyu_preprocessed_csv/hallyu_2026_country_scope.csv](../hallyu_preprocessed_csv/hallyu_2026_country_scope.csv) | 30 | 9 | `a90f3e7829231957592eddf3fd5263766cb13e28814195360a3c565e1c7cb3fb` |
| [hallyu_preprocessed_csv/hallyu_2026_data_dictionary.csv](../hallyu_preprocessed_csv/hallyu_2026_data_dictionary.csv) | 75 | 4 | `eb8f43524daaa55ddf886ffeca4202f0766e07669a5f253b7f58ceabe0001bfd` |
| [hallyu_preprocessed_csv/hallyu_2026_design_parameters.csv](../hallyu_preprocessed_csv/hallyu_2026_design_parameters.csv) | 5 | 5 | `1702043249372483ac94ffa2cac262448f300dac3b0c4d42d34e00041d567aa6` |
| [hallyu_preprocessed_csv/hallyu_2026_eligibility_rules.csv](../hallyu_preprocessed_csv/hallyu_2026_eligibility_rules.csv) | 6 | 6 | `87deb67571887af13dc73fc6896f8c73427263ea89a029380df3c3366a097eef` |
| [hallyu_preprocessed_csv/hallyu_2026_reference_only.csv](../hallyu_preprocessed_csv/hallyu_2026_reference_only.csv) | 11 | 10 | `2fa403aa76da27ba3d0139638d22c5152086a385b8392a5f390408a93eb7b791` |
| [hallyu_preprocessed_csv/hallyu_2026_scoring_inputs.csv](../hallyu_preprocessed_csv/hallyu_2026_scoring_inputs.csv) | 4 | 19 | `761be4597263dd135d3e2ff997bfb2f589c20b52ef2c6b1bc64e3bf6ad962891` |
| [hallyu_preprocessed_csv/hallyu_2026_source_indicators.csv](../hallyu_preprocessed_csv/hallyu_2026_source_indicators.csv) | 12 | 23 | `f99fea85000beb0825a44cb3253c43cc462cba2e0699efbca4fd42dd2bb5da3f` |
| [hallyu_preprocessed_csv/hallyu_2026_source_metadata.csv](../hallyu_preprocessed_csv/hallyu_2026_source_metadata.csv) | 12 | 3 | `4308222a0e43122f67d0d7db3e720ee42c2b4b97eb2f6abd8e8dee79d91ac52f` |
| [reference_calc/eligible_courses.csv](../reference_calc/eligible_courses.csv) | 234 | 14 | `2ae3d5ff26b3a6d431c66c3963e15aa76951f8e4d815e77471c603258b03f7d4` |

## 입력 구분

- 전국 장소·시티투어, 관광데이터랩 연령·성연령·지역 지출·해양 CSV를 포함합니다. 원본 다운로드 ZIP이 전처리 스크립트에서 필요하면 해당 모듈의 data/source 경로에 보존했습니다.
- 한류 8개 CSV는 원문 발표 집계치와 설계값의 구분을 포함하며 개인 응답 원자료가 아닙니다.
- `eligible_courses.csv`는 280개 코스 중 분류 조건을 통과한 234개 처리 결과입니다(2026-09-29 범주 미확인 경유지 2차 재분류 후. 코스 재점검 전 179개, 연결 재점검 전 229개, 1차 재분류 전 223개. 2차 재분류는 코스 수를 바꾸지 않았고 화성 "바다와 하루"가 들어오고 화순 적벽 코스 하나가 빠졌다). 6.3에서 코스 가산에 쓰는 방문 후보 수와 야경 표식 열을 추가했습니다.
- `analysis/stop_category_review.csv`는 이름만으로 범주를 정할 수 없는 시티투어 경유지의 검토 범주와 판단 근거입니다(30행). 범주는 5범주, NON_VISIT, UNKNOWN만 허용하며 `run_analysis.py`가 읽을 때 검사합니다.
- `analysis/survey_responses_template.csv`는 헤더만 있는 선택적 직접 코사인 평가 입력 양식입니다. 최신 분기 설문은 `survey/implementation/example_answers.json`과 `reference_calc/demo_answers.json`을 사용합니다.
- 실제 이용자 응답은 포함하지 않았습니다. 제공 예제는 가상 응답입니다.
- 성별과 연령 비율은 각각의 주변분포이며 성×연령 결합 분포가 아닙니다.
- 지출업종 분류·입력은 제외하고 지역 지출 비율은 설명 분석에만 유지합니다.
