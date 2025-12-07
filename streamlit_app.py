import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, storage, auth
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import io
import json
from datetime import datetime
import pandas as pd
import plotly.express as px
import requests

# Firebase 초기화
@st.cache_resource
def init_firebase():
    """Firebase 초기화"""
    try:
        firebase_config = {
            "type": st.secrets["firebase"]["type"],
            "project_id": st.secrets["firebase"]["project_id"],
            "private_key_id": st.secrets["firebase"]["private_key_id"],
            "private_key": st.secrets["firebase"]["private_key"],
            "client_email": st.secrets["firebase"]["client_email"],
            "client_id": st.secrets["firebase"]["client_id"],
            "auth_uri": st.secrets["firebase"]["auth_uri"],
            "token_uri": st.secrets["firebase"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["firebase"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"],
            "universe_domain": st.secrets["firebase"]["universe_domain"]
        }
        
        try:
            firebase_admin.get_app()
        except ValueError:
            cred = credentials.Certificate(firebase_config)
            firebase_admin.initialize_app(cred, {
                'storageBucket': st.secrets["firebase"]["storage_bucket"]
            })
        
        return firestore.client(), storage.bucket()
    except Exception as e:
        st.error(f"Firebase 초기화 실패: {e}")
        return None, None

# 감정 상태 정의
EMOTIONS = {
    "😊 매우 행복": "happy",
    "😌 평온": "calm",
    "😐 무표정": "neutral",
    "😢 슬픔": "sad",
    "😠 화남": "angry",
    "😰 불안": "anxious"
}

EMOTION_COLORS = {
    "happy": "#FFD700",
    "calm": "#87CEEB",
    "neutral": "#D3D3D3",
    "sad": "#4169E1",
    "angry": "#FF6347",
    "anxious": "#FFB6C1"
}

def student_mode(db, bucket):
    """학생 모드"""
    st.title("🎨 학생 정서 모니터링 시스템")
    st.write("당신의 감정 상태를 선택하고 그림을 그려주세요!")
    
    # 세션 상태 초기화
    if "drawing_mode" not in st.session_state:
        st.session_state.drawing_mode = "freedraw"
    if "stroke_width" not in st.session_state:
        st.session_state.stroke_width = 2
    if "stroke_color" not in st.session_state:
        st.session_state.stroke_color = "#000000"
    if "bg_color" not in st.session_state:
        st.session_state.bg_color = "#FFFFFF"
    if "submission_success" not in st.session_state:
        st.session_state.submission_success = False
    
    # 성공 메시지 표시
    if st.session_state.submission_success:
        st.success("✅ 데이터가 성공적으로 전송되었습니다!")
        st.balloons()
        
        if st.button("🔄 다시 시작하기"):
            st.session_state.submission_success = False
            st.rerun()
        return
    
    # UI 레이아웃
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📝 정보 입력")
        
        student_name = st.text_input(
            "학생 이름을 입력해주세요:",
            placeholder="예: 김철수",
            key="student_name"
        )
        
        st.write("**현재 감정 상태를 선택해주세요:**")
        emotion = st.radio(
            "감정 선택",
            list(EMOTIONS.keys()),
            key="emotion_selection",
            label_visibility="collapsed"
        )
        
        st.write("**그리기 도구 설정:**")
        
        drawing_mode = st.selectbox(
            "그리기 모드:",
            ("freedraw", "line", "rect", "circle"),
            format_func=lambda x: {
                "freedraw": "✏️ 자유 그리기",
                "line": "📏 직선",
                "rect": "◻️ 사각형",
                "circle": "⭕ 원"
            }[x],
            key="drawing_mode_select"
        )
        st.session_state.drawing_mode = drawing_mode
        
        stroke_width = st.slider(
            "펜 굵기:",
            1, 20, 2,
            key="stroke_width_slider"
        )
        st.session_state.stroke_width = stroke_width
        
        stroke_color = st.color_picker(
            "펜 색상:",
            "#000000",
            key="stroke_color_picker"
        )
        st.session_state.stroke_color = stroke_color
        
        bg_color = st.color_picker(
            "배경 색상:",
            "#FFFFFF",
            key="bg_color_picker"
        )
        st.session_state.bg_color = bg_color
    
    with col2:
        st.subheader("🎨 그림 그리기")
        
        canvas_result = st_canvas(
            fill_color="rgba(255, 165, 0, 0.3)",
            stroke_width=st.session_state.stroke_width,
            stroke_color=st.session_state.stroke_color,
            background_color=st.session_state.bg_color,
            background_image=None,
            update_streamlit=True,
            height=400,
            width=400,
            drawing_mode=st.session_state.drawing_mode,
            key="canvas"
        )
    
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col2:
        if st.button("📤 제출하기", use_container_width="stretch"):
            if not student_name:
                st.error("학생 이름을 입력해주세요!")
            elif canvas_result.image_data is None:
                st.error("그림을 그려주세요!")
            else:
                try:
                    with st.spinner("데이터 전송 중..."):
                        image = Image.fromarray(canvas_result.image_data.astype('uint8'))
                        
                        if image.mode == 'RGBA':
                            rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                            rgb_image.paste(image, mask=image.split()[3])
                            image = rgb_image
                        
                        img_byte_arr = io.BytesIO()
                        image.save(img_byte_arr, format='JPEG', quality=95)
                        img_byte_arr.seek(0)
                        
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        emotion_key = EMOTIONS[emotion]
                        filename = f"drawings/{student_name}_{emotion_key}_{timestamp}.jpg"
                        
                        blob = bucket.blob(filename)
                        blob.upload_from_string(
                            img_byte_arr.getvalue(),
                            content_type='image/jpeg'
                        )
                        
                        doc_data = {
                            "student_name": student_name,
                            "emotion": emotion,
                            "emotion_key": emotion_key,
                            "timestamp": datetime.now(),
                            "image_path": filename,
                            "image_url": f"gs://{bucket.name}/{filename}"
                        }
                        
                        db.collection("student_emotions").add(doc_data)
                        
                        st.session_state.submission_success = True
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"❌ 데이터 전송 실패: {e}")
    
    st.markdown("---")
    st.info("💡 TIP: 당신의 감정 상태를 자유롭게 표현해주세요. 그림은 저희 시스템에 안전하게 저장됩니다.")

def teacher_mode(db, bucket, teacher_email):
    """교사 모드"""
    st.title("👨‍🏫 교사 대시보드")
    st.write(f"로그인: {teacher_email}")
    
    # 로그아웃 버튼
    col1, col2, col3 = st.columns([3, 1, 1])
    with col3:
        if st.button("🚪 로그아웃"):
            st.session_state.teacher_logged_in = False
            st.session_state.teacher_email = None
            st.session_state.mode = None
            st.rerun()
    
    st.markdown("---")
    
    # Firestore에서 데이터 조회
    try:
        docs = db.collection("student_emotions").stream()
        data = []
        for doc in docs:
            data.append(doc.to_dict())
        
        if not data:
            st.warning("⚠️ 제출된 감정 데이터가 없습니다.")
            return
        
        # 감정 데이터 분석
        df = pd.DataFrame(data)
        
        # 감정별 개수 집계
        emotion_counts = df['emotion_key'].value_counts().reset_index()
        emotion_counts.columns = ['emotion', 'count']
        emotion_counts['emotion_label'] = emotion_counts['emotion'].map({
            'happy': '😊 행복',
            'calm': '😌 평온',
            'neutral': '😐 무표정',
            'sad': '😢 슬픔',
            'angry': '😠 화남',
            'anxious': '😰 불안'
        })
        emotion_counts['color'] = emotion_counts['emotion'].map(EMOTION_COLORS)
        
        # 레이아웃
        left_col, right_col = st.columns([1, 1])
        
        with left_col:
            st.subheader("📊 감정 상태 통계")
            
            # 막대 그래프
            fig = px.bar(
                emotion_counts,
                x='emotion_label',
                y='count',
                color='emotion',
                color_discrete_map=dict(zip(emotion_counts['emotion'], emotion_counts['color'])),
                title="학생 감정 상태 분포",
                labels={'emotion_label': '감정', 'count': '명'},
                height=400
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width="stretch")
            
            # 통계 정보
            st.write("**📈 통계 정보:**")
            st.metric("총 제출 수", len(df))
            st.metric("가장 많은 감정", emotion_counts.loc[emotion_counts['count'].idxmax(), 'emotion_label'])
            
        with right_col:
            st.subheader("🎨 학생 그림 갤러리")
            
            # 이미지 필터링
            filter_emotion = st.selectbox(
                "감정으로 필터링:",
                ["모두보기"] + list(EMOTIONS.values()),
                format_func=lambda x: "모두보기" if x == "모두보기" else {
                    'happy': '😊 행복',
                    'calm': '😌 평온',
                    'neutral': '😐 무표정',
                    'sad': '😢 슬픔',
                    'angry': '😠 화남',
                    'anxious': '😰 불안'
                }.get(x, x),
                key="teacher_emotion_filter"
            )
            
            # 필터링된 데이터
            if filter_emotion == "모두보기":
                filtered_data = df
            else:
                filtered_data = df[df['emotion_key'] == filter_emotion]
            
            # 갤러리 표시
            if len(filtered_data) == 0:
                st.info("해당 감정의 그림이 없습니다.")
            else:
                # 3열로 갤러리 표시
                cols = st.columns(3)
                for idx, (_, row) in enumerate(filtered_data.iterrows()):
                    col = cols[idx % 3]
                    with col:
                        try:
                            # Storage에서 이미지 다운로드
                            image_path = row['image_path']
                            blob = bucket.blob(image_path)
                            image_data = blob.download_as_bytes()
                            image = Image.open(io.BytesIO(image_data))
                            
                            st.image(image, width=300)
                            
                            # 이미지 정보
                            emotion_label = {
                                'happy': '😊 행복',
                                'calm': '😌 평온',
                                'neutral': '😐 무표정',
                                'sad': '😢 슬픔',
                                'angry': '😠 화남',
                                'anxious': '😰 불안'
                            }.get(row['emotion_key'], row['emotion_key'])
                            
                            st.caption(f"👤 {row['student_name']} | {emotion_label}")
                        except Exception as e:
                            st.error(f"이미지 로드 실패: {e}")
    
    except Exception as e:
        st.error(f"❌ 데이터 조회 실패: {e}")

def login_page():
    """로그인 페이지"""
    st.set_page_config(
        page_title="학생 정서 모니터링",
        page_icon="🎨",
        layout="wide"
    )
    
    st.title("🎨 학생 정서 모니터링 시스템")
    st.write("학생 또는 교사로 입장해주세요.")
    
    st.markdown("""
    <style>
    .stButton button {
        height: 120px;
        font-size: 18px;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("👨‍🎓 학생 입장", use_container_width="stretch", key="student_btn"):
            st.session_state.mode = "student"
            st.rerun()
    
    with col2:
        if st.button("👨‍🏫 교사 입장", use_container_width="stretch", key="teacher_btn"):
            st.session_state.mode = "teacher_login"
            st.rerun()

def teacher_login():
    """교사 로그인 페이지"""
    st.title("👨‍🏫 교사 로그인")
    
    email = st.text_input("이메일:", key="teacher_email_input")
    password = st.text_input("비밀번호:", type="password", key="teacher_password_input")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔐 로그인", use_container_width="stretch"):
            if not email or not password:
                st.error("이메일과 비밀번호를 입력해주세요.")
            else:
                try:
                    with st.spinner("로그인 중..."):
                        # Firebase REST API를 사용한 로그인
                        api_key = st.secrets["firebase"].get("api_key", None)
                        
                        if api_key:
                            # REST API를 통한 로그인
                            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
                            payload = {
                                "email": email,
                                "password": password,
                                "returnSecureToken": True
                            }
                            response = requests.post(url, json=payload)
                            
                            if response.status_code == 200:
                                st.session_state.teacher_logged_in = True
                                st.session_state.teacher_email = email
                                st.session_state.mode = "teacher"
                                st.success("✅ 로그인 성공!")
                                st.rerun()
                            else:
                                st.error("❌ 이메일 또는 비밀번호가 잘못되었습니다.")
                        else:
                            st.error("❌ API 키 설정이 필요합니다. Firebase 콘솔에서 Web API Key를 secrets.toml에 추가해주세요.")
                
                except Exception as e:
                    st.error(f"❌ 로그인 실패: {e}")
    
    with col2:
        if st.button("⬅️ 돌아가기", use_container_width="stretch"):
            st.session_state.mode = None
            st.rerun()

def main():
    st.set_page_config(
        page_title="학생 정서 모니터링",
        page_icon="🎨",
        layout="wide"
    )
    
    # 세션 상태 초기화
    if "mode" not in st.session_state:
        st.session_state.mode = None
    if "teacher_logged_in" not in st.session_state:
        st.session_state.teacher_logged_in = False
    if "teacher_email" not in st.session_state:
        st.session_state.teacher_email = None
    
    # Firebase 초기화
    db, bucket = init_firebase()
    if db is None or bucket is None:
        st.error("Firebase 연결에 실패했습니다.")
        return
    
    # 페이지 라우팅
    if st.session_state.mode == "student":
        student_mode(db, bucket)
    elif st.session_state.mode == "teacher_login":
        teacher_login()
    elif st.session_state.mode == "teacher" and st.session_state.teacher_logged_in:
        teacher_mode(db, bucket, st.session_state.teacher_email)
    else:
        login_page()

if __name__ == "__main__":
    main()
