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

"""Behave step definitions for the cli_scenarios feature."""
import fcntl
import os
from time import sleep, time

import behave
import yaml
from behave import given, then, when

from features.steps.sh_run import ChildTerminatingPopen, run
from features.steps.util import (
    download_url,
    get_docker_images,
    kill_docker_containers,
    timeout,
    wait_for,
)

OK_EXIT_CODE = 0


def _read_lines_with_timeout(*streams, max_seconds=30, max_lines=100):
    """
    We want to read from multiple streams, merge outputs together,
    limiting the number of lines we want.
    Also don't try for longer than ``timeout`` seconds.
    """
    start_time = time()
    lines = []
    stream_dead = [False for _ in streams]

    # Tweak all streams to be non-blocking
    for i, stream in enumerate(streams):

        # In some cases, if the command dies at start, it will be a string here.
        if isinstance(stream, str):
            lines += stream.split("\n")
            stream_dead[i] = True
            continue

        descriptor = stream.fileno()
        flags = fcntl.fcntl(descriptor, fcntl.F_GETFL)
        fcntl.fcntl(descriptor, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    while (
        len(lines) < max_lines
        and not all(stream_dead)
        and time() - start_time < max_seconds
    ):
        for i, stream in enumerate(streams):
            if stream_dead[i]:
                continue

            new_line = stream.readline().decode().strip()

            if new_line:
                lines.append(new_line)

            sleep(0.1)

    return "\n".join(lines)


def _get_docker_ipython_output(context):
    """Get first 16 lines of ipython output if not already retrieved"""
    if hasattr(context, "ipython_stdout"):
        return context.ipython_stdout

    try:
        context.ipython_stdout = _read_lines_with_timeout(
            context.result.stdout, context.result.stderr, max_lines=16
        )
    finally:
        kill_docker_containers(context.project_name)

    return context.ipython_stdout


def _check_service_up(context: behave.runner.Context, url: str, string: str):
    """
    Check that a service is running and responding appropriately

    Args:
        context: Test context.
        url: Url that is to be read.
        string: The string to be checked.
    """
    data = download_url(url)

    try:
        assert context.result.poll() is None
        assert string in data
    finally:
        if "docker" in context.result.args:
            kill_docker_containers(context.project_name)
        else:
            context.result.terminate()


@given("I have prepared a config file")
def create_configuration_file(context):
    """Behave step to create a temporary config file
    (given the existing temp directory)
    and store it in the context.
    """
    context.config_file = context.temp_dir / "config"
    context.project_name = "project-dummy"

    root_project_dir = context.temp_dir / context.project_name
    context.root_project_dir = root_project_dir
    config = {
        "project_name": context.project_name,
        "repo_name": context.project_name,
        "output_dir": str(context.temp_dir),
        "python_package": context.project_name.replace("-", "_"),
        "include_example": True,
    }
    with context.config_file.open("w") as config_file:
        yaml.dump(config, config_file, default_flow_style=False)


@given("I run a non-interactive kedro new")
def create_project_from_config_file(context):
    """Behave step to run kedro new
    given the config I previously created.
    """
    res = run([context.kedro, "new", "-c", str(context.config_file)], env=context.env)
    assert res.returncode == 0


@given('I have executed the kedro command "{command}"')
def exec_make_target_checked(context, command):
    """Execute Makefile target"""
    make_cmd = [context.kedro] + command.split()

    res = run(make_cmd, env=context.env, cwd=str(context.root_project_dir))

    if res.returncode != OK_EXIT_CODE:
        print(res.stdout)
        print(res.stderr)
        assert False


@given("I have removed old docker image of test project")
def remove_old_docker_images(context):
    """Remove old docker images of project"""
    run(["docker", "rmi", context.project_name])


@when('I execute the kedro command "{command}"')
def exec_kedro_target(context, command):
    """Execute Kedro target"""
    split_command = command.split()
    make_cmd = [context.kedro] + split_command
    print(make_cmd)

    if split_command[0] == "docker" and split_command[1] in ("ipython", "jupyter"):
        context.result = ChildTerminatingPopen(
            make_cmd, env=context.env, cwd=str(context.root_project_dir)
        )
    else:
        context.result = run(
            make_cmd, env=context.env, cwd=str(context.root_project_dir)
        )


@when('I occupy port "{port}"')
def occupy_port(context, port):
    """Execute  target"""
    ChildTerminatingPopen(
        ["nc", "-l", "0.0.0.0", port],
        env=context.env,
        cwd=str(context.root_project_dir),
    )


@then('I should get a message including "{msg}"')
def read_docker_stdout(context, msg):
    """Read stdout and raise AssertionError if the given message is not there."""

    if hasattr(context.result.stdout, "read"):
        context.result.stdout = context.result.stdout.read().decode("utf-8")

    try:
        if msg not in context.result.stdout:
            print(context.result.stdout)
            assert False, "Message '{0}' not found in stdout".format(msg)
    finally:
        kill_docker_containers(context.project_name)


@then('Standard error should contain a message including "{msg}"')
def read_docker_stderr(context, msg):
    """Read stderr and raise AssertionError if the given message is not there."""

    if hasattr(context.result.stderr, "read"):
        context.result.stderr = context.result.stderr.read().decode("utf-8")

    try:
        if msg not in context.result.stderr:
            print(context.result.stderr)
            assert False, "Message '{0}' not found in stderr".format(msg)
    finally:
        kill_docker_containers(context.project_name)


@then("I should get a successful exit code")
def check_status_code(context):
    if context.result.returncode != OK_EXIT_CODE:
        print(context.result.stdout)
        print(context.result.stderr)
        assert False, "Expected exit code {} but got {}".format(
            OK_EXIT_CODE, context.result.returncode
        )


@then("I should get an error exit code")
def check_failed_status_code(context):
    if context.result.returncode == OK_EXIT_CODE:
        print(context.result.stdout)
        print(context.result.stderr)
        assert False, "Expected exit code other than {} but got {}".format(
            OK_EXIT_CODE, context.result.returncode
        )


@then('I should see messages from docker ipython startup including "{msg}"')
def check_docker_ipython_msg(context, msg):
    stdout = _get_docker_ipython_output(context)
    assert msg in stdout, (
        "Expected the following message segment to be printed on stdout: "
        "{exp_msg},\nbut got {actual_msg}".format(exp_msg=msg, actual_msg=stdout)
    )


@then("Jupyter Notebook should run on port {port}")
def check_jupyter_nb_proc_on_port(context: behave.runner.Context, port: int):
    """
    Check that jupyter notebook service is running on specified port

    Args:
        context: Test context
        port: Port to check
    """
    url = "http://localhost:{:d}".format(int(port))
    wait_for(
        func=_check_service_up,
        expected_result=None,
        print_error=False,
        context=context,
        url=url,
        string="Jupyter Notebook",
        timeout_=15,
    )


@then("A new docker image for test project should be created")
def check_docker_project_created(context):
    """Check that docker image for test project has been created"""

    def _check_image():
        while True:
            if get_docker_images(context.project_name):
                return True
            sleep(0.5)

    assert timeout(_check_image, duration=30)
