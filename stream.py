import streamlit as st
import sqlite3
from datetime import datetime
from app2 import PrinceChatbot  

# Initialize session state variables
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'phone_verified' not in st.session_state:
    st.session_state.phone_verified = False
if 'chatbot' not in st.session_state:
    st.session_state.chatbot = None
if 'phone_number' not in st.session_state:
    st.session_state.phone_number = None

# Page config
st.set_page_config(
    page_title="Heirs Insurance Group - Prince Chatbot",
    page_icon="💬",
    layout="centered"
)

# Custom CSS
st.markdown("""
    <style>
    .stTextInput>div>div>input {
        border-radius: 20px;
    }
    .stButton>button {
        border-radius: 20px;
        width: 100%;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .user-message {
        background-color: #e6f3ff;
        margin-left: 2rem;
    }
    .bot-message {
        background-color: #f0f0f0;
        margin-right: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)

def verify_phone(phone_number: str) -> bool:
    """Verify if the phone number exists in the database."""
    try:
        with sqlite3.connect("prince.db") as conn:
            cursor = conn.cursor()
            result = cursor.execute(
                "SELECT COUNT(*) FROM customers WHERE phone = ?",
                (phone_number,)
            ).fetchone()
            return result[0] > 0
    except sqlite3.Error:
        return False

def main():
    st.title("Heirs Insurance Group")
    st.subheader("Chat with Prince 👨‍💼")

    # Phone number verification section
    if not st.session_state.phone_verified:
        st.markdown("### Please verify your phone number to continue")
        with st.form("phone_verification"):
            phone_number = st.text_input("Enter your phone number:")
            submit_button = st.form_submit_button("Verify")
            
            if submit_button and phone_number:
                if verify_phone(phone_number):
                    st.session_state.phone_verified = True
                    st.session_state.phone_number = phone_number
                    st.session_state.chatbot = PrinceChatbot("prince.db")
                    st.success("Phone number verified! You can now start chatting.")
                    st.rerun()
                else:
                    st.error("Phone number not found. Please contact support.")
    
    # Chat interface
    else:
        # Display chat history
        chat_container = st.container()
        with chat_container:
            for message in st.session_state.chat_history:
                if message["role"] == "user":
                    st.markdown(f"""
                        <div class="chat-message user-message">
                            <div><strong>You:</strong> {message["content"]}</div>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                        <div class="chat-message bot-message">
                            <div><strong>Prince:</strong> {message["content"]}</div>
                        </div>
                    """, unsafe_allow_html=True)

        # Quick action buttons
        st.markdown("### Quick Actions")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Buy a Product"):
                user_input = "Buy a Product"
                response = st.session_state.chatbot.process_message(user_input, st.session_state.phone_number)
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.rerun()
        
        with col2:
            if st.button("Make a Claim"):
                user_input = "Make a Claim"
                response = st.session_state.chatbot.process_message(user_input, st.session_state.phone_number)
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.rerun()

        # Chat input
        st.markdown("### Chat")
        with st.form("chat_input", clear_on_submit=True):
            user_input = st.text_input("Type your message:", key="user_message")
            submit_button = st.form_submit_button("Send")

            if submit_button and user_input:
                response = st.session_state.chatbot.process_message(user_input, st.session_state.phone_number)
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.rerun()

        # Footer
        st.markdown("---")
        st.markdown("Need help? Contact our support team at support@heirsinsurance.com")

        # Reset button
        if st.button("Reset Chat"):
            st.session_state.chat_history = []
            st.session_state.phone_verified = False
            st.session_state.chatbot = None
            st.session_state.phone_number = None
            st.rerun()

if __name__ == "__main__":
    main()