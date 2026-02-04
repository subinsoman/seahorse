# Copyright 2017 deepsense.ai (CodiLime, Inc)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import print_function

import sys


def log_debug(s):
    print('[PyExecutor DEBUG] {}'.format(s), file=sys.stdout)
    sys.stdout.flush()


def log_error(s):
    print('[PyExecutor ERROR] {}'.format(s), file=sys.stderr)
    sys.stderr.flush()


def log_info(s):
    print('[PyExecutor INFO] {}'.format(s), file=sys.stdout)
    sys.stdout.flush()
