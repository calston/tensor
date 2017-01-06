from setuptools import setup, find_packages


setup(
    name="tensor",
    version='1.0.0',
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
        'construct<2.6',
        'pysnmp==4.2.5',
        'cryptography',
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
