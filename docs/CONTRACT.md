# CONTRACT.md

# PaaS Clone --- Technical Contract

> **Current implementation scope:** the code in this repository is an
> intentionally smaller local POC than the target architecture described
> below. It clones a repository, builds its root-level `Dockerfile` directly
> into Minikube, deploys a single app container with a NodePort Service, and
> returns the Minikube IP and allocated port after the rollout is ready. It
> does not currently provide a registry, PostgreSQL, Ingress, persistence,
> or asynchronous project statuses. See the root README for the runnable
> setup and API contract.

## 1. Purpose

This document defines the technical contract for the PaaS proof of
concept.

The goal is to provide a very small Railway-like platform:

> A user provides a Git repository containing a Dockerized backend. The
> platform builds the Docker image, pushes it to a registry, deploys the
> application on Kubernetes together with a PostgreSQL database, and
> returns a public URL.

The POC is intentionally implemented as a **modular monolith**, not as
several microservices.

The main modules are:

``` text
main/
build/
deployment/
shared/
```

Infrastructure required by the PaaS is kept separately:

``` text
infra/
├── docker-compose.yml
└── kubernetes/
```

------------------------------------------------------------------------

# 2. Architecture

``` text
                         ┌─────────────────┐
                         │    Frontend     │
                         │ React + TS      │
                         └────────┬────────┘
                                  │ HTTP
                                  ▼
                         ┌─────────────────┐
                         │      Main       │
                         │   FastAPI/API   │
                         └────────┬────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
             ┌─────────────┐             ┌──────────────┐
             │    Build    │             │  Deployment  │
             │   module    │             │    module    │
             └──────┬──────┘             └───────┬──────┘
                    │                              │
                    ▼                              ▼
             Docker Registry                  Kubernetes
                                                   │
                                      ┌────────────┴────────────┐
                                      │                         │
                                      ▼                         ▼
                                   Backend                  PostgreSQL
```

The modules communicate through **internal Python interfaces / function
calls**.

For the POC, we do not introduce HTTP or MQTT communication between
these modules.

This keeps the architecture simple while preserving clear boundaries so
that modules can later be extracted into microservices if necessary.

------------------------------------------------------------------------

# 3. Repository structure

Recommended structure:

``` text
paas/
├── main/
│   ├── api.py
│   ├── project_service.py
│   └── ...
│
├── build/
│   ├── service.py
│   ├── git.py
│   ├── docker.py
│   └── ...
│
├── deployment/
│   ├── service.py
│   ├── kubernetes.py
│   └── ...
│
├── shared/
│   ├── models.py
│   └── ...
│
├── infra/
│   ├── docker-compose.yml
│   └── kubernetes/
│
└── CONTRACT.md
```

## Responsibilities

### `main/`

Responsible for:

-   HTTP API
-   project creation
-   project status
-   orchestration
-   persistence of PaaS project state

`main` is the entry point of the application.

It calls `BuildService` and `DeploymentService`.

------------------------------------------------------------------------

### `build/`

Responsible for:

-   cloning the Git repository
-   validating the repository
-   building the Docker image
-   tagging the image
-   pushing the image to the registry
-   returning the resulting image reference

The POC assumes that the repository already contains a valid
`Dockerfile`.

Automatic framework/language detection is out of scope.

------------------------------------------------------------------------

### `deployment/`

Responsible for:

-   creating the Kubernetes namespace
-   creating PostgreSQL
-   creating the backend Deployment
-   creating Kubernetes Services
-   creating the application Secret
-   creating the Ingress
-   injecting `DATABASE_URL`
-   waiting for the application to become ready
-   returning the public URL

------------------------------------------------------------------------

### `shared/`

Contains models and types shared between modules.

Examples:

-   `Project`
-   `BuildResult`
-   `DeploymentResult`
-   status enums
-   shared exceptions

`shared/` must remain small.

------------------------------------------------------------------------

### `infra/`

Contains infrastructure required to run the PaaS itself.

Example:

``` text
infra/
├── docker-compose.yml
└── kubernetes/
```

The infrastructure is **not application logic**.

For example:

-   PostgreSQL for the PaaS database
-   Docker Registry
-   MQTT broker, if MQTT is later needed
-   Kubernetes configuration

The registry itself is not a PaaS microservice that we develop.

------------------------------------------------------------------------

# 4. End-to-end workflow

The main POC workflow is:

