"""
Balthazar - Interface Streamlit
Gestion de projets au format .balthazar
"""
import streamlit as st
import asyncio
import nest_asyncio
import os
from datetime import datetime

nest_asyncio.apply()
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from config import BALTHAZAR_NAME, BALTHAZAR_VERSION, BALTHAZAR_DESCRIPTION
from utils import balthazar_scan_docs
from indexer import (
    balthazar_get_milvus_store, 
    balthazar_reset_database,
    balthazar_incremental_ingest
)
from search import (
    balthazar_init_llm_settings, 
    balthazar_query_corpus, 
    balthazar_search_sources
)
from monitoring import balthazar_init_prometheus
from projects import (
    balthazar_list_projects,
    balthazar_get_current_project,
    balthazar_set_current_project,
    balthazar_create_project,
    balthazar_delete_project,
    balthazar_open_project,
    balthazar_save_project,
    balthazar_close_project,
    balthazar_export_project
)

# === CONFIGURATION ===
st.set_page_config(
    page_title=f"{BALTHAZAR_NAME} - {BALTHAZAR_DESCRIPTION}",
    page_icon="🔍",
    layout="wide"
)

# === INITIALISATION ===
balthazar_init_llm_settings()
batch_success, batch_error, docs_indexed = balthazar_init_prometheus()

# === GESTION PROJET ACTUEL ===
if "current_project" not in st.session_state:
    current_balthazar = balthazar_get_current_project()
    if current_balthazar and os.path.exists(current_balthazar):
        st.session_state.current_project = balthazar_open_project(current_balthazar)
    else:
        st.session_state.current_project = None

current_project = st.session_state.current_project

# === SIDEBAR ===
with st.sidebar:
    st.title(f"🔍 {BALTHAZAR_NAME}")
    st.caption(f"Version {BALTHAZAR_VERSION}")
    st.divider()
    
    # Sélection projet
    st.subheader("📁 Projet")
    
    projects = balthazar_list_projects()
    
    if projects:
        project_options = {p['balthazar_file']: p['name'] for p in projects}
        project_options['_new'] = "➕ Nouveau..."
        
        current_file = current_project['balthazar_file'] if current_project else None
        
        selected = st.selectbox(
            "Sélectionner",
            options=list(project_options.keys()),
            format_func=lambda x: project_options[x],
            index=0 if not current_file else (
                list(project_options.keys()).index(current_file) 
                if current_file in project_options else 0
            ),
            key="project_selector"
        )
        
        if selected == '_new':
            st.session_state.show_new_project = True
        elif selected != current_file:
            # Ferme l'ancien projet
            if current_project:
                balthazar_close_project(current_project)
            
            # Ouvre le nouveau
            st.session_state.current_project = balthazar_open_project(selected)
            balthazar_set_current_project(selected)
            st.session_state.balthazar_indexed = False
            st.rerun()
    else:
        st.info("Aucun projet")
        st.session_state.show_new_project = True
    
    # Infos projet
    if current_project:
        with st.expander("ℹ️ Infos", expanded=False):
            st.write(f"**Nom:** {current_project['name']}")
            st.write(f"**Dossier:** `{current_project['folder_path']}`")
            if current_project.get('description'):
                st.write(f"**Description:** {current_project['description']}")
    
    st.divider()
    
    # Navigation
    page = st.radio(
        "Navigation",
        ["🏠 Accueil", "🔍 Recherche", "📁 Projets", "⚙️ Admin"],
        label_visibility="collapsed"
    )
    
    st.divider()
    
    # Stats
    st.subheader("📊 Stats")
    if current_project and os.path.exists(current_project['db_path']):
        size = os.path.getsize(current_project['db_path']) / (1024 * 1024)
        st.metric("Base", f"{size:.1f} MB")
    else:
        st.info("Pas d'index")

# === FORMULAIRE NOUVEAU PROJET ===
if st.session_state.get('show_new_project', False):
    with st.form("new_project"):
        st.subheader("➕ Nouveau projet")
        
        name = st.text_input("Nom", placeholder="Documentation FMB")
        desc = st.text_area("Description", placeholder="Documents financiers")
        folder = st.text_input("Dossier source", placeholder="/chemin/vers/dossier")
        
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("✅ Créer", use_container_width=True)
        with col2:
            cancel = st.form_submit_button("❌ Annuler", use_container_width=True)
        
        if submit and name and folder:
            balthazar_file = balthazar_create_project(name, desc, folder)
            if balthazar_file:
                if current_project:
                    balthazar_close_project(current_project)
                st.session_state.current_project = balthazar_open_project(balthazar_file)
                balthazar_set_current_project(balthazar_file)
                st.session_state.show_new_project = False
                st.session_state.balthazar_indexed = False
                st.rerun()
        
        if cancel:
            st.session_state.show_new_project = False
            st.rerun()

