import streamlit as st
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv

# 페이지 레이아웃을 넓게 설정
st.set_page_config(layout="wide")

# Load the .env file
load_dotenv()

# Database connection setup
def init_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_DATABASE")
    )

# Function to fetch student data from the database
# 시간을 오름차순으로 정렬하여 가져오기
def fetch_students():
    conn = init_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, email, date FROM inquiry_talk ORDER BY date ASC")
    students = cursor.fetchall()
    cursor.close()
    conn.close()
    return students

# Function to fetch conversation and advice data for a specific student
def fetch_student_data(student_id):
    conn = init_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT conversation1, conversation2, conversation3, conversation4, advice1, advice2, advice3, advice4 FROM inquiry_talk WHERE id = %s", (student_id,))
    data = cursor.fetchone()
    cursor.close()
    conn.close()
    return data

# Main page
def overall_page():
    st.title("학생 대화 및 피드백 확인")

    # Password authentication
    password = st.text_input("비밀번호를 입력하세요", type="password")
    if password != os.getenv("PASSWORD"):  # Using the password from .env
        st.warning("올바른 비밀번호를 입력하세요.")
        return
    
    # Fetch and display student selection dropdown (sorted by date in ascending order)
    students = fetch_students()
    if not students:
        st.warning("등록된 학생 정보가 없습니다.")
        return

    # Create the options for the combo box sorted by date (ascending)
    student_options = [f"{s['name']} ({s['email']}) - {s['date']}" for s in students]
    selected_student = st.selectbox("학생을 선택하세요", student_options)

    # Get the selected student's ID
    student_id = students[student_options.index(selected_student)]["id"]

    # Fetch the selected student's data
    student_data = fetch_student_data(student_id)

    if student_data:
        # Display the data in tabs
        tabs = st.tabs(["탐구 질문", "가설", "배경이론", "준비물 및 탐구과정"])

        with tabs[0]:
            st.header("탐구 질문 대화 기록")
            st.markdown(student_data["conversation1"])
            st.header("탐구 질문 피드백")
            st.markdown(student_data["advice1"])

        with tabs[1]:
            st.header("가설 대화 기록")
            st.markdown(student_data["conversation2"])
            st.header("가설 피드백")
            st.markdown(student_data["advice2"])

        with tabs[2]:
            st.header("배경이론 대화 기록")
            st.markdown(student_data["conversation3"])
            st.header("배경이론 피드백")
            st.markdown(student_data["advice3"])

        with tabs[3]:
            st.header("준비물 및 탐구과정 대화 기록")
            st.markdown(student_data["conversation4"])
            st.header("준비물 및 탐구과정 피드백")
            st.markdown(student_data["advice4"])

# Streamlit app execution
if __name__ == "__main__":
    overall_page()
