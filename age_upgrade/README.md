# 관광데이터랩 연령 인기 관광지 업그레이드

2026-09-27 생성. 업로드한 2025-09~2026-08 자료를 기존 앱 장소·시티투어에 연결한 탐색 분석입니다. 기간은 업로드 파일명 기준입니다. 70곳의 연령 패턴 분석과 전국 앱 장소3,118행에 대한 결합 결과를 구별하세요. 전 지역의 연령별 인기도가 확보된 자료는 아닙니다.

## 재현

Python3.11+ 환경에서 `pip install -r requirements.txt` 후 이 폴더의 `python prepare_age_data.py`, `python run_age_clustering.py` 순서로 실행합니다. 원본 ZIP은 data/source/datalab_age_source.zip, 이름은 바뀌었지만 바이트는 업로드와 같습니다. prepare_age_data는 원본 CSV를 재파싱하고 공백 제거 명칭 매칭을 재생성하며, 앱 설정 age-popularity.json은 ../tour_scoring/data/에 씁니다. 후보 프로필 age-candidate-profiles.json도 tour_scoring/data/에 한 부만 둡니다. 후보 테마/코스 프로필은 기준 커밋의 고정 스냅샷이며 자동 최신화하지 않습니다. 군집 학습은 네트워크를 사용하지 않습니다.

통합 Notebook은 별도 pca_notebook 폴더에 있으며 CSV/모듈 데이터를 내장했습니다. 기존 장소 G군집 9개 그래프와 신규 연령 A군집 6개 그래프를 생성합니다. 모든23개 코드 셀을 IPython에서 순서대로 실행한 출력이 저장되어 있습니다. 이 환경에서 Jupyter 커널 소켓이 제한되어 IPython 순차 실행으로 검증했습니다.

점수는 별도 tour_scoring 폴더의 Node 엔진이 계산합니다. `npm run demo:v3`와 `npm test`를 실행하세요. results/age_score_examples.json 및 *_age_score_changes.csv는 실제 JavaScript 실행값입니다. 노트북의 Python 보조함수는 장소220건에서 이 값과 일치함을 검사합니다.

## 산식과 컬럼

- 원자료 순위 source_rank, 비율 share_pct를 보존합니다. 동률은 비율 기준 중간순위 rank_tie_adjusted로 처리합니다.
- 군집 입력 R=(31-중간순위)/30, Top30 밖은 목록 노출0. 방문량0을 뜻하지 않습니다. 전체(all)는 학습에서 제외합니다.
- 점수 입력 age_intensity_[연령]=비율/동일연령 최대비율. 누락은 빈값으로 보존하고 엔진에서 가산 없음 처리합니다.
- place_id는 앱ID, datalab_id는 원자료 관광지ID로 서로 다른 식별체계입니다. match_weight=0.5는 잠정 명칭 연결 감쇠계수입니다.
- age_cluster=A01/A02/A03은 장소의 관측 연령 패턴이며 여행자의 C1~C10이나 기존 장소 G군집과 다릅니다. A번호에는 순위 의미가 없습니다.
- results/nationwide_places_age_clustered.csv는 3,118행 전체를 보존하고 기존 정보+연령 비율·강도·매칭상태·A군집을 추가했습니다. 숙박569행도 원장 유지용으로 남기며 eligible_cluster=0을 확인하세요.
- age_data_status=no_linked_top30_data는 인기 없음이 아니라 연계 자료 없음입니다. 44잠정 연결 중 숙박1곳을 포함합니다.

## 결과와 적용 범위

70관심지점 → 3개 탐색 군집(46/11/13곳). raw k=3 실루엣0.3949; PCA 2축 설명력73.44%; 비율 변수로 바꾼 민감도 ARI0.1732. A군집은 설명과 비교에만 쓰며 자동 보정에 쓰지 않습니다.

장소 가산 기본 A=0.03×0.5×age_intensity, 최대+0.015. 국내 모드에서만 시범 적용합니다. 60대·70대 이상은 원자료60대 이상을 공유합니다. 10대·해외·누락·검증모드 잠정연결은 가산0입니다. 시티투어는 연결된 경유지의 가산을 전체 슬롯 수로 평균하며 후보 경유지 연결에도0.5를 곱합니다. 연령별로 가산이 발생한 코스는 5/4/1/3/3개입니다(전체280개). 이것이 상위 추천에 모두 들어간다는 뜻은 아닙니다.

각 계수와 기본 국내 적용 정책은 시범 설계값입니다. 표본 수와 분모가 없으므로 신뢰구간, 방문 확률, 실제 체류시간, 향상률을 추정하지 않습니다. 2026 한류 선호와 기존 체류 공식은 변경하지 않습니다.

공식 지표 안내: https://datalab.visitkorea.or.kr/datalab/portal/loc/getPopuTourAttrac.do?callYn=Y&tabDiv=3
