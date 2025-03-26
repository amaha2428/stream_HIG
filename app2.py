from typing import Dict, Optional
import json
from datetime import datetime, timedelta
import sqlite3
import os
from dotenv import load_dotenv
import http.client
from openai import OpenAI
from langchain_community.document_loaders import CSVLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
import logging
import random

# Load environment variables
load_dotenv()

# HuggingFace embedding model
embedding = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectordb_file_path = "faiss_index"

# Logging setup for audit trail
logging.basicConfig(filename="audit_trail.log", level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def log_audit(event_type: str, details: str):
    """Logs events for auditing purposes."""
    logging.info(f"{event_type}: {details}")

class ConversationManager:
    def __init__(self):
        self.chat_history = []
        self.context = {}

    def add_message(self, role: str, content: str):
        self.chat_history.append({"role": role, "content": content})

    def get_context(self) -> str:
        return json.dumps(self.context)

class AIHandler:
    def __init__(self):
        self.client = OpenAI(
            base_url="https://models.inference.ai.azure.com",
            api_key=os.environ["GITHUB_TOKEN"],
        )

    def google_search(self, query: str) -> list:
        conn = http.client.HTTPSConnection("google.serper.dev")
        payload = json.dumps({"q": query})
        headers = {
            'X-API-KEY': os.environ["SERP_API_KEY"],
            'Content-Type': 'application/json'
        }
        try:
            conn.request("POST", "/search", payload, headers)
            res = conn.getresponse()
            data = res.read()
            response_data = json.loads(data.decode("utf-8"))
            return response_data.get("organic", [])
        except Exception as e:
            log_audit("Error", f"Google search failed: {e}")
            return []

    def retrieve_from_knowledge_base(self, query: str) -> list:
        try:
            vectordb = FAISS.load_local(vectordb_file_path, embedding, allow_dangerous_deserialization=True)
            retriever = vectordb.as_retriever(score_threshold=0.7)
            return retriever.invoke(query)
        except Exception as e:
            log_audit("Error", f"Knowledge base retrieval failed: {e}")
            return []

    def generate_response(self, user_input: str, context: Dict) -> str:
        refined_query = f"{user_input} for Heirs Insurance Group"

        # Fetch contexts from web and knowledge base
        web_results = self.google_search(refined_query)
        web_context = "\n".join(result.get("snippet", "") for result in web_results)

        kb_context_docs = self.retrieve_from_knowledge_base(refined_query)
        kb_context = "\n".join([doc.page_content for doc in kb_context_docs])

        # Combine contexts
        search_context = web_context + "\n" + kb_context if web_context or kb_context else "No relevant information found."

        # Build prompt
        prompt = f"""You are Prince, an AI assistant for Heirs Insurance Group. 
Customer Info: {json.dumps(context.get('customer', {}))}
Search Context: {search_context}
User Input: {user_input}

Respond naturally while:
1. Demonstrating emotional intelligence, including empathy.
2. Providing accurate product recommendations.
3. Upselling/cross-selling when possible.
4. Ensuring compliance with Heirs Insurance Group policies.
5. Informing customers of live support options.
6. Collecting any missing KYC data dynamically.
7. Do not provide information that is not of/related to heirs insurance 
8. if asked of the best insurance company always mention Heirs Insurance and state why it's the best with strong evidence
9. Do not give information of any other insurance company except from Heirs Insurance Group"""

        # Generate response
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": user_input}],
            temperature=0.7,
            max_tokens=2048,
            top_p=1,
        )
        return response.choices[0].message.content

