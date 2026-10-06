# 미국 국가안보용 unobligated HALEU: 2027–2029 적격 공급 재조사

기준일: 2026-10-06. 기존 TARGET: `unobligated-haleu-us-qualified-supply`. 최종 상태: **OBSERVE**. 정부·사업자 원문 34개 문서를 검토했다. 동일 발표의 IR/SEC 재게시, 원료 공급·연료 제조·원자로 award는 독립 수요로 중복 계수하지 않았다. 원문 위치와 접근 범위는 [sources.json](sources.json), 구조화된 판단은 [history-append.json](history-append.json)에 있다.

목적은 2027–2029년 같은 기간·고객·농축도·형상의 확정 또는 강한 필요량이 실제 사용 가능한 unobligated 적격 공급량보다 큰지를 검증하는 것이다. 기존 OBSERVE와 기업 투자 지표는 판단 근거로 사용하지 않았다. 과거 history는 수정하지 않는다. Objective Lock은 `bct-objective-1`, SHA256 `0b2de0186c92fa0c5466539b42cdf5a4fba164a7c9fb62092e396cb4ebe0cff7`; JSON export에 `bct.objective_lock.stamp_export`를 적용한다. 이번 요청 기반 조사는 EARLY·strict·예측 성공으로 집계하지 않는다.

## 판단과 가장 중요한 범위 수정

확정 HALEU 계약과 국가안보 원자로 배치 목표는 실재한다. 그러나 **군사시설의 전력용 microreactor가 반드시 unobligated HALEU를 써야 한다는 전제부터 아직 확정되지 않았다.** GAO는 DoD/DOE 판단이 미결정이라고 기록한다. 같은 보고서에서 현재 16기 Centrus 시범 cascade는 외국 부품을 포함해 해당 구성의 산출물이 unobligated가 아니라고 설명한다. 회사가 AC100 기술의 unobligated 공급 가능성을 강조하는 것과 실제 구성·batch 적격성은 별개다. 이후 부품 대체 완료와 batch release 자료는 확보하지 못했다. [S01,S02]

따라서 미국산, 비러시아산, HALEU, unobligated, 특정 원자로에 적합한 완성 연료는 각각 다른 조건이다. 민간 첨단원자로 전체 수요나 정부의 요청 대비 부족 전망을 이 TARGET의 확정 수요로 옮기지 않는다. 미확인은 수요 0·공급 0 또는 공급 충분을 뜻하지 않는다.

## 실제 필요량과 필요 시점

