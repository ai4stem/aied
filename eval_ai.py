import os
import openai
import json
import mysql.connector
import markdown
import smtplib
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import matplotlib.font_manager as fm
from dotenv import load_dotenv
from openai import OpenAI
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

# Load the .env file
load_dotenv()

# Get the password from .env file
stored_password = os.getenv("PASSWORD")
openai.api_key = os.getenv("OPENAI_API_KEY")

evaluation_prompt = (
    "다음은 AI 역량 평가에 대한 문항(Problem)과 사용자의 응답결과(User_Answer)를 나타낸 정보야."
    "이 데이터는 Domain을 기준으로 인공지능 소양, 인공지능 이해, 데이터의 이해, 인공지능의 활용 4가지로 나눠져 있고, 여러 요소들은 입문, 기초, 해설의 3가지 수준으로 나눠져 있어."
    "그리고 각 문항에 대한 정보는 Problem, Choice로 나눠져 있고, 학습자의 문항별 응답 정보는 선택한 답(User_Answer), 정답 여부(Correct), 문항 응답 시간(Time_Taken)으로 구성되어 있어."
    "이러한 내용을 토대로 해서 인공지능 소양, 인공지능 이해, 데이터의 이해, 인공지능의 활용의 4가지 영역별, 그리고 이를 종합한 관점에서 피드백을 제공해 줘."
    "즉, 4개의 영역 및 종합 평가 등 5개에 대한 수준 및 피드백을 알려 줘."
    "이 때, 각 영역에 대한 내용은 강점과 약점, 그리고 발전하기 위한 방법이나 참고내용을 알려 줘. 종합 평가의 경우는 학습자가 입문자, 기초, 중급, 고급으로 나눠서 판단해 줘."
    "각 영역별로 최소한 200자 이상의 피드백을 제공하도록 해."
)

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_feedback",
            "description": "Get feedbacks about the dignostic test for AI competence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "literacy": {
                        "type": "string",
                        "description": "Feedback for AI literacy",
                    },
                    "understanding": {
                        "type": "string",
                        "description": "Feedback for AI understanding",
                    },
                    "data": {
                        "type": "string",
                        "description": "Feedback for Data understanding",
                    },
                    "application": {
                        "type": "string",
                        "description": "Feedback for application of AI",
                    },
                    "overall": {
                        "type": "string",
                        "description": "Feedback for overall test",
                    },
                },
                
                "required": ["literacy", "understanding", "data", "application", "overall"],
            },
        }
    }
]

dict_name = {"literacy": "인공지능 소양", "understanding": "인공지능 이해", "data": "데이터의 이해", "application": "인공지능의 활용", "overall": "종합 평가"}


# Load the ai_test_update.csv file
questions_df = pd.read_csv('ai_test_update.csv')

# Connect to the MySQL database
db = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    passwd=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_DATABASE")
)

# Function to validate password
def validate_password(password):
    return password == stored_password

# Function to get user list from the database
def get_user_list():
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, name, email, date FROM ai_assessment_results")
    users = cursor.fetchall()
    return users

# Function to get user's responses from the database
def get_user_responses(id):
    cursor = db.cursor(dictionary=True)
    cursor.execute(f"SELECT * FROM ai_assessment_results WHERE id = {id}")
    user_data = cursor.fetchone()
    return user_data

def create_score_chart(scores):
    # 한글 폰트 설정
    #fontpath = fm.findfont(fm.FontProperties(family='NanumSquareRound'))
    #font = fm.FontProperties(fname=fontpath, size=12)
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = ['NanumSquareRound', 'Malgun Gothic', 'Arial', 'Helvetica']
    plt.rcParams['axes.unicode_minus'] = False

    #plt.rcParams['font.family'] = 'NanumSquareRound'
    #plt.rcParams['axes.unicode_minus'] = False

    fig, ax = plt.subplots(figsize=(14, 6))  # 그래프 크기를 좀 더 키웁니다.
    domains = list(scores.keys())
    values = list(scores.values())
    
    # 막대 그래프 생성
    bars = ax.barh(domains, values, color='#3498db', height=0.6)
    
    # x축 설정
    ax.set_xlim(0, 1)
    ax.set_xticks(np.arange(0, 1.1, 0.2))
    ax.set_xticklabels([f'{x:.0%}' for x in np.arange(0, 1.1, 0.2)], fontsize=22)  # x축 레이블 크기 증가
    ax.set_xlabel('정답률', fontsize=22, labelpad=10)  # x축 제목 추가
    
    # y축 설정
    ax.set_yticks(range(len(domains)))
    ax.set_yticklabels(domains, fontsize=22)  # y축 레이블 크기 증가
    
    # 제목 설정
    ax.set_title('AI 역량 평가 결과', fontsize=30, pad=20)
    
    # 격자 설정
    ax.grid(axis='x', color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
    
    # 테두리 제거
    for spine in ax.spines.values():
        spine.set_visible(False)
    
    # 값 표시
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax.text(width, bar.get_y() + bar.get_height()/2, f'{values[i]:.1%}', 
                ha='left', va='center', fontsize=20, fontweight='bold')
    
    # 여백 조정
    plt.tight_layout()
    
    # 이미지로 저장
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=150)
    img_buffer.seek(0)
    plt.close()
    
    return img_buffer


