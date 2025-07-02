from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in dokos_woocommerce/__init__.py
from dokos_woocommerce import __version__ as version

setup(
	name="dokos_woocommerce",
	version=version,
	description="WooCommerce Integration for Dokos",
	author="Dokos SAS",
	author_email="hello@dokos.io",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
