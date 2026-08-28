import streamlit as st
from adoption_analytics.auth.user_management import UserManagementService
from datetime import datetime

def render_settings_page(current_user: dict):
    st.markdown("<p style='color: #6C757D; margin-bottom: 2rem;'>Gérez les comptes autorisés à accéder à Adoption Analytics.</p>", unsafe_allow_html=True)

    service = UserManagementService()

    st.subheader("Gestion des accès")

    users = service.list_users()

    if users:
        # En-tête de la table
        h1, h2, h3, h4, h5 = st.columns([2, 3, 2, 2, 2])
        h1.markdown("**Nom & Rôle**")
        h2.markdown("**Email**")
        h3.markdown("**Créé le**")
        h4.markdown("**Statut**")
        h5.markdown("**Action**")
        st.divider()

        for user in users:
            is_current = user.id == current_user.get("id")
            created_str = user.created_at.strftime("%d/%m/%Y") if isinstance(user.created_at, datetime) else str(user.created_at)

            c1, c2, c3, c4, c5 = st.columns([2, 3, 2, 2, 2])
            with c1:
                admin_text = " (Admin)" if user.is_admin else ""
                st.markdown(f"{user.name}<br/><small style='color:#6c757d;'>{user.role}{admin_text}</small>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<span style='font-size: 0.9rem;'>{user.email}</span>", unsafe_allow_html=True)
            with c3:
                st.markdown(f"<span style='font-size: 0.9rem;'>{created_str}</span>", unsafe_allow_html=True)
            with c4:
                if user.is_active:
                    st.markdown("<span style='color: #198754; font-weight: 500; font-size: 0.9rem;'>Actif</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<span style='color: #dc3545; font-weight: 500; font-size: 0.9rem;'>Désactivé</span>", unsafe_allow_html=True)
            with c5:
                if is_current:
                    st.caption("Session actuelle")
                elif user.is_active:
                    if st.button("Désactiver", key=f"deactivate_{user.id}"):
                        try:
                            service.deactivate_user(user.id, current_user.get("id"))
                            st.rerun()
                        except ValueError as ve:
                            st.error(str(ve))
                        except Exception:
                            st.error("Une erreur technique est survenue lors de la gestion des utilisateurs.")
                else:
                    if st.button("Réactiver", key=f"activate_{user.id}"):
                        try:
                            service.activate_user(user.id)
                            st.rerun()
                        except ValueError as ve:
                            st.error(str(ve))
                        except Exception:
                            st.error("Une erreur technique est survenue lors de la gestion des utilisateurs.")
            st.markdown("<hr style='margin: 0.5rem 0; opacity: 0.5;'/>", unsafe_allow_html=True)

    st.markdown("<br/>", unsafe_allow_html=True)
    st.subheader("Ajouter un utilisateur")

    with st.form("add_user_form", border=True):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Nom complet")
            role = st.selectbox("Rôle", ["IT", "Manager"])
        with c2:
            email = st.text_input("Email professionnel")

        st.markdown("<br/>", unsafe_allow_html=True)
        c3, c4 = st.columns(2)
        with c3:
            password = st.text_input("Mot de passe initial", type="password")
        with c4:
            confirm_password = st.text_input("Confirmer le mot de passe", type="password")

        st.markdown("<br/>", unsafe_allow_html=True)
        submitted = st.form_submit_button("Ajouter l'utilisateur")

        if submitted:
            if password != confirm_password:
                st.error("Les mots de passe ne correspondent pas.")
            else:
                try:
                    service.create_user(
                        email=email,
                        name=name,
                        password=password,
                        role=role
                    )
                    st.success("Utilisateur ajouté avec succès.")
                    st.rerun()
                except ValueError as ve:
                    st.error(str(ve))
                except Exception:
                    st.error("Une erreur technique est survenue lors de la gestion des utilisateurs.")
