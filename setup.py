from setuptools import setup, find_packages


setup(
    name="tensor",
    version='0.2.6',
    url='http://github.com/calston/tensor',
    license='MIT',
    description="A Twisted based monitoring agent for Riemann",
    author='Colin Alston',
    author_email='colin.alston@gmail.com',
    packages=find_packages() + [
        "twisted.plugins",
    ],
    package_data={
        'twisted.plugins': ['twisted/plugins/tensor_plugin.py']
    },
    include_package_data=True,
    install_requires=[
        'Twisted',
        'PyYaml',
        'protobuf',
        'construct',
        'pysnmp',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Topic :: System :: Monitoring',
    ],
)
