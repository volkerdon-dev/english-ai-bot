FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app
COPY static ./static
# Include legacy grammar assets so /legacy/grammar.html works inside the container
COPY grammar.html ./
COPY grammar.js ./
COPY grammar-ui.css ./
COPY grammar-ios.js ./
COPY grammar_categories_tree.json ./
RUN mkdir -p /app/static || true
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "-m", "app.main"]

