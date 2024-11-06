import streamlit as st
import pandas as pd
import mysql.connector
from dotenv import load_dotenv
import os
from datetime import datetime
import time
from dotenv import load_dotenv
from openai import OpenAI
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import re

# .env 파일 불러오기
load_dotenv()

# MySQL 환경 변수 불러오기
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_DATABASE')

# MySQL 연결 설정
db_connection = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME
)
cursor = db_connection.cursor()

# 문제 풀이 단계
def load_information(i):
    """엑셀 파일에서 특정 도메인의 문제 로드"""
    return df.loc[i, 'domain'], df.loc[i, 'content'], df.loc[i, 'performance']

# MySQL에 데이터 저장 예시
def save_conversation_to_db(domain_idx, conversation, duration):
    domain_content_column = f"domain_{domain_idx}_content"
    domain_time_column = f"domain_{domain_idx}_time"
    domain_done_column = f"domain_{domain_idx}_done"
    
    # 대화 내용 및 시간을 저장하는 쿼리 (id 기준으로 업데이트)
    update_query = f"""
    UPDATE paced_learning 
    SET {domain_content_column}=%s, {domain_time_column}=%s, {domain_done_column}=1 
    WHERE id=%s
    """
    print(f"Saved ID: {st.session_state.user_id}")
    
    save_to_db(update_query, (conversation, duration, st.session_state.user_id))

def save_to_db(query, values):
    try:
        cursor.execute(query, values)
        db_connection.commit()
    except mysql.connector.Error as err:
        st.error(f"MySQL 오류가 발생했습니다: {err}")
        db_connection.rollback()

# LaTeX 수식과 일반 텍스트를 구분하여 처리하는 함수
def process_text(text):
    # 여러 종류의 LaTeX 수식 패턴을 감지하는 정규 표현식
    pattern = r'(\$\$.*?\$\$|\$.*?\$|\\\[.*?\\\]|\\\(.*?\\\))'
    
    # 입력된 텍스트에서 LaTeX 부분과 일반 텍스트를 분리
    parts = re.split(pattern, text)

    # 분리된 각 부분을 순서대로 처리
    for part in parts:
        part = part.strip()  # 앞뒤 공백 제거
        if re.match(r'^\$\$.*\$\$$', part):  # $$ ... $$ 형식 감지
            st.latex(part.strip('$$'))
        elif re.match(r'^\$.*\$$', part):  # $ ... $ 형식 감지
            st.latex(part.strip('$'))
        elif re.match(r'^\\\[.*\\\]$', part):  # \[ ... \] 형식 감지
            st.latex(part.strip('\\[').strip('\\]'))
        elif re.match(r'^\\\(.*\\\)$', part):  # \( ... \) 형식 감지
            st.latex(part.strip('\\(').strip('\\)'))
        else:
            st.markdown(part)  # 나머지는 일반 텍스트로 출력

initial_prompt = (
    "이것은 일반물리학 열역학 분야 학습용 챗봇이야."
    "제공되는 영역, 요소, 기대 수준을 고려하여 문제를 생성하고 풀이 과정과 함께 정답을 입력하도록 요구해."
    "1. 문제는 기초 수준부터 생성하고, 정답을 맞추면 보통 수준 문제으로 넘어가. 그리고 보통 수준을 맞추면 심화 수준 문제로 넘어가고. 만약 정답이 틀리면 같은 수준의 문제를 학습자가 이미 틀린 문제에 대한 응답을 고려해서 같은 수준을 다시 출제하고 그걸 맞추면 그 위 난이도를 출제하도록 해. 그리고 심화 수준까지 맞추면 종료해."
    "2. 만약 같은 수준 문제를 3개 이상 틀리면 '해당 영역 학습이 종료되었습니다. 다음 버튼을 누르세요.'라고 출력해."
    "3. 문제를 틀리면 바로 다음 문제를 풀지 않고, 다음과 같은 전략을 통해 오답 풀이를 진행하도록 해."
    "(1) 먼저 문제가 요구하는 것이 무엇인지 물어보고, 이를 알면 다음 스텝으로, 모르면 문제가 요구하는 것이 무엇인지 설명해 줘."
    "(2) 그 다음은 문제와 관련된 주요 개념이나 법칙이 무엇인지 물어보고, 이를 알면 다음 스텝으로, 모르면 문제와 관련된 개념과 스텝이 무엇인지 설명해 줘."
    "(3) 그리고 문제를 어떻게 풀면 좋을지 풀이 전략에 대해 물어보고, 이를 알면 실제 문제를 풀어보도록 하고, 모르면 전략에 대해 설명해 줘."
    "(4) 최종적으로 문제를 다 풀었으면 그럼 새로운 문제를 제시하면 돼."
    "(1)~(4)의 단계는 계산 문제인지 아닌지에 따라서 융통성 있게 적용해 줘. 이건 정량적인 계산을 다루는 문제에 국한해서 제시한 거야."
)

