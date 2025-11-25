"""
Balthazar - Moteur d'indexation
Indexation par batch avec déduplication et mise à jour incrémentale
Support format .balthazar
"""
import os
import json
import streamlit as st
from datetime import datetime
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext
from llama_index.vector_stores.milvus import MilvusVectorStore

from config import (
    BALTHAZAR_BATCH_SIZE, 
    BALTHAZAR_COLLECTION_NAME, 
    BALTHAZAR_EMBED_DIM,
    BALTHAZAR_NAME
)
from utils import balthazar_is_temp_docx, balthazar_compute_md5
from monitoring import balthazar_send_alert_mail


def balthazar_load_index_metadata(project_config):
    """
    Balthazar - Charge les métadonnées de l'index
    
    Args:
        project_config: Configuration du projet
    
    Returns:
        Dictionnaire des métadonnées
    """
    metadata_path = project_config['metadata_path']
    
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            st.warning(f"⚠️ Erreur lecture métadonnées : {e}")
            return {}
    return {}


def balthazar_save_index_metadata(metadata, project_config):
    """
    Balthazar - Sauvegarde les métadonnées de l'index
    
    Args:
        metadata: Dictionnaire des métadonnées
        project_config: Configuration du projet
    """
    metadata_path = project_config['metadata_path']
    
    try:
        with open(metadata_path, 'w') as f:
            json.dump(metadata, indent=2, fp=f)
    except Exception as e:
        st.error(f"❌ Erreur sauvegarde métadonnées : {e}")


def balthazar_check_folder_index_status(folder, project_config):
    """
    Balthazar - Vérifie l'état de l'index pour un dossier
    
    Args:
        folder: Chemin du dossier à vérifier
        project_config: Configuration du projet
        
    Returns:
        Tuple (has_index, files_to_add, files_to_update, files_to_remove)
    """
    from utils import balthazar_scan_docs
    
    metadata = balthazar_load_index_metadata(project_config)
    folder_abs = os.path.abspath(folder)
    
    folder_data = metadata.get(folder_abs, {})
    indexed_files = folder_data.get('files', {})
    
    current_files = balthazar_scan_docs(folder)
    
    files_to_add = []
    files_to_update = []
    files_to_remove = []
    
    for file_path in current_files:
        file_hash = balthazar_compute_md5(file_path)
        
        if file_path not in indexed_files:
            files_to_add.append(file_path)
        elif indexed_files[file_path]['hash'] != file_hash:
            files_to_update.append(file_path)
    
    for indexed_path in indexed_files.keys():
        if indexed_path not in current_files:
            files_to_remove.append(indexed_path)
    
    has_index = len(indexed_files) > 0
    
    return has_index, files_to_add, files_to_update, files_to_remove


def balthazar_update_folder_metadata(folder, processed_files, project_config):
    """
    Balthazar - Met à jour les métadonnées après indexation
    
    Args:
        folder: Chemin du dossier
        processed_files: Liste des fichiers traités
        project_config: Configuration du projet
    """
    metadata = balthazar_load_index_metadata(project_config)
    folder_abs = os.path.abspath(folder)
    
    if folder_abs not in metadata:
        metadata[folder_abs] = {
            'folder': folder_abs,
            'first_indexed_at': datetime.now().isoformat(),
            'files': {}
        }
    
    metadata[folder_abs]['last_updated_at'] = datetime.now().isoformat()
    
    for file_path in processed_files:
        if os.path.exists(file_path):
            metadata[folder_abs]['files'][file_path] = {
                'hash': balthazar_compute_md5(file_path),
                'indexed_at': datetime.now().isoformat(),
                'size_bytes': os.path.getsize(file_path)
            }
    
    balthazar_save_index_metadata(metadata, project_config)


def balthazar_incremental_ingest(folder, milvus_store, batch_size=BALTHAZAR_BATCH_SIZE, email_alert=None, project_config=None):
    """
    Balthazar - Indexation incrémentale
    
    Args:
        folder: Dossier à indexer
        milvus_store: Instance MilvusVectorStore
        batch_size: Taille des batches
        email_alert: Email pour alertes
        project_config: Configuration du projet
        
    Returns:
        Tuple (error_batches, total_indexed, stats)
    """
    st.info(f"🔍 {BALTHAZAR_NAME} - Vérification de l'index pour {folder}...")
    
    has_index, to_add, to_update, to_remove = balthazar_check_folder_index_status(folder, project_config)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📄 Index existant", "Oui" if has_index else "Non")
    with col2:
        st.metric("➕ Nouveaux", len(to_add))
    with col3:
        st.metric("🔄 Modifiés", len(to_update))
    with col4:
        st.metric("🗑️ Supprimés", len(to_remove))
    
    files_to_process = to_add + to_update
    
    if not files_to_process and not to_remove:
        st.success(f"✅ {BALTHAZAR_NAME} - Index à jour, rien à faire !")
        return [], 0, {
            'has_index': has_index,
            'added': 0,
            'updated': 0,
            'removed': 0
        }
    
    errors = []
    total_indexed = 0
    
    if files_to_process:
        st.info(f"⚙️ {BALTHAZAR_NAME} - Indexation de {len(files_to_process)} fichier(s)...")
        errors, total_indexed = balthazar_batch_ingest(
            files_to_process, 
            milvus_store, 
            batch_size, 
            email_alert,
            project_config
        )
    
    if to_remove:
        st.warning(f"⚠️ {len(to_remove)} fichier(s) supprimé(s) détecté(s).")
    
    if total_indexed > 0:
        balthazar_update_folder_metadata(folder, files_to_process, project_config)
    
    stats = {
        'has_index': has_index,
        'added': len(to_add),
        'updated': len(to_update),
        'removed': len(to_remove)
    }
    
    return errors, total_indexed, stats


