#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

import logging

from cinder import context as cinder_context
import cinder.exception
from cinder import objects
objects.register_all()
from cinder.db.sqlalchemy import api as cinder_db
from cinder import rpc
from cinder.transfer import api as transfer_api
from oslo_config import cfg

from oschown import base
from oschown import exception

# Not sure why but this has to happen at import time where our config
# is set properly
cfg.CONF([], project='cinder')
CONF = cfg.CONF
rpc.init(CONF)
TRANSFER_API = transfer_api.API()

LOG = logging.getLogger(__name__)


class CinderResource(base.ChownableResource):
    def __init__(self, volume):
        self._volume = volume
        self._admin_ctx = cinder_context.get_admin_context()
        self._deps = []
        self._collect_instances()

    def _collect_instances(self):
        if self._volume.volume_attachment:
            for attachment in self._volume.volume_attachment:
                LOG.info('Cinder volume %s requires attached instance %s' % (
                    self._volume.id, attachment.instance_uuid))
                self._deps.append('nova:%s' % attachment.instance_uuid)

    @property
    def dependencies(self):
        return self._deps

    @property
    def identifier(self):
        return 'cinder:%s' % self._volume['id']

    def _set_vol_state(self, state):
        cinder_db.volume_update(self._admin_ctx, self._volume['id'],
                                {'status': 'available'})

    def chown(self, context):
        orig_state = self._volume['status']
        # NOTE(danms): The transfer API trivially blocks the operation
        # on in-use volumes. So, we cheat here and hack the status so
        # that we can push it through and then reset it when we are done.
        # It would be nice if we could get an ignore_state=True flag to the
        # transfer api create method for this usage, but not sure if the
        # cinder people would be up for that.
        # FIXME(danms): Log/print a warning here if we are operating
        # on an in-use volume.
        self._set_vol_state('available')
        try:
            transfer_spec = TRANSFER_API.create(self._admin_ctx,
                                                self._volume['id'],
                                                'oschown')
            user_ctx = cinder_context.RequestContext(
                context.target_user_id,
                context.target_project_id)
            TRANSFER_API.accept(user_ctx,
                                transfer_spec['id'],
                                transfer_spec['auth_key'])
        finally:
            self._set_vol_state(orig_state)


class CinderProject(base.ChownableProject):
    def __init__(self):
        super(CinderProject, self).__init__()

    @property
    def name(self):
        return 'cinder'

    def collect_resource_by_id(self, context, resource_id):
        ctx = cinder_context.get_admin_context()
        try:
            vol = objects.Volume.get_by_id(ctx, resource_id)
        except cinder.exception.VolumeNotFound:
            raise exception.UnableToResolveResources(
                'Cinder volume %s not found' % resource_id)
        resource = CinderResource(vol)
        self._resources.append(resource)
        return resource
