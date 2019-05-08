import setuptools

setuptools.setup(
    setup_requires=['setuptools-odoo'],
    odoo_addon={
        'external_dependencies_override': {
            'python': {
                'swiftclient': 'python-swiftclient>=3.7.0',
                'keystoneclient': 'python-keystoneclient>=3.19.0',
                'keystoneauth1': 'keystoneauth1>=3.14.0',
            },
        },
    }
)
