# UM6P data sources

This folder contains source-specific landing zones for the modular analytics platform.

- `learning_center/`: expected files are `daily-kpis.csv`, `nginx-events.csv`, and `top-routes.csv`.
- `booking/`: placeholder for the future Booking source once access is granted.

The app also supports the current external Learning Center path:

```text
C:\Users\PC\adoption-assistant\data\um6p\learning_center
```

To override it, set the `LEARNING_CENTER_DATA_DIR` environment variable.
