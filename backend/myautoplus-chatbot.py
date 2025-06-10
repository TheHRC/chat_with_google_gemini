from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from bs4 import BeautifulSoup
import requests
import os
from typing import List, Dict, Any, Optional
import base64
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)

from langchain.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

from dotenv import load_dotenv
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_LLM_MODEL_NAME = os.getenv("GOOGLE_LLM_MODEL_NAME")
GOOGLE_EMBEDDING_MODEL_NAME = os.getenv("GOOGLE_EMBEDDING_MODEL_NAME")

# Initialize FastAPI app
app = FastAPI(title="MyAutoPlus Registration Chatbot")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define input model
class ChatRequest(BaseModel):
    query: str

# Define response model
class ChatResponse(BaseModel):
    text_response: str
    images: List[Dict[str, str]] = []

# Helper function to scrape and process MyAutoPlus registration content
def scrape_myautoplus_registration_content(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    documents = []
    
    # Extract main sections (Quebec vs other provinces)
    registration_sections = soup.find_all('details')
    
    for section in registration_sections:
        # Get section title
        section_title = section.find('h2').get_text(strip=True)
        
        # Process each step within the section
        steps = section.find_all(lambda tag: tag.name == 'p' and 'Step' in tag.get_text())
        
        for i, step_header in enumerate(steps):
            step_title = step_header.get_text(strip=True)
            
            # Find the content following this step header
            step_content = ""
            next_elements = step_header.find_next('ul').find_all('li')
            for element in next_elements:
                step_content += element.get_text(strip=True) + " "
            
            # Find associated image if any
            image_div = step_header.find_next('div', class_='py-2 flex justify-center items-center')
            image_url = None
            if image_div and image_div.find('img'):
                img_tag = image_div.find('img')
                image_url = img_tag.get('src')
                alt_text = img_tag.get('alt', '')
            
            # Create document
            doc = Document(
                page_content=f"{step_title}: {step_content}",
                metadata={
                    'section': section_title,
                    'step_number': i+1,
                    'step_title': step_title,
                    'image_url': image_url,
                    'full_step': f"{step_title}: {step_content}"
                }
            )
            documents.append(doc)
    
    # Also extract "what you will need" section
    requirements_section = soup.find('p', string=lambda text: text and "What you will need" in text)
    if requirements_section:
        requirements_list = requirements_section.find_next('ul')
        requirements_text = "What you will need: "
        
        for item in requirements_list.find_all('li'):
            requirements_text += item.get_text(strip=True) + " "
        
        doc = Document(
            page_content=requirements_text,
            metadata={
                'section': 'Requirements',
                'step_number': 0,
                'step_title': 'What you will need',
                'full_step': requirements_text
            }
        )
        documents.append(doc)
    
    return documents

# Initialize vector store
# def initialize_vector_store(html_content):
#     # Extract content from HTML
#     documents = scrape_myautoplus_registration_content(html_content)
#
#     # Split text into smaller chunks if needed
#     text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
#
#     # Prepare for embeddings
#     texts = []
#     metadatas = []
#
#     for doc in documents:
#         chunks = text_splitter.split_text(doc.page_content)
#         for chunk in chunks:
#             texts.append(chunk)
#             metadatas.append(doc.metadata)
#
#     # Create vector store
#     embeddings = GoogleGenerativeAIEmbeddings(model=GOOGLE_EMBEDDING_MODEL_NAME, google_api_key=GOOGLE_API_KEY)
#     vectorstore = FAISS.from_texts(texts, embeddings, metadatas=metadatas)
#
#     return vectorstore

import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)

def initialize_vector_store(html_content):
    # Extract content from HTML
    documents = scrape_myautoplus_registration_content(html_content)
    if not documents:
        logging.error("No documents extracted from HTML content.")
        return None

    # Split text into smaller chunks if needed
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    # Prepare for embeddings
    texts = []
    metadatas = []

    for doc in documents:
        chunks = text_splitter.split_text(doc.page_content)
        if not chunks:
            logging.warning(f"No text chunks generated for document: {doc.metadata}")
        for chunk in chunks:
            texts.append(chunk)
            metadatas.append(doc.metadata)

    if not texts:
        logging.error("No text chunks generated from documents.")
        return None

    # Create vector store
    embeddings = GoogleGenerativeAIEmbeddings(model=GOOGLE_EMBEDDING_MODEL_NAME, google_api_key=GOOGLE_API_KEY)
    embedding_vectors = embeddings.embed_texts(texts)
    if not embedding_vectors:
        logging.error("No embeddings generated for text chunks.")
        return None

    vectorstore = FAISS.from_texts(texts, embeddings, metadatas=metadatas)
    return vectorstore



