============================
Run the project using Docker
============================
This How-To shows you how to run django, postgres and celery in Docker
containers.

The assumption is that you have `Docker Engine <https://docs.docker.com/engine/>`_
and `docker-compose <https://github.com/docker/compose>`_ (Version 2), or
`Docker Desktop <https://docs.docker.com/desktop/>`_ installed.

The ``docker-compose.yml`` defines services for all the components: postgres, celery,
django, etc. Run the project site using:

..  code-block:: shell

    docker compose up

It will take a few, actually several, moments to download and build the
images and run the containers. However, that is all there is to it.

Changing the configuration
--------------------------
The ``docker-compose.yml`` is configured with sensible defaults, so everything
runs out of the box. If you need to change the configuration the ``.env.example``
file contains a complete list of variables that are used to configure the
containers or are used for Django settings. Create a copy and adjust it to
match your local environment:

..  code-block:: shell

    cp .env.example .env

You can then set the environment variables using:

..  code-block:: shell

    set -o allexport
    source .env
    set +o allexport

There is also a docker compose override file, docker-compose.override.yml.example.
This can be used to customise the configuration for different environments. The
example file maps the ports for PostgreSQL and RabbitMQ locally so you can use
tools like `Flower: <https://flower.readthedocs.io/en/latest/>`_ to monitor the
services in development. Create a copy, and it will be merged with `docker-compose.yml`
the next time you bring up the containers:

..  code-block:: shell

    cp docker-compose.override.yml.example docker-compose.override.yml

Using direnv
------------
If you install `direnv <https://direnv.net/>`_, then whenever you cd to the project
directory you can automatically set the environment variables.

The root directory contains a ``.envrc`` configuration file so once direnv
is installed all you have to do is whitelist it:

..  code-block:: shell

    direnv allow .
