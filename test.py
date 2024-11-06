import re
import streamlit as st

def display_text_and_latex(text):
    # 수식 구분을 위한 패턴 정의 (원시 문자열 사용)
    pattern = r'(\\\[.*?\\\]|\\\(.*?\\\))'
    
    # 패턴을 기준으로 문자열을 분리
    parts = re.split(pattern, text, flags=re.DOTALL)
    
    print(parts)  # 디버깅용 출력
    
    for part in parts:
        # 수식 부분이 LaTeX 구분 기호로 둘러싸여 있는지 확인 (re.fullmatch 사용)
        if re.fullmatch(pattern, part, flags=re.DOTALL):  # LaTeX 수식인 경우
            print("LaTeX 수식 부분:", part)
            
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
            
            st.latex(cleaned_latex.strip())  # LaTeX 수식 렌더링
        else:
            # 일반 텍스트인 경우
            st.markdown(part)

# 테스트할 문자열 (원시 문자열로 처리해야 백슬래시 문제가 해결됨)
text = '''
질량 m인 물체가 스프링에 연결되어 있을 때, 변위에 비례하는 복원력이 작용하며, 이 때 운동 방정식은 다음과 같이 주어진다:
\[
\\frac{d^2x}{dt^2} = -kx
\]
이 미분 방정식을 풀고, 그 해가 물리적으로 무엇을 의미하는지 설명하시오.
'''

text = '''
이상 기체의 압력이 다음과 같이 주어진다:
\( P(V) = \\frac{nRT}{V} \)
기체가 부피 $( V_1 $)에서 $ (V_2 $)로 변화할 때 수행하는 일을 구하고 풀이 과정을 설명하시오.
'''

# 함수 호출
display_text_and_latex(text)
