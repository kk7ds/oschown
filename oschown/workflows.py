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
import mock
import oslo_config.cfg

nova_conf = oslo_config.cfg.ConfigOpts()
cinder_conf = oslo_config.cfg.ConfigOpts()


# NOTE(danms): This is a crazy hack to import these project modules
# but with separated global oslo.config objects. Hopefully I can
# replace this with something that isn't quite as crazy (and at least
# doesn't use mock), but this works for testing.
with mock.patch('oslo_config.cfg.CONF', new=cinder_conf):
    from oschown import chown_cinder

with mock.patch('oslo_config.cfg.CONF', new=nova_conf):
    from oschown import chown_nova

from oschown import chown_neutron

from oschown import exception

LOG = logging.getLogger(__name__)


def parse_resource_id(resource_id):
    return resource_id.split(':', 1)


class ResourceCollection(object):
    """A collection of resources across projects.

    Collects resources that must be resolved and chown'ed together.
    """

    RESOURCE_TYPES = {
        'cinder': chown_cinder.CinderProject(),
        'nova': chown_nova.NovaProject(),
        'neutron': chown_neutron.NeutronProject(),
    }

    def __init__(self, context):
        self._collected_resources = {}
        self._context = context

    def need_resource(self, resource_id):
        """Mark a resource id like project:id as needed for resolution.

        Needed resources must be chown'ed with the other resources in
        the collection.
        """

        if resource_id not in self._collected_resources:
            self._collected_resources[resource_id] = None

    @property
    def resolved_resources(self):
        """A list of ChownableResource objects that have been resolved."""

        return [res for res in self._collected_resources.values()
                if res is not None]

    @property
    def unresolved_resources(self):
        """A list of resource identifiers that are yet unresolved."""

        return [r_id for r_id, r_res in self._collected_resources.items()
                if r_res is None]

    @property
    def have_all_resources(self):
        """Return whether or not all known resources have been resolved."""

        return len(self.unresolved_resources) == 0

    def resolve_missing_resources_one(self):
        """One pass of resource resolution.

        Make one pass through the list of unresolved resources and try
        to resolve them (collecting any additional dependencies.
        """

        for resource_id in self.unresolved_resources:
            project_id, local_id = parse_resource_id(resource_id)
            if project_id not in self.RESOURCE_TYPES:
                raise exception.UnknownResourceType()

            project = self.RESOURCE_TYPES[project_id]
            resource = project.collect_resource_by_id(self._context,
                                                      local_id)
            self._collected_resources[resource_id] = resource
            for dep in resource.dependencies:
                self.need_resource(dep)

    def resolve_missing_resources(self):
        """Resolve all resources.

        Attempt to repeatedly resolve all resources in the list of
        needed ones. This runs until we have resolved all resources or
        we stop making progress.

        :raises: exception.UnableToResolveResources if some resources are not
                 resolvable
        """

        last_unresolved = None
        while not self.have_all_resources:
            self.resolve_missing_resources_one()
            now_unresolved = self.unresolved_resources
            if now_unresolved == last_unresolved:
                raise exception.UnableToResolveResources()
            last_unresolved = now_unresolved

    def chown_resources(self):
        """Actually change ownership of all resources in the collection.

        Does not actually change ownership if the context indicates a dry run
        should be performed.
        """

        for resource in self.resolved_resources:
            if self._context.dry_run:
                LOG.info('Would chown resource %s' % resource.identifier)
            else:
                LOG.info('Chowning resource %s' % resource.identifier)
                resource.chown(self._context)


def _workflow_main(context, collection):
    try:
        collection.resolve_missing_resources()
    except exception.ChownException as e:
        LOG.error('Unable to resolve resources: %s' % e)
        return

    LOG.info('Resolved %i resources to be chowned: %s' % (
        len(collection.resolved_resources),
        ','.join([r.identifier for r in collection.resolved_resources])))

    collection.chown_resources()


def workflow_nova(context, instance_id):
    """Resolve and change ownership of an instance and dependent resources."""

    collection = ResourceCollection(context)
    collection.need_resource('nova:%s' % instance_id)
    _workflow_main(context, collection)


def workflow_cinder(context, volume_id):
    """Resolve and change ownership of a volume and dependent resources."""

    collection = ResourceCollection(context)
    collection.need_resource('cinder:%s' % volume_id)
    _workflow_main(context, collection)
