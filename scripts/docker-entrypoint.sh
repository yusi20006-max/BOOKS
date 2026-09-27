#!/bin/sh
set -eu

python -c 'from books.config import load_settings; from books.db import Database; s=load_settings(); Database(s.db_path).migrate()'
exec streamlit run src/books/app.py --server.address "$BOOKS_HOST" --server.port "$BOOKS_PORT" --server.headless true