# 챗봇 응답 함수
def get_chatgpt_response(i, prompt):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if prompt == "":
        st.session_state[f"messages {i}"].append({"role": "user", "content": "학습을 시작하겠습니다.", "timestamp": timestamp})
    else:
        st.session_state[f"messages {i}"].append({"role": "user", "content": prompt, "timestamp": timestamp})
    
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=st.session_state[f"messages {i}"],
    )
    
    answer = response.choices[0].message.content
    print(f"from server: {answer}")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    st.session_state[f"messages {i}"].append({"role": "assistant", "content": answer, "timestamp": timestamp})    

    return answer

# 파일 불러오기 (엑셀 파일)
excel_file = './general_que.xlsx'
df = pd.read_excel(excel_file)

total_domains = 6

# Streamlit app
st.markdown("""
    <h1 style='text-align: center;'>AI 기반 일반물리학 피드백 시스템</h1>
""", unsafe_allow_html=True)

if 'state' not in st.session_state:
    st.session_state.state = 'intro'
    st.session_state.domain = -1
    st.session_state.completed_domains = 0
    st.session_state.progress = 0  # Progress 초기값 설정
    print("Initialized OK")
    print(f"Complete domain: {st.session_state.completed_domains}")

if st.session_state.state == 'intro':
    col1, col2, col3 = st.columns([1, 3, 1])

    with col2:
        # 기본 사용자 정보 입력
        st.title("물리학습 자동 평가")
        name = st.text_input("이름을 입력해 주세요")
        email = st.text_input("이메일을 입력해 주세요")

        # 학습 시작 단계
        if st.button("확인"):
            if not name or not email:
                st.error("이름과 이메일을 모두 입력해 주세요.")
            elif "@" not in email or "." not in email:
                st.error("유효한 이메일을 입력해 주세요.")
            else:
                st.session_state.name = name
                st.session_state.email = email
                st.session_state.state = "disclaimer"
                st.rerun()

