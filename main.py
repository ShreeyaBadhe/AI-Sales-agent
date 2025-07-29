import json
import uuid
import streamlit.components.v1 as components
import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.messages.tool import ToolMessage

from virtual_sales_agent.graph import graph

def set_page_config():
    st.set_page_config(
        page_title="Virtual Sales Agent Chat",
        layout="wide",
        initial_sidebar_state="expanded",
    )

def set_page_style():
    st.markdown(
        f"""
        <style>
        {open("assets/style.css").read()}
        </style>
        """,
        unsafe_allow_html=True,
    )

def initialize_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    if "pending_approval" not in st.session_state:
        st.session_state.pending_approval = None
    if "config" not in st.session_state:
        st.session_state.config = {
            "configurable": {
                "customer_id": "123456789",
                "thread_id": st.session_state.thread_id,
            }
        }


def setup_sidebar():
    with st.sidebar:
        st.markdown(
            """
            <div class="agent-profile">
                <div class="profile-header">
                    <div class="avatar">🤖</div>
                    <h1>Virtual Sales Agent</h1>
                </div>
                <div class="feature-list">
                    <div class="feature-item"><span class="icon">🛒</span><span>Browse available products</span></div>
                    <div class="feature-item"><span class="icon">📦</span><span>Place orders</span></div>
                    <div class="feature-item"><span class="icon">🚚</span><span>Track your orders</span></div>
                    <div class="feature-item"><span class="icon">🎯</span><span>Get personalized recommendations</span></div>
                </div>
                <div class="status-card">
                    <div class="status-indicator"></div>
                    <span>Ready to Assist</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        components.html("""
            <script>
            const addMicButton = () => {
                const inputBox = window.parent.document.querySelector('textarea');
                if (!inputBox) return;

                const existingButton = document.getElementById("voice-button");
                if (existingButton) return;

                const button = document.createElement("button");
                button.innerHTML = "🎤 Speak";
                button.id = "voice-button";
                button.style.padding = "10px 16px";
                button.style.marginBottom = "10px";
                button.style.background = "#6c47ff";
                button.style.color = "white";
                button.style.border = "none";
                button.style.borderRadius = "10px";
                button.style.fontWeight = "bold";
                button.style.cursor = "pointer";
                button.style.transition = "box-shadow 0.3s ease";
                        
                const recognition = new(window.SpeechRecognition || window.webkitSpeechRecognition)();
                recognition.continuous = false;
                recognition.lang = 'en-US';
                recognition.interimResults = false;
                recognition.maxAlternatives = 1;

                
                recognition.onstart = () => {
                    button.style.boxShadow = "0 0 0 8px rgba(108, 71, 255, 0.4)";
                    button.style.animation = "pulse 1.5s infinite";
                };
                recognition.onend = () => {
                    button.style.boxShadow = "none";
                    button.style.animation = "none";
                };

                button.onclick = () => recognition.start();

                 recognition.onresult = (event) => {
                    const transcript = event.results[0][0].transcript;
                    inputBox.focus();
                    inputBox.value = transcript;
                    inputBox.dispatchEvent(new Event('input', { bubbles: true }));

                    const spaceEvent = new KeyboardEvent('keydown', {
                        key: ' ',
                        keyCode: 32,
                        which: 32,
                        bubbles: true
                    });
                    inputBox.dispatchEvent(spaceEvent);
                };

                const parent = inputBox.parentElement;
                parent.insertBefore(button, inputBox);
            };

            window.addEventListener('load', () => {
                const style = document.createElement("style");
                style.innerHTML = `
                    @keyframes pulse {
                        0% { box-shadow: 0 0 0 0 rgba(108, 71, 255, 0.6); }
                        70% { box-shadow: 0 0 0 12px rgba(108, 71, 255, 0); }
                        100% { box-shadow: 0 0 0 0 rgba(108, 71, 255, 0); }
                    }
                `;
                document.head.appendChild(style);
                addMicButton();
            });
            </script>
        """, height=0)

        st.markdown("---")
        if st.button("🔄 Start New Chat", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

        if st.button("🔍 Visualize Workflow", use_container_width=True):
            st.image("assets/graph.png")

        st.markdown(
            """
            <div class="sidebar-footer">
                <div class="powered-by">
                    Enhanced by AI • Crafted for You
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )




