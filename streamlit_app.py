
import streamlit as st
import requests
from datetime import datetime
import uuid
import time

# Page configuration
st.set_page_config(
    page_title="Agent DB - Business Intelligence",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🤖"
)

# API base URL from secrets or default
API_BASE_URL = st.secrets.get("API_BASE_URL", "http://localhost:8000")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global Styles */
    .stApp {
        background-color: #0f1111;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        color: #ffffff; /* default white on dark */
    }

    /* Hide Streamlit default elements */
    #MainMenu, footer, header, .stDeployButton {display: none;}

    /* -------- Sidebar -------- */
    section[data-testid="stSidebar"] {
        background: #ffffff; /* white sidebar */
        border-right: 1px solid #e2e8f0;
        border-radius: 0 16px 16px 0;
        color: #000000 !important; /* black text */
    }

    /* Sidebar button (keeps branding colors) */
    section[data-testid="stSidebar"] .stButton > button {
        background: linear-gradient(135deg, #4a90e2, #50e3c2) !important;
        color: #ffffff !important;
        font-weight: 600;
        border-radius: 12px;
        border: none;
    }

    /* -------- Main Header -------- */
    .main-header {
        background: linear-gradient(135deg, #4a90e2, #50e3c2);
        padding: 2rem;
        margin: -1rem -1rem 2rem -1rem;
        border-radius: 0 0 20px 20px;
        text-align: center;
        color: #ffffff;
    }
    .main-header h1 {font-size: 2.5rem; font-weight: 200;}
    .main-header p {opacity: 0.9;}

    /* -------- Chat Messages -------- */
    .chat-message {
        border-radius: 16px;
        padding: 1.2rem;
        margin: 1rem 0;
        animation: fadeInUp 0.3s ease-out;
        border-left: 6px solid transparent;
    }
    @keyframes fadeInUp {
        from {opacity: 0; transform: translateY(10px);}
        to {opacity: 1; transform: translateY(0);}
    }

    .user-message {
        background: #edf2f7; /* light bg */
        color: #000000;       /* black text */
        border-left-color: #4299e1;
    }
    .bot-message {
        background: #1e2432; /* dark bg */
        color: #ffffff;      /* white text */
        border-left-color: #48bb78;
    }
    .error-message {
        background: #fff5f5; /* light red */
        color: #000000;      /* black text */
        border-left-color: #f56565;
    }

    /* -------- Stat Cards -------- */
    .stat-card {
        background: #1e2432; /* dark */
        color: #ffffff;
        border: 1px solid #4a5568;
        border-radius: 16px;
        padding: 1.2rem;
        text-align: center;
    }
    .stat-title {color: #cbd5e0;}
    .stat-value {color: #ffffff;}

    /* -------- Inputs -------- */
    .stTextInput > div > div > input {
        background-color: #ffffff !important;
        color: #000000 !important; /* black on white */
        border: 1px solid #ccc !important;
        border-radius: 12px;
    }
    .stTextInput > div > div > input::placeholder {color: #6b7280 !important;}

    /* -------- Metrics -------- */
    .stMetric {
        background: #1e2432;
        border: 1px solid #4a5568;
        border-radius: 16px;
        color: #ffffff !important;
    }

    /* -------- Code Blocks -------- */
    .stCodeBlock {
        background-color: #1a202c !important;
        border-radius: 12px;
        color: #ffffff !important;
    }

    /* -------- Expanders -------- */
    .streamlit-expanderHeader {
        background: #f7fafc !important; /* light */
        color: #000000 !important;      /* black */
    }
    .streamlit-expanderContent {
        background: #1a202c !important; /* dark */
        color: #ffffff !important;      /* white */
    }

    /* -------- Alerts -------- */
    .stSuccess {background: #f0fff4 !important; color: #000000 !important;}
    .stError   {background: #fff5f5 !important; color: #000000 !important;}
    .stInfo    {background: #ebf8ff !important; color: #000000 !important;}
    .stWarning {background: #fffaf0 !important; color: #000000 !important;}

    /* -------- Checkbox -------- */
    .stCheckbox label {color: #000000 !important;} /* always readable on light bg */

</style>
""", unsafe_allow_html=True)



# Initialize session state
if 'chat_threads' not in st.session_state:
    st.session_state.chat_threads = [
        {"id": str(uuid.uuid4()), "title": "New Conversation", "messages": []}
    ]

if 'current_thread_id' not in st.session_state:
    st.session_state.current_thread_id = st.session_state.chat_threads[0]['id']

if 'selected_table_schema' not in st.session_state:
    st.session_state.selected_table_schema = None

if 'health_status' not in st.session_state:
    st.session_state.health_status = None

if 'tables' not in st.session_state:
    st.session_state.tables = []

if 'loading' not in st.session_state:
    st.session_state.loading = False

# Helper functions
@st.cache_data(ttl=60)
def check_api_health():
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.json() if response.status_code == 200 else None
    except requests.exceptions.ConnectionError:
        return {"status": "connection_error", "message": "Unable to connect to API"}
    except requests.exceptions.Timeout:
        return {"status": "timeout", "message": "API request timed out"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@st.cache_data(ttl=300)
def get_tables():
    try:
        response = requests.get(f"{API_BASE_URL}/tables", timeout=5)
        return response.json().get("tables", []) if response.status_code == 200 else []
    except:
        return []

def ask_question_api(question, use_human_approval=False):
    try:
        response = requests.post(
            f"{API_BASE_URL}/ask",
            json={"question": question, "use_human_approval": use_human_approval},
            timeout=30,
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API Error {response.status_code}: {response.text}"}
    except requests.exceptions.ConnectionError:
        return {"error": "Connection failed. Please check if the API server is running."}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out. The query might be too complex."}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

def get_table_schema(table_name):
    try:
        response = requests.get(f"{API_BASE_URL}/schema/{table_name}", timeout=10)
        return response.json() if response.status_code == 200 else None
    except:
        return None

def get_current_thread():
    for thread in st.session_state.chat_threads:
        if thread['id'] == st.session_state.current_thread_id:
            return thread
    return None

def add_message_to_thread(thread_id, message):
    for thread in st.session_state.chat_threads:
        if thread['id'] == thread_id:
            thread['messages'].append(message)
            if (thread['title'] == "New Conversation" and 
                message['type'] == 'user' and 
                len([m for m in thread['messages'] if m['type'] == 'user']) == 1):
                thread['title'] = message['content'][:40] + ("..." if len(message['content']) > 40 else "")
            break

def set_current_thread(thread_id):
    st.session_state.current_thread_id = thread_id

def add_new_thread():
    new_id = str(uuid.uuid4())
    st.session_state.chat_threads.append({
        "id": new_id,
        "title": "New Conversation",
        "messages": []
    })
    set_current_thread(new_id)

def render_message(message):
    timestamp = message["timestamp"].strftime("%H:%M:%S")
    if message["type"] == "user":
        st.markdown(f"""
        <div class="chat-message user-message">
            <div class="message-header">
                👤 You <span class="timestamp">{timestamp}</span>
            </div>
            {message["content"]}
        </div>
        """, unsafe_allow_html=True)
    elif message["type"] == "bot":
        st.markdown(f"""
        <div class="chat-message bot-message">
            <div class="message-header">
                Agent DB <span class="timestamp">{timestamp}</span>
            </div>
            {message["content"]}
        </div>
        """, unsafe_allow_html=True)
        if message.get("query"):
            with st.expander("🔍 View SQL Query & Results", expanded=False):
                st.code(message["query"], language="sql")
                if message.get("result"):
                    st.subheader("Query Results:")
                    st.code(str(message["result"])[:1000] + ("..." if len(str(message["result"])) > 1000 else ""))
    elif message["type"] == "error":
        st.markdown(f"""
        <div class="chat-message error-message">
            <div class="message-header">
                ❌ Error <span class="timestamp">{timestamp}</span>
            </div>
            {message["content"]}
        </div>
        """, unsafe_allow_html=True)

def main():
    # Main header
    st.markdown("""
    <div class="main-header">
        <h1>Agent DB</h1>
        <p>AI-Powered Business Intelligence Dashboard</p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar content
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 1rem 0; margin-bottom: 1rem;">
            <div style="font-size: 1.5rem; font-weight: 700; color: #4a90e2;">💬 Conversations</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("➕ New Chat Thread", key="new_thread", help="Start a fresh conversation"):
            add_new_thread()
            st.experimental_rerun()
        st.markdown("---")
        st.markdown("**Recent Conversations**")
        
        threads = st.session_state.chat_threads
        current_id = st.session_state.current_thread_id
        
        for i, thread in enumerate(threads[-10:]):
            thread_title = thread['title']
            if len(thread_title) > 35:
                thread_title = thread_title[:35] + "..."
            is_active = thread['id'] == current_id
            if st.button(f"💬 {thread_title}", key=f"thread_{thread['id']}", help=f"Switch to: {thread['title']}"):
                set_current_thread(thread['id'])
                st.experimental_rerun()

        st.markdown("---")
        st.markdown("**🗄️ Database Status**")
        health_status = check_api_health()
        st.session_state.health_status = health_status
        
        if health_status:
            if health_status.get("status") == "healthy":
                st.markdown('<div class="status-online"><span class="status-dot online"></span>Database Connected</div>', unsafe_allow_html=True)
                tables_count = len(health_status.get('available_tables', []))
                st.info(f"📊 {tables_count} tables available")
            elif health_status.get("status") == "connection_error":
                st.markdown('<div class="status-offline"><span class="status-dot offline"></span>Connection Failed</div>', unsafe_allow_html=True)
                st.error("🔌 Check API server")
            else:
                st.markdown('<div class="status-offline"><span class="status-dot offline"></span>Database Offline</div>', unsafe_allow_html=True)
                st.error("❌ System Error")
        else:
            st.markdown('<div class="status-offline"><span class="status-dot offline"></span>API Unreachable</div>', unsafe_allow_html=True)
            st.error("🔌 API Unreachable")
        
        st.markdown("** Database Tables**")
        tables = get_tables()
        st.session_state.tables = tables
        if tables:
            with st.expander(f"📊 View All Tables ({len(tables)})", expanded=False):
                for table in tables:
                    if st.button(f"📄 {table}", key=f"schema_{table}", help=f"View schema for {table}"):
                        schema = get_table_schema(table)
                        if schema:
                            st.session_state.selected_table_schema = {
                                "table": table,
                                "schema": schema.get("schema", "Schema not available")
                            }
                        st.experimental_rerun()
        else:
            st.warning("No tables found")

        st.markdown("---")
        st.markdown("**Quick Questions**")
        example_questions = [
            "How many records are in each table?",
            "Show me the database schema",
            "What's the total customer count?",
            "Analyze recent transaction trends",
            "Show table relationships",
            "Get performance metrics"
        ]
        for i, question in enumerate(example_questions):
            if st.button(question, key=f"example_{i}", help="Click to ask this question"):
                current_thread = get_current_thread()
                if current_thread:
                    add_message_to_thread(current_thread['id'], {
                        "type": "user",
                        "content": question,
                        "timestamp": datetime.now()
                    })
                    with st.spinner("🤖 Processing your question..."):
                        result = ask_question_api(question, False)
                    if "error" in result:
                        add_message_to_thread(current_thread['id'], {
                            "type": "error",
                            "content": result['error'],
                            "timestamp": datetime.now()
                        })
                    else:
                        add_message_to_thread(current_thread['id'], {
                            "type": "bot",
                            "content": result.get("answer", "No answer available"),
                            "query": result.get("query", ""),
                            "result": result.get("result", ""),
                            "timestamp": datetime.now()
                        })
                    st.experimental_rerun()

    # Main content area
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown('<div class="custom-container">', unsafe_allow_html=True)
        # st.markdown("""
        # <div class="section-header">
        #     <span class="section-icon">💭</span>
        #     <span class="section-title">Chat Interface</span>
        # </div>
        # """, unsafe_allow_html=True)

        current_thread = get_current_thread()
        if not current_thread:
            st.error("No active thread found")
            return


        
        st.markdown("""
            <style>
            /* Make input text and placeholder white */
            [data-baseweb="input"] input {
                color: #ffffff !important;       /* typed text */
                background-color: #1e2432 !important; /* dark background */
                border-radius: 12px !important;
                border: 1px solid #4a5568 !important;
                padding: 0.6rem 1rem !important;
                font-size: 1rem !important;
            }
            [data-baseweb="input"] input::placeholder {
                color: #cbd5e0 !important;       /* placeholder text (light gray) */
            }
            </style>
        """, unsafe_allow_html=True)

        # Question input
        question_input = st.text_input(
            "Ask your question",
            key=f"input_{current_thread['id']}",
            placeholder="How many users registered this month?",
            help="Type your question about the database or business metrics",
        )

        col_btn, col_approval = st.columns([1, 2])
        with col_btn:
            ask_button = st.button("Ask Question", key=f"ask_{current_thread['id']}", type="primary")

        with col_approval:
            use_approval = st.checkbox(
                "Require approval for SQL execution",
                key=f"approval_{current_thread['id']}",
                value=False,
                help="Enable to review SQL queries before execution"
            )

        if ask_button and question_input.strip():
            add_message_to_thread(current_thread['id'], {
                "type": "user",
                "content": question_input.strip(),
                "timestamp": datetime.now()
            })
            with st.spinner("🤖 Processing your question..."):
                result = ask_question_api(question_input.strip(), use_approval)
            if "error" in result:
                add_message_to_thread(current_thread['id'], {
                    "type": "error",
                    "content": result['error'],
                    "timestamp": datetime.now()
                })
            else:
                add_message_to_thread(current_thread['id'], {
                    "type": "bot",
                    "content": result.get("answer", "No answer available"),
                    "query": result.get("query", ""),
                    "result": result.get("result", ""),
                    "timestamp": datetime.now()
                })
            st.experimental_rerun()

        st.markdown("---")
        st.markdown("**Conversation History**")
        messages = current_thread.get("messages", [])
        if messages:
            for message in messages:
                render_message(message)
            if st.button("🗑️ Clear Conversation", key=f"clear_{current_thread['id']}"):
                current_thread['messages'] = []
                st.experimental_rerun()
        else:
            st.info("👋 Start by asking a question about your database!")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="custom-container">', unsafe_allow_html=True)
        st.markdown("""
        <div class="section-header" style="color:white">
            <span class="section-icon">📊</span>
            <span class="section-title">System Metrics</span>
        </div>
        """, unsafe_allow_html=True)

        health_status = st.session_state.health_status
        if health_status and health_status.get("status") == "healthy":
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Status", "🟢 Online", "Connected")
            with col_b:
                tables_count = len(health_status.get("available_tables", []))
                # st.metric("Tables", f"{tables_count}", "Available")
            st.metric("Response Time", "0.3s", "Optimized")
            st.metric("Uptime", "99.9%", "Stable")
        else:
            st.metric("Status", "🔴 Offline", "Disconnected")
            st.metric("Tables", "0", "Unavailable")
        st.markdown('</div>', unsafe_allow_html=True)

        if st.session_state.selected_table_schema:
            st.markdown('<div class="custom-container">', unsafe_allow_html=True)
            st.markdown(f"""
            <div class="section-header">
                <span class="section-icon">📄</span>
                <span class="section-title">Table: {st.session_state.selected_table_schema['table']}</span>
            </div>
            """, unsafe_allow_html=True)
            st.code(st.session_state.selected_table_schema['schema'], language="sql")
            if st.button("❌ Close Schema View", key="close_schema"):
                st.session_state.selected_table_schema = None
                st.experimental_rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="custom-container">', unsafe_allow_html=True)
        st.markdown("""
        <div class="section-header">
            <span class="section-icon">🔗</span>
            <span class="section-title">API Information</span>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(f"""
        <div class="api-info">
Health Check:<br>
GET {API_BASE_URL}/health<br><br>
Ask Question:<br>
POST {API_BASE_URL}/ask<br><br>
Get Tables:<br>
GET {API_BASE_URL}/tables<br><br>
Documentation:<br>
{API_BASE_URL}/docs
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

       

def footer():
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; padding: 2rem; background: linear-gradient(135deg, #1a1a1a, #2a2a2a); border-radius: 16px; margin-top: 2rem;">
        <h3 style="color: #4a90e2; margin-bottom: 1rem;">Agent DB</h3>
        <p style="color: #b0b0b0; margin-bottom: 0.5rem;">AI-Powered Business Intelligence Platform</p>
        <p style="color: #808080; font-size: 0.9rem;">Ask questions in natural language • Get instant insights • Make data-driven decisions</p>
        <div style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid #3a3a3a;">
            <p style="color: #606060; font-size: 0.8rem;">Powered by Advanced AI • Secure Database Integration • Real-time Analytics</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Auto-refresh functionality
def auto_refresh_status():
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = datetime.now()
    current_time = datetime.now()
    time_diff = (current_time - st.session_state.last_refresh).seconds
    if time_diff > 60:
        st.cache_data.clear()
        st.session_state.last_refresh = current_time
        st.session_state.health_status = check_api_health()

def safe_execute(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        return None

if __name__ == "__main__":
    try:
        auto_refresh_status()
        main()
        # footer()
    except Exception as e:
        st.error(f"Application error: {str(e)}")
        st.markdown("""
        <div style="text-align: center; padding: 2rem; background: rgba(239, 68, 68, 0.1); border-radius: 12px; margin: 2rem 0;">
            <h3 style="color: #ef4444;">⚠️ Application Error</h3>
            <p style="color: #b0b0b0;">Please refresh the page or contact support if the issue persists.</p>
        </div>
        """, unsafe_allow_html=True)
