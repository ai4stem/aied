import streamlit as st
import pandas as pd
import mysql.connector
import time
import json
import re
import os
import markdown
import smtplib
from datetime import datetime
from io import BytesIO
from dotenv import load_dotenv
from openai import OpenAI
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

# Set page config at the very beginning
st.set_page_config(page_title="열물리학 역량 평가", page_icon=":thermometer:", layout="wide")

# Load environment variables
load_dotenv()

# Database connection parameters
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_DATABASE = os.getenv("DB_DATABASE")

# CSS to adjust button styles
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
@st.cache_data(ttl=600)  # 캐시가 10분마다 무효화되도록 설정
def load_questions():
    return pd.read_excel('problem.xlsx')

questions = load_questions()

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_feedback",
            "description": "Get feedbacks about the diagnostic test for thermal physics",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        }
    }
]

for i in range(1, 12):
    tools[0]["function"]["parameters"]["properties"][f"score{i}"] = {
        "type": "integer",
        "enum": [0, 1, 2, 3],
        "description": f"Score for question {i}"
    }

tools[0]["function"]["parameters"]["properties"]["all_score"] = {
    "type": "integer", 
    "enum": [i for i in range(34)],
    "description": "Score for overall test"
}

# feed1 ~ feed11까지 반복적으로 추가
for i in range(1, 12):
    tools[0]["function"]["parameters"]["properties"][f"feed{i}"] = {
        "type": "string", 
        "description": f"Feedback for question {i}"
    }

# overall 피드백 추가
tools[0]["function"]["parameters"]["properties"]["overall"] = {
    "type": "string", 
    "description": "Feedback for overall test"
}

# 필수 필드로 추가
tools[0]["function"]["parameters"]["required"] = [f"score{i}" for i in range(1, 12)] + ["all_score"] + [f"feed{i}" for i in range(1, 12)] + ["overall"]

# Function to validate email
def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

