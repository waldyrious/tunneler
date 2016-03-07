from unittest import TestCase

from mock import Mock, patch

from ..models import Configuration, Tunnel
from ..process import ProcessHelper
from ..tunneler import (
    ConfigNotFound,
    Tunneler,
    check_name_exists,
)


class CheckTunnelExistsTestCase(TestCase):
    def test_tunnel_exists(self):
        func = Mock()
        name = 'atunnel'
        tunneler = Mock()
        tunneler.config.tunnels = {'atunnel': 'yes indeed'}
        tunneler.config.groups = {}

        decorated_func = check_name_exists(func)
        decorated_func(tunneler, name)

        func.assert_called_once_with(tunneler, name)

    def test_tunnel_does_not_exist(self):
        func = Mock()
        name = 'atunnel'
        tunneler = Mock()
        tunneler.config.tunnels = {}
        tunneler.config.groups = {}

        decorated_func = check_name_exists(func)

        with self.assertRaises(ConfigNotFound):
            _ = decorated_func(tunneler, name)  # NOQA

        self.assertEqual(func.call_count, 0)


class TunnelerTestCase(TestCase):
    def setUp(self):
        self.process_helper = Mock(ProcessHelper)
        self.tunnel_name = 'test_tunnel'
        self.group_name = 'test_group'
        self.tunnel = Tunnel(
            name=self.tunnel_name,
            user='somebody',
            server='somewhere',
            local_port=2323,
            remote_port=3434,
        )
        tunnel_config = {
            self.tunnel_name: {
                'user': self.tunnel.user,
                'server': self.tunnel.server,
                'local_port': self.tunnel.local_port,
                'remote_port': self.tunnel.remote_port,
            }
        }
        group_config = {
            self.group_name: [(self.tunnel_name, None)],
        }

        self.config = Configuration(
            common={'default_user': 'testuser'},
            tunnels=tunnel_config,
            groups=group_config
        )
        self.empty_config = Configuration({}, {}, {})

        self.tunneler = Tunneler(self.process_helper, self.empty_config)

    def test_start_with_group(self):
        self.tunneler.config = self.config
        with patch.object(self.tunneler, '_start_group') as _start_group_stub:
            self.tunneler.start(self.group_name)
            _start_group_stub.assert_called_once_with(self.group_name)

    def test_start_with_tunnel(self):
        self.tunneler.config = self.config
        with patch.object(self.tunneler, '_start_tunnel') as _start_tunnel_stub:
            self.tunneler.start(self.tunnel_name)
            _start_tunnel_stub.assert_called_once_with(self.tunnel_name)

    def test_get_configured_groups(self):
        self.tunneler.config = self.config
        self.assertEqual([self.group_name], self.tunneler.get_configured_groups())

    def test_identify_tunnel_with_one_found(self):
        name = 'testserver'
        fullname = 'fullserver.name'
        port = 42

        tunnel_config = {
            'server': fullname,
            'remote_port': port,
        }
        self.tunneler.config = Configuration(
            common={},
            tunnels={name: tunnel_config},
            groups={},
        )

        result = self.tunneler.identify_tunnel(fullname, port)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], name)

    def test_identify_tunnel_with_more_than_one_found(self):
        name = 'testserver'
        name2 = 'testserver-clone'
        fullname = 'fullserver.name'
        port = 42

        tunnel_config = {
            'server': fullname,
            'remote_port': port,
        }
        self.tunneler.config = Configuration(
            common={},
            tunnels={name: tunnel_config, name2: tunnel_config},
            groups={},
        )

        result = self.tunneler.identify_tunnel(fullname, port)
        self.assertEqual(len(result), 2)
        self.assertEqual(set(result), set([name, name2]))

    def test_identify_tunnel_when_not_found(self):
        with self.assertRaises(LookupError):
            self.tunneler.identify_tunnel('someserver.somewhere', 69)

    def test_identify_groups(self):
        group_config = {
            'group1': [('tunnel1', None), ('tunnel2', 1234)],
            'group2': [('tunnel3', None)],
        }
        self.tunneler.config = Configuration(
            common={},
            tunnels={},
            groups=group_config,
        )

        result = self.tunneler.identify_group([])
        self.assertEqual(result, [])

        result = self.tunneler.identify_group(['tunnel1', 'tunnel2'])
        self.assertEqual(result, ['group1'])

        result = self.tunneler.identify_group(['tunnel1', 'tunnel4'])
        self.assertEqual(result, [])

        result = self.tunneler.identify_group(
            ['tunnel1', 'tunnel2', 'tunnel3']
        )
        self.assertEqual(result, ['group1', 'group2'])

    def test_get_configured_tunnels(self):
        tunnel_config = {'a': None, 'b': None}
        self.tunneler.config = Configuration(
            common={},
            tunnels=tunnel_config,
            groups={},
        )

        configured_tunnels = self.tunneler.get_configured_tunnels()
        self.assertEqual(set(configured_tunnels), set(tunnel_config.keys()))

    def test_get_configured_tunnels_with_filtering(self):
        tunnel_config = {'a': None, 'b': None}
        self.tunneler.config = Configuration(
            common={},
            tunnels=tunnel_config,
            groups={},
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

    def test_get_active_tunnel_when_active_and_in_config(self):
        self.process_helper.get_active_tunnels = Mock(
            return_value=[self.tunnel])
        self.tunneler.config = self.config
        found_tunnel = self.tunneler.get_active_tunnel(self.tunnel_name)
        self.assertEqual(self.tunnel, found_tunnel)

    def test_get_active_tunnel_when_active_and_not_in_config(self):
        self.process_helper.get_active_tunnels = Mock(
            return_value=[self.tunnel])
        self.tunneler.config = self.empty_config
        with self.assertRaises(NameError):
            self.tunneler.get_active_tunnel(self.tunnel_name)

    def test_get_active_tunnel_when_not_active_and_in_config(self):
        self.process_helper.get_active_tunnels = Mock(return_value=[])
        self.tunneler.config = self.config
        with self.assertRaises(NameError):
            self.tunneler.get_active_tunnel(self.tunnel_name)

    def test_get_active_tunnel_when_not_active_and_not_in_config(self):
        self.process_helper.get_active_tunnels = Mock(return_value=[])
        self.tunneler.config = self.empty_config
        with self.assertRaises(NameError):
            self.tunneler.get_active_tunnel('idonotexist')

    def test_is_tunnel_active(self):
        tunnel_config = {'server1': None, 'server2': None}
        self.tunneler.config = Configuration(
            common={},
            tunnels=tunnel_config,
            groups={},
        )
        self.tunneler.get_active_tunnel = Mock(
            side_effect=[Tunnel(), NameError])
        self.assertTrue(self.tunneler.is_tunnel_active('server1'))
        self.assertFalse(self.tunneler.is_tunnel_active('server2'))

    def test_get_active_tunnels(self):
        self.tunneler.config = self.config
        self.process_helper.get_active_tunnels = Mock(
            return_value=[self.tunnel])

        result = self.tunneler.get_active_tunnels()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], self.tunnel_name)

    def test_get_active_tunnels_handle_unknown(self):
        unknown_tunnel = Tunnel(name='iamnotinconfig')
        self.process_helper.get_active_tunnels = Mock(
            return_value=[unknown_tunnel])

        result = self.tunneler.get_active_tunnels()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], 'Unknown')

    def test_start_tunnel(self):
        self.tunneler.config = self.config
        self.tunneler.get_active_tunnel = Mock(side_effect=NameError)
        self.process_helper._start_tunnel = Mock(return_value=True)

        result = self.tunneler._start_tunnel(self.tunnel_name)

        self.assertEqual(self.process_helper.start_tunnel.call_count, 1)
        self.assertEqual(result, [(self.tunnel_name, self.tunnel.local_port)])

    def test_start_tunnel_if_command_fails(self):
        self.tunneler.config = self.config
        self.tunneler.get_active_tunnel = Mock(side_effect=NameError)
        self.process_helper.start_tunnel = Mock(return_value=False)

        [(name, result)] = self.tunneler._start_tunnel(self.tunnel_name)
        self.assertEquals(name, self.tunnel_name)
        self.assertTrue(
            'somebody@somewhere' in result
            and '2323' in result
            and '3434' in result
        )

    def test_start_tunnel_if_already_active(self):
        self.tunneler.config = self.config
        self.tunneler.get_active_tunnel = Mock(return_value=object())

        result = self.tunneler._start_tunnel(self.tunnel_name)
        self.assertEqual(result, [(self.tunnel_name, 'already running')])

    def test_stop_with_tunnel(self):
        self.tunneler.config = self.config
        self.tunneler._stop_group = Mock()
        self.tunneler._stop_tunnel = Mock()

        self.tunneler.stop(self.tunnel_name)
        self.assertFalse(self.tunneler._stop_group.called)
        self.assertTrue(self.tunneler._stop_tunnel.called)

    def test_stop_with_group(self):
        self.tunneler.config = self.config
        self.tunneler._stop_group = Mock()
        self.tunneler._stop_tunnel = Mock()

        self.tunneler.stop(self.group_name)
        self.assertTrue(self.tunneler._stop_group.called)
        self.assertFalse(self.tunneler._stop_tunnel.called)

    def test_stop_group(self):
        self.tunneler.config = self.config
        self.tunneler._stop_tunnel = Mock(return_value=[True])

        # Stop group is a generator!
        result = list(self.tunneler._stop_group(self.group_name))

        self.assertEqual(result, [True])
        self.assertEqual(self.tunneler._stop_tunnel.call_count, 1)

    def test_stop_tunnel(self):
        self.tunneler.config = self.config
        self.tunneler.get_active_tunnel = Mock(return_value=object())
        self.process_helper._stop_tunnel = Mock(return_value=True)

        result = self.tunneler._stop_tunnel(self.tunnel_name)

        self.assertEqual(self.process_helper.stop_tunnel.call_count, 1)
        self.assertTrue(result)

    def test_stop_tunnel_if_command_fails(self):
        self.tunneler.config = self.config
        self.tunneler.get_active_tunnel = Mock(return_value=object())
        self.process_helper.stop_tunnel = Mock(return_value=False)

        result = self.tunneler._stop_tunnel(self.tunnel_name)

        self.assertEquals(result, [(self.tunnel_name, False)])

    def test_stop_tunnel_if_already_inactive(self):
        self.tunneler.config = self.config
        self.tunneler.get_active_tunnel = Mock(side_effect=NameError)

        result = self.tunneler._stop_tunnel(self.tunnel_name)

        self.assertEqual(result, [(self.tunnel_name, False)])

    def test_stop_all_tunnels(self):
        active_tunnels = [(self.tunnel_name, self.tunnel), ('Unknown', None)]
        self.tunneler.get_active_tunnels = Mock(return_value=active_tunnels)
        self.tunneler._stop_tunnel = Mock(return_value='True')

        result = self.tunneler.stop_all_tunnels()

        self.assertEqual(len(result), 1)
        self.assertEqual(
            self.tunneler._stop_tunnel.call_count, 1)
