FROM hermes-agent:local

WORKDIR /workspace

# Install Sovereign AI Platform dependencies: in-process vector engine, schemas & tooling
COPY requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r /workspace/requirements.txt && \
    ln -sfn /workspace /agent_service && \
    mkdir -p /usr/local/lib/hermes-agent/venv/lib/python3.11/site-packages && \
    echo "/usr/local/lib/python3.11/site-packages" > /usr/local/lib/hermes-agent/venv/lib/python3.11/site-packages/system_packages.pth

ENV PYTHONSAFEPATH=1
ENV PYTHONPATH=/:/workspace

CMD ["gateway"]
