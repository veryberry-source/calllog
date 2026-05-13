import streamlit as st
import pandas as pd
import numpy as np

# 페이지 설정
st.set_page_config(page_title="선거여론조사 콜로그 분석", layout="wide")

st.title("🗳️ 선거여론조사 콜로그 분석")
st.caption("응답률 산출 및 특성별 집계")

# 1. 콜로그 매핑 딕셔너리
mapping_dict = {
    "결번": "1 결번",
    "FAX": "2 비적격", "조사대상아님": "2 비적격", "오류처리": "2 비적격", "회사": "2 비적격",
    "비수신": "3 비수신", "응답자부재": "3 비수신", "대기중종료": "3 비수신", "통화중": "3 비수신",
    "단순거절": "4 거절중단", "진행": "4 거절중단", "중단": "4 거절중단", "예약": "4 거절중단", "운전중": "4 거절중단", "거절": "4 거절중단",
    "면접성공": "5 면접성공"
}

# 파일 업로드 섹션
col1, col2 = st.columns(2)
with col1:
    log_file = st.file_uploader("1️⃣ 콜로그 엑셀 파일 (필수)", type=["xlsx"])
with col2:
    attr_file = st.file_uploader("2️⃣ 번호 특성 파일 (선택)", type=["xlsx"])

if log_file:
    # 1. 콜로그 데이터 로드 및 정리
    df_log = pd.read_excel(log_file)
    df_log.columns = df_log.columns.str.strip()
    
    log_req = ['TEL', 'GUBUN', 'CallLog', 'ORDER']
    missing_cols = [c for c in log_req if c not in df_log.columns]
    
    if not missing_cols:
        # 콜로그 분류 변수 생성
        df_log['Result_Cat'] = df_log['CallLog'].map(mapping_dict).fillna("미분류")
        
        # 번호별 최종(최신 ORDER) 데이터 유지 (ORDER 변수 보존)
        final_df = df_log.sort_values(['TEL', 'ORDER'], ascending=[True, True]).groupby('TEL').tail(1).reset_index(drop=True)
        
        # 2. 번호 특성 파일 처리 및 통합
        if attr_file:
            df_attr = pd.read_excel(attr_file)
            df_attr.columns = df_attr.columns.str.strip()
            
            # 안심번호 변환 및 매칭
            if '050 안심번호' in df_attr.columns:
                df_attr = df_attr.rename(columns={'050 안심번호': 'TEL'})
            
            if 'TEL' in df_attr.columns:
                df_attr['TEL'] = df_attr['TEL'].astype(str).str.replace('-', '')
                final_df['TEL'] = final_df['TEL'].astype(str).str.replace('-', '')
                # 콜로그 기준 Left Join
                final_df = pd.merge(final_df, df_attr, on='TEL', how='left', suffixes=('', '_attr'))
                st.success("✅ 번호 특성 데이터가 성공적으로 통합되었습니다.")

        # --- 교차 분석 설정 ---
        st.sidebar.header("📊 분석 설정")
        exclude_cols = ['TEL', 'CallLog', 'Result_Cat'] # ORDER는 분석 대상에서 제외하되 데이터에는 유지
        available_vars = [c for c in final_df.columns if c not in exclude_cols]
        
        default_index = available_vars.index('GUBUN') if 'GUBUN' in available_vars else 0
        cross_var = st.sidebar.selectbox("교차 분석 기준 변수 선택", available_vars, index=default_index)
        
        # --- 지표 계산 함수 (전체 합계 포함) ---
        def calculate_nesdc_metrics(data, group_col):
            # 카테고리 정의
            categories = ["1 결번", "2 비적격", "3 비수신", "4 거절중단", "5 면접성공"]
            
            # 1. 그룹별 집계
            summary = data.groupby([group_col, 'Result_Cat']).size().unstack(fill_value=0)
            for cat in categories:
                if cat not in summary.columns: summary[cat] = 0
            summary = summary[categories]
            
            # 2. 전체(Total) 행 계산
            total_sum = summary.sum().to_frame().T
            total_sum.index = ['[전체]']
            
            # 3. 데이터 결합 (전체를 맨 위로)
            combined = pd.concat([total_sum, summary])
            
            # 4. 여심위 공식 적용
            combined['전체(N)'] = combined.sum(axis=1)
            combined['성공+거절'] = combined['5 면접성공'] + combined['4 거절중단']
            combined['e'] = (combined['성공+거절'] / (combined['성공+거절'] + combined['2 비적격'])).fillna(0)
            combined['접촉률분모'] = combined['성공+거절'] + (combined['3 비수신'] * combined['e']).round(0)
            combined['응답률분모'] = combined['성공+거절']
            
            combined['접촉률(%)'] = (combined['성공+거절'] / combined['접촉률분모'] * 100).fillna(0).round(1)
            combined['응답률(%)'] = (combined['5 면접성공'] / combined['성공+거절'] * 100).fillna(0).round(1)
            combined['RR(%)'] = (combined['접촉률(%)'] * combined['응답률(%)'] / 100).fillna(0).round(1)
            
            return combined[["1 결번", "2 비적격", "3 비수신", "4 거절중단", "5 면접성공", "전체(N)", "접촉률분모","응답률분모", "접촉률(%)", "응답률(%)", "RR(%)"]]

        # 결과 테이블 생성
        result_table = calculate_nesdc_metrics(final_df, cross_var)
        
        st.subheader(f"📍 {cross_var}별 분석 결과 (상단: 전체 합계)")
        st.dataframe(result_table.style.format({
            '접촉률분모': '{:.0f}', '접촉분자': '{:,}','접촉률(%)': '{:.1f}%', '응답률(%)': '{:.1f}%', 'RR(%)': '{:.1f}%'
        }))
        
        # 상세 데이터 및 다운로드
        with st.expander("🔍 통합 데이터(최종 콜 기준) 확인"):
            st.write(final_df) # ORDER 변수가 포함된 최종 데이터셋

        st.download_button(
            label="통합 분석 결과 다운로드 (CSV)",
            data=final_df.to_csv(index=False).encode('utf-8-sig'),
            file_name="integrated_survey_data.csv",
            mime="text/csv"
        )
    else:
        st.error(f"필수 컬럼이 부족합니다: {missing_cols}")
else:
    st.info("좌측 상단에서 콜로그 파일을 업로드하여 분석을 시작하세요.")