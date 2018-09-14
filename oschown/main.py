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

import argparse
import logging
import os

import keystoneauth1.exceptions.http
from keystoneauth1.identity import v3 as keystone_v3
from keystoneauth1 import session as keystone_session
from keystoneclient.v3 import client as keystone_client

from oschown import base


WORKFLOW_TYPES = {}


def _configure_logging():
    logging.basicConfig(
        format='%(levelname)s:%(message)s',
        level=logging.WARNING)
    logging.getLogger('cinder').setLevel(logging.ERROR)
    logging.getLogger('castellan').setLevel(logging.ERROR)
    logging.getLogger('stevedore').setLevel(logging.ERROR)


def _get_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true',
                        default=False,
                        help='Enable verbose output')
    parser.add_argument('--dry-run', action='store_true',
                        default=False,
                        help='Do not actually chown resources')
    parser.add_argument('--root-resource', metavar='RESOURCE',
                        help='Resource type (%s)' % (
                            ','.join(WORKFLOW_TYPES.keys())))
    parser.add_argument('--root-id', metavar='ID',
                        help='Resource id')
    parser.add_argument('--all-resources-for-project', metavar='PROJECT',
                        help='Move all resources in this project')
    parser.add_argument('--target-project', required=True, metavar='PROJECT',
                        help='Change ownership of resources to this project')
    parser.add_argument('--target-user', required=True, metavar='USER',
                        help='Change ownership of resources to this user')
    parser.add_argument('--no-validate', action='store_true',
                        default=False,
                        help='Do not validate/normalize target '
                        'user and project')
    return parser


def _resolve_project(user_id, project_id):
    """Attempt to verify or normalize project and user id/names.

    Assumes standard OS_ environment variables for credentials.
    """
    auth = keystone_v3.Password(
        auth_url=os.getenv('OS_AUTH_URL') + '/v3',
        username=os.getenv('OS_USERNAME'),
        password=os.getenv('OS_PASSWORD'),
        project_name=os.getenv('OS_PROJECT_NAME'),
        user_domain_id=os.getenv('OS_USER_DOMAIN_ID'),
        project_domain_id=os.getenv('OS_PROJECT_DOMAIN_ID'))
    sess = keystone_session.Session(auth=auth)
    keystone = keystone_client.Client(session=sess)

    try:
        project = keystone.projects.find(name=project_id)
    except keystoneauth1.exceptions.http.NotFound:
        project = keystone.projects.find(id=project_id)

    try:
        user = keystone.users.find(name=user_id)
    except keystoneauth1.exceptions.http.NotFound:
        user = keystone.users.find(id=user_id)

    return user.id, project.id


def _populate_workflows():
    from oschown import workflows

    WORKFLOW_TYPES.update({
        'nova': workflows.workflow_nova,
        'cinder': workflows.workflow_cinder,
    })


def main():
    _configure_logging()
    _populate_workflows()
    parser = _get_arg_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    if args.no_validate:
        user_id = args.target_user
        project_id = args.target_project
    else:
        user_id, project_id = _resolve_project(
            args.target_user, args.target_project)

    context = base.ChownContext(user_id, project_id,
                                args.dry_run)

    if args.root_resource and args.root_id:
        workflow = WORKFLOW_TYPES.get(args.root_resource)
        if not workflow:
            print('No workflow for %s' % args.root_resource)
            return 1
        workflow(context, args.root_id)
    elif args.all_resources_for_project:
        # FIXME(danms): Go through all the workflows, collecting
        # resources by project id
        print('Not implemented')
    else:
        print('Use either --root-resource and --root-id or '
              '--all_resources_for_project')


if __name__ == '__main__':
    main()
