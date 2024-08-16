# Dockerfile
# Utiliser une image de base Python
FROM python:slim-bullseye

# Définir le répertoire de travail dans le conteneur
WORKDIR /app

# Copier le fichier requirements.txt et installer les dépendances
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le code source dans le répertoire de travail du conteneur
COPY . .

# Exposer le port que l'application utilisera
EXPOSE 8001

# Commande pour démarrer l'application FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
