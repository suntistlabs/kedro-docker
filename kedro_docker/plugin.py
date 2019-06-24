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
# The QuantumBlack Visual Analytics Limited (“QuantumBlack”) name and logo
# (either separately or in combination, “QuantumBlack Trademarks”) are
# trademarks of QuantumBlack. The License does not grant you any right or
# license to the QuantumBlack Trademarks. You may not use the QuantumBlack
# Trademarks or any confusingly similar mark as a trademark for your product,
#     or use the QuantumBlack Trademarks in any other manner that might cause
# confusion in the marketplace, including but not limited to in advertising,
# on websites, or on software.
#
# See the License for the specific language governing permissions and
# limitations under the License.

""" Kedro plugin for packaging a project with Docker """
import shlex
import subprocess
from pathlib import Path
from typing import Dict, Tuple, Union

import click
from click import ClickException
from kedro.cli import get_project_context
from kedro.cli.utils import call, forward_command

from .helpers import (
    add_jupyter_args,
    check_docker_image_exists,
    compose_docker_run_args,
    copy_template_files,
    get_uid_gid,
    is_port_in_use,
    make_container_name,
)

NO_DOCKER_MESSAGE = """
Cannot connect to the Docker daemon. Is the Docker daemon running?
"""


DOCKER_DEFAULT_VOLUMES = (
    "conf/local",
    "data",
    "logs",
    "notebooks",
    "references",
    "results",
)


def _image_callback(ctx, param, value):  # pylint: disable=unused-argument
    image = value or str(get_project_context("project_path").name)
    check_docker_image_exists(image)
    return image


def _port_callback(ctx, param, value):  # pylint: disable=unused-argument
    if is_port_in_use(value):
        raise ClickException(
            "Port {} is already in use on the host. "
            "Please specify an alternative port number.".format(value)
        )
    return value


def _make_port_option(**kwargs):
    defaults = {
        "type": int,
        "default": 8888,
        "help": "Host port to publish to.",
        "callback": _port_callback,
    }
    kwargs = dict(defaults, **kwargs)
    return click.option("--port", **kwargs)


def _make_image_option(**kwargs):
    defaults = {
        "type": str,
        "default": None,
        "help": "Docker image tag. Default is the project directory name.",
    }
    kwargs = dict(defaults, **kwargs)
    return click.option("--image", **kwargs)


def _make_docker_args_option(**kwargs):
    defaults = {
        "type": str,
        "default": "",
        "callback": lambda ctx, param, value: shlex.split(value),
        "help": "Optional arguments to be passed to `docker run` command.",
    }
    kwargs = dict(defaults, **kwargs)
    return click.option("--docker-args", **kwargs)


@click.group(name="Docker")
def commands():
    """ Kedro plugin for packaging a project with Docker """
    pass


