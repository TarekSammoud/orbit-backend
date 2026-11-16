from fastapi import FastAPI, HTTPException, status

from build.docker import ImageBuildError
from build.git import GitCloneError
from deployment import DeploymentError
from main.project_service import create_project
from shared.schemas.models import CreateProjectRequest, ProjectResponse

app = FastAPI(title="Minikube POC")


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Minikube POC API"}


@app.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_endpoint(project: CreateProjectRequest) -> ProjectResponse:
    try:
        return create_project(project)
    except (GitCloneError, ImageBuildError, DeploymentError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc