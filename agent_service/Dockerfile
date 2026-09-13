FROM hermes-agent:local

WORKDIR /workspace

# Install Sovereign AI Platform dependencies: in-process vector engine, schemas & tooling
COPY requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r /workspace/requirements.txt

CMD ["gateway"]