@commands.group(name="docker")
def docker_group():
    """Dockerize your Kedro project."""
    # check that docker is running
    try:
        res = subprocess.run(
            ["docker", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ).returncode
    except FileNotFoundError:
        raise ClickException(NO_DOCKER_MESSAGE)
    if res:
        raise ClickException(NO_DOCKER_MESSAGE)


@docker_group.command(
    name="build", context_settings=dict(help_option_names=["-h", "--help"])
)
@click.option(
    "--uid",
    type=int,
    default=None,
    help="User ID for kedro user inside the container. "
    "Default is the current user's UID.",
)
@click.option(
    "--gid",
    type=int,
    default=None,
    help="Group ID for kedro user inside the container. "
    "Default is the current user's GID.",
)
@_make_image_option()
@_make_docker_args_option(
    help="Optional arguments to be passed to `docker build` command."
)
def docker_build(uid, gid, image, docker_args):
    """Build a Docker image for the project."""

    uid, gid = get_uid_gid(uid, gid)
    project_path = get_project_context("project_path")
    image = image or str(project_path.name)

    template_path = Path(__file__).parent / "template"
    verbose = get_project_context("verbose")
    copy_template_files(
        project_path, template_path, ["Dockerfile", ".dockerignore"], verbose
    )

    combined_args = compose_docker_run_args(
        required_args=[
            ("--build-arg", "KEDRO_UID={0}".format(uid)),
            ("--build-arg", "KEDRO_GID={0}".format(gid)),
        ],
        # add image tag if only it is not already supplied by the user
        optional_args=[("-t", image)],
        user_args=docker_args,
    )
    command = ["docker", "build"] + combined_args + [str(project_path)]
    call(command)


def _mount_info() -> Dict[str, Union[str, Tuple]]:
    project_path = get_project_context("project_path")
    res = dict(
        host_root=str(project_path),
        container_root="/home/kedro",
        mount_volumes=DOCKER_DEFAULT_VOLUMES,
    )
    return res


@forward_command(docker_group, "run")
@_make_image_option(callback=_image_callback)
@_make_docker_args_option()
def docker_run(image, docker_args, args):
    """Run the pipeline in the Docker container.
    Any extra arguments unspecified in this help
    are passed to `docker run` as is."""

    container_name = make_container_name(image, "run")
    _docker_run_args = compose_docker_run_args(
        optional_args=[("--rm", None), ("--name", container_name)],
        user_args=docker_args,
        **_mount_info()
    )

    command = (
        ["docker", "run"] + _docker_run_args + [image, "kedro", "run"] + list(args)
    )
    call(command)


@forward_command(docker_group, "ipython")
@_make_image_option(callback=_image_callback)
@_make_docker_args_option()
def docker_ipython(image, docker_args, args):
    """Run ipython in the Docker container.
    Any extra arguments unspecified in this help are passed to
    `kedro ipython` command inside the container as is."""
    container_name = make_container_name(image, "ipython")
    _docker_run_args = compose_docker_run_args(
        optional_args=[("--rm", None), ("-it", None), ("--name", container_name)],
        user_args=docker_args,
        **_mount_info()
    )

    command = (
        ["docker", "run"] + _docker_run_args + [image, "kedro", "ipython"] + list(args)
    )
    call(command)


@docker_group.group(name="jupyter")
def docker_jupyter():
    """Run jupyter notebook / lab in Docker container."""


@forward_command(docker_jupyter, "notebook")
@_make_image_option(callback=_image_callback)
@_make_port_option()
@_make_docker_args_option()
def docker_jupyter_notebook(docker_args, port, image, args):
    """Run jupyter notebook in the Docker container.
    Any extra arguments unspecified in this help are passed to
    `kedro jupyter notebook` command inside the container as is."""
    container_name = make_container_name(image, "jupyter-notebook")
    _docker_run_args = compose_docker_run_args(
        required_args=[("-p", "{}:8888".format(port))],
        optional_args=[("--rm", None), ("-it", None), ("--name", container_name)],
        user_args=docker_args,
        **_mount_info()
    )

    args = add_jupyter_args(list(args))
    command = (
        ["docker", "run"]
        + _docker_run_args
        + [image, "kedro", "jupyter", "notebook"]
        + args
    )
    call(command)


@forward_command(docker_jupyter, "lab")
@_make_image_option(callback=_image_callback)
@_make_port_option()
@_make_docker_args_option()
def docker_jupyter_lab(docker_args, port, image, args):
    """Run jupyter lab in the Docker container.
    Any extra arguments unspecified in this help are passed to
    `kedro jupyter lab` command inside the container as is."""

    container_name = make_container_name(image, "jupyter-lab")
    _docker_run_args = compose_docker_run_args(
        required_args=[("-p", "{}:8888".format(port))],
        optional_args=[("--rm", None), ("-it", None), ("--name", container_name)],
        user_args=docker_args,
        **_mount_info()
    )

    args = add_jupyter_args(list(args))
    command = (
        ["docker", "run"] + _docker_run_args + [image, "kedro", "jupyter", "lab"] + args
    )
    call(command)


@forward_command(docker_group, "cmd")
@_make_image_option(callback=_image_callback)
@_make_docker_args_option()
def docker_cmd(args, docker_args, image):
    """Run arbitrary command from ARGS in the Docker container.
    If ARGS are not specified, this will invoke `kedro run` inside the container."""

    container_name = make_container_name(image, "cmd")
    _docker_run_args = compose_docker_run_args(
        optional_args=[("--rm", None), ("--name", container_name)],
        user_args=docker_args,
        **_mount_info()
    )

    command = ["docker", "run"] + _docker_run_args + [image] + list(args)
    call(command)