# MySQL에 데이터를 저장하고, 생성된 id를 반환하는 함수
def save_to_database(data):
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_DATABASE
        )
        cursor = connection.cursor()

        # INSERT 쿼리
        query = """
        INSERT INTO thermal_init 
        (name, email, date, total_time, q1, q2, q3, q4, q5, q6, q7, q8, q9, q10, q11,
        t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        # 데이터를 튜플 형태로 전달
        cursor.execute(query, tuple(data.values()))
        
        # 변경 사항 커밋
        connection.commit()
        
        # 생성된 id 반환
        student_id = cursor.lastrowid
        
        return student_id
    except mysql.connector.Error as error:
        st.error(f"Failed to save results to database: {error}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            
# Function to display text and LaTeX
def display_text_and_latex(text):
    # 수식 구분을 위한 패턴 정의 (원시 문자열 사용)
    pattern = r'(\\\[.*?\\\]|\\\(.*?\\\))'
    
    # 패턴을 기준으로 문자열을 분리
    parts = re.split(pattern, text, flags=re.DOTALL)
    
    print(parts)  # 디버깅용 출력
    
    for part in parts:
        # 수식 부분이 LaTeX 구분 기호로 둘러싸여 있는지 확인 (re.fullmatch 사용)
        if re.fullmatch(pattern, part, flags=re.DOTALL):  # LaTeX 수식인 경우
            #print("LaTeX 수식 부분:", part)
            
            # 수식의 양쪽 기호만 제거하고 내부는 그대로 유지
            if part.startswith('$$') and part.endswith('$$'):
                cleaned_latex = part[2:-2]  # $$ ... $$ 제거
            elif part.startswith('$') and part.endswith('$'):
                cleaned_latex = part[1:-1]  # $ ... $ 제거
            elif part.startswith('\\[') and part.endswith('\\]'):
                cleaned_latex = part[2:-2]  # \[ ... \] 제거
            elif part.startswith('\\(') and part.endswith('\\)'):
                cleaned_latex = part[2:-2]  # \( ... \) 제거
            else:
                cleaned_latex = part  # 포맷에 맞지 않으면 그대로 출력
            
            #print(cleaned_latex)
            
            st.latex(cleaned_latex.strip())  # LaTeX 수식 렌더링
        else:
            # 일반 텍스트인 경우
            st.markdown(part)
           
# MySQL에서 학습자 데이터를 id로 불러오는 함수
def fetch_student_data_by_id(student_id):
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_DATABASE
        )
        cursor = connection.cursor(dictionary=True)
        
        # 학습자 id를 이용해 데이터를 조회
        query = "SELECT * FROM thermal_init WHERE id = %s"
        cursor.execute(query, (student_id,))
        result = cursor.fetchone()
        
        return result
    except mysql.connector.Error as error:
        st.error(f"Failed to fetch student data: {error}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

evaluation_prompt = (
    "다음은 열물리학 과목 수강생을 위한 진단 평가에 대한 문항과 사용자의 응답결과를 나타낸 정보야."
    "이 데이터는 Domain을 기준으로 수학적 이해와 물리적 이해의 2가지로 나눠져 있고, 각각의 문항은 미흡, 보통, 양호, 우수의 4단계로 평가 기준을 가지고 있어."
    "그리고 각 문항에 대한 사용자의 응답시간과 응답내용, 평가기준을 고려해서 각각의 문항에 대해 미흡(0), 보통(1), 양호(2), 우수(3) 중 어디에 해당하는지와 함께 문제 풀이를 위한 학습자의 응답 수준에 맞는 풀이 및 피드백을 제공해 줘."
    "또한 전체적인 관점에서의 총평과 피드백도 제공해 줘."
    "만약 입력한 텍스트가 없다면 0점 처리하고, 피드백은 문제를 풀기 위한 단계나 푸는 과정을 보여주도록 해."
    "그러니까 11개의 문항에 대한 점수(0~3) 및 종합 점수, 각 문항에 대한 피드백 및 종합 피드백을 제공해 줘야 해."
    "각각의 문항에 대해 최소한 200자 이상의 피드백을 제공하도록 해."
)

# 엑셀 파일을 불러와 답안과 비교하여 평가
def evaluate_student_data(student_data):    
    # 평가 결과 저장
    correct = []
    feed = []
    
    query = ''
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    for i in range(len(questions)):
        timed = student_data[f't{i+1}']
        solution = student_data[f'q{i+1}']
        query += f"문항 {i+1}: {questions.loc[i, 'Problem']}\n"
        query += f"평가기준: {questions.loc[i, 'Standard']}\n"
        query += f'응답 시간: {timed}초\n'
        query += f'응답 내용: {solution}\n'
    
    query = evaluation_prompt + '\n' + query
    messages = [] 
    messages.append({"role": "system", "content": "You are the expert of physics. Don't make assumptions about what values to plug into functions."})
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
    
    print(all_feedback)
    
    # 문항별로 평가
    for i in range(1, 12):
        feed.append(all_feedback[f'feed{i}'])
        correct.append(all_feedback[f'score{i}'])
    
    total_score = float(f"{all_feedback['all_score']/11:.2f}")
    total_feedback = all_feedback['overall']
            
    return total_score, total_feedback, correct, feed

# 평가 결과를 MySQL에 id로 업데이트하는 함수
def update_student_results_by_id(student_id, total_score, total_feedback, correct, feed):
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_DATABASE
        )
        cursor = connection.cursor()
        
        # MySQL에 업데이트할 쿼리
        query = """
        UPDATE thermal_init
        SET total_score = %s,
            total_feedback = %s,
            correct1 = %s, correct2 = %s, correct3 = %s, correct4 = %s, correct5 = %s, 
            correct6 = %s, correct7 = %s, correct8 = %s, correct9 = %s, correct10 = %s, correct11 = %s,
            feed1 = %s, feed2 = %s, feed3 = %s, feed4 = %s, feed5 = %s,
            feed6 = %s, feed7 = %s, feed8 = %s, feed9 = %s, feed10 = %s, feed11 = %s
        WHERE id = %s
        """
        
        # 데이터 업데이트
        cursor.execute(query, (
            total_score, total_feedback, 
            *correct, *feed, student_id
        ))
        connection.commit()
        
        st.success("결과가 성공적으로 업데이트되었습니다.")
    except mysql.connector.Error as error:
        st.error(f"Failed to update student results: {error}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# 이메일로 평가 결과 전송 함수
def send_email(recipient_email, name, subject, markdown_body, chart_buffer=None):
    sender_email = os.getenv('EMAIL_ADDRESS')
    sender_password = os.getenv('EMAIL_PASSWORD')  # 앱 비밀번호 사용

    if not markdown_body:
        st.error("평가 결과가 없습니다. 이메일을 보내지 않습니다.")
        return False

    # Markdown을 HTML로 변환
    html_body = markdown.markdown(markdown_body)

    message = MIMEMultipart("related")
    message['From'] = sender_email
    message['To'] = recipient_email
    message['Subject'] = subject

    # HTML 메시지 추가
    html_part = MIMEText(html_body, 'html')
    message.attach(html_part)

    # 이미지 첨부 (옵션)
    if chart_buffer:
        image = MIMEImage(chart_buffer.getvalue())
        image.add_header('Content-ID', '<image1>')
        message.attach(image)

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(message)
        return True
    except Exception as e:
        st.error(f"이메일을 보내는 동안 오류가 발생했습니다: {str(e)}")
        return False

# 학습자의 답변과 평가 결과를 테이블로 보여주고, 피드백을 문자열로 저장하는 함수
def display_evaluation_results(student_data, correct_data, feed_data, total_score, total_feedback):
    markdown_content = f"""
    ## 열물리학 역량 평가 결과

    **학습자:** {student_data['name']}  
    **이메일:** {student_data['email']}  
    **응답 일시:** {student_data['date']}  
    **종합 점수:** {total_score}점/11점  
    **종합 피드백:** {total_feedback}

    ### 문항별 평가 결과
    """

    for i in range(1, 12):
        markdown_content += f"""
    #### 문항 {i}
    
    **문항 내용:** {questions.loc[i-1, 'Problem']}  
    **응답 내용:** {student_data[f'q{i}']}  
    **점수:** {correct_data[i-1]}  
    **평가 결과:** {feed_data[i-1]}

    """

    return markdown_content
 
# Initialize session state variables
# Initialize session state variables
if 'email_sent' not in st.session_state:
    st.session_state.email_sent = False
if 'results_checked' not in st.session_state:
    st.session_state.results_checked = False
if 'markdown_content' not in st.session_state:
    st.session_state.markdown_content = ""
if 'state' not in st.session_state:
    st.session_state.state = 'intro'
if 'start_time' not in st.session_state:
    st.session_state.start_time = None
if 'end_time' not in st.session_state:
    st.session_state.end_time = None
if 'answers' not in st.session_state:
    st.session_state.answers = {}
if 'times' not in st.session_state:
    st.session_state.times = {}
if 'question_start_times' not in st.session_state:
    st.session_state.question_start_times = {}

# Streamlit app
st.markdown("""
    <h1 style='text-align: center;'>열물리학 역량 평가</h1>