# 동의 후 이전 데이터 불러오기
elif st.session_state.state == "disclaimer":
    st.title("Disclaimer")
    st.write("""
    이 프로그램은 AI 기반 학습 프로그램입니다. 학습자의 수준에 따라 맞춤형 문제가 제시되며, 학습 내용과 대화 내용이 기록됩니다.
    모든 학습 결과가 완료되면 전문가의 검토를 거쳐 입력한 이메일을 통해 결과가 전송됩니다.
    서버로의 통신 시간이 걸리기 때문에 응답이 올 때까지는 기다렸다가 다음 메시지를 입력하기 바랍니다.
    '동의'를 누르면 이에 동의한 것으로 간주합니다.
    """)

    if st.button("동의"):
        print("Agreed.")
        # MySQL에서 해당 사용자의 가장 최근 학습 데이터를 조회
        select_query = """
        SELECT id, domain_1_done, domain_2_done, domain_3_done, domain_4_done, domain_5_done, domain_6_done
        FROM paced_learning
        WHERE email = %s AND complete = 0
        ORDER BY date DESC
        LIMIT 1
        """
        cursor.execute(select_query, (st.session_state.email,))
        result = cursor.fetchone()

        if result:
            print("Found record")
            st.session_state.user_id = result[0]
            st.session_state.completed_domains = sum(result[1:])  # 완료된 도메인 수 계산
            st.session_state.domain = result[1:].index(0) if 0 in result[1:] else total_domains
            
            # 6개 도메인이 모두 완료되었는지 확인
            if st.session_state.completed_domains >= total_domains:
                st.session_state.state = 'feedback'
                st.rerun()
            else:
                # 라디오 버튼을 통해 선택을 묻는 부분 추가
                load_data_choice = st.radio("이전에 학습했던 데이터를 불러오시겠습니까?", ("예", "아니요"))
                
                if load_data_choice == "예":
                    print("Yes")
                    # 이전 데이터에서 진행 상황을 복원
                    st.session_state.state = "quiz"
                    st.session_state.progress = st.progress(st.session_state.completed_domains / total_domains)
                    st.rerun()
                elif load_data_choice == "아니요":
                    print("No")
                    # 새로운 레코드 생성
                    insert_query = """
                    INSERT INTO paced_learning (name, email, date) VALUES (%s, %s, NOW())
                    """
                    cursor.execute(insert_query, (st.session_state.name, st.session_state.email))
                    db_connection.commit()
                    st.session_state.user_id = cursor.lastrowid

                    st.session_state.state = "quiz"
                    st.session_state.progress = st.progress(0)
                    st.rerun()
        else:
            print("Not found")
            # 이전 데이터가 없으면 새로운 레코드 생성
            insert_query = """
            INSERT INTO paced_learning (name, email, date) VALUES (%s, %s, NOW())
            """
            cursor.execute(insert_query, (st.session_state.name, st.session_state.email))
            db_connection.commit()
            st.session_state.user_id = cursor.lastrowid

            st.session_state.state = "quiz"
            st.session_state.progress = st.progress(0)
            st.rerun()

elif st.session_state.state == "quiz":
    st.header("문제 풀이")

    # start_time이 존재하지 않으면 초기화 (처음 퀴즈가 시작될 때)
    if 'start_time' not in st.session_state:
        st.session_state.start_time = datetime.now()  # 대화 시작 시간을 설정

    if st.session_state.domain == -1:
        st.session_state.domain += 1

    if 'progress' in st.session_state:
        progress_percent = st.session_state.completed_domains / total_domains
        st.progress(progress_percent)  # 매번 새로운 progress 객체 생성
    
    index = st.session_state.domain
    answer = ""

    if not f"messages {index}" in st.session_state:
        domain_name, content, perform = load_information(index)
        prompt = content + '\n' + perform + '\n' + initial_prompt
        st.header(domain_name)
        st.session_state[f"messages {index}"] = [{"role": "system", "content": prompt}]
        answer = get_chatgpt_response(st.session_state.domain, "")

    # 대화 기록 출력 (Markdown 적용 + LaTeX 처리)
    if f"messages {index}" in st.session_state:
        for message in st.session_state[f"messages {index}"]:
            role = message["role"]
            content = message["content"]
            timestamp = message.get("timestamp", "")

            if role == "user":
                st.markdown(f"**You** ({timestamp}):")
                process_text(content)  # LaTeX과 텍스트 처리
            elif role == "assistant":
                st.markdown(f"**AI** ({timestamp}):")
                process_text(content)  # LaTeX과 텍스트 처리

    with st.form(key='quiz_form', clear_on_submit=True):
        user_input = st.text_area("You: ", key="user_input")
        submit = st.form_submit_button(label="제출")

        if submit and user_input:
            answer = get_chatgpt_response(st.session_state.domain, user_input)
            
            # 대화 종료 시간과 걸린 시간 계산
            end_time = datetime.now()
            duration = (end_time - st.session_state.start_time).total_seconds() / 60.0  # 분 단위로 변환

            # 대화 내용 저장
            conversation = "\n".join([f"{msg['role']} ({msg.get('timestamp', 'N/A')}): {msg['content']}" for msg in st.session_state[f"messages {index}"]])
            
            # MySQL에 대화 내용과 시간을 업데이트 (id 기준으로)
            save_conversation_to_db(index + 1, conversation, duration)

            # 리렌더링
            st.rerun()  # 상태 업데이트 후 즉시 리렌더링

    # 마지막 메시지를 확인
    last_message = st.session_state[f"messages {index}"][-1]['content'] if st.session_state[f"messages {index}"] else ""

    # 마지막 메시지에 '학습 종료' 관련 키워드가 있는지 확인
    if "완료" in last_message or "종료" in last_message or "마쳤습니다" in last_message or "마치겠습니다" in last_message or '알겠습니다' in last_message or '중단' in last_message:
        st.success("학습이 종료되었습니다. 다음 단계를 진행하세요.")
        
        # '다음' 버튼을 렌더링하여 다음 도메인으로 진행
        if st.button(label='다음'):
            st.session_state.completed_domains += 1  # 완료된 도메인 개수 업데이트
            print(f"Current: {st.session_state.completed_domains} out of {total_domains}")
            
            if st.session_state.completed_domains >= total_domains:
                st.session_state.state = 'feedback'  # 모든 도메인이 끝나면 피드백 단계로 이동
            else:
                st.session_state.domain += 1  # 다음 도메인으로 이동
                st.session_state.start_time = datetime.now()  # 새로운 도메인 시작 시간 설정
            st.rerun()  # 상태 갱신
                           
