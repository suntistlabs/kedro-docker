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


@docker
Feature: Docker commands in new projects
  Background:
    Given I have prepared a config file
    And I run a non-interactive kedro new
    And I have executed the kedro command "install"

  Scenario: Execute docker build target
    Given I have removed old docker image of test project
    When I execute the kedro command "docker build"
    Then I should get a successful exit code
    And A new docker image for test project should be created

  Scenario: Execute docker run target successfully
    Given I have executed the kedro command "docker build"
    When I execute the kedro command "docker run"
    Then I should get a successful exit code
    And I should get a message including "kedro.runner.sequential_runner - INFO - Pipeline execution completed successfully"

  Scenario: Execute docker run in parallel mode
    Given I have executed the kedro command "docker build"
    When I execute the kedro command "docker run --parallel"
    Then I should get a successful exit code
    And I should get a message including "kedro.runner.parallel_runner - INFO - Pipeline execution completed successfully"

  Scenario: Use custom UID and GID for Docker image
    Given I have executed the kedro command "docker build --uid 10001 --gid 20002"
    When I execute the kedro command "docker run"
    Then I should get a successful exit code
    And I should get a message including "INFO - Pipeline execution completed successfully"

  Scenario: Execute docker jupyter notebook target
    Given I have executed the kedro command "docker build"
    When I execute the kedro command "docker jupyter notebook"
    Then Jupyter Notebook should run on port 8888

  Scenario: Execute docker jupyter notebook target on custom port
    Given I have executed the kedro command "docker build"
    When I execute the kedro command "docker jupyter notebook --port 8899"
    Then Jupyter Notebook should run on port 8899

  Scenario: Execute docker jupyter lab target
    Given I have executed the kedro command "docker build"
    When I execute the kedro command "docker jupyter lab"
    Then Jupyter Notebook should run on port 8888

  Scenario: Execute docker jupyter lab target on custom port
    Given I have executed the kedro command "docker build"
    When I execute the kedro command "docker jupyter lab --port 8899"
    Then Jupyter Notebook should run on port 8899

  Scenario: Jupyter port already used
    Given I have executed the kedro command "docker build"
    When I occupy port "8890"
    And I execute the kedro command "docker jupyter lab --port 8890"
    Then I should get an error exit code
    And Standard error should contain a message including "Error: Port 8890 is already in use on the host. Please specify an alternative port number."

  Scenario: Execute docker kedro test target
    Given I have executed the kedro command "docker build"
    When I execute the kedro command "docker cmd kedro test"
    Then I should get a successful exit code
    And I should get a message including "2 passed"
    And I should get a message including "/usr/local/bin/python -m pytest"

  Scenario: Execute docker cmd without target command
    Given I have executed the kedro command "docker build"
    When I execute the kedro command "docker cmd"
    Then I should get a successful exit code
    And I should get a message including "kedro.runner.sequential_runner - INFO - Pipeline execution completed successfully"

  Scenario: Execute docker cmd with non-existent target
    Given I have executed the kedro command "docker build"
    When I execute the kedro command "docker cmd kedro non-existent"
    Then Standard error should contain a message including "Error: No such command "non-existent""

  Scenario: Execute docker ipython target
    Given I have executed the kedro command "docker build"
    When I execute the kedro command "docker ipython"
    Then I should see messages from docker ipython startup including "An enhanced Interactive Python"
    And  I should see messages from docker ipython startup including "INFO - ** Kedro project project-dummy"
    And  I should see messages from docker ipython startup including "INFO - Defined global variable context"

  Scenario: Execute docker run target without building image
    Given I have removed old docker image of test project
    When I execute the kedro command "docker run"
    Then I should get an error exit code
    And Standard error should contain a message including "Error: Unable to find image `project-dummy` locally."

  Scenario: Execute docker dive target
    Given I have executed the kedro command "docker build"
    When I execute the kedro command "docker dive"
    Then I should get a successful exit code
    And I should get a message including "Result:PASS [Total:3] [Passed:3] [Failed:0] [Warn:0] [Skipped:0]"

  Scenario: Execute docker dive with missing CI config
    Given I have executed the kedro command "docker build"
    When I execute the kedro command "docker dive -c non-existent"
    Then I should get a successful exit code
    And I should get a message including "file not found, using default CI config"
    And I should get a message including "Result:PASS [Total:3] [Passed:2] [Failed:0] [Warn:0] [Skipped:1]"

  Scenario: Execute docker dive without building image
    Given I have removed old docker image of test project
    When I execute the kedro command "docker dive"
    Then I should get an error exit code
    And Standard error should contain a message including "Error: Unable to find image `project-dummy` locally."
