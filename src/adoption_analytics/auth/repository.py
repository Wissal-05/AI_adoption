import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import psycopg
from psycopg.rows import class_row

from config.settings import settings

@dataclass
class PlatformUser:
    id: int
    email: str
    name: str
    password_hash: str
    role: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime


class PlatformUserRepository:
    """Repository pour gérer les utilisateurs de la plateforme (authentification)."""

    def __init__(self):
        # We fetch credentials dynamically when a connection is needed
        pass
        
    def _get_connection(self):
        host = settings.db_host
        port = settings.db_port
        dbname = settings.db_name
        user = settings.db_user
        password = settings.db_password
        
        return psycopg.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            row_factory=class_row(PlatformUser)
        )

    def get_by_email(self, email: str) -> Optional[PlatformUser]:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM platform_users WHERE LOWER(email) = LOWER(%s)",
                    (email,)
                )
                return cur.fetchone()

    def list_users(self) -> List[PlatformUser]:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM platform_users ORDER BY id")
                return cur.fetchall()

    def create_user(
        self,
        email: str,
        name: str,
        password_hash: str,
        role: str,
        is_active: bool = True,
        is_admin: bool = False
    ) -> PlatformUser:
        
        email = email.strip().lower()
        if role not in {"IT", "Manager"}:
            raise ValueError(f"Rôle invalide : {role}. Doit être 'IT' ou 'Manager'.")
            
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO platform_users 
                        (email, name, password_hash, role, is_active, is_admin) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING *
                        """,
                        (email, name, password_hash, role, is_active, is_admin)
                    )
                    return cur.fetchone()
        except psycopg.errors.UniqueViolation:
            raise ValueError(f"Un compte avec l'email {email} existe déjà.")

    def set_active(self, user_id: int, is_active: bool) -> None:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE platform_users 
                    SET is_active = %s, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = %s
                    """,
                    (is_active, user_id)
                )

    def update_role(self, user_id: int, role: str) -> None:
        if role not in {"IT", "Manager"}:
            raise ValueError(f"Rôle invalide : {role}. Doit être 'IT' ou 'Manager'.")
            
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE platform_users 
                    SET role = %s, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = %s
                    """,
                    (role, user_id)
                )

    def update_admin(self, user_id: int, is_admin: bool) -> None:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE platform_users 
                    SET is_admin = %s, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = %s
                    """,
                    (is_admin, user_id)
                )
