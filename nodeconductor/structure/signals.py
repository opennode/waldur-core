from django.dispatch import Signal

# Role related signals
# sender = structure class, e.g. Customer or Project
structure_role_granted = Signal(providing_args=['structure', 'user', 'role'])
structure_role_revoked = Signal(providing_args=['structure', 'user', 'role'])

# Resource related signals
# sender = resource class
project_resource_added = Signal(providing_args=['project', 'resource', 'membership'])
project_resource_removed = Signal(providing_args=['project', 'resource', 'membership'])

customer_account_credited = Signal(providing_args=['instance', 'amount'])
customer_account_debited = Signal(providing_args=['instance', 'amount'])

resource_imported = Signal(providing_args=['instance'])