# === VÉRIFICATION PROJET ===
if not current_project and page not in ["📁 Projets"]:
    st.warning("⚠️ Aucun projet sélectionné")
    st.stop()

# === PAGE ACCUEIL ===
if page == "🏠 Accueil":
    st.title(f"🔍 {BALTHAZAR_NAME}")
    st.subheader(BALTHAZAR_DESCRIPTION)
    
    if current_project:
        st.info(f"📁 Projet: **{current_project['name']}**")
        
        # Indexation auto
        if "balthazar_indexed" not in st.session_state:
            folder = current_project['folder_path']
            
            if os.path.isdir(folder):
                milvus_store = balthazar_get_milvus_store(project_config=current_project)
                errors, total, stats = balthazar_incremental_ingest(
                    folder,
                    milvus_store,
                    project_config=current_project
                )
                
                if stats['has_index']:
                    st.info("🔄 Mise à jour incrémentale")
                else:
                    st.info("🆕 Indexation initiale")
                
                if total > 0:
                    docs_indexed.set(total)
                    
                    if not errors:
                        st.success(
                            f"✅ {stats['added']} nouveau(x), "
                            f"{stats['updated']} modifié(s)"
                        )
                    else:
                        st.warning(f"⚠️ {len(errors)} erreurs")
                else:
                    st.success("✅ Index à jour")
                
                # Sauvegarde le projet
                balthazar_save_project(current_project)
            else:
                st.error(f"❌ Dossier introuvable: {folder}")
            
            st.session_state.balthazar_indexed = True
        else:
            st.success("✅ Corpus vérifié")
            
            if st.button("🔍 Vérifier mises à jour", use_container_width=True):
                st.session_state.balthazar_indexed = False
                st.rerun()
        
        # Actions
        st.divider()
        st.subheader("⚡ Actions")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Ré-indexer", use_container_width=True):
                st.session_state.balthazar_indexed = False
                st.rerun()
        with col2:
            if st.button("💾 Sauvegarder", use_container_width=True):
                if balthazar_save_project(current_project):
                    st.success("✅ Projet sauvegardé")

# === PAGE RECHERCHE ===
elif page == "🔍 Recherche":
    st.title(f"🔍 Recherche")
    
    if current_project:
        st.info(f"📁 Dans: **{current_project['name']}**")
        
        query = st.text_input(
            "Rechercher:",
            placeholder="budget, contrat, sécurité...",
            key="search"
        )
        
        num_results = st.slider("Résultats", 3, 20, 5)
        
        if st.button("🔎 Rechercher", type="primary", use_container_width=True):
            if not query:
                st.warning("⚠️ Entrez un terme")
            else:
                with st.spinner("Recherche..."):
                    results = balthazar_search_sources(
                        query, 
                        top_k=num_results,
                        project_config=current_project
                    )
                    
                    if not results:
                        st.warning("Aucun résultat")
                    else:
                        st.success(f"✅ {len(results)} résultat(s)")
                        
                        for i, r in enumerate(results, 1):
                            with st.expander(
                                f"📄 {i}. {r['file_name']} ({r['score']:.3f})",
                                expanded=(i == 1)
                            ):
                                st.markdown(f"**Fichier:** `{r['file_path']}`")
                                st.metric("Score", f"{r['score']:.3f}")
                                st.text_area(
                                    "Extrait",
                                    r['text'],
                                    height=200,
                                    key=f"r_{i}",
                                    disabled=True,
                                    label_visibility="collapsed"
                                )
        
        # Q&A
        st.divider()
        with st.expander("💬 Question/Réponse"):
            question = st.text_input("Question:", key="qa")
            
            if st.button("Questionner", key="qa_btn"):
                if question:
                    with st.spinner("Génération..."):
                        response = balthazar_query_corpus(question, current_project)
                        st.markdown("### 💡 Réponse")
                        st.write(response)

