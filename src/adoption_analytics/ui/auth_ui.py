import streamlit as st
import logging

from adoption_analytics.auth.service import AuthService

logger = logging.getLogger(__name__)

def require_authentication():
    """
    Protège l'accès à l'application.
    Affiche le formulaire de connexion si non authentifié, puis bloque l'exécution.
    Retourne l'utilisateur authentifié (dict) si succès.
    """
    if "authenticated_user" in st.session_state and st.session_state.authenticated_user is not None:
        return st.session_state.authenticated_user

    st.markdown("<br><br><br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            """
            <div style="text-align: center; margin-bottom: 2rem;">
                <h1 style="margin-bottom: 0;">Adoption Analytics</h1>
                <p style="font-size: 1.2rem; font-weight: 500;">Analyse de l'adoption et de l'utilisation des services numériques</p>
                <p style="color: #6C757D; font-size: 0.9rem;">Accès réservé aux équipes IT et managers autorisés.</p>
            </div>
            """, 
            unsafe_allow_html=True
        )

        with st.form("login_form", border=True):
            email = st.text_input("Email professionnel")
            password = st.text_input("Mot de passe", type="password")
            submit_button = st.form_submit_button("Se connecter", use_container_width=True)

            if submit_button:
                try:
                    auth_service = AuthService()
                    user = auth_service.authenticate(email, password)
                    # Sauvegarder uniquement les champs sûrs sous forme de dict
                    st.session_state.authenticated_user = {
                        "id": user.id,
                        "email": user.email,
                        "name": user.name,
                        "role": user.role,
                        "is_admin": user.is_admin
                    }
                    st.rerun()
                except ValueError as e:
                    # Gère "Email ou mot de passe incorrect." et "Ce compte est désactivé..."
                    st.error(str(e))
                except Exception as e:
                    logger.error(f"Erreur technique lors de l'authentification: {e}")
                    st.error("Le service d'authentification est temporairement indisponible.")

    # On stoppe Streamlit pour ne pas charger le dashboard
    st.stop()


def render_sidebar_user_profile(user):
    """
    Affiche le profil utilisateur dans la sidebar et gère la déconnexion.
    """
    st.sidebar.markdown(
        f"""
        <div style="padding: 15px; border-radius: 8px; background-color: #f8f9fa; margin-bottom: 1rem; border: 1px solid #e9ecef;">
            <div style="font-weight: 600; font-size: 1.05rem; color: #212529;">{user.get('name', '')}</div>
            <div style="font-weight: 500; font-size: 0.9rem; color: #495057; margin-top: 2px;">{user.get('role', '')}</div>
            <div style="font-size: 0.8rem; color: #6c757d; margin-top: 2px;">{user.get('email', '')}</div>
        </div>
        """, 
        unsafe_allow_html=True
    )
    
    if st.sidebar.button("Se déconnecter", use_container_width=True):
        # Nettoyage de la session
        keys_to_remove = ["authenticated_user", "assistant_chat_history"]
        for key in keys_to_remove:
            if key in st.session_state:
                del st.session_state[key]
        
        st.rerun()
