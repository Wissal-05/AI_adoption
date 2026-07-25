"""Mécanismes de déduplication idempotents pour le pipeline d'ingestion.

Génère des identifiants d'événements déterministes à partir des données de log
et fournit des outils pour filtrer les doublons déjà persistés dans le stockage.
"""

import hashlib
import pandas as pd


def generate_event_id(row: pd.Series | dict) -> str:
    """Génère un identifiant d'événement déterministe (hash SHA-256) pour une seule ligne.

    Recherche les champs disponibles dans la ligne (qu'elle soit brute ou normalisée)
    et les concatène dans un ordre strict pour produire une signature unique.
    """
    # 1. Extraction et normalisation du timestamp
    ts_val = ""
    for k in ["event_timestamp", "timestamp", "event_time_local", "event_time_utc"]:
        if k in row and pd.notna(row[k]):
            val = row[k]
            if isinstance(val, pd.Timestamp):
                ts_val = val.isoformat()
            else:
                ts_val = str(val)
            break

    # 2. Service / Source
    service_val = ""
    for k in ["service", "app", "source"]:
        if k in row and pd.notna(row[k]):
            service_val = str(row[k])
            break

    # 3. Utilisateur / IP
    user_val = ""
    for k in ["user_id", "visitor_id_approx", "client_ip", "source_ip", "remote_addr"]:
        if k in row and pd.notna(row[k]):
            user_val = str(row[k])
            break

    # 4. Méthode HTTP
    method_val = ""
    if "method" in row and pd.notna(row["method"]):
        method_val = str(row["method"])

    # 5. Route / Path
    route_val = ""
    for k in ["route", "path"]:
        if k in row and pd.notna(row[k]):
            route_val = str(row[k])
            break

    # 6. Status code
    status_val = ""
    for k in ["status_code", "status"]:
        if k in row and pd.notna(row[k]):
            status_val = str(int(float(row[k])))
            break

    # 7. Taille de réponse
    bytes_val = ""
    if "bytes_sent" in row and pd.notna(row["bytes_sent"]):
        bytes_val = str(int(float(row["bytes_sent"])))

    # Concaténation avec un délimiteur pour éviter les collisions par contiguïté
    signature = "|".join([ts_val, service_val, user_val, method_val, route_val, status_val, bytes_val])

    # Hash SHA-256
    return hashlib.sha256(signature.encode("utf-8")).hexdigest()


def generate_event_ids(df: pd.DataFrame) -> pd.Series:
    """Génère des IDs d'événements de manière vectorisée et ultra-rapide (optimisé pandas).

    Évite l'utilisation coûteuse de .apply(..., axis=1) sur les grands DataFrames.
    """
    if df.empty:
        return pd.Series(dtype=str)

    # 1. Timestamp
    if "event_timestamp" in df.columns:
        ts = df["event_timestamp"].astype(str)
    elif "event_time_local" in df.columns:
        ts = df["event_time_local"].astype(str)
    elif "event_time_utc" in df.columns:
        ts = df["event_time_utc"].astype(str)
    elif "timestamp" in df.columns:
        ts = df["timestamp"].astype(str)
    else:
        ts = pd.Series("", index=df.index)

    # 2. Service / Source
    if "service" in df.columns:
        service = df["service"].fillna("").astype(str)
    elif "app" in df.columns:
        service = df["app"].fillna("").astype(str)
    elif "source" in df.columns:
        service = df["source"].fillna("").astype(str)
    else:
        service = pd.Series("", index=df.index)

    # 3. Utilisateur / IP
    if "user_id" in df.columns:
        user = df["user_id"].fillna("").astype(str)
    elif "visitor_id_approx" in df.columns:
        user = df["visitor_id_approx"].fillna("").astype(str)
    elif "client_ip" in df.columns:
        user = df["client_ip"].fillna("").astype(str)
    elif "source_ip" in df.columns:
        user = df["source_ip"].fillna("").astype(str)
    elif "remote_addr" in df.columns:
        user = df["remote_addr"].fillna("").astype(str)
    else:
        user = pd.Series("", index=df.index)

    # 4. Méthode
    method = df["method"].fillna("").astype(str) if "method" in df.columns else pd.Series("", index=df.index)

    # 5. Route / Path
    if "route" in df.columns:
        route = df["route"].fillna("").astype(str)
    elif "path" in df.columns:
        route = df["path"].fillna("").astype(str)
    else:
        route = pd.Series("", index=df.index)

    # 6. Status code
    if "status_code" in df.columns:
        status = df["status_code"].fillna(0).astype(int).astype(str)
    elif "status" in df.columns:
        # Gère les floats éventuels avant cast en int
        status = pd.to_numeric(df["status"], errors="coerce").fillna(0).astype(int).astype(str)
    else:
        status = pd.Series("", index=df.index)

    # 7. Bytes
    if "bytes_sent" in df.columns:
        bytes_col = pd.to_numeric(df["bytes_sent"], errors="coerce").fillna(0).astype(int).astype(str)
    else:
        bytes_col = pd.Series("", index=df.index)

    # Concaténation vectorisée
    signatures = ts + "|" + service + "|" + user + "|" + method + "|" + route + "|" + status + "|" + bytes_col

    # Application du hachage sur la série concaténée (beaucoup plus rapide que axis=1)
    return signatures.apply(lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest())


def deduplicate_events(df: pd.DataFrame, existing_ids: set[str]) -> tuple[pd.DataFrame, int]:
    """Déduplique un DataFrame d'événements.

    Élimine :
      1. Les doublons présents au sein même du lot courant.
      2. Les doublons déjà présents dans le stockage.
    """
    if df.empty:
        return df.copy(), 0

    if "event_id" not in df.columns:
        df = df.copy()
        df["event_id"] = generate_event_ids(df)

    initial_count = len(df)

    # 1. Déduplication interne
    df_clean = df.drop_duplicates(subset=["event_id"], keep="first").copy()

    # 2. Déduplication externe
    df_clean["event_id"] = df_clean["event_id"].astype(str)
    existing_str_ids = {str(eid) for eid in existing_ids}
    df_final = df_clean[~df_clean["event_id"].isin(existing_str_ids)].copy()

    total_ignored = initial_count - len(df_final)

    return df_final, total_ignored
