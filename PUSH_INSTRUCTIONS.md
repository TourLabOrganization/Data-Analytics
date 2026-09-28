# Data-Analytics 브랜치 push 준비본

원격 저장소: https://github.com/TourLabOrganization/Data-Analytics
브랜치: analytics/pca-cosine-survey-v6.2
커밋: e3f0aed80bf752339cbada5d9cf7f15c39e175f1

369개 파일의 로컬 커밋과 검증을 완료했습니다. GitHub 연결의 브랜치 생성 API가 403 Resource not accessible by integration을 반환했고, 로컬 Git에는 push 인증 정보가 없어 원격 push는 미완료입니다. 이 ZIP을 제공했다는 사실은 GitHub 업로드 완료를 의미하지 않습니다.

## 내용

- Data-Analytics/: 커밋된 전체 파일. 입력 CSV, PCA·코사인 노트북, 점수 계산 코드, 최신 설문, Word·MD, 학습 결과, PNG, 검증 기록.
- Tour_Navigator_Data_Analytics.bundle: 동일 브랜치와 커밋을 복원하는 완전한 Git bundle.

## 인증된 Git 환경에서 그대로 push

ZIP을 풀고 해당 폴더에서 실행하세요. 작업 폴더 이름 Data-Analytics-push가 이미 있으면 다른 새 이름을 선택하세요.

```bash
git clone -b analytics/pca-cosine-survey-v6.2 Tour_Navigator_Data_Analytics.bundle Data-Analytics-push
cd Data-Analytics-push
git remote set-url origin https://github.com/TourLabOrganization/Data-Analytics.git
git push -u origin analytics/pca-cosine-survey-v6.2
```

기본 브랜치 main에 병합하거나 강제 push하지 않습니다. 새로운 원격 브랜치가 다른 커밋으로 이미 존재하면 push 오류를 확인한 뒤 비교해야 합니다.

GitHub 연결을 통한 재시도에는 해당 저장소에 대한 앱의 Contents 쓰기 권한이 필요합니다. 개인 토큰을 대화에 붙여 넣을 필요는 없습니다.

검증: 설문 완료 경로 141,833개, 179개 코스 참조 추천, 기존 Node.js 산식 테스트 통과. 노트북 19개 코드 셀과 분석 결과는 기존 검증 스냅숏과 동일합니다. 상세 검증은 Data-Analytics/verification/release_validation.json에 있습니다.
