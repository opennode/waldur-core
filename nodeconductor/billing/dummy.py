
class DummyDataSet(object):
    PRICELIST = dict(
        core=1000,
        ram_mb=500,
        storage_mb=300,
        license_type=700,
    )

    INVOICES = (
        {
            'year': 2015,
            'month': 3,
            'amount': 10.00,
            'customer_uuid': '690c89287ad4480fbc82212f307a0d0e',
            'customer_name': 'Alice',
            'customer_native_name': 'Alice C.',
            'uuid': '6e08f48681834ba5aadd426a0abe9282',
        },
        {
            'year': 2015,
            'month': 4,
            'amount': -3.75,
            'customer_uuid': '690c89287ad4480fbc82212f307a0d0e',
            'customer_name': 'Alice',
            'customer_native_name': 'Alice C.',
            'uuid': '2836139c25ce4a709175598b9d31e7ef',
        },
        {
            'year': 2015,
            'month': 4,
            'amount': 15.00,
            'customer_uuid': '5bd9f82e0ccf4c1f9ed6c83dd546bf33',
            'customer_name': 'Bob',
            'customer_native_name': 'Bobby Z.',
            'uuid': 'b3224126ea64424696101a70c68417a8',
        },
    )

    @classmethod
    def invoices_queryset(cls):
        class Invoice(object):
            def __init__(self, data):
                self.__dict__.update(data)
                self.pk = self.uuid

        return [Invoice(obj) for obj in cls.INVOICES]
