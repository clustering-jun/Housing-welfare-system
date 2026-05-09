# Data Information

본 분석에 사용된 데이터는 국토지리정보원 및 공공데이터포털에서 제공받거나 다운로드하여 활용한 자료입니다.
관련 데이터는 「공간정보의 구축 및 관리 등에 관한 법률」, 「국토교통부 국가공간정보 보안관리규정」, 「국토지리정보원 공간정보 제공에 관한 규정」 등 관련 법령 및 규정에 따라 본 저장소에서는 원본 데이터를 공개하지 않습니다.
데이터 활용을 원하시는 경우, 각 기관의 공식 절차를 통해 직접 데이터를 신청하거나 다운로드하시기 바랍니다.

The data used in this analysis were obtained from or downloaded through the National Geographic Information Institute and the Public Data Portal.
In accordance with relevant laws and regulations, including the Act on the Establishment, Management, etc. of Spatial Data, the Ministry of Land, Infrastructure and Transport National Spatial Information Security Management Regulation, and the National Geographic Information Institute Regulations on the Provision of Spatial Information, the original datasets are not publicly distributed in this repository.
If you wish to use the data, please apply for or download them directly through the official procedures provided by each institution.

## Structure

```text
data/
  raw/        # 원본 데이터
  interim/    # 전처리 중간 산출물
  processed/  # 모델/API 입력용 정제 데이터
  external/   # 외부 참조 데이터
```

## Expected Files

- `data/processed/result_vulnerability_index.csv`: 추천 API 입력 데이터
- `data/raw/community/RentalHousing_CommunityStatus.csv`: 커뮤니티 프로그램 원본 데이터
- `data/processed/unique_community_names_cleaned.txt`: 정제된 커뮤니티 프로그램명 목록