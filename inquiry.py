import streamlit as st
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv
import requests
import re
import json
import time
from openai import OpenAI
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import markdown  # Markdown을 HTML로 변환하기 위해 필요

# .env 파일을 로드
load_dotenv()

probs = {"climbing magnet": "Attach a rod assembled from cylindrical neodymium magnets horizontally to a vertical ferromagnetic rod. Limit the motion of the magnets to the vertical direction. When the ferromagnetic rod is spun around its axis of symmetry, the magnetic rod begins to climb up. Explain this phenomenon and investigate how the rate of climbing depends on relevant parameters.",
         "Spaghetti accelerator": "When a piece of spaghetti is pushed into a bent tube, small debris of spaghetti may be ejected from the other end of the tube at a surprisingly high speed. Investigate this phenomenon.", 
         "Rigid ramp walker": "Construct a rigid ramp walker with four legs (e.g. in the form of a ladder). The construction may begin to ‘walk’ down a rough ramp. Investigate how the geometry of the walker and relevant parameters affect its terminal velocity of walking.", 
         "Rebounding capsule": "A spherical ball dropped onto a hard surface will never rebound to the release height, even if it has an initial spin. A capsule-shaped object (i.e. Tic Tac mint) on the other hand may exceed the initial height. Investigate this phenomenon.", 
         "Sweet mirage": "Fata Morgana is the name given to a particular form of mirage. A similar effect can be produced by shining a laser through a fluid with a refractive index gradient. Investigate the phenomenon.", 
         "Falling tower": "Identical discs are stacked one on top of another to form a freestanding tower. The bottom disc can be removed by applying a sudden horizontal force such that the rest of the tower will drop down onto the surface and the tower remains standing. Investigate the phenomenon and determine the conditions that allow the tower to remain standing.", 
         "Pepper pot": "If you take a salt or pepper pot and just shake it, the contents will pour out relatively slowly. However, if an object is rubbed along the bottom of the pot, then the rate of pouring can increase dramatically. Explain this phenomenon and investigate how the rate depends on the relevant parameters.", 
         "Leidenfrost stars": "In the Leidenfrost effect, a water drop placed on a hot surface can survive for minutes. Under certain circumstances, such a drop develops oscillating star shapes. Induce different oscillatory modes and investigate them."
         }

# uploads 폴더가 존재하지 않으면 생성
if not os.path.exists('uploads'):
    os.makedirs('uploads')

def contains_heading(text, headings):
    for heading in headings:
        if heading in text:
            return True
    return False

# MySQL 연결 설정
def init_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_DATABASE')
    )

# MySQL 업데이트 함수
def update_table(field, value):
    if 'record_id' not in st.session_state:
        st.error("레코드가 생성되지 않았습니다. 먼저 레코드를 생성하세요.")
        return

    conn = init_connection()
    cursor = conn.cursor()

    # id 값을 기준으로 레코드를 업데이트
    query = f"UPDATE inquiry_talk SET {field} = %s WHERE id = %s"
    cursor.execute(query, (value, st.session_state.record_id))

    conn.commit()
    cursor.close()
    conn.close()

