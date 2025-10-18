import os
import pickle
from langchain.vectorstores import FAISS
from langchain.embeddings.openai import OpenAIEmbeddings

VECTOR_FILE = "faiss_index.pkl"

def save_vector_store(vector_store):
    with open(VECTOR_FILE, "wb") as f:
        pickle.dump(vector_store, f)

def load_vector_store():
    if os.path.exists(VECTOR_FILE):
        with open(VECTOR_FILE, "rb") as f:
            return pickle.load(f)
    return None

def create_vector_store(documents):
    embeddings = OpenAIEmbeddings()
    vector_store = FAISS.from_texts(documents, embeddings)
    save_vector_store(vector_store)
    return vector_store
