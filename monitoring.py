"""
Balthazar - Monitoring et alertes
Métriques Prometheus et alertes email
"""
import smtplib
from prometheus_client import CollectorRegistry, Gauge, start_http_server
import streamlit as st
from config import (
    BALTHAZAR_PROMETHEUS_PORT, 
    BALTHAZAR_SMTP_HOST, 
    BALTHAZAR_SMTP_FROM,
    BALTHAZAR_NAME
)


def balthazar_init_prometheus():
    """
    Balthazar - Initialise les métriques Prometheus
    
    Returns:
        Tuple (batch_success, batch_error, docs_indexed)
    """
    if "balthazar_prom_initialized" not in st.session_state:
        st.session_state.balthazar_prom_registry = CollectorRegistry()
        
        st.session_state.balthazar_batch_success = Gauge(
            'balthazar_batch_success', 
            'Balthazar - Succès des batches', 
            ['batch_id'], 
            registry=st.session_state.balthazar_prom_registry
        )
        
        st.session_state.balthazar_batch_error = Gauge(
            'balthazar_batch_error', 
            'Balthazar - Erreurs des batches', 
            ['batch_id'], 
            registry=st.session_state.balthazar_prom_registry
        )
        
        st.session_state.balthazar_docs_indexed = Gauge(
            'balthazar_docs_indexed', 
            'Balthazar - Documents indexés', 
            registry=st.session_state.balthazar_prom_registry
        )
        
        try:
            start_http_server(
                BALTHAZAR_PROMETHEUS_PORT, 
                registry=st.session_state.balthazar_prom_registry
            )
        except OSError:
            pass  # Port déjà utilisé
        
        st.session_state.balthazar_prom_initialized = True
    
    return (
        st.session_state.balthazar_batch_success,
        st.session_state.balthazar_batch_error,
        st.session_state.balthazar_docs_indexed
    )


def balthazar_send_alert_mail(subject, body, to):
    """
    Balthazar - Envoie une alerte par email
    
    Args:
        subject: Sujet de l'email
        body: Corps de l'email
        to: Destinataire
    """
    if not to:
        return
    
    try:
        s = smtplib.SMTP(BALTHAZAR_SMTP_HOST)
        msg = f"Subject: [{BALTHAZAR_NAME}] {subject}\n\n{body}"
        s.sendmail(BALTHAZAR_SMTP_FROM, to, msg)
        s.quit()
    except Exception as e:
        st.error(f"[{BALTHAZAR_NAME}] ❌ Échec envoi mail: {e}")