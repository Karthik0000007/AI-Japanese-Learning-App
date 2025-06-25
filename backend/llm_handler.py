from langchain_community.llms import Ollama

# Initialize the model
ollama = Ollama(model="llama3")

def ask_llama(prompt):
    response = ollama.invoke(prompt)
    return response