``` text
1. User creates a project
        ↓
2. Main creates project with status QUEUED
        ↓
3. BuildService.build()
        ↓
4. Git clone
        ↓
5. docker build
        ↓
6. docker push
        ↓
7. BuildResult
        ↓
8. DeploymentService.deploy()
        ↓
9. Create Kubernetes namespace
        ↓
10. Create PostgreSQL
        ↓
11. Create backend Deployment
        ↓
12. Create backend Service
        ↓
13. Create Ingress
        ↓
14. Wait for backend to be ready
        ↓
15. DeploymentResult
        ↓
16. Main updates project status to READY
        ↓
17. API returns project information + URL
```

------------------------------------------------------------------------

# 5. Project API

## `POST /projects`

Creates a new project and starts the deployment workflow.

### Input

``` json
{
  "name": "my-app",
  "repository_url": "https://github.com/user/my-app"
}
```

### Input fields

  --------------------------------------------------------------------------
  Field              Type                          Required Description
  ------------------ ---------------- --------------------- ----------------
  `name`             string                             yes Project name

  `repository_url`   string                             yes Git repository
                                                            containing the
                                                            Dockerfile
  --------------------------------------------------------------------------

### Example

``` bash
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-app",
    "repository_url": "https://github.com/user/my-app"
  }'
```

### Output

``` json
{
  "id": "abc123",
  "name": "my-app",
  "repository_url": "https://github.com/user/my-app",
  "status": "QUEUED",
  "url": null,
  "image": null,
  "error": null
}
```

HTTP status:

``` text
201 Created
```

The workflow may continue asynchronously after the project has been
created.

------------------------------------------------------------------------

# 6. Project status

The project status must use the following values:

``` text
QUEUED
BUILDING
DEPLOYING
STARTING
READY
FAILED
```

### State flow

``` text
QUEUED
   ↓
BUILDING
   ↓
DEPLOYING
   ↓
STARTING
   ↓
READY
```

Any stage can result in:

``` text
FAILED
```

Example:

``` text
QUEUED → BUILDING → FAILED
```

------------------------------------------------------------------------

# 7. Project output model

A project is represented as:

``` json
{
  "id": "abc123",
  "name": "my-app",
  "repository_url": "https://github.com/user/my-app",
  "status": "READY",
  "url": "https://abc123.paas.local",
  "image": "registry.local:5000/my-app:abc123",
  "error": null
}
```

### Fields

  Field              Type          Description
  ------------------ ------------- ------------------------------------
  `id`               string        Unique project identifier
  `name`             string        Project name
  `repository_url`   string        Source Git repository
  `status`           enum          Current project status
  `url`              string/null   Public application URL
  `image`            string/null   Built Docker image
  `error`            string/null   Error message if deployment failed

------------------------------------------------------------------------

# 8. Build contract

`main` must interact with the build module through a clean internal
interface.

Example:

``` python
class BuildService:
    def build(
        self,
        repository_url: str,
        project_id: str
    ) -> BuildResult:
        ...
```

The build module must not know about HTTP requests or frontend logic.

------------------------------------------------------------------------

## Build input

Conceptually:

``` json
{
  "project_id": "abc123",
  "repository_url": "https://github.com/user/my-app"
}
```

------------------------------------------------------------------------

## Build output

``` json
{
  "image": "registry.local:5000/my-app:abc123"
}
```

Represented internally by:

``` python
@dataclass
class BuildResult:
    image: str
```

------------------------------------------------------------------------

# 9. Build process

The build module performs:

``` text
repository_url
      ↓
git clone
      ↓
validate Dockerfile
      ↓
docker build
      ↓
tag image
      ↓
docker push
      ↓
image reference
```

Example image:

``` text
registry.local:5000/my-app:abc123
```

The image naming convention is:

``` text
<registry>/<project-name>:<project-id>
```

This guarantees that each project has a unique image tag.

------------------------------------------------------------------------

# 10. Deployment contract

`main` must interact with the deployment module through:

``` python
class DeploymentService:
    def deploy(
        self,
        project_id: str,
        image: str
    ) -> DeploymentResult:
        ...
```

------------------------------------------------------------------------

## Deployment input

Conceptually:

``` json
{
  "project_id": "abc123",
  "image": "registry.local:5000/my-app:abc123"
}
```

------------------------------------------------------------------------

## Deployment output

``` json
{
  "url": "https://abc123.paas.local",
  "status": "READY"
}
```

Represented internally by:

``` python
@dataclass
class DeploymentResult:
    url: str
    status: str
```

------------------------------------------------------------------------

# 11. Kubernetes deployment

Each project receives its own Kubernetes namespace.

For project:

``` text
abc123
```

the namespace is:

``` text
project-abc123
```

The namespace contains:

``` text
project-abc123
│
├── backend Deployment
├── backend Service
├── postgres Deployment
├── postgres Service
├── Secret
└── Ingress
```

