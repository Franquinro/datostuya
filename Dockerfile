FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar aplicación y datos iniciales
COPY . .

# Puerto por defecto de Coolify
EXPOSE 8080

ENV PORT=8080
ENV DATA_DIR=/app/data
ENV PYTHONUNBUFFERED=1

CMD ["python", "server.py"]
