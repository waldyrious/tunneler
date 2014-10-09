from unittest import TestCase

from mock import Mock

from ..models import Configuration, Tunnel
from ..process import ProcessHelper
from ..tunneler import (
    AlreadyThereError,
    ConfigNotFound,
    Tunneler,
    check_tunnel_exists,
)


class CheckTunnelExistsTestCase(TestCase):
    def test_tunnel_exists(self):
        func = Mock()
        name = 'atunnel'
        tunneler = Mock()
        tunneler.config.tunnels = {'atunnel': 'yes indeed'}

        decorated_func = check_tunnel_exists(func)
        decorated_func(tunneler, name)

        func.assert_called_once_with(tunneler, name)

    def test_tunnel_does_not_exist(self):
        func = Mock()
        name = 'atunnel'
        tunneler = Mock()
        tunneler.config.tunnels = {}

        decorated_func = check_tunnel_exists(func)

        with self.assertRaises(ConfigNotFound):
            _ = decorated_func(tunneler, name)  # NOQA

        self.assertEqual(func.call_count, 0)


class TunnelerTestCase(TestCase):
    def setUp(self):
        self.process_helper = Mock(ProcessHelper)
        self.tunnel_name = 'test_tunnel'
        tunnel_data = {
            self.tunnel_name: {
                'user': 'somebody',
                'server': 'somewhere',
                'local_port': 2323,
                'remote_port': 3434,
            }
        }

        self.config = Configuration(
            common={},
            tunnels=tunnel_data)

        self.tunneler = Tunneler(self.process_helper, Configuration({}, {}))

    def test_find_tunnel_name(self):
        name = 'testserver'
        fullname = 'fullserver.name'
        port = 42

        tunnel_data = {
            'server': fullname,
            'remote_port': port,
        }
        self.tunneler.config = Configuration(
            common={},
            tunnels={name: tunnel_data},
        )

        result = self.tunneler.find_tunnel_name(fullname, port)
        self.assertEqual(result, name)

    def test_find_tunnel_name_when_not_found(self):
        with self.assertRaises(LookupError):
            self.tunneler.find_tunnel_name('someserver.somewhere', 69)

    def test_get_configured_tunnels(self):
        tunnel_data = {'a': None, 'b': None}
        self.tunneler.config = Configuration(
            common={},
            tunnels=tunnel_data,
        )

        configured_tunnels = self.tunneler.get_configured_tunnels()
        self.assertEqual(configured_tunnels, tunnel_data.keys())

    def test_get_configured_tunnels_with_filtering(self):
        tunnel_data = {'a': None, 'b': None}
        self.tunneler.config = Configuration(
            common={},
            tunnels=tunnel_data,
        )

        # Filtering active
        self.tunneler.is_tunnel_active = Mock(side_effect=[True, False])
        configured_tunnels = self.tunneler.get_configured_tunnels(
            filter_active=True)
        self.assertEqual(configured_tunnels, ['a'])
        self.assertEqual(self.tunneler.is_tunnel_active.call_count, 2)

        # Filtering inactive
        self.tunneler.is_tunnel_active = Mock(side_effect=[True, False])
        configured_tunnels = self.tunneler.get_configured_tunnels(
            filter_active=False)
        self.assertEqual(configured_tunnels, ['b'])
        self.assertEqual(self.tunneler.is_tunnel_active.call_count, 2)

    def test_is_tunnel_active(self):
        tunnel_data = {'server1': None, 'server2': None}
        self.tunneler.config = Configuration(
            common={},
            tunnels=tunnel_data,
        )
        self.tunneler.get_tunnel = Mock(side_effect=[Tunnel(), NameError])
        self.assertTrue(self.tunneler.is_tunnel_active('server1'))
        self.assertFalse(self.tunneler.is_tunnel_active('server2'))

    def test_start_tunnel(self):
        self.tunneler.config = self.config
        self.tunneler.get_active_tunnel = Mock(side_effect=NameError)
        self.process_helper.start_tunnel = Mock('start_tunnel')

        self.tunneler.start_tunnel(self.tunnel_name)

        self.assertEqual(self.process_helper.start_tunnel.call_count, 1)

    def test_start_tunnel_if_already_active(self):
        self.tunneler.config = self.config
        self.tunneler.get_active_tunnel = Mock(return_value=object())

        with self.assertRaises(AlreadyThereError):
            self.tunneler.start_tunnel(self.tunnel_name)

    def test_stop_tunnel(self):
        self.tunneler.config = self.config
        self.tunneler.get_active_tunnel = Mock(return_value=object())
        self.process_helper.stop_tunnel = Mock('stop_tunnel')

        self.tunneler.stop_tunnel(self.tunnel_name)

        self.assertEqual(self.process_helper.stop_tunnel.call_count, 1)

    def test_stop_tunnel_if_already_inactive(self):
        self.tunneler.config = self.config
        self.tunneler.get_active_tunnel = Mock(side_effect=NameError)

        with self.assertRaises(AlreadyThereError):
            self.tunneler.stop_tunnel(self.tunnel_name)
