"""
AI Chatbot Interface - Interactive AI assistant for user support

This module provides a conversational interface for users to get help
with payments, account questions, and general assistance.
"""

import streamlit as st
import requests
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid

def render_chatbot(db_manager, config_manager):
    """Main chatbot interface"""
    
    st.markdown("# 💬 AI Assistant")
    st.markdown("Get instant help with payments, account questions, and more!")
    
    # Initialize chat session
    if 'chat_session_id' not in st.session_state:
        st.session_state.chat_session_id = str(uuid.uuid4())
    
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    if 'chat_suggestions' not in st.session_state:
        st.session_state.chat_suggestions = get_default_suggestions()
    
    # Main chat interface
    render_chat_interface(db_manager, config_manager)
    
    # Sidebar with quick actions and suggestions
    render_chat_sidebar(db_manager, config_manager)

def render_chat_interface(db_manager, config_manager):
    """Render the main chat interface"""
    
    # Chat history container
    chat_container = st.container()
    
    with chat_container:
        if not st.session_state.chat_history:
            # Welcome message
            st.markdown("### 👋 Welcome! How can I help you today?")
            st.markdown("I can assist you with:")
            st.markdown("- Making payments and transfers")
            st.markdown("- Checking transaction history")
            st.markdown("- Account settings and security")
            st.markdown("- Understanding policies and fees")
            st.markdown("- General banking questions")
            st.markdown("---")
        else:
            # Display chat history
            for message in st.session_state.chat_history:
                render_chat_message(message)
    
    # Chat input form
    render_chat_input(db_manager, config_manager)
    
    # Quick suggestion buttons
    render_quick_suggestions()

def render_chat_message(message: Dict[str, Any]):
    """Render individual chat message"""
    
    if message['role'] == 'user':
        # User message
        st.markdown(f"""
        <div style="display: flex; justify-content: flex-end; margin: 10px 0;">
            <div style="background-color: #0066cc; color: white; padding: 10px 15px; 
                        border-radius: 18px 18px 5px 18px; max-width: 70%; 
                        word-wrap: break-word;">
                <strong>You:</strong><br>{message['content']}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    elif message['role'] == 'assistant':
        # AI assistant message
        st.markdown(f"""
        <div style="display: flex; justify-content: flex-start; margin: 10px 0;">
            <div style="background-color: #f0f2f6; color: #333; padding: 10px 15px; 
                        border-radius: 18px 18px 18px 5px; max-width: 70%; 
                        word-wrap: break-word;">
                <strong>🤖 AI Assistant:</strong><br>{message['content']}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Show suggestions if available
        if message.get('suggestions'):
            with st.expander("💡 Related suggestions"):
                for suggestion in message['suggestions']:
                    if st.button(suggestion, key=f"suggestion_{hash(suggestion)}"):
                        send_message(suggestion, db_manager, config_manager)
    
    elif message['role'] == 'system':
        # System message
        st.info(f"ℹ️ {message['content']}")
    
    st.markdown("---")

def render_chat_input(db_manager, config_manager):
    """Render chat input form"""
    
    with st.form("chat_input_form", clear_on_submit=True):
        col1, col2 = st.columns([4, 1])
        
        with col1:
            user_input = st.text_area(
                "Type your message:",
                placeholder="Ask me anything about payments, your account, or banking...",
                height=100,
                key="chat_input"
            )
        
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)  # Spacing
            send_button = st.form_submit_button("Send 📤", type="primary")
            
            st.markdown("<br>", unsafe_allow_html=True)  # Spacing
            if st.form_submit_button("Clear Chat 🗑️"):
                clear_chat_history()
                st.rerun()
        
        if send_button and user_input.strip():
            send_message(user_input.strip(), db_manager, config_manager)
            st.rerun()

def render_quick_suggestions():
    """Render quick suggestion buttons"""
    
    if st.session_state.chat_suggestions:
        st.markdown("### 💡 Quick Questions")
        
        # Display suggestions in columns
        cols = st.columns(2)
        
        for i, suggestion in enumerate(st.session_state.chat_suggestions[:6]):
            with cols[i % 2]:
                if st.button(suggestion, key=f"quick_{i}", use_container_width=True):
                    send_message(suggestion, None, None)  # Quick suggestions don't need db/config
                    st.rerun()

