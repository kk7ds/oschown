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
import nova.conf
from nova import config
from nova import context as nova_context
from nova.db.sqlalchemy import api as nova_db
from nova.db.sqlalchemy import models as nova_db_models
from nova import objects

from oschown import base
from oschown import exception

LOG = logging.getLogger(__name__)


class NovaResource(base.ChownableResource):
    def __init__(self, instance):
        self._admin_ctx = nova_context.get_admin_context()
        self._instance = instance
        self._deps = []
        self._collect_volumes()
        self._collect_ports()

    def _collect_volumes(self):
        bdms = objects.BlockDeviceMappingList.get_by_instance_uuids(
            self._admin_ctx, [self._instance['uuid']])
        for bdm in bdms:
            if bdm.is_volume:
                LOG.info('Nova instance %s requires attached volume %s' % (
                    self._instance['uuid'], bdm.volume_id))
                self._deps.append('cinder:%s' % bdm.volume_id)

    def _collect_ports(self):
        info = objects.InstanceInfoCache.get_by_instance_uuid(
            self._admin_ctx, self._instance['uuid'])
        for port in info.network_info:
            LOG.info('Nova instance %s requires port %s' % (
                self._instance['uuid'], port['id']))
            self._deps.append('neutron:%s' % port['id'])

    @property
    def dependencies(self):
        return self._deps

    @property
    def identifier(self):
        return 'nova:%s' % self._instance['uuid']

    def _chown_instance_record(self, ctx, context):
        nova_db.instance_update(ctx, self._instance['uuid'],
                                {'project_id': context.target_project_id,
                                 'user_id': context.target_user_id})

    def _chown_instance_mapping(self, ctx, context):
        im = objects.InstanceMapping.get_by_instance_uuid(
            ctx, self._instance['uuid'])
        im.project_id = context.target_project_id
        im.save()

    @staticmethod
    @nova_db.pick_context_manager_writer
    def _chown_actions_db(ctx, context, instance_uuid):
        query = nova_db.model_query(ctx, nova_db_models.InstanceAction)
        query = query.filter_by(instance_uuid=instance_uuid)
        action_ids = []
        for action in query.all():
            action_ids.append(action.id)
            action.project_id = context.target_project_id
            action.user_id = context.target_user_id
            ctx.session.add(action)
        return action_ids

    def _chown_instance_actions(self, ctx, context):
        action_ids = self._chown_actions_db(ctx, context,
                                            self._instance['uuid'])
        for action_id in action_ids:
            LOG.info('Changing ownership of instance action %i' % action_id)

    def chown(self, context):
        self._chown_instance_record(self._admin_ctx, context)
        self._chown_instance_mapping(self._admin_ctx, context)
        self._chown_instance_actions(self._admin_ctx, context)


class NovaProject(base.ChownableProject):
    def __init__(self):
        super(NovaProject, self).__init__()
        self.conf = nova.conf.CONF
        config.parse_args([])
        objects.register_all()

    @property
    def name(self):
        return 'nova'

    def check(self, context):
        objects.Instance
        pass

    def collect_resources_by_owner(self, context, user_id, project_id):
        ctx = nova_context.RequestContext(user_id, project_id)
        insts = nova_db.instance_get_all_by_filters_sort(ctx, {})
        for inst in insts:
            if inst['deleted']:
                continue
            resource = NovaResource(inst)
            self._resources.append(resource)

    def collect_resource_by_id(self, context, resource_id):
        ctx = nova_context.get_admin_context()
        try:
            inst = nova_db.instance_get_by_uuid(ctx, resource_id)
        except nova.exception.InstanceNotFound:
            raise exception.UnableToResolveResources(
                'Nova instance %s not found' % resource_id)
        resource = NovaResource(inst)
        self._resources.append(resource)
        return resource
