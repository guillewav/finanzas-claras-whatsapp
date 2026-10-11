FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir "llama-stack[starter]==0.7.3" "mcp<2.0" pyyaml
COPY docker/llama_stack_entrypoint.py .
EXPOSE 8321
CMD ["python", "llama_stack_entrypoint.py"]
