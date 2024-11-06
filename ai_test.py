import streamlit as st
import pandas as pd
import mysql.connector
from datetime import datetime
import time
import re
import os
from dotenv import load_dotenv

# Set page config at the very beginning
st.set_page_config(page_title="AI 역량 평가", page_icon=":brain:", layout="wide")

# Load environment variables
load_dotenv()

# Database connection parameters
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_DATABASE = os.getenv("DB_DATABASE")

# CSS를 사용하여 버튼 스타일 조정
st.markdown("""
<style>
    .stButton > button {
        width: 100%;
    }
    .custom-button-container {
        display: flex;
        justify-content: center;
        gap: 20px;
    }
</style>
""", unsafe_allow_html=True)

# Load questions
@st.cache_data
def load_questions():
    return pd.read_csv('ai_test_update.csv')

questions = load_questions()

# Function to validate email
def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

# Function to save data to MySQL
def save_to_database(data):
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_DATABASE
        )
        cursor = connection.cursor()

        query = """
        INSERT INTO ai_assessment_results 
        (name, email, date, total_time, q1, q2, q3, q4, q5, q6, q7, q8, q9, q10,
        q11, q12, q13, q14, q15, q16, q17, q18, q19, q20,
        q21, q22, q23, q24, q25, q26, q27, q28, q29, q30,
        q31, q32, q33, q34, q35, q36, q37, q38, q39, q40,
        t1, t2, t3, t4, t5, t6, t7, t8, t9, t10,
        t11, t12, t13, t14, t15, t16, t17, t18, t19, t20,
        t21, t22, t23, t24, t25, t26, t27, t28, t29, t30,
        t31, t32, t33, t34, t35, t36, t37, t38, t39, t40)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s)
        """
        
        query_with_data = query % tuple(data.values())
        print(query_with_data)  # 출력

        cursor.execute(query, tuple(data.values()))
        connection.commit()
        
        return True
    except mysql.connector.Error as error:
        st.error(f"Failed to save results to database: {error}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# 유효한 값인지 검사하는 함수 추가
def is_valid_answer(answer_index):
    return 0 <= answer_index <= 4

# Streamlit app
st.markdown("""
    <h1 style='text-align: center;'>AI 역량 평가</h1>
""", unsafe_allow_html=True)

if 'state' not in st.session_state:
    st.session_state.state = 'intro'
    st.session_state.start_time = None
    st.session_state.answers = {}
    st.session_state.times = {}
    st.session_state.question_start_times = {}

if st.session_state.state == 'intro':
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.write("AI 역량 평가에 오신 것을 환영합니다.")
        name = st.text_input("이름을 입력해주세요")
        email = st.text_input("이메일을 입력해주세요")
        
        if st.button("시작하기"):
            if not name or not email:
                st.warning("이름과 이메일을 모두 입력해주세요.")
            elif not is_valid_email(email):
                st.warning("올바른 이메일 형식이 아닙니다.")
            else:
                st.session_state.name = name
                st.session_state.email = email
                st.session_state.state = 'disclaimer'
                st.rerun()

elif st.session_state.state == 'disclaimer':
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("""
            본 진단 평가는 AI 역량을 평가하기 위해 개발되었습니다.

            - **총 문항 수:** 40개
            - **제한 시간:** 60분

            ## 주의사항

            - 내용을 잘 모르는 경우에는 "잘 모르겠다"라고 응답하셔도 괜찮습니다.
            - 평가 결과는 입력한 이메일로 전송됩니다.
            - 모든 정보는 익명으로 관리됩니다.

            **아래 확인 버튼을 누르시면 제반 사항에 대해 동의한 것으로 판단하고 평가를 시작합니다.**
            """)

        if st.button("확인 및 평가 시작"):
            st.session_state.state = 'test'
            st.session_state.start_time = time.time()
            st.session_state.question_number = 0
            st.rerun()

elif st.session_state.state == 'test':
    if 'start_time' not in st.session_state:
        st.session_state.start_time = time.time()

    # 남은 시간을 계산하는 부분
    total_time = 3600  # 60분 = 3600초
    elapsed_time = time.time() - st.session_state.start_time
    remaining_time = max(total_time - elapsed_time, 0)
    
    minutes = int(remaining_time // 60)
    seconds = int(remaining_time % 60)
    
    st.markdown(f"남은 시간: {minutes}분 {seconds}초")

    # 진행 막대 표시 (감소하는 방향으로 변경)
    progress = remaining_time / total_time
    st.progress(progress)

    if st.session_state.question_number < len(questions):
        question = questions.iloc[st.session_state.question_number]
        current_question_number = st.session_state.question_number + 1
        st.write(f"문항 {current_question_number}/40")
        st.markdown(question['Problem'], unsafe_allow_html=True)
        
        if pd.notna(question['Figure']):
            st.image(f"images/{question['Figure']}")
        
        choices = [choice.strip() for choice in question['Choice'].split('\n') if choice.strip()]
        choices.append("⑤ 모르겠음")
        
        # 현재 문제의 시작 시간 기록
        if f"start_time_q{current_question_number}" not in st.session_state.question_start_times:
            st.session_state.question_start_times[f"start_time_q{current_question_number}"] = time.time()

        answer = st.radio("답을 선택하세요:", choices, key=f"q{current_question_number}", index=4)
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("이전 문제", disabled=current_question_number == 1):
                if current_question_number > 1:
                    # 현재 문제의 소요 시간 업데이트
                    question_time = time.time() - st.session_state.question_start_times[f"start_time_q{current_question_number}"]
                    st.session_state.times[f"t{current_question_number}"] = st.session_state.times.get(f"t{current_question_number}", 0) + question_time
                    
                    st.session_state.question_number -= 1
                    st.rerun()
                else:
                    st.warning("첫 번째 문항입니다.")

        with col2:
            if st.button("다음 문제"):
                if answer is None:
                    st.warning("답을 선택해주세요.")
                else:
                    # 사용자의 답이 유효한 값인지 확인
                    selected_answer_index = choices.index(answer) + 1 if answer != "⑤ 모르겠음" else 0
                    
                    print('selected answer:', selected_answer_index)
                    
                    if not is_valid_answer(selected_answer_index):
                        st.error("잘못된 답변이 선택되었습니다. 유효한 답변만 입력해주세요.")
                    else:
                        # 현재 문제의 소요 시간 계산 및 업데이트
                        question_time = time.time() - st.session_state.question_start_times[f"start_time_q{current_question_number}"]
                        st.session_state.times[f"t{current_question_number}"] = st.session_state.times.get(f"t{current_question_number}", 0) + question_time
                        
                        st.session_state.answers[f"q{current_question_number}"] = selected_answer_index
                        st.session_state.question_number += 1
                        
                        # 다음 문제의 시작 시간 기록
                        if st.session_state.question_number < len(questions):
                            st.session_state.question_start_times[f"start_time_q{st.session_state.question_number + 1}"] = time.time()
                        
                        st.rerun()
        
        #st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.session_state.state = 'finished'
        st.rerun()

elif st.session_state.state == 'finished':
    st.write("수고하셨습니다. 모든 문제를 완료하셨습니다.")
    total_time = time.time() - st.session_state.start_time
    st.write(f"총 소요 시간: {int(total_time // 60)}분 {int(total_time % 60)}초")
    
    # Prepare data for database
    data = {
        'name': st.session_state.name,
        'email': st.session_state.email,
        'date': datetime.now(),
        'total_time': round(total_time, 2)
    }
    for i in range(1, 41):
        data[f'q{i}'] = st.session_state.answers.get(f'q{i}', -1)
        
    for i in range(1, 41):
        data[f't{i}'] = round(st.session_state.times.get(f't{i}', -1), 2)
    
    if save_to_database(data):
        st.success("결과가 성공적으로 저장되었습니다.")
    else:
        st.error("결과 저장에 실패했습니다. 관리자에게 문의해주세요.")
