Sample data
===========

Sample data can be created using management command '``nodeconductor createsampledata``'.

It takes one parameter as input: sample data set

- **alice** - creates a structured set with relationships depicted below. String in a circle means username. Password
  is generated equal to the username. If user with such a username already exists, it will be left as is except for the
  staff flag.
- **random** - creates a random data set filling in all of the fields. Can be called multiple times to generate
  more data.

.. image:: ../images/testdata-alice.png


Other objects from alice dataset:
 - **resources** - project "bells.org" has 10 OpenStack instances
 - **OpenStackSettings** - settings with such attributes:

   .. code-block:: python

    {
        'auth_url': 'http://keystone.example.com:5000/v2.0',
        'username': 'test_user',
        'password': 'test_password',
        'tenant_name': 'test_tenant'
    }