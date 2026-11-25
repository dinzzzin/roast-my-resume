FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HF_HOME=/srv/models

# CPU-only PyTorch first: the default PyPI build on Intel machines pulls ~2 GB of
# NVIDIA CUDA libraries we never use. Its own layer, so it is cached across rebuilds.
RUN pip install --no-cache-dir torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data

# Download the embedding model and build the FAISS indexes into the image,
# so the running container never needs the network for RAG.
RUN python -m app.rag.build_index
ENV HF_HUB_OFFLINE=1

EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