| 프로젝트/관계 | 확인한 원문상의 강도·물량 | 공개 일정 | 2027–2029 대조에 남은 공백 |
|---|---|---|---|
| Antares–Standard Nuclear | 2026년 8월 연료계약: **기본 1MTU HALEU TRISO**, 고객 옵션 **추가 최대 7MTU** | 향후 수년, 연도별 납품량 미공개 | 1MTU의 연도별 배분·assay·납품 기한·unobligated 조항 UNKNOWN. 옵션 7MTU는 확정 수요 제외 [S09] |
| Centrus–Antares | 9/17 확정 다년 HALEU 계약·선급금 | decade 종료 전 인도 시작; 회사는 2027 발전·2028 초기 군사배치 계획 | 2027 또는 2028 필수 납기라는 증명 없음. 원료 공급과 위 제조계약은 같은 코어일 수 있으므로 합산 금지 [S02] |
| Army Janus | 8/26 다섯 업체와 milestone agreements, 최대 $2.2bn | FY2027–2031 milestone 지급; 최초 원자로 **2028년 9월 목표** | >20기 기대치를 연도별 확정 코어로 사용하지 않음. 대수·kgU·적격 의무·loading일 UNKNOWN [S06] |
| Radiant Janus | 최대 $750m 계약, **2030년까지 Kaleidos 15기** | 2030년 종료 목표 | 15기가 2028년 인도된다는 해석 금지. core당 kgU·연도별 대수 UNKNOWN [S07] |
| Radiant–Standard / Centrus | 8월 확정 연료 제조 장기계약, 9/9 Centrus 장기 원료 계약·선급금 | 제조계약은 early2030s 지원, Centrus 인도는 decade 종료 전 시작 | May term sheet와 August definitive 계약을 두 번 세지 않음. DOE 배정·원료·제조를 별도 최종수요로 합산하지 않음 [S08–S12] |
| X-energy–Centrus | 8/6 확정 LEU·HALEU enrichment 계약·선급금 | 연도별 HALEU 물량·납기 미공개 | LEU와 HALEU 구분, 민간 고객의 unobligated 필요 미입증 [S13] |
| Kairos Hermes 1 / Hermes 2 | Hermes용 DOE HALEU 계약 최종화, LANL 제조; Hermes2 4월 착공 | startup/operation 연료 지원 | 발전 목표·착공이 연도별 확정 kgU를 제공하지 않음. DOE 배정과 겹치는 재고는 잔여 공급으로 재계수 금지 [S17,S18] |
| NASA SR1 Freedom | DOE 3차 조건부 배정, HALEU 전력장치 계획 | late2028 발사, 2029 도착 | kgU·assay·unobligated 의무·최종 배정계약 UNKNOWN. 발사 전 코어를 2029 도착 수요로 다시 세지 않음 [S14,S16] |
| Project Pele / 초기 Antares / 초기 Radiant | BWXT Pele full core 2025 납품; Antares prototype 2026 criticality 연료; Radiant DOE feed 실제 수령·core 제조 | 이미 실현된 초기 연료 공급 | 2027 이후 새 코어나 재장전 의무를 확인 없이 부여하지 않음 [S11,S19,S20] |
| NNSA tritium·naval propulsion | 각각 기존 unobligated LEU·HEU 임무 | 기존 비축으로 장기 임무 유지 | HALEU의 2027–2029 구매 수요와 구분. 기존 임무 비축을 microreactor 자유 가용 물량으로 전환하지 않음 [S01,S32] |

| 연도 | 실제 공개된 필요 시점의 근거 | 확정·강한 총 HALEU kgU | 그중 필수 unobligated kgU | 같은 연도 실제 공급 충돌 |
|---|---|---|---|---|
| 2027 | Antares 첫 발전 계획; Janus milestone 기간 시작 | UNKNOWN | UNKNOWN | 입증되지 않음 |
| 2028 | Janus 첫 원자로 Sep 목표; Antares 초기배치 계획; NASA late2028 발사 | UNKNOWN | UNKNOWN | 입증되지 않음 |
| 2029 | Janus2030 목표를 향한 배치 및 Centrus 장기계약 인도 시작 범위 | UNKNOWN | UNKNOWN | 입증되지 않음 |

필요일은 발전일보다 앞선 원료 입고·제조 투입·core loading일이어야 한다. 그 차이는 공개되지 않아 임의 lead time을 넣지 않는다. 1MTU 확정 계약을 각 연도에 균등 배분하지 않는다. 미래 ramp는 기준일 현재 계획이며 관측된 2027–2029 생산 실적이 아니다.

## enrichment와 실제 고객 가용량