# Function to generate response with images
def generate_response_with_images(query, vectorstore):
    # Create prompt template that instructs the LLM to include images in response
    prompt_template = """
    You are a helpful assistant for MyAutoPlus registration process. 
    Use the following retrieved information to answer the user's question.
    If the information contains references to images, mention that visual guides are available and describe them.
    
    Retrieved information:
    {context}
    
    User question: {question}
    
    Instructions:
    1. Answer specifically based on the retrieved information
    2. If steps are involved, list them in order
    3. Mention when visual guides are available
    4. Be concise but thorough
    
    Answer:
    """
    
    PROMPT = PromptTemplate(
        template=prompt_template, 
        input_variables=["context", "question"]
    )
    
    # Create retrieval chain
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    
    # Get relevant documents
    docs = retriever.get_relevant_documents(query)
    
    # Extract images from metadata
    image_urls = []
    for doc in docs:
        if 'image_url' in doc.metadata and doc.metadata['image_url']:
            image_urls.append({
                'url': doc.metadata['image_url'],
                'step': doc.metadata['step_title'],
                'section': doc.metadata['section']
            })
    
    # Remove duplicates while preserving order
    unique_images = []
    seen_urls = set()
    for img in image_urls:
        if img['url'] not in seen_urls:
            unique_images.append(img)
            seen_urls.add(img['url'])
    
    # Create chain for text response
    llm = ChatGoogleGenerativeAI(
        model=GOOGLE_LLM_MODEL_NAME,
        google_api_key=GOOGLE_API_KEY,
        temperature=0
    )
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": PROMPT}
    )
    
    # Generate text response
    result = qa_chain({"query": query})
    
    return {
        "text_response": result["result"],
        "images": unique_images
    }

# Load HTML content (in a real app, this would be loaded once at startup)
def load_html_content():
    # For this example, we're using the HTML content that was provided
    # In a real app, you might load from a file or fetch from a URL
    with open("myautoplus_registration.html", "r", encoding="utf-8") as f:
        return f.read()

# Create vector store at startup
html_content = """
<!DOCTYPE html>
<!-- HTML content here - replace with actual content in production -->
"""
vectorstore = None

@app.on_event("startup")
async def startup_event():
    global vectorstore, html_content
    # In a real application, you would load the HTML from a file or URL
    # For now, we're using the global variable
    vectorstore = initialize_vector_store(html_content)

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    global vectorstore
    
    if vectorstore is None:
        return {"text_response": "The system is still initializing. Please try again in a moment."}
    
    # Process query
    result = generate_response_with_images(request.query, vectorstore)
    
    return result

# Simple frontend for testing
@app.get("/", response_class=HTMLResponse)
async def get_homepage():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MyAutoPlus Registration Chatbot</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            #chat-container { border: 1px solid #ddd; border-radius: 5px; padding: 20px; height: 400px; overflow-y: auto; margin-bottom: 20px; }
            #input-container { display: flex; }
            #user-input { flex-grow: 1; padding: 10px; border: 1px solid #ddd; border-radius: 5px; margin-right: 10px; }
            button { padding: 10px 20px; background-color: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer; }
            .user-message { text-align: right; margin-bottom: 10px; }
            .bot-message { text-align: left; margin-bottom: 10px; }
            .message-content { display: inline-block; padding: 10px; border-radius: 5px; max-width: 70%; }
            .user-message .message-content { background-color: #DCF8C6; }
            .bot-message .message-content { background-color: #F1F0F0; }
            .image-container { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px; }
            .image-container img { max-width: 200px; max-height: 200px; border: 1px solid #ddd; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>MyAutoPlus Registration Chatbot</h1>
        <div id="chat-container">
            <div class="bot-message">
                <div class="message-content">
                    Hello! I'm the MyAutoPlus Registration Assistant. How can I help you with your registration process today?
                </div>
            </div>
        </div>
        <div id="input-container">
            <input type="text" id="user-input" placeholder="Ask a question about registration...">
            <button onclick="sendMessage()">Send</button>
        </div>

        <script>
            const chatContainer = document.getElementById('chat-container');
            const userInput = document.getElementById('user-input');

            userInput.addEventListener('keypress', function(event) {
                if (event.key === 'Enter') {
                    sendMessage();
                }
            });

            async function sendMessage() {
                const message = userInput.value.trim();
                if (!message) return;

                // Add user message to chat
                addUserMessage(message);
                userInput.value = '';

                // Send request to API
                try {
                    const response = await fetch('/chat', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ query: message }),
                    });

                    const data = await response.json();
                    addBotMessage(data.text_response, data.images);
                } catch (error) {
                    console.error('Error:', error);
                    addBotMessage('Sorry, there was an error processing your request.');
                }
            }

            function addUserMessage(message) {
                const messageDiv = document.createElement('div');
                messageDiv.className = 'user-message';
                messageDiv.innerHTML = `<div class="message-content">${message}</div>`;
                chatContainer.appendChild(messageDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }

            function addBotMessage(message, images = []) {
                const messageDiv = document.createElement('div');
                messageDiv.className = 'bot-message';
                
                let messageHTML = `<div class="message-content">${message}`;
                
                if (images && images.length > 0) {
                    messageHTML += '<div class="image-container">';
                    images.forEach(img => {
                        messageHTML += `<img src="${img.url}" alt="${img.step}" title="${img.section}: ${img.step}">`;
                    });
                    messageHTML += '</div>';
                }
                
                messageHTML += '</div>';
                messageDiv.innerHTML = messageHTML;
                
                chatContainer.appendChild(messageDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
