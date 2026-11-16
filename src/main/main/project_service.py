
from uuid import uuid4

from build.service import BuildService
from deployment import DeploymentService
from shared.schemas.models import CreateProjectRequest


def create_project(project: CreateProjectRequest) -> dict[str, str]:
    project_id = uuid4().hex
    image = BuildService().build(project.repository_url, project_id)
    url = DeploymentService().deploy(
        project_id=project_id,
        image=image,
        name=project.name,
        port=project.port,
    )
    return {
        "id": project_id,
        "name": project.name,
        "repository_url": project.repository_url,
        "status": "READY",
        "url": url,
        "image": image,
    }