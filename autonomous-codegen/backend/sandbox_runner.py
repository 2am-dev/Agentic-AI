"""
Sandbox execution using Docker
All code runs inside an isolated container
"""
import docker
import os
import asyncio
import uuid
import tarfile
import io
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "codegen-sandbox")
WORKSPACE_PATH = os.getenv("WORKSPACE_PATH", "/workspace")

# Docker client
try:
    docker_client = docker.from_env()
    logger.info("Docker client initialized")
except Exception as e:
    logger.error(f"Docker init failed: {e}")
    docker_client = None


class SandboxRunner:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.workspace = Path(WORKSPACE_PATH) / session_id
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.container_workspace = "/sandbox/workspace"

    def _get_container_config(self, network_enabled: bool = False):
        """Get Docker container configuration"""
        config = {
            "image": SANDBOX_IMAGE,
            "working_dir": self.container_workspace,
            "volumes": {
                str(self.workspace): {
                    "bind": self.container_workspace,
                    "mode": "rw"
                }
            },
            "mem_limit": "512m",
            "cpu_period": 100000,
            "cpu_quota": 50000,  # 50% CPU
            "pids_limit": 50,
            "security_opt": ["no-new-privileges:true"],
            "read_only": False,
            "remove": True,
            "stdout": True,
            "stderr": True,
        }

        if not network_enabled:
            config["network_mode"] = "none"
        
        return config

    async def execute_code(
        self,
        code: str,
        language: str = "python",
        timeout: int = 30,
        network_enabled: bool = False
    ) -> dict:
        """Execute code in sandbox"""
        if not docker_client:
            return {"success": False, "error": "Docker not available"}

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._run_code_sync,
                code, language, timeout, network_enabled
            )
            return result
        except Exception as e:
            logger.error(f"Sandbox execution error: {e}")
            return {"success": False, "error": str(e)}

    def _run_code_sync(
        self,
        code: str,
        language: str,
        timeout: int,
        network_enabled: bool
    ) -> dict:
        """Synchronous code execution"""
        # Build command based on language
        if language == "python":
            # Write to temp file to handle multiline
            temp_file = f"_temp_{uuid.uuid4().hex[:8]}.py"
            (self.workspace / temp_file).write_text(code)
            cmd = f"python {temp_file}"
            cleanup = temp_file
        elif language == "javascript":
            temp_file = f"_temp_{uuid.uuid4().hex[:8]}.js"
            (self.workspace / temp_file).write_text(code)
            cmd = f"node {temp_file}"
            cleanup = temp_file
        elif language == "bash":
            temp_file = f"_temp_{uuid.uuid4().hex[:8]}.sh"
            (self.workspace / temp_file).write_text(code)
            cmd = f"bash {temp_file}"
            cleanup = temp_file
        else:
            return {"success": False, "error": f"Unsupported language: {language}"}

        try:
            config = self._get_container_config(network_enabled)

            result = docker_client.containers.run(
                command=f"/bin/bash -c '{cmd}'",
                timeout=timeout,
                **config
            )

            output = result.decode("utf-8") if isinstance(result, bytes) else str(result)

            # Cleanup temp file
            try:
                (self.workspace / cleanup).unlink()
            except Exception:
                pass

            return {
                "success": True,
                "output": output,
                "language": language
            }

        except docker.errors.ContainerError as e:
            stderr = e.stderr.decode("utf-8") if e.stderr else str(e)
            try:
                (self.workspace / cleanup).unlink()
            except Exception:
                pass
            return {
                "success": False,
                "error": stderr,
                "exit_code": e.exit_status
            }
        except docker.errors.APIError as e:
            return {"success": False, "error": f"Docker API error: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def execute_file(self, filename: str, args: str = "") -> dict:
        """Execute an existing file in sandbox"""
        filepath = self.workspace / filename
        if not filepath.exists():
            return {"success": False, "error": f"File not found: {filename}"}

        ext = filepath.suffix.lower()
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".sh": "bash",
            ".ts": "javascript"  # Would need ts-node
        }

        language = lang_map.get(ext, "bash")
        code = filepath.read_text()
        return await self.execute_code(code, language)

    async def install_package(self, package: str) -> dict:
        """Install a Python package in the sandbox"""
        if not docker_client:
            return {"success": False, "error": "Docker not available"}

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._install_package_sync,
                package
            )
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _install_package_sync(self, package: str) -> dict:
        """Synchronous package installation"""
        try:
            # Allow network for installation
            config = self._get_container_config(network_enabled=True)
            
            result = docker_client.containers.run(
                command=f"pip install --quiet {package}",
                timeout=60,
                **config
            )

            output = result.decode("utf-8") if isinstance(result, bytes) else str(result)
            return {
                "success": True,
                "message": f"Installed {package}",
                "output": output
            }
        except docker.errors.ContainerError as e:
            stderr = e.stderr.decode("utf-8") if e.stderr else str(e)
            return {"success": False, "error": stderr}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write_file(self, filename: str, content: str) -> dict:
        """Write a file to the workspace"""
        try:
            filepath = self.workspace / filename
            # Create parent dirs if needed
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content, encoding="utf-8")
            return {
                "success": True,
                "message": f"Written: {filename}",
                "size": len(content)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def read_file(self, filename: str) -> dict:
        """Read a file from the workspace"""
        try:
            filepath = self.workspace / filename
            if not filepath.exists():
                return {"success": False, "error": f"File not found: {filename}"}
            content = filepath.read_text(encoding="utf-8")
            return {
                "success": True,
                "filename": filename,
                "content": content
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_files(self) -> dict:
        """List all files in workspace"""
        try:
            files = []
            for f in self.workspace.rglob("*"):
                if f.is_file() and not f.name.startswith("_temp_"):
                    rel_path = f.relative_to(self.workspace)
                    files.append({
                        "name": str(rel_path),
                        "size": f.stat().st_size
                    })
            return {"success": True, "files": files}
        except Exception as e:
            return {"success": False, "error": str(e)}
