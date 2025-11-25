"""
Balthazar - Moteur de recherche
Recherche documentaire et génération de réponses IA
"""
from llama_index.core import VectorStoreIndex, StorageContext, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama

from config import (
    BALTHAZAR_EMBED_MODEL, 
    BALTHAZAR_LLM_MODEL, 
    BALTHAZAR_OLLAMA_BASE_URL, 
    BALTHAZAR_OLLAMA_TIMEOUT
)
from indexer import balthazar_get_milvus_store


def balthazar_init_llm_settings():
    """Initialise les paramètres LLM et embeddings"""
    Settings.embed_model = HuggingFaceEmbedding(model_name=BALTHAZAR_EMBED_MODEL)
    Settings.llm = Ollama(
        model=BALTHAZAR_LLM_MODEL,
        base_url=BALTHAZAR_OLLAMA_BASE_URL,
        request_timeout=BALTHAZAR_OLLAMA_TIMEOUT
    )


def balthazar_query_corpus(question, project_config):
    """
    Interroge le corpus et génère une réponse
    
    Args:
        question: Question en langage naturel
        project_config: Configuration du projet
        
    Returns:
        Réponse générée par le LLM
    """
    milvus_store = balthazar_get_milvus_store(project_config=project_config)
    storage = StorageContext.from_defaults(vector_store=milvus_store)
    index = VectorStoreIndex.from_vector_store(milvus_store, storage_context=storage)
    engine = index.as_query_engine()
    
    return engine.query(question)


def balthazar_search_sources(question, top_k=5, project_config=None):
    """
    Recherche les sources pertinentes
    
    Args:
        question: Terme recherché
        top_k: Nombre de résultats
        project_config: Configuration du projet
    
    Returns:
        Liste de résultats avec file_name, file_path, score, text
    """
    milvus_store = balthazar_get_milvus_store(project_config=project_config)
    storage = StorageContext.from_defaults(vector_store=milvus_store)
    index = VectorStoreIndex.from_vector_store(milvus_store, storage_context=storage)
    
    retriever = index.as_retriever(similarity_top_k=top_k)
    nodes = retriever.retrieve(question)
    
    results = []
    for node in nodes:
        file_name = node.metadata.get('file_name', 'Inconnu')
        file_path = node.metadata.get('file_path', 'Inconnu')
        
        results.append({
            'file_name': file_name,
            'file_path': file_path,
            'score': node.score,
            'text': node.text
        })
    
    return results