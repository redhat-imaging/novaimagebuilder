# coding=utf-8

#   Copyright 2013 Red Hat, Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import tempfile
import os
from unittest import TestCase
from novaimagebuilder.CacheManager import CacheManager
from tests.MockOS import MockOS
from tests.MockStackEnvironment import MockStackEnvironment


class TestCacheManager(TestCase):
    def setUp(self):
        self.cache_mgr = CacheManager()
        self.cache_mgr.env = MockStackEnvironment()
        self.os_dict = {'shortid': 'mockos'}
        self.install_config = {'arch': 'mockarch'}
        self.os = MockOS(self.os_dict, 'mock-install', 'nowhere', self.install_config)
        self.tmp_file = tempfile.NamedTemporaryFile(delete=False)
        self.tmp_file.close()

    def tearDown(self):
        os.remove(self.tmp_file.name)
        del self.tmp_file
        del self.cache_mgr
        del self.os

    def test_lock_and_get_index(self):
        self.assertIsNone(self.cache_mgr.index)
        self.cache_mgr.lock_and_get_index()
        self.assertIsNotNone(self.cache_mgr.index)
        self.assertIsInstance(self.cache_mgr.index, dict)

    def test_write_index_and_unlock(self):
        self.cache_mgr.lock_and_get_index()
        self.cache_mgr._set_index_value('TestOS1', 'Test', 'nowhere', True)
        self.cache_mgr._set_index_value('TestOS2', 'Test', None, {'aTest': True})
        self.assertRaises(Exception, self.cache_mgr._set_index_value, ('TestOS3', 'Test', None, 0))
        self.cache_mgr.write_index_and_unlock()
        self.assertIsNone(self.cache_mgr.index)
        self.cache_mgr.lock_and_get_index()
        self.assertTrue(self.cache_mgr._get_index_value('TestOS1', 'Test', 'nowhere'))
        self.assertIsInstance(self.cache_mgr._get_index_value('TestOS2', 'Test', None), dict)
        self.assertIsNone(self.cache_mgr.index.get('TestOS3'))
        try:
            del self.cache_mgr.index['TestOS1']
            del self.cache_mgr.index['TestOS2']
            self.cache_mgr.write_index_and_unlock()
        except KeyError:
            pass

    def test_unlock_index(self):
        self.cache_mgr.lock_and_get_index()
        self.assertIsNotNone(self.cache_mgr.index)
        self.cache_mgr.unlock_index()
        self.assertIsNone(self.cache_mgr.index)

    def test_retrieve_and_cache_object(self):
        locations = self.cache_mgr.retrieve_and_cache_object('mock-obj', self.os, 'file://' + self.tmp_file.name, False)
        self.assertIsNotNone(locations)
        self.assertIsInstance(locations, dict)
        try:
            self.cache_mgr.lock_and_get_index()
            del self.cache_mgr.index['%s-%s' % (self.os_dict['shortid'], self.install_config['arch'])]
            self.cache_mgr.write_index_and_unlock()
        except KeyError:
            pass