""", unsafe_allow_html=True)

if st.session_state.state == 'intro':
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.write("열물리학 역량 평가에 오신 것을 환영합니다.")
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
            본 진단 평가는 열물리학 역량을 평가하기 위해 개발되었습니다.

            - **총 문항 수:** 11개
            - **제한 시간:** 60분

            ## 주의사항

            - 각 문항에 대해 서술형으로 풀이과정과 함께 답변해 주세요.
            - 평가 결과는 입력한 이메일로 전송될 수 있습니다.
            - 모든 정보는 익명으로 관리됩니다.

            **아래 확인 버튼을 누르시면 제반 사항에 대해 동의한 것으로 판단하고 평가를 시작합니다.**
            """)

        if st.button("확인 및 평가 시작"):
            st.session_state.state = 'test'
            st.session_state.start_time = time.time()
            st.session_state.end_time = st.session_state.start_time + 60 * 60  # 60 minutes
            st.session_state.question_number = 0
            st.rerun()

elif st.session_state.state == 'test':
    # 입력 방법 확인용 확장 메뉴 추가
    with st.expander("입력 방법 확인"):
        st.markdown(
            """
            수식을 입력하기 위해서는 수식의 앞과 뒤를 `$` 과 `$`으로 감싸야 합니다. `$ 수식 $`.
             
            | **수학 상수 및 기호**       | **표현 방법 (LaTeX 코드)**      | **결과**              |**연산자/기호**      | **표현 방법 (LaTeX 코드)**      | **결과**              |
            |----------------------|---------------------------------|-----------------------|----------------------|---------------------------------|-----------------------|
            | 파이 (Pi)             | `\\pi`                           | $\pi$             |곱셈                  | `\\times`                        | $ \\times $          |
            | 오메가 (Omega)        | `\\omega`                        | $\\omega $          |나눗셈                | `\\div`                          | $ \\div $            |
            | 인피니티 (Infinity)   | `\\infty`                        | $ \\infty $        |제곱근                | `\\sqrt{}`                       | $ \\sqrt{x} $       |
            | 델타 (Delta)          | `\\Delta`                        | $ \\Delta $          |분수                  | `\\dfrac{}{}`                    | $ \\dfrac{a}{b} $    |
            | 델 (Nabla)            | `\\nabla`                        | $ \\nabla $          |점곱                  | `\\cdot`                         | $ \\cdot $           |
            | 베타 (Beta)           | `\\beta`                         | $ \\beta $           |미분                  | `\\dfrac{d}{dx}`                 | $ \\dfrac{d}{dx} $   |
            | 감마 (Gamma)          | `\\gamma`                        | $ \\gamma $         |적분                  | `\\int`                          | $ \\int $           |
            | 사인 (Sine)           | `\\sin`                          | $ \\sin $            |중적분                | `\\iint`, `\\iiint`               | $ \\iint, \\iiint $   |
            | 코사인 (Cosine)        | `\\cos`                          | $ \\cos $            |무한대에서 적분       | `\\int_0^\\infty`                 | $ \\int_0^\\infty $   |
            | 탄젠트 (Tangent)      | `\\tan`                          | $ \\tan $            |벡터                  | `\\vec{}`                        | $ \\vec{v} $         |
            | 사인 제곱             | `\\sin^2`                        | $ \\sin^2 \\theta $   |행렬                  | `\\begin{pmatrix}a & b \\\\ c & d \\end{pmatrix}` | $ \\begin{pmatrix}a & b \\\\ c & d \\end{pmatrix} $ |
            | 코사인 제곱           | `\\cos^2`                        | $ \\cos^2 \\theta $   |내적                  | `\\cdot`                         | $ \\vec{A} \\cdot \\vec{B} $ |
            | 아크 사인             | `\\arcsin`                       | $ \\arcsin $         |외적                  | `\\times`                        | $ \\vec{A} \\times \\vec{B} $ |
            """
        )

    # Time and progress display
    current_time = time.time()
    if current_time > st.session_state.end_time:
        st.session_state.state = 'finished'
        st.rerun()
    
    remaining_time = st.session_state.end_time - current_time
    minutes, seconds = divmod(int(remaining_time), 60)
    progress = 1 - (remaining_time / (60 * 60))

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"### 남은 시간: {minutes:02d}분 {seconds:02d}초")
    with col2:
        st.progress(progress)

    if st.session_state.question_number < len(questions):
        question = questions.iloc[st.session_state.question_number]
        current_question_number = st.session_state.question_number + 1
        st.write(f"문항 {current_question_number}/11")
        
        # Use display_text_and_latex function for LaTeX support
        display_text_and_latex(question['Problem'])
        
        # Record start time for the current question
        if f"start_time_q{current_question_number}" not in st.session_state.question_start_times:
            st.session_state.question_start_times[f"start_time_q{current_question_number}"] = time.time()

        answer = st.text_area("답변을 입력하세요:", key=f"q{current_question_number}", 
                              value=st.session_state.answers.get(f"q{current_question_number}", ""))
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("이전 문제", disabled=current_question_number == 1):
                if current_question_number > 1:
                    # Update time spent on current question
                    question_time = time.time() - st.session_state.question_start_times[f"start_time_q{current_question_number}"]
                    st.session_state.times[f"t{current_question_number}"] = st.session_state.times.get(f"t{current_question_number}", 0) + question_time
                    
                    st.session_state.question_number -= 1
                    st.rerun()
                else:
                    st.warning("첫 번째 문항입니다.")

        with col2:
            if st.button("다음 문제"):
                # Update answer and time for current question
                st.session_state.answers[f"q{current_question_number}"] = answer
                question_time = time.time() - st.session_state.question_start_times[f"start_time_q{current_question_number}"]
                st.session_state.times[f"t{current_question_number}"] = st.session_state.times.get(f"t{current_question_number}", 0) + question_time
                
                st.session_state.question_number += 1
                
                # Record start time for next question
                if st.session_state.question_number < len(questions):
                    st.session_state.question_start_times[f"start_time_q{st.session_state.question_number + 1}"] = time.time()
                
                st.rerun()

    else:
        st.session_state.state = 'finished'
        st.rerun()