# Function to display user data with calculated scores and update MySQL
def display_user_data(id):
    user_data = get_user_responses(id)
    if user_data:
        results = questions_df.copy()
        user_answers = [user_data[f'q{i}'] for i in range(1, 41)]  # Using q1 to q40
        results['User_Answer'] = user_answers
        results['Correct'] = results['Answer'] == results['User_Answer']
        results['Time_Taken'] = [user_data[f't{i}'] for i in range(1, 41)]  # Using t1 to t40 for time

        # Calculate counts
        correct_count = int(results['Correct'].sum())
        unknown_count = int((results['User_Answer'] == 0).sum())
        incorrect_count = 40 - correct_count - unknown_count

        # Update a1~a40 in the database
        cursor = db.cursor()
        for i in range(1, 41):
            correct_value = 1 if results['Correct'][i-1] else (0 if user_data[f'q{i}'] != -1 else -1)
            cursor.execute(f"UPDATE ai_assessment_results SET a{i} = %s WHERE id = %s", (correct_value, id))

        # Update the counts in the database
        update_query = """
        UPDATE ai_assessment_results
        SET correct_count = %s, incorrect_count = %s, unknown_count = %s
        WHERE id = %s
        """
        cursor.execute(update_query, (correct_count, incorrect_count, unknown_count, id))
        db.commit()

        # Calculate scores by domain
        domain_scores = {
            '인공지능 소양': results[results['Domain'] == '인공지능 소양']['Correct'].mean(),
            '인공지능 이해': results[results['Domain'] == '인공지능 이해']['Correct'].mean(),
            '데이터의 이해': results[results['Domain'] == '데이터의 이해']['Correct'].mean(),
            '인공지능의 활용': results[results['Domain'] == '인공지능의 활용']['Correct'].mean()
        }

        # Create and save the chart
        chart_buffer = create_score_chart(domain_scores)

        # Store the results and chart in session state
        st.session_state.results = results
        st.session_state.results_filtered = results.drop(columns=['No', 'CVR_1', 'CVR_2', 'CVR_3', 'CVR_4', 'CVR_5', 'CVR_6',
                                                                  'Difficult_1', 'Difficult_2', 'Difficult_3', 'Difficult_4', 'Difficult_5', 'Difficult_6',
                                                                  'Problem', 'Choice', 'Figure'])
        st.session_state.chart_buffer = chart_buffer
        
        # Display the scores and chart
        st.write("### 학습자 진단 개요 ")
        st.write(f"**정답률**: {correct_count/40:.2f}")
        st.write(f"**무응답률**: {unknown_count/40:.2f}")
        for domain, score in domain_scores.items():
            st.write(f"**{domain} 점수**: {score:.2f}")
        
        st.image(chart_buffer, caption='', use_column_width=True)
        
        # Display filtered results
        st.write("### 사용자 응답 및 정답 확인")
        st.write(st.session_state.results_filtered)

# ... (evaluation_prompt and tools remain unchanged)