| 공급 경로 | 실제 확인한 상태 | 명목/계약 수치 | 적격 미예약 물량으로 계산할 수 없는 이유 |
|---|---|---|---|
| Piketon 시범 cascade | 16기; 2026년 6월까지 누적 **>1,900kg HALEU UF6**, 정부 소유 [S03,S04] | 900kg UF6 연간 lot는 kgU와 다름 | 기존 생산은 DOE 소유·배정 대상. 외국 부품 구성, postSept30 재가동·unobligated release UNKNOWN [S01,S04] |
| 시범 계약 연장 | 7–9월 Option1b는 **생산 없이 유지·보관**, $15m | 추가 생산 옵션과 상업전환은 별개 | 9월30일 후 commercial transition agreement·실제 운전 증거 미확보. 2027에도 연속 생산한다고 가정하지 않음 [S04] |
| Centrus 신규 HALEU | 첫 신규 capacity **2029 예상**; 초기 연간 **12metrictons HALEU** 증설 계획 [S03] | 이론적 정상 가동 규모 | 2029 full-year kgU, 가동 분기, yield, 고객 배정, license 변경·DOE readiness·부품 구성 UNKNOWN |
| General Matter | 9/28 첫 NRC 신청, HanfordFMEF 평가·lease [S28,S29] | 정부 award·투자 계획 | 신청≠인가≠가동≠적격19.75%batch. 2027–2029 kgU UNKNOWN |
| Urenco 미국/영국 | 미국 LEU·최대10%LEU+ 경로; 영국 higher-assay 계획은2031 [S27] | 일반 LEU SWU·10% 제품 | 19.75% 고객과 assay 불일치; 외국 기술 의무 별개;2031은 범위 밖 |
| DOE HALEU Availability | **2028말21.2MTU**,2030말23.4MTU 누적 공급 전망(2026년4월 기준) [S01] | 연간 CAPA나 현재 재고 아님 | 배정·사용·형상·obligated status·회수량 중복 미공개;2029 값 보간 금지 |

단위 오류를 막기 위해 GAO의 fluorine 제거 후 설명을 참조한다. UF6 물량을 MTU와 동일하게 취급하지 않고, 제품형태 전환량을 fabrication 양품량으로도 취급하지 않는다. 따라서 회사의 >1,900kgUF6를 1.9MTU 미예약 연료로 넣지 않았다. [S01,S03]

### $900m DOE 계약 원문이 실제로 의무화한 시점

SEC Exhibit10.3에 공개된 ACO task order **89243226FNE400212**의 수행기간은 2026-07-06~2036-07-05이다. CLIN1은 새 capacity 설치·operational readiness와 nominal19.75% **1MTU** HALEU를 DOE가 인수하도록 **2032-07-05**까지 요구한다. CLIN2/3의 각각5MTU는 아직 행사되지 않은 옵션이다. 계약은 더 이른 상업운전을 허용하므로2032가 최초 공급 가능일이라는 뜻도 아니다. [S05]

이 task order는 NNSA 임무 지원을 요구하지 않는다. 미국 소재 시설·신규 농축 CAPA를 이유로 곧바로 국가안보용 unobligated 적격 공급으로 세지 않는다. fresh mined/converted feed 조건도 있지만, 그 조건 하나가 모든 부품·기술·연료의 국제 의무를 제거하지 않는다. NNSA의120기/cascade 계획은 별도 LEU 임무 계획으로서 시범16기나12MTHALEU의 ready date를 입증하지 않는다. [S01,S05]

## 이미 배정된 공급과 relief

DOE allocation round2(2025-08)는 Antares·Standard Nuclear·ACU/Natura 등을, round3(2026-07)는 NASA·RadiantBuckley 등을 포함한다. 조건부 배정은 현물 납품과 다르다. Kairos의 finalized 계약, Radiant가 실제 받은 DOE feed, Centrus 정부 생산, 민간 prepayment 물량을 서로 독립적인 잔여 재고로 더하지 않는다. 공개된 고객별 annual allocation ledger가 없어 신규 고객에 남은 양은 **UNKNOWN**이다. [S14,S15,S17,S11]

