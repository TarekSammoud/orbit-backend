# Minikube deployment POC

A small FastAPI API that deploys a Git repository to a local Minikube
cluster. `POST /projects` clones the repository, builds its root-level
`Dockerfile` into Minikube's image store, deploys one container behind a
Kubernetes NodePort Service, waits for the deployment to become ready, and
returns its address.

This is a synchronous local proof of concept: the request remains open while
the image is built and the app starts. It does not use a registry, database,
Ingress, or persistent project storage.

## Requirements

Run the API and these tools from the same WSL distribution:

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Git
- Docker Engine
- Minikube and kubectl

Start Docker, then start Minikube and the API from the repository root:

```bash
minikube start --driver=docker
uv sync
PYTHONPATH=src/main:src uv run uvicorn main.main:app --host 0.0.0.0 --port 8000
```

The API documentation is available at `http://localhost:8000/docs`.

## Deploy a project

The Git repository must contain a `Dockerfile` at its root. The app is assumed
to listen on port `8000`; pass `port` if it listens on a different port.

```bash
curl -X POST http://localhost:8000/projects \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "demo",
    "repository_url": "https://github.com/your-user/your-fastapi-demo",
    "port": 8000
  }'
```

On success, the API returns HTTP `201` with `status: "READY"` and a `url`, for
example:

```json
{
  "id": "a1b2c3d4e5f6478899aabbccddeeff00",
  "name": "demo",
  "repository_url": "https://github.com/your-user/your-fastapi-demo",
  "status": "READY",
  "url": "http://192.168.49.2:31234",
  "image": "poc-project:a1b2c3d4e5f6478899aabbccddeeff00"
}
```

Open the returned URL from WSL to access the deployed app. Build, clone, and
Kubernetes errors are returned as HTTP `502` details.

## Example app

[`examples/fastapi-demo/`](examples/fastapi-demo/) contains the small FastAPI
app and Dockerfile used by this POC. Publish that directory as its own Git
repository, then use that repository URL in the request above.