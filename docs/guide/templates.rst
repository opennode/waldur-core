Templates workflow
------------------

1. Staff defines a template group through admin interfaces and links several
templates to it. A template corresponds to provisioning of a resource and allows
to set default options.

2. Project administrator or customer owner executes "provision" action of the
template groups with passing additional options required for provisioning of the
resources. Respone of the "provision" action will contain
provision state description and links to provisioned resources or error messages
should an exception occur.