def display_chat_history():
    """Display the chat history."""
    if not st.session_state.messages:
        st.markdown(
            """
            <div style='text-align: center; padding: 30px;'>
                <h1>👋 Welcome!</h1>
                <p>How can I assist you today?</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    for message in st.session_state.messages:
        role = "user" if isinstance(message, HumanMessage) else "assistant"
        with st.chat_message(role):
            st.write(message.content)


def process_events(event):
    """Process events from the graph and extract messages."""
    seen_ids = set()

    if isinstance(event, dict) and "messages" in event:
        messages = event["messages"]
        last_message = messages[-1] if messages else None

        if isinstance(last_message, AIMessage):
            if last_message.id not in seen_ids and last_message.content:
                seen_ids.add(last_message.id)
                st.session_state.messages.append(last_message)
                with st.chat_message("assistant"):
                    st.write(last_message.content)

            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                return last_message.tool_calls[0]

    return None


def handle_tool_approval(snapshot, event):
    """Handle tool approval process."""
    st.write("⚠️ The assistant wants to perform an action. Do you approve?")

    last_message = snapshot.values.get("messages", [])[-1]

    if (
        isinstance(last_message, AIMessage)
        and hasattr(last_message, "tool_calls")
        and last_message.tool_calls
    ):
        tool_call = last_message.tool_calls[0]
        with st.chat_message("assistant"):
            st.markdown("#### 🔧 Proposed Action")

            with st.expander("View Function Details", expanded=True):
                st.info(f"Function: **{tool_call['name']}**")

                try:
                    args_formatted = json.dumps(tool_call["args"], indent=2)
                    st.code(f"Arguments:\n{args_formatted}", language="json")
                except:
                    st.code(f"Arguments:\n{tool_call['args']}")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Approve"):
            with st.spinner("Processing..."):
                try:
                    result = graph.invoke(None, st.session_state.config)
                    process_events(result)
                    st.session_state.pending_approval = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Error processing approval: {str(e)}")

    with col2:
        if st.button("❌ Deny"):
            st.session_state.show_reason_input = True

        if st.session_state.get("show_reason_input", False):
            reason = st.text_input("Please explain why you're denying this action:")
            submit = st.button("Submit Denial", key="submit_denial")
            if reason and submit:
                with st.spinner("Processing..."):
                    try:
                        result = graph.invoke(
                            {
                                "messages": [
                                    ToolMessage(
                                        tool_call_id=last_message.tool_calls[0]["id"],
                                        content=f"API call denied by user. Reasoning: '{reason}'. Continue assisting, accounting for the user's input.",
                                    )
                                ]
                            },
                            st.session_state.config,
                        )
                        process_events(result)
                        st.session_state.pending_approval = None
                        st.session_state.show_reason_input = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error processing denial: {str(e)}")


def main():
    set_page_config()
    set_page_style()
    initialize_session_state()
    setup_sidebar()

    display_chat_history()

    if st.session_state.pending_approval:
        handle_tool_approval(*st.session_state.pending_approval)

    if prompt := st.chat_input("What would you like to order?"):
        human_message = HumanMessage(content=prompt)
        st.session_state.messages.append(human_message)
        with st.chat_message("user"):
            st.write(prompt)

        try:
            with st.spinner("Thinking..."):
                events = list(
                    graph.stream(
                        {"messages": st.session_state.messages},
                        st.session_state.config,
                        stream_mode="values",
                    )
                )

                last_event = events[-1]
                tool_call = process_events(last_event)

                if tool_call:
                    snapshot = graph.get_state(st.session_state.config)
                    if snapshot.next:
                        for event in events:
                            st.session_state.pending_approval = (snapshot, event)
                            st.rerun()

        except Exception as e:
            st.error(f"Error processing message: {str(e)}")


if __name__ == "__main__":
    main()
