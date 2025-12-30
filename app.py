import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
import tempfile
from langchain_community.document_loaders import PyPDFLoader
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

# -----------------------------------------------------------------------------
# [1] 기본 설정
# -----------------------------------------------------------------------------
st.set_page_config(page_title="KW-GraduSafe: 공지사항 분석기", page_icon="🎓", layout="wide")

# 사이드바에서 API 키 입력 받기 (보안)
with st.sidebar:
    st.header("⚙️ 설정")
    # [수정 포인트 1] 여기에 본인의 구글 API 키를 따옴표 안에 넣으세요. 매번 입력 안 해도 됩니다.
    default_api_key = ""  # 예: "AIzaSy..."
    
    api_key = st.text_input("Google API Key", value=default_api_key, type="password", placeholder="AIzaSy...")
    
    if not api_key:
        st.info("구글 AI Studio에서 받은 무료 키를 입력하세요.")
    else:
        st.success("API 키가 입력되었습니다!")
        
    st.markdown("---")
    st.markdown("**[사용법]**")
    st.markdown("1. 광운대 공지사항 게시글 URL을 복사합니다.")
    st.markdown("2. URL 입력창에 붙여넣습니다.")
    st.markdown("3. 분석 버튼을 누르고 질문합니다.")

# -----------------------------------------------------------------------------
# [2] 핵심 기능 함수 (크롤링 & AI)
# -----------------------------------------------------------------------------

# 함수 1: URL에서 PDF 링크 찾기 (크롤링)
def get_pdf_links(url):
    try:
        # 광운대 홈페이지는 봇 차단이 있을 수 있어 헤더 추가
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        pdf_list = []
        # 'a' 태그 중 href가 .pdf로 끝나는 것 찾기
        for a_tag in soup.find_all('a', href=True):
            if a_tag['href'].lower().endswith('.pdf'):
                # 상대 경로인 경우 절대 경로로 변환 (광운대 기준)
                file_url = a_tag['href']
                if not file_url.startswith('http'):
                    if file_url.startswith('/'):
                        file_url = 'https://www.kw.ac.kr' + file_url
                    else:
                        file_url = 'https://www.kw.ac.kr/kw_service/' + file_url # 예시 경로
                
                pdf_list.append({
                    "name": a_tag.get_text(strip=True) or "이름 없는 PDF",
                    "url": file_url
                })
        return pdf_list
    except Exception as e:
        st.error(f"크롤링 중 오류 발생: {e}")
        return []

# 함수 2: PDF 다운로드 및 텍스트 추출
def download_and_parse_pdf(pdf_url):
    try:
        response = requests.get(pdf_url)
        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(response.content)
            tmp_file_path = tmp_file.name
        
        # LangChain으로 읽기
        loader = PyPDFLoader(tmp_file_path)
        pages = loader.load_and_split()
        
        full_text = ""
        for page in pages:
            full_text += page.page_content
            
        # 임시 파일 삭제
        os.remove(tmp_file_path)
        return full_text
    except Exception as e:
        st.error(f"PDF 처리 중 오류 발생: {e}")
        return None

# 함수 3: AI에게 질문하기
def ask_gemini(text, question, key):
    os.environ["GOOGLE_API_KEY"] = key
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
    
    template = """
    너는 광운대학교 행정 문서를 분석해주는 스마트한 AI 비서야.
    아래 [문서 내용]을 꼼꼼히 읽고 [질문]에 대해 정확하게 답변해줘.
    문서에 없는 내용은 추측하지 말고 "문서에 나와있지 않습니다"라고 말해.
    중요한 날짜나 요건은 굵게 표시해줘.

    [문서 내용]
    {context}

    [질문]
    {question}
    """
    prompt = PromptTemplate(template=template, input_variables=["context", "question"])
    chain = prompt | llm
    response = chain.invoke({"context": text, "question": question})
    return response.content

# -----------------------------------------------------------------------------
# [3] 메인 UI 구성
# -----------------------------------------------------------------------------
st.title("🔗 공지사항 PDF 자동 분석기")
st.markdown("광운대 공지사항 링크만 넣으세요. PDF를 찾아 읽어드립니다.")

# 세션 상태 초기화 (대화 기록 저장용)
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "pdf_text" not in st.session_state:
    st.session_state.pdf_text = None

# 1. URL 입력
# [수정 포인트 2] 자주 테스트하는 공지사항 URL을 여기에 넣어두세요.
default_url = "" # 예: "https://www.kw.ac.kr/ko/life/notice.jsp?BoardMode=view&bid=..."

target_url = st.text_input("공지사항 URL 입력", value=default_url, placeholder="https://www.kw.ac.kr/ko/life/notice.jsp?BoardMode=view&bid=...")

if st.button("PDF 찾기"):
    if not target_url:
        st.warning("URL을 입력해주세요.")
    else:
        with st.spinner("홈페이지를 탐색 중입니다..."):
            pdfs = get_pdf_links(target_url)
            if not pdfs:
                st.error("첨부된 PDF 파일을 찾을 수 없습니다. (로그인 필요한 페이지는 안 될 수 있습니다)")
            else:
                st.success(f"PDF {len(pdfs)}개를 발견했습니다!")
                # 발견된 PDF 리스트를 세션에 저장
                st.session_state.found_pdfs = pdfs

# 2. PDF 선택 및 분석
if "found_pdfs" in st.session_state and st.session_state.found_pdfs:
    selected_pdf = st.selectbox(
        "분석할 파일을 선택하세요", 
        st.session_state.found_pdfs, 
        format_func=lambda x: x['name']
    )
    
    if st.button("이 파일 분석하기"):
        if not api_key:
            st.warning("왼쪽 사이드바에 API Key를 먼저 입력해주세요!")
        else:
            with st.spinner(f"'{selected_pdf['name']}' 다운로드 및 분석 중..."):
                text_content = download_and_parse_pdf(selected_pdf['url'])
                if text_content:
                    st.session_state.pdf_text = text_content
                    st.session_state.current_pdf_name = selected_pdf['name']
                    st.success("분석 완료! 아래 채팅창에서 질문하세요.")
                    # 채팅 기록 초기화
                    st.session_state.chat_history = [{"role": "ai", "message": f"'{selected_pdf['name']}' 파일 내용을 학습했습니다. 무엇이든 물어보세요!"}]

# 3. 채팅 인터페이스
if st.session_state.pdf_text:
    st.divider()
    st.subheader(f"💬 {st.session_state.current_pdf_name} Q&A")
    
    # 채팅 기록 표시
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["message"])
            
    # 사용자 입력
    if user_query := st.chat_input("질문을 입력하세요 (예: 제출 기한이 언제야?)"):
        # 사용자 메시지 표시
        with st.chat_message("user"):
            st.markdown(user_query)
        st.session_state.chat_history.append({"role": "user", "message": user_query})
        
        # AI 답변 생성
        with st.chat_message("ai"):
            with st.spinner("답변 작성 중..."):
                answer = ask_gemini(st.session_state.pdf_text, user_query, api_key)
                st.markdown(answer)
        st.session_state.chat_history.append({"role": "ai", "message": answer})