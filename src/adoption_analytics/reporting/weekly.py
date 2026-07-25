import pandas as pd

from adoption_analytics.metrics.adoption import compute_adoption_metrics, find_underused_services, compute_usage_rate


def build_weekly_summary(df: pd.DataFrame) -> str:
    if df.empty:
        return "Aucune donnée disponible pour générer la synthèse hebdomadaire."

    metrics = compute_adoption_metrics(df)
    underused = find_underused_services(df)
    top_department = (
        df.groupby("department")["user_id"].nunique().sort_values(ascending=False).head(1).index.tolist()
    )
    least_used_services = ", ".join(underused["service"].head(3).tolist()) or "aucun"

    return (
        f"Cette semaine, {metrics['wau']} utilisateurs uniques ont utilisé les services suivis. "
        f"L'activité mensuelle atteint {metrics['mau']} utilisateurs, avec une fréquence moyenne de "
        f"{metrics['avg_events_per_active_user']:.1f} événements par utilisateur actif. "
        f"Le département le plus actif est {top_department[0] if top_department else 'indéterminé'}. "
        f"Services à surveiller: {least_used_services}."
    )
