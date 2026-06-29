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

import json
import tempfile
import time
import unittest
from unittest import mock

from novabucks.radas_sign import RadasReceiver


class RadasSignReceiverTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()

    def reset_receiver(self, r_receiver: RadasReceiver) -> None:
        r_receiver._message_handled = False
        r_receiver.sign_result_errors = []
        r_receiver.sign_result_status = None

    def _make_mock_config(self, result_queue="Consumer.svc.VirtualTopic.eng.robosignatory.sign.>"):
        mock_radas_config = mock.MagicMock()
        mock_radas_config.validate.return_value = True
        mock_radas_config.client_ca.return_value = "test-client-ca"
        mock_radas_config.client_key.return_value = "test-client-key"
        mock_radas_config.client_key_password.return_value = "test-client-key-pass"
        mock_radas_config.root_ca.return_value = "test-root-ca"
        mock_radas_config.receiver_timeout.return_value = 60
        mock_radas_config.result_queue.return_value = result_queue
        return mock_radas_config

    def test_on_start_inserts_request_id_before_virtual_topic(self):
        mock_radas_config = self._make_mock_config()
        with (
            mock.patch("novabucks.radas_sign.Container"),
            mock.patch("novabucks.radas_sign.SSLDomain"),
            mock.patch("novabucks.radas_sign.Event") as event,
        ):
            mock_container = mock.MagicMock()
            event.container = mock_container
            r_receiver = RadasReceiver("/tmp", "my-request-id", mock_radas_config)
            r_receiver.on_start(event)
            _, kwargs = mock_container.create_receiver.call_args
            self.assertEqual(
                kwargs["source"],
                "Consumer.svc.my-request-id.VirtualTopic.eng.robosignatory.sign.>",
            )

    def test_on_start_empty_request_id_leaves_queue_unchanged(self):
        configured = "Consumer.svc.VirtualTopic.eng.robosignatory.sign.>"
        mock_radas_config = self._make_mock_config(result_queue=configured)
        with (
            mock.patch("novabucks.radas_sign.Container"),
            mock.patch("novabucks.radas_sign.SSLDomain"),
            mock.patch("novabucks.radas_sign.Event") as event,
        ):
            mock_container = mock.MagicMock()
            event.container = mock_container
            r_receiver = RadasReceiver("/tmp", "", mock_radas_config)
            r_receiver.on_start(event)
            _, kwargs = mock_container.create_receiver.call_args
            self.assertEqual(kwargs["source"], configured)

    def test_on_start_no_virtual_topic_leaves_queue_unchanged(self):
        configured = "queue://some.static.queue"
        mock_radas_config = self._make_mock_config(result_queue=configured)
        with (
            mock.patch("novabucks.radas_sign.Container"),
            mock.patch("novabucks.radas_sign.SSLDomain"),
            mock.patch("novabucks.radas_sign.Event") as event,
        ):
            mock_container = mock.MagicMock()
            event.container = mock_container
            r_receiver = RadasReceiver("/tmp", "my-request-id", mock_radas_config)
            r_receiver.on_start(event)
            _, kwargs = mock_container.create_receiver.call_args
            self.assertEqual(kwargs["source"], configured)

    def test_radas_receiver(self):
        mock_radas_config = self._make_mock_config()

        # Mock Container run to avoid real AMQP connection
        with (
            mock.patch("novabucks.radas_sign.Container") as mock_container,
            mock.patch("novabucks.radas_sign.SSLDomain") as ssl_domain,
            mock.patch("novabucks.radas_sign.OrasClient") as oras_client,
            mock.patch("novabucks.radas_sign.Event") as event,
        ):
            test_result_path = tempfile.mkdtemp()
            test_request_id = "test-request-id"
            r_receiver = RadasReceiver(test_result_path, test_request_id, mock_radas_config)
            self.assertEqual(ssl_domain.call_count, 1)
            self.assertEqual(r_receiver.sign_result_loc, test_result_path)
            self.assertEqual(r_receiver.request_id, test_request_id)

            # prepare mock
            mock_receiver = mock.MagicMock()
            mock_conn = mock.MagicMock()
            mock_container.connect.return_value = mock_conn
            mock_container.create_receiver.return_value = mock_receiver
            event.container = mock_container
            event.message = mock.MagicMock()
            event.connection = mock.MagicMock()

            # test on_start
            r_receiver.on_start(event)
            self.assertEqual(mock_container.connect.call_count, 1)
            self.assertEqual(mock_container.create_receiver.call_count, 1)
            self.assertTrue(r_receiver._start_time > 0.0)
            self.assertTrue(r_receiver._start_time < time.time())
            self.assertEqual(mock_container.schedule.call_count, 1)

            # test on_message: unmatched case
            test_ummatch_result = {
                "i": "1",
                "msg_id": "test-id",
                "timestamp": time.time(),
                "topic": "test-topic",
                "username": "test-user",
                "msg": {
                    "request_id": "test-request-id-no-match",
                    "file_reference": "quay.io/example/test-repo",
                    "result_reference": "quay.io/example-sign/sign-repo",
                    "sig_keyname": "testkey",
                    "signing_status": "success",
                    "errors": [],
                },
            }
            event.message.body = json.dumps(test_ummatch_result)
            r_receiver.on_message(event)
            self.assertEqual(event.connection.close.call_count, 0)
            self.assertEqual(mock_container.stop.call_count, 0)
            self.assertFalse(r_receiver._message_handled)
            self.assertIsNone(r_receiver.sign_result_status)
            self.assertEqual(r_receiver.sign_result_errors, [])
            self.assertEqual(oras_client.call_count, 0)

            # test on_message: matched case with failed status
            self.reset_receiver(r_receiver)
            test_failed_result = {
                "i": "1",
                "msg_id": "test-id",
                "timestamp": time.time(),
                "topic": "test-topic",
                "username": "test-user",
                "msg": {
                    "request_id": "test-request-id",
                    "file_reference": "quay.io/example/test-repo",
                    "result_reference": "quay.io/example-sign/sign-repo",
                    "sig_keyname": "testkey",
                    "signing_status": "failed",
                    "errors": ["error1", "error2"],
                },
            }
            event.message.body = json.dumps(test_failed_result)
            r_receiver.on_message(event)
            self.assertEqual(event.connection.close.call_count, 1)
            self.assertEqual(mock_container.stop.call_count, 1)
            self.assertTrue(r_receiver._message_handled)
            self.assertEqual(r_receiver.sign_result_status, "failed")
            self.assertEqual(r_receiver.sign_result_errors, ["error1", "error2"])
            self.assertEqual(oras_client.call_count, 0)

            # test on_message: matched case with success status
            self.reset_receiver(r_receiver)
            test_success_result = {
                "i": "1",
                "msg_id": "test-id",
                "timestamp": time.time(),
                "topic": "test-topic",
                "username": "test-user",
                "msg": {
                    "request_id": "test-request-id",
                    "file_reference": "quay.io/example/test-repo",
                    "result_reference": "quay.io/example-sign/sign-repo",
                    "sig_keyname": "testkey",
                    "signing_status": "success",
                    "errors": [],
                },
            }
            event.message.body = json.dumps(test_success_result)
            r_receiver.on_message(event)
            self.assertEqual(event.connection.close.call_count, 2)
            self.assertEqual(mock_container.stop.call_count, 2)
            self.assertTrue(r_receiver._message_handled)
            self.assertEqual(r_receiver.sign_result_status, "success")
            self.assertEqual(r_receiver.sign_result_errors, [])
            self.assertEqual(oras_client.call_count, 1)
            oras_client_call = oras_client.return_value
            self.assertEqual(oras_client_call.pull.call_count, 1)

            # test on_timer_task: not timeout
            r_receiver.on_timer_task(event)
            self.assertEqual(event.connection.close.call_count, 2)
            self.assertEqual(mock_container.stop.call_count, 2)
            self.assertEqual(mock_container.schedule.call_count, 2)

            # test on_timer_task: timeout
            mock_radas_config.receiver_timeout.return_value = 0
            r_receiver.on_timer_task(event)
            self.assertEqual(event.connection.close.call_count, 3)
            self.assertEqual(mock_container.stop.call_count, 3)
            self.assertEqual(mock_container.schedule.call_count, 2)