| relief 경로 | 사실 | 계산에서 유지한 제한 |
|---|---|---|
| Japan 반환 HALEU | 2026-05 실제1.7metricton shipment, Y12에서 reconstitution 예정 [S24] | kgU basis·최종 적격 batch·배정·21.2MTU와의 중복 UNKNOWN |
| SRS 회수 | 2026-02 H Canyon uranium recovery 재개 결정, 잠재 최대19metrictons [S25] | 잠재 자원량≠즉시 사용 가능 HALEU. 처리 일정·수율·불순물·연도별 release UNKNOWN |
| HEU downblend | 2025 amendedROD의2.2MTHEU→3.1MTHALEU 경로 [S26] | 의사결정·평가상의 총량을 연도별 완료 재고로 전환하지 않음 |
| EO fuel bank | 20MT 관련 지시와 필수 국가안보 비축 보전 [S32] | 이미 확보·무제약 배정된20MT가 아니며 DOE 전망에 다시 더하지 않음 |
| 공급계약·증설 | prepayment, 신규 enrichment·TRISO시설 | 시작 시점·acceptance·ramp·allocation을 확인한 후 해당 연도에만 반영 |
| 원자로 일정 변화 | 목표 지연 시 연료 필요 시점도 이동 가능 | 실제 취소/변경 문서 없이 kg를 삭제하지 않으며 시나리오상의 반증으로만 기록 |

## 어느 단계가 가장 좁은가

**입증된 전체 공급망의 최협소 단계는 UNKNOWN.** 수량 대조가 되지 않으므로 “enrichment보다 fabrication이 더 부족”하다고 판정하지 않는다. 다만 농축 capacity를 고객 사용 가능 연료로 바꾸는 과정에서 다음 gate를 구분한다.

| 단계 | 실제 증거 | 후보/판정 |
|---|---|---|
| conversion 및 unobligated cascade qualification | 미국 내 원천·부품 적격과 실제 구성의 mismatch | 부모TARGET의 적격성 gate로 기록. 연도별 hard shortfall 미확인 [S01] |
| **19.75% UF6 deconversion → oxide/metal** | GAO 제약 언급; DOE6업체 IDIQ, ACO bid는 operationalline 증명 아님 | 가장 구체적인 물리 공정 위험 후보. 처리량·recipe별 필요량 UNKNOWN [S01,S23,S04] |
| TRISO 제조 | BWXT·Standard·LANL 실제 제조/납품 | 제조능력 자체가 없다는 해석 반증. GAO 이해관계자는 제조 전반을 대체로 제한으로 보지 않음 [S01,S11,S19,S20] |
| Standard 확장 | SN-0 최대0.5MTU/년; SN-TN/SN-ID 각초기1MTU/년, 각2.5까지 확장 계획; Q42026 authorization목표 | 계획 CAPA 합계를 해당 assay 양품·고객 잔여 슬롯으로 계산하지 않음 [S09,S10] |
| TRISO-X TX1 | 2026-02 Part70 license, early2028 생산 기대,700,000pebbles/년 명목 | 운영 전 inspection·제품 고객 qualification·kgU/pebble·수율·배정 UNKNOWN [S21] |
| Framatome Richland | 2026-06 license<10%; JV2027 제조 목표 | <10%제조 승인으로19.75%고객 공급을 증명할 수 없음 [S09] |
| Natrium 금속 연료 | Framatome–TerraPower metalpuck 제조 성공 | 시험은 depleteduranium;19.75HALEU 상업 양품 CAPA 미확인 [S22] |
| 운송·수령 | 기존 UF6/TRISO packages 및 실제 feedshipment; NAC신규package 개발 | 전면적 운송 불가능 반증. 고객별 수령허가·assay·형상·cask 잔여 슬롯은 UNKNOWN [S11,S20,S30,S31] |

작은 실제 원료 receipt와 데모 core 성공은 mass-commercial availability를 입증하지 않지만 공급이 완전히 끊겼다는 주장에는 반증이다. GAO의 UF6 deconversion 제약을 모든 scrap-to-oxide나 모든 TRISO 제조 부재로 확대하지 않는다. 하위 후보는 이 부모 history에만 저장하며 새 TARGET을 만들지 않는다.

## 대체가 실제로 가능한가

