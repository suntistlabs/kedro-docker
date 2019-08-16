# Copyright 2018-2019 QuantumBlack Visual Analytics Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND
# NONINFRINGEMENT. IN NO EVENT WILL THE LICENSOR OR OTHER CONTRIBUTORS
# BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF, OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# The QuantumBlack Visual Analytics Limited ("QuantumBlack") name and logo
# (either separately or in combination, "QuantumBlack Trademarks") are
# trademarks of QuantumBlack. The License does not grant you any right or
# license to the QuantumBlack Trademarks. You may not use the QuantumBlack
# Trademarks or any confusingly similar mark as a trademark for your product,
#     or use the QuantumBlack Trademarks in any other manner that might cause
# confusion in the marketplace, including but not limited to in advertising,
# on websites, or on software.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Common functions for e2e testing."""

import tempfile
import urllib
import venv
from pathlib import Path
from threading import Thread
from time import sleep, time
from typing import Any, Callable, List

import docker
from kedro.cli.utils import get_pkg_version

PIP_INSTALL_SCRIPT = "https://bootstrap.pypa.io/get-pip.py"


class WaitForException(Exception):
    pass


def wait_for(
    func: Callable,
    expected_result: Any = True,
    timeout_: int = 10,
    print_error: bool = True,
    sleep_for: int = 1,
    **kwargs: Any
):
    """
    Run specified function until it returns expected result until timeout.

    Args:
        func: Specified function.
        expected_result: Result that is expected. Defaults to None.
        timeout_: Time out in seconds. Defaults to 10.
        print_error: Whether any exceptions raised should be printed. Defaults to False.
        sleep_for: Execute func every specified number of seconds. Defaults to 1.
        **kwargs: Arguments to be passed to func.

    Raises:
         WaitForException: If func doesn't return expected result within the
            specified time.

    """
    end = time() + timeout_
    while time() <= end:
        try:
            retval = func(**kwargs)
        except Exception as err:  # pylint: disable=broad-except
            if print_error:
                print(err)
        else:
            if retval == expected_result:
                return None

        sleep(sleep_for)

    raise WaitForException(
        "func: %s, didn't return '%s' within specified"
        " timeout: %d" % (func, expected_result, timeout_)
    )


class TimeoutException(Exception):
    """Exception class for ``timeout()`` function below."""


def timeout(
        func: Callable, duration: int = 10, **kwargs: Any
) -> Any:
    """
    Run specified function until timeout. If success, return the return value
    of specified function. Otherwise throw TimeoutException.

    Args:
        func: Specified function.
        duration: Duration for timeout in seconds. Defaults to 10.
        kwargs: Keyword arguments to be passed to func.

    Returns:
        Any object.

    Raises:
         TimeoutException: if func doesn't return finish executing within
            specified time.
    """
    end = time() + duration
    result_dict = {}  # just to store return value as side effect

    def wrapper_func():
        result_dict["result"] = func(**kwargs)

    new_thread = Thread(target=wrapper_func, daemon=True)
    new_thread.start()

    while time() <= end and new_thread.is_alive():
        sleep(0.1)

    if "result" not in result_dict:
        raise TimeoutException(
            "`{0}` did not finish executing within {1:d} seconds".format(
                func.__name__, duration
            )
        )
    return result_dict["result"]


def download_url(url: str) -> str:
    """
    Download and return decoded contents of url.

    Args:
        url: Url that is to be read.

    Returns:
        Decoded data fetched from url.
    """
    with urllib.request.urlopen(url) as http_response_obj:
        return http_response_obj.read().decode()


def init_docker_client(**kwargs) -> docker.client.DockerClient:
    """
    Initialise docker client.

    Args:
        kwargs: Keyword arguments to be passed to ``docker.from_env()`` call.

    Returns:
        DockerClient object.
    """
    # otherwise docker on CircleCI fails with an error:
    # docker.errors.APIError: 400 Client Error: Bad Request ("client version
    # 1.35 is too new. Maximum supported API version is 1.34")
    kwargs.setdefault("version", "1.34")
    return docker.from_env(**kwargs)


def get_docker_containers(name: str) -> List[docker.models.containers.Container]:
    """
    Get list of docker containers which contain `name` in their names.

    Args:
        name: String that docker container name should contain or match.

    Returns:
        List of docker containers.
    """
    client = init_docker_client()
    return [c for c in client.containers.list() if name in c.name]


def kill_docker_containers(name: str):
    """
    Kill docker containers containing specified specified string in name.

    Args:
        name: Name (or substring) of docker containers.
    """
    containers_to_stop = get_docker_containers(name)
    for container in containers_to_stop:
        container.kill()


def docker_prune():
    """Prunes docker images and containers"""
    client = init_docker_client()
    client.containers.prune()
    client.images.prune()


def get_docker_images(name: str) -> List[docker.models.images.Image]:
    """
    Get docker images with `name` in their names.

    Args:
        name: Name (or substring) of docker images.

    Returns:
        List of docker images.

    """
    client = init_docker_client()
    return [i for i in client.images.list() if any(name in t for t in i.tags)]


def modify_kedro_ver(req_file: Path, version: str) -> str:
    """
    Modify project kedro requirement to deal with invalid kedro version
    bug when bumping up version.

    Args:
        req_file: Path to `requirements.txt` in kedro project.
        version: Version of kedro to insert into project `requirements.txt`.

    Returns:
        Version of kedro in original project `requirements.txt`
    """
    project_reqs = req_file.read_text("utf-8")
    org_version = get_pkg_version(req_file, "kedro")
    project_reqs = project_reqs.replace(org_version, version)
    req_file.write_text(project_reqs)
    return org_version


def create_new_venv() -> str:
    """
    Create a new venv.

    Returns:
        Path to created venv.
    """
    # Create venv
    venv_dir = tempfile.mkdtemp()
    venv.main([str(venv_dir)])
    return venv_dir