# 피드백 단계
elif st.session_state.state == "feedback":
    st.header("피드백")
    feedback_q1 = st.slider("나의 물리학 수준은 어느 정도라고 생각합니까?", 1, 5)
    feedback_q2 = st.slider("나는 물리학습에 얼마나 열정과 관심을 갖고 있습니까?", 1, 5)
    feedback_q3 = st.slider("인공지능은 나의 이해나 의도를 잘 파악하였습니까?", 1, 5)
    feedback_q4 = st.slider("인공지능을 이용한 문제 풀이는 문제를 해결하는 데에 도움이 되었습니까?", 1, 5)
    feedback_q5 = st.slider("인공지능이 제시한 설명이나 답변은 신뢰할 수 있습니까?", 1, 5)
    feedback_q6 = st.slider("인공지능을 이용한 문제 풀이는 주의를 집중하고 학습하는 데에 긍정적입니까?", 1, 5)
    feedback_q7 = st.slider("인공지능을 이용한 학습을 통해 내 물리 이해가 향상되었다고 생각합니까?", 1, 5)
    feedback_q8 = st.slider("다른 단원에 대해서도 AI 기반 학습에 참여할 의사가 있습니까?", 1, 5)
    feedback_q9 = st.text_area("인공지능을 활용한 학습 소감에 대해 자유롭게 남겨주세요.")
    feedback_q10 = st.text_area("본 시스템의 문제점이나 개선해야 할 점에 대해 자유롭게 남겨주세요.")

    if st.button("제출"):
        # id 값을 세션에서 가져와서 그 id로 업데이트
        if 'user_id' in st.session_state:
            user_id = st.session_state['user_id']
            insert_feedback_query = """
            UPDATE paced_learning 
            SET feedback_1=%s, feedback_2=%s, feedback_3=%s, feedback_4=%s, feedback_5=%s,
                feedback_6=%s, feedback_7=%s, feedback_8=%s, feedback_9=%s, feedback_10=%s, complete=1
            WHERE id=%s
            """
            cursor.execute(insert_feedback_query, (feedback_q1, feedback_q2, feedback_q3, feedback_q4, feedback_q5,
                                                   feedback_q6, feedback_q7, feedback_q8, feedback_q9, feedback_q10, user_id))
            db_connection.commit()
            st.success("피드백이 제출되었습니다. 감사합니다!")
        else:
            st.error("유저 ID를 찾을 수 없습니다. 처음부터 다시 시도해 주세요.")
