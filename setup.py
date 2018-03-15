'''
usage:
 (sudo) python setup.py +
	 install		... local
	 register		... at http://pypi.python.org/pypi
	 sdist			... create *.tar to be uploaded to pyPI
	 sdist upload	... build the package and upload in to pyPI
'''


from setuptools import setup, find_packages
import os


def read(*paths):
    """Build a file path from *paths* and return the contents."""
    try:
        f_name = os.path.join(*paths)
        with open(f_name, 'r') as f:
            return f.read()
    except IOError:
        print('%s not existing ... skipping' % f_name)
        return ''


setup(
    name='dAwebAPI',
    version='0.1',
    author='Karl Bedrich',
    author_email='karl.bedrich@nus.edu.sg',
    url='https://github.com/radjkarl/daWebApi',
    license='GPL v3',
    description='A Python library to access dA-compatible webAPIs',
    install_requires=[],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Other Audience',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    packages=find_packages(exclude=['tests*']),
    include_package_data=True,
    package_data={
        '': ['*.pdf'],
    },
    scripts=[] if not os.path.exists('bin') else [
        os.path.join('bin', x) for x in os.listdir('bin')],
    long_description=(
        read('README.rst') + '\n\n' +
        read('CHANGES.rst') + '\n\n' +
        read('AUTHORS.rst')
    ),
)