------------------------------------------------------------------------

# 12. PostgreSQL contract

Every deployed project receives its own PostgreSQL instance.

Example:

``` text
project-abc123
│
├── backend
│
└── postgres
```

The PostgreSQL Service is named:

``` text
postgres
```

Because Kubernetes DNS works inside the namespace, the backend can
connect to:

``` text
postgres:5432
```

The backend receives a `DATABASE_URL` environment variable.

Example:

``` text
postgresql://user:password@postgres:5432/app
```

The exact credentials are implementation details and must not be
returned by the public API.

------------------------------------------------------------------------

# 13. Kubernetes backend configuration

The backend Deployment uses the image produced by the Build module.

Example:

``` json
{
  "project_id": "abc123",
  "image": "registry.local:5000/my-app:abc123",
  "database": {
    "host": "postgres",
    "port": 5432
  }
}
```

Internally, this results in Kubernetes resources equivalent to:

``` text
Deployment:
    image = registry.local:5000/my-app:abc123

Environment:
    DATABASE_URL = postgresql://...

Service:
    backend:8000

Ingress:
    abc123.paas.local
```

------------------------------------------------------------------------

# 14. Public URL

The public URL convention is:

``` text
https://<project-id>.paas.local
```

Example:

``` text
https://abc123.paas.local
```

The exact domain can change depending on the local Kubernetes
environment.

The important contract is that `DeploymentService` returns the final
URL:

``` json
{
  "url": "https://abc123.paas.local",
  "status": "READY"
}
```

------------------------------------------------------------------------

# 15. Project status API

## `GET /projects/{project_id}`

Returns the current state of a project.

### Example

``` http
GET /projects/abc123
```

### Output

``` json
{
  "id": "abc123",
  "name": "my-app",
  "repository_url": "https://github.com/user/my-app",
  "status": "READY",
  "url": "https://abc123.paas.local",
  "image": "registry.local:5000/my-app:abc123",
  "error": null
}
```

------------------------------------------------------------------------

# 16. Failed project

If a build or deployment fails:

``` json
{
  "id": "abc123",
  "name": "my-app",
  "repository_url": "https://github.com/user/my-app",
  "status": "FAILED",
  "url": null,
  "image": null,
  "error": "Docker build failed"
}
```

The error should be useful enough for the frontend to display a
meaningful message.

Sensitive information such as passwords, tokens or private credentials
must not be exposed.

------------------------------------------------------------------------

# 17. HTTP errors

Recommended API errors:

### `400 Bad Request`

Invalid request data.

``` json
{
  "detail": "Invalid project name"
}
```

### `404 Not Found`

Project does not exist.

``` json
{
  "detail": "Project abc123 not found"
}
```

### `422 Unprocessable Entity`

Invalid request schema.

``` json
{
  "detail": [
    {
      "loc": ["body", "repository_url"],
      "msg": "Invalid URL",
      "type": "value_error"
    }
  ]
}
```

### `500 Internal Server Error`

Unexpected platform error.

``` json
{
  "detail": "Internal platform error"
}
```

------------------------------------------------------------------------

# 18. Internal orchestration contract

The main module orchestrates the workflow.

Conceptually:

``` python
project = project_service.create_project(
    name=request.name,
    repository_url=request.repository_url
)

project.status = "BUILDING"

build_result = build_service.build(
    repository_url=project.repository_url,
    project_id=project.id
)

project.image = build_result.image
project.status = "DEPLOYING"

deployment_result = deployment_service.deploy(
    project_id=project.id,
    image=build_result.image
)

project.url = deployment_result.url
project.status = "READY"
```

If an exception occurs:

``` python
project.status = "FAILED"
project.error = str(error)
```

------------------------------------------------------------------------

# 19. Infrastructure

Infrastructure required for the POC is kept under:

``` text
infra/
```

Recommended initial structure:

``` text
infra/
├── docker-compose.yml
└── kubernetes/
```

## Local infrastructure

`docker-compose.yml` can run infrastructure services such as:

``` text
PostgreSQL
Docker Registry
Mosquitto (optional)
```

Example:

``` text
┌──────────────────────────────────┐
│         Docker Compose           │
│                                  │
│ PostgreSQL                       │
│ Docker Registry                  │
│ Mosquitto (optional)             │
└──────────────────────────────────┘
```

------------------------------------------------------------------------

# 20. PaaS PostgreSQL vs user PostgreSQL

There are two different PostgreSQL concepts.

## PaaS PostgreSQL

Used by the platform itself.

``` text
infra/
    PostgreSQL
        ↓
projects
deployments
builds
...
```

