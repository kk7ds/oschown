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


class ChownContext(object):
    """A context object for a given chown operation."""

    def __init__(self, target_user_id, target_project_id,
                 dry_run=False):
        self.target_user_id = target_user_id
        self.target_project_id = target_project_id
        self.dry_run = dry_run


class ChownableResource(object):
    """A chown'able resource in a specific project."""

    @property
    def identifier(self):
        """Return an identifier like project:id."""

        return '%s:0' % self.__class__.__name__

    @property
    def dependencies(self):
        """Return a list of dependency resource identifiers.

        The resource identifiers are those that need to be chown'ed
        along with this resource. These can be resources on the same
        project or another project.
        """

        return []

    def chown(self, context):
        """Actually change ownership of this resource."""

        pass


class ChownableProject(object):
    """Base class for a project that supports oschown.

    This represents a project that has some resources which may need
    to be chown'd. When the query methods are called, the project
    should collect resources based on ChownableResource in the
    @resources field.
    """

    def __init__(self):
        self._resources = []

    @property
    def name(self):
        """The nice name of the project"""
        return self.__class__.__name__

    @property
    def resources(self):
        """Return the list of resources collected by the project."""
        return self._resources

    def check(self, context):
        pass

    def collect_resources_by_owner(self, context, user_id, project_id):
        """Collect all resources owned by @user_id and @project_id."""
        pass

    def collect_resource_by_id(self, context, resource_id):
        """Collect a specific resource by id."""
        pass
