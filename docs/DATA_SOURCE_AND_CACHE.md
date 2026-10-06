# Data Source and Cache Notes

The original research scripts used Fonturkey/TEFAS-style public endpoints for Turkish pension fund general information and allocation data.

The public repo version separates this into:

- `turkeyfundlens.data.tefas_client`: API fetching
- `turkeyfundlens.storage.sqlite_store`: optional SQLite cache
- `turkeyfundlens.core.engine`: analytics engine working from DataFrames

SQLite is recommended for repeated analysis, but it is not mandatory.
