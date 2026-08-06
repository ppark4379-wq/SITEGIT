FROM python:3.12-slim
WORKDIR /workspace
COPY backend/requirements.txt /workspace/backend/requirements.txt
RUN pip install --no-cache-dir -r /workspace/backend/requirements.txt
COPY backend /workspace/backend
COPY frontend /workspace/frontend
COPY seed /workspace/seed
COPY policies /workspace/policies
COPY contracts /workspace/contracts
ENV PYTHONPATH=/workspace/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
