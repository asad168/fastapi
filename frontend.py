import streamlit as st
import requests
import base64
import urllib.parse

st.set_page_config(page_title="Simple Social", layout="wide")

# Initialize session state
if 'token' not in st.session_state:
    st.session_state.token = None
if 'user' not in st.session_state:
    st.session_state.user = None


def get_headers():
    """Get authorization headers with token"""
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}


def login_page():
    st.title("🚀 Simple Social")
    
    # Use tabs to separate Login and Sign Up
    tab1, tab2 = st.tabs(["Existing User (Login)", "New User (Sign Up)"])

    with tab1:
        st.subheader("Login to your account")
        login_email = st.text_input("Email", key="login_email")
        login_password = st.text_input("Password", type="password", key="login_pw")
        
        if st.button("Login", type="primary"):
            if login_email and login_password:
                # OAuth2 password flow uses 'username' field for the email
                login_data = {"username": login_email, "password": login_password}
                response = requests.post("http://localhost:8000/auth/jwt/login", data=login_data)

                if response.status_code == 200:
                    st.session_state.token = response.json()["access_token"]
                    # Fetch user details
                    user_resp = requests.get("http://localhost:8000/users/me", headers=get_headers())
                    if user_resp.status_code == 200:
                        st.session_state.user = user_resp.json()
                        st.success("Welcome back!")
                        st.rerun()
                else:
                    st.error("Login failed. Check your email/password or Register first.")

    with tab2:
        st.subheader("Create a new account")
        reg_email = st.text_input("Email", key="reg_email")
        reg_password = st.text_input("Password", type="password", key="reg_pw")
        confirm_password = st.text_input("Confirm Password", type="password")

        if st.button("Create Account"):
            if reg_password != confirm_password:
                st.error("Passwords do not match!")
            elif reg_email and reg_password:
                signup_data = {"email": reg_email, "password": reg_password}
                response = requests.post("http://localhost:8000/auth/register", json=signup_data)

                if response.status_code == 201:
                    st.success("Account created successfully! Now go to the Login tab.")
                else:
                    detail = response.json().get("detail", "Error")
                    st.error(f"Registration failed: {detail}")


def upload_page():
    st.title("📸 Share Something")

    uploaded_file = st.file_uploader("Choose media", type=['png', 'jpg', 'jpeg', 'mp4', 'avi', 'mov', 'mkv', 'webm'])
    caption = st.text_area("Caption:", placeholder="What's on your mind?")

    if uploaded_file and st.button("Share", type="primary"):
        with st.spinner("Uploading..."):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            data = {"caption": caption}
            response = requests.post("http://localhost:8000/upload", files=files, data=data, headers=get_headers())

            if response.status_code == 200:
                st.success("Posted!")
                st.rerun()
            else:
                st.error("Upload failed!")


def encode_text_for_overlay(text):
    """Encode text for ImageKit overlay - base64 then URL encode"""
    if not text:
        return ""
    # Base64 encode the text
    base64_text = base64.b64encode(text.encode('utf-8')).decode('utf-8')
    # URL encode the result
    return urllib.parse.quote(base64_text)


def create_transformed_url(original_url, transformation_params, caption=None):
    if not original_url:
        return ""
        
    if caption:
        encoded_caption = encode_text_for_overlay(caption)
        transformation_params = f"l-text,ie-{encoded_caption},ly-N20,lx-20,fs-100,co-white,bg-000000A0,l-end"

    if not transformation_params:
        return original_url

    # Safer parsing: Look for the 'ik.imagekit.io/your_id/' part
    # A standard ImageKit URL: https://ik.imagekit.io/demo/img.jpg
    # Transformed: https://ik.imagekit.io/demo/tr:w-400/img.jpg
    
    url_parts = original_url.split('/')
    if len(url_parts) < 4:
        return original_url
        
    # Reconstruct with tr: transformation
    base = "/".join(url_parts[:4])
    path = "/".join(url_parts[4:])
    return f"{base}/tr:{transformation_params}/{path}"


def feed_page():
    st.title("🏠 Feed")

    response = requests.get("http://localhost:8000/feed", headers=get_headers())
    if response.status_code == 200:
        posts = response.json()["posts"]

        if not posts:
            st.info("No posts yet! Be the first to share something.")
            return

        for post in posts:
            st.markdown("---")

            # Header with user, date, and delete button (if owner)
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{post['email']}** • {post['created_at'][:10]}")
            with col2:
                if post.get('is_owner', False):
                    if st.button("🗑️", key=f"delete_{post['id']}", help="Delete post"):
                        # Delete the post
                        response = requests.delete(f"http://localhost:8000/posts/{post['id']}", headers=get_headers())
                        if response.status_code == 200:
                            st.success("Post deleted!")
                            st.rerun()
                        else:
                            st.error("Failed to delete post!")

            # Uniform media display with caption overlay
            caption = post.get('caption', '')
            if post['file_type'] == 'image':
                uniform_url = create_transformed_url(post['url'], "", caption)
                st.image(uniform_url, width=300)
            else:
                # For videos: specify only height to maintain aspect ratio + caption overlay
                uniform_video_url = create_transformed_url(post['url'], "w-400,h-200,cm-pad_resize,bg-blurred")
                st.video(uniform_video_url, width=300)
                st.caption(caption)

            st.markdown("")  # Space between posts
    else:
        st.error("Failed to load feed")


# Main app logic
if st.session_state.user is None:
    login_page()
else:
    # Sidebar navigation
    st.sidebar.title(f"👋 Hi {st.session_state.user['email']}!")

    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.session_state.token = None
        st.rerun()

    st.sidebar.markdown("---")
    page = st.sidebar.radio("Navigate:", ["🏠 Feed", "📸 Upload"])

    if page == "🏠 Feed":
        feed_page()
    else:
        upload_page()


# streamlit run "D:\visual studio\Python Projects\Fast_API\Fast_API\frontend.py"