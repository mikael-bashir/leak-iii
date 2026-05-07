# 1. Base Image
FROM ubuntu:22.04

# 2. CREATE THE GUEST USER (Required for Hugging Face Spaces permissions)
RUN useradd -m -u 1000 user

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

# 3. Install System Dependencies
# cmake and build-essential are CRITICAL for compiling llama-cpp-python 
RUN apt-get update && apt-get install -y \
    curl git build-essential python3 python3-pip python3-venv cmake tzdata && \
    rm -rf /var/lib/apt/lists/*

# 4. Switch to the unprivileged user
USER user
ENV HOME=/home/user
# Put uv in the PATH
ENV PATH="${HOME}/.local/bin:${PATH}"

# 5. Install Python package manager (uv)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# 6. Setup Workspace & Copy Files
WORKDIR ${HOME}/app
COPY --chown=user . ${HOME}/app

# 7. Setup Python Virtual Environment
# Create a venv directly in the app folder and add it to the PATH
RUN uv python install 3.11
RUN uv venv --python 3.11 ${HOME}/app/.venv
ENV PATH="${HOME}/app/.venv/bin:${PATH}"

# 8. Install Leak-III Dependencies
RUN uv pip install mcp huggingface-hub llama-cpp-python starlette uvicorn nest-asyncio typing

# 9. Environment Variables
EXPOSE 7860

# 10. Boot the server using the virtual environment
# Ensure your python script is named 'app.py' (or change this to match your filename)
CMD ["python3", "app.py"]