# Function to evaluate the user responses and send to GPT-4 API
def evaluate_user(id):
    user_data = get_user_responses(id)
    if user_data:
        # 정보 가져오기
        results = st.session_state.get('results_filtered', None)
        
        # 데이터프레임이 비어 있는지 확인
        if results is None or results.empty:
            st.error("사용자 응답 데이터가 없습니다.")
            return

        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        dict_data = results.to_dict()
        dict_as_str = json.dumps(dict_data, indent=4)  # indent=4로 읽기 쉽게 포맷팅
        query = evaluation_prompt + dict_as_str
        
        messages = [] 
        messages.append({"role": "system", "content": "You are the expert of AI competence. Don't make assumptions about what values to plug into functions."})
        messages.append({"role": "user", "content": query})
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools
        )
        
        all_feedback = {}
        
        if hasattr(resp.choices[0].message, 'tool_calls'):
            for tool_call in resp.choices[0].message.tool_calls:
                if tool_call.function.name == 'get_feedback':
                    feedback = json.loads(tool_call.function.arguments)
                    all_feedback.update(feedback)
        else:
            all_feedback = json.loads(resp.choices[0].message.tool_calls[0].function.arguments)

        # Display GPT-4 feedback
        st.write("### AI 기반 평가 피드백 ")
        
        markdown_text = ""
        for key, value in all_feedback.items():
            markdown_text += f"**{dict_name[key]}**: {value}\n\n"

        # 피드백을 세션 상태에 저장
        st.session_state.feedback_text = markdown_text
        
        # Streamlit에서 마크다운 출력
        st.markdown(markdown_text)

        # MySQL 업데이트 (각 피드백을 DB에 저장)
        update_query = """
        UPDATE ai_assessment_results
        SET ai_literacy_feedback = %s, ai_understanding_feedback = %s,
            data_understanding_feedback = %s, ai_application_feedback = %s, overall_feedback = %s
        WHERE id = %s
        """
        
        cursor = db.cursor()
        cursor.execute(update_query, (
            all_feedback.get('literacy', ''),
            all_feedback.get('understanding', ''),
            all_feedback.get('data', ''),
            all_feedback.get('application', ''),
            all_feedback.get('overall', ''),
            id
        ))
        db.commit()

# 이메일로 평가 결과 전송 함수
def send_email(recipient_email, name, subject, body, chart_buffer):
    sender_email = os.getenv('EMAIL_ADDRESS')
    sender_password = os.getenv('EMAIL_PASSWORD')  # 앱 비밀번호 사용

    # body가 None이거나 비어 있으면 이메일 전송 중단
    if not body:
        st.error("평가 결과가 없습니다. 이메일을 보내지 않습니다.")
        return False

    # 마크다운을 HTML로 변환
    html_body = markdown.markdown(body)

    message = MIMEMultipart("related")
    message['From'] = sender_email
    message['To'] = recipient_email
    message['Subject'] = subject

    # HTML 메시지 추가
    html_part = MIMEText(html_body + '<br><img src="cid:image1">', 'html')
    message.attach(html_part)

    # 이미지 첨부
    image = MIMEImage(chart_buffer.getvalue())
    image.add_header('Content-ID', '<image1>')
    message.attach(image)

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)  # 앱 비밀번호로 로그인
            server.send_message(message)
            server.quit()
        return True
    except Exception as e:
        st.error(f"이메일을 보내는 동안 오류가 발생했습니다: {str(e)}")
        print(f"Error occurred while sending an email: {str(e)}")
        return False

# Streamlit app
st.title("AI 역량 평가 결과")

# Password input
password = st.text_input("비밀번호를 입력한 뒤, 엔터를 누르세요.:", type="password")

if password:
    if validate_password(password):
        st.success("비밀번호가 일치합니다.")
        
        # Fetch and display users
        users = get_user_list()
        user_names = [f"{user['name']} ({user['email']} / {user['date']})" for user in users]
        selected_user = st.selectbox("평가할 학습자 선택:", user_names)
        
        if selected_user:
            selected_id = users[user_names.index(selected_user)]['id']
            selected_email = users[user_names.index(selected_user)]['email']
            selected_name = users[user_names.index(selected_user)]['name']
            
            # Button to display user data
            if st.button("사용자 응답 및 정답 확인") or st.session_state.get('results_filtered') is not None:
                display_user_data(selected_id)
                
            # Button to evaluate the user
            if st.button("종합 평가하기"):
                evaluate_user(selected_id)

            # 결과 보내기 버튼을 눌르기 전에 세션 상태에 피드백이 있는지 확인
            if 'feedback_text' in st.session_state and st.session_state.feedback_text and 'chart_buffer' in st.session_state:
                st.write("### 종합 평가 완료. 결과를 이메일로 보내세요.")
                if st.button("결과 보내기"):
                    subject = f"AI 역량 평가 결과 - {selected_name}"
                    if send_email(selected_email, selected_name, subject, st.session_state.feedback_text, st.session_state.chart_buffer):
                        st.success("평가 결과가 이메일로 성공적으로 발송되었습니다.")
            else:
                st.warning("먼저 종합 평가하기 버튼을 눌러 평가를 완료하세요.")
    else:
        st.error("비밀번호가 일치하지 않습니다.")