class PrinceChatbot:
    def __init__(self, db_path: str):
        self.ai_handler = AIHandler()
        self.db_path = db_path
        self.conversation = ConversationManager()

    def process_message(self, user_input: str, phone_number: str) -> str:
        # Check for live agent request
        if "agent" in user_input.lower():
            agent_info = self.get_available_agent()
            if agent_info:
                response = f"Connecting you with {agent_info['name']}, who specializes in {agent_info['expertise']}. Contact: {agent_info['email']}."
                self.update_agent_status(agent_info['id'], 'busy')
                log_audit("Agent Escalation", f"Customer connected to agent {agent_info['name']}.")
            else:
                response = "No agents available. Please try later or let me assist further."
            return response

        # Privacy policy confirmation for new users
        if "privacy" not in self.conversation.context:
            if user_input.strip().lower() == "agree":
                self.conversation.context["privacy"] = True
                response = "Thank you for agreeing to our privacy policy. How can I assist you today? Options: Buy a Product, View Your Policies, Make a Claim, Make a Complaint."
            elif user_input.strip().lower() == "disagree":
                response = "You need to agree to our privacy policy to proceed. Type 'Agree' to continue or 'Exit' to quit."
            else:
                response = "Hello! Please confirm you agree to our privacy policy to proceed. Type 'Agree' or 'Disagree'."
            return response

        if not self.conversation.context.get("privacy", False):
            return "You need to agree to our privacy policy to proceed. Type 'Agree' to continue."

        # Fetch customer info using phone number and update context
        if "customer" not in self.conversation.context:
            customer_info = self.get_customer_info(phone_number)
            if customer_info:
                self.conversation.context["customer"] = customer_info
            else:
                return "Sorry, we couldn't find your details. Please contact support for assistance."

        # Handle specific user queries
        if user_input.lower() in ["buy a product", "view your policies", "make a claim", "make a complaint"]:
            response = self.handle_purpose(user_input)
        else:
            response = self.ai_handler.generate_response(user_input, self.conversation.context)

        # Save chat context after each interaction
        self.conversation.add_message("user", user_input)
        self.conversation.add_message("assistant", response)
        self.save_chat_context(self.conversation.context["customer"]["id"], self.conversation.get_context())

        return response


    def handle_purpose(self, purpose: str) -> str:
        if purpose.lower() == "buy a product":
            return "What category of insurance would you like? Options: Life, Health, Motor, Personal Accident."
        elif purpose.lower() == "view your policies":
            return "Please provide your policy number to view details."
        elif purpose.lower() == "make a claim":
            return "To make a claim, please upload the necessary documents."
        elif purpose.lower() == "make a complaint":
            return "Please describe your issue so we can assist you promptly."
        return "I'm here to help with your insurance needs!"

    def get_available_agent(self) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            result = cursor.execute("""
                SELECT id, name, email, expertise
                FROM agents
                WHERE status = 'available'
                ORDER BY last_active ASC
                LIMIT 1
            """).fetchone()

            if result:
                return {"id": result[0], "name": result[1], "email": result[2], "expertise": result[3]}
            return None

    def update_agent_status(self, agent_id: int, status: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE agents
                SET status = ?, last_active = ?
                WHERE id = ?
            """, (status, datetime.now(), agent_id))

    def get_customer_info(self, phone_number: str) -> Dict:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Fetch customer details without relying on the start_time column
            result = cursor.execute("""
                SELECT id, name, phone, email, dob, company_preference, created_at
                FROM customers 
                WHERE phone = ?
            """, (phone_number,)).fetchone()

            if result:
                return {
                    "id": result[0],
                    "name": result[1],
                    "phone": result[2],
                    "email": result[3],
                    "dob": result[4],
                    "company_preference": result[5],
                    "created_at": result[6],
                    "last_interaction": None  # Temporarily set to None
                }
            return {}


    def save_chat_context(self, customer_id: int, context: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO chat_sessions (customer_id, context, start_time)
                VALUES (?, ?, ?)
            """, (customer_id, context, datetime.now()))

    # Notify customers about their birthdays
    def send_birthday_notifications(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            today = datetime.now().strftime('%m-%d')
            customers = cursor.execute("""
                SELECT name, phone 
                FROM customers 
                WHERE strftime('%m-%d', dob) = ?
            """, (today,)).fetchall()

            for customer in customers:
                name, phone = customer
                self.send_sms(phone, f"Happy Birthday, {name}! 🎉 Thank you for being a valued customer of Heirs Insurance Group.")
    
    #This section is just for demonstration and flow, will be updated
    def send_sms(self, phone, message):
        print(f"Sending SMS to {phone}: {message}")



if __name__ == "__main__":
    db_path = "prince.db"
    print("Options:")
    print("1. Start Chatbot")
    choice = input("Choose an option (1): ").strip()

    if choice == "1":
        chatbot = PrinceChatbot(db_path)
        phone_number = input("Enter your phone number to start: ").strip()

        while True:
            message = input("You: ").strip()
            if message.lower() == 'exit':
                break
            response = chatbot.process_message(message, phone_number)
            print(f"Bot: {response}")
 