**LEU→HALEU 단순 blending:** 목표 assay보다 낮은 두 재료를 섞어 목표보다 높은 assay를 얻을 수 없다. 19.75%가 필요하면 재농축 또는 더 높은 assay의 투입물(예:HEU)을 통한 downblend가 필요하다. 재농축은 qualification gate를 우회하지 못한다. 회수 HALEU·HEU downblend는 실제 경로지만 provenance·불순물·형상·정부 release를 확인해야 한다. 특정 고객의<10%대체는 재설계·허가 조건이 확인되어야 한다.

**러시아산:** PublicLaw118-62는 상업 수입 제한과 waiver의2028-01-01 종료를 명시한다. 동시에 DOE가 국가안보·비확산 목적으로 또는 DOE계약에 따라 수입하는 경우의 예외도 명시한다. 따라서 안보용 수입이 법률상 무조건 불가능하다고 쓰지 않는다. 그렇다고 예외가 실제 계약·수출허가·unobligated 적격 물량을 보장하지도 않는다. 추가 제재 H.R.5334 enrolled text의 section111도 읽었으나 개별 시행·승인 물량은 UNKNOWN이다. 공개된 실제 이TARGET용 계약이 없어2027–2029 잔여 공급에 넣지 않는다. [S33,S34]

**동맹국·외국산:** 비러시아 공급이 가능해도 foreignpeacefuluse 의무를 제거하지 않는다. assay·feed 및 기술의 국제 의무·고객 허가가 맞아야 한다. 영국의2031 higher-assay ramp는 이 조사 기간을 직접 구제하지 못한다. 미국의LEU+나Richland<10% 제품은 그 농축도용 고객에는 유용할 수 있으나19.75%코어의 확정 대체가 아니다. [S27,S09]

## 승격·반증 조건 및 결정적 UNKNOWN

승격하려면 최소한 프로젝트별 unobligated 필수 조항과 연도별 kgU·필요일이 확인되고, 같은 assay/형상에 대해 재고·정부 배정·고객 예약을 차감한 적격 산출물 또는 슬롯의 공급일이 확인되어야 한다. 그 후 특정 분기/연도에 부족을 검증한다. 낮은 명목 CAPA와 높은 광범위 전망의 비교만으로 승격하지 않는다.

결정적 UNKNOWN은 (1)DoD/NASA의 적용 의무, (2)연도별 core/refuel·assay·입고일, (3)Antares1MTU 납품 분할과7MTU option행사, (4)DOE재고·배정·provenance·release, (5)Centrus 재가동·외국부품대체·NRC/DOE 변경승인, (6)2029 cascade ramp·yield·예약, (7)oxide/metal deconversion taskorder·처리량·leadtime, (8)fabricator 고객 recipe양품·미예약 슬롯, (9)운송/site수령 허가, (10)회수·반환 stock과 누적전망의 중복이다.

DROP도 근거가 부족하다. 구체적 확정계약·정부프로그램·공급 적격성 gate가 존재하고, 일반 공급의 요청 대비 부족 위험은 남아 있다. 현재 판단은 **OBSERVE: 위험은 조사할 가치가 있으나 2027·2028·2029의 `확정/강한 필수 unobligated 수요 > 실제 가용 적격 잔여 공급`은 모두 미입증**이다. 추가 조사에서 좁은 공정의 같은기간 충돌이 드러나면 부모 기록에 먼저 append하고 정식 TARGET 분리를 검토한다.

## 검증과 저장

기존 history·다른 TARGET 불변, 중복 TARGET 없음, operation idempotence, 원격CAS와 readback을 검증한다. canonical 원장은 `future-bottleneck-data:future-tracking.json`의 해당 TARGET history이며, 이 조사 패키지는 main의 `docs/registrations/unobligated-haleu-20261006/`에 저장한다. 실제 수행 결과와 commit/PR 정보는 `verification.json`, `storage-receipt.json`, `main-reflection.json`에 기록한다. main 반영 완료라는 표현은 원격 파일 확인 후에만 사용한다.
