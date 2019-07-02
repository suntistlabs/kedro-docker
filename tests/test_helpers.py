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

from pathlib import Path

from click import ClickException
from pytest import mark, raises

from kedro_docker.helpers import (
    add_jupyter_args,
    check_docker_image_exists,
    compose_docker_run_args,
    copy_template_files,
    get_uid_gid,
    is_port_in_use,
    make_container_name,
)


def test_missing_docker_image(mocker):
    """Check the error raised when docker image is missing"""
    patched_subproc = mocker.patch("subprocess.run")
    patched_subproc.return_value.stdout = b""
    image_name = "image-name"
    pattern = "Unable to find image `{}` locally".format(image_name)
    with raises(ClickException, match=pattern):
        check_docker_image_exists(image_name)
    assert patched_subproc.call_count == 1


@mark.parametrize(
    "args",
    [
        ["image-name-with-suffix"],
        ["image name with  suffix"],
        ["image!name", "with-suffix"],
        ["image!&+=*name", "with-suffix"],
    ],
)
def test_make_container_name(args):
    """Test docker container name normalization"""
    assert make_container_name(*args) == "image-name-with-suffix"


class TestComposeDockerRunArgs:
    def test_args(self, tmp_path):
        """Test composing the arguments for `docker run` command"""
        kwargs = dict(
            host_root=str(tmp_path),
            container_root="/home/kedro/projectname",
            optional_args=[("-arg1", "projectname"), ("--arg4", "x4")],
            required_args=[("-arg2", None), ("-arg3", "x2")],
            user_args=["-arg1", "-arg2=y2", "-arg3", "y3"],
        )
        expected = ["-arg2", "-arg3", "x2", "--arg4", "x4"] + kwargs["user_args"]
        assert compose_docker_run_args(**kwargs) == expected

    def test_mount(self, tmp_path):
        """Test composing the arguments with volumes to mount"""
        host_root = tmp_path.resolve()
        kwargs = dict(
            host_root=str(host_root),
            container_root="/home/kedro/projectname",
            mount_volumes=("conf/local", "data", "logs"),
            user_args=["-v", "y1"],
        )
        expected = []
        for _vol in kwargs["mount_volumes"]:
            _mount_vol = "{}:{}/{}".format(
                host_root / _vol, kwargs["container_root"], _vol
            )
            expected.extend(["-v", _mount_vol])
        expected += kwargs["user_args"]
        assert compose_docker_run_args(**kwargs) == expected

    @mark.parametrize("host_root", ["host_root", None])
    @mark.parametrize("container_root", ["container_root", None])
    def test_bad_mount(self, host_root, container_root):
        """Check the error raised when host and/or container roots are
        not defined, but mount volumes are provided"""
        mount_volumes = ("conf/local", "data", "logs")
        pattern = (
            "Both `host_root` and `container_root` must be specified "
            "in `compose_docker_run_args` call if `mount_volumes` "
            "are provided."
        )
        if not (host_root and container_root):
            with raises(ClickException, match=pattern):
                compose_docker_run_args(
                    host_root=host_root,
                    container_root=container_root,
                    mount_volumes=mount_volumes,
                )


class TestCopyTemplateFiles:
    def test_copy(self, tmp_path):
        """Test copying template files"""
        this_file = Path(__file__)
        dest_file = tmp_path / this_file.name
        assert not dest_file.exists()
        copy_template_files(tmp_path, this_file.parent, [this_file.name], True)
        assert dest_file.exists()

    def test_skip(self, tmp_path):
        """Test copying is skipped if destination path already exists"""
        this_file = Path(__file__)
        dest_file = tmp_path / this_file.name
        with dest_file.open("w") as f:
            f.write("helo world")
        copy_template_files(tmp_path, this_file.parent, [this_file.name])
        with dest_file.open("r") as f:
            assert f.read().strip() == "helo world"


class TestGetUidGid:
    @mark.parametrize(
        "uid, gid, expected",
        [
            [999, 0, (999, 0)],
            [None, 2, (123, 2)],
            [3, None, (3, 456)],
            [None, None, (123, 456)],
        ],
    )
    def test_posix(self, uid, gid, expected, mocker):
        """Test getting user and group id when host system is Posix"""
        mocker.patch("os.name", new="posix")
        mocker.patch("os.getuid", return_value=123)
        pw_gid = mocker.Mock()
        pw_gid.pw_gid = 456
        mocker.patch("pwd.getpwuid", return_value=pw_gid)
        assert get_uid_gid(uid, gid) == expected

    @mark.parametrize(
        "uid, gid, expected",
        [
            [234, 567, (234, 567)],
            [None, 2, (999, 2)],
            [3, None, (3, 0)],
            [None, None, (999, 0)],
        ],
    )
    def test_windows(self, uid, gid, expected, mocker):
        """Test getting user and group id when host system is Windows"""
        mocker.patch("os.name", new="windows")
        assert get_uid_gid(uid, gid) == expected


@mark.parametrize(
    "run_args, expected",
    [
        ([], ["--ip", "0.0.0.0", "--no-browser"]),
        (["--no-browser"], ["--no-browser", "--ip", "0.0.0.0"]),
        (["--foo", "ip"], ["--foo", "ip", "--ip", "0.0.0.0", "--no-browser"]),
        (["--foo", "ip", "--ip"], ["--foo", "ip", "--ip", "--no-browser"]),
        (["--foo", "--no-browser", "--ip=baz"], ["--foo", "--no-browser", "--ip=baz"]),
        (
            ["--foo", "--no-browser=bar", "--ip=baz"],
            ["--foo", "--no-browser=bar", "--ip=baz", "--no-browser"],
        ),
    ],
)
def test_add_jupyter_args(run_args, expected):
    """Test adding jupyter args to the existing list of CLI args"""
    assert add_jupyter_args(run_args) == expected


@mark.parametrize("port", [8888, 98765, 80, 8080])
@mark.parametrize("mock_return_value, expected", [(0, True), (61, False)])
def test_is_port_in_use(mocker, port, mock_return_value, expected):
    _mock = mocker.patch("socket.socket.connect_ex", return_value=mock_return_value)
    assert is_port_in_use(port) is expected
    _mock.assert_called_once_with(("0.0.0.0", port))
