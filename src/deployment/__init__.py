import json
import re
import socket
import subprocess
import time


class DeploymentError(RuntimeError):
    pass


class DeploymentService:
    def __init__(self) -> None:
        self._port_forwards: dict[str, subprocess.Popen] = {}

    def deploy(self, project_id: str, image: str, name: str, port: int) -> str:
        namespace = _namespace_name(name, project_id)
        labels = {"app": project_id}

        resources = {
            "apiVersion": "v1",
            "kind": "List",
            "items": [
                {
                    "apiVersion": "v1",
                    "kind": "Namespace",
                    "metadata": {"name": namespace},
                },
                {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "metadata": {"name": "app", "namespace": namespace},
                    "spec": {
                        "replicas": 1,
                        "selector": {"matchLabels": labels},
                        "template": {
                            "metadata": {"labels": labels},
                            "spec": {
                                "containers": [
                                    {
                                        "name": "app",
                                        "image": image,
                                        "imagePullPolicy": "Never",
                                        "ports": [{"containerPort": port}],
                                    }
                                ]
                            },
                        },
                    },
                },
                {
                    "apiVersion": "v1",
                    "kind": "Service",
                    "metadata": {"name": "app", "namespace": namespace},
                    "spec": {
                        "type": "ClusterIP",
                        "selector": labels,
                        "ports": [
                            {
                                "port": port,
                                "targetPort": port,
                                "protocol": "TCP",
                            }
                        ],
                    },
                },
            ],
        }

        self._run(
            ["kubectl", "--context=minikube", "apply", "-f", "-"],
            input=json.dumps(resources),
            timeout=60,
        )

        self._run(
            [
                "kubectl",
                "--context=minikube",
                "rollout",
                "status",
                "deployment/app",
                "--namespace",
                namespace,
                "--timeout=180s",
            ],
            timeout=190,
        )

        self.stop_port_forward(project_id)

        local_port = self._find_free_port()

        command = [
            "kubectl",
            "--context=minikube",
            "port-forward",
            f"service/app",
            f"{local_port}:{port}",
            "--namespace",
            namespace,
        ]

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError as exc:
            raise DeploymentError(
                "kubectl is not installed or is not available on PATH."
            ) from exc

        self._port_forwards[project_id] = process

        # Wait briefly for kubectl to establish the forwarding listener.
        deadline = time.monotonic() + 10

        while time.monotonic() < deadline:
            if process.poll() is not None:
                stderr = process.stderr.read() if process.stderr else ""
                self._port_forwards.pop(project_id, None)
                raise DeploymentError(
                    f"kubectl port-forward failed: {stderr.strip()}"
                )

            try:
                with socket.create_connection(
                    ("127.0.0.1", local_port), timeout=0.2
                ):
                    return f"http://localhost:{local_port}"
            except OSError:
                time.sleep(0.1)

        self.stop_port_forward(project_id)
        raise DeploymentError(
            f"Port forwarding did not start on localhost:{local_port}."
        )

    def stop_port_forward(self, project_id: str) -> None:
        process = self._port_forwards.pop(project_id, None)

        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

        if process is not None and process.stderr is not None:
            process.stderr.close()

    @staticmethod
    def _find_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    @staticmethod
    def _run(
        command: list[str],
        *,
        timeout: int,
        input: str | None = None,
    ) -> str:
        try:
            result = subprocess.run(
                command,
                input=input,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise DeploymentError(
                f"{command[0]} is not installed or is not available on PATH."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise DeploymentError(
                f"Command {' '.join(command)} exceeded the {timeout}-second time limit."
            ) from exc

        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip()
            raise DeploymentError(
                f"Command {' '.join(command)} failed: {detail}"
            )

        return result.stdout


def _namespace_name(name: str, project_id: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)[:40].strip("-") or "project"
    return f"{slug}-{project_id[:8]}"