def balthazar_get_milvus_store(overwrite=False, project_config=None):
    """
    Balthazar - Retourne une instance MilvusVectorStore
    
    Args:
        overwrite: Si True, écrase la collection
        project_config: Configuration du projet
        
    Returns:
        Instance MilvusVectorStore
    """
    db_path = project_config['db_path']
    
    return MilvusVectorStore(
        uri=db_path,
        collection_name=BALTHAZAR_COLLECTION_NAME,
        dim=BALTHAZAR_EMBED_DIM,
        overwrite=overwrite
    )


def balthazar_batch_ingest(docx_files, milvus_store, batch_size=BALTHAZAR_BATCH_SIZE, email_alert=None, project_config=None):
    """
    Balthazar - Indexe des fichiers par batch
    
    Args:
        docx_files: Liste des fichiers
        milvus_store: Instance MilvusVectorStore
        batch_size: Taille des batches
        email_alert: Email pour alertes
        project_config: Configuration du projet
        
    Returns:
        Tuple (error_batches, total_indexed)
    """
    dedup_hashes = set()
    error_batches = []
    total_indexed = 0
    total_files = len(docx_files)
    total_batches = (total_files + batch_size - 1) // batch_size
    
    db_path = project_config['db_path']
    
    st.markdown(f"### 📦 {BALTHAZAR_NAME} - Progression globale")
    batch_progress = st.progress(0)
    batch_status = st.empty()
    
    st.markdown(f"### 📄 {BALTHAZAR_NAME} - Progression détaillée")
    file_progress = st.progress(0)
    file_status = st.empty()
    
    st.markdown(f"### 📊 {BALTHAZAR_NAME} - Statistiques")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📁 Total", total_files)
    with col2:
        metric_indexed = st.empty()
        metric_indexed.metric("✅ Indexés", 0)
    with col3:
        metric_duplicates = st.empty()
        metric_duplicates.metric("🔄 Doublons", 0)
    with col4:
        metric_errors = st.empty()
        metric_errors.metric("❌ Erreurs", 0)
    
    for i in range(0, len(docx_files), batch_size):
        batch_num = i // batch_size
        batch = docx_files[i:i+batch_size]
        batch_filtered = []
        
        batch_progress.progress((batch_num) / total_batches)
        batch_status.text(f"📦 Batch {batch_num + 1}/{total_batches}")
        
        for idx, fname in enumerate(batch):
            file_in_batch = idx + 1
            files_processed = i + idx + 1
            
            file_progress.progress(file_in_batch / len(batch))
            file_status.text(
                f"📄 Analyse: {os.path.basename(fname)} "
                f"({files_processed}/{total_files})"
            )
            
            if balthazar_is_temp_docx(fname):
                continue
            
            h = balthazar_compute_md5(fname)
            if h in dedup_hashes:
                metric_duplicates.metric("🔄 Doublons", len(dedup_hashes) - total_indexed)
                continue
            
            dedup_hashes.add(h)
            batch_filtered.append(fname)
        
        file_progress.progress(0)
        
        if not batch_filtered:
            batch_progress.progress((batch_num + 1) / total_batches)
            continue
        
        try:
            file_status.text(
                f"⚙️ Indexation de {len(batch_filtered)} documents du batch {batch_num + 1}..."
            )
            
            docs = SimpleDirectoryReader(input_files=batch_filtered).load_data()
            
            if i == 0 and not os.path.exists(db_path):
                index = VectorStoreIndex.from_documents(docs, vector_store=milvus_store)
            else:
                storage = StorageContext.from_defaults(vector_store=milvus_store)
                index = VectorStoreIndex.from_documents(docs, storage_context=storage)
            
            index.storage_context.persist()
            total_indexed += len(batch_filtered)
            
            metric_indexed.metric("✅ Indexés", total_indexed)
            metric_duplicates.metric("🔄 Doublons", len(dedup_hashes) - total_indexed)
            
            batch_progress.progress((batch_num + 1) / total_batches)
            
        except Exception as e:
            error_batches.append((i, str(e)))
            st.error(f"[{BALTHAZAR_NAME}] ❌ Erreur batch {batch_num + 1}: {e}")
            
            metric_errors.metric("❌ Erreurs", len(error_batches))
            
            balthazar_send_alert_mail(
                f"Erreur batch {batch_num + 1}",
                f"{e}",
                email_alert
            )
            
            batch_progress.progress((batch_num + 1) / total_batches)
    
    batch_progress.progress(1.0)
    file_progress.progress(1.0)
    batch_status.text(f"✅ {BALTHAZAR_NAME} - Indexation terminée")
    file_status.text(f"✅ {BALTHAZAR_NAME} - Tous les fichiers traités")
    
    return error_batches, total_indexed


def balthazar_reset_database(project_config):
    """
    Balthazar - Supprime la base et métadonnées
    
    Args:
        project_config: Configuration du projet
    
    Returns:
        True si succès
    """
    db_path = project_config['db_path']
    metadata_path = project_config['metadata_path']
    
    deleted = False
    
    if os.path.exists(db_path):
        os.remove(db_path)
        deleted = True
    
    if os.path.exists(metadata_path):
        os.remove(metadata_path)
        deleted = True
    
    return deleted