def render_chat_sidebar(db_manager, config_manager):
    """Render chat sidebar with actions and info"""
    
    with st.sidebar:
        st.markdown("### 🔧 Chat Actions")
        
        # Export chat history
        if st.button("📄 Export Chat", use_container_width=True):
            export_chat_history()
        
        # Escalate to human support
        if st.button("👨‍💼 Human Support", use_container_width=True):
            escalate_to_support(db_manager)
        
        # Rate the conversation
        if st.session_state.chat_history:
            st.markdown("### ⭐ Rate this conversation")
            rating = st.select_slider(
                "How helpful was the AI assistant?",
                options=[1, 2, 3, 4, 5],
                value=5,
                format_func=lambda x: "⭐" * x
            )
            
            if st.button("Submit Rating", use_container_width=True):
                submit_chat_rating(rating, db_manager)
                st.success("Thank you for your feedback!")
        
        st.markdown("---")
        
        # Chat statistics
        if st.session_state.chat_history:
            st.markdown("### 📊 Chat Stats")
            message_count = len(st.session_state.chat_history)
            user_messages = len([m for m in st.session_state.chat_history if m['role'] == 'user'])
            
            st.metric("Messages", message_count)
            st.metric("Your messages", user_messages)
        
        st.markdown("---")
        
        # Help and tips
        with st.expander("💭 Tips for better assistance"):
            st.markdown("""
            **Be specific:** Instead of "help with payment", try "how do I send money to John?"
            
            **Include details:** Mention amounts, dates, or error messages when relevant
            
            **Ask follow-ups:** Feel free to ask for clarification or more details
            
            **Use examples:** "Show me how to..." works better than "Can you help?"
            """)

def send_message(message: str, db_manager, config_manager):
    """Send message and get AI response"""
    
    # Add user message to history
    user_message = {
        'role': 'user',
        'content': message,
        'timestamp': datetime.now()
    }
    st.session_state.chat_history.append(user_message)
    
    # Generate AI response
    with st.spinner("🤖 AI is thinking..."):
        ai_response = get_ai_response(message, db_manager, config_manager)
    
    # Add AI response to history
    assistant_message = {
        'role': 'assistant',
        'content': ai_response['response'],
        'suggestions': ai_response.get('suggestions', []),
        'timestamp': datetime.now()
    }
    st.session_state.chat_history.append(assistant_message)
    
    # Update suggestions based on response
    if ai_response.get('related_topics'):
        st.session_state.chat_suggestions = ai_response['related_topics']
    
    # Check if escalation is needed
    if ai_response.get('escalate_to_admin'):
        escalation_message = {
            'role': 'system',
            'content': 'This conversation has been flagged for human review. A support agent will be notified.',
            'timestamp': datetime.now()
        }
        st.session_state.chat_history.append(escalation_message)

