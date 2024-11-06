import streamlit as st
import pandas as pd
from pathlib import Path
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv
import re  # 정규표현식을 위한 import 추가

load_dotenv()

def send_email(receiver_email, dataframe):
    # 이메일 계정 설정 (여기서는 Gmail을 예로 듭니다)
    sender_email = os.getenv("EMAIL_ADDRESS")
    sender_password = os.getenv("EMAIL_PASSWORD")
    
    # 이메일 제목과 수신자 설정
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = "지도안 평가 결과"

    # 이메일 본문 내용 생성
    html = dataframe.to_html()
    body = f"""
    <html>
    <body>
        <p>안녕하세요,</p>
        <p>다음은 지도안 평가 결과입니다:</p>
        {html}
        <p>감사합니다.</p>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(body, "html"))

    # SMTP 서버 연결 및 이메일 전송
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        print("이메일 전송 성공")
    except Exception as e:
        print(f"이메일 전송 실패: {e}")
        
# Step 1: User Authentication
st.set_page_config(layout="wide")
st.title("지도안 수정을 위한 가이드 웹페이지")

def is_valid_email(email):
    # 이메일 형식을 확인하는 정규표현식 패턴
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def start_page():
    # 사용자 정보 입력
    name = st.text_input("이름")
    email = st.text_input("이메일")
    
    # 비밀번호 입력 필드 위에 안내 문구 추가
    st.write("비밀번호를 설정하지 않은 경우, 학번 8자리를 입력하시기 바랍니다.")
    password = st.text_input("비밀번호", type="password")

    if st.button("확인"):
        # 이메일 형식 검증
        if not is_valid_email(email):
            st.error("올바른 이메일 형식이 아닙니다.")
            return
            
        # id.xlsx 파일에서 name과 password가 일치하는지 확인
        id_file = Path("id.xlsx")
        if id_file.exists():
            id_data = pd.read_excel(id_file)
            user_match = id_data[(id_data['name'] == name) & (id_data['passcode'] == password)]
            
            if not user_match.empty:
                st.session_state["authenticated"] = True
                st.session_state["name"] = name
                st.session_state["email"] = email
                st.session_state.step = 'disclaimer'
                st.success("인증되었습니다.")
                st.rerun()
            else:
                st.error("이름 또는 비밀번호가 일치하지 않습니다.")
        else:
            st.error("ID 파일이 존재하지 않습니다.")
            
def agree_page():
    # Step 2: Disclaimer 화면
    if "authenticated" in st.session_state and st.session_state["authenticated"]:
        st.write("이것은 동료학습과 AI, 전문가의 도움을 받아 지도안을 수정할 수 있도록 만든 웹페이지입니다.")
        if st.button("동의"):
            st.session_state["agreed"] = True
            st.session_state.step = 'view'
            st.rerun()

def view_page():
    # Step 3: Display 평가 데이터 테이블
    if "agreed" in st.session_state and st.session_state["agreed"]:
        # 평가 데이터 불러오기
        peer_file = Path("peer_comment.xlsx")
        expert_file = Path("expert_comment.xlsx")
        ai_file = Path("ai_comment.xlsx")

        if peer_file.exists() and expert_file.exists() and ai_file.exists():
            peer_data = pd.read_excel(peer_file)
            expert_data = pd.read_excel(expert_file)
            ai_data = pd.read_excel(ai_file)

            # 사용자 이름에 맞는 평가 데이터 필터링
            user_peer = peer_data[peer_data['name'] == st.session_state["name"]][['goal', 'intro', 'model', 'explain', 'response', 'eval']]
            user_expert = expert_data[expert_data['name'] == st.session_state["name"]][['goal', 'intro', 'model', 'explain', 'response', 'eval']]
            user_ai = ai_data[ai_data['name'] == st.session_state["name"]][['goal', 'intro', 'model', 'explain', 'response', 'eval']]

            # 행과 열을 재구성하여 표 형식으로 구성
            if not user_peer.empty and not user_expert.empty and not user_ai.empty:
                # 행과 열을 재구성
                table_data = pd.DataFrame({
                    '동료': user_peer.values.flatten(),
                    '교수자': user_expert.values.flatten(),
                    'AI': user_ai.values.flatten()
                }, index=['학습목표', '도입', '수업모형', '개념설명', '학습자 반응', '정리 및 평가'])

                st.write("평가 결과")

                # 텍스트 줄바꿈을 위한 함수
                def make_text_wrappable(text):
                    return '<div style="white-space: pre-wrap; word-wrap: break-word; height: auto;">' + text + '</div>'

                # DataFrame의 모든 셀에 스타일 적용
                styled_df = table_data.style.format(make_text_wrappable)
                styled_df.set_properties(**{
                    'white-space': 'pre-wrap',
                    'height': 'auto',
                    'min-height': '150px',
                    'text-align': 'left',
                    'vertical-align': 'top',
                    'padding': '10px'
                })

                # 스타일이 적용된 데이터프레임 출력
                st.markdown(
                    """
                    <style>
                    .dataframe td, .dataframe th {
                        white-space: pre-wrap !important;
                        min-height: 150px !important;
                        vertical-align: top !important;
                        padding: 10px !important;
                    }
                    </style>
                    """,
                    unsafe_allow_html=True
                )
                st.write(styled_df.to_html(escape=False), unsafe_allow_html=True)
                
                # Step 4: 결과 전송
                if st.button("결과 전송"):
                    if "name" in st.session_state and "email" in st.session_state:
                        # 이메일 전송 기능 호출
                        send_email(st.session_state["email"], table_data)
                        st.success("결과가 이메일로 전송되었습니다.")
                    else:
                        st.error("인증이 필요합니다.")
            else:
                st.warning("해당 사용자의 평가 데이터가 없습니다.")
        else:
            st.error("평가 파일을 찾을 수 없습니다.")
                 
# 단계별 페이지 호출
if "step" not in st.session_state:
    st.session_state.step = "start"

if st.session_state.step == "start":
    start_page()
elif st.session_state.step == "disclaimer":
    agree_page()
elif st.session_state.step == "view":
    view_page()