# 파일 업로드 이후 MySQL에 저장하는 함수
def save_initial_inquiry_data():
    conn = init_connection()
    cursor = conn.cursor()
    query = '''INSERT INTO inquiry_talk (student_number, name, email, date, topic, problem, hypothesis, theory, apparatus, process)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''
    cursor.execute(query, (
        st.session_state.student_number, st.session_state.name, st.session_state.email, datetime.now(),
        st.session_state.topic, st.session_state.problem, st.session_state.hypothesis,
        st.session_state.theory, st.session_state.apparatus, st.session_state.process
    ))
    conn.commit()
    st.session_state.record_id = cursor.lastrowid
    
    cursor.close()
    conn.close()

# 단계별 페이지 정의
# 단계별 페이지 함수 정의
def start_page():
    st.title("탐구 설계 챗봇")
    
    student_number = st.text_input("학번")
    name = st.text_input("이름")
    email = st.text_input("이메일")
    
    if st.button("확인"):
        if student_number and name and email:
            st.session_state.student_number = student_number
            st.session_state.name = name
            st.session_state.email = email
            st.session_state.step = "disclaimer"
            print("Moving to disclaimer.")
            st.rerun()
        else:
            st.error("모든 필드를 입력해주세요.")

def disclaimer_page():
    st.title("Disclaimer")
    st.markdown("""
    본 대화 내용은 저장되며 학습 목적으로 사용될 수 있습니다.  
    또한 저장된 내용은 물리학습 앱의 발전을 위해 분석에 사용될 수 있습니다. 
    자신이 작성한 PDF 파일을 업로드하면 해당 내용을 토대로 탐구 질문, 가설, 배경이론, 탐구 과정에 대해 차례차례 질문하고 대화하게 됩니다.   
    인공지능과의 대화 내용은 사용자의 이메일로도 전송 가능합니다.  
    이에 **동의**하십니까?
    """)
    
    if st.button("동의"):
        # 세션 상태 초기화: get() 메서드를 사용하여 안전하게 상태 초기화
        st.session_state.problem = st.session_state.get('problem', "")
        st.session_state.hypothesis = st.session_state.get('hypothesis', "")
        st.session_state.theory = st.session_state.get('theory', "")
        st.session_state.apparatus = st.session_state.get('apparatus', "")
        st.session_state.process = st.session_state.get('process', "")
        st.session_state.upload_processed = st.session_state.get('upload_processed', False)  # 파일 처리 여부 확인
        st.session_state.last_uploaded_file = st.session_state.get('last_uploaded_file', None)  # 마지막 업로드된 파일
        st.session_state["messages"] = []
        st.session_state['all'] = []
        st.session_state.step = "upload"
        print("Agreed")
        st.rerun()

initial_prompt = [
    (
        "너는 물리 분야 탐구를 위한 튜터의 역할을 수행해 줘."
        "맨 처음 대화를 '안녕하세요. 반갑습니다. 탐구 질문 생성과 관련해 궁금한 점이 있나요?'라고 물어보고 시작해."
        "만약 궁금한 점이 있으면 응답해 주되, 탐구 질문이나 탐구와 관련이 없는 응답에는 대답하지 마."
        "그리고 궁금한 점이 없다면 네가 대화를 통해서 탐구 질문을 정교화하고 발전할 수 있도록 도와줘야 하는데 그 기준은 다음과 같고, 학습자는 대학교 1학년 수준이라는 사실을 잊지 마."
        "고려해야 하는 기준은 다음과 같아."
        "1) 문제가 명확하고 구체적인가?"
        "2) 실제로 관찰하거나 실험을 통해서 정답을 얻을 수 있는가?"
        "3) 과학적 이론이나 법칙을 통해 설명할 수 있는가?"
        "4) 문제가 실험자의 수준을 고려할 때 적절한 수준인가?"
        "5) 질문에 관련된 변수나 변인이 구체적이고 측정 가능한가?"
        "6) 널리 알려진 사실이 아닌 구체적이고 독창적인 문제인가?"
        "6가지를 고려해서 잘 충족하는 부분이 있다면 넘어가도 되고, 네가 답을 바로 알려 주지 말고 대화를 통해서 사용자가 탐구 문제를 정교화할 수 있도록 도와 줘. 그리고 6가지를 한번에 물어보지 마."
        "최소한 5번 이상의 대화를 반복하도록 하고, 대화가 종료되었으면 '수고하셨습니다. 다음 단계로 이동하세요.' 이렇게 인사해."
        "학습자가 설계한 탐구 주제 및 관련 설명은 다음과 같아."),
    (
        "너는 물리 분야 탐구를 위한 튜터의 역할을 수행해 줘."
        "맨 처음 대화를 '안녕하세요. 반갑습니다. 탐구 가설과 관련해 궁금한 점이 있나요?'라고 물어보고 시작해."
        "만약 궁금한 점이 있으면 응답해 주되, 가설이나 탐구와 관련이 없는 응답에는 대답하지 마."
        "그리고 궁금한 점이 없다면 네가 대화를 통해서 가설을 정교화하고 발전할 수 있도록 도와줘야 하는데 그 기준은 다음과 같고, 학습자는 대학교 1학년 수준이라는 사실을 잊지 마."
        "고려해야 하는 기준은 다음과 같아."
        "1) 이 가설은 실험이나 관찰을 통해 검증될 수 있는가?"
        "2) 가설의 진술이 명확하고 구체적인가? 변수들이 구체적으로 정의되어 있는가?"
        "3) 가설이 과학적 이론과 일관성이 있는가? 기존 연구와 얼마나 관련이 있는가?"
        "4) 가설을 검증할 수 있는 실험이 실질적으로 가능한가? (자원, 시간, 기술적 측면)"
        "5) 가설은 기존의 연구와 비교했을 때 얼마나 독창적인가?"
        "5가지를 고려해서 잘 충족하는 부분이 있다면 넘어가도 되고, 네가 답을 바로 알려 주지 말고 대화를 통해서 사용자가 가설을 정교화할 수 있도록 도와 줘. 그리고 5가지를 한번에 물어보지 마."
        "최소한 5번 이상의 대화를 반복하도록 하고, 대화가 종료되었으면 '수고하셨습니다. 다음 단계로 이동하세요.' 이렇게 인사해."
        "학습자가 설계한 탐구 주제 및 관련 설명은 다음과 같아."),
    (
        "너는 물리 분야 탐구를 위한 튜터의 역할을 수행해 줘."
        "맨 처음 대화를 '안녕하세요. 반갑습니다. 배경이론과 관련해 궁금한 점이 있나요?'라고 물어보고 시작해."
        "만약 궁금한 점이 있으면 응답해 주되, 과학적 이론이나 탐구와 관련이 없는 응답에는 대답하지 마."
        "그리고 궁금한 점이 없다면 네가 대화를 통해서 탐구 문제와 가설을 설명하고 입증할 수 있는 적절한 이론이나 법칙을 고려할 수 있도록 도와줘. 학습자는 대학교 1학년 수준이라는 사실을 잊지 마."
        "네가 답을 바로 알려 주지 말고 대화를 통해서 사용자가 배경이론을 얼마나 잘 알고 있는지, 이를 이해하려면 어떤 것들을 참고하면 좋을지 알려주면 좋겠어.한번에 여러 가지를 물어보지 마."
        "최소한 5번 이상의 대화를 반복하도록 하고, 대화가 종료되었으면 '수고하셨습니다. 다음 단계로 이동하세요.' 이렇게 인사해."
        "학습자가 설계한 탐구 주제 및 관련 설명은 다음과 같아."),
    (
        "너는 물리 분야 탐구를 위한 튜터의 역할을 수행해 줘."
        "맨 처음 대화를 '안녕하세요. 반갑습니다. 준비물과 탐구과정에 관련해 궁금한 점이 있나요?'라고 물어보고 시작해."
        "만약 궁금한 점이 있으면 응답해 주되, 과학적 이론이나 탐구와 관련이 없는 응답에는 대답하지 마."
        "그리고 궁금한 점이 없다면 네가 대화를 통해서 탐구 문제와 가설, 배경이론과 연관지어서 적절한 탐구 과정과 필요한 준비물을 찾을 수 있도록 도와줘. 학습자는 대학교 1학년 수준이라는 사실을 잊지 마."
        "네가 답을 바로 알려 주지 말고 대화를 통해서 사용자가 탐구 문제와 가설에 연관지어서 적절한 준비를 할 수 있도록 대화를 진행하고, 한 번에 여러 가지를 물어보지 마."
        "최소한 5번 이상의 대화를 반복하도록 하고, 대화가 종료되었으면 '수고하셨습니다. 다음 단계로 이동하세요.' 이렇게 인사해."
        "학습자가 설계한 탐구 주제 및 관련 설명은 다음과 같아.")
]
                  
# 챗봇 응답 함수
def get_response(step, prompt):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if prompt == "":
        prompt = initial_prompt[step]
        prompt += f"탐구 주제: {st.session_state.topic}\n"
        prompt += f"설명: {probs[st.session_state.topic]}\n"
        prompt += f"탐구 문제: {st.session_state.problem}\n"
        prompt += f"가설: {st.session_state.hypothesis}\n"
        prompt += f"배경이론: {st.session_state.theory}\n"
        prompt += f"준비물: {st.session_state.apparatus}\n"
        prompt += f"탐구 과정: {st.session_state.process}"
        st.session_state["messages"].append({"role": "system", "content": prompt, "timestamp": timestamp})
    else:
        st.session_state["messages"].append({"role": "user", "content": prompt, "timestamp": timestamp})
    
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=st.session_state["messages"],
    )
    
    answer = response.choices[0].message.content
    print(f"from server: {answer}")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state["messages"].append({"role": "assistant", "content": answer, "timestamp": timestamp})    

    return answer

def inquiry_problem_page():
    st.title("탐구 문제")
    if st.session_state.messages == []:
        print("Calling first")
        get_response(0, "")

    # 대화 기록 출력
    for message in st.session_state["messages"]:
        role = message["role"]
        content = message["content"]
        timestamp = message.get("timestamp", "")

        if role == "user":
            st.markdown(f"**You** ({timestamp}):")
            st.markdown(content)
        elif role == "assistant":
            st.markdown(f"**AI** ({timestamp}):")
            st.markdown(content)

    # 사용자 입력 처리
    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_area("You: ", key="user_input")
        submit = st.form_submit_button(label="제출")

        if submit and user_input:
            # 사용자 입력 처리 및 응답 생성
            get_response(0, user_input)
            # 리렌더링
            st.rerun()

    if st.button("다음"):
        # 대화 내용 저장
        conversation = "\n".join([f"{msg['role']} ({msg.get('timestamp', 'N/A')}): {msg['content']}" for msg in st.session_state["messages"]])
        update_table("conversation1", conversation)
        st.session_state.step = "hypothesis"
        st.session_state.all.append(st.session_state["messages"])
        st.session_state["messages"] = []
        st.rerun()
        
def inquiry_hypothesis_page():
    st.title("탐구 가설")
    if not st.session_state['messages']:
        get_response(1, "")

    # 대화 기록 출력
    for message in st.session_state["messages"]:
        role = message["role"]
        content = message["content"]
        timestamp = message.get("timestamp", "")

        if role == "user":
            st.markdown(f"**You** ({timestamp}):")
            st.markdown(content)
        elif role == "assistant":
            st.markdown(f"**AI** ({timestamp}):")
            st.markdown(content)

    # 사용자 입력 처리
    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_area("You: ", key="user_input")
        submit = st.form_submit_button(label="제출")

        if submit and user_input:
            # 사용자 입력 처리 및 응답 생성
            get_response(1, user_input)
            # 리렌더링
            st.rerun()

    if st.button("다음"):
        # 대화 내용 저장
        conversation = "\n".join([f"{msg['role']} ({msg.get('timestamp', 'N/A')}): {msg['content']}" for msg in st.session_state["messages"]])
        update_table("conversation2", conversation)
        st.session_state.step = "theory"
        st.session_state.all.append(st.session_state["messages"])
        st.session_state["messages"] = []
        st.rerun()
    
def inquiry_theory_page():
    st.title("배경 이론")
    if st.session_state.messages == []:
        get_response(2, "")

    # 대화 기록 출력
    for message in st.session_state["messages"]:
        role = message["role"]
        content = message["content"]
        timestamp = message.get("timestamp", "")

        if role == "user":
            st.markdown(f"**You** ({timestamp}):")
            st.markdown(content)
        elif role == "assistant":
            st.markdown(f"**AI** ({timestamp}):")
            st.markdown(content)

    # 사용자 입력 처리
    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_area("You: ", key="user_input")
        submit = st.form_submit_button(label="제출")

        if submit and user_input:
            # 사용자 입력 처리 및 응답 생성
            get_response(2, user_input)
            # 리렌더링
            st.rerun()

    if st.button("다음"):
        # 대화 내용 저장
        conversation = "\n".join([f"{msg['role']} ({msg.get('timestamp', 'N/A')}): {msg['content']}" for msg in st.session_state["messages"]])
        update_table("conversation3", conversation)
        st.session_state.step = "process"
        st.session_state.all.append(st.session_state["messages"])
        st.session_state["messages"] = []
        st.rerun()

def inquiry_process_page():
    st.title("탐구 과정 및 절차")
    if st.session_state.messages == []:
        get_response(3, "")

    # 대화 기록 출력
    for message in st.session_state["messages"]:
        role = message["role"]
        content = message["content"]
        timestamp = message.get("timestamp", "")

        if role == "user":
            st.markdown(f"**You** ({timestamp}):")
            st.markdown(content)
        elif role == "assistant":
            st.markdown(f"**AI** ({timestamp}):")
            st.markdown(content)

    # 사용자 입력 처리
    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_area("You: ", key="user_input")
        submit = st.form_submit_button(label="제출")

        if submit and user_input:
            # 사용자 입력 처리 및 응답 생성
            get_response(3, user_input)
            # 리렌더링
            st.rerun()

    if st.button("다음"):
        # 대화 내용 저장
        conversation = "\n".join([f"{msg['role']} ({msg.get('timestamp', 'N/A')}): {msg['content']}" for msg in st.session_state["messages"]])
        update_table("conversation4", conversation)
        st.session_state.step = "overall"
        st.session_state.all.append(st.session_state["messages"])
        st.session_state["messages"] = []
        st.rerun()    

tools = [
    {
        "type": "function",
        "function": {
            "name": "summarise_feedback",
            "description": "Summarise feedback suggested from the AI expert",
            "parameters": {
                "type": "object",
                "properties": {
                    "problem": {
                        "type": "string",
                        "description": "AI expert's advice for problem identification",
                    },
                    "hypothesis": {
                        "type": "string",
                        "description": "AI expert's advice for establishing hypothesis",
                    },
                    "theory": {
                        "type": "string",
                        "description": "AI expert's advice for building up theory",
                    },
                    "process": {
                        "type": "string",
                        "description": "AI expert's advice for reifying process",
                    },
                },
                "required": ["problem", "hypothesis", "theory", "process"],
            },
        }
    }
]

def get_feedback(index):
    try:
        message = [{"role": "system", "content": "너는 물리 분야 탐구를 위한 튜터야."}]
        con_en = ['problem', 'hypothesis', 'theory', 'process']
        con_kr = ['질문', '가설', '이론', '과정']
        
        prompt = "다음은 학습자가 작성한 탐구 내용에 대한 피드백에 관한 대화 기록이야:\n"
        prompt += f"이에 대해 {con_kr[index]}에 대한 인공지능과 사용자의 대화 내용은 다음과 같아:\n"
        prompt += f"{con_kr[index]}: {st.session_state.all[index]}\n"
        prompt += f"이 내용을 토대로 {con_kr[index]}에 대한 검토 의견을 정리해서 제공해 줘. 한글로 대답해."
        
        message.append({"role": "user", "content": prompt})
        
        print("Calling feedback message.")
        
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=message,
        )
        
        print(response)
        answer = response.choices[0].message.content
        
        return answer

    except Exception as e:
        st.error(f"AI 피드백을 불러오는 중 오류가 발생했습니다: {e}")
        st.session_state.feedback = None  # 에러 발생 시 피드백 초기화
        return None

# 이메일 전송 함수 (HTML 지원)
def send_email(to_email, name, subject, body_markdown):
    try:
        # 이메일 설정
        from_email = os.getenv("EMAIL_ADDRESS")
        email_password = os.getenv("EMAIL_PASSWORD")
        
        # Markdown을 HTML로 변환
        body_html = markdown.markdown(body_markdown)

        # 이메일 메시지 생성
        message = MIMEMultipart("alternative")
        message["From"] = from_email
        message["To"] = to_email
        message["Subject"] = subject

        # Plain text와 HTML 버전의 이메일을 모두 추가 (Plain text는 선택 사항)
        part1 = MIMEText(body_markdown, "plain")  # plain text로도 첨부
        part2 = MIMEText(body_html, "html")       # HTML로 변환된 내용 첨부

        # 이메일 본문에 추가
        message.attach(part1)  # plain text
        message.attach(part2)  # HTML

        # 이메일 서버 설정 및 전송
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(from_email, email_password)
        server.sendmail(from_email, to_email, message.as_string())
        server.quit()

        return True
    except Exception as e:
        st.error(f"이메일 전송 중 오류가 발생했습니다: {e}")
        return False
        
def overall_page():
    st.title("총평 및 피드백")
    
    # 페이지가 로드될 때 자동으로 피드백 요청
    if "summary" not in st.session_state:
        items = []
        
        for i in range(4):
            result = get_feedback(i)
            if result is None:
                result = get_feedback(i)
            items.append(result)
        
        st.session_state.sum_problem = items[0]
        st.session_state.sum_hypothesis = items[1]
        st.session_state.sum_theory = items[2]
        st.session_state.sum_process = items[3]
        st.session_state.summary = True   

    if st.session_state.summary:
        is_error = False
        
        if st.session_state.sum_problem is None:
            st.error("서버로부터 데이터를 받아오는 데에 실패했습니다. 다시 실행해 주세요.")
            is_error = True
        elif st.session_state.sum_hypothesis is None:
            st.error("서버로부터 데이터를 받아오는 데에 실패했습니다. 다시 실행해 주세요.")
            is_error = True
        elif st.session_state.sum_theory is None:
            st.error("서버로부터 데이터를 받아오는 데에 실패했습니다. 다시 실행해 주세요.")
            is_error = True
        elif st.session_state.sum_process is None:
            st.error("서버로부터 데이터를 받아오는 데에 실패했습니다. 다시 실행해 주세요.")
            is_error = True

        # AI 피드백을 텍스트로 출력
        st.markdown("### AI 피드백 요약")
        st.markdown("**탐구 문제 피드백**")
        st.markdown(st.session_state.sum_problem)
        st.markdown('---')
        st.markdown("**가설 피드백**")
        st.markdown(st.session_state.sum_hypothesis)
        st.markdown('---')
        st.markdown("**배경이론 피드백**")
        st.markdown(st.session_state.sum_theory)
        st.markdown('---')
        st.markdown("**탐구 과정 피드백**")
        st.markdown(st.session_state.sum_process)

        # Markdown 형식의 이메일 본문 생성
        email_body = f"""
        ### AI 피드백 결과:  

        **탐구 문제 피드백**:  
        {st.session_state.sum_problem}  
        ---
        **가설 피드백**:  
        {st.session_state.sum_hypothesis}  
        ---
        **배경이론 피드백**:  
        {st.session_state.sum_theory}  
        ---
        **탐구 과정 피드백**:  
        {st.session_state.sum_process}
        """

        # 이메일 보내기, 새로 고침, 다음 버튼을 한 줄에 배치
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("결과 이메일 보내기"):
                subject = "AI 피드백 결과"
                # 이메일 보내기 함수 호출, Markdown 형식의 본문을 전달
                if send_email(st.session_state.email, st.session_state.name, subject, email_body):
                    st.success("결과가 이메일로 성공적으로 전송되었습니다.")
                else:
                    st.error("이메일 전송 중 오류가 발생했습니다.")

        with col2:
            if st.button("새로 고침"):
                items = []
                
                for i in range(4):
                    result = get_feedback(i)
                    if result is None:
                        result = get_feedback(i)
                    items.append(result)
                
                st.session_state.sum_problem = items[0]
                st.session_state.sum_hypothesis = items[1]
                st.session_state.sum_theory = items[2]
                st.session_state.sum_process = items[3]
                st.session_state.summary = True
                st.rerun()

        with col3:
            if st.button("다음"):
                update_table("advice1", st.session_state.sum_problem)
                update_table("advice2", st.session_state.sum_hypothesis)
                update_table("advice3", st.session_state.sum_theory)
                update_table("advice4", st.session_state.sum_process)                

                st.session_state.step = "feedback"
                st.rerun()

    else:
        st.warning("AI 피드백이 아직 로드되지 않았습니다. 다시 시도해주세요.")

def display_previous_conversations(messages):
    for i, message in enumerate(messages):
        role = message["role"]
        content = message["content"]
        timestamp = message.get("timestamp", "")
            
        if role == "user":
            st.markdown(f"**You** ({timestamp}):")
            st.markdown(content)
        elif role == "assistant" or role == "system":
            st.markdown(f"**AI** ({timestamp}):")
            st.markdown(content)

# 피드백 페이지
def feedback_page():
    st.title("인공지능 사용 피드백 입력하기")
    
    st.header("이전 대화 내용 확인")
    st.markdown("---")

    tabs = st.tabs(["탐구 질문", "가설", "배경이론", "준비물 및 탐구과정"])
    
    with tabs[0]:
        st.header("탐구 질문 대화 기록")
        display_previous_conversations(st.session_state.all[0])
        st.header("탐구 질문 피드백")
        st.markdown(st.session_state.sum_problem)

    with tabs[1]:
        st.header("가설 대화 기록")
        display_previous_conversations(st.session_state.all[1])
        st.header("가설 피드백")
        st.markdown(st.session_state.sum_hypothesis)

    with tabs[2]:
        st.header("배경이론 대화 기록")
        display_previous_conversations(st.session_state.all[2])
        st.header("배경이론 피드백")
        st.markdown(st.session_state.sum_theory)

    with tabs[3]:
        st.header("준비물 및 탐구과정 대화 기록")
        display_previous_conversations(st.session_state.all[3])
        st.header("준비물 및 탐구과정 피드백")
        st.markdown(st.session_state.sum_process)

    st.markdown("---")

    st.header("최종 인공지능 활용에 대한 피드백 입력")
    
    feedbacks = []
    feedbacks.append(st.slider("1. 나는 인공지능에 대해 배우는 것이 좋다.", 1, 5))
    feedbacks.append(st.slider("2. 나는 학습을 할 때 인공지능을 사용하는 것이 재미있다.", 1, 5))
    feedbacks.append(st.slider("3. 나는 학습을 할 때 인공지능을 사용하면 편안하다.", 1, 5))
    feedbacks.append(st.slider("4. 나는 과제를 할 때 인공지능을 사용하면 안심이 된다.", 1, 5))
    feedbacks.append(st.slider("5. 인공지능을 사용하는 것은 사람과의 대화가 없어서 불편하다.", 1, 5))
    feedbacks.append(st.slider("6. 나는 인공지능을 사용했을 때 틀린 답변이 나올까 봐 걱정된다.", 1, 5))
    feedbacks.append(st.slider("7. 나는 인공지능을 사용할 수 없으면 불안하다.", 1, 5))
    feedbacks.append(st.slider("8. 학습을 할 때 인공지능을 사용하는 기술은 학생들에게 꼭 필요하다.", 1, 5))
    feedbacks.append(st.slider("9. 인공지능은 학습에 도움을 준다.", 1, 5))
    feedbacks.append(st.slider("10. 인공지능은 학습 경험을 향상시킨다.", 1, 5))
    feedbacks.append(st.slider("11. 인공지능은 학습과 관련된 자신감을 높여준다.", 1, 5))
    feedbacks.append(st.slider("12. 인공지능은 글 쓰는 능력을 키워준다.", 1, 5))
    feedbacks.append(st.slider("13. 인공지능은 공부에 대한 내 개인적인 요구를 채워준다.", 1, 5))
    feedbacks.append(st.slider("14. 인공지능은 평생학습을 지원한다.", 1, 5))
    feedbacks.append(st.slider("15. 인공지능은 창의력 같은 높은 수준의 기술을 키워준다.", 1, 5))
    feedbacks.append(st.slider("16. 나는 인공지능의 발전을 계속 지켜볼 것이다.", 1, 5))
    feedbacks.append(st.slider("17. 나는 인공지능을 사용해서 얻은 좋은 점들을 친구와 이야기할 것이다.", 1, 5))
    feedbacks.append(st.slider("18. 나는 인공지능을 과외 선생님처럼 사용할 것이다.", 1, 5))
    feedbacks.append(st.slider("19. 나는 인공지능을 학습 자료로 사용할 것이다.", 1, 5))
    feedbacks.append(st.slider("20. 나는 시험 공부와 연습을 위해 인공지능을 사용할 것이다.", 1, 5))
    feedbacks.append(st.slider("21. 나는 학습 자료를 요약하고 분석할 때 인공지능을 사용할 것이다.", 1, 5))
    feedbacks.append(st.slider("22. 나는 학습 목표를 이루기 위해 인공지능을 계속 사용할 것이다.", 1, 5))
    feedbacks.append(st.text_area("23. 인공지능을 이용한 탐구 설계 활동은 어떤 점에서 긍정적이었는지, 그렇게 생각한 이유(사례)와 함께 적어주세요."))
    feedbacks.append(st.text_area("24. 인공지능을 이용한 탐구 설계 활동은 어떤 점에서 아쉬웠는지, 그렇게 생각한 이유(사례)와 함께 적어주세요."))
    feedbacks.append(st.text_area("25. 인공지능을 이용한 탐구 설계 활동에서 인공지능을 무엇이라고 생각하고 사용했습니까? (예시) 친구나 동료, 선생님, 전지전능한 신, 기계 등"))
    feedbacks.append(st.text_area("26. 여러분들이 교사가 되었을 때, 학생들의 탐구 설계 활동에 인공지능을 활용한다면 어떤 방법으로 하면 좋을지, 그 방법과 그렇게 생각한 이유를 적어주세요."))
    
    if st.button("제출"):
        for i in range(26):
            update_table(f"feedback{i+1}", feedbacks[i])
        st.success("피드백이 제출되었습니다.")

# 파일 업로드 후 데이터를 MySQL에 저장하는 페이지
def upload_page():
    st.title("파일 업로드 및 파싱")

    # PDF 파일만 업로드 가능하도록 설정
    uploaded_file = st.file_uploader("PDF 파일을 업로드하세요.", type="pdf")

    # 새 파일 업로드 시 기존 상태 초기화
    if uploaded_file is not None and uploaded_file != st.session_state.last_uploaded_file:
        st.session_state.upload_processed = False  # 새로운 파일이 업로드되면 상태를 초기화
        st.session_state.last_uploaded_file = uploaded_file
        st.write(f"파일이 성공적으로 업로드되었습니다: {uploaded_file.name}")

    st.session_state.topic = st.selectbox("주제를 선택하세요", probs.keys())
    st.text_area("탐구 문제", st.session_state.problem, height=150)
    st.text_area("가설", st.session_state.hypothesis, height=150)
    st.text_area("배경 이론", st.session_state.theory, height=150)
    st.text_area("준비물", st.session_state.apparatus, height=150)
    st.text_area("탐구 과정", st.session_state.process, height=150)

    # 파일 업로드가 이미 처리된 경우, 다시 처리하지 않도록 조건을 추가
    if uploaded_file is not None and not st.session_state.upload_processed:        
        # 파일 확장자를 포함한 원본 파일명 얻기
        file_extension = os.path.splitext(uploaded_file.name)[1]  # 파일 확장자 (.pdf)
        base_filename = f"{st.session_state.name}"  # 파일의 기본 이름

        # uploads 폴더에 중복되지 않는 파일명 생성
        counter = 1
        file_path = os.path.join('uploads', f"{base_filename}{file_extension}")
        
        while os.path.exists(file_path):
            file_path = os.path.join('uploads', f"{base_filename}{counter}{file_extension}")
            counter += 1

        # 파일을 지정된 경로에 저장
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
                
        api_key = os.getenv("UPSTAGE_API_KEY")
        url = "https://api.upstage.ai/v1/document-ai/document-parse"
        headers = {"Authorization": f"Bearer {api_key}"}
        files = {"document": open(file_path, "rb")}
        data = {"output_formats": "['text']"}
        response = requests.post(url, headers=headers, files=files, data=data)
        result = response.json()
        elements = result['elements']

        contents = ["", "", "", "", ""]
        headings = ["탐구 문제", "가설", "배경이론", "준비물", "탐구 과정"]
        is_ok = False
        nums = 0
        title = ''
            
        for element in elements:
            category = element['category'].strip()
            text = element['content']['text'].strip()

            if 'heading' in category and '탐구 계획서' in text:
                is_ok = True
                continue

            if is_ok:
                if nums == 0:
                    #print(f"Title: {text}")
                    nums += 1
                    continue
                if 'heading' in category:
                    if contains_heading(text, headings):
                        #print(f"Here - {text}")
                        nums += 1
                        continue

                if 'table' in category and nums == 1:
                    # 학번과 성명을 추출하는 정규 표현식
                    pattern = r"학번\s(\d+)\s성명\s(\S+)"
                    match = re.search(pattern, text)
                    
                    # 학번과 성명 추출
                    if match:
                        student_id = match.group(1)
                        student_name = match.group(2)
                        #print(f"학번: {student_id}, 성명: {student_name}")
                    else:
                        print("학번과 성명을 찾을 수 없습니다.")
                    continue

                contents[nums-2] += '\n'
                contents[nums-2] += text

        # 여기에서 parse_pdf.ipynb 참고하여 PDF 파싱 후 아래 정보 채우기
        st.session_state.problem = contents[0].strip()
        st.session_state.hypothesis = contents[1].strip()
        st.session_state.theory = contents[2].strip()
        st.session_state.apparatus = contents[3].strip()
        st.session_state.process = contents[4].strip()
        # 파일이 처리되었음을 저장
        st.session_state.upload_processed = True
        st.rerun()
        
    # 다음 버튼 클릭 시 MySQL에 저장
    if st.button("다음"):
        if st.session_state.topic and st.session_state.problem:
            save_initial_inquiry_data()
            st.session_state.step = "problem"
            st.success("탐구 정보가 저장되었습니다.")
            print("Successfully saved.")
            st.rerun()
        else:
            st.error("주제와 탐구 문제를 입력해야 합니다.")

# 단계별 페이지 호출
if "step" not in st.session_state:
    st.session_state.step = "start"

if st.session_state.step == "start":
    start_page()
elif st.session_state.step == "disclaimer":
    disclaimer_page()
elif st.session_state.step == "upload":
    upload_page()
elif st.session_state.step == "problem":
    inquiry_problem_page()
elif st.session_state.step == "hypothesis":
    inquiry_hypothesis_page()
elif st.session_state.step == "theory":
    inquiry_theory_page()
elif st.session_state.step == "process":
    inquiry_process_page()
elif st.session_state.step == "overall":
    overall_page()
elif st.session_state.step == "feedback":
    feedback_page()
