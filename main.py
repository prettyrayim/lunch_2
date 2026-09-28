```python
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import re
import calendar
from datetime import datetime


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="송탄고등학교 급식 영양 균형 분석",
    page_icon="🍚",
    layout="wide"
)

st.title("🍚 송탄고등학교 급식 영양 균형 분석")
st.write(
    "탄수화물, 단백질, 지방이 가장 균형적으로 잡힌 날은 "
    "한 달에 얼마나 있을까?"
)

st.info(
    "이 앱에서는 탄수화물·단백질·지방의 에너지 비율이 "
    "각각 적정 범위에 들어오는 날을 '균형적인 날'로 정의합니다."
)


# =========================================================
# 나이스 API 설정
# =========================================================

try:
    API_KEY = st.secrets["NEIS_KEY"]
except Exception:
    st.error(
        "NEIS_KEY가 없습니다.\n\n"
        "Streamlit의 Settings → Secrets에 다음과 같이 입력해주세요.\n\n"
        'NEIS_KEY = "발급받은 인증키"'
    )
    st.stop()


SCHOOL_NAME = "송탄고등학교"

SCHOOL_INFO_URL = "https://open.neis.go.kr/hub/schoolInfo"
MEAL_URL = "https://open.neis.go.kr/hub/mealServiceDietInfo"


# =========================================================
# 학교 정보 조회
# =========================================================

@st.cache_data(ttl=86400)
def find_school():

    params = {
        "KEY": API_KEY,
        "Type": "json",
        "pIndex": 1,
        "pSize": 5,
        "SCHUL_NM": SCHOOL_NAME
    }

    response = requests.get(
        SCHOOL_INFO_URL,
        params=params,
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    if "schoolInfo" not in data:
        return None

    try:
        rows = data["schoolInfo"][1]["row"]
    except (KeyError, IndexError):
        return None

    # 정확히 송탄고등학교인 학교 찾기
    for row in rows:
        if row.get("SCHUL_NM") == SCHOOL_NAME:
            return row

    # 정확히 일치하는 학교가 없으면 첫 번째 결과 사용
    if rows:
        return rows[0]

    return None


school = find_school()

if school is None:
    st.error("송탄고등학교의 학교 정보를 찾을 수 없습니다.")
    st.stop()


ATPT_CODE = school["ATPT_OFCDC_SC_CODE"]
SCHOOL_CODE = school["SD_SCHUL_CODE"]

st.caption(
    f"학교: {school['SCHUL_NM']} | "
    f"교육청 코드: {ATPT_CODE} | "
    f"학교 코드: {SCHOOL_CODE}"
)


# =========================================================
# 연도 / 월 선택
# =========================================================

today = datetime.now()

col1, col2 = st.columns(2)

with col1:
    year = st.number_input(
        "📅 연도",
        min_value=2020,
        max_value=today.year,
        value=today.year,
        step=1
    )

with col2:
    month = st.selectbox(
        "📅 분석할 월",
        range(1, 13),
        index=today.month - 1,
        format_func=lambda x: f"{x}월"
    )


# =========================================================
# 적정 비율
# =========================================================

st.markdown("### ⚖️ 균형 판단 기준")

st.write(
    "학교급식의 영양 기준을 참고하여 다음 범위를 모두 만족하는 날을 "
    "균형적인 날로 판단합니다."
)

c1, c2, c3 = st.columns(3)

with c1:
    st.metric(
        "탄수화물",
        "55~70%"
    )

with c2:
    st.metric(
        "단백질",
        "7~20%"
    )

with c3:
    st.metric(
        "지방",
        "15~30%"
    )

CARB_MIN = 55
CARB_MAX = 70

PROTEIN_MIN = 7
PROTEIN_MAX = 20

FAT_MIN = 15
FAT_MAX = 30


# =========================================================
# 급식 데이터 조회
# =========================================================

@st.cache_data(ttl=3600)
def get_meal_data(year, month):

    last_day = calendar.monthrange(year, month)[1]

    from_date = f"{year}{month:02d}01"
    to_date = f"{year}{month:02d}{last_day:02d}"

    params = {
        "KEY": API_KEY,
        "Type": "json",
        "pIndex": 1,
        "pSize": 1000,
        "ATPT_OFCDC_SC_CODE": ATPT_CODE,
        "SD_SCHUL_CODE": SCHOOL_CODE,
        "MMEAL_SC_CODE": "2",
        "MLSV_FROM_YMD": from_date,
        "MLSV_TO_YMD": to_date
    }

    response = requests.get(
        MEAL_URL,
        params=params,
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    if "mealServiceDietInfo" not in data:
        return []

    try:
        rows = data["mealServiceDietInfo"][1]["row"]
    except (KeyError, IndexError):
        return []

    return rows


try:
    rows = get_meal_data(year, month)
except requests.exceptions.RequestException as e:
    st.error(f"나이스 API를 불러오는 중 오류가 발생했습니다.\n\n{e}")
    st.stop()


if not rows:
    st.warning(
        f"{year}년 {month}월에는 송탄고등학교 중식 데이터가 없습니다."
    )
    st.stop()


# =========================================================
# NTR_INFO 영양정보 추출
# =========================================================

def extract_nutrition(ntr_info):

    if not ntr_info:
        return None, None, None

    # 나이스 NTR_INFO 예:
    # 탄수화물(g) : 165.4<br/>
    # 단백질(g) : 51.4<br/>
    # 지방(g) : 25.4

    carb_match = re.search(
        r"탄수화물\s*\(g\)\s*:\s*([0-9]+(?:\.[0-9]+)?)",
        ntr_info
    )

    protein_match = re.search(
        r"단백질\s*\(g\)\s*:\s*([0-9]+(?:\.[0-9]+)?)",
        ntr_info
    )

    fat_match = re.search(
        r"지방\s*\(g\)\s*:\s*([0-9]+(?:\.[0-9]+)?)",
        ntr_info
    )

    carb = float(carb_match.group(1)) if carb_match else None
    protein = float(protein_match.group(1)) if protein_match else None
    fat = float(fat_match.group(1)) if fat_match else None

    return carb, protein, fat


# =========================================================
# 데이터 분석
# =========================================================

result = []

for row in rows:

    carb, protein, fat = extract_nutrition(
        row.get("NTR_INFO", "")
    )

    # 영양정보가 없는 날은 분석에서 제외
    if carb is None or protein is None or fat is None:
        continue

    # 탄수화물/단백질 = 4 kcal/g
    # 지방 = 9 kcal/g
    carb_kcal = carb * 4
    protein_kcal = protein * 4
    fat_kcal = fat * 9

    total_kcal = carb_kcal + protein_kcal + fat_kcal

    if total_kcal <= 0:
        continue

    # 에너지 비율 계산
    carb_ratio = carb_kcal / total_kcal * 100
    protein_ratio = protein_kcal / total_kcal * 100
    fat_ratio = fat_kcal / total_kcal * 100

    # 각 기준 범위에 들어오는지 확인
    carb_ok = CARB_MIN <= carb_ratio <= CARB_MAX
    protein_ok = PROTEIN_MIN <= protein_ratio <= PROTEIN_MAX
    fat_ok = FAT_MIN <= fat_ratio <= FAT_MAX

    balanced = carb_ok and protein_ok and fat_ok

    result.append({
        "날짜": row["MLSV_YMD"],
        "탄수화물(g)": carb,
        "단백질(g)": protein,
        "지방(g)": fat,
        "탄수화물 비율": carb_ratio,
        "단백질 비율": protein_ratio,
        "지방 비율": fat_ratio,
        "총 에너지(kcal)": total_kcal,
        "균형적인 날": balanced,
        "메뉴": row.get("DDISH_NM", "")
    })


df = pd.DataFrame(result)


if df.empty:
    st.error(
        "해당 월에 탄수화물·단백질·지방 정보가 있는 "
        "급식 데이터가 없습니다."
    )
    st.stop()


# 날짜 변환
df["날짜"] = pd.to_datetime(
    df["날짜"],
    format="%Y%m%d"
)

df = df.sort_values("날짜").reset_index(drop=True)


# =========================================================
# 균형적인 날 계산
# =========================================================

balanced_df = df[df["균형적인 날"]].copy()

total_days = len(df)
balanced_days = len(balanced_df)

if total_days > 0:
    balanced_percent = balanced_days / total_days * 100
else:
    balanced_percent = 0


# =========================================================
# 결과 요약
# =========================================================

st.markdown("## 📊 분석 결과")

c1, c2, c3 = st.columns(3)

with c1:
    st.metric(
        "분석한 급식일",
        f"{total_days}일"
    )

with c2:
    st.metric(
        "균형적인 날",
        f"{balanced_days}일"
    )

with c3:
    st.metric(
        "균형적인 날의 비율",
        f"{balanced_percent:.1f}%"
    )


# =========================================================
# 연구 질문에 대한 답
# =========================================================

st.markdown("### 🔎 연구 질문에 대한 답")

if balanced_days == 0:

    st.warning(
        f"{year}년 {month}월에는 탄수화물·단백질·지방의 "
        f"에너지 비율이 모두 적정 범위에 들어오는 날이 "
        f"없었습니다."
    )

else:

    st.success(
        f"{year}년 {month}월에는 총 {total_days}일의 급식 중 "
        f"**{balanced_days}일**이 탄수화물·단백질·지방의 "
        f"에너지 비율이 모두 적정 범위에 들어왔습니다."
    )


# =========================================================
# 그래프 1
# 날짜별 영양소 비율
# =========================================================

st.markdown("## 📈 날짜별 탄수화물·단백질·지방 비율")

ratio_df = df[
    [
        "날짜",
        "탄수화물 비율",
        "단백질 비율",
        "지방 비율"
    ]
].copy()

ratio_long = ratio_df.melt(
    id_vars="날짜",
    var_name="영양소",
    value_name="비율"
)

fig_ratio = px.line(
    ratio_long,
    x="날짜",
    y="비율",
    color="영양소",
    markers=True,
    labels={
        "날짜": "날짜",
        "비율": "에너지 비율 (%)",
        "영양소": "영양소"
    },
    title="날짜별 3대 영양소 에너지 비율"
)

fig_ratio.add_hrect(
    y0=CARB_MIN,
    y1=CARB_MAX,
    opacity=0.08,
    line_width=0
)

fig_ratio.update_layout(
    hovermode="x unified"
)

st.plotly_chart(
    fig_ratio,
    use_container_width=True
)


# =========================================================
# 그래프 2
# 균형적인 날 / 아닌 날
# =========================================================

st.markdown("## 🥗 한눈에 보는 균형적인 날")

chart_df = df.copy()

chart_df["판정"] = chart_df["균형적인 날"].map({
    True: "균형적인 날",
    False: "기준을 벗어난 날"
})

fig_balance = px.bar(
    chart_df,
    x="날짜",
    y="총 에너지(kcal)",
    color="판정",
    title="날짜별 급식과 균형 여부",
    labels={
        "날짜": "날짜",
        "총 에너지(kcal)": "총 에너지(kcal)",
        "판정": "판정"
    },
    hover_data=[
        "탄수화물 비율",
        "단백질 비율",
        "지방 비율"
    ]
)

st.plotly_chart(
    fig_balance,
    use_container_width=True
)


# =========================================================
# 균형적인 날 목록
# =========================================================

st.markdown("## 📅 균형적인 날 목록")

if balanced_df.empty:

    st.write("균형적인 날이 없습니다.")

else:

    display_df = balanced_df[
        [
            "날짜",
            "탄수화물(g)",
            "단백질(g)",
            "지방(g)",
            "탄수화물 비율",
            "단백질 비율",
            "지방 비율"
        ]
    ].copy()

    display_df["날짜"] = display_df["날짜"].dt.strftime(
        "%Y-%m-%d"
    )

    display_df = display_df.rename(
        columns={
            "탄수화물 비율": "탄수화물 비율(%)",
            "단백질 비율": "단백질 비율(%)",
            "지방 비율": "지방 비율(%)"
        }
    )

    st.dataframe(
        display_df.style.format({
            "탄수화물(g)": "{:.1f}",
            "단백질(g)": "{:.1f}",
            "지방(g)": "{:.1f}",
            "탄수화물 비율(%)": "{:.1f}",
            "단백질 비율(%)": "{:.1f}",
            "지방 비율(%)": "{:.1f}"
        }),
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# 가장 균형적인 날 찾기
# =========================================================

st.markdown("## 🏆 기준에 가장 가까운 날")

def distance_from_range(value, minimum, maximum):

    if value < minimum:
        return minimum - value

    if value > maximum:
        return value - maximum

    return 0


df["균형 거리"] = (
    df["탄수화물 비율"].apply(
        lambda x: distance_from_range(
            x, CARB_MIN, CARB_MAX
        )
    )
    +
    df["단백질 비율"].apply(
        lambda x: distance_from_range(
            x, PROTEIN_MIN, PROTEIN_MAX
        )
    )
    +
    df["지방 비율"].apply(
        lambda x: distance_from_range(
            x, FAT_MIN, FAT_MAX
        )
    )
)

best_day = df.sort_values(
    "균형 거리",
    ascending=True
).iloc[0]


b1, b2, b3, b4 = st.columns(4)

with b1:
    st.metric(
        "날짜",
        best_day["날짜"].strftime("%m월 %d일")
    )

with b2:
    st.metric(
        "탄수화물",
        f"{best_day['탄수화물 비율']:.1f}%"
    )

with b3:
    st.metric(
        "단백질",
        f"{best_day['단백질 비율']:.1f}%"
    )

with b4:
    st.metric(
        "지방",
        f"{best_day['지방 비율']:.1f}%"
    )


# =========================================================
# 전체 데이터
# =========================================================

with st.expander("📋 전체 분석 데이터 보기"):

    all_df = df[
        [
            "날짜",
            "탄수화물(g)",
            "단백질(g)",
            "지방(g)",
            "탄수화물 비율",
            "단백질 비율",
            "지방 비율",
            "총 에너지(kcal)",
            "균형적인 날"
        ]
    ].copy()

    all_df["날짜"] = all_df["날짜"].dt.strftime(
        "%Y-%m-%d"
    )

    all_df = all_df.rename(
        columns={
            "탄수화물 비율": "탄수화물 비율(%)",
            "단백질 비율": "단백질 비율(%)",
            "지방 비율": "지방 비율(%)"
        }
    )

    st.dataframe(
        all_df.style.format({
            "탄수화물(g)": "{:.1f}",
            "단백질(g)": "{:.1f}",
            "지방(g)": "{:.1f}",
            "탄수화물 비율(%)": "{:.1f}",
            "단백질 비율(%)": "{:.1f}",
            "지방 비율(%)": "{:.1f}",
            "총 에너지(kcal)": "{:.1f}"
        }),
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# 데이터 출처
# =========================================================

st.caption(
    "데이터 출처: 나이스 교육정보 개방 포털 - 학교기본정보 및 급식식단정보"
)
```