def get_ai_response(message: str, db_manager, config_manager) -> Dict[str, Any]:
    """Get AI response from backend or generate locally"""
    
    try:
        # Try to get response from backend API
        if config_manager and config_manager.get('api_base_url'):
            response = requests.post(
                f"{config_manager.get('api_base_url')}/chatbot/chat",
                json={
                    "message": message,
                    "session_id": st.session_state.chat_session_id,
                    "context": get_chat_context()
                },
                headers={"Authorization": f"Bearer {st.session_state.get('access_token', '')}"},
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
        
        # Fallback to local response generation
        return generate_local_response(message)
        
    except Exception as e:
        st.error(f"Error getting AI response: {str(e)}")
        return generate_local_response(message)

def generate_local_response(message: str) -> Dict[str, Any]:
    """Generate AI response locally without backend"""
    
    message_lower = message.lower()
    
    # Payment-related queries
    if any(word in message_lower for word in ['payment', 'pay', 'send', 'transfer', 'money']):
        return {
            'response': """To make a payment:

1. Go to the 'New Payment' section
2. Enter the recipient details and amount
3. Select your payment method
4. Review the transaction details
5. Submit for AI security validation

Your payment will be processed securely with real-time fraud detection. Processing times vary:
• Card payments: 2-5 minutes
• Bank transfers: 1-3 business days
• Wallet transfers: Instant

Need help with a specific payment? Just let me know!""",
            'suggestions': [
                "What are the transaction limits?",
                "How do I cancel a payment?",
                "Payment methods available",
                "Transaction fees"
            ]
        }
    
    # Account-related queries
    elif any(word in message_lower for word in ['account', 'profile', 'settings', 'password']):
        return {
            'response': """For account management:

**Profile Settings:**
• Update personal information in the Profile section
• Change password in Security Settings
• Enable two-factor authentication for extra security

**Account Features:**
• View transaction history
• Export your data
• Manage notification preferences
• Update privacy settings

**Security:**
• Your account is protected by encryption
• AI monitors for suspicious activity
• Regular security updates

What specific account feature would you like help with?""",
            'suggestions': [
                "How to change password?",
                "Enable two-factor authentication",
                "Update notification settings",
                "Export my data"
            ]
        }
    
    # Transaction history queries
    elif any(word in message_lower for word in ['history', 'transactions', 'past', 'previous']):
        return {
            'response': """To view your transaction history:

1. Go to the 'History' section
2. Use filters to find specific transactions:
   • Date range
   • Transaction status
   • Amount range
   • Category

**Available Information:**
• Transaction details and status
• Payment recipients
• Processing times
• Risk assessments

You can also export your transaction data as CSV for your records.

Looking for a specific transaction?""",
            'suggestions': [
                "Filter transactions by date",
                "Check payment status",
                "Export transaction data",
                "Understanding risk scores"
            ]
        }
    
    # Security-related queries
    elif any(word in message_lower for word in ['security', 'safe', 'fraud', 'protection']):
        return {
            'response': """Your security is our top priority:

**AI Protection:**
• Real-time fraud detection
• Risk scoring for every transaction
• Suspicious pattern recognition
• Automated threat blocking

**Encryption & Privacy:**
• End-to-end encryption
• PCI DSS compliance
• Secure data storage
• Privacy controls

**Authentication:**
• Strong password requirements
• Optional two-factor authentication
• Session timeout protection

**Monitoring:**
• 24/7 system monitoring
• Instant alert system
• Regular security updates

Feel safe about a specific concern?""",
            'suggestions': [
                "How does fraud detection work?",
                "Enable two-factor authentication",
                "Report suspicious activity",
                "Privacy settings"
            ]
        }
    
    # General help
    elif any(word in message_lower for word in ['help', 'support', 'how', 'what', 'guide']):
        return {
            'response': """I'm here to help! Here's what I can assist you with:

**Payments & Transfers:**
• Making payments
• Transaction limits and fees
• Payment methods
• Processing times

**Account Management:**
• Profile settings
• Security features
• Notification preferences
• Data export

**System Features:**
• AI fraud detection
• Risk assessment
• Transaction history
• Policy information

**Support:**
• Technical issues
• Account questions
• Feature explanations
• Best practices

What would you like help with specifically?""",
            'suggestions': [
                "Make a payment",
                "Check account settings",
                "View transaction history",
                "Security features"
            ]
        }
    
    # Default response for unclear queries
    else:
        return {
            'response': """I'm here to help with your banking and payment needs! 

I can assist you with:
• Making payments and transfers
• Managing your account settings
• Understanding transaction history
• Security and privacy features
• General banking questions

Could you please be more specific about what you'd like help with? For example:
• "How do I send money to someone?"
• "What are my transaction limits?"
• "How do I change my password?"

The more details you provide, the better I can assist you!""",
            'suggestions': [
                "How to make a payment?",
                "Account security features",
                "Transaction limits",
                "Contact human support"
            ]
        }

def get_chat_context() -> Dict[str, Any]:
    """Get context for AI response"""
    
    user_data = st.session_state.get('user_data', {})
    recent_messages = st.session_state.chat_history[-5:] if len(st.session_state.chat_history) > 5 else st.session_state.chat_history
    
    return {
        'user_id': user_data.get('id'),
        'user_email': user_data.get('email'),
        'user_role': user_data.get('role'),
        'session_id': st.session_state.chat_session_id,
        'recent_messages': [
            {
                'role': msg['role'],
                'content': msg['content'],
                'timestamp': msg['timestamp'].isoformat()
            }
            for msg in recent_messages
        ]
    }

def get_default_suggestions() -> List[str]:
    """Get default quick suggestions"""
    return [
        "How do I make a payment?",
        "What are the transaction limits?",
        "How can I check my payment history?",
        "What security measures are in place?",
        "How do I cancel a pending payment?",
        "What payment methods are available?"
    ]

def clear_chat_history():
    """Clear chat history"""
    st.session_state.chat_history = []
    st.session_state.chat_session_id = str(uuid.uuid4())
    st.session_state.chat_suggestions = get_default_suggestions()

def export_chat_history():
    """Export chat history as text file"""
    if not st.session_state.chat_history:
        st.warning("No chat history to export")
        return
    
    # Prepare chat export
    export_content = f"Chat Export - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    export_content += "=" * 50 + "\n\n"
    
    for message in st.session_state.chat_history:
        timestamp = message['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        role = "You" if message['role'] == 'user' else "AI Assistant"
        
        export_content += f"[{timestamp}] {role}:\n"
        export_content += f"{message['content']}\n\n"
    
    # Provide download button
    st.download_button(
        label="Download Chat History",
        data=export_content,
        file_name=f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain"
    )

def escalate_to_support(db_manager):
    """Escalate conversation to human support"""
    
    # Add escalation message to chat
    escalation_message = {
        'role': 'system',
        'content': 'Your conversation has been escalated to our human support team. A support agent will review your chat and get back to you soon.',
        'timestamp': datetime.now()
    }
    st.session_state.chat_history.append(escalation_message)
    
    # In a real implementation, this would:
    # 1. Create a support ticket
    # 2. Notify support agents
    # 3. Save chat context for review
    
    st.success("Your conversation has been escalated to human support. You'll receive a response soon!")

def submit_chat_rating(rating: int, db_manager):
    """Submit chat rating and feedback"""
    
    # In a real implementation, this would save to database
    feedback_data = {
        'session_id': st.session_state.chat_session_id,
        'rating': rating,
        'message_count': len(st.session_state.chat_history),
        'user_id': st.session_state.get('user_data', {}).get('id'),
        'timestamp': datetime.now()
    }
    
    # For now, just store in session state
    if 'chat_feedback' not in st.session_state:
        st.session_state.chat_feedback = []
    
    st.session_state.chat_feedback.append(feedback_data)

# Additional helper functions for enhanced functionality

def get_contextual_help(topic: str) -> str:
    """Get contextual help for specific topics"""
    
    help_topics = {
        'payments': "Learn how to make secure payments with our AI-powered validation system.",
        'security': "Understand our multi-layered security features that protect your transactions.",
        'account': "Manage your profile, settings, and preferences easily.",
        'history': "Track and analyze your transaction history with powerful filtering tools."
    }
    
    return help_topics.get(topic, "Get help with banking and payment features.")

def suggest_related_actions(message: str) -> List[str]:
    """Suggest related actions based on user message"""
    
    message_lower = message.lower()
    
    if 'payment' in message_lower:
        return [
            "Go to New Payment",
            "Check Transaction History",
            "View Payment Methods",
            "Contact Support"
        ]
    elif 'account' in message_lower:
        return [
            "Update Profile",
            "Security Settings",
            "Notification Preferences",
            "Export Data"
        ]
    else:
        return [
            "Make Payment",
            "View History",
            "Account Settings",
            "Get Help"
        ]

def handle_special_commands(message: str) -> Optional[str]:
    """Handle special chat commands"""
    
    if message.startswith('/help'):
        return "Available commands: /help, /clear, /export, /support"
    elif message.startswith('/clear'):
        clear_chat_history()
        return "Chat history cleared!"
    elif message.startswith('/export'):
        export_chat_history()
        return "Chat history export initiated!"
    elif message.startswith('/support'):
        escalate_to_support(None)
        return "Escalated to human support!"
    
    return None