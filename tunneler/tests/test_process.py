from unittest import TestCase

from mock import Mock, patch

from ..models import Tunnel
from ..process import ProcessHelper


class ProcessHelperTestCase(TestCase):
    def setUp(self):
        self.process_helper = ProcessHelper()

    def test_process_line_to_tunnel_ok(self):
        line = '-N -L2323:localhost:4545 hiyou@aserver.aplace.net'
        expected = (2323, 4545, 'hiyou', 'aserver.aplace.net')

        self.assertEqual(
            self.process_helper.extract_tunnel_info(line),
            expected
        )

    def test_process_line_to_tunnel_not_ok(self):
        line = '-N -L3434:localhost:1212 server.aplace.net'

        with self.assertRaises(AttributeError):
            self.process_helper.extract_tunnel_info(line)

    @patch('tunneler.process.call')
    def test_start_tunnel_success(self, call_mock):
        call_mock.return_value = 0

        result = self.process_helper.start_tunnel(
            'user', 'server', 1212, 3434)
        self.assertTrue(result)

    @patch('tunneler.process.call')
    def test_start_tunnel_failure(self, call_mock):
        call_mock.return_value = 13

        result = self.process_helper.start_tunnel(
            'user', 'server', 1212, 3434)
        self.assertFalse(result)

    # TODO fix these last two tests... they're stupid and I hate them
    # def test_stop_success(self):
    #     tunnel = Mock(Tunnel)
    #     process_mock = Mock('process')
    #     process_mock.terminate.return_value = None
    #     tunnel.process = process_mock

    #     self.assertTrue(self.process_helper.stop_tunnel(tunnel))

    # def test_stop_failure(self):
    #     tunnel = Mock(Tunnel)
    #     tunnel.process.terminate.side_effect = Exception

    #     self.assertFalse(self.process_helper.stop_tunnel(tunnel))