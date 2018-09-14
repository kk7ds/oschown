OpenStack Ownership Transfer Utility
====================================

What is oschown?
----------------

* ``oschown`` is an operator tool that aims to provide a canonical
  solution for transferring ownership of resources in an openstack
  cloud.

* ``oschown`` is a workflow that links together multiple modules to
  handle dependent resources across projects to avoid a situation
  where (for example) an instance is transferred but its storage,
  network, etc resources are not.

* ``oschown`` is currently an orchestrated workflow of *hacks*, but
  is intended to be a *canonical hack* that can be reviewed for
  *relative safety* by projects to avoid operators needing to cook up
  local hacky solutions to this problem which may be incomplete and
  inconsistent.

Supported Resources and Status
------------------------------

* Nova: instances, cell mappings, instance actions (TODO)

* Cinder: volumes and snapshots

* Neutron: nothing (instances must be detached from all ports)

Exit codes
----------

* ``Code 0``: Resources were resolved and transferred
* ``Code 1``: Something went wrong

Usage and Theory of Operation
-----------------------------

Running oschown requires choosing a top-level workflow, which is done
by providing a root resource type and identifier. From that resource,
dependent resources are discovered and resolved in a loop until all
resources have been identified as supported, or no more progress can
be made. If all resources are resolved and supported, then the
ownership transfer will be completed.

Currently, all supported modules require a project-specific
configuration file with connectivity direct to the corresponding
database. Admin credentials are also required for validating and
normalizing the target project/user, unless validation is
disabled. Because the actual code for cinder and nova are used
directly, those python modules must be available.

Executing oschown with ``--help`` will provide a basic usage overview:

.. code-block:: console

    $ oschown --help
    usage: oschown [-h] [-v] [--dry-run] [--root-resource RESOURCE] [--root-id ID]
                   [--all-resources-for-project PROJECT] --target-project PROJECT
                   --target-user USER [--no-validate]
    
    optional arguments:
      -h, --help            show this help message and exit
      -v, --verbose         Enable verbose output
      --dry-run             Do not actually chown resources
      --root-resource RESOURCE
                            Resource type (cinder,nova)
      --root-id ID          Resource id
      --all-resources-for-project PROJECT
                            Move all resources in this project
      --target-project PROJECT
                            Change ownership of resources to this project
      --target-user USER    Change ownership of resources to this user
      --no-validate         Do not validate/normalize target user and project

Example Nova usage
------------------

Given a nova instance with the following state:

* Instance uuid a88e5c31-d6b8-4b18-a641-e4605d4355e3
* An attached volume 8a3cb0b0-0475-4360-a381-3b0290c9915e
* All network ports detached

An initial dry-run in verbose mode is advisable, which generates the
following output:

.. code-block:: console

    $ oschown --target-project demo --target-user demo --root-resource nova --root-id a88e5c31-d6b8-4b18-a641-e4605d4355e3 --dry-run -v
    INFO:Nova instance a88e5c31-d6b8-4b18-a641-e4605d4355e3 requires attached volume 8a3cb0b0-0475-4360-a381-3b0290c9915e
    INFO:Cinder volume 8a3cb0b0-0475-4360-a381-3b0290c9915e requires attached instance a88e5c31-d6b8-4b18-a641-e4605d4355e3
    INFO:Resolved 2 resources to be chowned: nova:a88e5c31-d6b8-4b18-a641-e4605d4355e3,cinder:8a3cb0b0-0475-4360-a381-3b0290c9915e
    INFO:Would chown resource nova:a88e5c31-d6b8-4b18-a641-e4605d4355e3
    INFO:Would chown resource cinder:8a3cb0b0-0475-4360-a381-3b0290c9915e

Assuming the planned actions look legitimate, running again without
``--dry-run`` will actually change resource ownership:

.. code-block:: console

    $ oschown --target-project demo --target-user demo --root-resource nova --root-id a88e5c31-d6b8-4b18-a641-e4605d4355e3 -v
    INFO:Nova instance a88e5c31-d6b8-4b18-a641-e4605d4355e3 requires attached volume 8a3cb0b0-0475-4360-a381-3b0290c9915e
    INFO:Cinder volume 8a3cb0b0-0475-4360-a381-3b0290c9915e requires attached instance a88e5c31-d6b8-4b18-a641-e4605d4355e3
    INFO:Resolved 2 resources to be chowned: nova:a88e5c31-d6b8-4b18-a641-e4605d4355e3,cinder:8a3cb0b0-0475-4360-a381-3b0290c9915e
    INFO:Chowning resource nova:a88e5c31-d6b8-4b18-a641-e4605d4355e3
    FIXME: Update instance action 25
    FIXME: Update instance action 10
    INFO:Chowning resource cinder:8a3cb0b0-0475-4360-a381-3b0290c9915e

Example Cinder usage
--------------------

If the primary desire is to change the ownership of a volume, provide
that cinder resource as the root. Any instances that have the volume
attached will be found and included if necessary.

.. code-block:: console

    $ oschown --target-project demo --target-user demo --root-resource cinder --root-id c732984d-21a3-4693-9ff4-f83653c63daa -v
