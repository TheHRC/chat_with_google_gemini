import os
from abc import ABC, abstractmethod

# For text-to-speech
import pyttsx3
from dotenv import load_dotenv
from langchain.chains import RetrievalQA
from langchain.docstore.document import Document
from langchain.document_loaders import DirectoryLoader, PyPDFLoader
from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI

# Loading the environment variables
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_LLM_MODEL_NAME = os.getenv("GOOGLE_LLM_MODEL_NAME")
GOOGLE_EMBEDDING_MODEL_NAME = os.getenv("GOOGLE_EMBEDDING_MODEL_NAME")


class ChatWithDocuments(ABC):
    @abstractmethod
    def _get_embedder(self):
        pass

    @abstractmethod
    def _load_doc(self) -> list[Document]:
        pass

    @abstractmethod
    def _clean_text(self, text: str) -> str:
        pass

    @abstractmethod
    def _get_text_from_doc(self, docs: list[Document]) -> list[Document]:
        pass

    @abstractmethod
    def _store_and_get_embeddings(self):
        pass

    @abstractmethod
    def _get_stored_embeddings(self):
        pass

    @abstractmethod
    def _get_retrival_chain(self):
        pass

    @abstractmethod
    def ask_llm(self, query: str):
        pass

    @abstractmethod
    def _get_tts_engine(self):
        pass

    @abstractmethod
    def play_llm_response(self, llm_response: str):
        pass


class ChatWithPDF(ChatWithDocuments):

    def __init__(self, doc_path: str = None, embeddings_path: str = None, single_file: bool = False):
        self.doc_path = doc_path
        self.single_file = single_file
        if single_file and doc_path:
            file_name = os.path.splitext(os.path.basename(doc_path))[0]
            self.path_to_store_embeddings = os.path.join(r"C:\Users\princ\workspace\projects\chatbot_with_google_gemini\backend\embeddings", file_name)
        else:
            self.path_to_store_embeddings = r"C:\Users\princ\workspace\projects\chatbot_with_google_gemini\backend\embeddings" if not embeddings_path else embeddings_path
        os.makedirs(self.path_to_store_embeddings, exist_ok=True)
        # self.text_to_speech_engine = self._get_tts_engine()
        self.embedder = self._get_embedder()
        self.embeddings = self._store_and_get_embeddings() if doc_path else self._get_stored_embeddings()

    def _get_embedder(self):
        # cuda_available = torch.cuda.is_available()
        # return HuggingFaceInstructEmbeddings(model_name="hkunlp/instructor-xl",
        #                                      # Todo: add cuda availability check later
        #                                      model_kwargs={"device": "cpu" if not cuda_available else "cuda"})
        return GoogleGenerativeAIEmbeddings(model=GOOGLE_EMBEDDING_MODEL_NAME, google_api_key=GOOGLE_API_KEY)

    def _load_doc(self) -> list[Document]:
        if self.single_file:
            loader = PyPDFLoader(self.doc_path)
        else:
            loader = DirectoryLoader(self.doc_path, glob=f"./*.pdf", loader_cls=PyPDFLoader)

        # returns docs
        return loader.load()

    def _clean_text(self, text: str) -> str:
        return text.encode('utf-8', 'ignore').decode('utf-8')

    def _get_text_from_doc(self, docs: list[Document]) -> list[Document]:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200)

        cleaned_docs = []
        for doc in docs:
            cleaned_text = self._clean_text(doc.page_content)
            cleaned_docs.append(Document(page_content=cleaned_text, metadata=doc.metadata))

        return text_splitter.split_documents(cleaned_docs)

    def _store_and_get_embeddings(self):
        docs = self._load_doc()
        texts = self._get_text_from_doc(docs)
        vector_db = Chroma.from_documents(texts, self.embedder, persist_directory=self.path_to_store_embeddings)
        return vector_db

    def _get_stored_embeddings(self):
        vector_db = Chroma(persist_directory=self.path_to_store_embeddings, embedding_function=self.embedder)
        return vector_db

    def _get_retrival_chain(self):
        # retriever = self.embeddings.as_retriever(score_threshold=0.7)
        retriever = self.embeddings.as_retriever(search_kwargs={"k": 5})
        prompt_template = """Given the following context and a question, generate an answer based on this context only.
           In the answer try to provide as much text as possible from "response" section in the source document context
           without making much changes. If the answer is not found in the context, kindly state "I don't know." 
           Don't try to make up an answer.

           CONTEXT: {context}

           QUESTION: {question}"""

        PROMPT = PromptTemplate(
            template=prompt_template, input_variables=["context", "question"]
        )
        llm = ChatGoogleGenerativeAI(model=GOOGLE_LLM_MODEL_NAME,
                                     google_api_key=GOOGLE_API_KEY,
                                     convert_system_message_to_human=True
                                     )
        return RetrievalQA.from_chain_type(llm=llm,
                                           # chain_type="stuff",
                                           retriever=retriever,
                                           # memory=memory,
                                           return_source_documents=True,
                                           # chain_type_kwargs={"prompt": PROMPT},
                                           verbose=True)

    def ask_llm(self, query: str):
        chain = self._get_retrival_chain()
        llm_response = chain(query)
        return llm_response["result"]

    def _get_tts_engine(self):
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        engine.setProperty("voice", voices[1].id)
        engine.setProperty("rate", 150)
        return engine

    def play_llm_response(self, llm_response: str):
        print(llm_response)
        self.text_to_speech_engine.say(llm_response)
        self.text_to_speech_engine.runAndWait()


def llm_initializer(embeddings_path: str):
    print("Initializing...")
    chat_with_pdf = ChatWithPDF(embeddings_path=embeddings_path)
    print("Done Initializing!")
    return chat_with_pdf


if __name__ == "__main__":
    print("Welcome to chat with document!")
    print("=" * 50)
    choice = int(input("1. Save new encoding & start chatting\n"
                       "2. Chat with existing encoding\n"
                       "3. Add single PDF and embed\n"
                       "Please enter your choice: "
                       )
                 )
    if choice == 1:
        doc_path = input("Enter the PDF(s) path: ")
        chat_with_pdf = ChatWithPDF(doc_path)
        while True:
            query = input("Query: ").strip()
            llm_response = chat_with_pdf.ask_llm(query)
            chat_with_pdf.play_llm_response(llm_response)
    elif choice == 2:
        embeddings_path = input("Enter the embedding's path: ").strip()
        chat_with_pdf = ChatWithPDF(embeddings_path=embeddings_path)
        while True:
            query = input("Query: ").strip()
            llm_response = chat_with_pdf.ask_llm(query)
            print(llm_response)
    elif choice == 3:
        file_path = input("Enter the PDF file path: ").strip()
        chat_with_pdf = ChatWithPDF(doc_path=file_path, single_file=True)
        print("Single PDF embedded and loaded successfully!")