# === PAGE PROJETS ===
elif page == "📁 Projets":
    st.title("📁 Projets")
    
    projects = balthazar_list_projects()
    
    if not projects:
        st.info("Aucun projet")
    else:
        st.write(f"**{len(projects)} projet(s)**")
        
        for p in projects:
            is_current = current_project and p['balthazar_file'] == current_project['balthazar_file']
            
            with st.expander(
                f"📁 {p['name']}" + (" ✅" if is_current else ""),
                expanded=is_current
            ):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write(f"**Fichier:** `{p['balthazar_file']}`")
                    st.write(f"**Dossier:** `{p['folder_path']}`")
                    if p.get('description'):
                        st.write(f"**Description:** {p['description']}")
                    
                    file_size = os.path.getsize(p['balthazar_file']) / (1024 * 1024)
                    st.metric("Taille", f"{file_size:.1f} MB")
                
                with col2:
                    if not is_current:
                        if st.button("✅ Ouvrir", key=f"open_{p['balthazar_file']}", use_container_width=True):
                            if current_project:
                                balthazar_close_project(current_project)
                            st.session_state.current_project = balthazar_open_project(p['balthazar_file'])
                            balthazar_set_current_project(p['balthazar_file'])
                            st.session_state.balthazar_indexed = False
                            st.rerun()
                    
                    if st.button("📥 Exporter", key=f"export_{p['balthazar_file']}", use_container_width=True):
                        export_name = f"{p['name']}_export_{datetime.now().strftime('%Y%m%d')}.balthazar"
                        
                        # Si c'est le projet actuel, sauvegarde d'abord
                        if is_current:
                            balthazar_save_project(current_project)
                        
                        with open(p['balthazar_file'], 'rb') as f:
                            st.download_button(
                                "⬇️ Télécharger",
                                f,
                                file_name=export_name,
                                mime="application/zip",
                                use_container_width=True
                            )
                    
                    if st.button("🗑️ Supprimer", key=f"del_{p['balthazar_file']}", use_container_width=True):
                        if balthazar_delete_project(p['balthazar_file']):
                            if is_current:
                                st.session_state.current_project = None
                            st.rerun()
    
    st.divider()
    
    # Import
    st.subheader("📥 Importer un projet")
    uploaded = st.file_uploader("Fichier .balthazar", type=['balthazar'])
    
    if uploaded:
        import shutil
        temp_path = f"temp_{uploaded.name}"
        with open(temp_path, 'wb') as f:
            f.write(uploaded.getbuffer())
        
        # Copie dans workspace
        from config import BALTHAZAR_PROJECTS_DIR
        from projects import balthazar_init_workspace
        balthazar_init_workspace()
        
        dest_path = os.path.join(BALTHAZAR_PROJECTS_DIR, uploaded.name)
        shutil.move(temp_path, dest_path)
        
        st.success(f"✅ Projet importé: {uploaded.name}")
        st.rerun()
    
    if st.button("➕ Nouveau projet", use_container_width=True):
        st.session_state.show_new_project = True
        st.rerun()

# === PAGE ADMIN ===
elif page == "⚙️ Admin":
    st.title("⚙️ Administration")
    
    if current_project:
        st.info(f"📁 {current_project['name']}")
        
        st.subheader("🔄 Mise à jour")
        if st.button("🔄 Mettre à jour", type="primary", use_container_width=True):
            milvus_store = balthazar_get_milvus_store(project_config=current_project)
            errors, total, stats = balthazar_incremental_ingest(
                current_project['folder_path'],
                milvus_store,
                project_config=current_project
            )
            
            if total > 0:
                st.success(f"✅ {stats['added']} nouveau(x), {stats['updated']} modifié(s)")
                balthazar_save_project(current_project)
            else:
                st.success("✅ À jour")
        
        st.divider()
        
        st.subheader("🗄️ Base")
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Dossier", current_project['folder_path'])
            if os.path.exists(current_project['db_path']):
                size = os.path.getsize(current_project['db_path']) / (1024 * 1024)
                st.metric("Taille", f"{size:.1f} MB")
        
        with col2:
            st.warning("⚠️ Danger")
            if st.button("🗑️ Reset", type="secondary", use_container_width=True):
                if balthazar_reset_database(current_project):
                    st.success("✅ Base supprimée")
                    balthazar_save_project(current_project)
                    st.session_state.balthazar_indexed = False
                    st.rerun()

# === FOOTER ===
st.divider()
st.caption(f"⚡ {BALTHAZAR_NAME} v{BALTHAZAR_VERSION} • Format .balthazar")