## User PostgreSQL

Created for each deployed project.

``` text
Kubernetes
└── project-abc123
    ├── backend
    └── postgres
```

They must not be confused.

------------------------------------------------------------------------

# 21. Docker Registry

The Docker Registry stores images produced by the Build module.

Example:

``` text
Build
  │
  │ docker push
  ▼
registry.local:5000
  │
  └── my-app:abc123
```

Kubernetes later pulls:

``` text
registry.local:5000/my-app:abc123
```

The registry is infrastructure.

We do not implement a custom registry service.

------------------------------------------------------------------------

# 22. MQTT

MQTT is **not required for the initial POC architecture**.

The modular monolith should use direct Python interfaces:

``` text
Main
 │
 ├── BuildService.build()
 │
 └── DeploymentService.deploy()
```

MQTT can be introduced later if the team identifies a real
asynchronous/event-driven requirement.

Potential future topics:

``` text
paas/projects/deploy
paas/projects/status

paas/build/request
paas/build/completed

paas/deployment/request
paas/deployment/completed
```

If the architecture is later extracted into microservices, MQTT can
become one possible communication mechanism:

``` text
                 MQTT
                   │
       ┌───────────┼───────────┐
       ▼           ▼           ▼
     Main        Build     Deployment
      MS           MS          MS
```

The current POC must not depend on this extraction.

------------------------------------------------------------------------

# 23. What is explicitly out of scope

The POC does not initially require:

-   automatic language/framework detection
-   GitHub webhooks
-   custom buildpacks
-   Dockerfile generation
-   horizontal autoscaling
-   multi-node production Kubernetes
-   advanced authentication
-   billing
-   custom domains
-   SSL certificate automation
-   rolling deployments
-   advanced secrets management
-   production-grade observability
-   microservices for Main/Build/Deployment
-   MQTT communication between internal modules

These can be added later if required.

------------------------------------------------------------------------

# 24. Team ownership

The modular structure allows parallel development without creating
separate microservices.

Suggested ownership:

  Team member   Responsibility
  ------------- ----------------------------------------------
  P1            `main/` --- API, projects, orchestration
  P2            `build/` --- Git, Docker build, registry
  P3            `deployment/` --- Kubernetes resources
  P4            `infra/` --- Kubernetes/local infrastructure
  P5            Frontend --- React + TypeScript

All members follow the contracts defined in this document.

------------------------------------------------------------------------

# 25. Definition of Done

The POC is considered successful when the following scenario works:

### Input

``` json
{
  "name": "hello-api",
  "repository_url": "https://github.com/user/hello-api"
}
```

The repository contains:

``` text
hello-api/
└── Dockerfile
```

### Expected workflow

``` text
POST /projects
      ↓
QUEUED
      ↓
BUILDING
      ↓
Docker image created
      ↓
Image pushed to registry
      ↓
DEPLOYING
      ↓
Kubernetes namespace created
      ↓
PostgreSQL created
      ↓
Backend deployed
      ↓
Ingress created
      ↓
STARTING
      ↓
READY
```

### Expected final output

``` json
{
  "id": "abc123",
  "name": "hello-api",
  "repository_url": "https://github.com/user/hello-api",
  "status": "READY",
  "url": "https://abc123.paas.local",
  "image": "registry.local:5000/hello-api:abc123",
  "error": null
}
```

The URL must expose the user's backend.

For example:

``` bash
curl https://abc123.paas.local
```

could return:

``` json
{
  "message": "Hello from my PaaS"
}
```

------------------------------------------------------------------------

# 26. Future microservice extraction

The POC intentionally uses a modular monolith.

Once the boundaries are validated, the modules can be extracted:

``` text
Current:

┌──────────────────────────────┐
│          PaaS App            │
│                              │
│  ┌──────┐ ┌──────┐ ┌──────┐ │
│  │ Main │ │Build │ │Deploy│ │
│  └──────┘ └──────┘ └──────┘ │
└──────────────────────────────┘
```

Potential future architecture:

``` text
             ┌──────────┐
             │ Frontend │
             └────┬─────┘
                  │
                  ▼
             ┌──────────┐
             │ Main API │
             └────┬─────┘
                  │
            ┌─────┴─────┐
            │           │
            ▼           ▼
        ┌───────┐   ┌────────────┐
        │ Build │   │ Deployment │
        │  MS   │   │     MS     │
        └───────┘   └────────────┘
```

The contracts in this document should remain stable enough that this
extraction can happen without redesigning the entire PaaS.

The key principle is:

> **Validate the boundaries first, extract microservices later.**