# Streamlit의 결과 확인 및 전송 부분
if st.session_state.state == 'finished':
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
    
    for i in range(1, 12):
        data[f'q{i}'] = st.session_state.answers.get(f'q{i}', '')
        
    for i in range(1, 12):
        data[f't{i}'] = round(st.session_state.times.get(f't{i}', 0), 2)
    
    student_id = save_to_database(data)
    if student_id:
        st.session_state.student_id = student_id
        st.success(f"결과가 성공적으로 저장되었습니다!")
        
        if 'results_checked' not in st.session_state:
            st.session_state.results_checked = False

        if st.button("결과 확인하기"):
            student_data = fetch_student_data_by_id(student_id)
            
            if student_data:
                total_score, total_feedback, correct, feed = evaluate_student_data(student_data)
                update_student_results_by_id(student_id, total_score, total_feedback, correct, feed)
                
                # Markdown 형식의 결과를 생성하고 저장
                markdown_content = display_evaluation_results(student_data, correct, feed, total_score, total_feedback)
                st.session_state.markdown_content = markdown_content
                
                # Streamlit에 Markdown 내용 표시
                st.markdown(markdown_content)
                
                st.session_state.results_checked = True
                st.session_state.email_sent = False  # 결과를 새로 확인했으므로 이메일 전송 상태 초기화

        if st.session_state.results_checked:
            #st.write("결과가 확인되었습니다.")  # 디버깅용 출력
            
            #st.write(f"현재 이메일 전송 상태: {st.session_state.email_sent}")  # 디버깅용 출력

            if st.button("결과 전송하기"):
                #st.write("결과 전송하기 버튼이 클릭되었습니다.")  # 디버깅용 출력
                
                if not st.session_state.email_sent:
                    #st.write("이메일 전송을 시작합니다.")  # 디버깅용 출력
                    
                    try:
                        success = send_email(
                            recipient_email=st.session_state.email,
                            name=st.session_state.name,
                            subject="열역학 평가 결과",
                            markdown_body=st.session_state.markdown_content
                        )

                        if success:
                            st.session_state.email_sent = True
                            st.success("결과가 이메일로 성공적으로 전송되었습니다.")
                        else:
                            st.error("이메일 전송에 실패했습니다.")
                    except Exception as e:
                        st.error(f"이메일 전송 중 오류 발생: {str(e)}")
                else:
                    st.info("이미 이메일이 전송되었습니다.")
            
            #st.write(f"최종 이메일 전송 상태: {st.session_state.email_sent}")  # 디버깅용 출력


# Rerun the app every second to update the timer
if st.session_state.state == 'test':
    time.sleep(1)
    st.rerun()