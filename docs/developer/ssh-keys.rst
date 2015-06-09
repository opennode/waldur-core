Propagate SSH keys
==================

Users' SSH public keys are automatically synced with cloud Service backend when required:

* After Service Project Link creation: propagate SSH keys of all users from a link project to backend
* On adding/removing user's SSH key: add or remove it from related backend respectively
* On adding/removing user to a Project: ditto

All SSH keys are identified by fingerprint in order to avoid duplicates.
