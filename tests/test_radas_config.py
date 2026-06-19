"""
Copyright (C) 2022 Red Hat, Inc. (https://github.com/Commonjava/charon)

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

         http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import os
import shutil
import tempfile
import unittest

from novabucks.radas_sign import RadasConfig
from novabucks.utils.files import overwrite_file


class RadasConfigTest(unittest.TestCase):

    def setUp(self) -> None:
        self.__prepare_ca()

    def tearDown(self) -> None:
        self.__clear_ca()

    def __prepare_ca(self):
        self.__tempdir = tempfile.mkdtemp()
        self.__client_ca_path = os.path.join(self.__tempdir, "client_ca.crt")
        self.__client_key_path = os.path.join(self.__tempdir, "client_key.crt")
        self.__client_key_pass_file = os.path.join(self.__tempdir, "client_key_password.txt")
        self.__root_ca = os.path.join(self.__tempdir, "root_ca.crt")
        overwrite_file(self.__client_ca_path, "client ca")
        overwrite_file(self.__client_key_path, "client key")
        overwrite_file(self.__client_key_pass_file, "it's password")
        overwrite_file(self.__root_ca, "root ca")

    def __clear_ca(self):
        shutil.rmtree(self.__tempdir)

    def test_full_radas_config(self):
        radas_settings = {
            "umb_host": "test.umb.api.com",
            "result_queue": "queue.result.test",
            "request_channel": "topic://topic.request.test",
            "client_ca": self.__client_ca_path,
            "client_key": self.__client_key_path,
            "client_key_pass_file": self.__client_key_pass_file,
            "root_ca": self.__root_ca,
        }
        print(radas_settings)
        rconf = RadasConfig(radas_settings)
        self.assertIsNotNone(rconf)
        self.assertTrue(rconf.validate())

    def test_missing_umb_host(self):
        radas_settings = {
            "result_queue": "queue.result.test",
            "request_channel": "topic://topic.request.test",
            "client_ca": self.__client_ca_path,
            "client_key": self.__client_key_path,
            "client_key_pass_file": self.__client_key_pass_file,
        }
        rconf = RadasConfig(radas_settings)
        self.assertIsNotNone(rconf)
        self.assertFalse(rconf.validate())

    def test_missing_result_queue(self):
        radas_settings = {
            "umb_host": "test.umb.api.com",
            "request_channel": "topic://topic.request.test",
            "client_ca": self.__client_ca_path,
            "client_key": self.__client_key_path,
            "client_key_pass_file": self.__client_key_pass_file,
        }
        rconf = RadasConfig(radas_settings)
        self.assertIsNotNone(rconf)
        self.assertFalse(rconf.validate())

    def test_missing_request_queue(self):
        radas_settings = {
            "umb_host": "test.umb.api.com",
            "result_queue": "queue.result.test",
            "client_ca": self.__client_ca_path,
            "client_key": self.__client_key_path,
            "client_key_pass_file": self.__client_key_pass_file,
        }
        rconf = RadasConfig(radas_settings)
        self.assertIsNotNone(rconf)
        self.assertFalse(rconf.validate())

    def test_unaccessible_client_ca(self):
        radas_settings = {
            "umb_host": "test.umb.api.com",
            "result_queue": "queue.result.test",
            "request_channel": "topic://topic.request.test",
            "client_ca": self.__client_ca_path,
            "client_key": "client_key.crt",
            "client_key_pass_file": self.__client_key_pass_file,
        }
        os.remove(self.__client_ca_path)
        rconf = RadasConfig(radas_settings)
        self.assertIsNotNone(rconf)
        self.assertFalse(rconf.validate())

    def test_unaccessible_client_key(self):
        radas_settings = {
            "umb_host": "test.umb.api.com",
            "result_queue": "queue.result.test",
            "request_channel": "topic://topic.request.test",
            "client_ca": "client_ca.crt",
            "client_key": self.__client_key_path,
            "client_key_pass_file": self.__client_key_pass_file,
        }
        os.remove(self.__client_key_path)
        rconf = RadasConfig(radas_settings)
        self.assertIsNotNone(rconf)
        self.assertFalse(rconf.validate())

    def test_unaccessible_client_password_file(self):
        radas_settings = {
            "umb_host": "test.umb.api.com",
            "result_queue": "queue.result.test",
            "request_channel": "topic://topic.request.test",
            "client_ca": self.__client_ca_path,
            "client_key": self.__client_key_path,
            "client_key_pass_file": self.__client_key_pass_file,
        }
        os.remove(self.__client_key_pass_file)
        rconf = RadasConfig(radas_settings)
        self.assertIsNotNone(rconf)
        self.assertFalse(rconf.validate())

    def test_unaccessible_root_ca(self):
        radas_settings = {
            "umb_host": "test.umb.api.com",
            "result_queue": "queue.result.test",
            "request_channel": "topic://topic.request.test",
            "client_ca": self.__client_ca_path,
            "client_key": self.__client_key_path,
            "client_key_pass_file": self.__client_key_pass_file,
            "root_ca": self.__root_ca,
        }
        os.remove(self.__root_ca)
        rconf = RadasConfig(radas_settings)
        self.assertIsNotNone(rconf)
        self.assertFalse(rconf.validate())
