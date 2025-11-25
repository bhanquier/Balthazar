"""
Balthazar - Export/Import de données
Format .balthazar pour sauvegarder et partager les corpus indexés
"""
import os
import json
import zipfile
from datetime import datetime
import streamlit as st
from llama_index.core import StorageContext

from config import (
    BALTHAZAR_EMBED_MODEL,
    BALTHAZAR_LLM_MODEL,
    BALTHAZAR_VERSION
)
from indexer import balthazar_get_project_paths


def balthazar_export_corpus(output_path, corpus_name, description="", tags=None, project_config=None):
    """
    Balthazar - Exporte le corpus indexé au format .balthazar
    
    Args:
        output_path: Chemin du fichier .balthazar à créer
        corpus_name: Nom du corpus
        description: Description du corpus
        tags: Liste de tags (optionnel)
        project_config: Configuration du projet (optionnel)
        
    Returns:
        Chemin du fichier créé ou None si erreur
    """
    if tags is None:
        tags = []
    
    if not output_path.endswith('.balthazar'):
        output_path += '.balthazar'
    
    st.info(f"📦 Balthazar - Export du corpus vers {output_path}...")
    
    db_path, metadata_path = balthazar_get_project_paths(project_config)
    
    # Création du manifest
    manifest = {
        "format_version": "1.0",
        "export_info": {
            "created_at": datetime.now().isoformat(),
            "balthazar_version": BALTHAZAR_VERSION,
            "export_type": "full"
        },
        "model_info": {
            "embedding_model": BALTHAZAR_EMBED_MODEL,
            "embedding_dim": 384,
            "llm_model": BALTHAZAR_LLM_MODEL
        }
    }
    
    # Métadonnées du corpus
    metadata = {
        "corpus_name": corpus_name,
        "description": description,
        "tags": tags,
        "indexed_at": datetime.now().isoformat()
    }
    
    # Création du ZIP
    try:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Ajoute manifest et metadata
            zipf.writestr("manifest.json", json.dumps(manifest, indent=2))
            zipf.writestr("metadata.json", json.dumps(metadata, indent=2))
            
            # Ajoute la base Milvus complète
            if os.path.exists(db_path):
                zipf.write(db_path, "vectors/milvus.db")
                st.success(f"✅ Base vectorielle exportée")
            
            # Ajoute les métadonnées d'indexation
            if os.path.exists(metadata_path):
                zipf.write(metadata_path, "index_metadata.json")
                st.success(f"✅ Métadonnées d'indexation exportées")
        
        file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
        st.success(f"✅ Corpus exporté : {output_path} ({file_size:.1f} MB)")
        
        return output_path
        
    except Exception as e:
        st.error(f"❌ Erreur lors de l'export : {e}")
        return None


def balthazar_import_corpus(balthazar_file, project_config=None):
    """
    Balthazar - Importe un corpus depuis un fichier .balthazar
    
    Args:
        balthazar_file: Chemin du fichier .balthazar
        project_config: Configuration du projet (optionnel)
        
    Returns:
        True si succès, False sinon
    """
    if not balthazar_file.endswith('.balthazar'):
        st.error("❌ Le fichier doit avoir l'extension .balthazar")
        return False
    
    if not os.path.exists(balthazar_file):
        st.error(f"❌ Fichier introuvable : {balthazar_file}")
        return False
    
    st.info(f"📥 Balthazar - Import du corpus {balthazar_file}...")
    
    db_path, metadata_path = balthazar_get_project_paths(project_config)
    
    try:
        with zipfile.ZipFile(balthazar_file, 'r') as zipf:
            # Lit le manifest
            manifest_data = zipf.read("manifest.json")
            manifest = json.loads(manifest_data)
            
            # Lit les métadonnées
            metadata_data = zipf.read("metadata.json")
            metadata = json.loads(metadata_data)
            
            # Affiche les infos
            st.write(f"**Corpus :** {metadata['corpus_name']}")
            st.write(f"**Description :** {metadata['description']}")
            st.write(f"**Créé le :** {metadata['indexed_at']}")
            st.write(f"**Modèle :** {manifest['model_info']['embedding_model']}")
            
            # Vérifie la compatibilité du modèle
            if manifest['model_info']['embedding_model'] != BALTHAZAR_EMBED_MODEL:
                st.warning(
                    f"⚠️ Modèle différent : "
                    f"{manifest['model_info']['embedding_model']} vs {BALTHAZAR_EMBED_MODEL}"
                )
            
            # Extrait la base vectorielle
            st.info("📂 Extraction de la base vectorielle...")
            zipf.extract("vectors/milvus.db", ".")
            
            # Déplace au bon endroit
            import shutil
            if os.path.exists(db_path):
                os.remove(db_path)
            shutil.move("vectors/milvus.db", db_path)
            
            # Extrait les métadonnées d'indexation si présentes
            try:
                zipf.extract("index_metadata.json", ".")
                if os.path.exists(metadata_path):
                    os.remove(metadata_path)
                shutil.move("index_metadata.json", metadata_path)
            except KeyError:
                st.info("ℹ️ Pas de métadonnées d'indexation dans ce corpus")
            
            # Nettoie
            if os.path.exists("vectors"):
                os.rmdir("vectors")
            
            st.success(f"✅ Corpus importé avec succès !")
            return True
            
    except Exception as e:
        st.error(f"❌ Erreur lors de l'import : {e}")
        return False


def balthazar_list_corpus_info(balthazar_file):
    """
    Balthazar - Affiche les informations d'un fichier .balthazar sans l'importer
    
    Args:
        balthazar_file: Chemin du fichier .balthazar
        
    Returns:
        Dictionnaire avec les informations ou None si erreur
    """
    if not os.path.exists(balthazar_file):
        return None
    
    try:
        with zipfile.ZipFile(balthazar_file, 'r') as zipf:
            manifest = json.loads(zipf.read("manifest.json"))
            metadata = json.loads(zipf.read("metadata.json"))
            
            return {
                "manifest": manifest,
                "metadata": metadata,
                "file_size_mb": os.path.getsize(balthazar_file) / (1024 * 1024)
            }
    except Exception as e:
        st.error(f"❌ Erreur lecture : {e}")
        return None