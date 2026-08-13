"""Database-backed background jobs.

This package keeps the first worker implementation dependency-free: jobs are
stored in the existing app database, so local mode uses SQLite and production
mode uses Neon/Postgres.
"""
