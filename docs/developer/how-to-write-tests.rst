How to write tests
==================

Application tests structure
---------------------------

Application tests should follow next structure:

 - **/tests/**  -  folder, contains all application tests.
 - **/tests/test_my_entity.py**  - file, contains API calls tests that are logically related
                               to entity. Example: test calls for project CRUD + actions.
 - **/tests/test_my_entity.py:MyEntityActionTest**  -  class, contains tests that are related
                                                       to particular endpoint. Examples: 
                                                       ProjectCreateTest, InstanceResizeTest.
 - **/tests/unittests/**  -  folder, contains unittests for particular file.
 - **/tests/unittests/test_file_name.py**  -  file, contains test of classes and methods from 
                                          application file "file_name". Examples:
                                          test_models.py, test_handlers.py.


Tips for writing tests
----------------------

 - cover important or complex functions and methods with unittests;
 - write at least one test for a positive flow for each endpoint;
 - do not write tests for actions that does not exist. If you don't support 
   "create" action for any user there is no need to write test for that.
