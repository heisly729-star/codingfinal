import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, storage
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import io
import json
from datetime import datetime

# Firebase 초기화
@st.cache_resource
def init_firebase():
    """Firebase 초기화"""
    try:
        # streamlit secrets에서 Firebase 자격증명 가져오기
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
        
        # Firebase 앱이 이미 초기화되어 있는지 확인
        try:
            firebase_admin.get_app()
        except ValueError:
            # 앱이 초기화되지 않았을 경우
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

def main():
    st.set_page_config(
        page_title="학생 정서 모니터링",
        page_icon="🎨",
        layout="wide"
    )
    
    st.title("🎨 학생 정서 모니터링 시스템")
    st.write("당신의 감정 상태를 선택하고 그림을 그려주세요!")
    
    # Firebase 초기화
    db, bucket = init_firebase()
    if db is None or bucket is None:
        st.error("Firebase 연결에 실패했습니다.")
        return
    
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
        
        # 다시 시작 버튼
        if st.button("🔄 다시 시작하기"):
            st.session_state.submission_success = False
            st.rerun()
        return
    
    # UI 레이아웃
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📝 정보 입력")
        
        # 학생 이름 입력
        student_name = st.text_input(
            "학생 이름을 입력해주세요:",
            placeholder="예: 김철수",
            key="student_name"
        )
        
        # 감정 상태 선택
        st.write("**현재 감정 상태를 선택해주세요:**")
        emotion = st.radio(
            "감정 선택",
            list(EMOTIONS.keys()),
            key="emotion_selection",
            label_visibility="collapsed"
        )
        
        # 그리기 도구 설정
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
        
        # 그리기 캔버스
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
    
    # 제출 버튼
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col2:
        if st.button("📤 제출하기", use_container_width=True):
            # 입력 검증
            if not student_name:
                st.error("학생 이름을 입력해주세요!")
            elif canvas_result.image_data is None:
                st.error("그림을 그려주세요!")
            else:
                try:
                    with st.spinner("데이터 전송 중..."):
                        # 그림을 PIL Image로 변환
                        image = Image.fromarray(canvas_result.image_data.astype('uint8'))
                        
                        # RGBA를 RGB로 변환 (JPEG는 RGBA를 지원하지 않음)
                        if image.mode == 'RGBA':
                            # 흰색 배경으로 RGBA를 RGB로 변환
                            rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                            rgb_image.paste(image, mask=image.split()[3])
                            image = rgb_image
                        
                        # 이미지를 바이트 배열로 변환
                        img_byte_arr = io.BytesIO()
                        image.save(img_byte_arr, format='JPEG', quality=95)
                        img_byte_arr.seek(0)
                        
                        # 파일명 생성 (학생이름_감정_시간.jpg)
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        emotion_key = EMOTIONS[emotion]
                        filename = f"drawings/{student_name}_{emotion_key}_{timestamp}.jpg"
                        
                        # Firebase Storage에 이미지 업로드
                        blob = bucket.blob(filename)
                        blob.upload_from_string(
                            img_byte_arr.getvalue(),
                            content_type='image/jpeg'
                        )
                        
                        # Firestore에 메타데이터 저장
                        doc_data = {
                            "student_name": student_name,
                            "emotion": emotion,
                            "emotion_key": emotion_key,
                            "timestamp": datetime.now(),
                            "image_path": filename,
                            "image_url": f"gs://{bucket.name}/{filename}"
                        }
                        
                        # Firestore에 문서 추가
                        db.collection("student_emotions").add(doc_data)
                        
                        # 성공 플래그를 세션에 저장
                        st.session_state.submission_success = True
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"❌ 데이터 전송 실패: {e}")
    
    # 하단 정보
    st.markdown("---")
    st.info("💡 TIP: 당신의 감정 상태를 자유롭게 표현해주세요. 그림은 저희 시스템에 안전하게 저장됩니다.")

if __name__ == "__main__":
    main()
