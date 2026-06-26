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
import time
import unittest
from unittest import mock

from novabucks.radas_sign import RadasSender


class RadasSignSenderTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()

    def test_radas_sender(self):
        # Mock configuration
        mock_radas_config = mock.MagicMock()
        mock_radas_config.validate.return_value = True
        mock_radas_config.client_ca.return_value = "test-client-ca"
        mock_radas_config.client_key.return_value = "test-client-key"
        mock_radas_config.client_key_password.return_value = "test-client-key-pass"
        mock_radas_config.root_ca.return_value = "test-root-ca"
        mock_radas_config.radas_sign_timeout_retry_count.return_value = 5

        test_payload = {
            "request_id": "mock-id",
            "requested_by": "test-user",
            "type": "mrrc",
            "file_reference": "quay.io/test/repo",
            "sig_keyname": "test-key",
            "exclude": [],
        }

        # Mock Container run to avoid real AMQP connection
        with (
            mock.patch("novabucks.radas_sign.Container") as mock_container,
            mock.patch("novabucks.radas_sign.SSLDomain") as ssl_domain,
            mock.patch("novabucks.radas_sign.Event") as event,
        ):
            json_payload = json.dumps(test_payload)
            r_sender = RadasSender(json_payload, mock_radas_config)
            self.assertEqual(ssl_domain.call_count, 1)
            self.assertEqual(r_sender.payload, json_payload)
            self.assertIs(r_sender.rconf, mock_radas_config)
            self.assertIsNone(r_sender._message)
            self.assertIsNone(r_sender._pending)

            # test on_start
            mock_sender = mock.MagicMock()
            mock_conn = mock.MagicMock()
            mock_container.connect.return_value = mock_conn
            mock_container.create_sender.return_value = mock_sender
            event.container = mock_container
            r_sender.on_start(event)
            self.assertEqual(mock_container.connect.call_count, 1)
            self.assertEqual(mock_container.create_sender.call_count, 1)
            # on_start now schedules a timeout check
            self.assertEqual(mock_container.schedule.call_count, 1)
            self.assertTrue(r_sender._start_time > 0.0)

            # test on_sendable
            mock_sender.credit = 1
            r_sender.on_sendable(event)
            self.assertIsNotNone(r_sender._message)
            self.assertEqual(mock_sender.send.call_count, 1)

            # test on_accepted
            r_sender.on_accepted(event)
            self.assertEqual(r_sender.status, "success")
            self.assertEqual(r_sender._retried, 0)
            self.assertEqual(r_sender._sender.close.call_count, 1)
            self.assertEqual(r_sender._container.stop.call_count, 1)

            # test on_rejected
            r_sender.on_rejected(event)
            self.assertIsNone(r_sender._pending)
            self.assertEqual(r_sender._retried, 1)
            self.assertEqual(r_sender._container.schedule.call_count, 2)

            # test on_released
            r_sender.on_released(event)
            self.assertIsNone(r_sender._pending)
            self.assertEqual(r_sender._retried, 2)
            self.assertEqual(r_sender._container.schedule.call_count, 3)

            # test on_timer_task with _message_sent=True and _pending set
            # (delivery retry path)
            r_sender._pending = r_sender._message
            r_sender.on_timer_task(event)
            self.assertIsNone(r_sender._pending)
            self.assertEqual(r_sender._retried, 2)
            self.assertEqual(mock_sender.send.call_count, 2)

    def test_sender_connection_timeout(self):
        """Test that the sender times out if the connection is never established."""
        mock_radas_config = mock.MagicMock()
        mock_radas_config.validate.return_value = True
        mock_radas_config.client_ca.return_value = "test-client-ca"
        mock_radas_config.client_key.return_value = "test-client-key"
        mock_radas_config.client_key_password.return_value = "test-client-key-pass"
        mock_radas_config.root_ca.return_value = "test-root-ca"

        with (
            mock.patch("novabucks.radas_sign.Container"),
            mock.patch("novabucks.radas_sign.SSLDomain"),
            mock.patch("novabucks.radas_sign.Event") as event,
        ):
            r_sender = RadasSender("{}", mock_radas_config)

            mock_container = mock.MagicMock()
            event.container = mock_container
            r_sender.on_start(event)

            # Simulate time passing beyond the connection timeout
            r_sender._start_time = time.time() - (r_sender._connection_timeout + 1)
            r_sender.on_timer_task(event)

            self.assertEqual(r_sender.status, "failed")
            self.assertEqual(r_sender._container.stop.call_count, 1)

    def test_sender_connection_not_timed_out(self):
        """Test that the sender reschedules the timer if not yet timed out."""
        mock_radas_config = mock.MagicMock()
        mock_radas_config.validate.return_value = True
        mock_radas_config.client_ca.return_value = "test-client-ca"
        mock_radas_config.client_key.return_value = "test-client-key"
        mock_radas_config.client_key_password.return_value = "test-client-key-pass"
        mock_radas_config.root_ca.return_value = "test-root-ca"

        with (
            mock.patch("novabucks.radas_sign.Container"),
            mock.patch("novabucks.radas_sign.SSLDomain"),
            mock.patch("novabucks.radas_sign.Event") as event,
        ):
            r_sender = RadasSender("{}", mock_radas_config)

            mock_container = mock.MagicMock()
            event.container = mock_container
            r_sender.on_start(event)

            # Timer fires but we haven't timed out yet
            schedule_count_before = mock_container.schedule.call_count
            r_sender.on_timer_task(event)

            # Should have rescheduled, not failed
            self.assertIsNone(r_sender.status)
            self.assertEqual(mock_container.schedule.call_count, schedule_count_before + 1)

    def test_sender_transport_error(self):
        """Test that transport errors are surfaced and cause failure."""
        mock_radas_config = mock.MagicMock()
        mock_radas_config.ssl_enabled.return_value = False

        with mock.patch("novabucks.radas_sign.Event") as event:
            r_sender = RadasSender("{}", mock_radas_config)
            r_sender._container = mock.MagicMock()
            r_sender._sender = mock.MagicMock()

            cond = mock.MagicMock()
            cond.name = "amqp:connection:forced"
            cond.description = "broker forced disconnect"
            event.transport = mock.MagicMock()
            event.transport.condition = cond

            r_sender.on_transport_error(event)

            self.assertEqual(r_sender.status, "failed")
            self.assertEqual(r_sender._container.stop.call_count, 1)
